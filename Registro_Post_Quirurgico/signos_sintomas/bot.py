"""
Lógica del bot de WhatsApp para el seguimiento postoperatorio remoto.

Diseño:
- Lógica PURA respecto al transporte: `procesar_mensaje(telefono, texto)` recibe
  texto plano y devuelve texto plano. No conoce HTTP ni Twilio. La vista
  (views.py) traduce HTTP <-> esta función.
- El estado de la conversación se persiste en el modelo ConversacionWhatsApp,
  porque cada mensaje de WhatsApp llega como una petición independiente.
- El bot NO diagnostica ni muestra alertas al paciente. Solo captura telemetría,
  ejecuta el motor con estado persistente y responde una confirmación neutra.

Máquina de estados (10 preguntas):
    [AUXILIO — se mira ANTES que el estado, decisión D21]
      Si el mensaje trae ayuda / auxilio / socorro / emergencia como palabra
      suelta, en CUALQUIER estado incluido a mitad del cuestionario: se
      descarta el flujo en curso, se responde MSG_AUXILIO y se crea una
      alerta AUXILIO / ALTA. Va primero a propósito: el caso que originó la
      decisión ocurre a mitad del cuestionario, y mirarlo después dejaría
      "necesito ayuda" guardado como hinchazón.
    INICIO
      -> ESPERANDO_TEMPERATURA      admite "saltar" (D20) -> temperatura=None
                                    y responde con el eco: "Anoté: 37.5 °C."
      -> ESPERANDO_DOLOR            0-10, donde 0 = sin dolor (D20)
      -> ESPERANDO_TIENE_DRENAJE
      -> ESPERANDO_ASPECTO_DRENAJE    (se omite si tiene_drenaje=False)
      -> ESPERANDO_CANTIDAD_DRENAJE   (se omite si tiene_drenaje=False)
      -> ESPERANDO_GASES_NAUSEAS
      -> ESPERANDO_HINCHAZON
      -> ESPERANDO_FRECUENCIA_CARDIACA
      -> ESPERANDO_FRECUENCIA_RESPIRATORIA
      -> ESPERANDO_TOLERANCIA_LIQUIDOS
      -> COMPLETADO
"""

import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .alert_engine import registrar_alerta_auxilio
from .evaluacion_alertas import evaluar_registro_con_estado, registrar_fallo_evaluacion
from .models import (
    RANGOS_CLINICOS,
    CheckInProgramado,
    ConversacionWhatsApp,
    Paciente,
    RegistroDiario,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mensajes del bot — español coloquial, tuteo, tono cálido. NUNCA muestran
# alertas; la confirmación final es siempre neutra.
# ---------------------------------------------------------------------------
MSG_NO_REGISTRADO = (
    "Hola. Tu número aún no está registrado en nuestro programa de seguimiento. "
    "Por favor comunícate con tu médico para activarlo. Estamos para acompañarte."
)
MSG_SIN_CONSENTIMIENTO = (
    "Tu médico aún no ha confirmado tu registro en el sistema. "
    "Por favor contáctalo para completar el proceso de ingreso. "
    "Una vez confirmado, podrás comenzar tu seguimiento."
)
MSG_YA_REGISTRADO = (
    "¡Tus datos de hoy ya están registrados! "
    "Si tienes alguna duda sobre tu recuperación, puedes escribirme aquí."
)
MSG_SIN_CHECKIN = (
    "Por ahora no tienes un reporte pendiente. "
    "Te escribiré cuando sea la hora. "
    "Si tienes alguna duda sobre tu recuperación, puedes preguntarme aquí."
)
MSG_CONFIRMACION = (
    "¡Listo! Hemos registrado tu reporte de hoy. Gracias por cuidarte. "
    "Tu equipo médico está pendiente de tu seguimiento. ¡Que tengas un buen día!"
)
# Mensajes de cierre con recomendación según severidad de alertas
# (decisión clínica 02/07/2026 — tono tranquilizador, sin diagnóstico).
# Nunca mencionan el tipo de alerta ni valores específicos (regla del bot:
# el paciente jamás ve la clasificación clínica). BAJA no lleva mensaje
# adicional; usa MSG_CONFIRMACION.
MSG_CIERRE_ALERTA_MEDIA = (
    "Hemos registrado tu reporte de hoy.\n\n"
    "Hemos notado algunos valores que vale la pena revisar. "
    "Te recomendamos contactar a tu medico en las proximas "
    "horas para contarle como te has sentido. No es urgente, "
    "pero es importante que este al tanto.\n\n"
    "Te escribiremos en tu proximo turno."
)
MSG_CIERRE_ALERTA_ALTA = (
    "Hemos registrado tu reporte de hoy.\n\n"
    "Algunos de tus valores de hoy necesitan atencion pronto. "
    "Te recomendamos comunicarte con tu medico o dirigirte "
    "al servicio de urgencias mas cercano. Esto es por "
    "precaucion — ve con calma y cuentale al medico como "
    "te has sentido estos dias.\n\n"
    "Te escribiremos en tu proximo turno."
)
# --- Palabra de auxilio (decisión D21, 08/09/2026) ---
#
# Hasta hoy no existía ninguna forma de que el paciente saliera del
# cuestionario. "estoy sangrando mucho, necesito ayuda" escrito en la pregunta
# 7 se guardaba como `hinchazon='mucho'` y el bot pasaba a la pregunta 8.
#
# El mensaje NO diagnostica ni tranquiliza: manda a buscar atención. Es la única
# situación en la que el bot rompe su propia regla de no dar indicaciones, y es
# deliberado — aquí el silencio es peor que la indicación.
MSG_AUXILIO = (
    "Entiendo que necesitas ayuda. Detengo el reporte de hoy.\n\n"
    "*Si sientes que es una emergencia, llama al 123 o ve al servicio de "
    "urgencias más cercano ahora mismo.*\n\n"
    "También te recomiendo llamar a tu médico y contarle lo que está pasando. "
    "Ya avisé a tu equipo médico de que pediste ayuda.\n\n"
    "Cuando estés en un lugar seguro, escríbeme y retomamos tu reporte."
)

MSG_ABANDONO_REINICIO = (
    "Hola, parece que ayer no pudimos terminar tu reporte. "
    "Esos datos quedaron sin registrar.\n\n"
    "¡Empecemos el reporte de hoy!\n\n"
    "1. ¿Cuál es tu temperatura corporal? Escríbela en números, por ejemplo: 37.5"
)

MSG_PREGUNTA_TEMPERATURA = (
    "¡Hola! Vamos con tu reporte de hoy.\n\n"
    "Si en algún momento te sientes en peligro, escribe *AYUDA*.\n\n"
    "1. ¿Cuál es tu temperatura corporal? Escríbela en números, por ejemplo: 37.5\n"
    "(si hoy no tienes termómetro, responde *saltar*)"
)
MSG_REINTENTO_TEMPERATURA = (
    "No logré entender la temperatura.\n\n"
    "Escríbela con punto y un decimal, así: *37.5*\n"
    "(si escribes 375 o 37 5 no puedo saber si son 37.5 o 39)\n\n"
    "Si hoy no tienes termómetro, responde *saltar* y seguimos con el resto."
)

MSG_PREGUNTA_DOLOR = (
    "2. Del 0 al 10, ¿cuánto dolor sientes hoy?\n"
    "(0 es ninguno, 10 es insoportable)"
)
MSG_REINTENTO_DOLOR = (
    "Por favor envíame un número del 0 al 10 para indicar tu dolor. "
    "Si hoy no tienes dolor, responde 0."
)

MSG_PREGUNTA_TIENE_DRENAJE = (
    "3. ¿Tienes drenaje activo en este momento? Responde *sí* o *no*."
)
MSG_REINTENTO_TIENE_DRENAJE = (
    "No entendí tu respuesta. "
    "Por favor responde *sí* si tienes drenaje, o *no* si no tienes. "
    "Ejemplo: sí / no"
)

MSG_PREGUNTA_ASPECTO = (
    "4. ¿Cómo se ve el líquido del drenaje hoy? Responde con el número:\n"
    "1. Amarillo claro o rosado\n"
    "2. Rojo con sangre\n"
    "3. Amarillo turbio\n"
    "4. Amarillo verdoso o con pus\n"
    "5. Café oscuro o con olor muy fuerte"
)
MSG_REINTENTO_ASPECTO = (
    "Por favor responde con un número del 1 al 5 según cómo se ve tu drenaje."
)

MSG_PREGUNTA_CANTIDAD = (
    "5. ¿Cuánto líquido salió por el drenaje hoy?\n"
    "Responde: poco, normal o mucho.\n"
    "Si puedes medirlo, agrega los ml (ej: 'poco, 30ml')"
)
MSG_REINTENTO_CANTIDAD = (
    "No te entendí. Responde poco, normal o mucho "
    "(y si quieres, los ml, ej: 'normal, 50ml')."
)

MSG_PREGUNTA_GASES_NAUSEAS = (
    "6. Ya casi terminamos.\n"
    "¿Has podido pasar gases o ir al baño hoy? (sí/no)\n"
    "Y ¿cuántas veces has tenido náuseas o vómito hoy? (si ninguna, 0)\n"
    "Puedes responder así: 'sí, 0'"
)
MSG_REINTENTO_GASES_NAUSEAS = (
    "Por favor dime si pasaste gases (sí/no) y cuántas veces tuviste náuseas. "
    "Ejemplo: 'sí, 0' o 'no, 2'."
)
MSG_TURNO_SIGUIENTE = (
    "El reporte anterior se cerró, pero todavía tienes uno pendiente de hoy. "
    "¡Vamos con ese!\n\n"
    "1. ¿Cuál es tu temperatura corporal? Escríbela en números, por ejemplo: 37.5\n"
    "(si hoy no tienes termómetro, responde *saltar*)"
)

MSG_PREGUNTA_HINCHAZON = (
    "7. ¿Cómo siente la hinchazón o distensión de su abdomen hoy?\n"
    "Responda: *nada*, *algo* o *mucho*."
)
MSG_REINTENTO_HINCHAZON = (
    "No entendí. ¿Cómo siente la hinchazón de su abdomen? "
    "Responda *nada*, *algo* o *mucho*."
)

MSG_PREGUNTA_FRECUENCIA_CARDIACA = (
    "8. ¿Cuál es su frecuencia cardíaca (pulso) en este momento?\n"
    "Escriba el número de latidos por minuto, por ejemplo: 78.\n"
    "Si no puede medirla ahora, responda con alguna de estas palabras:\n"
    "*saltar · omitir · no sé · no tengo · sin dato*"
)
MSG_REINTENTO_FRECUENCIA_CARDIACA = (
    "No entendí. Escriba su frecuencia cardíaca en latidos por minuto (ej: 78), "
    "o responda *saltar* si no puede medirla ahora."
)

MSG_PREGUNTA_FRECUENCIA_RESPIRATORIA = (
    "9. ¿Cuál es su frecuencia respiratoria?\n"
    "Escriba el número de respiraciones por minuto, por ejemplo: 16.\n"
    "Si no puede medirla ahora, responda con alguna de estas palabras:\n"
    "*saltar · omitir · no sé · no tengo · sin dato*"
)
MSG_REINTENTO_FRECUENCIA_RESPIRATORIA = (
    "No entendí. Escriba su frecuencia respiratoria en respiraciones por minuto "
    "(ej: 16), o responda *saltar* si no puede medirla ahora."
)

MSG_PREGUNTA_TOLERANCIA_LIQUIDOS = (
    "10. Última pregunta.\n"
    "¿Ha podido tomar líquidos (agua, caldo, jugo) sin vomitar? "
    "Responda *sí* o *no*."
)
MSG_REINTENTO_TOLERANCIA_LIQUIDOS = (
    "No entendí su respuesta. ¿Pudo tomar líquidos sin vomitar? "
    "Responda *sí* o *no*."
)

# Respuestas predefinidas a dudas (espejo de knowledge_base.md mientras no haya RAG)
#
# D4: ninguna de estas respuestas puede contener un umbral clínico. El paciente
# no necesita auto-evaluarse — el sistema le pregunta la temperatura dos veces al
# día y el motor la evalúa. Un umbral aquí, además de contradecir al motor,
# rompe la regla no negociable de que el paciente nunca ve los valores que
# disparan una alerta. La redacción final está pendiente de validación médica:
# ver knowledge_base.md, sección "Consulta pendiente al médico".
RESP_FIEBRE = (
    "Registramos tu temperatura en cada reporte y tu equipo médico la está "
    "revisando. Si te sientes peor, con escalofríos o mucho malestar, "
    "comunícate con tu médico. Si es urgente, ve al servicio de urgencias."
)
RESP_COMER = (
    "La alimentación se recupera gradualmente. Sigue las indicaciones de tu médico."
)
RESP_DOLOR = (
    "Algo de molestia es esperado. Si el dolor es muy intenso o repentino, contacta "
    "a tu médico urgente."
)
RESP_FALLBACK = (
    "Para esa pregunta específica, te recomiendo contactar directamente a tu médico. "
    "Estamos aquí para tu seguimiento diario."
)


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def procesar_mensaje(telefono, texto):
    """Procesa un mensaje entrante y devuelve el texto de respuesta del bot."""
    telefono = _normalizar_telefono(telefono)
    texto = (texto or "").strip()

    paciente = Paciente.objects.filter(
        telefono_whatsapp=telefono, activo=True
    ).first()
    if paciente is None:
        return MSG_NO_REGISTRADO

    # Guard de consentimiento informado (HABEAS DATA — P-15, 01/07/2026).
    # El médico debe haber marcado consentimiento_informado=True antes de que
    # el paciente pueda usar el bot. Mensaje neutro: no menciona "consentimiento"
    # ni "datos" para no confundir al paciente — el médico tiene el contexto.
    if not paciente.consentimiento_informado:
        return MSG_SIN_CONSENTIMIENTO

    # A4: bloqueo transaccional — dos mensajes simultáneos del mismo paciente
    # (doble tap) esperan en cola en vez de leer/escribir el mismo estado.
    with transaction.atomic():
        conv, _ = ConversacionWhatsApp.objects.get_or_create(paciente=paciente)
        conv = ConversacionWhatsApp.objects.select_for_update().get(pk=conv.pk)
        hoy = timezone.localdate()

        return _procesar_con_conv(conv, paciente, texto, hoy)


def _procesar_con_conv(conv, paciente, texto, hoy):
    # D21 — el auxilio se atiende ANTES que el estado de la conversación.
    #
    # Va aquí arriba, y no dentro del despacho de cada pregunta, precisamente
    # porque el caso reproducido ocurre a mitad del cuestionario: si se mirara
    # después, "AYUDA" escrito en la pregunta 7 se seguiría guardando como
    # hinchazón. El flujo en curso se descarta: los datos parciales de un
    # paciente que está pidiendo socorro no valen nada frente a atenderlo.
    if _es_auxilio(texto):
        _limpiar_temporales(conv)
        _reiniciar(conv)
        registrar_alerta_auxilio(
            paciente,
            'El paciente pidió ayuda por WhatsApp durante el seguimiento. '
            'Se detuvo el cuestionario y se le indicó buscar atención '
            'inmediata. Contactar cuanto antes.',
        )
        return MSG_AUXILIO

    en_flujo = conv.estado not in (
        ConversacionWhatsApp.ESTADO_INICIO,
        ConversacionWhatsApp.ESTADO_COMPLETADO,
    )

    # A1: conversación abandonada a mitad de flujo en un día anterior.
    # Los datos parciales se descartan; el día anterior queda sin registro.
    if en_flujo and timezone.localdate(conv.fecha_actualizacion) < hoy:
        _limpiar_temporales(conv)
        # Si hay check-in PENDIENTE hoy, ir directo a TEMPERATURA (el mensaje
        # de abandono ya pregunta la temperatura — sin paso extra para el paciente).
        checkin_hoy = CheckInProgramado.objects.select_for_update().filter(
            paciente=paciente,
            fecha_dia=hoy,
            estado=CheckInProgramado.ESTADO_PENDIENTE,
        ).order_by('orden').first()
        conv.checkin_actual = checkin_hoy
        conv.estado = (
            ConversacionWhatsApp.ESTADO_TEMPERATURA if checkin_hoy
            else ConversacionWhatsApp.ESTADO_INICIO
        )
        conv.save()
        return MSG_ABANDONO_REINICIO

    # Si ya estamos en mitad del flujo de hoy, continuar respondiendo.
    if en_flujo:
        checkin = None
        if conv.checkin_actual_id is not None:
            checkin = CheckInProgramado.objects.select_for_update().filter(
                pk=conv.checkin_actual_id,
                paciente=paciente,
                estado=CheckInProgramado.ESTADO_PENDIENTE,
            ).first()
        else:
            # Compatibilidad con conversaciones iniciadas antes de la migración
            # que incorporó checkin_actual.
            checkin = CheckInProgramado.objects.select_for_update().filter(
                paciente=paciente,
                fecha_dia=hoy,
                estado=CheckInProgramado.ESTADO_PENDIENTE,
            ).order_by('orden').first()
            if checkin is not None:
                conv.checkin_actual = checkin
                conv.save(update_fields=['checkin_actual', 'fecha_actualizacion'])

        if checkin is None:
            # BE-01 — el turno guardado en la conversación ya no está
            # PENDIENTE (lo cerró el cron por vencido), pero eso NO significa
            # que el paciente no tenga nada que reportar: puede tener el turno
            # de la tarde esperando.
            #
            # Hasta el 08/09/2026 se respondía "Por ahora no tienes un reporte
            # pendiente" —falso— justo al paciente que vuelve a colaborar
            # después de haber abandonado por la mañana. Solo lo recuperaba si
            # insistía con un segundo mensaje. Reproducido en
            # `proceso/verificaciones/2026-09-08_reproduccion_bugs_paciente.py`.
            otro = CheckInProgramado.objects.select_for_update().filter(
                paciente=paciente,
                fecha_dia=hoy,
                estado=CheckInProgramado.ESTADO_PENDIENTE,
            ).order_by('orden').first()
            _limpiar_temporales(conv)
            if otro is None:
                _reiniciar(conv)
                return MSG_SIN_CHECKIN
            conv.checkin_actual = otro
            conv.estado = ConversacionWhatsApp.ESTADO_TEMPERATURA
            conv.save()
            return MSG_TURNO_SIGUIENTE
        return _procesar_respuesta_flujo(conv, paciente, texto, checkin)

    # Fuera del flujo (INICIO o COMPLETADO): FAQ disponible siempre.
    respuesta_duda = _responder_duda(texto)
    if respuesta_duda is not None:
        return respuesta_duda

    # Buscar el CheckInProgramado PENDIENTE de hoy.
    checkin = CheckInProgramado.objects.select_for_update().filter(
        paciente=paciente,
        fecha_dia=hoy,
        estado=CheckInProgramado.ESTADO_PENDIENTE,
    ).order_by('orden').first()

    if checkin is not None:
        conv.checkin_actual = checkin
        conv.estado = ConversacionWhatsApp.ESTADO_TEMPERATURA
        conv.save()
        return MSG_PREGUNTA_TEMPERATURA

    # No hay check-in pendiente — ¿completó alguno hoy?
    if CheckInProgramado.objects.filter(
        paciente=paciente,
        fecha_dia=hoy,
        estado=CheckInProgramado.ESTADO_COMPLETADO,
    ).exists():
        return MSG_YA_REGISTRADO

    return MSG_SIN_CHECKIN


# ---------------------------------------------------------------------------
# Despacho de cada pregunta del flujo
# ---------------------------------------------------------------------------
def _procesar_respuesta_flujo(conv, paciente, texto, checkin):
    estado = conv.estado

    if estado == ConversacionWhatsApp.ESTADO_TEMPERATURA:
        # D20 — sin termómetro no se pierde el turno entero. `saltar` funciona
        # aquí igual que en pulso y respiración; la Regla 1 no evalúa sin dato.
        if _es_salto(texto):
            conv.temp_temperatura = None
        else:
            valor = _parse_temperatura(texto)
            if valor is None:
                return MSG_REINTENTO_TEMPERATURA
            conv.temp_temperatura = valor
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.save()
        # D19, segunda mitad: el bot dice lo que entendió, aquí y no al cerrar.
        return _eco_temperatura(conv.temp_temperatura) + MSG_PREGUNTA_DOLOR

    if estado == ConversacionWhatsApp.ESTADO_DOLOR:
        # D20 — 0 pasa a ser válido: "hoy no tengo dolor". No dispara ninguna
        # regla porque queda por debajo del piso de las tres ventanas.
        valor = _parse_entero_rango(texto, *RANGOS_CLINICOS['dolor_eva'])
        if valor is None:
            return MSG_REINTENTO_DOLOR
        conv.temp_dolor_eva = valor
        conv.estado = ConversacionWhatsApp.ESTADO_TIENE_DRENAJE
        conv.save()
        return MSG_PREGUNTA_TIENE_DRENAJE

    if estado == ConversacionWhatsApp.ESTADO_TIENE_DRENAJE:
        respuesta_lower = _sin_acentos(texto.strip().lower())
        if respuesta_lower in ('si', 's', 'yes', 'si.', 'claro', 'si tengo'):
            conv.temp_tiene_drenaje = True
            conv.estado = ConversacionWhatsApp.ESTADO_ASPECTO_DRENAJE
            conv.save()
            return MSG_PREGUNTA_ASPECTO
        if respuesta_lower in ('no', 'no.', 'n', 'no tengo'):
            conv.temp_tiene_drenaje = False
            conv.temp_aspecto_drenaje = 'sin_drenaje'
            conv.temp_cantidad_drenaje = 'sin_drenaje'
            conv.estado = ConversacionWhatsApp.ESTADO_GASES_NAUSEAS
            conv.save()
            return MSG_PREGUNTA_GASES_NAUSEAS
        return MSG_REINTENTO_TIENE_DRENAJE

    if estado == ConversacionWhatsApp.ESTADO_ASPECTO_DRENAJE:
        aspecto = _parse_aspecto(texto)
        if aspecto is None:
            return MSG_REINTENTO_ASPECTO
        conv.temp_aspecto_drenaje = aspecto
        # Si no hay drenaje, la cantidad es coherente y se omite la pregunta 4.
        if aspecto == 'sin_drenaje':
            conv.temp_cantidad_drenaje = 'sin_drenaje'
            conv.temp_volumen_drenaje_ml = None
            conv.estado = ConversacionWhatsApp.ESTADO_GASES_NAUSEAS
            conv.save()
            return MSG_PREGUNTA_GASES_NAUSEAS
        conv.estado = ConversacionWhatsApp.ESTADO_CANTIDAD_DRENAJE
        conv.save()
        return MSG_PREGUNTA_CANTIDAD

    if estado == ConversacionWhatsApp.ESTADO_CANTIDAD_DRENAJE:
        cantidad, ml = _parse_cantidad(texto)
        if cantidad is None:
            return MSG_REINTENTO_CANTIDAD
        conv.temp_cantidad_drenaje = cantidad
        conv.temp_volumen_drenaje_ml = ml  # puede ser None
        conv.estado = ConversacionWhatsApp.ESTADO_GASES_NAUSEAS
        conv.save()
        return MSG_PREGUNTA_GASES_NAUSEAS

    if estado == ConversacionWhatsApp.ESTADO_GASES_NAUSEAS:
        gases, nauseas = _parse_gases_nauseas(texto)
        if gases is None or nauseas is None:
            return MSG_REINTENTO_GASES_NAUSEAS
        conv.temp_presencia_gases = gases
        conv.temp_episodios_nauseas = nauseas
        conv.estado = ConversacionWhatsApp.ESTADO_HINCHAZON
        conv.save()
        return MSG_PREGUNTA_HINCHAZON

    if estado == ConversacionWhatsApp.ESTADO_HINCHAZON:
        nivel = _parse_hinchazon(texto)
        if nivel is None:
            return MSG_REINTENTO_HINCHAZON
        conv.temp_hinchazon_abdominal = nivel
        conv.estado = ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA
        conv.save()
        return MSG_PREGUNTA_FRECUENCIA_CARDIACA

    if estado == ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA:
        if _es_salto(texto):
            conv.temp_frecuencia_cardiaca = None
        else:
            valor = _parse_entero_rango(texto, *RANGOS_CLINICOS['frecuencia_cardiaca'])
            if valor is None:
                return MSG_REINTENTO_FRECUENCIA_CARDIACA
            conv.temp_frecuencia_cardiaca = valor
        conv.estado = ConversacionWhatsApp.ESTADO_FRECUENCIA_RESPIRATORIA
        conv.save()
        return MSG_PREGUNTA_FRECUENCIA_RESPIRATORIA

    if estado == ConversacionWhatsApp.ESTADO_FRECUENCIA_RESPIRATORIA:
        if _es_salto(texto):
            conv.temp_frecuencia_respiratoria = None
        else:
            valor = _parse_entero_rango(texto, *RANGOS_CLINICOS['frecuencia_respiratoria'])
            if valor is None:
                return MSG_REINTENTO_FRECUENCIA_RESPIRATORIA
            conv.temp_frecuencia_respiratoria = valor
        conv.estado = ConversacionWhatsApp.ESTADO_TOLERANCIA_LIQUIDOS
        conv.save()
        return MSG_PREGUNTA_TOLERANCIA_LIQUIDOS

    if estado == ConversacionWhatsApp.ESTADO_TOLERANCIA_LIQUIDOS:
        respuesta_lower = _sin_acentos(texto.strip().lower())
        if respuesta_lower in ('si', 's', 'yes', 'si.', 'claro', 'si pude'):
            conv.temp_tolero_liquidos = True
        elif respuesta_lower in ('no', 'no.', 'n', 'no pude'):
            conv.temp_tolero_liquidos = False
        else:
            return MSG_REINTENTO_TOLERANCIA_LIQUIDOS
        _registro, alertas_nuevas = _crear_registro(conv, paciente, checkin)
        _finalizar(conv, checkin.fecha_dia)
        return _mensaje_cierre(alertas_nuevas)

    # Estado inesperado: reiniciar de forma segura.
    _reiniciar(conv)
    return MSG_PREGUNTA_TEMPERATURA


def _mensaje_cierre(alertas_nuevas):
    """Elige el mensaje de cierre según la severidad máxima de las alertas
    generadas por este check-in (Bloque B). BAJA y sin alertas → cierre neutro.
    ALTA tiene prioridad sobre MEDIA.

    **No lleva el eco de lo anotado, y es deliberado.** El eco vive en el paso
    de la temperatura (D19). Ponerlo aquí revelaría el valor que disparó la
    alerta junto al mensaje de severidad, que es justo lo que la decisión del
    Bloque B (02/07/2026) prohíbe: el paciente ve la recomendación, nunca los
    valores que la produjeron. Lo destapó `test_alerta_no_se_muestra_al_paciente`
    cuando el eco se probó aquí.
    """
    severidades = {a.severidad for a in alertas_nuevas}
    if 'ALTA' in severidades:
        return MSG_CIERRE_ALERTA_ALTA
    if 'MEDIA' in severidades:
        return MSG_CIERRE_ALERTA_MEDIA
    return MSG_CONFIRMACION


def _crear_registro(conv, paciente, checkin):
    """Crea el RegistroDiario definitivo, lo vincula al CheckInProgramado
    fijado al iniciar la conversación y evalúa las alertas de forma síncrona.

    Devuelve `(registro, alertas_nuevas)`. La evaluación es síncrona (Bloque B,
    02/07/2026) — no diferida a on_commit — porque el bot necesita conocer la
    severidad máxima de las alertas para elegir el mensaje de cierre correcto
    ANTES de responderle al paciente.

    El vínculo OneToOne (checkin.registro) y el cambio de estado del check-in
    ocurren dentro del mismo bloque atomic que la creación del registro, así no
    pueden quedar registros huérfanos ni check-ins COMPLETADO sin registro.

    fecha_referencia=checkin.fecha_dia corrige el cruce de medianoche: si el
    paciente responde un check-in de ayer después de las 00:00, el engine agrupa
    los datos por el día correcto (decisión 0-①).

    Robustez (savepoint defensivo): la evaluación corre dentro de su propio
    savepoint. Si el motor de alertas fallara (bug futuro), se descarta solo la
    evaluación — el RegistroDiario y el check-in COMPLETADO SIEMPRE quedan
    guardados, y el paciente recibe el mensaje de cierre neutro. Nunca se pierde
    el reporte del paciente por un fallo del engine. El fallo sí queda anotado
    en el registro (estado ERROR), fuera del savepoint revertido, para que sea
    visible en el Admin y recuperable por `reintentar_evaluaciones_alertas`.
    """
    registro = RegistroDiario.objects.create(
        paciente=paciente,
        temperatura=conv.temp_temperatura,
        dolor_eva=conv.temp_dolor_eva,
        tiene_drenaje=conv.temp_tiene_drenaje,
        aspecto_drenaje=conv.temp_aspecto_drenaje,
        cantidad_drenaje=conv.temp_cantidad_drenaje,
        volumen_drenaje_ml=conv.temp_volumen_drenaje_ml,
        presencia_gases=conv.temp_presencia_gases,
        episodios_nauseas=conv.temp_episodios_nauseas,
        hinchazon_abdominal=conv.temp_hinchazon_abdominal,
        frecuencia_cardiaca=conv.temp_frecuencia_cardiaca,
        frecuencia_respiratoria=conv.temp_frecuencia_respiratoria,
        tolero_liquidos=conv.temp_tolero_liquidos,
    )

    checkin.registro = registro
    checkin.estado = CheckInProgramado.ESTADO_COMPLETADO
    checkin.fecha_respuesta = timezone.now()
    checkin.save()
    fecha_referencia = checkin.fecha_dia

    alertas_nuevas = []
    try:
        with transaction.atomic():  # savepoint: aísla un posible fallo del engine
            alertas_nuevas = evaluar_registro_con_estado(
                registro, fecha_referencia=fecha_referencia
            )
    except Exception as exc:
        # El reporte del paciente ya está guardado (fuera de este savepoint).
        # No se pierde nada; el paciente recibe el cierre neutro.
        #
        # Al revertirse el savepoint se perdió también la constancia del fallo
        # que el motor había escrito (estado ERROR, intento consumido y nombre
        # de la excepción). Se vuelve a registrar aquí, ya fuera del savepoint,
        # para que el registro no se vea como uno que jamás pasó por el motor
        # (hallazgo 7).
        registrar_fallo_evaluacion(registro, exc)
        logger.exception(
            "Fallo al evaluar alertas del registro pk=%s (paciente pk=%s); "
            "queda marcado para reintento y se usa cierre neutro.",
            registro.pk, paciente.pk,
        )
        alertas_nuevas = []

    return registro, alertas_nuevas


# ---------------------------------------------------------------------------
# Dudas / FAQ
# ---------------------------------------------------------------------------
def _responder_duda(texto):
    """Devuelve una respuesta predefinida si el mensaje es una duda; si no, None.

    Heurística conservadora (sin RAG): se detectan palabras clave. Un mensaje
    con '?' que no coincida recibe el fallback de "contacta a tu médico".
    Un mensaje sin palabra clave ni '?' devuelve None para no bloquear el inicio
    del cuestionario diario.
    """
    t = _sin_acentos(texto.lower())
    if 'fiebre' in t:
        return RESP_FIEBRE
    if 'comer' in t or 'comida' in t or 'aliment' in t:
        return RESP_COMER
    if 'dolor' in t or 'duele' in t:
        return RESP_DOLOR
    if '?' in texto:
        return RESP_FALLBACK
    return None


# ---------------------------------------------------------------------------
# Parsers de respuestas clínicas
# ---------------------------------------------------------------------------
_PALABRAS_SALTO = frozenset({
    'saltar', 'omitir', 'no se', 'no se.', 'no sé', 'no sé.',
    'no puedo', 'no tengo', 'sin dato', 'sin datos',
})


def _es_salto(texto):
    """True si el paciente indicó que no puede proporcionar el dato.

    Acepta la frase suelta ("saltar", "no puedo") y también la frase
    **completada**: "no tengo termómetro", "no puedo medirla ahora". Antes
    exigía coincidencia exacta, y la respuesta más natural de un paciente
    sin termómetro —"no tengo termómetro"— lo dejaba atascado en la
    pregunta 1, que es justo el caso que la ficha D20 viene a resolver. Lo
    destapó volver a ejecutar la reproducción después de arreglarlo.

    El prefijo se exige al PRINCIPIO del mensaje y seguido de un espacio, no
    en cualquier posicion.

    Aun asi, "no tengo dolor" SI cuenta como salto para esta funcion. No es un
    problema, y conviene decir por que en vez de fingir que el prefijo lo
    resuelve: esta funcion solo se consulta en las tres preguntas que admiten
    saltarse —temperatura, frecuencia cardiaca y respiratoria—, y la del dolor
    no es una de ellas. Alli el 0 es la respuesta valida (D20), asi que esa
    frase nunca llega hasta aqui.
    """
    limpio = _sin_acentos(texto.strip().lower())
    if limpio in _PALABRAS_SALTO:
        return True
    return any(limpio.startswith(frase + ' ') for frase in _PALABRAS_SALTO)

# Palabras que sacan al paciente del cuestionario y avisan al médico (D21).
#
# Lista corta y explícita a propósito. NO se detectan síntomas ("sangrando",
# "me duele"): eso convertiría al bot en un clasificador clínico, que es justo
# lo que el proyecto promete no hacer, y llenaría el panel de falsos positivos
# con las respuestas normales del cuestionario. Se reconoce una palabra que se
# le anuncia al paciente en el saludo — una palabra de auxilio que nadie sabe
# que existe no sirve de nada.
# Se buscan como PALABRA SUELTA en cualquier parte del mensaje, no como
# mensaje completo. El caso que originó la decisión es literalmente
# "estoy sangrando mucho, necesito ayuda": exigir que el mensaje fuera
# exactamente `ayuda` dejaba ese caso sin arreglar — y así estaba escrito
# en el primer intento, hasta que volver a ejecutar la reproducción lo
# destapó. Es la razón por la que la reproducción se re-ejecuta.
_PALABRAS_AUXILIO = ('ayuda', 'auxilio', 'socorro', 'emergencia')

# `urgencia` y `urgencias` NO están en la lista, aunque suenen igual de
# graves: aparecen en preguntas normales del paciente ("¿debo ir a
# urgencias?") y en los propios mensajes del bot. Dispararían una alerta
# ALTA por una duda, y una lista de auxilio que cría ruido termina
# ignorada, que es la peor forma de fallar para esto.
_RE_AUXILIO = re.compile(r'\b(?:' + '|'.join(_PALABRAS_AUXILIO) + r')\b')


def _es_auxilio(texto):
    """True si el paciente pidió ayuda explícitamente, en cualquier estado.

    El límite de palabra distingue "necesito ayuda" de "¿me puedes ayudar
    con la app?": `ayudar` no dispara.
    """
    return bool(_RE_AUXILIO.search(_sin_acentos(texto.lower())))


def _parse_temperatura(texto):
    r"""Extrae una temperatura escrita de forma INEQUÍVOCA (30.0–45.0 °C).

    Decisión D19 (08/09/2026). El regex anterior era `\d{2}(?:[.,]\d)?`, que
    tomaba los dos primeros dígitos y **descartaba el resto en silencio**:

        "379"   ->  37.0   ->  ninguna alerta, y mensaje de cierre normal
        "37 9"  ->  37.0   ->  ídem
        "375"   ->  37.0   ->  ídem

    Escribir sin separador es lo más natural desde el teclado de un celular, así
    que un paciente con 37,9 de fiebre quedaba registrado en 37,0 sin que ni él
    ni el médico pudieran notarlo: 37,0 es un valor perfectamente creíble en un
    postoperatorio.

    Ahora se exige que el número esté **completo y solo**. Se tolera lo que la
    gente escribe alrededor ("tengo 37.5 grados"), pero no dígitos pegados a
    otros dígitos. Lo ambiguo se rechaza y el bot vuelve a preguntar con un
    ejemplo.

    **No se interpreta `379` como 37,9 a propósito:** sería adivinar el valor
    que dispara la alerta más grave del sistema, y un acierto y un error se
    verían idénticos en la ficha.
    """
    limpio = texto.strip().replace(',', '.')
    match = re.fullmatch(r'[^\d]*(\d{2}(?:\.\d{1,2})?)[^\d]*', limpio)
    if not match:
        return None
    try:
        valor = Decimal(match.group(1))
    except InvalidOperation:
        return None
    minimo, maximo = RANGOS_CLINICOS['temperatura']
    if minimo <= valor <= maximo:
        return valor
    return None


def _eco_temperatura(valor):
    """Le devuelve al paciente la temperatura que quedó anotada (D19).

    Es la otra mitad de la corrección del parser, y cubre lo que el rechazo no
    puede cubrir: el **dedazo válido**. Quien quiso escribir 37.5 y escribió
    38.5 pasa todos los filtros —es una temperatura perfectamente posible— y
    hasta el 08/09/2026 no tenía ninguna forma de enterarse. El médico tampoco.

    Va pegado a la respuesta del paciente, antes de que exista ninguna alerta,
    así que no revela ningún juicio clínico: es el número que él mismo acaba de
    teclear.
    """
    anotado = f'{valor} °C' if valor is not None else 'sin medir (la saltaste)'
    return f'Anoté: {anotado}.\n\n'


def _parse_entero_rango(texto, minimo, maximo):
    # Rechaza decimales (ej. "78.5" o "78,5") para no truncar en silencio;
    # el bot pide reintento y el paciente aprende a redondear.
    if re.search(r'\d+[.,]\d+', texto):
        return None
    match = re.search(r'\d+', texto)
    if not match:
        return None
    valor = int(match.group(0))
    if minimo <= valor <= maximo:
        return valor
    return None


def _parse_aspecto(texto):
    """Mapea la opción 1–5 del paciente a la clave médica de aspecto_drenaje."""
    mapa = {
        '1': 'seroso',
        '2': 'hematico',
        '3': 'turbio',
        '4': 'purulento',
        '5': 'fecaloide',
    }
    match = re.search(r'[1-5]', texto)
    if not match:
        return None
    return mapa[match.group(0)]


def _parse_cantidad(texto):
    """Devuelve (cantidad_cualitativa, ml_o_None). cantidad=None si no se entiende."""
    t = _sin_acentos(texto.lower())
    if 'poco' in t:
        cantidad = 'poco'
    elif 'normal' in t:
        cantidad = 'normal'
    elif 'mucho' in t:
        cantidad = 'mucho'
    elif 'sin drenaje' in t or 'no tengo' in t or 'ninguno' in t:
        cantidad = 'sin_drenaje'
    else:
        return None, None

    ml = None
    match_ml = re.search(r'(\d+)\s*ml', t)
    if match_ml:
        ml = int(match_ml.group(1))
    return cantidad, ml


def _parse_hinchazon(texto):
    """Mapea la respuesta del paciente a nivel de hinchazón: nada/algo/mucho.

    Vocabulario tolerante. Devuelve None si no se entiende. Se evalúa de
    mayor a menor especificidad; 'no' se detecta con límite de palabra para
    no confundirlo con 'menos' (en 'más o menos')."""
    t = _sin_acentos(texto.lower())
    if 'mucho' in t or 'bastante' in t or 'demasiado' in t:
        return 'mucho'
    if 'algo' in t or 'poco' in t or 'mas o menos' in t or 'masomenos' in t:
        return 'algo'
    if 'nada' in t or re.search(r'\bno\b', t):
        return 'nada'
    return None


def _parse_gases_nauseas(texto):
    """Devuelve (presencia_gases_bool_o_None, episodios_nauseas_int_o_None).

    Si la respuesta es ambigua ("no sé") o falta el número de náuseas, devuelve
    (None, None) para que el bot pida un reintento en vez de interpretar mal.
    """
    t = _sin_acentos(texto.lower())

    # Respuesta ambigua: "no sé" contiene "no" pero NO afirma ausencia de gases.
    # Con límite de palabra, "no sentí náuseas" sí se considera respuesta válida.
    if re.search(r'\bno se\b', t):
        return None, None

    # Sin número de náuseas no se puede completar la respuesta.
    match = re.search(r'\d+', t)
    if match is None:
        return None, None
    nauseas = int(match.group(0))

    # DB-01 — techo. Sin esto, "si, 99999" llegaba tal cual a la base, reventaba
    # el PositiveSmallIntegerField con un DataError, el webhook devolvía 500 y
    # el paciente NO recibía ninguna respuesta: no podía saber si su reporte
    # había entrado. Reproducido el 08/09/2026.
    minimo, maximo = RANGOS_CLINICOS['episodios_nauseas']
    if not (minimo <= nauseas <= maximo):
        return None, None

    gases = None
    if re.search(r'\bno\b', t):
        gases = False
    elif re.search(r'\bsi\b', t):
        gases = True

    return gases, nauseas


# ---------------------------------------------------------------------------
# Helpers de estado y utilidades
# ---------------------------------------------------------------------------
def _normalizar_telefono(telefono):
    if telefono is None:
        return ''
    return telefono.replace('whatsapp:', '').strip()


def _sin_acentos(cadena):
    return ''.join(
        c for c in unicodedata.normalize('NFD', cadena)
        if unicodedata.category(c) != 'Mn'
    )


def _limpiar_temporales(conv):
    conv.temp_temperatura = None
    conv.temp_dolor_eva = None
    conv.temp_tiene_drenaje = None
    conv.temp_aspecto_drenaje = None
    conv.temp_cantidad_drenaje = None
    conv.temp_volumen_drenaje_ml = None
    conv.temp_presencia_gases = None
    conv.temp_episodios_nauseas = None
    conv.temp_hinchazon_abdominal = None
    conv.temp_frecuencia_cardiaca = None
    conv.temp_frecuencia_respiratoria = None
    conv.temp_tolero_liquidos = None


def _reiniciar(conv):
    """Prepara la conversación para un nuevo ciclo diario."""
    conv.estado = ConversacionWhatsApp.ESTADO_INICIO
    conv.checkin_actual = None
    _limpiar_temporales(conv)
    conv.save()


def _finalizar(conv, hoy):
    """Cierra el registro del día: marca COMPLETADO y limpia parciales."""
    conv.estado = ConversacionWhatsApp.ESTADO_COMPLETADO
    conv.fecha_ultimo_registro = hoy
    conv.checkin_actual = None
    _limpiar_temporales(conv)
    conv.save()
