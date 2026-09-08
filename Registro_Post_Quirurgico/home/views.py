import ipaddress
import logging
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import MensajeContacto

logger = logging.getLogger(__name__)

_LIMITE_CONTACTO_HORA = 5   # envíos por IP por hora
_MAX_NOMBRE  = 100
_MAX_TELEFONO = 30
_MAX_MENSAJE = 2000
_RAILWAY_EDGE_RE = re.compile(r'^railway/[a-z0-9-]+$')


def _get_client_ip(request):
    remote_addr = request.META.get('REMOTE_ADDR', '')
    if not getattr(settings, 'TRUST_RAILWAY_PROXY', False):
        return remote_addr

    railway_edge = request.META.get('HTTP_X_RAILWAY_EDGE', '')
    real_ip = request.META.get('HTTP_X_REAL_IP', '')
    if not _RAILWAY_EDGE_RE.fullmatch(railway_edge):
        return remote_addr

    try:
        return str(ipaddress.ip_address(real_ip))
    except ValueError:
        return remote_addr


def _rate_limit_contacto_excedido(ip):
    """True si la IP superó el límite de envíos por hora.

    Falla CERRADO ante una caída del cache (decisión D2): el formulario es la
    única puerta sin firma —cualquiera en internet puede tocarla— y el rate
    limit es su único control. Si el cache no responde, se trata como límite
    excedido para no dejar el formulario abierto al abuso.
    """
    if not ip:
        return False
    clave = 'rl_contacto_{}'.format(ip.replace('.', '_').replace(':', '_'))
    try:
        conteo = cache.incr(clave)
    except ValueError:
        # El cache respondió "no existe la clave": primer envío de la ventana.
        cache.set(clave, 1, 3600)
        conteo = 1
    except Exception:  # noqa: BLE001  (a propósito: cualquier fallo del cache degrada a fallo CERRADO)
        logger.warning(
            'Rate limit del formulario degradado: el cache no responde; se '
            'bloquea el envío (fallo cerrado).'
        )
        return True
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


def politica_datos(request):
    """Politica de tratamiento de datos personales (Ley 1581/2012).

    BORRADOR. Existe porque la casilla de autorizacion del formulario tiene
    que enlazar a algun sitio: pedir permiso sin decir para que ni ante quien
    no es autorizacion informada.

    Lo que le falta para ser valida son datos que el proyecto todavia no
    tiene: responsable del tratamiento identificado, direccion, canal para
    ejercer los derechos y plazo maximo de retencion. Son los mismos
    corchetes sin llenar de la decision P-12 y del formato de
    consentimiento. NO se inventan: la plantilla los muestra como pendientes
    y el aviso de boceto lo deja claro.
    """
    return render(request, "home/politica_datos.html", {
        "seccion": "politica",
        "mostrar_aviso_boceto": MOSTRAR_AVISO_BOCETO,
    })

def salud(request):
    """Health check para monitoreo externo (D2, punto 5).

    Verifica base de datos y cache. Devuelve 200 si ambos responden, 503 si
    alguno falla. El cuerpo NO lleva detalle: quien consulta el endpoint no
    debe conocer la topología interna ni qué componente falló.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        cache.set('salud_check', '1', 10)
        if cache.get('salud_check') != '1':
            raise RuntimeError('cache no confirmó la escritura')
    except Exception:  # noqa: BLE001  (un health check DEBE atrapar todo: cualquier fallo es un 503)
        logger.warning('Health check /salud/ falló: base de datos o cache no responde.')
        return HttpResponse(status=503)
    return HttpResponse(status=200)


def index(request):
    return render(request, "home/index.html", {
        "seccion": "inicio",
        "mostrar_aviso_boceto": MOSTRAR_AVISO_BOCETO,
    })


def contacto(request):
    mensaje_enviado = False
    error_rate_limit = False
    error_autorizacion = False

    if request.method == "POST":
        ip = _get_client_ip(request)
        if _rate_limit_contacto_excedido(ip):
            error_rate_limit = True
        else:
            nombre  = request.POST.get("nombre",  "").strip()[:_MAX_NOMBRE]
            telefono = request.POST.get("telefono", "").strip()[:_MAX_TELEFONO]
            mensaje = request.POST.get("mensaje",  "").strip()[:_MAX_MENSAJE]
            # SEC-03 / decisión D23 — el artículo 6 de la Ley 1581/2012 exige
            # autorización EXPLÍCITA para datos sensibles, y este formulario
            # recibe datos de salud por más que se pida no enviarlos.
            #
            # La casilla se comprueba en el SERVIDOR y no solo con `required`
            # en el HTML: un `required` se salta con un POST directo, que es
            # exactamente como se reprodujo el hallazgo el 08/09/2026.
            autorizo = request.POST.get("autorizacion_datos") in ("1", "on", "true")

            if not autorizo:
                error_autorizacion = True
            elif nombre and telefono and mensaje:
                MensajeContacto.objects.create(
                    nombre=nombre,
                    telefono=telefono,
                    mensaje=mensaje,
                    autorizacion_datos=True,
                    # La autorización hay que poder demostrarla después, no
                    # solo recogerla: se guarda cuándo se dio.
                    fecha_autorizacion=timezone.now(),
                    medico_destinatario=_medico_destinatario_contacto(),
                )
                mensaje_enviado = True

    return render(
        request,
        "home/contacto.html",
        {
            "mensaje_enviado": mensaje_enviado,
            "error_rate_limit": error_rate_limit,
            "error_autorizacion": error_autorizacion,
            "seccion": "contacto",
            "mostrar_aviso_boceto": MOSTRAR_AVISO_BOCETO,
        },
    )
