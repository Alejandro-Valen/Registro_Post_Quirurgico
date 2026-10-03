"""
WSGI config for Registro_Post_Quirurgico project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# SEC-04 (02/10/2026): este archivo solo lo usa el servidor de producción
# (gunicorn, en el Dockerfile y en nixpacks.toml). Si a un despliegue le falta
# DJANGO_SETTINGS_MODULE, tiene que arrancar con PRODUCCIÓN, que se detiene si
# le falta algo, y no con la configuración de desarrollo, que arrancaba sin
# HSTS, sin redirección HTTPS, sin cookies seguras y sin CSP sin decir nada.
# `manage.py` sigue eligiendo la base: `runserver` y la suite no cambian.
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE', 'Registro_Post_Quirurgico.settings_production'
)

application = get_wsgi_application()
