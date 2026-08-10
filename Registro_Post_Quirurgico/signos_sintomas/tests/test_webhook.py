"""Webhook de Twilio: firma, limites de tasa, concurrencia y carga.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Alerta,
    CheckInProgramado,
    ConversacionWhatsApp,
    NotificacionAlerta,
    Paciente,
    RecepcionWebhookTwilio,
    RegistroDiario,
)
from .soporte import medico_de_pruebas


class WebhookWhatsAppTests(TestCase):
    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_post_valido_devuelve_twiml(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Webhook",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        # Bloque 3: el bot requiere CheckInProgramado PENDIENTE para iniciar el flujo
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        respuesta = self.client.post(
            self.url,
            {
                'From': 'whatsapp:+573001112233',
                'Body': 'hola',
                'MessageSid': 'SMwebhookvalido0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertIn('temperatura', respuesta.content.decode().lower())

    @override_settings(
        TWILIO_VALIDATE_SIGNATURE=True,
        TWILIO_AUTH_TOKEN='token_prueba_firma_valida',
    )
    def test_firma_twilio_valida_permite_procesar(self):
        from twilio.request_validator import RequestValidator

        payload = {
            'From': 'whatsapp:+573009999991',
            'Body': 'hola',
            'MessageSid': 'SMfirmavalida0001',
        }
        firma = RequestValidator(
            'token_prueba_firma_valida'
        ).compute_signature(f'http://testserver{self.url}', payload)

        respuesta = self.client.post(
            self.url,
            payload,
            HTTP_X_TWILIO_SIGNATURE=firma,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertEqual(
            RecepcionWebhookTwilio.objects.get().estado,
            RecepcionWebhookTwilio.ESTADO_COMPLETADO,
        )

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

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='token_falso')
    def test_header_ausente_devuelve_403(self):
        # Sin X-Twilio-Signature en el request → la firma vacía no valida → 403.
        respuesta = self.client.post(
            self.url,
            {'From': 'whatsapp:+573001112233', 'Body': 'hola'},
            # No se incluye HTTP_X_TWILIO_SIGNATURE
        )
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_body_vacio_devuelve_twiml(self):
        # Body ausente / vacío no debe romper el webhook; paciente desconocido
        # recibe respuesta amable.
        respuesta = self.client.post(
            self.url,
            {
                'From': 'whatsapp:+573009999999',
                'Body': '',
                'MessageSid': 'SMbodyvacio0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_sid_ausente_devuelve_400_sin_procesar(self):
        from unittest.mock import patch

        with patch('signos_sintomas.views.procesar_mensaje') as procesar:
            respuesta = self.client.post(
                self.url,
                {'From': 'whatsapp:+573009999999', 'Body': 'hola'},
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.content, b'')
        procesar.assert_not_called()
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), 0)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_idempotencia_mismo_sid_ignora_segundo_mensaje(self):
        # Twilio puede reintentar un webhook con el mismo MessageSid.
        # El segundo mensaje con el mismo SID debe devolver TwiML vacío sin
        # ejecutar la lógica del bot de nuevo.
        Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Idempotencia",
            telefono_whatsapp="+573002223344",
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            consentimiento_informado=True,
        )
        payload = {
            'From': 'whatsapp:+573002223344',
            'Body': 'hola',
            'MessageSid': 'SMidempotencia0001',
        }
        primera = self.client.post(self.url, payload)
        segunda = self.client.post(self.url, payload)

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        # Segunda respuesta es TwiML vacío (sin <Message>)
        self.assertNotIn(b'<Message>', segunda.content)
        # Primera sí tiene contenido
        self.assertIn(b'<Message>', primera.content)
        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMidempotencia0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 1)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_error_del_bot_deja_recepcion_reintentable(self):
        from unittest.mock import patch

        payload = {
            'From': 'whatsapp:+573002223355',
            'Body': 'contenido sensible que no debe persistirse',
            'MessageSid': 'SMreintento0001',
        }
        with patch(
            'signos_sintomas.views.procesar_mensaje',
            side_effect=RuntimeError('detalle sensible'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)

        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMreintento0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_ERROR)

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='Reporte recibido',
        ) as procesar:
            respuesta = self.client.post(self.url, payload)

        self.assertEqual(respuesta.status_code, 200)
        procesar.assert_called_once()
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 2)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_fallo_antes_de_confirmar_recibo_revierte_el_avance_del_bot(self):
        from unittest.mock import patch

        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo='Paciente Atomicidad Webhook',
            telefono_whatsapp='+573002223388',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        payload = {
            'From': 'whatsapp:+573002223388',
            'Body': 'hola',
            'MessageSid': 'SMatomicidad0001',
        }

        with patch(
            'signos_sintomas.views._marcar_recepcion_completada',
            side_effect=RuntimeError('caída antes del commit'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)

        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMatomicidad0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_ERROR)
        self.assertFalse(ConversacionWhatsApp.objects.filter(paciente=paciente).exists())

        respuesta = self.client.post(self.url, payload)

        self.assertEqual(respuesta.status_code, 200)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 2)
        conversacion = ConversacionWhatsApp.objects.get(paciente=paciente)
        self.assertEqual(
            conversacion.estado,
            ConversacionWhatsApp.ESTADO_TEMPERATURA,
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_sid_en_proceso_devuelve_503_para_que_twilio_reintente(self):
        from unittest.mock import patch

        RecepcionWebhookTwilio.objects.create(message_sid='SMenproceso0001')

        with patch('signos_sintomas.views.procesar_mensaje') as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573002223366',
                    'Body': 'hola',
                    'MessageSid': 'SMenproceso0001',
                },
            )

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta['Retry-After'], '30')
        procesar.assert_not_called()

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_token_idempotencia_se_guarda_sin_datos_medicos(self):
        from unittest.mock import patch

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='Reporte recibido',
        ):
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573002223377',
                    'Body': 'dolor 9 y fiebre',
                    'MessageSid': 'SMtoken0001',
                },
                HTTP_I_TWILIO_IDEMPOTENCY_TOKEN='token-reintento-1',
            )

        self.assertEqual(respuesta.status_code, 200)
        recepcion = RecepcionWebhookTwilio.objects.get(message_sid='SMtoken0001')
        self.assertEqual(recepcion.idempotency_token, 'token-reintento-1')
        valores = ' '.join(str(valor) for valor in recepcion.__dict__.values())
        self.assertNotIn('dolor 9', valores)
        self.assertNotIn('+573002223377', valores)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_rate_limit_excedido_informa_sin_procesar_el_mensaje(self):
        """Superado el límite, el mensaje no se procesa y el paciente recibe
        orientación.

        POR QUÉ CAMBIÓ (no es un ajuste, cambió el requisito — D2 punto 3):
        antes la verificación del rate limit ocurría DESPUÉS de reclamar el
        SID, así que un mensaje limitado dejaba una fila COMPLETADO en
        RecepcionWebhookTwilio. Ahora la verificación ocurre ANTES de reclamar
        el SID, de modo que un mensaje limitado no debe dejar fila alguna. La
        aserción sobre la fila se invirtió para reflejarlo; las de la respuesta
        al paciente no cambian.
        """
        from signos_sintomas.views import _LIMITE_MENSAJES_HORA, _MSG_RATE_LIMIT
        telefono = 'whatsapp:+573005556677'
        # Forzar el contador de cache directamente al límite
        clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
        cache.set(clave, _LIMITE_MENSAJES_HORA, 3600)

        respuesta = self.client.post(
            self.url,
            {
                'From': telefono,
                'Body': 'hola',
                'MessageSid': 'SMratelimit0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b'<Message>', respuesta.content)
        self.assertIn(_MSG_RATE_LIMIT.encode(), respuesta.content)
        self.assertFalse(
            RecepcionWebhookTwilio.objects.filter(
                message_sid='SMratelimit0001',
            ).exists()
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_webhook_falla_abierto_si_el_cache_no_responde(self):
        """D2 (punto 1): si el cache no responde, el webhook NO puede dejar sin
        respuesta al paciente. La firma de Twilio sigue protegiendo la puerta,
        así que se procesa el mensaje (fallar abierto) en vez de devolver 500.
        """
        from unittest.mock import MagicMock, patch

        cache_caido = MagicMock()
        cache_caido.incr.side_effect = ConnectionError('redis inalcanzable')
        with patch('signos_sintomas.views.cache', cache_caido), patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='respuesta del bot',
        ) as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573001112299',
                    'Body': 'hola',
                    'MessageSid': 'SMcachecaido0001',
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        procesar.assert_called_once()

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_limite_por_hora_permite_mas_de_veinte_mensajes(self):
        """D2 (punto 4): el límite sube de 20 a 60. 30 mensajes en una hora ya
        no bloquean al paciente — un cuestionario completo son ~11 mensajes y
        la población objetivo (personas mayores, recién operadas) reintenta.
        """
        from unittest.mock import patch

        from signos_sintomas.views import _MSG_RATE_LIMIT

        telefono = 'whatsapp:+573005556699'
        clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
        cache.set(clave, 30, 3600)

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='respuesta del bot',
        ) as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': telefono,
                    'Body': 'hola',
                    'MessageSid': 'SMlimite60000001',
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(_MSG_RATE_LIMIT.encode(), respuesta.content)
        procesar.assert_called_once()

class WebhookFlujoCompletoTests(TestCase):
    TELEFONO = '+573006660001'

    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')
        medico = get_user_model().objects.create_user(
            username='medico_flujo_webhook',
            password='pass',
            email='medico-flujo@test.com',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo='Paciente Flujo Webhook',
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
            medico_responsable=medico,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_recorrido_completo_por_webhook_crea_registro_alerta_y_outbox(self):
        respuestas = [
            'hola', '38.5', '3', 'sí', '1', 'normal',
            'sí, 0', 'nada', '78', '16', 'sí',
        ]

        ultima_respuesta = None
        for indice, texto in enumerate(respuestas, start=1):
            ultima_respuesta = self.client.post(
                self.url,
                {
                    'From': f'whatsapp:{self.TELEFONO}',
                    'Body': texto,
                    'MessageSid': f'SMflujocompleto{indice:04d}',
                },
            )
            self.assertEqual(ultima_respuesta.status_code, 200)

        self.assertIn('urgencias', ultima_respuesta.content.decode().lower())
        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.checkin.refresh_from_db()
        conversacion = ConversacionWhatsApp.objects.get(paciente=self.paciente)
        alerta = Alerta.objects.get(paciente=self.paciente, tipo='SEPSIS')
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)

        self.assertEqual(registro.temperatura, Decimal('38.5'))
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(self.checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(self.checkin.registro, registro)
        self.assertEqual(conversacion.estado, ConversacionWhatsApp.ESTADO_COMPLETADO)
        self.assertEqual(alerta.severidad, 'ALTA')
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.destinatario, 'medico-flujo@test.com')
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), len(respuestas))
        self.assertFalse(
            RecepcionWebhookTwilio.objects.exclude(
                estado=RecepcionWebhookTwilio.ESTADO_COMPLETADO,
            ).exists()
        )

class WebhookConcurrenciaTests(TransactionTestCase):
    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_dos_requests_simultaneos_del_mismo_sid_procesan_una_vez(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from django.test import Client

        iniciado = Event()
        liberar = Event()
        url = reverse('signos_sintomas:webhook_whatsapp')
        payload = {
            'From': 'whatsapp:+573006660002',
            'Body': 'hola',
            'MessageSid': 'SMconcurrente0001',
        }

        def procesar_lento(*args, **kwargs):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el primer worker.')
            return 'Reporte recibido'

        def enviar():
            close_old_connections()
            try:
                return Client().post(url, payload)
            finally:
                close_old_connections()

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            side_effect=procesar_lento,
        ) as procesar:
            with ThreadPoolExecutor(max_workers=2) as executor:
                primera_futura = executor.submit(enviar)
                self.assertTrue(iniciado.wait(timeout=10))
                segunda = executor.submit(enviar).result(timeout=10)
                liberar.set()
                primera = primera_futura.result(timeout=10)

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 503)
        self.assertEqual(segunda['Retry-After'], '30')
        procesar.assert_called_once()
        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMconcurrente0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 1)

class WebhookCargaTests(TransactionTestCase):
    PACIENTES = 50

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_rafaga_50_pacientes_responde_antes_del_timeout_twilio(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from time import perf_counter

        from django.test import Client

        url = reverse('signos_sintomas:webhook_whatsapp')
        barrera = Barrier(self.PACIENTES)
        respuestas = [
            'hola', '37.0', '3', 'sí', '1', 'normal',
            'sí, 0', 'nada', '78', '16', 'sí',
        ]
        for indice in range(self.PACIENTES):
            telefono = f'+5730077{indice:05d}'
            paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
                nombre_completo=f'Paciente Carga {indice:02d}',
                telefono_whatsapp=telefono,
                fecha_cirugia=timezone.localdate() - timedelta(days=2),
                consentimiento_informado=True,
            )
            CheckInProgramado.objects.create(
                paciente=paciente,
                fecha_dia=timezone.localdate(),
                orden=1,
                etiqueta=CheckInProgramado.ETIQUETA_MANANA,
                hora_programada=timezone.now(),
            )

        def enviar(indice):
            close_old_connections()
            try:
                telefono = f'+5730077{indice:05d}'
                barrera.wait(timeout=20)
                cliente = Client()
                resultados_paciente = []
                for paso, texto in enumerate(respuestas, start=1):
                    inicio = perf_counter()
                    respuesta = cliente.post(
                        url,
                        {
                            'From': f'whatsapp:{telefono}',
                            'Body': texto,
                            'MessageSid': f'SMcarga{indice:03d}{paso:02d}',
                        },
                    )
                    resultados_paciente.append(
                        (respuesta.status_code, perf_counter() - inicio)
                    )
                return resultados_paciente
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=self.PACIENTES) as executor:
            lotes = list(executor.map(enviar, range(self.PACIENTES)))

        resultados = [resultado for lote in lotes for resultado in lote]
        estados = [estado for estado, _ in resultados]
        duraciones = [duracion for _, duracion in resultados]
        total_webhooks = self.PACIENTES * len(respuestas)
        self.assertEqual(estados, [200] * total_webhooks)
        self.assertLess(max(duraciones), 15)
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), total_webhooks)
        self.assertEqual(ConversacionWhatsApp.objects.count(), self.PACIENTES)
        self.assertEqual(RegistroDiario.objects.count(), self.PACIENTES)
        self.assertEqual(
            CheckInProgramado.objects.filter(
                estado=CheckInProgramado.ESTADO_COMPLETADO,
            ).count(),
            self.PACIENTES,
        )
        self.assertFalse(
            RecepcionWebhookTwilio.objects.exclude(
                estado=RecepcionWebhookTwilio.ESTADO_COMPLETADO,
            ).exists()
        )
