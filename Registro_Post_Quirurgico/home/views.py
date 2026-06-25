from django.core.cache import cache
from django.shortcuts import render

from .models import MensajeContacto

_LIMITE_CONTACTO_HORA = 5   # envíos por IP por hora
_MAX_NOMBRE  = 100
_MAX_TELEFONO = 30
_MAX_MENSAJE = 2000


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
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


def index(request):
    return render(request, "home/index.html")


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
                )
                mensaje_enviado = True

    return render(
        request,
        "home/contacto.html",
        {"mensaje_enviado": mensaje_enviado, "error_rate_limit": error_rate_limit},
    )
