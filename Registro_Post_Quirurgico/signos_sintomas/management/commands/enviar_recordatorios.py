"""
Management command: enviar_recordatorios

Envía (o registra como pendiente de envío) el mensaje de inicio del
check-in diario a cada paciente con CheckInProgramado PENDIENTE cuya
hora_programada ya pasó.

FASE 4 (Sprint 4): este command loguea el intento pero no envía nada
por WhatsApp — la integración Twilio saliente se implementa en Sprint 5
(FASE 4 técnica). Para cada check-in pendiente, el médico puede igualmente
usar el dashboard para ver quién no ha respondido.

Idempotente: solo procesa check-ins PENDIENTE — los COMPLETADO y
NO_RESPONDIDO ya fueron procesados.

Cron sugerido: 7:00 AM Bogotá (después de crear_checkins_diarios a las 6:00).
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from signos_sintomas.models import CheckInProgramado

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envía el recordatorio de check-in a pacientes con turno pendiente."

    def handle(self, *args, **options):
        ahora = timezone.now()
        pendientes = CheckInProgramado.objects.filter(
            estado=CheckInProgramado.ESTADO_PENDIENTE,
            hora_programada__lte=ahora,
        ).select_related('paciente')

        enviados = 0
        for checkin in pendientes:
            telefono = checkin.paciente.telefono_whatsapp
            # FASE 4: sustituir este bloque por llamada a Twilio.
            # twilio_client.messages.create(
            #     from_='whatsapp:+14155238886',
            #     to=f'whatsapp:{telefono}',
            #     body="Buenos días 🌿 Es hora de tu reporte diario..."
            # )
            logger.info(
                "enviar_recordatorios: check-in %d — paciente %s (%s) — "
                "programado %s — [envío Twilio pendiente FASE 4]",
                checkin.pk,
                checkin.paciente.nombre_completo,
                telefono,
                checkin.hora_programada.isoformat(),
            )
            enviados += 1

        resumen = (
            f"enviar_recordatorios {timezone.localdate()}: "
            f"{enviados} check-ins procesados (envío Twilio diferido a FASE 4)."
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
