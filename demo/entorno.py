"""Arranca el sistema real sobre una base de datos DESECHABLE.

**Por qué una base desechable y no la de desarrollo.** La demo crea pacientes,
registros y alertas. Si escribiera en la base de siempre, cada ensayo dejaría
basura y el día de la reunión el panel estaría lleno de «Paciente Demo 7». Se usa
la maquinaria de bases de prueba de Django: se crea una al empezar y se destruye
al salir. **No queda rastro.**

**Lo que NO hace este módulo.** No simula nada del sistema. Llama a
`bot.procesar_mensaje()` y a `alert_engine.evaluar_registro()`, que son las
mismas funciones que atienden a un paciente real por WhatsApp. Lo único que
cambia es la puerta por la que entra el texto.

Eso no es mérito de la demo: el bot se escribió desde el principio como *lógica
pura respecto al transporte* —«recibe texto plano y devuelve texto plano, no
conoce HTTP ni Twilio»—, y por eso enchufarle una terminal sale gratis.
"""

import os
import sys
import warnings
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'

_runner = None
_config_vieja = None


def arrancar():
    """Deja Django listo con una base de datos temporal.

    Devuelve el nombre del motor que acabó usando: 'PostgreSQL' o 'SQLite'.

    **Por qué hay plan B.** Esto se enseña en una reunión, en un portátil que
    puede no ser el de siempre. Si PostgreSQL no está levantado, la demo se
    caería en el peor momento posible por una razón que no tiene nada que ver
    con el sistema. Así que si el motor de verdad no está, se sigue con SQLite
    **y se dice en pantalla**: bajar de motor en silencio sería el tipo de
    detalle que este proyecto lleva un mes quitándose de encima.
    """
    global _runner, _config_vieja

    sys.path.insert(0, str(PROYECTO))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'Registro_Post_Quirurgico.settings')
    import django
    django.setup()

    from django.test.utils import setup_test_environment
    setup_test_environment()

    # Cada demo se lleva su propia base, con el número de proceso en el nombre.
    # Sin esto, dos demos abiertas a la vez chocan: la segunda muere con «la base
    # de datos test_registro_postquirurgico_db ya existe» y no arranca hasta que
    # se cierre la primera. Pasó de verdad, con dos ventanas abiertas.
    from django.conf import settings
    settings.DATABASES['default'].setdefault('TEST', {})
    settings.DATABASES['default']['TEST']['NAME'] = f'test_demo_{os.getpid()}'

    from django.db import DatabaseError
    try:
        # El intento fallido de PostgreSQL escupe un RuntimeWarning largo de
        # Django antes de rendirse. Es ruido de un camino que ya sabemos que no
        # va a funcionar, y en pantalla parece que algo se rompió.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _montar()
        return 'PostgreSQL'
    except (DatabaseError, OSError, ImportError, SystemExit):
        # `SystemExit` no sobra: cuando Django no puede crear la base de pruebas
        # no lanza una excepción de base de datos, imprime el motivo y llama a
        # `sys.exit(2)`. Sin capturarlo, el plan B se saltaba justo en el caso
        # para el que existe.
        _usar_sqlite()
        _montar()
        return 'SQLite'


def _montar():
    from django.test.runner import DiscoverRunner
    global _runner, _config_vieja
    _runner = DiscoverRunner(verbosity=0, interactive=False)
    _config_vieja = _runner.setup_databases()


def _usar_sqlite():
    """Reemplaza la conexión por una SQLite en memoria.

    Se comprobó que el recorrido completo del bot y las seis alertas del caso
    grave salen idénticas en los dos motores; las restricciones del modelo son
    `CheckConstraint`, que SQLite también aplica.

    **Sin migraciones, a propósito.** La migración 0010 crea un índice funcional
    con `AT TIME ZONE`, que es SQL de PostgreSQL y SQLite no entiende. Con
    `MIGRATION_MODULES` en `None` —mecanismo del propio Django— las tablas se
    crean directamente desde los modelos de hoy. Lo que se pierde es ese índice,
    que solo acelera consultas: ninguna regla clínica depende de él.
    """
    from django.apps import apps
    from django.conf import settings
    from django.db import connections
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
    settings.MIGRATION_MODULES = {a.label: None for a in apps.get_app_configs()}
    # Django normaliza `DATABASES` una sola vez y guarda el resultado. Sin
    # tirar ese cache, la conexión nueva sale a medio construir y revienta con
    # un `KeyError: 'MIRROR'` en vez de con el error de PostgreSQL, que es el
    # que hay que enseñar. Se comprobó provocando el fallo a propósito.
    from asgiref.local import Local
    connections.close_all()
    for cache in ('settings', 'databases'):
        connections.__dict__.pop(cache, None)
    connections._settings = None
    connections._connections = Local(connections.thread_critical)


def apagar():
    """Destruye la base temporal. Se llama siempre, también si algo falla."""
    global _runner, _config_vieja
    if _runner is None:
        return
    from django.test.utils import teardown_test_environment
    try:
        _runner.teardown_databases(_config_vieja)
    finally:
        teardown_test_environment()
        _runner = None


# ---------------------------------------------------------------------------
# Fixtures de la demo
# ---------------------------------------------------------------------------
def crear_medico():
    from django.contrib.auth import get_user_model
    medico, _ = get_user_model().objects.get_or_create(
        username='medico_demo',
        defaults={'is_staff': True, 'is_superuser': True,
                  'email': 'medico@ejemplo.com',
                  'first_name': 'Médico', 'last_name': 'de guardia'},
    )
    return medico


def crear_paciente(nombre, telefono, dias_postoperatorio=5):
    from django.utils import timezone

    from signos_sintomas.models import Paciente
    return Paciente.objects.create(
        medico_responsable=crear_medico(),
        nombre_completo=nombre,
        telefono_whatsapp=telefono,
        fecha_cirugia=timezone.localdate() - timedelta(days=dias_postoperatorio),
        consentimiento_informado=True,
        activo=True,
    )


def abrir_turno(paciente, dias_atras=0, orden=None, horas_atras=0):
    """Un turno de check-in, como lo crearía `crear_checkins_diarios`.

    `orden` importa más de lo que parece: la racha de SILENCIO se cuenta
    recorriendo los turnos por (fecha_dia, orden), no por fecha de creación.
    Por eso los turnos de la demo se reparten en días reales —dos por día—
    en vez de amontonar cuatro en el mismo día, que no ocurriría nunca.
    """
    from django.utils import timezone

    from signos_sintomas.models import CheckInProgramado
    dia = timezone.localdate() - timedelta(days=dias_atras)
    if orden is None:
        orden = CheckInProgramado.objects.filter(
            paciente=paciente, fecha_dia=dia).count() + 1
    etiqueta = (CheckInProgramado.ETIQUETA_MANANA if orden == 1
                else CheckInProgramado.ETIQUETA_TARDE)
    return CheckInProgramado.objects.create(
        paciente=paciente,
        fecha_dia=dia,
        orden=orden,
        etiqueta=etiqueta,
        hora_programada=timezone.now() - timedelta(days=dias_atras,
                                                  hours=horas_atras),
    )


def vencer_turnos():
    """Corre el command real que cierra los turnos vencidos.

    No es una imitación: es `cerrar_checkins_vencidos`, el mismo que corre en
    el cron.
    """
    from io import StringIO

    from django.core.management import call_command
    call_command('cerrar_checkins_vencidos',
                 stdout=StringIO(), stderr=StringIO())


def alertas_de(paciente):
    """Lo que el médico ve del paciente, sin resolver, ordenado por gravedad."""
    from signos_sintomas.models import Alerta
    orden = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}
    alertas = list(Alerta.objects.filter(paciente=paciente, resuelta=False))
    alertas.sort(key=lambda a: (orden.get(a.severidad, 9), -a.veces))
    return alertas


def hablar(paciente, texto):
    """Un mensaje del paciente, procesado por el bot REAL."""
    from signos_sintomas import bot
    return bot.procesar_mensaje(f'whatsapp:{paciente.telefono_whatsapp}', texto)
