"""
Management command: cron_matutino

Ejecuta EN ORDEN las tareas programadas de la mañana (6:00 AM Bogotá). Se usa
como el único comando de arranque del servicio cron matutino de Railway.

Por qué un solo comando: encadenar con '&&' en el "Custom Start Command" de
Railway resultó ejecutar SOLO el primer comando (el resto se descartaba). Aquí
el orden queda garantizado por la lista de abajo, que se recorre en secuencia
dentro de un mismo proceso, y es testeable.

Ante un fallo (D14): las tareas están aisladas entre sí — un fallo operativo no
puede impedir que se entregue una alerta clínica ya generada. La única excepción
es la dependencia declarada abajo, con su motivo. La corrida termina en error
igualmente. Ver `signos_sintomas/cron_runner.py`.
"""

from django.core.management.base import BaseCommand

from signos_sintomas.cron_runner import TareaCron, ejecutar_tareas

TAREAS_MATUTINAS = [
    TareaCron('desactivar_pacientes_vencidos'),
    TareaCron(
        'crear_checkins_diarios',
        depende_de='desactivar_pacientes_vencidos',
        motivo=(
            'Motivo clínico: sin la desactivación previa, un paciente que vence '
            'hoy recibiría un check-in que quedaría PENDIENTE para siempre '
            '—ya no responde— y generaría una alerta SILENCIO espuria al '
            'cerrarse. Ver docs/cron_setup.md.'
        ),
    ),
    TareaCron('cerrar_checkins_vencidos'),
    TareaCron('enviar_recordatorios'),
    TareaCron('reintentar_evaluaciones_alertas'),
    TareaCron('procesar_notificaciones_email'),
]


class Command(BaseCommand):
    help = "Ejecuta en orden las tareas matutinas del cron (para Railway)."

    def handle(self, *args, **options):
        ejecutar_tareas(self, 'cron_matutino', TAREAS_MATUTINAS)
