"""
Management command: desactivar_pacientes_vencidos

Desactiva pacientes cuyo día postoperatorio supera DIAS_SEGUIMIENTO (10,
decisión de producto P-5, 01/07/2026). La desactivación manual por el
médico sigue disponible desde el Admin; este command cubre el caso
automático. Se ejecuta diario junto con crear_checkins_diarios, pero
ANTES de este (no después) — así el paciente que justo vence ese día no
recibe un check-in que después quedaría PENDIENTE para siempre y
terminaría generando una alerta SILENCIO espuria (ver
test_scheduler_no_crea_checkins_tras_desactivacion en tests.py).

Idempotente: solo actúa sobre pacientes con activo=True, así que correrlo
dos veces el mismo día no tiene efecto la segunda vez.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from signos_sintomas.models import Paciente

logger = logging.getLogger(__name__)

DIAS_SEGUIMIENTO = 10  # decisión de producto P-5, 01/07/2026


class Command(BaseCommand):
    help = "Desactiva pacientes cuyo día postoperatorio alcanza DIAS_SEGUIMIENTO."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué pacientes se desactivarían, sin modificar la BD.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.localdate()

        desactivados = []
        for paciente in Paciente.objects.filter(activo=True):
            dias_post = (hoy - paciente.fecha_cirugia).days
            if dias_post >= DIAS_SEGUIMIENTO:
                desactivados.append((paciente, dias_post))
                if not dry_run:
                    paciente.activo = False
                    paciente.save(update_fields=['activo'])

        for paciente, dias_post in desactivados:
            mensaje = (
                f'desactivar_pacientes_vencidos: {paciente.nombre_completo} '
                f'{"se desactivaría" if dry_run else "desactivado"} (POD {dias_post})'
            )
            logger.info(mensaje)
            self.stdout.write(self.style.WARNING(mensaje))

        resumen = (
            f'desactivar_pacientes_vencidos {hoy}: '
            f'{len(desactivados)} paciente(s) '
            f'{"a desactivar (dry-run)" if dry_run else "desactivados"}.'
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
