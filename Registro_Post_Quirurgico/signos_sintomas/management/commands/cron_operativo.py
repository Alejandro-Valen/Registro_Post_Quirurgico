"""Tareas frecuentes que comparten el servicio cron operativo de Railway."""

from django.core.management import call_command
from django.core.management.base import BaseCommand


TAREAS_OPERATIVAS = [
    'cerrar_checkins_vencidos',
    'procesar_notificaciones_email',
]


class Command(BaseCommand):
    help = 'Cierra check-ins vencidos y procesa notificaciones pendientes.'

    def handle(self, *args, **options):
        for tarea in TAREAS_OPERATIVAS:
            self.stdout.write(f'--- cron_operativo: {tarea} ---')
            call_command(tarea)
        self.stdout.write(
            self.style.SUCCESS('cron_operativo: todas las tareas completadas.')
        )
