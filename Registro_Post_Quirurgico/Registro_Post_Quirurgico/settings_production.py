"""
Configuración de producción — extiende settings.py con directivas de seguridad HTTPS.

Uso:
    DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_production

Variables de entorno OBLIGATORIAS en producción (además de las del .env base):
    ALLOWED_HOSTS          — dominio(s) real(es), separados por coma. Lo lee
                             settings.py base con config('ALLOWED_HOSTS'); NO es
                             'DJANGO_ALLOWED_HOSTS'. Ej: "midominio.up.railway.app"
    CSRF_TRUSTED_ORIGINS   — origen HTTPS, ej: "https://midominio.up.railway.app"
    SECRET_KEY             — clave larga y aleatoria (no reutilizar la de desarrollo)
    DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT — credenciales de PostgreSQL
    REDIS_URL              — cache compartido (ver CACHES abajo)
    TRUST_RAILWAY_PROXY    — True solo cuando el tráfico entra por Railway
    EMAIL_DELIVERY_PROVIDER — "resend" para entrega por HTTPS en Railway
    RESEND_API_KEY         — clave de API del proyecto en Resend
    RESEND_FROM_EMAIL      — remitente verificado o onboarding@resend.dev
    EMAIL_HOST_USER/PASSWORD — obligatorias solo con proveedor "django"

B1: configuración de producción con cabeceras HTTPS, cookies seguras y HSTS.
A6: DEBUG hardcodeado a False — nunca True en producción.
"""
from .settings import *  # noqa: F401, F403
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

# A6: DEBUG=False siempre en producción. Stacktrace nunca llega al cliente.
DEBUG = False

# D13: la autenticidad del webhook no se lee del entorno.
#
# La firma X-Twilio-Signature es la ÚNICA cerradura del webhook: la URL es
# pública y adivinable, no hay login y está exenta de CSRF. Sin validación,
# cualquiera que conozca la URL puede inyectar telemetría falsa en la historia
# de un paciente, o cerrar su check-in del día como respondido —apagando la
# alerta SILENCIO de alguien que en realidad no respondió—.
#
# NO CREAR la variable TWILIO_VALIDATE_SIGNATURE en Railway, ni siquiera con
# valor True: python-decouple convierte la cadena vacía en False, y Railway
# reemplaza por cadena vacía toda referencia que no puede resolver
# (docs/trampas_conocidas.md, incidente del 25/07/2026). Una casilla que no
# existe no se puede configurar mal; una que existe se abre en silencio el día
# que alguien la mueva de sitio.
#
# False sigue siendo legítimo en desarrollo local, donde no hay firma real que
# validar: allí lo gobierna settings.py leyendo el .env.
TWILIO_VALIDATE_SIGNATURE = True

# --- Archivos estáticos con WhiteNoise (despliegue, 04/07/2026) ---
# Railway no tiene un Nginx delante que sirva /static/, así que WhiteNoise
# sirve los estáticos del Admin desde el propio proceso Django. El middleware
# va INMEDIATAMENTE después de SecurityMiddleware (índice 0 de la lista base).
# collectstatic corre al arrancar el contenedor (ver Dockerfile) hacia STATIC_ROOT.
MIDDLEWARE = [
    MIDDLEWARE[0],  # django.middleware.security.SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    *MIDDLEWARE[1:],
]
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # Comprime y versiona (hash) los estáticos. Si collectstatic fallara
        # por una referencia estática inexistente, degradar a
        # 'whitenoise.storage.CompressedStaticFilesStorage' (sin manifest).
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# B1: cabeceras de seguridad HTTPS
SESSION_COOKIE_SECURE   = True
CSRF_COOKIE_SECURE      = True
SECURE_SSL_REDIRECT     = True
SECURE_HSTS_SECONDS     = 31536000   # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD     = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS         = 'DENY'

# CSP de producción: los scripts solo pueden salir de nuestros estáticos.
# El Admin y el tablero todavía usan algunos atributos style="...", por eso
# style-src conserva unsafe-inline de forma acotada; script-src no lo permite.
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'script-src': [CSP.SELF],
    'style-src': [CSP.SELF, CSP.UNSAFE_INLINE],
    'img-src': [CSP.SELF, 'data:'],
    'font-src': [CSP.SELF],
    'connect-src': [CSP.SELF],
    'object-src': [CSP.NONE],
    'base-uri': [CSP.SELF],
    'form-action': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
}

# B1: CSRF origins explícitos (Twilio + dominio propio).
# Ejemplo en .env de producción: CSRF_TRUSTED_ORIGINS=https://midominio.com
# Obligatoria (hallazgo 11): vacía, el POST del login devuelve 403 sin
# explicación y el fallo aparece en la cara del médico, no al desplegar.
# `config_obligatoria` llega desde settings.py con el import * de arriba.
CSRF_TRUSTED_ORIGINS = config_obligatoria('CSRF_TRUSTED_ORIGINS', cast=Csv())

# Railway documenta X-Real-IP como la IP remota y X-Railway-Edge como una
# cabecera presente en todas las solicitudes que atraviesan su edge. La
# confianza se habilita de forma explícita para no aceptar esos headers en
# despliegues directos o locales.
#
# TRUST_RAILWAY_PROXY vive ahora en settings.py, donde además gobierna
# USE_X_FORWARDED_HOST y SECURE_PROXY_SSL_HEADER (hallazgo 6): un solo
# interruptor para las tres cabeceras del proxy. En Railway debe estar en True
# — sin él, Django ve HTTP detrás del edge y SECURE_SSL_REDIRECT entra en un
# bucle de redirecciones.

# B5: URL del admin en producción debe diferir de la de desarrollo (ver urls.py).
# Se documenta aquí para recordatorio; el cambio real está en urls.py.

# Cache compartido entre workers (A3/A5/C7 dependen de esto).
# En producción se REQUIERE Redis o Memcached — el backend de memoria de
# Django (default) no comparte estado entre procesos/workers y haría que
# los rate limits compartidos entre workers fallarían silenciosamente.
# Variable de entorno: REDIS_URL=redis://:password@host:6379/1
# Obligatoria (hallazgo 11): con el default de localhost, una REDIS_URL vacía o
# mal referenciada tras recrear el servicio arrancaría "bien" y degradaría en
# silencio los rate limits compartidos entre workers.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config_obligatoria('REDIS_URL'),
    }
}

# Sprint 5, Bloque 5 — entrega real del email de alerta ALTA.
EMAIL_DELIVERY_PROVIDER = config(
    'EMAIL_DELIVERY_PROVIDER', default='django'
).strip().lower()
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)
PANEL_MEDICO_URL = config('PANEL_MEDICO_URL', default='')

if EMAIL_DELIVERY_PROVIDER == 'django':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = config_obligatoria('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config_obligatoria('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
elif EMAIL_DELIVERY_PROVIDER == 'resend':
    # Obligatorias (hallazgo 11): vacías, el aviso de una alerta ALTA se
    # acumula en el outbox y falla 10 veces antes de rendirse (D6), en vez de
    # avisar al desplegar que la credencial nunca se configuró.
    RESEND_API_KEY = config_obligatoria('RESEND_API_KEY')
    RESEND_FROM_EMAIL = config_obligatoria('RESEND_FROM_EMAIL')
else:
    raise ImproperlyConfigured(
        'EMAIL_DELIVERY_PROVIDER debe ser "django" o "resend".'
    )
