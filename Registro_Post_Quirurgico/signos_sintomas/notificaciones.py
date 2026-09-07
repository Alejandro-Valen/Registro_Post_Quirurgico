"""Procesamiento durable de notificaciones clínicas por correo."""

from datetime import timedelta

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import NotificacionAlerta

# Tope de reintentos (D6). Con el backoff (5, 15, 45, 135 min, luego cada 6 h),
# 10 intentos son ≈39 horas: generoso para un fallo transitorio. Si a las 39 h
# sigue fallando, la causa es configuración (API key, destinatario) y ninguna
# cantidad de reintentos la resuelve. Como efecto colateral, el tope elimina el
# riesgo de desbordamiento del contador.
MAX_INTENTOS_NOTIFICACION = 10


class DestinatarioNoConfigurado(Exception):
    pass


class EntregaEmailNoConfirmada(Exception):
    pass


class ProveedorEmailNoConfigurado(Exception):
    pass


def _contenido_seguro(notificacion):
    """Construye un aviso sin datos identificables ni detalle clínico."""
    asunto = 'Alerta clínica alta pendiente de atención'
    lineas = [
        'Se registró una alerta clínica de severidad alta que requiere revisión.',
        '',
        f'Referencia interna: alerta #{notificacion.alerta_id}',
        'Acceda al panel médico con sus credenciales para consultar el caso.',
    ]
    panel_url = getattr(settings, 'PANEL_MEDICO_URL', '').strip()
    if panel_url:
        lineas.extend(['', panel_url])
    lineas.extend([
        '',
        'Este es un mensaje automático. No responda a este correo.',
    ])
    return asunto, '\n'.join(lineas)


def _minutos_reintento(intentos):
    """Backoff 5, 15, 45, 135 y luego máximo cada 6 horas."""
    return min(5 * (3 ** max(intentos - 1, 0)), 360)


def _enviar_por_resend(notificacion, asunto, cuerpo):
    api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
    remitente = getattr(settings, 'RESEND_FROM_EMAIL', '').strip()
    if not api_key or not remitente:
        raise ProveedorEmailNoConfigurado

    respuesta = requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Idempotency-Key': f'alerta-alta-{notificacion.alerta_id}',
        },
        json={
            'from': remitente,
            'to': [notificacion.destinatario],
            'subject': asunto,
            'text': cuerpo,
        },
        timeout=getattr(settings, 'EMAIL_TIMEOUT', 10),
    )
    respuesta.raise_for_status()
    if not respuesta.json().get('id'):
        raise EntregaEmailNoConfirmada


def _entregar_email(notificacion, asunto, cuerpo):
    proveedor = getattr(settings, 'EMAIL_DELIVERY_PROVIDER', 'django').strip().lower()
    if proveedor == 'resend':
        _enviar_por_resend(notificacion, asunto, cuerpo)
        return
    if proveedor != 'django':
        raise ProveedorEmailNoConfigurado

    enviados = send_mail(
        subject=asunto,
        message=cuerpo,
        from_email=None,
        recipient_list=[notificacion.destinatario],
        fail_silently=False,
    )
    if enviados != 1:
        raise EntregaEmailNoConfirmada


def _enviar(notificacion):
    if not notificacion.destinatario:
        medico = notificacion.alerta.paciente.medico_responsable
        if medico and medico.email:
            notificacion.destinatario = medico.email
            notificacion.save(update_fields=['destinatario'])
        else:
            raise DestinatarioNoConfigurado

    asunto, cuerpo = _contenido_seguro(notificacion)
    _entregar_email(notificacion, asunto, cuerpo)


def procesar_notificaciones_pendientes(limite=50):
    """Envía hasta ``limite`` filas vencidas y devuelve un resumen.

    Cada envío mantiene bloqueada exclusivamente su fila. Si el proceso muere
    durante la llamada externa, la transacción revierte y la fila sigue
    pendiente. ``skip_locked`` evita duplicados si dos workers coinciden.
    """
    ahora = timezone.now()
    candidatos = list(
        NotificacionAlerta.objects.filter(
            estado=NotificacionAlerta.ESTADO_PENDIENTE,
            proximo_intento__lte=ahora,
        )
        .order_by('proximo_intento', 'pk')
        .values_list('pk', flat=True)[:limite]
    )

    enviadas = 0
    errores = 0
    for notificacion_pk in candidatos:
        with transaction.atomic():
            notificacion = (
                # of=('self',): el FOR UPDATE bloquea SOLO la fila de la
                # notificación, no las de alerta/paciente que trae el JOIN
                # (hallazgo 2). Así la llamada de red del envío no mantiene
                # bloqueadas filas que el webhook del paciente necesita.
                NotificacionAlerta.objects.select_for_update(
                    skip_locked=True, of=('self',),
                )
                # medico_responsable es nullable. Incluirlo en select_related
                # produciría un LEFT JOIN que PostgreSQL no permite bloquear
                # con FOR UPDATE.
                .select_related('alerta__paciente')
                .filter(
                    pk=notificacion_pk,
                    estado=NotificacionAlerta.ESTADO_PENDIENTE,
                    proximo_intento__lte=timezone.now(),
                )
                .first()
            )
            if notificacion is None:
                continue

            notificacion.intentos += 1
            notificacion.fecha_ultimo_intento = timezone.now()
            try:
                _enviar(notificacion)
            except Exception as exc:  # noqa: BLE001  (cualquier fallo de envío entra al backoff; D6)
                errores += 1
                notificacion.ultimo_error = type(exc).__name__[:100]
                if notificacion.intentos >= MAX_INTENTOS_NOTIFICACION:
                    # Se agotaron los reintentos: estado terminal visible (D6).
                    notificacion.estado = NotificacionAlerta.ESTADO_FALLIDA
                    notificacion.save(update_fields=[
                        'estado',
                        'intentos',
                        'fecha_ultimo_intento',
                        'ultimo_error',
                    ])
                else:
                    notificacion.proximo_intento = timezone.now() + timedelta(
                        minutes=_minutos_reintento(notificacion.intentos)
                    )
                    notificacion.save(update_fields=[
                        'intentos',
                        'fecha_ultimo_intento',
                        'ultimo_error',
                        'proximo_intento',
                    ])
            else:
                enviadas += 1
                notificacion.estado = NotificacionAlerta.ESTADO_ENVIADA
                notificacion.fecha_envio = timezone.now()
                notificacion.ultimo_error = ''
                notificacion.save(update_fields=[
                    'estado',
                    'intentos',
                    'fecha_ultimo_intento',
                    'fecha_envio',
                    'ultimo_error',
                ])

    return {
        'candidatas': len(candidatos),
        'enviadas': enviadas,
        'errores': errores,
    }
