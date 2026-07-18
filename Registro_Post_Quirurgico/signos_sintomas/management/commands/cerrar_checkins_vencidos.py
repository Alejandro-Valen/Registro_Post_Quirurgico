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
from django.db import transaction
from django.utils import timezone

from signos_sintomas.alert_engine import registrar_alerta_silencio
from signos_sintomas.models import (
    CheckInProgramado,
    ConversacionWhatsApp,
    Paciente,
)

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

        vencidos = list(
            CheckInProgramado.objects.filter(
                estado=CheckInProgramado.ESTADO_PENDIENTE,
                hora_programada__lte=corte,
            ).order_by('hora_programada', 'pk').values_list('pk', flat=True)
        )

        cerrados = 0
        detecciones_silencio = 0
        conversaciones_activas = 0

        for checkin_pk in vencidos:
            with transaction.atomic():
                checkin = (
                    CheckInProgramado.objects.select_for_update()
                    .select_related('paciente')
                    .filter(
                        pk=checkin_pk,
                        estado=CheckInProgramado.ESTADO_PENDIENTE,
                        hora_programada__lte=corte,
                    )
                    .first()
                )
                if checkin is None:
                    continue

                conversacion_activa = ConversacionWhatsApp.objects.filter(
                    checkin_actual=checkin,
                    fecha_actualizacion__gt=corte,
                ).exclude(
                    estado__in=[
                        ConversacionWhatsApp.ESTADO_INICIO,
                        ConversacionWhatsApp.ESTADO_COMPLETADO,
                    ],
                ).exists()
                if conversacion_activa:
                    conversaciones_activas += 1
                    continue

                checkin.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
                checkin.save(update_fields=['estado'])
                cerrados += 1

                racha = _calcular_racha(checkin.paciente, checkin)
                severidad = _severidad_silencio(racha)

                registrar_alerta_silencio(
                    checkin,
                    severidad,
                    f"El paciente no completó el check-in del "
                    f"{checkin.fecha_dia} ({checkin.get_etiqueta_display()}). "
                    f"Racha de {racha} check-in(s) sin respuesta consecutivos.",
                )
                detecciones_silencio += 1

                logger.info(
                    "cerrar_checkins_vencidos: check-in pk=%d, paciente pk=%d, "
                    "racha=%d, alerta SILENCIO=%s.",
                    checkin.pk,
                    checkin.paciente_id,
                    racha,
                    severidad,
                )

        resumen = (
            f"cerrar_checkins_vencidos {timezone.localdate()}: "
            f"{cerrados} check-ins cerrados, {detecciones_silencio} detecciones "
            f"SILENCIO, {conversaciones_activas} conversaciones activas omitidas."
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
