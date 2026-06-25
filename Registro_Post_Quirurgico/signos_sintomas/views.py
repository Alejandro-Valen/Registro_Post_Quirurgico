from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from .bot import procesar_mensaje

# --- Constantes de protección del webhook ---
_LIMITE_MENSAJES_HORA = 20          # A5: máx. mensajes por número/hora
_TTL_SID_PROCESADO   = 300          # A3: ventana de idempotencia (5 min)


@sensitive_post_parameters('From', 'Body')   # B2: oculta PII en error reports
@csrf_exempt          # Twilio no envía token CSRF; exento SOLO en esta vista.
@require_POST         # El webhook solo acepta POST (GET -> 405).
def webhook_whatsapp(request):
    """Recibe un mensaje de WhatsApp vía Twilio y responde en TwiML."""
    if not _firma_twilio_valida(request):
        return HttpResponseForbidden()

    sid      = request.POST.get('MessageSid') or request.POST.get('SmsMessageSid', '')
    telefono = request.POST.get('From', '')
    texto    = request.POST.get('Body', '')[:500]

    # A3: idempotencia — rechazar si este SID ya fue procesado.
    if sid and _sid_ya_procesado(sid):
        return HttpResponse(str(MessagingResponse()), content_type='application/xml')

    # A5: rate limiting por número de teléfono.
    if _rate_limit_excedido(telefono):
        return HttpResponse(str(MessagingResponse()), content_type='application/xml')

    respuesta = procesar_mensaje(telefono, texto)

    # A3: marcar SID como procesado para evitar reintentos duplicados.
    if sid:
        cache.set(f'twilio_sid_{sid}', True, _TTL_SID_PROCESADO)

    twiml = MessagingResponse()
    twiml.message(respuesta)
    return HttpResponse(str(twiml), content_type='application/xml')


def _sid_ya_procesado(sid):
    """A3: True si este MessageSid ya fue procesado en la ventana de idempotencia."""
    return bool(cache.get(f'twilio_sid_{sid}'))


def _rate_limit_excedido(telefono):
    """A5: True si el número superó el límite de mensajes por hora."""
    if not telefono:
        return False
    clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
    try:
        conteo = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, 3600)
        conteo = 1
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
