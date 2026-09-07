import re
from pathlib import Path

from decouple import Csv, UndefinedValueError, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Variables de entorno obligatorias (hallazgo 11) ---
# `config('X')` solo protege del caso "no existe". Si la variable existe pero
# está vacía devuelve '' y el proceso arranca con una configuración inválida
# que falla mucho después y lejos de su causa: un correo que nunca sale, un
# login que devuelve 403, un cache que no comparte estado entre workers.
_PLACEHOLDER_RE = re.compile(r'^<.*>$')


def config_obligatoria(nombre, cast=None):
    """Lee una variable que el despliegue REQUIERE y detiene el arranque si no sirve.

    Rechaza tres formas de estar mal: no definida, vacía (o solo espacios), y
    con el placeholder de ejemplo todavía puesto. Pegar los `<...>` literalmente
    en las variables de Railway fue la causa raíz del 403 de Twilio y de los
    login fallidos al Admin (BITACORA, 06/07/2026): el proceso arrancaba
    normal y el fallo aparecía en otra parte, sin relación aparente.

    El mensaje nombra la variable pero NUNCA muestra su valor: varias de ellas
    son secretos.
    """
    try:
        valor = config(nombre)
    except UndefinedValueError:
        valor = None

    texto = '' if valor is None else str(valor).strip()
    if not texto:
        raise ImproperlyConfigured(
            f'La variable de entorno {nombre} es obligatoria y está vacía o sin '
            'definir. Escribe su valor en el .env (o en las variables del '
            'servicio en Railway), crudo: sin comillas y sin <corchetes>.'
        )
    if _PLACEHOLDER_RE.match(texto):
        raise ImproperlyConfigured(
            f'La variable de entorno {nombre} conserva un placeholder de ejemplo '
            'entre < >. Reemplázalo por el valor real, sin los signos.'
        )
    return cast(texto) if cast else texto


SECRET_KEY = config_obligatoria('SECRET_KEY')
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
    'axes',          # B5: bloqueo de intentos de login al admin
    'signos_sintomas',
    'home',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',   # B5: debe ir DESPUÉS de AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',  # B5: primero axes, luego el default
    'django.contrib.auth.backends.ModelBackend',
]

# B5: configuración de django-axes
AXES_FAILURE_LIMIT     = 5    # bloquea tras 5 intentos fallidos
AXES_COOLOFF_TIME      = 1    # desbloqueo automático tras 1 hora
AXES_LOCK_OUT_AT_FAILURE = True
AXES_RESET_ON_SUCCESS  = True  # reinicia el contador al loguearse bien

ROOT_URLCONF = 'Registro_Post_Quirurgico.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Carpeta de plantillas del proyecto — se busca ANTES que las de las
        # apps, así podemos sobreescribir plantillas del Admin (base_site.html,
        # índice del panel del médico).
        'DIRS': [BASE_DIR / 'templates'],
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
        'NAME': config_obligatoria('DB_NAME'),
        'USER': config_obligatoria('DB_USER'),
        'PASSWORD': config_obligatoria('DB_PASSWORD'),
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
# Destino de collectstatic. En producción WhiteNoise sirve desde aquí
# (ver settings_production.py). En desarrollo runserver sirve los estáticos
# de las apps directamente, así que STATIC_ROOT solo se usa al hacer deploy.
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# B5: URL del admin — en producción cambiar a slug no trivial vía .env.
# Ejemplo: ADMIN_URL=gestion-clinica-x7k2/
ADMIN_URL = config('ADMIN_URL', default='admin/')

# --- Twilio / WhatsApp webhook (Sprint 3) ---
# Fail-safe: si la variable NO existe en .env, la validación queda ACTIVA.
# Para desactivarla (solo pruebas locales) hay que escribirla explícitamente:
#   TWILIO_VALIDATE_SIGNATURE=False
TWILIO_VALIDATE_SIGNATURE = config('TWILIO_VALIDATE_SIGNATURE', default=True, cast=bool)
# Secreto: vive solo en .env. default='' para no romper el arranque; la ausencia
# real se maneja con error claro en el webhook (nunca falla abierto).
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')

# Cuenta staff que recibe los mensajes del formulario público de contacto.
# Si queda vacía o no existe, los mensajes se conservan sin asignar y solo
# son visibles para el superusuario (fail-closed para datos personales).
MEDICO_CONTACTO_USERNAME = config('MEDICO_CONTACTO_USERNAME', default='')

# --- Confianza en el proxy que está delante (hallazgo 6) ---
# Railway —y ngrok en desarrollo— entregan la petición al proceso por HTTP y
# describen la original en cabeceras: X-Forwarded-Proto, X-Forwarded-Host y
# X-Real-IP. Creerles solo es correcto si TODO el tráfico entra por ese edge;
# si el proceso es alcanzable de forma directa, cualquiera puede escribirlas y
# hacerle creer a Django que una petición en claro llegó por HTTPS.
#
# Un solo interruptor gobierna las tres cabeceras: el esquema, el host
# reconstruido y la IP del cliente (home.views._get_client_ip). Por defecto NO
# se confía; se declara con TRUST_RAILWAY_PROXY=True en el entorno.
#
# Al activarlo, build_absolute_uri() reconstruye la URL pública https que Twilio
# firmó — imprescindible para validar X-Twilio-Signature detrás del túnel.
TRUST_RAILWAY_PROXY = config('TRUST_RAILWAY_PROXY', default=False, cast=bool)
USE_X_FORWARDED_HOST = TRUST_RAILWAY_PROXY
SECURE_PROXY_SSL_HEADER = (
    ('HTTP_X_FORWARDED_PROTO', 'https') if TRUST_RAILWAY_PROXY else None
)

# --- Logging (B2) ---
#
# QUÉ HACE Y QUÉ NO — corregido en D11 (Loop D). El comentario anterior decía
# que este LOGGING "filtra PHI/PII". No filtra nada: el único filtro declarado
# es RequireDebugFalse, que decide a quién se le manda un correo de error, no
# qué se escribe. Un comentario que promete una garantía de privacidad que no
# existe es peor que no tener comentario — hace que nadie vuelva a mirar.
#
# Lo que sí protege la identidad del paciente, y dónde vive de verdad:
#   1. El código no la escribe. Los comandos y las señales identifican al
#      paciente por `pk` (D11), y hay una prueba guardián que recorre la salida
#      de los comandos operativos forzando nivel INFO y falla si aparece un
#      nombre o un teléfono.
#   2. La vista del webhook usa @sensitive_post_parameters('From', 'Body'), que
#      oculta esos campos en el reporte de error de Django.
#   3. El nivel WARNING de `signos_sintomas` reduce el volumen, pero NO es una
#      garantía: es una configuración que alguien puede cambiar.
#
# Lo que NO está saneado: el texto de una excepción ajena que llegue por un
# traceback (`logger.exception`). El encabezado que escribe este proyecto usa
# solo `pk`s, pero una excepción de terceros podría arrastrar un valor. No hay
# ningún caso conocido; queda registrado como exposición condicional, fuera del
# alcance de D11 — redactar tracebacks es una capa de logging propia y merece su
# propia decisión.
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
