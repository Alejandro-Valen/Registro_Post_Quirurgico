"""Maquina de estados del bot de WhatsApp y sus respuestas al paciente.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from .. import bot
from ..models import (
    Alerta,
    CheckInProgramado,
    ConversacionWhatsApp,
    Paciente,
    RegistroDiario,
)
from .soporte import ANCLA_MEDIANOCHE, medico_de_pruebas


class BotWhatsAppTests(TestCase):
    TELEFONO = "+573001112233"
    TELEFONO_TWILIO = "whatsapp:+573001112233"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Bot",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        # Bloque 3: el bot requiere CheckInProgramado PENDIENTE para iniciar el flujo.
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def _completar_flujo(self, gases_nauseas="sí, 0", temperatura="37.0",
                         tiene_drenaje="sí", aspecto="1", cantidad="normal",
                         hinchazon="nada", frecuencia_cardiaca="78",
                         frecuencia_respiratoria="16", tolero_liquidos="sí"):
        """Recorre las 10 preguntas y devuelve la respuesta final del bot."""
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")          # -> temperatura
        bot.procesar_mensaje(self.TELEFONO_TWILIO, temperatura)     # -> dolor
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")             # -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, tiene_drenaje)   # -> aspecto (si sí)
        bot.procesar_mensaje(self.TELEFONO_TWILIO, aspecto)         # -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, cantidad)        # -> gases/nauseas
        bot.procesar_mensaje(self.TELEFONO_TWILIO, gases_nauseas)   # -> hinchazón
        bot.procesar_mensaje(self.TELEFONO_TWILIO, hinchazon)       # -> frecuencia cardíaca
        bot.procesar_mensaje(self.TELEFONO_TWILIO, frecuencia_cardiaca)      # -> frecuencia respiratoria
        bot.procesar_mensaje(self.TELEFONO_TWILIO, frecuencia_respiratoria)  # -> tolerancia líquidos
        return bot.procesar_mensaje(self.TELEFONO_TWILIO, tolero_liquidos)

    def test_paciente_no_registrado(self):
        respuesta = bot.procesar_mensaje("whatsapp:+570000000000", "hola")
        self.assertEqual(respuesta, bot.MSG_NO_REGISTRADO)
        self.assertEqual(ConversacionWhatsApp.objects.count(), 0)

    def test_primer_mensaje_inicia_cuestionario(self):
        self._crear_paciente()
        checkin = CheckInProgramado.objects.get()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertEqual(conv.checkin_actual, checkin)

    def test_flujo_completo_crea_registro(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(
            temperatura="37.0", aspecto="1", cantidad="normal", gases_nauseas="sí, 0"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        self.assertEqual(RegistroDiario.objects.count(), 1)
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.temperatura, Decimal("37.0"))
        self.assertEqual(registro.dolor_eva, 3)
        self.assertTrue(registro.tiene_drenaje)
        self.assertEqual(registro.aspecto_drenaje, "seroso")  # opción "1"
        self.assertEqual(registro.cantidad_drenaje, "normal")
        self.assertTrue(registro.presencia_gases)
        self.assertEqual(registro.episodios_nauseas, 0)
        self.assertEqual(registro.hinchazon_abdominal, "nada")
        self.assertEqual(registro.frecuencia_cardiaca, 78)
        self.assertEqual(registro.frecuencia_respiratoria, 16)
        self.assertTrue(registro.tolero_liquidos)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_COMPLETADO)
        self.assertIsNone(conv.checkin_actual)
        self.assertIsNone(conv.temp_temperatura)  # parciales limpiados
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )

    def test_alerta_no_se_muestra_al_paciente(self):
        # Bloque B: evaluar_registro ahora corre de forma síncrona dentro de
        # _crear_registro, así que la alerta ya existe al armar la respuesta.
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # dispara SEPSIS (ALTA)
        # La alerta se crea para el oncólogo...
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)
        # ...y el paciente recibe el cierre de severidad ALTA, pero SIN ver el
        # tipo de alerta ni los valores que la dispararon.
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)
        self.assertNotIn("sepsis", respuesta.lower())
        self.assertNotIn("alerta", respuesta.lower())
        self.assertNotIn("38.5", respuesta)

    def test_temperatura_invalida_reintenta(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "creo que tengo fiebre")
        self.assertEqual(respuesta, bot.MSG_REINTENTO_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_sin_drenaje_salta_pregunta_cantidad(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")           # dolor -> tiene_drenaje
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no")  # no tiene drenaje
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_GASES_NAUSEAS)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_GASES_NAUSEAS)
        self.assertFalse(conv.temp_tiene_drenaje)
        self.assertEqual(conv.temp_aspecto_drenaje, "sin_drenaje")
        self.assertEqual(conv.temp_cantidad_drenaje, "sin_drenaje")

    def test_extraccion_ml_opcional(self):
        self._crear_paciente()
        self._completar_flujo(aspecto="1", cantidad="poco, 30ml")
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.cantidad_drenaje, "poco")
        self.assertEqual(registro.volumen_drenaje_ml, 30)

    def test_ya_registrado_hoy(self):
        self._crear_paciente()
        self._completar_flujo()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_YA_REGISTRADO)
        self.assertEqual(RegistroDiario.objects.count(), 1)

    def test_duda_fiebre_responde_predefinido(self):
        self._crear_paciente()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "¿es normal tener fiebre?")
        self.assertEqual(respuesta, bot.RESP_FIEBRE)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_duda_desconocida_responde_fallback(self):
        self._crear_paciente()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "¿puedo bañarme hoy?")
        self.assertEqual(respuesta, bot.RESP_FALLBACK)

    def test_respuestas_predefinidas_no_revelan_umbrales_clinicos(self):
        """Ninguna respuesta al paciente puede contener un umbral clínico (D4).

        Regla de diseño no negociable del bot (CLAUDE.md): el paciente nunca ve
        los valores que disparan una alerta. Un umbral en la FAQ además puede
        contradecir al motor —RESP_FIEBRE decía 38 °C mientras el motor alerta
        desde 37.9— y le pide al paciente que se auto-evalúe cuando el sistema
        ya lo está midiendo dos veces al día.

        Este test no vigila una redacción concreta: vigila que no vuelva a
        aparecer una cifra clínica, sea cual sea el texto que apruebe el médico.
        """
        import re

        patron_umbral = re.compile(
            r'\d+([.,]\d+)?\s*(°\s*)?(c\b|grados|lpm|rpm|/10)',
            re.IGNORECASE,
        )
        for nombre in ('RESP_FIEBRE', 'RESP_COMER', 'RESP_DOLOR', 'RESP_FALLBACK'):
            texto = getattr(bot, nombre)
            encontrado = patron_umbral.search(texto)
            self.assertIsNone(
                encontrado,
                f'{nombre} expone un umbral clínico al paciente: '
                f'{encontrado.group(0) if encontrado else ""!r}',
            )

    def test_gases_nauseas_ambiguo_reintenta(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")      # dolor -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")     # tiene_drenaje -> aspecto
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")      # aspecto -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal") # cantidad -> gases/nauseas
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no sé")
        self.assertEqual(respuesta, bot.MSG_REINTENTO_GASES_NAUSEAS)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_GASES_NAUSEAS)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_fc_saltar_guarda_none_y_avanza(self):
        # A2: paciente sin oxímetro usa palabra de salto en FC → None, avanza a FR.
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí, 0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "nada")
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "saltar")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_FRECUENCIA_RESPIRATORIA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertIsNone(conv.temp_frecuencia_cardiaca)
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_RESPIRATORIA)

    def test_fr_omitir_guarda_none_y_flujo_completa(self):
        # A2: paciente usa "omitir" en FR → None guardado en RegistroDiario.
        self._crear_paciente()
        respuesta = self._completar_flujo(
            frecuencia_cardiaca="78", frecuencia_respiratoria="omitir"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.frecuencia_cardiaca, 78)
        self.assertIsNone(registro.frecuencia_respiratoria)

    def test_flujo_completo_sin_fc_ni_fr_crea_registro_con_nulls(self):
        # A2: ambas variables saltadas → RegistroDiario creado con FC=None, FR=None.
        self._crear_paciente()
        respuesta = self._completar_flujo(
            frecuencia_cardiaca="no sé", frecuencia_respiratoria="sin dato"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        registro = RegistroDiario.objects.get()
        self.assertIsNone(registro.frecuencia_cardiaca)
        self.assertIsNone(registro.frecuencia_respiratoria)

    def test_fc_fuera_de_rango_reintenta(self):
        # Un valor fuera del rango 30-250 lpm se rechaza y pide reintento,
        # sin avanzar de estado ni crear registro.
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")        # dolor -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")       # tiene_drenaje -> aspecto
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")        # aspecto -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal")   # cantidad -> gases/nauseas
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí, 0")    # gases -> hinchazón
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "nada")     # hinchazón -> frecuencia cardíaca
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "999")  # fuera de rango
        self.assertEqual(respuesta, bot.MSG_REINTENTO_FRECUENCIA_CARDIACA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(
            conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA
        )
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_sin_checkin_pendiente_muestra_mensaje(self):
        """Bloque 3: si no hay CheckInProgramado PENDIENTE hoy, el bot devuelve MSG_SIN_CHECKIN."""
        Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Sin CheckIn",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        # Sin CheckInProgramado → el bot responde MSG_SIN_CHECKIN y no crea RegistroDiario
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_SIN_CHECKIN)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_ya_registrado_via_checkin_completado(self):
        """Bloque 3: si el CheckInProgramado del día ya está COMPLETADO, responde MSG_YA_REGISTRADO."""
        self._crear_paciente()
        # Completar el flujo → checkin queda COMPLETADO
        self._completar_flujo()
        # Nuevo mensaje del mismo día
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_YA_REGISTRADO)

    def test_checkin_vinculado_al_registro_al_completar(self):
        """Bloque 3: al completar el flujo, el CheckInProgramado queda COMPLETADO y vinculado al RegistroDiario."""
        self._crear_paciente()
        self._completar_flujo()
        registro = RegistroDiario.objects.get()
        checkin = CheckInProgramado.objects.get()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(checkin.registro, registro)
        self.assertIsNotNone(checkin.fecha_respuesta)

    def test_con_dos_turnos_completa_el_checkin_fijado_al_iniciar(self):
        paciente = self._crear_paciente()
        primero = CheckInProgramado.objects.get(orden=1)
        segundo = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=2,
            etiqueta=CheckInProgramado.ETIQUETA_TARDE,
            hora_programada=timezone.now(),
        )

        self._completar_flujo()

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertIsNotNone(primero.registro_id)
        self.assertEqual(segundo.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertIsNone(segundo.registro_id)

    # --- Menu de aspecto del drenaje: las cinco opciones, una por una ---
    #
    # Hasta el 08/09/2026 solo se recorrian la "1" (seroso) y la "3" (turbio).
    # El sabotaje `'4': 'purulento'` -> `'seroso'` en `_parse_aspecto` pasaba
    # sin que cayera nada: el paciente marcaba purulento, el sistema guardaba
    # "dentro de lo esperado" y el medico no veia ninguna alerta ALTA.
    #
    # Se prueba el flujo completo y no `_parse_aspecto` por separado: lo que
    # importa clinicamente no es que la funcion traduzca, sino que lo traducido
    # llegue hasta `RegistroDiario`.

    def _aspecto_registrado(self, opcion):
        self._crear_paciente()
        self._completar_flujo(aspecto=opcion)
        return RegistroDiario.objects.get().aspecto_drenaje

    def test_menu_drenaje_opcion_1_registra_seroso(self):
        self.assertEqual(self._aspecto_registrado("1"), "seroso")

    def test_menu_drenaje_opcion_2_registra_hematico(self):
        self.assertEqual(self._aspecto_registrado("2"), "hematico")

    def test_menu_drenaje_opcion_3_registra_turbio(self):
        self.assertEqual(self._aspecto_registrado("3"), "turbio")

    def test_menu_drenaje_opcion_4_registra_purulento(self):
        self.assertEqual(self._aspecto_registrado("4"), "purulento")

    def test_menu_drenaje_opcion_5_registra_fecaloide(self):
        self.assertEqual(self._aspecto_registrado("5"), "fecaloide")

    def test_menu_drenaje_fecaloide_llega_hasta_la_alerta_alta(self):
        """Cierra la cadena completa del peor signo que captura el sistema.

        El paciente marca "5" en el menu; el bot debe traducirlo a fecaloide,
        el motor generar FUGA_ANASTOMOTICA/ALTA, y el paciente recibir el
        cierre de severidad ALTA sin que se le diga por que. Las pruebas del
        motor fijan la regla y las de arriba la traduccion: esta fija que las
        dos esten conectadas.
        """
        self._crear_paciente()
        respuesta = self._completar_flujo(aspecto="5")
        alerta = Alerta.objects.get(tipo="FUGA_ANASTOMOTICA")
        self.assertEqual(alerta.severidad, "ALTA")
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)


@freeze_time(ANCLA_MEDIANOCHE)
class BotMensajeCierreAlertaTests(TestCase):
    """Bloque B — mensaje de cierre del bot según severidad de las alertas
    generadas por el check-in. El paciente nunca ve el tipo de alerta ni los
    valores; solo una recomendación de acción tranquilizadora."""

    TELEFONO = "+573001114455"
    TELEFONO_TWILIO = "whatsapp:+573001114455"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Cierre",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def _completar_flujo(self, temperatura="37.0", aspecto="1", gases_nauseas="sí, 0"):
        """Recorre las 10 preguntas con drenaje presente. Devuelve la respuesta final."""
        def env(t):
            return bot.procesar_mensaje(self.TELEFONO_TWILIO, t)
        env("hola")            # -> temperatura
        env(temperatura)       # -> dolor
        env("3")               # -> tiene_drenaje
        env("sí")              # -> aspecto
        env(aspecto)           # -> cantidad
        env("normal")          # -> gases/nauseas
        env(gases_nauseas)     # -> hinchazón
        env("nada")            # -> frecuencia cardíaca
        env("78")              # -> frecuencia respiratoria
        env("16")              # -> tolerancia líquidos
        return env("sí")

    # --- Unidad: selección de mensaje según severidad máxima ---

    def test_mensaje_cierre_sin_alertas_es_confirmacion(self):
        self.assertEqual(bot._mensaje_cierre([]), bot.MSG_CONFIRMACION)

    def test_mensaje_cierre_solo_baja_es_confirmacion(self):
        from types import SimpleNamespace
        alertas = [SimpleNamespace(severidad='BAJA')]
        self.assertEqual(bot._mensaje_cierre(alertas), bot.MSG_CONFIRMACION)

    def test_mensaje_cierre_media_y_alta_prioriza_alta(self):
        from types import SimpleNamespace
        alertas = [SimpleNamespace(severidad='MEDIA'), SimpleNamespace(severidad='ALTA')]
        self.assertEqual(bot._mensaje_cierre(alertas), bot.MSG_CIERRE_ALERTA_ALTA)

    # --- Integración: a través del flujo real + motor de alertas ---

    def test_flujo_drenaje_seroso_baja_devuelve_confirmacion(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(aspecto="1")  # seroso -> FUGA BAJA
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)

    def test_flujo_drenaje_turbio_media_devuelve_cierre_media(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(aspecto="3")  # turbio -> FUGA MEDIA
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_MEDIA)

    def test_flujo_temperatura_alta_devuelve_cierre_alta(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # SEPSIS ALTA
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)

    def test_flujo_media_y_alta_devuelve_cierre_alta(self):
        self._crear_paciente()
        # temperatura 38.5 (SEPSIS ALTA) + drenaje turbio (FUGA MEDIA) -> ALTA
        respuesta = self._completar_flujo(temperatura="38.5", aspecto="3")
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)

    def test_mensajes_cierre_no_revelan_clasificacion_clinica(self):
        for msg in (bot.MSG_CIERRE_ALERTA_MEDIA, bot.MSG_CIERRE_ALERTA_ALTA):
            low = msg.lower()
            for prohibida in ('sepsis', 'fuga', 'taquicardia', 'alerta', 'riesgo', 'ileo'):
                self.assertNotIn(prohibida, low)

class ConsentimientoInformadoTests(TestCase):
    """Bloque 7 — consentimiento informado HABEAS DATA (P-15, 01/07/2026)."""

    TELEFONO = "+573006661111"
    TELEFONO_TWILIO = "whatsapp:+573006661111"

    def _crear_paciente(self, consentimiento_informado):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Consentimiento",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=consentimiento_informado,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def test_sin_consentimiento_bot_responde_mensaje_neutro_y_no_inicia_flujo(self):
        self._crear_paciente(consentimiento_informado=False)
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_SIN_CONSENTIMIENTO)
        self.assertFalse(ConversacionWhatsApp.objects.exists())

    def test_con_consentimiento_flujo_normal_continua(self):
        self._crear_paciente(consentimiento_informado=True)
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)

    def test_consentimiento_informado_false_por_default(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Default",
            telefono_whatsapp="+573006661112",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertFalse(paciente.consentimiento_informado)
        self.assertIsNone(paciente.fecha_consentimiento)

class ParseEnteroRangoDecimalTests(TestCase):
    """C4 — _parse_entero_rango rechaza decimales con punto y coma."""

    def test_punto_decimal_devuelve_none(self):
        self.assertIsNone(bot._parse_entero_rango("78.5", 30, 250))

    def test_coma_decimal_devuelve_none(self):
        self.assertIsNone(bot._parse_entero_rango("78,5", 30, 250))

    def test_entero_valido_pasa(self):
        self.assertEqual(bot._parse_entero_rango("78", 30, 250), 78)

    def test_fc_decimal_pide_reintento(self):
        """Flujo real: paciente escribe "78.5" en la pregunta de FC → reintento."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Decimal FC",
            telefono_whatsapp="+573007778881",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        checkin = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        from signos_sintomas import bot as b
        conv = ConversacionWhatsApp.objects.create(
            paciente=paciente,
            checkin_actual=checkin,
            estado=ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA,
        )
        respuesta = b.procesar_mensaje("+573007778881", "78.5")
        self.assertIn("latidos", respuesta.lower())
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA)

class BotAbandonoConversacionTests(TestCase):
    """A1 — Conversación abandonada a mitad de flujo en un día anterior."""

    TELEFONO = "+573001119999"
    TELEFONO_TWILIO = "whatsapp:+573001119999"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Abandono",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def test_conversacion_en_flujo_ayer_reinicia_con_aviso(self):
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.temp_temperatura = Decimal("37.0")
        conv.save()
        # Simular que la última actualización fue ayer
        ayer = timezone.now() - timedelta(days=1)
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(fecha_actualizacion=ayer)

        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")

        self.assertIn("ayer no pudimos terminar", respuesta)
        self.assertEqual(RegistroDiario.objects.count(), 0)
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertIsNone(conv.temp_temperatura)

    def test_inicio_incompleto_ayer_no_es_abandono(self):
        # Estado INICIO desde días anteriores: no es "flujo" → no envía aviso.
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(days=1)
        )

        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")

        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        self.assertNotIn("ayer no pudimos terminar", respuesta)

    def test_despues_de_aviso_flujo_normal_continua(self):
        # Después del reinicio con aviso, el bot espera temperatura.
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.temp_temperatura = Decimal("37.0")
        conv.save()
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(days=1)
        )

        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")  # recibe aviso
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.2")  # temperatura

        # Desde el 08/09/2026 (D19) la pregunta 2 va precedida del eco de la
        # temperatura anotada, para que el paciente pueda detectar un dedazo.
        self.assertIn("37.2", respuesta)
        self.assertTrue(respuesta.endswith(bot.MSG_PREGUNTA_DOLOR))
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_DOLOR)
        self.assertEqual(conv.temp_temperatura, Decimal("37.2"))

class BotEstadoEvaluacionMotorTests(TestCase):
    """Hallazgo 7 — un fallo del motor en la ruta del bot debe quedar registrado.

    `evaluar_registro_con_estado` guarda con cuidado el estado ERROR, el nombre
    de la excepción y el intento consumido, y RECIÉN DESPUÉS relanza. Pero en
    `bot._crear_registro` esa llamada vive dentro de un savepoint defensivo: la
    excepción sale de ese `atomic`, el savepoint se revierte y se lleva consigo
    las tres cosas. El registro queda como si el motor nunca se hubiera
    ejecutado.

    Lo que se pierde no es el reporte del paciente (ese está a salvo, y esa
    parte se verifica aquí también) sino el rastro del fallo: en el Admin el
    registro se ve PENDIENTE, igual que uno que todavía no ha pasado por el
    motor, y `ultimo_error_evaluacion_alertas` queda vacío.
    """

    TELEFONO = "+573001119977"
    TELEFONO_TWILIO = "whatsapp:+573001119977"

    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Estado Motor",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    def _completar_flujo(self):
        """Recorre las 10 preguntas sin drenaje. Devuelve la respuesta final."""
        def env(t):
            return bot.procesar_mensaje(self.TELEFONO_TWILIO, t)
        env("hola")     # -> temperatura
        env("37.0")     # -> dolor
        env("3")        # -> tiene_drenaje
        env("no")       # -> gases/náuseas (omite aspecto y cantidad)
        env("sí, 0")    # -> hinchazón
        env("nada")     # -> frecuencia cardíaca
        env("78")       # -> frecuencia respiratoria
        env("16")       # -> tolerancia líquidos
        return env("sí")

    def test_fallo_del_motor_deja_el_registro_marcado_como_error(self):
        from unittest.mock import patch

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=RuntimeError('temperatura 39.1 del paciente'),
        ):
            respuesta = self._completar_flujo()

        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )
        self.assertEqual(registro.intentos_evaluacion_alertas, 1)
        self.assertEqual(registro.ultimo_error_evaluacion_alertas, 'RuntimeError')
        self.assertNotIn('39.1', registro.ultimo_error_evaluacion_alertas)
        self.assertIsNotNone(registro.fecha_ultima_evaluacion_alertas)

        # El reporte del paciente nunca se pierde por un fallo del motor.
        self.checkin.refresh_from_db()
        self.assertEqual(self.checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(self.checkin.registro_id, registro.pk)
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)

    def test_registro_fallido_en_el_bot_se_recupera_con_el_command(self):
        """El motor no evaluó nada, así que el registro debe volver a la cola.

        Nace en verde: hoy el registro queda PENDIENTE, que el command también
        recoge. Está aquí para que la corrección del estado ERROR no rompa la
        recuperación — es la mitad del hallazgo que NO debe cambiar.
        """
        from unittest.mock import patch

        from django.core.management import call_command

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=RuntimeError('fallo transitorio del motor'),
        ):
            self._completar_flujo()

        call_command('reintentar_evaluaciones_alertas', verbosity=0)

        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(registro.ultimo_error_evaluacion_alertas, '')


@freeze_time(ANCLA_MEDIANOCHE)
class BugsDelPacienteTests(TestCase):
    """Regresión de los bugs del bot que tocaban al paciente (loop 08/09/2026).

    Los ocho hallazgos se **reprodujeron ejecutando código** antes de tocar
    nada (`proceso/verificaciones/2026-09-08_reproduccion_bugs_paciente.py`), y
    cada prueba de aquí se verificó revirtiendo su arreglo y viéndola caer
    (`proceso/verificaciones/2026-09-08_verificacion_bugs_paciente.py`).

    Fichas: **D19** (temperatura ambigua), **D20** (el dato que el paciente no
    puede dar), **D21** (palabra de auxilio). Más BE-01 y DB-01.
    """

    TELEFONO = '+573009990001'
    WA = 'whatsapp:+573009990001'

    def setUp(self):
        self.paciente = Paciente.objects.create(
            medico_responsable=medico_de_pruebas(),
            nombre_completo='Paciente Bugs',
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )

    def _checkin(self, orden=1, etiqueta=None, horas_atras=0):
        return CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=orden,
            etiqueta=etiqueta or CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timedelta(hours=horas_atras),
        )

    def _flujo(self, temperatura='37.0', dolor='3'):
        """Recorre el cuestionario entero y devuelve la respuesta final."""
        def env(t):
            return bot.procesar_mensaje(self.WA, t)
        env('hola')
        env(temperatura)
        env(dolor)
        env('no')          # sin drenaje
        env('si, 0')       # gases / náuseas
        env('nada')        # hinchazón
        env('78')          # frecuencia cardíaca
        env('16')          # frecuencia respiratoria
        return env('si')   # tolerancia a líquidos

    # --- D19: temperatura ambigua ---

    def test_temperatura_sin_separador_se_rechaza(self):
        """`379` no puede volver a entrar como 37,0 (DB-02).

        Era el bug más silencioso del sistema: el paciente con 37,9 de fiebre
        quedaba registrado en 37,0, sin alerta y con el mensaje de cierre
        normal. Ni él ni el médico podían notarlo, porque 37,0 es un valor
        perfectamente creíble en un postoperatorio.
        """
        for ambigua in ('379', '37 9', '375', '3790'):
            with self.subTest(entrada=ambigua):
                self.assertIsNone(bot._parse_temperatura(ambigua))

    def test_temperatura_bien_escrita_se_acepta(self):
        """La otra dirección: endurecer el parser no puede rechazar lo válido."""
        casos = {
            '37.9': Decimal('37.9'),
            '37,9': Decimal('37.9'),
            '38': Decimal('38'),
            'tengo 37.5 grados': Decimal('37.5'),
            '  36.6  ': Decimal('36.6'),
        }
        for entrada, esperada in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(bot._parse_temperatura(entrada), esperada)

    def test_temperatura_ambigua_pide_de_nuevo_y_no_crea_registro(self):
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        respuesta = bot.procesar_mensaje(self.WA, '379')
        self.assertEqual(respuesta, bot.MSG_REINTENTO_TEMPERATURA)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_el_bot_devuelve_la_temperatura_que_anoto(self):
        """UX-B05: el bot nunca decía lo que había entendido.

        Protege contra lo que el rechazo no cubre: el **dedazo válido**. Quien
        quiso escribir 37.5 y escribió 38.5 pasa todos los filtros, porque es
        una temperatura perfectamente posible, y hasta el 08/09/2026 no tenía
        forma de enterarse. El médico tampoco.
        """
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        respuesta = bot.procesar_mensaje(self.WA, '37.5')
        self.assertIn('37.5', respuesta)
        self.assertIn('anoté', respuesta.lower())

    def test_el_eco_va_antes_de_que_exista_ninguna_alerta(self):
        """Y por eso no puede revelar ninguna clasificación clínica.

        El primer sitio donde se puso el eco fue el mensaje de cierre, y ahí
        chocaba con la decisión del Bloque B (02/07/2026): el paciente ve la
        recomendación de severidad, **nunca** los valores que la dispararon. Lo
        destapó `test_alerta_no_se_muestra_al_paciente`, que llevaba dos meses
        protegiendo esa regla. En el paso de la temperatura no hay conflicto
        posible: todavía no se ha evaluado nada.
        """
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        respuesta = bot.procesar_mensaje(self.WA, '38.5')   # luego dará SEPSIS/ALTA

        self.assertIn('38.5', respuesta)
        self.assertEqual(Alerta.objects.count(), 0)
        for prohibida in ('sepsis', 'fiebre', 'alerta', 'urgencias', 'riesgo'):
            self.assertNotIn(prohibida, respuesta.lower())

    def test_el_cierre_no_repite_los_valores_que_dispararon_la_alerta(self):
        """La regla del Bloque B, fijada también desde este loop."""
        self._checkin()
        respuesta = self._flujo(temperatura='38.5')
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)
        self.assertNotIn('38.5', respuesta)

    # --- D20: el dato que el paciente no puede dar ---

    def test_saltar_temperatura_deja_reportar_todo_lo_demas(self):
        """Sin termómetro ya no se pierde el turno entero (UX-B04 / BE-07)."""
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        eco = bot.procesar_mensaje(self.WA, 'saltar')
        self.assertIn('sin medir', eco)

        bot.procesar_mensaje(self.WA, '3')
        bot.procesar_mensaje(self.WA, 'no')
        bot.procesar_mensaje(self.WA, 'si, 0')
        bot.procesar_mensaje(self.WA, 'nada')
        bot.procesar_mensaje(self.WA, '78')
        bot.procesar_mensaje(self.WA, '16')
        respuesta = bot.procesar_mensaje(self.WA, 'si')

        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        registro = RegistroDiario.objects.get()
        self.assertIsNone(registro.temperatura)
        self.assertEqual(registro.dolor_eva, 3)
        self.assertEqual(registro.frecuencia_cardiaca, 78)

    def test_la_frase_natural_del_paciente_tambien_salta(self):
        """«no tengo termómetro» es la respuesta real, no «saltar».

        El primer arreglo exigía coincidencia exacta, así que la frase más
        natural seguía dejando al paciente atascado en la pregunta 1 — el
        mismo caso que D20 venía a resolver. Lo destapó volver a ejecutar la
        reproducción después de darlo por arreglado.
        """
        for frase in ('saltar', 'no tengo termometro', 'no tengo termómetro',
                      'no puedo medirla ahora', 'no se'):
            with self.subTest(frase=frase):
                self.assertTrue(bot._es_salto(frase))

    def test_una_temperatura_no_se_confunde_con_un_salto(self):
        """La otra dirección: aflojar el salto no puede tragarse un dato."""
        for frase in ('37.5', 'no', 'mucho', 'nada', '0', 'si'):
            with self.subTest(frase=frase):
                self.assertFalse(bot._es_salto(frase))

    def test_sin_temperatura_no_se_evalua_la_regla_de_fiebre(self):
        """Un día sin dato es un desconocido, no una temperatura baja (D20)."""
        self._checkin()
        self._flujo(temperatura='saltar')
        self.assertEqual(Alerta.objects.filter(tipo='SEPSIS').count(), 0)

    def test_dolor_cero_es_valido_y_no_alerta(self):
        self._checkin()
        self._flujo(dolor='0')
        self.assertEqual(RegistroDiario.objects.get().dolor_eva, 0)
        self.assertEqual(Alerta.objects.filter(tipo='DOLOR_AGUDO').count(), 0)

    def test_dolor_fuera_de_rango_sigue_rechazado(self):
        """La otra dirección: abrir el 0 no puede abrir el 11."""
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        self.assertEqual(bot.procesar_mensaje(self.WA, '11'), bot.MSG_REINTENTO_DOLOR)

    # --- DB-01: el techo de náuseas ---

    def test_nauseas_desmesuradas_se_rechazan_en_el_bot(self):
        """`"si, 99999"` reventaba la base y el webhook devolvía 500.

        El paciente escribía y **no recibía ninguna respuesta**: no podía saber
        si su reporte había entrado.
        """
        self.assertEqual(bot._parse_gases_nauseas('si, 99999'), (None, None))
        self.assertEqual(bot._parse_gases_nauseas('si, 21'), (None, None))

    def test_nauseas_dentro_de_rango_siguen_pasando(self):
        """La otra dirección: el techo no puede comerse los valores reales."""
        self.assertEqual(bot._parse_gases_nauseas('si, 0'), (True, 0))
        self.assertEqual(bot._parse_gases_nauseas('no, 20'), (False, 20))

    # --- D21: palabra de auxilio ---

    def test_auxilio_a_mitad_del_cuestionario_corta_y_alerta(self):
        """El caso reproducido: se guardaba como hinchazón y el bot seguía."""
        self._checkin()
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        bot.procesar_mensaje(self.WA, '3')
        bot.procesar_mensaje(self.WA, 'no')
        bot.procesar_mensaje(self.WA, 'si, 0')
        respuesta = bot.procesar_mensaje(
            self.WA, 'estoy sangrando mucho, necesito ayuda')

        self.assertEqual(respuesta, bot.MSG_AUXILIO)
        alerta = Alerta.objects.get(tipo='AUXILIO')
        self.assertEqual(alerta.severidad, 'ALTA')
        self.assertFalse(alerta.resuelta)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_INICIO)
        self.assertIsNone(conv.temp_hinchazon_abdominal)

    def test_auxilio_fuera_del_cuestionario_tambien_alerta(self):
        respuesta = bot.procesar_mensaje(self.WA, 'AYUDA')
        self.assertEqual(respuesta, bot.MSG_AUXILIO)
        self.assertEqual(Alerta.objects.filter(tipo='AUXILIO').count(), 1)

    def test_las_respuestas_normales_no_disparan_auxilio(self):
        """La otra dirección, y la que decide si esto sirve de algo.

        Una palabra de auxilio que salta con las respuestas del cuestionario
        llena el panel de ruido y acaba ignorada. `ayudar` no cuenta, y
        `urgencias` tampoco: aparece en preguntas normales del paciente.
        """
        for normal in ('no', 'si', 'mucho', 'nada', '37.5', 'si, 0', 'saltar',
                       'me puedes ayudar con la app', 'debo ir a urgencias?'):
            with self.subTest(texto=normal):
                self.assertFalse(bot._es_auxilio(normal))

    def test_el_saludo_le_anuncia_la_palabra_al_paciente(self):
        """Una palabra de auxilio que nadie sabe que existe no sirve de nada."""
        self.assertIn('AYUDA', bot.MSG_PREGUNTA_TEMPERATURA)

    def test_el_mensaje_de_auxilio_manda_a_buscar_atencion(self):
        """La única vez que el bot da una indicación, y es deliberado."""
        texto = bot.MSG_AUXILIO.lower()
        self.assertIn('urgencias', texto)
        self.assertIn('123', texto)

    # --- BE-01: el turno de la tarde ---

    def _abandonar_la_manana_y_dejar_que_venza(self, manana):
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        conv = ConversacionWhatsApp.objects.get()
        # El cron no cierra un turno con conversación viva y reciente (guarda
        # deliberada), así que se envejece la conversación: el paciente dejó el
        # móvil por la mañana y vuelve por la tarde.
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(hours=11))
        call_command('cerrar_checkins_vencidos', stdout=StringIO(), stderr=StringIO())
        manana.refresh_from_db()
        self.assertEqual(manana.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)
        return conv

    def test_el_turno_de_la_tarde_no_se_niega(self):
        """El bot decía "no tienes un reporte pendiente" teniéndolo (BE-01).

        Y solo lo recuperaba si el paciente insistía con un segundo mensaje,
        justo cuando había vuelto a colaborar.
        """
        manana = self._checkin(orden=1, horas_atras=11)
        self._checkin(orden=2, etiqueta=CheckInProgramado.ETIQUETA_TARDE,
                      horas_atras=1)
        conv = self._abandonar_la_manana_y_dejar_que_venza(manana)

        respuesta = bot.procesar_mensaje(self.WA, 'hola')

        self.assertNotEqual(respuesta, bot.MSG_SIN_CHECKIN)
        self.assertEqual(respuesta, bot.MSG_TURNO_SIGUIENTE)
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertEqual(conv.checkin_actual.etiqueta,
                         CheckInProgramado.ETIQUETA_TARDE)

    def test_sin_turnos_pendientes_si_se_dice_que_no_hay(self):
        """La otra dirección: la corrección no puede inventar turnos."""
        manana = self._checkin(orden=1, horas_atras=11)
        self._abandonar_la_manana_y_dejar_que_venza(manana)

        self.assertEqual(bot.procesar_mensaje(self.WA, 'hola'), bot.MSG_SIN_CHECKIN)
