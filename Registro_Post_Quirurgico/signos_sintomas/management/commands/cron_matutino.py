"""
Management command: cron_matutino

Ejecuta EN ORDEN las tareas programadas de la mañana (6:00 AM Bogotá). Se usa
como el único comando de arranque del servicio cron matutino de Railway.

Por qué un solo comando: encadenar con '&&' en el "Custom Start Command" de
Railway resultó ejecutar SOLO el primer comando (el resto se descartaba). Aquí
el orden queda garantizado por `call_command` secuencial, dentro de un mismo
proceso, y es testeable.

Orden no negociable: `desactivar_pacientes_vencidos` ANTES de
`crear_checkins_diarios` (ver docs/cron_setup.md — si se invierte, un paciente
que vence ese día recibiría un check-in que quedaría PENDIENTE para siempre).
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

TAREAS_MATUTINAS = [
    'desactivar_pacientes_vencidos',
    'crear_checkins_diarios',
    'cerrar_checkins_vencidos',
    'enviar_recordatorios',
    'reintentar_evaluaciones_alertas',
]


class Command(BaseCommand):
    help = "Ejecuta en orden las tareas matutinas del cron (para Railway)."

    def handle(self, *args, **options):
        for tarea in TAREAS_MATUTINAS:
            self.stdout.write(f'--- cron_matutino: {tarea} ---')
            call_command(tarea)
        self.stdout.write(
            self.style.SUCCESS('cron_matutino: todas las tareas completadas.')
        )
