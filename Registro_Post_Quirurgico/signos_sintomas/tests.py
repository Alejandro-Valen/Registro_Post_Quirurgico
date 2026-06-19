from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import bot
from .alert_engine import evaluar_registro
from .models import Alerta, ConversacionWhatsApp, Paciente, RegistroDiario


class AlertEngineTests(TestCase):
    def test_temperatura_alta_crea_alerta_sepsis(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Prueba",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("38.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(Alerta.objects.count(), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_drenaje_purulento_crea_alerta_fuga_anastomotica(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Drenaje",
            telefono_whatsapp="+573004445566",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=True,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_nauseas_mayor_a_tres_crea_alerta_ileo_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nauseas",
            telefono_whatsapp="+573007778899",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=4,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "ILEO_PARALITICO")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_tres_registros_sin_gases_crea_alerta_ileo_alta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Gases",
            telefono_whatsapp="+573006661122",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registros = [
            RegistroDiario.objects.create(
                paciente=paciente,
                temperatura=Decimal("37.0"),
                dolor_eva=3,
                aspecto_drenaje="seroso",
                presencia_gases=False,
                episodios_nauseas=0,
            )
            for _ in range(3)
        ]

        alertas = evaluar_registro(registros[-1])

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "ILEO_PARALITICO")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_registro_sin_red_flags_no_crea_alertas(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Estable",
            telefono_whatsapp="+573005551234",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=1,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])
        self.assertEqual(Alerta.objects.count(), 0)

    def test_registro_con_varias_red_flags_crea_varias_alertas(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Multiple",
            telefono_whatsapp="+573005550000",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("38.5"),
            dolor_eva=4,
            tiene_drenaje=True,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=4,
        )

        alertas = evaluar_registro(registro)
        tipos_alerta = {alerta.tipo for alerta in alertas}

        self.assertEqual(len(alertas), 3)
        self.assertEqual(Alerta.objects.count(), 3)
        self.assertEqual(
            tipos_alerta,
            {"SEPSIS", "FUGA_ANASTOMOTICA", "ILEO_PARALITICO"},
        )

    def test_valores_limite_no_crean_alertas(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Limite",
            telefono_whatsapp="+573005559999",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        # 37.4°C: justo por debajo del umbral de subfebrícula (37.5°C)
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.4"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=3,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])
        self.assertEqual(Alerta.objects.count(), 0)

    def test_drenaje_seroso_con_tiene_drenaje_crea_baja(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Seroso",
            telefono_whatsapp="+573001110001",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "BAJA")

    def test_drenaje_hematico_crea_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hematico",
            telefono_whatsapp="+573001110002",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="hematico",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_drenaje_turbio_crea_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Turbio",
            telefono_whatsapp="+573001110003",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="turbio",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_sin_drenaje_no_genera_alerta_drenaje(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Drenaje",
            telefono_whatsapp="+573001110004",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="sin_drenaje",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])

    def test_tiene_drenaje_null_no_genera_alerta_drenaje(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Legacy",
            telefono_whatsapp="+573001110005",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        # tiene_drenaje=None simula un registro anterior a esta versión
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])

    def test_temperatura_379_crea_alerta_sepsis_alta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Temp Alta",
            telefono_whatsapp="+573008880001",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.9"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_subfebricula_un_solo_dia_no_crea_alerta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Subfebricula Un Dia",
            telefono_whatsapp="+573008880002",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.6"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(alertas, [])

    def test_subfebricula_dos_dias_consecutivos_crea_alerta_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Subfebricula Persistente",
            telefono_whatsapp="+573008880003",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        ayer = timezone.now() - timedelta(days=1)
        registro_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.6"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=registro_ayer.pk).update(
            fecha_registro=ayer
        )
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.7"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_hoy)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_temperatura_normal_no_crea_alerta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Temp Normal",
            telefono_whatsapp="+573008880004",
            fecha_cirugia=timezone.now().date(),
            medico_responsable="Medico Prueba",
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("36.8"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(alertas, [])


class BotWhatsAppTests(TestCase):
    TELEFONO = "+573001112233"
    TELEFONO_TWILIO = "whatsapp:+573001112233"

    def _crear_paciente(self):
        return Paciente.objects.create(
            nombre_completo="Paciente Bot",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable="Medico Prueba",
        )

    def _completar_flujo(self, gases_nauseas="sí, 0", temperatura="37.0",
                         tiene_drenaje="sí", aspecto="1", cantidad="normal"):
        """Recorre las 6 preguntas y devuelve la respuesta final del bot."""
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")          # -> temperatura
        bot.procesar_mensaje(self.TELEFONO_TWILIO, temperatura)     # -> dolor
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")             # -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, tiene_drenaje)   # -> aspecto (si sí)
        bot.procesar_mensaje(self.TELEFONO_TWILIO, aspecto)         # -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, cantidad)        # -> gases/nauseas
        return bot.procesar_mensaje(self.TELEFONO_TWILIO, gases_nauseas)

    def test_paciente_no_registrado(self):
        respuesta = bot.procesar_mensaje("whatsapp:+570000000000", "hola")
        self.assertEqual(respuesta, bot.MSG_NO_REGISTRADO)
        self.assertEqual(ConversacionWhatsApp.objects.count(), 0)

    def test_primer_mensaje_inicia_cuestionario(self):
        self._crear_paciente()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)

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
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_COMPLETADO)
        self.assertIsNone(conv.temp_temperatura)  # parciales limpiados

    def test_alerta_no_se_muestra_al_paciente(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # dispara SEPSIS
        # La alerta se crea para el oncólogo...
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)
        # ...pero el paciente solo ve la confirmación neutra.
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        self.assertNotIn("sepsis", respuesta.lower())
        self.assertNotIn("alerta", respuesta.lower())

    def test_temperatura_invalida_reintenta(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no sé")
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


class WebhookWhatsAppTests(TestCase):
    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_post_valido_devuelve_twiml(self):
        Paciente.objects.create(
            nombre_completo="Paciente Webhook",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            medico_responsable="Medico Prueba",
        )
        respuesta = self.client.post(
            self.url, {'From': 'whatsapp:+573001112233', 'Body': 'hola'}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertIn('temperatura', respuesta.content.decode().lower())

    def test_get_no_permitido(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 405)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='token_falso')
    def test_firma_invalida_devuelve_403(self):
        respuesta = self.client.post(
            self.url,
            {'From': 'whatsapp:+573001112233', 'Body': 'hola'},
            HTTP_X_TWILIO_SIGNATURE='firma_invalida',
        )
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='')
    def test_token_faltante_falla_seguro(self):
        # Escenario peligroso: validación activa pero token olvidado en .env.
        # Debe fallar con error claro de configuración, no saltarse la validación.
        with self.assertRaises(ImproperlyConfigured):
            self.client.post(
                self.url, {'From': 'whatsapp:+573001112233', 'Body': 'hola'}
            )
