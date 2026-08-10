"""Modelos clinicos: campos, constraints y validaciones.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    CheckInProgramado,
    Paciente,
    RegistroDiario,
)
from .soporte import medico_de_pruebas


class RegistroDiarioModelTests(TestCase):
    """Cálculo de dia_postoperatorio en RegistroDiario.save().
    El campo es PositiveSmallIntegerField (CHECK >= 0): el save nunca debe
    producir un valor negativo, ni siquiera con fecha_cirugia futura."""

    def _crear_registro(self, paciente):
        # Valores neutros: ninguna regla del alert_engine se dispara,
        # así el único factor bajo prueba es dia_postoperatorio.
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )

    def test_fecha_cirugia_futura_no_crashea_y_da_dia_cero(self):
        # Regresión del bug de producción: paciente pre-registrado con
        # cirugía programada a futuro. (hoy - mañana).days = -1 violaría el
        # CHECK del PositiveSmallIntegerField y haría crashear el save().
        # El clamp a 0 lo evita y conserva el registro para el médico.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Cirugia Futura",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() + timedelta(days=1),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_hoy_da_dia_cero(self):
        # Borde exacto: cirugía hoy → POD 0 (el día de la cirugía).
        # Aquí el .days ya es 0 natural, sin intervención del clamp.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Cirugia Hoy",
            telefono_whatsapp="+573009990002",
            fecha_cirugia=timezone.localdate(),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_pasada_calcula_dia_correcto(self):
        # Camino normal: el clamp NO debe alterar el cálculo positivo.
        # Operado hace 5 días → POD 5. Guarda contra un max(0, ...) mal
        # escrito que aplastara también los valores válidos.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente POD5",
            telefono_whatsapp="+573009990003",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 5)

    def test_registro_historico_usa_su_fecha_y_congela_el_pod(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Histórico",
            telefono_whatsapp="+573009990004",
            fecha_cirugia=timezone.localdate() - timedelta(days=10),
        )
        fecha_historica = timezone.now() - timedelta(days=4)
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            fecha_registro=fecha_historica,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        self.assertEqual(registro.dia_postoperatorio, 6)

        paciente.fecha_cirugia = timezone.localdate() - timedelta(days=20)
        paciente.save()
        registro.temperatura = Decimal("37.1")
        registro.save()
        registro.refresh_from_db()

        self.assertEqual(registro.dia_postoperatorio, 6)

class PacienteMedicoFKTests(TestCase):
    """Tests de la relación ForeignKey Paciente → auth.User (medico_responsable)."""

    def _crear_paciente(self, **kwargs):
        kwargs.setdefault('medico_responsable', medico_de_pruebas())
        return Paciente.objects.create(
            nombre_completo="Paciente FK Test",
            telefono_whatsapp="+573000000001",
            fecha_cirugia=timezone.localdate(),
            **kwargs,
        )

    def test_paciente_con_medico_fk(self):
        User = get_user_model()
        medico = User.objects.create_user(
            username='dr_test', password='x', first_name='Carlos', last_name='López'
        )
        paciente = self._crear_paciente(medico_responsable=medico)
        paciente.refresh_from_db()
        self.assertEqual(paciente.medico_responsable, medico)
        self.assertIn(paciente, medico.pacientes.all())

    def test_str_con_medico_nombre_completo(self):
        User = get_user_model()
        medico = User.objects.create_user(
            username='dr_str', password='x', first_name='Ana', last_name='Ruiz'
        )
        paciente = self._crear_paciente(medico_responsable=medico)
        self.assertEqual(str(paciente), "Paciente FK Test — Dr. Ana Ruiz")

    def test_str_con_medico_sin_nombre_usa_username(self):
        User = get_user_model()
        medico = User.objects.create_user(username='dr_noname', password='x')
        paciente = self._crear_paciente(medico_responsable=medico)
        self.assertEqual(str(paciente), "Paciente FK Test — Dr. dr_noname")

    def test_str_sin_medico(self):
        """Solo una ficha INACTIVA puede no tener responsable (D12).

        Antes el paciente se creaba activo. Desde la migración 0028 la base lo
        rechaza: `activo` es la palabra que hace el invariante cumplible, y las
        filas históricas conservan lo que tengan, incluido NULL.
        """
        paciente = self._crear_paciente(medico_responsable=None, activo=False)

        self.assertEqual(str(paciente), "Paciente FK Test — Sin médico asignado")

    def test_no_se_puede_borrar_un_medico_con_pacientes(self):
        """D12 (capa 2) — esta prueba afirmaba lo contrario.

        Se llamaba `test_set_null_al_borrar_usuario` y verificaba que borrar la
        cuenta del médico dejara al paciente con `medico_responsable=None`. Eso
        era exactamente el hallazgo: el paciente quedaba huérfano e invisible,
        en silencio. La prueba documentaba el defecto como si fuera el contrato.
        """
        from django.db.models import ProtectedError

        User = get_user_model()
        medico = User.objects.create_user(username='dr_delete', password='x')
        paciente = self._crear_paciente(medico_responsable=medico)

        with self.assertRaises(ProtectedError):
            medico.delete()

        paciente.refresh_from_db()
        self.assertEqual(paciente.medico_responsable, medico)

class CheckInProgramadoModelTests(TestCase):
    """Bloque 1 — Modelo CheckInProgramado: constraints, defaults y relaciones."""

    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente CheckIn",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
        )
        self.hoy = timezone.localdate()
        self.hora_programada = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)

    def _crear_checkin(self, orden=1, etiqueta=CheckInProgramado.ETIQUETA_MANANA, **kwargs):
        defaults = dict(
            paciente=self.paciente,
            fecha_dia=self.hoy,
            orden=orden,
            etiqueta=etiqueta,
            hora_programada=self.hora_programada,
        )
        defaults.update(kwargs)
        return CheckInProgramado.objects.create(**defaults)

    def test_creacion_exitosa_campos_validos(self):
        checkin = self._crear_checkin()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertEqual(checkin.etiqueta, CheckInProgramado.ETIQUETA_MANANA)
        self.assertEqual(checkin.orden, 1)
        self.assertIsNone(checkin.fecha_respuesta)
        self.assertIsNone(checkin.registro)

    def test_estado_default_es_pendiente(self):
        checkin = self._crear_checkin(orden=2, etiqueta=CheckInProgramado.ETIQUETA_TARDE)
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)

    def test_unique_constraint_mismo_paciente_dia_orden(self):
        self._crear_checkin(orden=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_checkin(orden=1)

    def test_dos_checkins_mismo_dia_distinto_orden_permitidos(self):
        manana = self._crear_checkin(orden=1, etiqueta=CheckInProgramado.ETIQUETA_MANANA)
        tarde  = self._crear_checkin(orden=2, etiqueta=CheckInProgramado.ETIQUETA_TARDE)
        self.assertEqual(CheckInProgramado.objects.filter(paciente=self.paciente, fecha_dia=self.hoy).count(), 2)
        self.assertNotEqual(manana.pk, tarde.pk)

    def test_fecha_dia_no_es_auto_now_add(self):
        ayer = self.hoy - timedelta(days=1)
        checkin = self._crear_checkin(fecha_dia=ayer)
        checkin.refresh_from_db()
        self.assertEqual(checkin.fecha_dia, ayer)

    def test_registro_onetooone_puede_asignarse(self):
        from decimal import Decimal
        checkin = self._crear_checkin()
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )
        checkin.registro = registro
        checkin.estado = CheckInProgramado.ESTADO_COMPLETADO
        checkin.fecha_respuesta = timezone.now()
        checkin.save()
        checkin.refresh_from_db()
        self.assertEqual(checkin.registro.pk, registro.pk)
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertIsNotNone(checkin.fecha_respuesta)

    def test_str_representacion(self):
        checkin = self._crear_checkin()
        self.assertIn(str(self.hoy), str(checkin))
        self.assertIn('MAÑANA', str(checkin))
        self.assertIn('PENDIENTE', str(checkin))

class PacienteCedulaTests(TestCase):
    """Sprint 5, Bloque 1A — campo cedula (P-4: identificador único, obligatorio)."""

    def test_paciente_sin_cedula_no_rompe_creacion(self):
        """Registros legado (sin cedula) siguen pudiéndose crear — null permitido."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Legado",
            telefono_whatsapp="+573001112222",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertIsNone(paciente.cedula)

    def test_cedula_duplicada_viola_unicidad(self):
        Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Uno",
            cedula="123456789",
            telefono_whatsapp="+573001112223",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paciente.objects.create(medico_responsable=medico_de_pruebas(),
                    nombre_completo="Paciente Dos",
                    cedula="123456789",
                    telefono_whatsapp="+573001112224",
                    fecha_cirugia=timezone.localdate(),
                )

    def test_dos_pacientes_sin_cedula_no_violan_unicidad(self):
        """NULL no cuenta como duplicado en la restricción unique (Postgres)."""
        Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Sin Cedula 1",
            telefono_whatsapp="+573001112225",
            fecha_cirugia=timezone.localdate(),
        )
        Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Sin Cedula 2",
            telefono_whatsapp="+573001112226",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertEqual(Paciente.objects.count(), 2)

    # -----------------------------------------------------------------
    # A-2: full_clean() exige cédula en pacientes nuevos
    # -----------------------------------------------------------------

    def test_full_clean_sin_cedula_en_paciente_nuevo_lanza_error(self):
        paciente = Paciente(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Nuevo Sin Cedula",
            telefono_whatsapp="+573001112227",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(ValidationError) as ctx:
            paciente.full_clean()
        self.assertIn('cedula', ctx.exception.message_dict)

    def test_full_clean_con_cedula_en_paciente_nuevo_no_lanza_error(self):
        paciente = Paciente(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Nuevo Con Cedula",
            cedula="999888777",
            telefono_whatsapp="+573001112228",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar

    def test_full_clean_paciente_existente_sin_cedula_no_lanza_error(self):
        """Pacientes migrados (ya tienen pk) no se les exige cédula retroactivamente."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(),
            nombre_completo="Paciente Legado Existente",
            telefono_whatsapp="+573001112229",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar — ya tiene pk

class PacienteActivoExigeMedicoTests(TestCase):
    """D12 — todo paciente ACTIVO tiene un médico que puede atenderlo.

    Un paciente activo sin médico responsable no es un pendiente visible: es un
    paciente invisible. Desaparece del listado del médico, desaparece de los KPI
    del tablero (el médico ve ceros, no un hueco) y su alerta ALTA queda con
    destinatario vacío. Cuatro capas, cada una tapa lo que las otras no ven.
    """

    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dra_d12',
            password='pass',
            is_staff=True,
            email='dra_d12@ejemplo.com',
        )
        ct = ContentType.objects.get_for_model(Paciente)
        self.medico.user_permissions.add(
            *Permission.objects.filter(content_type=ct)
        )

    def test_el_admin_no_deja_nacer_un_paciente_activo_sin_medico(self):
        """Capa 1 — la puerta de entrada de todos los días.

        El desplegable nace vacío y con una sola opción posible (el propio
        médico). Dejarlo así es el camino de menor resistencia, no un descuido
        rebuscado. Da igual si el formulario lo rechaza o si se lo asigna solo:
        lo que no puede quedar es un paciente activo sin responsable.
        """
        self.client.force_login(self.medico)

        self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Sin Responsable',
                'cedula': 'D12-0001',
                'telefono_whatsapp': '+573007770001',
                'fecha_cirugia': timezone.localdate().isoformat(),
                # `activo` es un checkbox: omitirlo crea el paciente INACTIVO y
                # la prueba pasaría en verde sin haber probado nada.
                'activo': 'on',
            },
            follow=True,
        )

        self.assertFalse(
            Paciente.objects.filter(
                activo=True, medico_responsable__isnull=True
            ).exists()
        )

    def test_el_admin_asigna_al_medico_que_guarda_en_vez_de_rechazarlo(self):
        """Añadida en D-4 para fijar CUÁL de los dos mecanismos se eligió.

        El invariante de arriba se cumpliría igual rechazando el formulario.
        Se eligió asignar: el médico no-superusuario solo puede elegirse a sí
        mismo, así que un error de validación sería un obstáculo por un campo
        con una única opción posible. Esta prueba impide que la corrección
        derive hacia el rechazo sin que nadie lo decida.
        """
        self.client.force_login(self.medico)

        self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Asignado Solo',
                'cedula': 'D12-0005',
                'telefono_whatsapp': '+573007770005',
                'fecha_cirugia': timezone.localdate().isoformat(),
                'activo': 'on',
            },
            follow=True,
        )

        paciente = Paciente.objects.get(cedula='D12-0005')
        self.assertEqual(paciente.medico_responsable, self.medico)

    def test_borrar_la_cuenta_del_medico_no_deja_pacientes_huerfanos(self):
        """Capa 2 — la puerta de atrás.

        Con on_delete=SET_NULL, borrar una cuenta de médico convierte a todos
        sus pacientes en huérfanos invisibles, en silencio. Quién atendió a un
        paciente es historia clínica, no configuración.
        """
        from django.db.models import ProtectedError

        Paciente.objects.create(
            nombre_completo='Paciente Con Responsable',
            telefono_whatsapp='+573007770002',
            cedula='D12-0002',
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )

        with self.assertRaises(ProtectedError):
            self.medico.delete()

    def test_la_base_rechaza_un_paciente_activo_sin_medico(self):
        """Capa 4 — la garantía, para lo que no pasa por el Admin.

        Un script, el shell o una carga de datos no ven el formulario. La
        restricción vive en la base y no se puede esquivar.
        """
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paciente.objects.create(
                    nombre_completo='Paciente De Script',
                    telefono_whatsapp='+573007770003',
                    cedula='D12-0003',
                    fecha_cirugia=timezone.localdate(),
                    medico_responsable=None,
                    activo=True,
                )

    def test_un_paciente_inactivo_sin_medico_sigue_siendo_valido(self):
        """NACE EN VERDE A PROPÓSITO: congela el alcance de la restricción.

        La palabra *activo* es la que hace el invariante cumplible. Exigir el
        médico en las filas históricas obligaría a inventarles uno — fabricar
        una atribución clínica, justo lo que D3 se negó a hacer. Esta prueba
        existe para que la capa 4 no se escriba como NOT NULL.
        """
        paciente = Paciente.objects.create(
            nombre_completo='Paciente Histórico',
            telefono_whatsapp='+573007770004',
            cedula='D12-0004',
            fecha_cirugia=timezone.localdate() - timedelta(days=30),
            medico_responsable=None,
            activo=False,
        )

        self.assertIsNone(paciente.medico_responsable)

    def _paciente_de(self, medico, sufijo):
        return Paciente.objects.create(
            nombre_completo='Paciente Sin Atención {}'.format(sufijo),
            telefono_whatsapp='+5730077711{}'.format(sufijo),
            cedula='D12-ATN-{}'.format(sufijo),
            fecha_cirugia=timezone.localdate(),
            medico_responsable=medico,
            activo=True,
        )

    def _contexto_del_tablero(self):
        from django.test import RequestFactory

        from ..templatetags.panel_admin import panel_triage

        peticion = RequestFactory().get('/')
        peticion.user = get_user_model().objects.create_superuser(
            username='super_tablero', password='pass', email='s@ejemplo.com'
        )
        return panel_triage({'request': peticion})

    def test_el_tablero_avisa_del_medico_inactivo(self):
        """Capa 3 — el riesgo operativo del día a día.

        Es la consecuencia directa de la regla "las cuentas no se borran, se
        desactivan": se desactiva al médico que se fue, sus pacientes siguen
        vivos respondiendo al bot, y sus alertas ALTA viajan al correo de
        alguien que ya no entra al sistema. El síntoma es idéntico al del
        huérfano —nadie mira a ese paciente— pero ninguna otra capa lo detecta.
        """
        medico = get_user_model().objects.create_user(
            username='dr_inactivo', password='x', is_staff=True,
            email='dr_inactivo@ejemplo.com', is_active=False,
        )
        self._paciente_de(medico, '1')

        self.assertEqual(self._contexto_del_tablero()['sin_atencion'], 1)

    def test_el_tablero_avisa_del_medico_sin_acceso_al_admin(self):
        medico = get_user_model().objects.create_user(
            username='dr_sin_staff', password='x', is_staff=False,
            email='dr_sin_staff@ejemplo.com',
        )
        self._paciente_de(medico, '2')

        self.assertEqual(self._contexto_del_tablero()['sin_atencion'], 1)

    def test_el_tablero_avisa_del_medico_sin_correo(self):
        """Un médico sin correo no recibe la alerta ALTA: el aviso no llega a
        nadie y `procesar_notificaciones_email` deja la corrida del cron en
        rojo permanente."""
        medico = get_user_model().objects.create_user(
            username='dr_sin_email', password='x', is_staff=True,
        )
        self._paciente_de(medico, '3')

        self.assertEqual(self._contexto_del_tablero()['sin_atencion'], 1)

    def test_el_tablero_no_avisa_cuando_el_medico_puede_atender(self):
        """NACE EN VERDE A PROPÓSITO: un aviso que salta siempre no es un aviso.

        `self.medico` está activo, es `is_staff` y tiene correo — las tres
        condiciones. Sin esta prueba, una consulta mal escrita que marcara a
        todos pasaría desapercibida: las otras tres seguirían en verde.
        """
        self._paciente_de(self.medico, '4')

        self.assertEqual(self._contexto_del_tablero()['sin_atencion'], 0)

    def test_el_aviso_es_visible_en_el_panel_del_superusuario(self):
        """Que el número esté en el contexto no sirve si nadie lo ve."""
        medico = get_user_model().objects.create_user(
            username='dr_invisible', password='x', is_staff=True,
        )
        self._paciente_de(medico, '5')
        superusuario = get_user_model().objects.create_superuser(
            username='super_visible', password='pass', email='sv@ejemplo.com'
        )
        self.client.force_login(superusuario)

        respuesta = self.client.get(reverse('admin:index'))

        self.assertContains(respuesta, 'sin atención efectiva')

    def test_el_seed_de_produccion_se_niega_sin_medico_usable(self):
        """El comando que hoy fabrica huérfanos: advierte y crea igual."""
        from io import StringIO

        from django.core.management import call_command

        get_user_model().objects.all().delete()

        call_command(
            'seed_demo_produccion', '--confirmar',
            stdout=StringIO(), stderr=StringIO(),
        )

        self.assertFalse(
            Paciente.objects.filter(cedula__startswith='DEMO-').exists()
        )

    def test_el_seed_de_produccion_rechaza_un_medico_inservible(self):
        """La segunda vía, más callada: el campo se llena con una cuenta inútil.

        `--medico` aceptaba cualquier username sin comprobar que la cuenta
        pudiera atender a nadie. El paciente resultante NO es huérfano —el campo
        está lleno, así que ni la restricción ni el aviso de huérfanos lo
        detectan— pero nadie puede verlo ni recibir su alerta.
        """
        from io import StringIO

        from django.core.management import call_command

        inservible = get_user_model().objects.create_user(
            username='dr_inservible', password='x', is_staff=False,
        )

        call_command(
            'seed_demo_produccion', '--confirmar', '--medico', inservible.username,
            stdout=StringIO(), stderr=StringIO(),
        )

        self.assertFalse(
            Paciente.objects.filter(cedula__startswith='DEMO-').exists()
        )
