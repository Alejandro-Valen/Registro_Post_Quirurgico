from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import render

from .models import MensajeContacto

_LIMITE_CONTACTO_HORA = 5   # envíos por IP por hora
_MAX_NOMBRE  = 100
_MAX_TELEFONO = 30
_MAX_MENSAJE = 2000


def _get_client_ip(request):
    # Usa REMOTE_ADDR: no es spoofeable por el cliente.
    # X-Forwarded-For se descarta porque el primer elemento lo pone el cliente
    # y puede ser falso. El proxy/balanceador de producción debe configurarse
    # para que REMOTE_ADDR refleje la IP real (Nginx: proxy_set_header).
    return request.META.get('REMOTE_ADDR', '')


def _rate_limit_contacto_excedido(ip):
    if not ip:
        return False
    clave = 'rl_contacto_{}'.format(ip.replace('.', '_').replace(':', '_'))
    try:
        conteo = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, 3600)
        conteo = 1
    return conteo > _LIMITE_CONTACTO_HORA


def _medico_destinatario_contacto():
    """Resuelve el médico configurado sin fallar abierto ante una mala config."""
    username = settings.MEDICO_CONTACTO_USERNAME.strip()
    if not username:
        return None
    return (
        get_user_model().objects
        .filter(username=username, is_active=True, is_staff=True)
        .first()
    )


# Mientras el médico no entregue sus datos reales, la landing muestra
# marcadores [entre corchetes] + un aviso de "boceto". Para pasar a producción
# final (datos reales cargados), poner MOSTRAR_AVISO_BOCETO = False.
MOSTRAR_AVISO_BOCETO = True


def index(request):
    return render(request, "home/index.html", {
        "seccion": "inicio",
        "mostrar_aviso_boceto": MOSTRAR_AVISO_BOCETO,
    })


def contacto(request):
    mensaje_enviado = False
    error_rate_limit = False

    if request.method == "POST":
        ip = _get_client_ip(request)
        if _rate_limit_contacto_excedido(ip):
            error_rate_limit = True
        else:
            nombre  = request.POST.get("nombre",  "").strip()[:_MAX_NOMBRE]
            telefono = request.POST.get("telefono", "").strip()[:_MAX_TELEFONO]
            mensaje = request.POST.get("mensaje",  "").strip()[:_MAX_MENSAJE]

            if nombre and telefono and mensaje:
                MensajeContacto.objects.create(
                    nombre=nombre,
                    telefono=telefono,
                    mensaje=mensaje,
                    medico_destinatario=_medico_destinatario_contacto(),
                )
                mensaje_enviado = True

    return render(
        request,
        "home/contacto.html",
        {
            "mensaje_enviado": mensaje_enviado,
            "error_rate_limit": error_rate_limit,
            "seccion": "contacto",
            "mostrar_aviso_boceto": MOSTRAR_AVISO_BOCETO,
        },
    )
