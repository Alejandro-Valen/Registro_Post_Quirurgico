"""
Lógica del bot de WhatsApp para el seguimiento postoperatorio remoto.

Diseño:
- Lógica PURA respecto al transporte: `procesar_mensaje(telefono, texto)` recibe
  texto plano y devuelve texto plano. No conoce HTTP ni Twilio. La vista
  (views.py) traduce HTTP <-> esta función.
- El estado de la conversación se persiste en el modelo ConversacionWhatsApp,
  porque cada mensaje de WhatsApp llega como una petición independiente.
- El bot NO diagnostica ni muestra alertas al paciente. Solo captura telemetría,
  delega en alert_engine.evaluar_registro() y responde una confirmación neutra.

Máquina de estados (9 preguntas):
    INICIO
      -> ESPERANDO_TEMPERATURA
      -> ESPERANDO_DOLOR
      -> ESPERANDO_TIENE_DRENAJE
      -> ESPERANDO_ASPECTO_DRENAJE    (se omite si tiene_drenaje=False)
      -> ESPERANDO_CANTIDAD_DRENAJE   (se omite si tiene_drenaje=False)
      -> ESPERANDO_GASES_NAUSEAS
      -> ESPERANDO_HINCHAZON
      -> ESPERANDO_FRECUENCIA_CARDIACA
      -> ESPERANDO_TOLERANCIA_LIQUIDOS
      -> COMPLETADO
"""

import re
import unicodedata

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .alert_engine import evaluar_registro
from .models import ConversacionWhatsApp, Paciente, RegistroDiario


# ---------------------------------------------------------------------------
# Mensajes del bot — español coloquial, tuteo, tono cálido. NUNCA muestran
# alertas; la confirmación final es siempre neutra.
# ---------------------------------------------------------------------------
MSG_NO_REGISTRADO = (
    "Hola 🌿 Tu número aún no está registrado en nuestro programa de seguimiento. "
    "Por favor comunícate con tu médico para activarlo. Estamos para acompañarte."
)
MSG_YA_REGISTRADO = (
    "Ya registramos tus datos de hoy ✅ Gracias por cuidarte. Nos vemos mañana 🌿"
)
MSG_CONFIRMACION = (
    "¡Listo! ✅ Hemos registrado tu reporte de hoy. Gracias por cuidarte 🌿 "
    "Tu equipo médico está pendiente de tu seguimiento. ¡Que tengas un buen día!"
)

MSG_PREGUNTA_TEMPERATURA = (
    "¡Hola! 🌿 Vamos con tu reporte de hoy.\n\n"
    "1️⃣ ¿Cuál es tu temperatura corporal? Escríbela en números, por ejemplo: 37.5"
)
MSG_REINTENTO_TEMPERATURA = (
    "No logré entender la temperatura. Envíame solo el número en °C, por ejemplo: 37.5"
)

MSG_PREGUNTA_DOLOR = (
    "2️⃣ Del 1 al 10, ¿cuánto dolor sientes hoy?\n"
    "(1 es casi nada, 10 es insoportable)"
)
MSG_REINTENTO_DOLOR = (
    "Por favor envíame un número del 1 al 10 para indicar tu dolor."
)

MSG_PREGUNTA_TIENE_DRENAJE = (
    "3️⃣ ¿Tienes drenaje activo en este momento? Responde *sí* o *no*."
)
MSG_REINTENTO_TIENE_DRENAJE = (
    "No entendí tu respuesta. "
    "Por favor responde *sí* si tienes drenaje, o *no* si no tienes. "
    "Ejemplo: sí / no"
)

MSG_PREGUNTA_ASPECTO = (
    "4️⃣ ¿Cómo se ve el líquido del drenaje hoy? Responde con el número:\n"
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
    "5️⃣ ¿Cuánto líquido salió por el drenaje hoy?\n"
    "Responde: poco, normal o mucho.\n"
    "Si puedes medirlo, agrega los ml (ej: 'poco, 30ml')"
)
MSG_REINTENTO_CANTIDAD = (
    "No te entendí. Responde poco, normal o mucho "
    "(y si quieres, los ml, ej: 'normal, 50ml')."
)

MSG_PREGUNTA_GASES_NAUSEAS = (
    "6️⃣ Ya casi terminamos 🌿\n"
    "¿Has podido pasar gases o ir al baño hoy? (sí/no)\n"
    "Y ¿cuántas veces has tenido náuseas o vómito hoy? (si ninguna, 0)\n"
    "Puedes responder así: 'sí, 0'"
)
MSG_REINTENTO_GASES_NAUSEAS = (
    "Por favor dime si pasaste gases (sí/no) y cuántas veces tuviste náuseas. "
    "Ejemplo: 'sí, 0' o 'no, 2'."
)

MSG_PREGUNTA_HINCHAZON = (
    "7️⃣ ¿Cómo siente la hinchazón o distensión de su abdomen hoy? 🌿\n"
    "Responda: *nada*, *algo* o *mucho*."
)
MSG_REINTENTO_HINCHAZON = (
    "No entendí. ¿Cómo siente la hinchazón de su abdomen? "
    "Responda *nada*, *algo* o *mucho*."
)

MSG_PREGUNTA_FRECUENCIA_CARDIACA = (
    "8️⃣ ¿Cuál es su frecuencia cardíaca (pulso) en este momento? 🌿\n"
    "Escriba el número de latidos por minuto, por ejemplo: 78"
)
MSG_REINTENTO_FRECUENCIA_CARDIACA = (
    "No entendí. Escriba su frecuencia cardíaca como un número de "
    "latidos por minuto (ej: 78)."
)

MSG_PREGUNTA_TOLERANCIA_LIQUIDOS = (
    "9️⃣ Última pregunta 🌿\n"
    "¿Ha podido tomar líquidos (agua, caldo, jugo) sin vomitar? "
    "Responda *sí* o *no*."
)
MSG_REINTENTO_TOLERANCIA_LIQUIDOS = (
    "No entendí su respuesta. ¿Pudo tomar líquidos sin vomitar? "
    "Responda *sí* o *no*."
)

# Respuestas predefinidas a dudas (espejo de knowledge_base.md mientras no haya RAG)
RESP_FIEBRE = (
    "Una temperatura leve los primeros días puede ser normal. Si supera 38°C "
    "comunícate con tu médico de inmediato."
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

    conv, _ = ConversacionWhatsApp.objects.get_or_create(paciente=paciente)
    hoy = timezone.localdate()

    # Nuevo día: si completó en un día anterior, reiniciar el ciclo diario.
    if (conv.estado == ConversacionWhatsApp.ESTADO_COMPLETADO
            and conv.fecha_ultimo_registro != hoy):
        _reiniciar(conv)

    en_flujo = conv.estado not in (
        ConversacionWhatsApp.ESTADO_INICIO,
        ConversacionWhatsApp.ESTADO_COMPLETADO,
    )

    # Dudas (FAQ) — solo cuando el paciente no está respondiendo el registro.
    if not en_flujo:
        respuesta_duda = _responder_duda(texto)
        if respuesta_duda is not None:
            return respuesta_duda

    # Ya completó hoy.
    if conv.estado == ConversacionWhatsApp.ESTADO_COMPLETADO:
        return MSG_YA_REGISTRADO

    # INICIO -> arrancar el cuestionario.
    if conv.estado == ConversacionWhatsApp.ESTADO_INICIO:
        conv.estado = ConversacionWhatsApp.ESTADO_TEMPERATURA
        conv.save()
        return MSG_PREGUNTA_TEMPERATURA

    return _procesar_respuesta_flujo(conv, paciente, texto, hoy)


# ---------------------------------------------------------------------------
# Despacho de cada pregunta del flujo
# ---------------------------------------------------------------------------
def _procesar_respuesta_flujo(conv, paciente, texto, hoy):
    estado = conv.estado

    if estado == ConversacionWhatsApp.ESTADO_TEMPERATURA:
        valor = _parse_temperatura(texto)
        if valor is None:
            return MSG_REINTENTO_TEMPERATURA
        conv.temp_temperatura = valor
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.save()
        return MSG_PREGUNTA_DOLOR

    if estado == ConversacionWhatsApp.ESTADO_DOLOR:
        valor = _parse_entero_rango(texto, 1, 10)
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
        elif respuesta_lower in ('no', 'no.', 'n', 'no tengo'):
            conv.temp_tiene_drenaje = False
            conv.temp_aspecto_drenaje = 'sin_drenaje'
            conv.temp_cantidad_drenaje = 'sin_drenaje'
            conv.estado = ConversacionWhatsApp.ESTADO_GASES_NAUSEAS
            conv.save()
            return MSG_PREGUNTA_GASES_NAUSEAS
        else:
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
        valor = _parse_entero_rango(texto, 30, 250)
        if valor is None:
            return MSG_REINTENTO_FRECUENCIA_CARDIACA
        conv.temp_frecuencia_cardiaca = valor
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
        _crear_registro(conv, paciente)
        _finalizar(conv, hoy)
        return MSG_CONFIRMACION

    # Estado inesperado: reiniciar de forma segura.
    _reiniciar(conv)
    return MSG_PREGUNTA_TEMPERATURA


def _crear_registro(conv, paciente):
    """Crea el RegistroDiario definitivo y dispara el motor de alertas.

    Las alertas NO se devuelven al paciente: quedan en BD para el oncólogo.
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
        tolero_liquidos=conv.temp_tolero_liquidos,
    )
    evaluar_registro(registro)
    return registro


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
def _parse_temperatura(texto):
    """Extrae una temperatura plausible (30.0–45.0 °C). Acepta coma o punto."""
    match = re.search(r'\d{2}(?:[.,]\d)?', texto)
    if not match:
        return None
    try:
        valor = Decimal(match.group(0).replace(',', '.'))
    except InvalidOperation:
        return None
    if Decimal('30.0') <= valor <= Decimal('45.0'):
        return valor
    return None


def _parse_entero_rango(texto, minimo, maximo):
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
    conv.temp_tolero_liquidos = None


def _reiniciar(conv):
    """Prepara la conversación para un nuevo ciclo diario."""
    conv.estado = ConversacionWhatsApp.ESTADO_INICIO
    _limpiar_temporales(conv)
    conv.save()


def _finalizar(conv, hoy):
    """Cierra el registro del día: marca COMPLETADO y limpia parciales."""
    conv.estado = ConversacionWhatsApp.ESTADO_COMPLETADO
    conv.fecha_ultimo_registro = hoy
    _limpiar_temporales(conv)
    conv.save()
