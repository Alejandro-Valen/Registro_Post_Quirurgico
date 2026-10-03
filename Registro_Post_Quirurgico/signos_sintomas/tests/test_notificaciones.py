"""Bandeja durable de correo al medico y sus reintentos.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time

from ..alert_engine import evaluar_registro
from ..models import (
    Alerta,
    NotificacionAlerta,
    Paciente,
    RegistroDiario,
)


class AlertaEmailNotificacionTests(TestCase):
    """Bandeja durable para avisar al médico por una alerta ALTA."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dr_email', password='pass', email='dr@test.com',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Email",
            cedula="800111222",
            telefono_whatsapp="+573019990002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )

    def _crear_alerta_alta(self):
        return Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Fiebre alta de prueba.',
        )

    def test_alerta_alta_se_encola_sin_conexion_de_red(self):
        from django.core import mail
        alerta = self._crear_alerta_alta()

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.destinatario, self.medico.email)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.intentos, 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PANEL_MEDICO_URL='https://ejemplo.test/acceso-seguro/')
    def test_procesador_envia_aviso_sin_datos_medicos(self):
        from django.core import mail
        from django.core.management import call_command

        alerta = self._crear_alerta_alta()
        call_command('procesar_notificaciones_email', verbosity=0)

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.medico.email])
        self.assertIn('Alerta clínica alta', correo.subject)
        self.assertIn(f'alerta #{alerta.pk}', correo.body)
        self.assertIn('https://ejemplo.test/acceso-seguro/', correo.body)
        self.assertNotIn(self.paciente.nombre_completo, correo.body)
        self.assertNotIn(self.paciente.telefono_whatsapp, correo.body)
        self.assertNotIn(self.paciente.cedula, correo.body)
        self.assertNotIn(alerta.mensaje, correo.body)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(notificacion.intentos, 1)
        self.assertIsNotNone(notificacion.fecha_envio)

    def test_procesador_es_idempotente_para_notificacion_enviada(self):
        from django.core import mail
        from django.core.management import call_command

        self._crear_alerta_alta()
        call_command('procesar_notificaciones_email', verbosity=0)
        call_command('procesar_notificaciones_email', verbosity=0)
        self.assertEqual(len(mail.outbox), 1)

    def test_fallo_externo_programa_reintento_sin_perder_la_fila(self):
        from unittest.mock import patch

        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        # TEST-06 (02/10/2026): hasta esta fecha se comprobaba solo que el
        # reintento quedara «después de ahora», y cualquier backoff positivo
        # —un minuto, un día— pasaba. Con el reloj congelado, el primero cae
        # exactamente a los 5 minutos (D6). El segundo de margen deja el
        # instante por delante de la creación de la fila, que ya está vencida.
        instante = timezone.now().replace(microsecond=0) + timedelta(seconds=1)
        with freeze_time(instante), patch(
            'signos_sintomas.notificaciones.send_mail',
            side_effect=TimeoutError('detalle que no debe persistirse'),
        ), self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.intentos, 1)
        self.assertEqual(notificacion.ultimo_error, 'TimeoutError')
        self.assertEqual(
            notificacion.proximo_intento, instante + timedelta(minutes=5)
        )
        self.assertNotIn('detalle', notificacion.ultimo_error)

    def test_backoff_sigue_la_escalera_de_d6(self):
        """TEST-06: 5, 15, 45 y 135 minutos, y desde ahí cada 6 horas (D6).

        Cada reintento se procesa justo cuando vence, con el reloj congelado, y
        se fija el minuto exacto del siguiente. La cifra no es cosmética: con
        esta escalera, el tope de 10 intentos son unas 39 horas, que es lo que
        D6 decidió que tarde un correo de alerta ALTA en declararse FALLIDO.
        El quinto intento es la frontera del tope: 5·3⁴ = 405 min se recorta a 360.
        """
        from unittest.mock import patch

        from ..notificaciones import procesar_notificaciones_pendientes

        alerta = self._crear_alerta_alta()
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        instante = timezone.now().replace(microsecond=0) + timedelta(seconds=1)
        NotificacionAlerta.objects.filter(pk=notificacion.pk).update(
            proximo_intento=instante,
        )

        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=TimeoutError('proveedor caído'),
        ):
            for intento, minutos in enumerate([5, 15, 45, 135, 360, 360], start=1):
                with self.subTest(intento=intento), freeze_time(instante):
                    procesar_notificaciones_pendientes()
                    notificacion.refresh_from_db()
                    self.assertEqual(notificacion.intentos, intento)
                    self.assertEqual(
                        notificacion.proximo_intento,
                        instante + timedelta(minutes=minutos),
                    )
                instante = notificacion.proximo_intento

    def test_notificacion_se_marca_fallida_tras_agotar_reintentos(self):
        """D6: el correo de alerta ALTA no se reintenta para siempre. Tras 10
        intentos fallidos la notificación queda en estado terminal FALLIDA en
        vez de reprogramarse — un correo de alerta ALTA que falla de forma
        permanente es información clínica que no llegó, y debe hacerse visible,
        no reintentarse en silencio.
        """
        from unittest.mock import patch

        from ..notificaciones import procesar_notificaciones_pendientes

        alerta = self._crear_alerta_alta()
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        # Ya acumuló 9 intentos fallidos; el décimo también falla.
        NotificacionAlerta.objects.filter(pk=notificacion.pk).update(
            intentos=9,
            proximo_intento=timezone.now() - timedelta(seconds=1),
        )

        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=TimeoutError('fallo externo persistente'),
        ):
            procesar_notificaciones_pendientes()

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.intentos, 10)
        self.assertEqual(notificacion.estado, 'FALLIDA')

    def test_notificacion_pendiente_se_puede_reintentar(self):
        from django.core import mail
        from django.core.management import call_command

        alerta = self._crear_alerta_alta()
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        NotificacionAlerta.objects.filter(pk=notificacion.pk).update(
            intentos=2,
            proximo_intento=timezone.now() - timedelta(seconds=1),
        )

        call_command('procesar_notificaciones_email', verbosity=0)

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(notificacion.intentos, 3)
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_invalido_es_rechazado(self):
        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', limite=0, verbosity=0)

    def test_alerta_media_no_se_encola(self):
        Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS',
            severidad='MEDIA',
            mensaje='Subfebrícula.',
        )
        self.assertEqual(NotificacionAlerta.objects.count(), 0)

    def test_alerta_alta_sin_destinatario_queda_pendiente_hasta_configurarlo(self):
        """El destinatario vacío ya no llega por un paciente sin médico.

        Se llamaba `..._sin_medico_...` y creaba un paciente ACTIVO con
        `medico_responsable=None`. Desde D12 ese estado no existe: la base lo
        rechaza. Pero el daño que la prueba protege —una alerta ALTA cuyo aviso
        no tiene a dónde ir— sigue siendo alcanzable por la vía que ahora es la
        única: un médico **sin correo configurado**. Es una de las cuatro
        condiciones que vigila la capa 3 de D12.

        Las aserciones no cambian: destinatario vacío, `CommandError`, y la
        notificación PENDIENTE con `ultimo_error='DestinatarioNoConfigurado'`.
        """
        from django.core.management import CommandError, call_command

        medico_sin_correo = get_user_model().objects.create_user(
            username='dr_sin_correo', password='x', is_staff=True,
        )
        paciente_sin_medico = Paciente.objects.create(
            nombre_completo="Sin Médico",
            telefono_whatsapp="+573019990003",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=medico_sin_correo,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente_sin_medico,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=paciente_sin_medico,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Sin medico.',
        )
        notificacion = NotificacionAlerta.objects.get()
        self.assertEqual(notificacion.destinatario, '')

        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'DestinatarioNoConfigurado')

    def test_backend_sin_entrega_confirmada_programa_reintento(self):
        from unittest.mock import patch

        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        with (
            patch('signos_sintomas.notificaciones.send_mail', return_value=0),
            self.assertRaises(CommandError),
        ):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'EntregaEmailNoConfirmada')

    @override_settings(
        EMAIL_DELIVERY_PROVIDER='resend',
        RESEND_API_KEY='re_clave_prueba',
        RESEND_FROM_EMAIL='Seguimiento <onboarding@resend.dev>',
        EMAIL_TIMEOUT=7,
        PANEL_MEDICO_URL='https://ejemplo.test/acceso-seguro/',
    )
    def test_resend_entrega_por_https_con_idempotencia_y_sin_datos_clinicos(self):
        from unittest.mock import Mock, patch

        from django.core.management import call_command

        respuesta = Mock()
        respuesta.json.return_value = {'id': 'email_123'}
        alerta = self._crear_alerta_alta()

        with patch(
            'signos_sintomas.notificaciones.requests.post',
            return_value=respuesta,
        ) as post:
            call_command('procesar_notificaciones_email', verbosity=0)

        llamada = post.call_args
        self.assertEqual(llamada.args[0], 'https://api.resend.com/emails')
        self.assertEqual(llamada.kwargs['timeout'], 7)
        self.assertEqual(
            llamada.kwargs['headers']['Idempotency-Key'],
            f'alerta-alta-{alerta.pk}',
        )
        carga = llamada.kwargs['json']
        self.assertEqual(carga['to'], [self.medico.email])
        self.assertIn(f'alerta #{alerta.pk}', carga['text'])
        self.assertNotIn(self.paciente.nombre_completo, carga['text'])
        self.assertNotIn(self.paciente.telefono_whatsapp, carga['text'])
        self.assertNotIn(self.paciente.cedula, carga['text'])
        self.assertNotIn(alerta.mensaje, carga['text'])

    @override_settings(
        EMAIL_DELIVERY_PROVIDER='resend',
        RESEND_API_KEY='',
        RESEND_FROM_EMAIL='Seguimiento <onboarding@resend.dev>',
    )
    def test_resend_sin_clave_conserva_notificacion_pendiente(self):
        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'ProveedorEmailNoConfigurado')

    def _registro_con_fc(self, fc):
        return RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True,
            episodios_nauseas=0, frecuencia_cardiaca=fc,
        )

    def test_notificacion_solo_al_alcanzar_alta_no_en_recurrencia(self):
        """MEDIA no encola; la escalada a ALTA encola una; la recurrencia, ninguna.

        TEST-12 (02/10/2026) — qué protege cada paso, dicho con honestidad. Los
        dos primeros fijan la guarda de `signals.py`: sin `escalo_a_alta`, la
        escalada de MEDIA a ALTA no avisaría al médico. El tercero NO la fija:
        `NotificacionAlerta.alerta` es uno a uno y la señal usa `get_or_create`,
        así que sin la guarda el conteo seguiría en 1 de todos modos. Lo que la
        guarda hace en la recurrencia lo fija la prueba siguiente.
        """
        evaluar_registro(self._registro_con_fc(120))
        self.assertEqual(NotificacionAlerta.objects.count(), 0)

        evaluar_registro(self._registro_con_fc(150))
        self.assertEqual(NotificacionAlerta.objects.count(), 1)

        evaluar_registro(self._registro_con_fc(155))
        self.assertEqual(NotificacionAlerta.objects.count(), 1)
        self.assertEqual(Alerta.objects.filter(tipo='TAQUICARDIA').count(), 1)

    def test_la_recurrencia_de_una_alta_no_toca_la_bandeja_de_correo(self):
        """TEST-12: lo que la guarda `escalo_a_alta` hace de verdad, y nada más.

        Que una alerta que ya era ALTA y vuelve a detectarse no lea ni escriba la
        bandeja de correo. No es lo que impide un segundo correo —eso lo
        garantiza la relación uno a uno alerta ↔ notificación—, sino que la
        recurrencia no consulte la bandeja ni vuelva a evaluar el destinatario en
        cada reporte del paciente. Esta prueba no pretende distinguir más que eso.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        evaluar_registro(self._registro_con_fc(150))   # ALTA nueva: encola 1
        self.assertEqual(NotificacionAlerta.objects.count(), 1)
        recurrencia = self._registro_con_fc(155)

        with CaptureQueriesContext(connection) as consultas:
            evaluar_registro(recurrencia)

        tabla = NotificacionAlerta._meta.db_table
        tocadas = [q['sql'] for q in consultas.captured_queries if tabla in q['sql']]
        self.assertEqual(
            tocadas, [],
            'La recurrencia de una alerta ALTA consultó la bandeja de correo.',
        )
        # Y la recurrencia sí se registró: no es una prueba que pase en vacío.
        self.assertEqual(Alerta.objects.get(tipo='TAQUICARDIA').veces, 2)

class NotificacionConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        medico = get_user_model().objects.create_user(
            username='medico_notificacion_concurrente',
            password='pass',
            email='medico-concurrente@test.com',
        )
        paciente = Paciente.objects.create(
            nombre_completo='Paciente Notificacion Concurrente',
            telefono_whatsapp='+573006660003',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            medico_responsable=medico,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal('38.5'),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje='sin_drenaje',
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alerta = Alerta.objects.create(
            paciente=paciente,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Prueba de concurrencia',
        )
        self.notificacion = NotificacionAlerta.objects.get(alerta=alerta)

    def test_dos_workers_no_envian_la_misma_notificacion_dos_veces(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from ..notificaciones import procesar_notificaciones_pendientes

        iniciado = Event()
        liberar = Event()

        def enviar_lento(notificacion):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el primer worker.')

        def procesar():
            close_old_connections()
            try:
                return procesar_notificaciones_pendientes(limite=1)
            finally:
                close_old_connections()

        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=enviar_lento,
        ) as enviar, ThreadPoolExecutor(max_workers=2) as executor:
            primero_futuro = executor.submit(procesar)
            self.assertTrue(iniciado.wait(timeout=10))
            segundo = executor.submit(procesar).result(timeout=10)
            liberar.set()
            primero = primero_futuro.result(timeout=10)

        self.notificacion.refresh_from_db()
        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(primero['enviadas'], 1)
        self.assertEqual(segundo['enviadas'], 0)
        self.assertEqual(self.notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(self.notificacion.intentos, 1)

    def test_el_envio_no_bloquea_la_fila_del_paciente(self):
        """Hallazgo 2: el envío de correo es una llamada de red potencialmente
        lenta. No debe mantener bloqueada la fila del paciente —sólo la de la
        notificación (of=('self',))— para no frenar el webhook del paciente,
        que necesita esa fila. Con el bloqueo del join completo, una transacción
        concurrente sobre el paciente esperaría a que terminara el envío.
        """
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from django.db import OperationalError

        from ..notificaciones import procesar_notificaciones_pendientes

        paciente_pk = self.notificacion.alerta.paciente_id

        iniciado = Event()
        liberar = Event()

        def enviar_lento(notificacion):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el worker.')

        def procesar():
            close_old_connections()
            try:
                return procesar_notificaciones_pendientes(limite=1)
            finally:
                close_old_connections()

        paciente_bloqueado = {}
        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=enviar_lento,
        ), ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(procesar)
            self.assertTrue(iniciado.wait(timeout=10))
            # Envío en curso → la notificación está bloqueada. Otra
            # transacción intenta bloquear la fila del paciente sin esperar.
            try:
                with transaction.atomic():
                    Paciente.objects.select_for_update(nowait=True).get(
                        pk=paciente_pk,
                    )
                paciente_bloqueado['valor'] = False
            except OperationalError:
                paciente_bloqueado['valor'] = True
            finally:
                liberar.set()
                futuro.result(timeout=10)

        self.assertFalse(
            paciente_bloqueado['valor'],
            'El envío de correo mantuvo bloqueada la fila del paciente.',
        )
