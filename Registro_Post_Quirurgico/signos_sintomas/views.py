import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from .bot import procesar_mensaje
from .models import RecepcionWebhookTwilio

logger = logging.getLogger(__name__)

# --- Constantes de protección del webhook ---
# El límite atrapa un bucle (cientos de mensajes/minuto), no vigila a un humano:
# un cuestionario completo son ~11 mensajes y un paciente confundido no pasa de
# ~40 en una hora. Con 60 el bucle se corta igual y el paciente nunca toca el
# techo (decisión D2, corrección post-auditoría).
_LIMITE_MENSAJES_HORA = 60
_MAX_EDAD_PROCESANDO = timedelta(minutes=2)
_MSG_RATE_LIMIT = (
    'Recibimos varios mensajes en poco tiempo y pausamos temporalmente el '
    'cuestionario. Inténtalo de nuevo más tarde. Si necesitas atención '
    'médica inmediata, comunícate con tu médico o con el servicio de '
    'urgencias.'
)


@sensitive_post_parameters('From', 'Body')   # B2: oculta PII en error reports
@csrf_exempt          # Twilio no envía token CSRF; exento SOLO en esta vista.
@require_POST         # El webhook solo acepta POST (GET -> 405).
def webhook_whatsapp(request):
    """Recibe un mensaje de WhatsApp vía Twilio y responde en TwiML."""
    if not _firma_twilio_valida(request):
        return HttpResponseForbidden()

    sid = request.POST.get('MessageSid') or request.POST.get('SmsMessageSid', '')
    if not _sid_twilio_valido(sid):
        return HttpResponse(status=400)

    telefono = request.POST.get('From', '')
    texto = request.POST.get('Body', '')[:500]
    token_idempotencia = request.headers.get('I-Twilio-Idempotency-Token', '')[:128]

    # El rate limit se verifica ANTES de reclamar el SID (decisión D2): un
    # mensaje limitado no debe dejar una fila colgada en RecepcionWebhookTwilio.
    if _rate_limit_excedido(telefono):
        return _respuesta_twiml(_MSG_RATE_LIMIT)

    recepcion, debe_procesar = _reclamar_recepcion_webhook(
        sid,
        token_idempotencia,
    )
    if not debe_procesar:
        if recepcion.estado == RecepcionWebhookTwilio.ESTADO_COMPLETADO:
            return _respuesta_twiml_vacia()
        respuesta = HttpResponse(status=503)
        respuesta['Retry-After'] = '30'
        return respuesta

    try:
        with transaction.atomic():
            recepcion = (
                RecepcionWebhookTwilio.objects.select_for_update()
                .get(pk=recepcion.pk)
            )
            respuesta = procesar_mensaje(telefono, texto)
            _marcar_recepcion_completada(recepcion)
    except Exception:
        RecepcionWebhookTwilio.objects.filter(
            pk=recepcion.pk,
            estado=RecepcionWebhookTwilio.ESTADO_PROCESANDO,
        ).update(
            estado=RecepcionWebhookTwilio.ESTADO_ERROR,
            fecha_actualizacion=timezone.now(),
        )
        raise

    return _respuesta_twiml(respuesta)


def _sid_twilio_valido(sid):
    """Acepta los identificadores alfanuméricos usados por Twilio."""
    return bool(sid and len(sid) <= 64 and re.fullmatch(r'[A-Za-z0-9]+', sid))


def _reclamar_recepcion_webhook(sid, token_idempotencia):
    """Obtiene el derecho exclusivo a procesar un SID.

    Un proceso caído puede dejar la fila en PROCESANDO; pasado el margen se
    permite reclamarla de nuevo. Las actualizaciones condicionales impiden que
    dos workers recuperen simultáneamente el mismo mensaje.
    """
    recepcion, creada = RecepcionWebhookTwilio.objects.get_or_create(
        message_sid=sid,
        defaults={'idempotency_token': token_idempotencia},
    )
    if creada:
        return recepcion, True
    if recepcion.estado == RecepcionWebhookTwilio.ESTADO_COMPLETADO:
        return recepcion, False

    filtros = {
        'pk': recepcion.pk,
        'estado': recepcion.estado,
    }
    if recepcion.estado == RecepcionWebhookTwilio.ESTADO_PROCESANDO:
        filtros['fecha_actualizacion__lte'] = timezone.now() - _MAX_EDAD_PROCESANDO

    actualizada = RecepcionWebhookTwilio.objects.filter(**filtros).update(
        estado=RecepcionWebhookTwilio.ESTADO_PROCESANDO,
        intentos=F('intentos') + 1,
        idempotency_token=token_idempotencia,
        fecha_actualizacion=timezone.now(),
    )
    if actualizada:
        recepcion.refresh_from_db()
        return recepcion, True

    recepcion.refresh_from_db()
    return recepcion, False


def _marcar_recepcion_completada(recepcion):
    RecepcionWebhookTwilio.objects.filter(pk=recepcion.pk).update(
        estado=RecepcionWebhookTwilio.ESTADO_COMPLETADO,
        fecha_actualizacion=timezone.now(),
    )


def _respuesta_twiml_vacia():
    return _respuesta_twiml()


def _respuesta_twiml(mensaje=None):
    twiml = MessagingResponse()
    if mensaje:
        twiml.message(mensaje)
    return HttpResponse(
        str(twiml),
        content_type='application/xml',
    )


def _rate_limit_excedido(telefono):
    """A5: True si el número superó el límite de mensajes por hora.

    Falla ABIERTO ante una caída del cache (decisión D2): el webhook es la ruta
    del paciente y la firma de Twilio ya protege la puerta, así que un fallo del
    cache no debe dejar al paciente sin respuesta. Se registra la degradación
    para el Arquitecto (no para el médico: es ruido de infraestructura).
    """
    if not telefono:
        return False
    clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
    try:
        conteo = cache.incr(clave)
    except ValueError:
        # El cache respondió "no existe la clave": primer mensaje de la ventana.
        cache.set(clave, 1, 3600)
        conteo = 1
    except Exception:  # noqa: BLE001  (a propósito: se degrada a fallo ABIERTO; la firma de Twilio sigue siendo la cerradura)
        logger.warning(
            'Rate limit del webhook degradado: el cache no responde; se procesa '
            'el mensaje (fallo abierto).'
        )
        return False
    return conteo > _LIMITE_MENSAJES_HORA


def _firma_twilio_valida(request):
    """Valida la firma X-Twilio-Signature.

    Fail-safe: si TWILIO_VALIDATE_SIGNATURE no está definida en .env, settings la
    deja en True, así que la validación está activa por defecto. Solo se omite si
    alguien la desactiva explícitamente con TWILIO_VALIDATE_SIGNATURE=False.

    Fail-clear: si la validación está activa pero falta el token, se levanta un
    error de configuración explícito en vez de saltarse la validación (fallar
    abierto) o devolver un 403 engañoso.
    """
    if not settings.TWILIO_VALIDATE_SIGNATURE:
        return True  # Desactivada a propósito (pruebas locales).

    if not settings.TWILIO_AUTH_TOKEN:
        raise ImproperlyConfigured(
            "TWILIO_VALIDATE_SIGNATURE está activo pero TWILIO_AUTH_TOKEN no está "
            "definido en .env. Configura el token de Twilio, o solo para pruebas "
            "locales agrega TWILIO_VALIDATE_SIGNATURE=False en tu .env."
        )

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    url = request.build_absolute_uri()
    firma = request.headers.get('X-Twilio-Signature', '')
    return validator.validate(url, request.POST, firma)
