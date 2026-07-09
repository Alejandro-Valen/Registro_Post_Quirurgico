"""
Management command: cerrar_checkins_vencidos

Cierra los CheckInProgramado PENDIENTE que superaron el período de gracia
(10 horas desde hora_programada) y genera una alerta SILENCIO según la
racha de check-ins sin respuesta.

Racha (check a check, ignorando horas): cuenta cuántos check-ins
consecutivos terminaron en NO_RESPONDIDO inmediatamente antes del actual,
en orden cronológico estricto (fecha_dia + orden).
  - Racha 1 (este check-in solo)  → SILENCIO BAJA
  - Racha 2 consecutivos          → SILENCIO MEDIA
  - Racha 3+                      → SILENCIO ALTA

La racha se rompe con cualquier check-in COMPLETADO entre medias.

El command es idempotente: el CheckConstraint `unique_checkin_paciente_dia_orden`
impide duplicados, y la verificación de estado PENDIENTE evita reprocesar.

Cron sugerido: 18:00 (tarde) y 06:00 AM (mañana siguiente) Bogotá.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from signos_sintomas.models import Alerta, CheckInProgramado, Paciente

logger = logging.getLogger(__name__)

HORAS_GRACIA = 10


def _calcular_racha(paciente, checkin_actual):
    """
    Cuenta cuántos check-ins NO_RESPONDIDO consecutivos preceden al actual
    (el actual NO está incluido en el conteo — representa el último del bloque).
    Devuelve racha_total = anteriores_no_respondidos + 1 (el actual).
    """
    anteriores = CheckInProgramado.objects.filter(
        paciente=paciente,
    ).exclude(
        pk=checkin_actual.pk,
    ).order_by('-fecha_dia', '-orden')

    racha = 1  # incluye el check-in actual
    for ci in anteriores:
        if ci.estado == CheckInProgramado.ESTADO_NO_RESPONDIDO:
            racha += 1
        else:
            # COMPLETADO o PENDIENTE rompe la racha
            break
    return racha


def _severidad_silencio(racha):
    if racha >= 3:
        return 'ALTA'
    if racha == 2:
        return 'MEDIA'
    return 'BAJA'


class Command(BaseCommand):
    help = "Cierra check-ins vencidos y genera alertas SILENCIO según racha de no-respuesta."

    def handle(self, *args, **options):
        ahora = timezone.now()
        corte = ahora - timedelta(hours=HORAS_GRACIA)

        vencidos = CheckInProgramado.objects.filter(
            estado=CheckInProgramado.ESTADO_PENDIENTE,
            hora_programada__lte=corte,
        ).select_related('paciente')

        cerrados = 0
        alertas_creadas = 0

        for checkin in vencidos:
            checkin.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
            checkin.save(update_fields=['estado'])
            cerrados += 1

            racha = _calcular_racha(checkin.paciente, checkin)
            severidad = _severidad_silencio(racha)

            Alerta.objects.create(
                paciente=checkin.paciente,
                registro_origen=None,
                tipo='SILENCIO',
                severidad=severidad,
                mensaje=(
                    f"El paciente no completó el check-in del "
                    f"{checkin.fecha_dia} ({checkin.get_etiqueta_display()}). "
                    f"Racha de {racha} check-in(s) sin respuesta consecutivos."
                ),
            )
            alertas_creadas += 1

            logger.info(
                "cerrar_checkins_vencidos: check-in %d — %s — %s %s — "
                "racha %d — alerta SILENCIO %s creada.",
                checkin.pk,
                checkin.paciente.nombre_completo,
                checkin.fecha_dia,
                checkin.get_etiqueta_display(),
                racha,
                severidad,
            )

        resumen = (
            f"cerrar_checkins_vencidos {timezone.localdate()}: "
            f"{cerrados} check-ins cerrados, {alertas_creadas} alertas SILENCIO creadas."
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
