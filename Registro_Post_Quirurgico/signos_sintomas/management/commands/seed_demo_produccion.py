"""
Management command: seed_demo_produccion

Crea 2 pacientes de EJEMPLO para mostrarle el dashboard al médico (panel del
Admin: lista de pacientes, alertas por severidad, gráficas e historial).

A diferencia de `seed_demo` (que está bloqueado en producción por el guard A-3
porque crea una cuenta con contraseña conocida), este comando SÍ puede correr
en producción de forma segura porque:

  1. NO crea ningún usuario ni contraseña — asigna los pacientes a un médico ya
     existente (--medico, o el primer superusuario).
  2. Exige la bandera explícita --confirmar: nunca corre por accidente.
  3. Los pacientes quedan marcados de forma inconfundible (nombre con prefijo
     "DEMO — ", cédula "DEMO-000X" y un teléfono ficticio reservado), así que
     jamás se confunden con un paciente real y el bot/cron nunca escribe a un
     número real.
  4. Es totalmente reversible: --limpiar borra EXACTAMENTE estos pacientes de
     ejemplo (y sus registros, alertas, check-ins y conversación), sin tocar
     ningún paciente real. Es la vía correcta porque los modelos usan PROTECT
     y por eso un paciente con registros NO se puede borrar desde el Admin.

Los registros se crean directamente en la base de datos (no pasan por WhatsApp
ni Twilio); las alertas las genera el alert_engine, igual que en producción.

Uso:
    # Crear los 2 pacientes de ejemplo:
    python manage.py seed_demo_produccion --confirmar
    python manage.py seed_demo_produccion --confirmar --medico usuario_del_medico

    # Retirarlos cuando el médico apruebe (deja la base limpia):
    python manage.py seed_demo_produccion --limpiar --confirmar

    # En local, agregar:  --settings=Registro_Post_Quirurgico.settings_local
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from signos_sintomas.alert_engine import evaluar_registro
from signos_sintomas.models import (
    Alerta, CheckInProgramado, ConversacionWhatsApp, Paciente, RegistroDiario,
)

logger = logging.getLogger(__name__)

PREFIJO_DEMO = 'DEMO — '

# Cada fila = (temp, dolor, gases, nauseas, aspecto_drenaje | None, tolero_liq, fc)
# aspecto None → tiene_drenaje=False.

# Paciente 1 — evolución COMPLICADA (fiebre/sepsis, fuga, taquicardia).
_DIAS_COMPLICADA = [
    (37.7, 7, False, 2, 'seroso',    True,  96),   # POD 1
    (38.0, 8, False, 3, 'seroso',    True, 100),   # POD 2 — fiebre + náuseas
    (38.3, 7, False, 2, 'turbio',    True, 108),   # POD 3 — SEPSIS/FUGA/taqui
    (37.6, 6, False, 1, 'turbio',    False,104),   # POD 4 — intolerancia
    (37.2, 5, True,  1, 'purulento', True,  98),   # POD 5 — FUGA alta
    (37.0, 4, True,  0, 'seroso',    True,  88),   # POD 6
    (36.9, 4, True,  0, 'seroso',    True,  84),   # POD 7
    (36.8, 3, True,  0, None,        True,  80),   # POD 8
    (36.7, 2, True,  0, None,        True,  76),   # POD 9
    (36.8, 2, True,  0, None,        True,  74),   # POD 10 — recuperación
]

# Paciente 2 — evolución MÁS LEVE (alguna náusea, dolor bajo, una intolerancia).
_DIAS_LEVE = [
    (37.2, 5, False, 1, 'seroso', True, 86),   # POD 1
    (37.1, 4, True,  1, 'seroso', True, 84),   # POD 2
    (37.0, 4, True,  2, 'seroso', True, 88),   # POD 3 — náuseas leves
    (36.9, 3, True,  0, 'seroso', True, 82),   # POD 4
    (37.3, 3, True,  0, 'seroso', False,90),   # POD 5 — intolerancia puntual
    (36.8, 2, True,  0, None,     True, 78),   # POD 6
    (36.8, 2, True,  0, None,     True, 76),   # POD 7
    (36.7, 1, True,  0, None,     True, 74),   # POD 8
]

DEMOS = [
    {
        'nombre': PREFIJO_DEMO + 'María González Ríos',
        'telefono': '+575550000001',
        'cedula': 'DEMO-0001',
        'tipo': 'colectomia_electiva',
        'dias': _DIAS_COMPLICADA,
    },
    {
        'nombre': PREFIJO_DEMO + 'Jorge Martínez Peña',
        'telefono': '+575550000002',
        'cedula': 'DEMO-0002',
        'tipo': 'sugarbaker_hipec',
        'dias': _DIAS_LEVE,
    },
]

TELEFONOS_DEMO = [d['telefono'] for d in DEMOS]


class Command(BaseCommand):
    help = "Crea (o retira) 2 pacientes de ejemplo para mostrar el dashboard médico."

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Obligatorio: confirma la operación (crear o limpiar).',
        )
        parser.add_argument(
            '--limpiar', action='store_true',
            help='Elimina los pacientes de ejemplo y todos sus datos.',
        )
        parser.add_argument(
            '--medico', default=None,
            help='username del médico al que se asignan los pacientes de ejemplo. '
                 'Por defecto: el primer superusuario.',
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(self.style.WARNING(
                'Este comando modifica la base de datos. Debes confirmar la '
                'operación con --confirmar.\n\n'
                '  Crear:   python manage.py seed_demo_produccion --confirmar\n'
                '  Limpiar: python manage.py seed_demo_produccion --limpiar --confirmar'
            ))
            return

        if options['limpiar']:
            self._limpiar()
            return

        self._crear(options['medico'])

    # ------------------------------------------------------------------ limpiar
    def _limpiar(self):
        pacientes = Paciente.objects.filter(telefono_whatsapp__in=TELEFONOS_DEMO)
        if not pacientes.exists():
            self.stdout.write(self.style.WARNING(
                'No hay pacientes de ejemplo para eliminar.'
            ))
            return

        pids = list(pacientes.values_list('pk', flat=True))
        # Orden obligatorio por las FKs PROTECT:
        # Alerta → CheckInProgramado → RegistroDiario → ConversacionWhatsApp → Paciente
        n_alertas = Alerta.objects.filter(paciente_id__in=pids).delete()[0]
        n_checkins = CheckInProgramado.objects.filter(paciente_id__in=pids).delete()[0]
        n_registros = RegistroDiario.objects.filter(paciente_id__in=pids).delete()[0]
        n_conv = ConversacionWhatsApp.objects.filter(paciente_id__in=pids).delete()[0]
        n_pac = pacientes.delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'Pacientes de ejemplo eliminados: {n_pac} pacientes, '
            f'{n_registros} registros, {n_alertas} alertas, '
            f'{n_checkins} check-ins, {n_conv} conversaciones.'
        ))

    # ------------------------------------------------------------------- crear
    def _crear(self, medico_username):
        if Paciente.objects.filter(telefono_whatsapp__in=TELEFONOS_DEMO).exists():
            self.stdout.write(self.style.WARNING(
                'Los pacientes de ejemplo ya existen. Para recrearlos, primero:\n'
                '  python manage.py seed_demo_produccion --limpiar --confirmar'
            ))
            return

        User = get_user_model()
        if medico_username:
            medico = User.objects.filter(username=medico_username).first()
            if medico is None:
                self.stderr.write(self.style.ERROR(
                    f'No existe un usuario con username "{medico_username}". Abortando.'
                ))
                return
        else:
            medico = User.objects.filter(is_superuser=True).order_by('pk').first()
            if medico is None:
                self.stdout.write(self.style.WARNING(
                    'No hay superusuario en la base: los pacientes de ejemplo '
                    'quedarán sin médico asignado. Usa --medico <username> para asignarlos.'
                ))

        total_alertas = 0
        for demo in DEMOS:
            total_alertas += self._crear_paciente(demo, medico)

        etiqueta_medico = medico.username if medico else '(sin médico)'
        self.stdout.write(self.style.SUCCESS(
            f'\n2 pacientes de ejemplo creados y asignados a: {etiqueta_medico}.\n'
            f'Alertas generadas por el motor: {total_alertas}.\n'
            f'Entra al Admin (/admin/) con tu cuenta para verlos en el dashboard.\n'
            f'Para retirarlos: python manage.py seed_demo_produccion --limpiar --confirmar'
        ))

    @transaction.atomic
    def _crear_paciente(self, demo, medico):
        hoy = timezone.localdate()
        dias = demo['dias']
        fecha_cirugia = hoy - timedelta(days=len(dias))

        paciente = Paciente.objects.create(
            nombre_completo=demo['nombre'],
            cedula=demo['cedula'],
            telefono_whatsapp=demo['telefono'],
            fecha_cirugia=fecha_cirugia,
            tipo_cirugia=demo['tipo'],
            medico_responsable=medico,
            activo=True,
            consentimiento_informado=True,
        )
        self.stdout.write(f'  Paciente de ejemplo creado: {paciente.nombre_completo}')

        tz = timezone.get_current_timezone()
        alertas_paciente = 0
        for dia_idx, (temp, dolor, gases, nauseas, aspecto, tolero, fc) in enumerate(dias):
            fecha_reg = timezone.datetime.combine(
                fecha_cirugia + timedelta(days=dia_idx + 1),
                timezone.datetime.min.time(),
                tzinfo=tz,
            ) + timedelta(hours=8)

            tiene_drenaje = aspecto is not None
            registro = RegistroDiario.objects.create(
                paciente=paciente,
                temperatura=Decimal(str(temp)),
                dolor_eva=dolor,
                tiene_drenaje=tiene_drenaje,
                aspecto_drenaje=aspecto if tiene_drenaje else 'sin_drenaje',
                cantidad_drenaje='normal' if tiene_drenaje else 'sin_drenaje',
                presencia_gases=gases,
                episodios_nauseas=nauseas,
                tolero_liquidos=tolero,
                frecuencia_cardiaca=fc,
            )
            # fecha_registro es auto_now_add; se fija al día correcto con update().
            RegistroDiario.objects.filter(pk=registro.pk).update(fecha_registro=fecha_reg)
            registro.refresh_from_db()

            CheckInProgramado.objects.create(
                paciente=paciente,
                fecha_dia=registro.fecha_registro.date(),
                orden=1,
                etiqueta=CheckInProgramado.ETIQUETA_MANANA,
                hora_programada=fecha_reg,
                fecha_respuesta=fecha_reg + timedelta(minutes=15),
                estado=CheckInProgramado.ESTADO_COMPLETADO,
                registro=registro,
            )

            alertas = evaluar_registro(
                registro, fecha_referencia=registro.fecha_registro.date(),
            )
            alertas_paciente += len(alertas)

        self.stdout.write(f'    {len(dias)} registros, {alertas_paciente} alertas.')
        return alertas_paciente
