"""
Señales de la app signos_sintomas.

Bloque 5C — Notificación email al médico responsable cuando se crea una
alerta de severidad ALTA. El envío se difiere con on_commit para garantizar
que la alerta ya existe en BD antes de intentar enviar el correo.

Backend de email:
- Desarrollo: EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
  (imprime en consola, no envía nada real — ver settings.py).
- Producción: configurar SMTP real en settings_production.py (Sprint 5).
"""

import logging

from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Alerta

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alerta)
def notificar_alerta_alta(sender, instance, created, **kwargs):
    """Envía email al médico responsable cuando una alerta ALCANZA severidad
    ALTA: al crearse como ALTA, o al ESCALAR a ALTA una alerta ya abierta
    (decisión Arquitecto 10/07/2026). NO se reenvía en cada recurrencia diaria
    del mismo problema — solo la primera vez que llega a ALTA. La escalada la
    marca el alert_engine con `instance._escalo_a_alta`."""
    if instance.severidad != 'ALTA':
        return
    escalo_a_alta = getattr(instance, '_escalo_a_alta', False)
    if not (created or escalo_a_alta):
        return

    medico = instance.paciente.medico_responsable
    if medico is None or not medico.email:
        logger.warning(
            "Alerta ALTA (pk=%d, tipo=%s) sin médico responsable o sin email — "
            "notificación no enviada.",
            instance.pk,
            instance.tipo,
        )
        return

    def _enviar():
        paciente = instance.paciente
        cedula_str = paciente.cedula or 'No registrada'

        asunto = (
            f"⚠️ ALERTA ALTA — {instance.get_tipo_display()} | "
            f"{paciente.nombre_completo}"
        )
        cuerpo = (
            f"⚠️  ALERTA CLÍNICA — ACCIÓN REQUERIDA\n"
            f"{'─' * 45}\n\n"
            f"PACIENTE\n"
            f"  Nombre:   {paciente.nombre_completo}\n"
            f"  Cédula:   {cedula_str}\n"
            f"  Teléfono: {paciente.telefono_whatsapp}\n\n"
            f"ALERTA\n"
            f"  Tipo:      {instance.get_tipo_display()}\n"
            f"  Severidad: {instance.get_severidad_display()}\n"
            f"  Fecha:     "
            f"{timezone.localtime(instance.fecha_alerta).strftime('%d/%m/%Y %H:%M')} "
            f"(hora Bogotá)\n\n"
            f"DETALLE\n"
            f"  {instance.mensaje}\n\n"
            f"{'─' * 45}\n"
            f"Por favor contacte al paciente o derive a urgencias si es necesario.\n\n"
            f"— Sistema de Monitoreo Posquirúrgico\n"
            f"  (Este es un mensaje automático — no responder a este correo)\n"
        )
        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=None,  # usa DEFAULT_FROM_EMAIL de settings
                recipient_list=[medico.email],
                fail_silently=False,
            )
            logger.info(
                "Notificación email enviada a %s por alerta ALTA pk=%d tipo=%s.",
                medico.email,
                instance.pk,
                instance.tipo,
            )
        except Exception as exc:
            logger.error(
                "Error enviando email de alerta ALTA pk=%d: %s",
                instance.pk,
                exc,
            )

    transaction.on_commit(_enviar)
