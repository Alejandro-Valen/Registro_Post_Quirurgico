"""
Configuración de producción — extiende settings.py con directivas de seguridad HTTPS.

Uso:
    DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_production

Variables de entorno OBLIGATORIAS en producción (además de las del .env base):
    DJANGO_ALLOWED_HOSTS   — dominio real, ej: "midominio.com"
    CSRF_TRUSTED_ORIGINS   — origen HTTPS, ej: "https://midominio.com"
    SECRET_KEY             — clave larga y aleatoria (no reutilizar la de desarrollo)
    EMAIL_HOST_USER        — cuenta de Gmail del proyecto (Sprint 5, Bloque 5)
    EMAIL_HOST_PASSWORD    — contraseña de aplicación de esa cuenta (NUNCA la normal)

B1: configuración de producción con cabeceras HTTPS, cookies seguras y HSTS.
A6: DEBUG hardcodeado a False — nunca True en producción.
"""
from .settings import *  # noqa: F401, F403
from decouple import config, Csv

# A6: DEBUG=False siempre en producción. Stacktrace nunca llega al cliente.
DEBUG = False

# B1: cabeceras de seguridad HTTPS
SESSION_COOKIE_SECURE   = True
CSRF_COOKIE_SECURE      = True
SECURE_SSL_REDIRECT     = True
SECURE_HSTS_SECONDS     = 31536000   # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD     = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS         = 'DENY'

# B1: CSRF origins explícitos (Twilio + dominio propio).
# Ejemplo en .env de producción: CSRF_TRUSTED_ORIGINS=https://midominio.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# B5: URL del admin en producción debe diferir de la de desarrollo (ver urls.py).
# Se documenta aquí para recordatorio; el cambio real está en urls.py.

# Cache compartido entre workers (A3/A5/C7 dependen de esto).
# En producción se REQUIERE Redis o Memcached — el backend de memoria de
# Django (default) no comparte estado entre procesos/workers y haría que
# la idempotencia por SID y el rate limiting fallaran silenciosamente.
# Variable de entorno: REDIS_URL=redis://:password@host:6379/1
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
    }
}

# Sprint 5, Bloque 5 — SMTP real para el email de alerta ALTA (signals.py).
# En desarrollo (settings_local.py) el backend sigue siendo consola — esto
# solo aplica cuando corre con DJANGO_SETTINGS_MODULE=...settings_production.
# EMAIL_HOST_USER/EMAIL_HOST_PASSWORD no tienen default: si faltan en el
# .env de producción, decouple falla fuerte (fail-clear) en vez de arrancar
# el servidor sin poder enviar correo.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
