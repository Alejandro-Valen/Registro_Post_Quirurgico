"""
Configuración de desarrollo local — importa el base y ajusta para máquina local.

Uso:
    DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_local

Equivalente a la configuración actual del .env con DEBUG=True.
NO usar con credenciales reales de Twilio activas ni con ngrok expuesto
(A6: DEBUG=True muestra stacktrace con variables locales al cliente HTTP).
"""
from .settings import *  # noqa: F401, F403

DEBUG = True

# En desarrollo, localhost siempre permitido aunque .env sobreescriba ALLOWED_HOSTS.
ALLOWED_HOSTS += ['localhost', '127.0.0.1']

# Email: consola en desarrollo — las alertas ALTA se imprimen, no se envían por SMTP.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'sistema-monitoreo@local.dev'
