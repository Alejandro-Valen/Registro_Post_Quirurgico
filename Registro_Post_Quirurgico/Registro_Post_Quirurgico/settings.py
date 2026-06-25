from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# Hosts permitidos: se definen por .env (separados por coma), NUNCA con wildcard
# '*' en el código. Dev: agrega tu dominio de ngrok. Prod: el dominio real.
# Si queda vacío y DEBUG=False, Django rechaza todo (fail-closed seguro).
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

# En desarrollo, garantizar acceso local aunque se haya definido un host de ngrok
# en .env (definir ALLOWED_HOSTS desactiva el permiso automático de localhost).
if DEBUG:
    ALLOWED_HOSTS += ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'signos_sintomas',
    'home',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Registro_Post_Quirurgico.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Registro_Post_Quirurgico.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Twilio / WhatsApp webhook (Sprint 3) ---
# Fail-safe: si la variable NO existe en .env, la validación queda ACTIVA.
# Para desactivarla (solo pruebas locales) hay que escribirla explícitamente:
#   TWILIO_VALIDATE_SIGNATURE=False
TWILIO_VALIDATE_SIGNATURE = config('TWILIO_VALIDATE_SIGNATURE', default=True, cast=bool)
# Secreto: vive solo en .env. default='' para no romper el arranque; la ausencia
# real se maneja con error claro en el webhook (nunca falla abierto).
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')

# Detrás de un túnel/proxy (ngrok): que build_absolute_uri() reconstruya la URL
# pública https que Twilio firmó (imprescindible para validar X-Twilio-Signature).
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --- Logging (B2) ---
# Filtra PHI/PII: los logs de Django nunca deben escribir el cuerpo del webhook
# (síntomas del paciente) ni el número de teléfono en claro. La vista del
# webhook ya usa @sensitive_post_parameters('From', 'Body') para los reportes
# de error; este LOGGING evita que aparezcan en los logs normales de Django.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'signos_sintomas': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}