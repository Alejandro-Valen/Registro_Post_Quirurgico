"""D29 (15/10/2026) — la sesión del panel caduca por inactividad.

SEC-15 dejó la sesión en 8 horas desde el ingreso y cerrada al cerrar el
navegador. Faltaba lo que pasa en medio: un médico que deja el panel abierto y
se levanta deja las fichas a la vista de quien se siente después, durante
horas. Decisión del Arquitecto: 30 minutos sin uso cierran la sesión.

Lo delicado: guardar la última actividad en cada petición MODIFICA la sesión, y
Django renueva su caducidad cada vez que la guarda. Sin un tope propio, las 8
horas de SEC-15 pasarían a contar desde el último clic y un médico activo no
saldría nunca. Por eso aquí se vigilan los dos límites, cada uno con su marca:

- `inicio`: cuándo entró. Pasadas `SESSION_COOKIE_AGE` (8 h), fuera.
- `ultima_actividad`: el último clic. Pasados `SESION_INACTIVIDAD_MAXIMA`, fuera.

Las dos se ponen al iniciar sesión (señal `user_logged_in`). Una sesión que no
las tenga —abierta antes de este cambio— se adopta como si empezara ahora: no
se expulsa a nadie por un dato que no existía.
"""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout

CLAVE_INICIO = 'panel_inicio'
CLAVE_ULTIMA_ACTIVIDAD = 'panel_ultima_actividad'
MSG_CADUCADA = (
    'Tu sesión se cerró tras 30 minutos sin uso, para que nadie más vea las '
    'fichas en este equipo. Vuelve a entrar para seguir.'
)
MSG_TOPE = (
    'Tu sesión llegó a su tope de 8 horas y se cerró. Vuelve a entrar para seguir.'
)


def _ahora():
    # `time.time()` y no `timezone.now()`: las marcas viven en la sesión, que se
    # serializa a JSON, y un número se guarda sin conversiones. Las pruebas
    # mueven este reloj con freezegun igual que el de Django.
    return time.time()


def marcar_inicio(sender, request, user, **kwargs):
    """Receptor de `user_logged_in`: las dos marcas nacen con la sesión."""
    ahora = _ahora()
    request.session[CLAVE_INICIO] = ahora
    request.session[CLAVE_ULTIMA_ACTIVIDAD] = ahora


class CaducidadPorInactividadMiddleware:
    """Va después de `AuthenticationMiddleware` (necesita `request.user`) y de
    `MessageMiddleware` (deja un aviso de por qué se cerró la sesión)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            self._vigilar(request)
        return self.get_response(request)

    def _vigilar(self, request):
        ahora = _ahora()
        sesion = request.session
        inicio = sesion.get(CLAVE_INICIO)
        ultima = sesion.get(CLAVE_ULTIMA_ACTIVIDAD)
        if inicio is None or ultima is None:
            sesion[CLAVE_INICIO] = inicio or ahora
            sesion[CLAVE_ULTIMA_ACTIVIDAD] = ahora
            return

        if ahora - inicio > settings.SESSION_COOKIE_AGE:
            self._cerrar(request, MSG_TOPE)
        elif ahora - ultima > settings.SESION_INACTIVIDAD_MAXIMA:
            self._cerrar(request, MSG_CADUCADA)
        else:
            sesion[CLAVE_ULTIMA_ACTIVIDAD] = ahora

    @staticmethod
    def _cerrar(request, aviso):
        logout(request)   # borra la sesión del servidor, no solo la cookie
        messages.info(request, aviso)
