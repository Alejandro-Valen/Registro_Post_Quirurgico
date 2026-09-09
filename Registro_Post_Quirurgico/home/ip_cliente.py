"""Cómo se averigua la IP real de quien hace una petición.

**Por qué vive en su propio módulo desde el 09/09/2026.** Esta función la usan
ahora dos defensas distintas:

1. El **rate limit del formulario público** (`home/views.py`), que limita los
   envíos por IP y por hora.
2. El **bloqueo de intentos de acceso** al panel del médico
   (`django-axes`, vía `AXES_CLIENT_IP_CALLABLE`), desde la corrección del
   hallazgo **SEC-02**.

Estaba dentro de `views.py` con un guion bajo delante, y un nombre privado usado
por dos subsistemas es un nombre que miente. Pero lo que de verdad importa no es
la estética: **si las dos defensas resolvieran la IP de formas distintas, una de
las dos estaría equivocada y nadie lo notaría.** Una sola función lo hace
imposible.

LA REGLA, Y POR QUÉ ES ASÍ
===========================

Una cabecera HTTP la puede escribir cualquiera. `X-Real-IP` solo se cree cuando
se cumplen las dos condiciones a la vez:

- `TRUST_RAILWAY_PROXY` está activado **en la configuración**, es decir, alguien
  declaró que esta instancia vive detrás del edge de Railway; y
- la petición trae `X-Railway-Edge` con el formato que pone ese edge.

Si falta cualquiera de las dos, o si `X-Real-IP` no es una IP válida, se usa
`REMOTE_ADDR`, que es la que ve el socket y nadie puede falsificar.

**El valor por defecto de `TRUST_RAILWAY_PROXY` es `False` a propósito**, y esa
decisión ya costó un susto: hasta el 31/07/2026 la prueba que la protegía no
fijaba el valor y **leía el del entorno de quien corriera la suite**. Pasaba en
verde solo porque el `.env` de desarrollo traía `False`, y cayó en la primera
corrida de la CI. La guarda de una decisión de seguridad no puede depender de un
archivo que no está en el repositorio.
"""

import ipaddress
import re

from django.conf import settings

_RAILWAY_EDGE_RE = re.compile(r'^railway/[a-z0-9-]+$')


def _get_client_ip(request):
    """IP del cliente, sin creerse ninguna cabecera que no esté respaldada.

    Conserva el nombre con guion bajo con el que nació para no romper los
    documentos y las pruebas que ya lo citan.
    """
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
