"""Panel del medico: scoping, tablero de triage y vistas del Admin.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Alerta,
    CheckInProgramado,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RegistroDiario,
)
from .soporte import medico_de_pruebas


class ConsentimientoInformadoAdminTests(TestCase):
    """Bloque 7 — auto-registro/limpieza de fecha_consentimiento vía Admin."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_consentimiento', password='pass')
        self.client.force_login(self.medico)
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Admin Consentimiento",
            cedula="700111222",
            telefono_whatsapp="+573006661113",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )

    def _url_change(self):
        return f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/'

    def _post_change(self, **overrides):
        data = {
            'nombre_completo': self.paciente.nombre_completo,
            'cedula': self.paciente.cedula,
            'telefono_whatsapp': self.paciente.telefono_whatsapp,
            'fecha_cirugia': self.paciente.fecha_cirugia.isoformat(),
            'medico_responsable': self.medico.pk,
        }
        data.update(overrides)
        return self.client.post(self._url_change(), data, follow=True)

    def test_marcar_consentimiento_registra_fecha_automaticamente(self):
        self.assertIsNone(self.paciente.fecha_consentimiento)
        self._post_change(consentimiento_informado='on')
        self.paciente.refresh_from_db()
        self.assertTrue(self.paciente.consentimiento_informado)
        self.assertIsNotNone(self.paciente.fecha_consentimiento)

    def test_desmarcar_consentimiento_limpia_fecha(self):
        self._post_change(consentimiento_informado='on')
        self.paciente.refresh_from_db()
        self.assertIsNotNone(self.paciente.fecha_consentimiento)

        self._post_change()  # sin 'consentimiento_informado' -> checkbox desmarcado
        self.paciente.refresh_from_db()
        self.assertFalse(self.paciente.consentimiento_informado)
        self.assertIsNone(self.paciente.fecha_consentimiento)

    def test_fecha_consentimiento_es_readonly_en_el_form(self):
        resp = self.client.get(self._url_change())
        self.assertNotContains(resp, 'name="fecha_consentimiento"')

class AdminScopingTests(TestCase):
    """Tests de scoping del admin por médico responsable (B6 + D2 + D5)."""

    def setUp(self):
        from decimal import Decimal

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico_a = User.objects.create_user(
            username='dr_a', password='pass', is_staff=True
        )
        self.medico_b = User.objects.create_user(
            username='dr_b', password='pass', is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username='super', password='pass'
        )
        # Los usuarios staff necesitan permisos explícitos de modelo para
        # acceder al admin — sin esto los 403 vendrían de falta de permiso
        # general, no del scoping por médico (falso positivo en tests).
        for model in (
            Paciente,
            RegistroDiario,
            Alerta,
            CheckInProgramado,
            NotificacionAlerta,
        ):
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            self.medico_a.user_permissions.add(*perms)
            self.medico_b.user_permissions.add(*perms)

        self.paciente_a = Paciente.objects.create(
            nombre_completo="Paciente del Doctor A",
            telefono_whatsapp="+573010000001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico_a,
        )
        self.paciente_b = Paciente.objects.create(
            nombre_completo="Paciente del Doctor B",
            telefono_whatsapp="+573010000002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico_b,
        )
        _campos_base = {
            'temperatura': Decimal('37.0'),
            'dolor_eva': 3,
            'aspecto_drenaje': 'sin_drenaje',
            'presencia_gases': True,
            'episodios_nauseas': 0,
        }
        self.registro_a = RegistroDiario.objects.create(
            paciente=self.paciente_a, **_campos_base
        )
        self.registro_b = RegistroDiario.objects.create(
            paciente=self.paciente_b, **_campos_base
        )
        self.alerta_a = Alerta.objects.create(
            paciente=self.paciente_a,
            registro_origen=self.registro_a,
            tipo='SEPSIS', severidad='BAJA', mensaje='Alerta A',
        )
        self.alerta_b = Alerta.objects.create(
            paciente=self.paciente_b,
            registro_origen=self.registro_b,
            tipo='SEPSIS', severidad='BAJA', mensaje='Alerta B',
        )
        self.notificacion_a = NotificacionAlerta.objects.create(
            alerta=self.alerta_a,
            destinatario='operaciones@test.com',
        )
        self.deteccion_a = DeteccionAlerta.objects.create(
            alerta=self.alerta_a,
            registro=self.registro_a,
            severidad_detectada='BAJA',
            mensaje_detectado='Detalle clínico A',
        )
        self.deteccion_b = DeteccionAlerta.objects.create(
            alerta=self.alerta_b,
            registro=self.registro_b,
            severidad_detectada='BAJA',
            mensaje_detectado='Detalle clínico B',
        )
        self.checkin_a = CheckInProgramado.objects.create(
            paciente=self.paciente_a,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        self.checkin_b = CheckInProgramado.objects.create(
            paciente=self.paciente_b,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    def _login(self, user):
        self.client.force_login(user)

    # ------------------------------------------------------------------ #
    # PacienteAdmin                                                        #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_pacientes_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todos_en_changelist_paciente(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_paciente_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_medico_puede_editar_su_propio_paciente(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_superuser_puede_editar_cualquier_paciente(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    # ------------------------------------------------------------------ #
    # RegistroDiarioAdmin                                                  #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_registros_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/registrodiario/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todos_en_changelist_registro(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/registrodiario/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_registro_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_superuser_puede_editar_cualquier_registro(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_medico_ve_registro_propio_pero_no_puede_modificarlo(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {'temperatura': '39.9'})
        self.assertEqual(resp.status_code, 403)
        self.registro_a.refresh_from_db()
        self.assertEqual(self.registro_a.temperatura, Decimal('37.0'))

    def test_medico_no_puede_borrar_paciente_propio(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_a.pk}/delete/'
        self.assertEqual(self.client.get(url).status_code, 403)

    # ------------------------------------------------------------------ #
    # AlertaAdmin                                                          #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_alertas_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todas_las_alertas_en_changelist(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_alerta_ajena(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_medico_no_puede_borrar_alerta_propia(self):
        # Alertas son registros clínicos; has_delete_permission retorna False
        # para cualquier no-superuser → 403 en la vista de borrado.
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/delete/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_superuser_puede_acceder_a_alerta_ajena(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_formulario_alerta_no_permite_resolver_directamente(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/change/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'name="resuelta"')

        self.client.post(url, {'resuelta': 'on'})
        self.alerta_a.refresh_from_db()
        self.assertFalse(self.alerta_a.resuelta)

    def test_detalle_detecciones_es_solo_lectura_y_respeta_scoping(self):
        self._login(self.medico_a)

        resp = self.client.get(
            f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/change/'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Detecciones de la alerta')
        self.assertContains(resp, 'Detalle clínico A')
        self.assertNotContains(resp, 'Detalle clínico B')
        self.assertNotContains(resp, 'name="detecciones-0-mensaje_detectado"')

    def test_medico_ve_checkin_propio_pero_no_puede_modificarlo(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/checkinprogramado/{self.checkin_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {'estado': CheckInProgramado.ESTADO_NO_RESPONDIDO})
        self.assertEqual(resp.status_code, 403)
        self.checkin_a.refresh_from_db()
        self.assertEqual(self.checkin_a.estado, CheckInProgramado.ESTADO_PENDIENTE)

    def test_medico_no_puede_ver_checkin_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/checkinprogramado/{self.checkin_b.pk}/change/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_filtro_fecha_checkin_usa_etiqueta_precisa(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/checkinprogramado/')
        self.assertContains(resp, 'Todas las fechas')
        self.assertNotContains(resp, 'Cualquier fecha')

    def test_medico_no_puede_ver_bandeja_tecnica_de_notificaciones(self):
        self._login(self.medico_a)
        lista = self.client.get('/admin/signos_sintomas/notificacionalerta/')
        detalle = self.client.get(
            f'/admin/signos_sintomas/notificacionalerta/{self.notificacion_a.pk}/change/'
        )
        self.assertEqual(lista.status_code, 403)
        self.assertEqual(detalle.status_code, 403)

    def test_superuser_puede_auditar_bandeja_de_notificaciones(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/notificacionalerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.notificacion_a.alerta_id)

class AlertaAdminAccionesTests(TestCase):
    """Bloque 5A — Colores severidad + acción marcar_resuelta en AlertaAdmin."""

    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='super5a', password='pass',
        )
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente 5A",
            telefono_whatsapp="+573019990001",
            fecha_cirugia=timezone.localdate(),
        )
        campos = {
            'temperatura': Decimal('37.0'), 'dolor_eva': 2,
            'aspecto_drenaje': 'sin_drenaje', 'presencia_gases': True, 'episodios_nauseas': 0,
        }
        self.registro = RegistroDiario.objects.create(paciente=self.paciente, **campos)
        self.alerta = Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre test',
        )

    def test_changelist_contiene_badge_severidad(self):
        """La lista de alertas renderiza el badge de severidad con HTML coloreado."""
        self.client.force_login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        # El badge usa border-radius como parte del estilo — confirma que se renderizó HTML
        self.assertContains(resp, 'border-radius')

    def test_accion_marcar_resuelta(self):
        """Bloque A: marcar_resuelta con el paso 'aplicar' + motivo actualiza
        la alerta, registra fecha_resolucion y guarda el motivo."""
        self.client.force_login(self.superuser)
        self.client.post(
            '/admin/signos_sintomas/alerta/',
            {
                'action': 'marcar_resuelta',
                'aplicar': '1',
                '_selected_action': [str(self.alerta.pk)],
                'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
                'motivo_resolucion_detalle': '',
            },
        )
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertIsNotNone(self.alerta.fecha_resolucion)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_CONTACTO)

class AlertaMotivoResolucionTests(TestCase):
    """Bloque A — motivo de resolución obligatorio con formulario intermedio."""

    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(username='super_motivo', password='pass')
        self.medico = User.objects.create_user(
            username='dr_motivo', password='pass', is_staff=True,
        )
        self.otro_medico = User.objects.create_user(
            username='dr_otro', password='pass', is_staff=True,
        )
        self._dar_permisos(self.medico)
        self._dar_permisos(self.otro_medico)
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Motivo",
            telefono_whatsapp="+573018880001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        self.alerta = Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre test',
        )

    def _dar_permisos(self, user):
        from django.contrib.auth.models import Permission
        perms = Permission.objects.filter(
            content_type__app_label='signos_sintomas',
            content_type__model='alerta',
        )
        user.user_permissions.add(*perms)

    def _post_accion(self, extra):
        data = {
            'action': 'marcar_resuelta',
            '_selected_action': [str(self.alerta.pk)],
        }
        data.update(extra)
        return self.client.post('/admin/signos_sintomas/alerta/', data)

    def test_motivo_resolucion_null_por_default(self):
        """Una alerta recién creada no tiene motivo de resolución."""
        self.assertIsNone(self.alerta.motivo_resolucion)

    def test_base_de_datos_rechaza_cierre_sin_motivo_y_fecha(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Alerta.objects.filter(pk=self.alerta.pk).update(resuelta=True)

    def test_modelo_rechaza_cierre_sin_motivo_y_fecha(self):
        self.alerta.resuelta = True
        with self.assertRaises(ValidationError):
            self.alerta.full_clean()

    def test_accion_sin_aplicar_muestra_formulario_intermedio(self):
        self.client.force_login(self.superuser)
        resp = self._post_accion({})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'motivo de resolución')
        self.assertEqual(
            resp.content.decode().count('<h1>Selecciona el motivo de resolución</h1>'),
            1,
        )
        self.assertContains(resp, 'admin/js/motivo_resolucion.js')
        self.assertNotContains(resp, 'DOMContentLoaded')
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_aplicar_con_motivo_valido_resuelve_y_guarda_motivo(self):
        self.client.force_login(self.superuser)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_URGENCIAS,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_URGENCIAS)

    def test_motivo_otro_sin_detalle_no_resuelve(self):
        self.client.force_login(self.superuser)
        resp = self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_OTRO,
            'motivo_resolucion_detalle': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'detalle cuando el motivo es')
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_motivo_otro_con_detalle_resuelve_y_guarda_detalle(self):
        self.client.force_login(self.superuser)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_OTRO,
            'motivo_resolucion_detalle': 'Resuelto en control presencial.',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_OTRO)
        self.assertEqual(
            self.alerta.motivo_resolucion_detalle, 'Resuelto en control presencial.'
        )

    def test_medico_no_resuelve_alertas_de_pacientes_ajenos(self):
        """El otro médico no es responsable de este paciente → no la resuelve."""
        self.client.force_login(self.otro_medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_resolver_registra_quien_resolvio(self):
        """D3: al resolver, la alerta guarda QUIÉN la resolvió. Sin este dato,
        una decisión clínica (p.ej. marcar una fuga como falso positivo) queda
        sin atribución el día que entre un segundo médico o se transfiera el
        sistema — datos que no se capturan no son recuperables.
        """
        self.client.force_login(self.medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.resuelta_por, self.medico)

    def test_resolver_escribe_en_el_historial_del_admin(self):
        """D3: la resolución deja una entrada en el historial de Django (el
        botón "Historial" de la alerta), imposible con queryset.update() a
        secas. Se registra con el usuario que resolvió.
        """
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        self.client.force_login(self.medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        ct = ContentType.objects.get_for_model(Alerta)
        entradas = LogEntry.objects.filter(
            content_type=ct,
            object_id=str(self.alerta.pk),
            user=self.medico,
        )
        self.assertTrue(entradas.exists())

class PacienteAdminIngresoTardioAdvertenciaTests(TestCase):
    """A-1 — advertencia en el Admin al crear un paciente con POD ya avanzado."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_a1', password='pass')
        self.client.force_login(self.medico)

    def _post_nuevo_paciente(self, dias_cirugia, tel, cedula):
        return self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Ingreso Tardío',
                'cedula': cedula,
                'telefono_whatsapp': tel,
                'fecha_cirugia': (timezone.localdate() - timedelta(days=dias_cirugia)).isoformat(),
            },
            follow=True,
        )

    def test_advierte_si_pod_es_mayor_o_igual_a_8(self):
        resp = self._post_nuevo_paciente(dias_cirugia=9, tel="+573002230001", cedula="900000001")
        self.assertContains(resp, "días postoperatorios")

    def test_no_advierte_si_pod_es_menor_a_8(self):
        resp = self._post_nuevo_paciente(dias_cirugia=3, tel="+573002230002", cedula="900000002")
        self.assertNotContains(resp, "días postoperatorios")

class PacienteAdminFiltrosHistorialTests(TestCase):
    """Sprint 5, Bloque 3 — filtro de alertas activas e historial configurable (P-8)."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_bloque3', password='pass')
        self.paciente_con_alerta = Paciente.objects.create(
            nombre_completo="Paciente Con Alerta Activa",
            telefono_whatsapp="+573020000001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.paciente_sin_alerta = Paciente.objects.create(
            nombre_completo="Paciente Sin Alerta Activa",
            telefono_whatsapp="+573020000002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        registro = RegistroDiario.objects.create(
            paciente=self.paciente_con_alerta,
            temperatura=Decimal('38.0'),
            dolor_eva=3,
            aspecto_drenaje='sin_drenaje',
            presencia_gases=True,
            episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente_con_alerta,
            registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre',
            resuelta=False,
        )
        self.client.force_login(self.medico)

    # -------------------------------------------------------------------
    # TieneAlertaActivaFilter
    # -------------------------------------------------------------------

    def test_filtro_alerta_activa_si_muestra_solo_pacientes_con_alerta_sin_resolver(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/?alerta_activa=si')
        self.assertContains(resp, "Paciente Con Alerta Activa")
        self.assertNotContains(resp, "Paciente Sin Alerta Activa")

    def test_filtro_alerta_activa_no_excluye_pacientes_con_alerta_pendiente(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/?alerta_activa=no')
        self.assertContains(resp, "Paciente Sin Alerta Activa")
        self.assertNotContains(resp, "Paciente Con Alerta Activa")

    def test_sin_filtro_muestra_ambos_pacientes(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertContains(resp, "Paciente Con Alerta Activa")
        self.assertContains(resp, "Paciente Sin Alerta Activa")

    # -------------------------------------------------------------------
    # Historial configurable por días
    # -------------------------------------------------------------------

    def _url_change(self, paciente):
        return f'/admin/signos_sintomas/paciente/{paciente.pk}/change/'

    def test_historial_default_es_7_dias(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta))
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_respeta_parametro_dias_de_la_url(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=10')
        self.assertContains(resp, '<strong>10 días</strong>', html=False)

    def test_historial_valor_invalido_usa_default(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=abc')
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_rechaza_periodo_fuera_de_las_opciones(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=30')
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_de_3_dias_no_incluye_un_cuarto_dia(self):
        for desplazamiento in (1, 2, 3):
            registro = RegistroDiario.objects.create(
                paciente=self.paciente_con_alerta,
                temperatura=Decimal('37.0'),
                dolor_eva=2,
                aspecto_drenaje='sin_drenaje',
                presencia_gases=True,
                episodios_nauseas=0,
            )
            fecha = timezone.datetime.combine(
                timezone.localdate() - timedelta(days=desplazamiento),
                timezone.datetime.min.time(),
                tzinfo=timezone.get_current_timezone(),
            ) + timedelta(hours=8)
            RegistroDiario.objects.filter(pk=registro.pk).update(fecha_registro=fecha)

        from ..admin import _historial_paciente

        contenido = _historial_paciente(self.paciente_con_alerta, dias=3)
        fecha_incluida = (timezone.localdate() - timedelta(days=2)).strftime('%d/%m')
        fecha_excluida = (timezone.localdate() - timedelta(days=3)).strftime('%d/%m')
        self.assertIn(fecha_incluida, contenido)
        self.assertNotIn(fecha_excluida, contenido)

class PanelTriageExperienciaTests(TestCase):
    """Loop 3: pendientes acumulados, prioridad y scoping en el tablero."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command('crear_medico', verbosity=0)
        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dr_panel', password='pass', is_staff=True,
        )
        self.otro_medico = User.objects.create_user(
            username='dr_panel_otro', password='pass', is_staff=True,
        )
        grupo = Group.objects.get(name='Médicos')
        self.medico.groups.add(grupo)
        self.otro_medico.groups.add(grupo)
        self.client.force_login(self.medico)

    def _paciente(self, nombre, telefono, cedula, medico=None):
        return Paciente.objects.create(
            nombre_completo=nombre,
            cedula=cedula,
            telefono_whatsapp=telefono,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable=medico or self.medico,
        )

    def _alerta(self, paciente, veces, fecha, severidad='ALTA'):
        return Alerta.objects.create(
            paciente=paciente,
            tipo='SEPSIS',
            severidad=severidad,
            mensaje='Alerta de prueba',
            veces=veces,
            fecha_ultima_deteccion=fecha,
        )

    def test_muestra_alerta_antigua_mientras_siga_sin_resolver(self):
        propio = self._paciente(
            'Paciente pendiente anterior', '+573040000001', 'PANEL-001',
        )
        ajeno = self._paciente(
            'Paciente ajeno invisible', '+573040000002', 'PANEL-002',
            medico=self.otro_medico,
        )
        self._alerta(propio, 1, timezone.now() - timedelta(days=3))
        self._alerta(ajeno, 1, timezone.now())

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Seguimiento que requiere atención')
        self.assertContains(resp, 'Paciente pendiente anterior')
        self.assertNotContains(resp, 'Paciente ajeno invisible')
        self.assertContains(resp, '1 pendiente')

    def test_prioriza_recurrencia_dentro_de_la_misma_severidad(self):
        menos = self._paciente(
            'Paciente recurrencia menor', '+573040000003', 'PANEL-003',
        )
        mas = self._paciente(
            'Paciente recurrencia mayor', '+573040000004', 'PANEL-004',
        )
        self._alerta(menos, 2, timezone.now())
        self._alerta(mas, 5, timezone.now() - timedelta(days=1))

        contenido = self.client.get('/admin/').content.decode()

        self.assertLess(
            contenido.index('Paciente recurrencia mayor'),
            contenido.index('Paciente recurrencia menor'),
        )

    def test_panel_muestra_solo_mensajes_de_contacto_asignados_al_medico(self):
        from home.models import MensajeContacto

        MensajeContacto.objects.create(
            nombre='Contacto propio visible',
            telefono='+573040000010',
            mensaje='Contenido sensible que no va en el tablero',
            medico_destinatario=self.medico,
        )
        MensajeContacto.objects.create(
            nombre='Contacto ajeno invisible',
            telefono='+573040000011',
            mensaje='Otro contenido',
            medico_destinatario=self.otro_medico,
        )
        MensajeContacto.objects.create(
            nombre='Contacto sin asignar invisible',
            telefono='+573040000012',
            mensaje='Pendiente del superusuario',
        )

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Mensajes de contacto')
        self.assertContains(resp, 'Contacto propio visible')
        self.assertNotContains(resp, 'Contacto ajeno invisible')
        self.assertNotContains(resp, 'Contacto sin asignar invisible')
        self.assertNotContains(resp, 'Contenido sensible que no va en el tablero')

    def test_avisa_de_correos_de_alerta_sin_entregar_propios(self):
        """D6: un correo de alerta ALTA que agotó los reintentos (FALLIDA) es
        información clínica que no llegó. El tablero debe avisarlo —también al
        médico— en vez de que el fallo quede enterrado en la bandeja.
        """
        propio = self._paciente(
            'Paciente correo fallido', '+573040000030', 'PANEL-030',
        )
        alerta = self._alerta(propio, 1, timezone.now())
        NotificacionAlerta.objects.update_or_create(
            alerta=alerta,
            defaults={
                'estado': NotificacionAlerta.ESTADO_FALLIDA,
                'intentos': 10,
            },
        )

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Correos de alerta sin entregar')

    def test_no_avisa_de_correos_fallidos_de_pacientes_ajenos(self):
        """El aviso de FALLIDA respeta el scoping por médico: un correo fallido
        de un paciente de otro médico no aparece en este tablero.
        """
        ajeno = self._paciente(
            'Paciente ajeno correo', '+573040000031', 'PANEL-031',
            medico=self.otro_medico,
        )
        alerta = self._alerta(ajeno, 1, timezone.now())
        NotificacionAlerta.objects.update_or_create(
            alerta=alerta,
            defaults={
                'estado': NotificacionAlerta.ESTADO_FALLIDA,
                'intentos': 10,
            },
        )

        resp = self.client.get('/admin/')

        self.assertNotContains(resp, 'Correos de alerta sin entregar')

class PacienteAdminHistorialCambiosTests(TestCase):
    """Loop 3: el historial distingue activación y desactivación."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(
            username='dr_historial_estado', password='pass',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo='Paciente Historial Estado',
            cedula='HIST-ESTADO-001',
            telefono_whatsapp='+573040000005',
            fecha_cirugia=timezone.localdate(),
            tipo_cirugia='otra',
            medico_responsable=self.medico,
            activo=True,
        )
        self.client.force_login(self.medico)

    def _guardar(self, activo):
        datos = {
            'nombre_completo': self.paciente.nombre_completo,
            'cedula': self.paciente.cedula,
            'telefono_whatsapp': self.paciente.telefono_whatsapp,
            'fecha_cirugia': self.paciente.fecha_cirugia.isoformat(),
            'tipo_cirugia': self.paciente.tipo_cirugia,
            'medico_responsable': str(self.medico.pk),
            '_save': 'Grabar',
        }
        if activo:
            datos['activo'] = 'on'
        return self.client.post(
            f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/',
            datos,
        )

    def _ultimo_mensaje(self):
        from django.contrib.admin.models import LogEntry
        return LogEntry.objects.filter(
            object_id=str(self.paciente.pk),
        ).latest('action_time').get_change_message()

    def test_historial_indica_seguimiento_desactivado(self):
        self.assertEqual(self._guardar(activo=False).status_code, 302)
        self.assertEqual(self._ultimo_mensaje(), 'Seguimiento desactivado.')

    def test_historial_indica_seguimiento_activado(self):
        Paciente.objects.filter(pk=self.paciente.pk).update(activo=False)
        self.paciente.refresh_from_db()
        self.assertEqual(self._guardar(activo=True).status_code, 302)
        self.assertEqual(self._ultimo_mensaje(), 'Seguimiento activado.')

class GraficaSignosVitalesTests(TestCase):
    """
    Sprint 5, Bloque 4 (rediseño 01/07/2026) — gráficas Chart.js con
    selector de período 3/7/10 días independiente del historial en
    tabla, turno M/T por CheckInProgramado real, y puntos de alerta.
    """

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_bloque4', password='pass')
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Grafica",
            telefono_whatsapp="+573030000001",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            medico_responsable=self.medico,
        )
        self.client.force_login(self.medico)

    def _url_change(self):
        return f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/'

    def _extraer_datos(self, contenido):
        import html
        import json
        import re
        match = re.search(r'data-graficas="([^"]+)"', contenido)
        self.assertIsNotNone(match, "No se encontró el JSON de las gráficas")
        return json.loads(html.unescape(match.group(1)))

    def test_sin_registros_no_carga_chartjs_desde_cdn(self):
        resp = self.client.get(self._url_change())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sin datos para graficar")
        self.assertNotContains(resp, "cdn.jsdelivr.net/npm/chart.js")

    def test_fc_nula_se_serializa_como_null_no_como_cero(self):
        """Bug reportado en la revisión visual: FC no capturada debía viajar
        como null (hueco en la línea), nunca como 0 (caída falsa a tierra)."""
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.2'), dolor_eva=6,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=1,
            frecuencia_cardiaca=None,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['fcs'], [None])
        self.assertNotIn(0, datos['7']['fcs'])

    def test_los_3_periodos_estan_precalculados_en_una_sola_carga(self):
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(set(datos.keys()), {'3', '7', '10'})
        for periodo in ('3', '7', '10'):
            self.assertEqual(datos[periodo]['temps'], [37.0])

    def test_turno_usa_etiqueta_del_checkin_no_la_hora_de_respuesta(self):
        """Decisión D2 (Sprint 3.6): el turno lo fija el evento programado,
        nunca la hora en que el paciente respondió."""
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        # Paciente respondió a las 3pm (T) al check-in que el sistema programó
        # como MAÑANA — el turno mostrado debe ser M, no T.
        RegistroDiario.objects.filter(pk=registro.pk).update(
            fecha_registro=timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)
        )
        CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
            estado=CheckInProgramado.ESTADO_COMPLETADO,
            registro=registro,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertTrue(datos['7']['labels'][0].endswith(' M'))

    def test_registro_legado_sin_checkin_usa_hora_local_como_respaldo(self):
        """Sin CheckInProgramado vinculado (dato legado), se usa la hora en
        zona horaria de Bogotá, no UTC — de lo contrario el respaldo
        clasifica mal registros creados en la mañana bogotana."""
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        # 8am Bogotá (UTC-5) = 13:00 UTC — con .hour crudo (UTC) esto daría
        # "T" incorrectamente; con timezone.localtime() da "M" correcto.
        ocho_am_bogota_en_utc = timezone.now().replace(hour=13, minute=0, second=0, microsecond=0)
        RegistroDiario.objects.filter(pk=registro.pk).update(fecha_registro=ocho_am_bogota_en_utc)
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertTrue(datos['7']['labels'][0].endswith(' M'))

    def test_alerta_alta_sin_resolver_marca_el_indice(self):
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.5'), dolor_eva=8,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente, registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre alta', resuelta=False,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['alertas_idx'], [0])

    def test_alerta_alta_resuelta_no_marca_el_indice(self):
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.5'), dolor_eva=8,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente, registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre alta', resuelta=True,
            fecha_resolucion=timezone.now(),
            motivo_resolucion=Alerta.MOTIVO_CONTACTO,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['alertas_idx'], [])

    def test_carga_chartjs_y_logica_desde_estaticos_locales(self):
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change())
        self.assertContains(resp, 'admin/js/vendor/chart.umd.min.js')
        self.assertContains(resp, 'admin/js/graficas_signos_vitales.js')
        self.assertNotContains(resp, 'cdn.jsdelivr.net')
        self.assertNotContains(resp, 'onclick=')

    def test_distribucion_y_licencia_chartjs_existen_en_staticfiles(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find('admin/js/vendor/chart.umd.min.js'))
        self.assertIsNotNone(finders.find('admin/js/vendor/Chart.js-LICENSE.md'))

    def test_selector_de_grafica_es_independiente_del_historial(self):
        """El ?dias= de la URL controla el historial en tabla (Bloque 3B);
        la gráfica siempre trae los 3 períodos precalculados, sin depender
        de ese parámetro."""
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change() + '?dias=10')
        self.assertContains(resp, '<strong>10 días</strong>', html=False)
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(set(datos.keys()), {'3', '7', '10'})

class AdminFiltrosNoExponenOtrasCuentasTests(TestCase):
    """Hallazgo 8 — el filtro lateral no debe revelar las demás cuentas médicas.

    El aislamiento por médico resistió las 15 comprobaciones de la auditoría:
    ningún dato de paciente se filtra. La fuga es de otra naturaleza y menor —
    `PacienteAdmin.list_filter` incluye `medico_responsable`, y ese filtro se
    construye con TODOS los usuarios de la base, no con los que el médico puede
    ver. Un médico lee ahí los nombres de usuario de sus colegas y del
    superusuario.
    """

    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico_a = User.objects.create_user(
            username='dr_filtro_a', password='pass', is_staff=True
        )
        self.medico_b = User.objects.create_user(
            username='dr_filtro_b', password='pass', is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username='super_filtro', password='pass'
        )
        ct = ContentType.objects.get_for_model(Paciente)
        for medico in (self.medico_a, self.medico_b):
            medico.user_permissions.add(*Permission.objects.filter(content_type=ct))

        for indice, medico in enumerate((self.medico_a, self.medico_b), start=1):
            Paciente.objects.create(
                nombre_completo=f"Paciente del filtro {indice}",
                telefono_whatsapp=f"+57301999000{indice}",
                cedula=f"FILTRO-000{indice}",
                fecha_cirugia=timezone.localdate(),
                medico_responsable=medico,
            )

    def _url_listado(self):
        return reverse('admin:signos_sintomas_paciente_changelist')

    def test_medico_no_ve_en_el_filtro_las_cuentas_de_los_demas(self):
        self.client.force_login(self.medico_a)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        # El marcador ancla el fallo al filtro lateral y no a otra parte de la
        # página: es el querystring que arma RelatedFieldListFilter.
        self.assertNotIn('medico_responsable__id__exact', contenido)
        self.assertNotIn('dr_filtro_b', contenido)
        self.assertNotIn('super_filtro', contenido)

    def test_superusuario_conserva_el_filtro_por_medico(self):
        """El filtro es útil para el superusuario: la corrección no debe borrarlo."""
        self.client.force_login(self.superuser)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        self.assertIn('medico_responsable__id__exact', contenido)
        self.assertIn('dr_filtro_a', contenido)
        self.assertIn('dr_filtro_b', contenido)

    def test_medico_sigue_viendo_solo_sus_pacientes(self):
        """Nace en verde: es el aislamiento que ya funciona y no debe romperse."""
        self.client.force_login(self.medico_a)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        self.assertIn('Paciente del filtro 1', contenido)
        self.assertNotIn('Paciente del filtro 2', contenido)


# ===========================================================================
# Loop D — D-1: pruebas en rojo de la auditoría de cierre (27/07/2026)
# Fichas D11, D12 y D13 en docs/decisiones_correccion_auditoria.md
# ===========================================================================


class TableroQueNoSeContradiceTests(TestCase):
    """UX-P01 — el tablero decía "Todo bajo control" con una ALTA sin resolver.

    Reproducido el 08/09/2026: con una única alerta ALTA de tipo SILENCIO, el
    KPI de arriba mostraba **1** y la lista de justo debajo imprimía *"Sin
    alertas pendientes. Todo bajo control."*. Ocurría **siempre** que la única
    ALTA era un SILENCIO — es decir, con el paciente que lleva dos días sin dar
    señales: exactamente cuando menos se puede decir que todo está bajo
    control.

    La causa: la lista de triage excluye `tipo='SILENCIO'` (es ausencia de
    datos, no un síntoma — ficha D1) y el KPI no. La exclusión se mantiene
    porque el criterio clínico sigue siendo correcto; lo que se corrige es que
    el estado vacío deje de tranquilizar cuando no debe.
    """

    def setUp(self):
        self.medico = medico_de_pruebas('medico_tablero')
        self.paciente = Paciente.objects.create(
            medico_responsable=self.medico,
            nombre_completo='Paciente Tablero',
            telefono_whatsapp='+573009990004',
            fecha_cirugia=timezone.localdate() - timedelta(days=6),
            # Explícito: `consentimiento_informado` es `default=False`, y desde
            # la ficha D22 eso significa "seguimiento detenido". El fixture de
            # esta clase representa a un paciente en seguimiento normal.
            consentimiento_informado=True,
        )

    def _contexto(self):
        from ..templatetags.panel_admin import panel_triage
        peticion = RequestFactory().get('/admin/')
        peticion.user = self.medico
        return panel_triage({'request': peticion})

    def _alerta(self, tipo, severidad='ALTA'):
        return Alerta.objects.create(
            paciente=self.paciente, tipo=tipo, severidad=severidad,
            mensaje='Detalle de prueba.', veces=1,
            fecha_ultima_deteccion=timezone.now(),
        )

    def test_una_alta_de_silencio_se_cuenta_aunque_no_este_en_la_lista(self):
        self._alerta('SILENCIO')
        ctx = self._contexto()
        self.assertEqual(ctx['kpi']['alta'], 1)
        self.assertEqual(len(ctx['atencion']), 0)
        # Lo que faltaba: el tablero ahora SABE que quedan alertas fuera.
        self.assertEqual(ctx['silencios_pendientes'], 1)

    def test_sin_ninguna_alerta_el_tablero_puede_tranquilizar(self):
        """La otra dirección: cuando de verdad no hay nada, se dice."""
        ctx = self._contexto()
        self.assertEqual(ctx['kpi']['alta'], 0)
        self.assertEqual(ctx['silencios_pendientes'], 0)

    def test_una_alerta_clinica_si_aparece_en_la_lista(self):
        """La otra dirección: excluir SILENCIO no puede esconder lo clínico."""
        self._alerta('SEPSIS')
        ctx = self._contexto()
        self.assertEqual(len(ctx['atencion']), 1)
        self.assertEqual(ctx['silencios_pendientes'], 0)

    def test_una_silencio_resuelta_ya_no_cuenta(self):
        alerta = self._alerta('SILENCIO')
        # Resolver exige cierre completo: la restricción `alerta_resuelta_con_cierre`
        # no deja marcar `resuelta` sin fecha ni motivo (ficha D3).
        alerta.resuelta = True
        alerta.fecha_resolucion = timezone.now()
        alerta.motivo_resolucion = Alerta.MOTIVO_CONTACTO
        alerta.save(update_fields=['resuelta', 'fecha_resolucion', 'motivo_resolucion'])
        self.assertEqual(self._contexto()['silencios_pendientes'], 0)

    def test_el_paciente_con_seguimiento_detenido_no_desaparece(self):
        """D22 — cumplir habeas data no puede producir un punto ciego.

        Un paciente que se esfuma del panel sin dejar rastro es el mismo fallo
        que la ficha D12 combatió: nadie lo mira, y nadie sabe que nadie lo
        mira.
        """
        self.paciente.consentimiento_informado = False
        self.paciente.save(update_fields=['consentimiento_informado'])
        ctx = self._contexto()
        self.assertEqual(ctx['total_detenidos'], 1)
        self.assertEqual(ctx['seguimiento_detenido'][0]['nombre'], 'Paciente Tablero')

    def test_el_paciente_que_si_consintio_no_aparece_como_detenido(self):
        """La otra dirección."""
        ctx = self._contexto()
        self.assertEqual(ctx['total_detenidos'], 0)
