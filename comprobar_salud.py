"""HEALTHCHECK del contenedor (SEC-13): ¿responde /salud/ con 200?

Lo ejecuta Docker dentro del contenedor cada cierto tiempo. Sale con 0 si la
aplicación responde sano y con 1 en cualquier otro caso: un 503 (base de datos
o cache caídos), un 301, un 400 o que gunicorn no conteste.

Por qué un script y no `curl`: `python:3.13-slim` no trae curl, y añadirlo
solo para esto es un paquete más que mantener al día. Usa únicamente la
biblioteca estándar, así que no arranca Django ni importa el proyecto.

El encabezado Host: producción no admite `localhost` en ALLOWED_HOSTS, y sin un
host permitido Django respondería 400. Se usa el primero de ALLOWED_HOSTS. Un
comodín `.dominio` se manda sin el punto, que Django acepta como el propio
dominio.

Las redirecciones NO se siguen: un 301 hacia HTTPS significaría que /salud/
dejó de estar exenta de SECURE_SSL_REDIRECT, y eso debe verse como fallo.
"""
import os
import sys
import urllib.error
import urllib.request


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _host():
    hosts = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',')]
    hosts = [h for h in hosts if h and h != '*']
    return hosts[0].lstrip('.') if hosts else 'localhost'


def main():
    puerto = os.environ.get('PORT', '8000')
    peticion = urllib.request.Request(
        f'http://127.0.0.1:{puerto}/salud/', headers={'Host': _host()})
    abridor = urllib.request.build_opener(_SinRedirecciones)
    try:
        with abridor.open(peticion, timeout=4) as respuesta:
            return 0 if respuesta.status == 200 else 1
    except (urllib.error.URLError, OSError):
        return 1


if __name__ == '__main__':
    sys.exit(main())
