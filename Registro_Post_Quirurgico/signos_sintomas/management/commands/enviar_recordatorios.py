"""
Management command: enviar_recordatorios

Envía (o registra como pendiente de envío) el mensaje de inicio del
check-in diario a cada paciente con CheckInProgramado PENDIENTE cuya
hora_programada ya pasó.

Es un STUB: loguea el intento pero no envía nada por WhatsApp. La
integración Twilio saliente está diferida sin fecha —el Sprint 5 cerró sin
ella— y necesita WhatsApp Business API, que es requisito del piloto real
(ver ROADMAP, «Requisitos para un PILOTO REAL»). Mientras tanto el sistema
es reactivo: el paciente escribe primero, y el médico ve en el panel quién
no ha respondido.

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
            telefono = checkin.paciente.telefono_whatsapp  # noqa: F841  (lo usa la llamada a Twilio de la FASE 4, comentada abajo)
            # FASE 4: sustituir este bloque por llamada a Twilio.
            # twilio_client.messages.create(
            #     from_='whatsapp:+14155238886',
            #     to=f'whatsapp:{telefono}',
            #     body="Buenos días 🌿 Es hora de tu reporte diario..."
            # )
            # D11: ni nombre ni teléfono en la salida. El teléfono se sigue
            # leyendo arriba porque la llamada real a Twilio lo necesita, pero
            # no se escribe: bastaba bajar el nivel del logger a INFO para
            # volcar la lista completa de pacientes con su celular.
            logger.info(
                "enviar_recordatorios: check-in %d — paciente pk=%d — "
                "programado %s — [envío Twilio pendiente FASE 4]",
                checkin.pk,
                checkin.paciente_id,
                checkin.hora_programada.isoformat(),
            )
            enviados += 1

        resumen = (
            f"enviar_recordatorios {timezone.localdate()}: "
            f"{enviados} check-ins procesados (envío Twilio diferido a FASE 4)."
        )
        logger.info(resumen)
        self.stdout.write(self.style.SUCCESS(resumen))
