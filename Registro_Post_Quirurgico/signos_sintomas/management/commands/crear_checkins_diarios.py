"""
Management command: crear_checkins_diarios

Crea los 2 CheckInProgramado del día (mañana y tarde) para cada paciente
activo. Se ejecuta una vez al día a las 6:00 AM (Bogotá) vía cron del SO.

Idempotente: usa get_or_create — si ya existe el check-in, no lo duplica.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from signos_sintomas.models import CheckInProgramado, Paciente

logger = logging.getLogger(__name__)

# Horas locales (Bogotá, UTC-5) para los dos turnos.
HORA_MANANA = 7   # 7:00 AM → el patient recibe el primer prompt
HORA_TARDE  = 14  # 2:00 PM → el segundo prompt


class Command(BaseCommand):
    help = "Crea los check-ins programados del día para todos los pacientes activos."

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        tz  = timezone.get_current_timezone()

        pacientes = Paciente.objects.filter(activo=True)
        creados = 0
        omitidos = 0

        for paciente in pacientes:
            for orden, etiqueta, hora in [
                (1, CheckInProgramado.ETIQUETA_MANANA, HORA_MANANA),
                (2, CheckInProgramado.ETIQUETA_TARDE,  HORA_TARDE),
            ]:
                hora_programada = timezone.datetime(
                    hoy.year, hoy.month, hoy.day, hora, 0, 0,
                    tzinfo=tz,
                )
                _, fue_creado = CheckInProgramado.objects.get_or_create(
                    paciente=paciente,
                    fecha_dia=hoy,
                    orden=orden,
                    defaults={
                        'etiqueta': etiqueta,
                        'hora_programada': hora_programada,
                    },
                )
                if fue_creado:
                    creados += 1
                else:
                    omitidos += 1

        resumen = (
            f"crear_checkins_diarios {hoy}: "
            f"{creados} creados, {omitidos} ya existían "
            f"({pacientes.count()} pacientes activos)."
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
