"""
Management command: seed_demo

Crea datos de demostración para mostrar el dashboard al equipo médico:
- 1 usuario demo is_staff (sin is_superuser — representa a un médico real)
- 1 paciente ficticio (Camilo Rueda, tel +573001234567)
- 10 días de RegistroDiario con variedad clínica (fiebre, drenaje, etc.)
- Las alertas se generan automáticamente por el alert_engine

Idempotente: si el paciente demo ya existe, omite la creación.

Solo puede ejecutarse con DEBUG=True (A-3): crea una cuenta con contraseña
conocida, por lo que en producción el comando aborta sin hacer nada.

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --borrar   # elimina y recrea todo
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from signos_sintomas.evaluacion_alertas import evaluar_registro_con_estado
from signos_sintomas.management.commands.crear_medico import (
    NOMBRE_GRUPO_MEDICOS,
    obtener_permisos_medico,
)
from signos_sintomas.models import (
    Alerta, CheckInProgramado, Paciente, RegistroDiario
)

logger = logging.getLogger(__name__)

TELEFONO_DEMO = '+573001234567'
USERNAME_DEMO = 'demo_medico'


# Datos de 10 días — (temp, dolor, gases, nauseas, aspecto_drenaje, tolero_liq, fc)
# aspecto_drenaje: si None → tiene_drenaje=False
_DIAS = [
    # POD 1 — post-op inmediato: fiebre, sin gases, drenaje seroso
    (37.6, 7, False, 1, 'seroso',        None,  88),
    # POD 2 — continúa sin gases, dolor alto
    (37.4, 8, False, 2, 'seroso',        True,  92),
    # POD 3 — fiebre alta → alerta SEPSIS ALTA
    (38.2, 6, False, 1, 'seroso',        True,  95),
    # POD 4 — mejora, primeros gases
    (37.2, 5, True,  0, 'seroso',        True,  82),
    # POD 5 — drenaje turbio → FUGA_ANASTOMOTICA MEDIA
    (37.0, 4, True,  0, 'turbio',        True,  78),
    # POD 6 — intolerancia oral
    (36.9, 3, True,  2, 'seroso',        False, 80),
    # POD 7 — mejoría, taquicardia leve
    (36.8, 3, True,  1, 'seroso',        True, 105),
    # POD 8 — buena evolución
    (36.7, 2, True,  0, None,            True,  76),
    # POD 9 — drenaje purulento → FUGA ALTA
    (37.1, 4, True,  0, 'purulento',     True,  91),
    # POD 10 — recuperación
    (36.8, 2, True,  0, None,            True,  74),
]


class Command(BaseCommand):
    help = "Crea datos de demostración para el dashboard médico."

    def add_arguments(self, parser):
        parser.add_argument(
            '--borrar',
            action='store_true',
            help='Elimina el paciente demo y todos sus datos antes de recrear.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stderr.write(
                self.style.ERROR(
                    'seed_demo NO puede ejecutarse en producción (DEBUG=False). '
                    'Este comando crea datos ficticios y una cuenta demo con '
                    'contraseña conocida. Abortando.'
                )
            )
            return

        User = get_user_model()

        if options['borrar']:
            Paciente.objects.filter(telefono_whatsapp=TELEFONO_DEMO).delete()
            self.stdout.write(self.style.WARNING('Datos demo anteriores eliminados.'))

        # Usuario demo — is_staff sin is_superuser, para representar la
        # experiencia real de un médico (ve solo sus propios pacientes; sin
        # acceso a Usuarios ni AXES). A-3, hallazgo de auditoría 02/07/2026.
        if not User.objects.filter(username=USERNAME_DEMO).exists():
            medico = User.objects.create_user(
                username=USERNAME_DEMO,
                password='demo1234',
                email='demo@medico.com',
                first_name='Demo',
                last_name='Médico',
                is_staff=True,
                is_superuser=False,
            )
            self.stdout.write(f'  Usuario demo creado: {USERNAME_DEMO} / demo1234')
        else:
            medico = User.objects.get(username=USERNAME_DEMO)

        grupo, _ = Group.objects.get_or_create(name=NOMBRE_GRUPO_MEDICOS)
        grupo.permissions.set(obtener_permisos_medico())
        medico.is_staff = True
        medico.is_superuser = False
        medico.save(update_fields=['is_staff', 'is_superuser'])
        medico.groups.set([grupo])
        medico.user_permissions.clear()

        if Paciente.objects.filter(telefono_whatsapp=TELEFONO_DEMO).exists():
            self.stdout.write(self.style.WARNING(
                f'El paciente demo ya existe ({TELEFONO_DEMO}). '
                f'Usa --borrar para recrear.'
            ))
            return

        # Paciente ficticio
        hoy = timezone.localdate()
        fecha_cirugia = hoy - timedelta(days=10)
        paciente = Paciente.objects.create(
            nombre_completo='Camilo Andrés Rueda Vargas',
            telefono_whatsapp=TELEFONO_DEMO,
            fecha_cirugia=fecha_cirugia,
            tipo_cirugia='colectomia_electiva',
            medico_responsable=medico,
            activo=True,
            consentimiento_informado=True,
        )
        self.stdout.write(f'  Paciente demo creado: {paciente.nombre_completo}')

        # 10 días de registros diarios
        alertas_total = 0
        for dia_idx, (temp, dolor, gases, nauseas, aspecto, tolero, fc) in enumerate(_DIAS):
            fecha_reg = timezone.datetime.combine(
                fecha_cirugia + timedelta(days=dia_idx + 1),
                timezone.datetime.min.time(),
                tzinfo=timezone.get_current_timezone(),
            ) + timedelta(hours=8)

            tiene_drenaje = aspecto is not None
            registro = RegistroDiario.objects.create(
                paciente=paciente,
                fecha_registro=fecha_reg,
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

            # Crear check-in completado para ese día
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

            alertas = evaluar_registro_con_estado(
                registro,
                fecha_referencia=registro.fecha_registro.date(),
            )
            alertas_total += len(alertas)

        self.stdout.write(
            self.style.SUCCESS(
                f'  10 registros creados, {alertas_total} alertas generadas.'
            )
        )
        self.stdout.write(self.style.SUCCESS(
            f'\nSeed demo completo. Accede al admin con: {USERNAME_DEMO} / demo1234'
        ))
