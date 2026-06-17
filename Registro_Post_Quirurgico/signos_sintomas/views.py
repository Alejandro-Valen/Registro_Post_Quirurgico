from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from .bot import procesar_mensaje


@csrf_exempt          # Twilio no envía token CSRF; exento SOLO en esta vista.
@require_POST         # El webhook solo acepta POST (GET -> 405).
def webhook_whatsapp(request):
    """Recibe un mensaje de WhatsApp vía Twilio y responde en TwiML."""
    if not _firma_twilio_valida(request):
        return HttpResponseForbidden("Firma de Twilio inválida")

    telefono = request.POST.get('From', '')
    texto = request.POST.get('Body', '')

    respuesta = procesar_mensaje(telefono, texto)

    twiml = MessagingResponse()
    twiml.message(respuesta)
    return HttpResponse(str(twiml), content_type='application/xml')


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
