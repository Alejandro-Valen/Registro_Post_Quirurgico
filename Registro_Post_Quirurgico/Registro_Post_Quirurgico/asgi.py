"""
ASGI config for Registro_Post_Quirurgico project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# SEC-04 (02/10/2026): igual que wsgi.py. Un servidor que arranca sin
# DJANGO_SETTINGS_MODULE elige producción, que falla cerrado, y no desarrollo.
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE', 'Registro_Post_Quirurgico.settings_production'
)

application = get_asgi_application()
