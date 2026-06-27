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

from .models import Alerta

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alerta)
def notificar_alerta_alta(sender, instance, created, **kwargs):
    """Envía email al médico responsable si la alerta nueva es de severidad ALTA."""
    if not created or instance.severidad != 'ALTA':
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
        asunto = (
            f"[ALERTA ALTA] {instance.get_tipo_display()} — "
            f"{instance.paciente.nombre_completo}"
        )
        cuerpo = (
            f"Estimado/a {medico.get_full_name() or medico.username},\n\n"
            f"Se ha generado una alerta de severidad ALTA para su paciente:\n\n"
            f"  Paciente: {instance.paciente.nombre_completo}\n"
            f"  Tipo: {instance.get_tipo_display()}\n"
            f"  Severidad: {instance.get_severidad_display()}\n"
            f"  Fecha: {instance.fecha_alerta.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Detalle: {instance.mensaje}\n\n"
            f"Por favor revise el dashboard y contacte al paciente si es necesario.\n\n"
            f"— Sistema de Monitoreo Posquirúrgico"
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
