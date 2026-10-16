"""TEST-11 — la suite completa, corrida con el reloj cruzando la medianoche.

QUÉ COMPRUEBA
=============

La auditoría del 07/09/2026 dejó TEST-11 como PLAUSIBLE y sin verificar: los
escenarios de varios días que NO usan el ancla de reloj (`soporte.py`) podrían
romperse si la corrida cruza la medianoche de Bogotá entre dos lecturas del
reloj —«ayer» y «hoy» caerían el mismo día—. Hacía falta correr la suite a las
23:59, y nadie lo había hecho.

CÓMO
====

Se adelanta el reloj con `freezegun` (`tick=True`) ANTES de que Django
arranque: marca la hora pedida al empezar y **sigue avanzando**, así que la
corrida cruza la medianoche de verdad a mitad de la suite. Las pruebas que
congelan el reloj con su propio `freeze_time` lo siguen haciendo encima.

Todo el código del proyecto lee la hora de `django.utils.timezone.now`: no hay
`date.today()` ni `datetime.now()` sueltos (comprobado el 15/10/2026, y la
prueba `NormaDeZonaHorariaTests` vigila los `.date()`).

USO
===

    cd Registro_Post_Quirurgico
    ..\\.venv\\Scripts\\python.exe ..\\proceso\\verificaciones\\2026-10-15_suite_a_medianoche.py [HH:MM:SS] [etiquetas de prueba...]

Por defecto arranca a las 23:58:30 de Bogotá. Sale con el código de la suite.

RESULTADO DEL 15/10/2026
========================

**Ninguna fragilidad.** La suite completa pasó cruzando la medianoche dos
veces —arrancando a las 23:58:30 y a las 23:57:00, para que el cambio de día
cayera sobre pruebas distintas—, y la clase del bot que trabaja con horas
relativas pasó aislada a las 23:59:59, 00:00:05, 00:30, 05:00 y 08:00.

**Una primera versión de este script dio 9 fallos, y eran suyos.** Parcheaba
`timezone.now` sumándole un desfase fijo, y las pruebas del backoff (TEST-06)
congelan el reloj con `freeze_time`: el parche le sumaba 3,6 horas al instante
congelado. Antes de dar un fallo por bueno hay que descartar que lo produzca
el instrumento; con `freezegun` los dos relojes se encadenan bien.
"""

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

hora = sys.argv[1] if len(sys.argv) > 1 else '23:58:30'
etiquetas = sys.argv[2:]   # vacío = la suite completa
sys.argv = sys.argv[:1]

from freezegun import freeze_time  # noqa: E402

_bogota = ZoneInfo('America/Bogota')
_ahora_sistema = datetime.now(_bogota)
_objetivo = datetime.combine(
    _ahora_sistema.date(), datetime.strptime(hora, '%H:%M:%S').time(), tzinfo=_bogota)
_desfase = _objetivo - _ahora_sistema

# `tick=True`: el reloj arranca en la hora pedida y SIGUE AVANZANDO, así que la
# corrida cruza la medianoche de verdad. Se usa freezegun y no un parche propio
# de `timezone.now` porque las pruebas congelan el reloj con `freeze_time`
# anidado: un parche propio le sumaba el desfase al instante congelado, y la
# primera corrida del 15/10 dio por eso 7 fallos que eran del arnés, no del
# sistema (el backoff de TEST-06).
freeze_time(_objetivo, tick=True).start()

import django.utils.timezone as tz  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Registro_Post_Quirurgico.settings')
sys.path.insert(0, os.getcwd())

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.test.utils import get_runner  # noqa: E402

inicio = tz.localtime(tz.now())
print(f'Reloj del proyecto al arrancar: {inicio:%Y-%m-%d %H:%M:%S %Z} '
      f'(desfase {_desfase.total_seconds() / 3600:+.2f} h)', flush=True)

Runner = get_runner(settings)
fallos = Runner(verbosity=1, interactive=False).run_tests(etiquetas)

fin = tz.localtime(tz.now())
print(f'Reloj del proyecto al terminar: {fin:%Y-%m-%d %H:%M:%S %Z}'
      f' — {"cruzó" if fin.date() != inicio.date() else "NO cruzó"} la medianoche')
assert timedelta(0) <= fin - inicio
sys.exit(1 if fallos else 0)
