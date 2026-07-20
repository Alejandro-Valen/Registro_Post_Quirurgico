"""Señales de dominio de signos_sintomas."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Alerta, NotificacionAlerta

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alerta)
def notificar_alerta_alta(sender, instance, created, **kwargs):
    """Encola una notificación cuando la alerta alcanza severidad ALTA.

    La fila se crea dentro de la misma transacción que guarda la alerta. No se
    realiza ninguna conexión de red en el webhook.
    """
    # Los seeds marcan sus pacientes con una cédula reservada. Excluirlos en
    # la frontera de dominio evita correos demo incluso si se agregan nuevos
    # comandos de poblado en el futuro.
    if (instance.paciente.cedula or '').startswith('DEMO-'):
        return
    if instance.severidad != 'ALTA':
        return
    escalo_a_alta = getattr(instance, '_escalo_a_alta', False)
    if not (created or escalo_a_alta):
        return

    medico = instance.paciente.medico_responsable
    destinatario = medico.email if medico and medico.email else ''
    if not destinatario:
        logger.warning(
            "Alerta ALTA pk=%d sin médico responsable o sin email; "
            "la notificación permanecerá pendiente.",
            instance.pk,
        )

    _, creada = NotificacionAlerta.objects.get_or_create(
        alerta=instance,
        defaults={'destinatario': destinatario},
    )
    if creada:
        logger.info('Notificación encolada para alerta ALTA pk=%d.', instance.pk)
