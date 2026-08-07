"""Tareas frecuentes que comparten el servicio cron operativo de Railway.

Ninguna de las tres depende clínicamente de otra: están juntas porque el plan
de Railway no daba para más servicios. Por eso ninguna declara `depende_de` —
un fallo de la primera no puede costar la entrega de las alertas ALTA del ciclo
(D14, ver `signos_sintomas/cron_runner.py`).
"""

from django.core.management.base import BaseCommand

from signos_sintomas.cron_runner import TareaCron, ejecutar_tareas


TAREAS_OPERATIVAS = [
    TareaCron('cerrar_checkins_vencidos'),
    TareaCron('reintentar_evaluaciones_alertas'),
    TareaCron('procesar_notificaciones_email'),
]


class Command(BaseCommand):
    help = (
        'Cierra check-ins vencidos, reintenta evaluaciones y procesa '
        'notificaciones pendientes.'
    )

    def handle(self, *args, **options):
        ejecutar_tareas(self, 'cron_operativo', TAREAS_OPERATIVAS)
