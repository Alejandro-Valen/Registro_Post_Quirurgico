"""Ejecución de las tareas que comparten un mismo servicio cron.

Por qué existe (decisión D14, `docs/decisiones_correccion_auditoria.md`): las
tareas de un cron están agrupadas porque el plan de Railway no daba para más
servicios, no por una razón clínica. Ejecutarlas en un bucle sin manejo de
errores hacía que **el fallo de una impidiera correr a las siguientes**: un
fallo persistente de `cerrar_checkins_vencidos` dejaba sin entregar los correos
de alerta ALTA de todo el ciclo, en las dos rutas a la vez.

La regla que implementa este módulo:

1. Se ejecutan **todas** las tareas. El fallo de una se registra y no detiene a
   las demás.
2. **Salvo dependencia clínica declarada:** una tarea que declara `depende_de`
   se omite si esa dependencia no completó. El aislamiento es selectivo y está
   escrito en el propio cron, con su motivo al lado — "continuar ante el fallo"
   a secas sería un error (ver el motivo de `crear_checkins_diarios`).
3. La corrida **termina en error** nombrando lo que falló y lo que se omitió.
   Rendirse en silencio sería peor que fallar: Railway marca la corrida como
   fallida y esa señal operativa es legítima; lo que no lo era es que costara
   los correos del ciclo.
"""

import logging
import traceback
from dataclasses import dataclass

from django.core.management import call_command
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TareaCron:
    """Una tarea del cron y, si la tiene, su dependencia clínica declarada.

    `motivo` explica **por qué** existe la dependencia y viaja al log cuando la
    tarea se omite: quien lea el log de Railway a las 6 AM tiene que entender
    qué dejó de pasar sin abrir el código.
    """

    nombre: str
    depende_de: str | None = None
    motivo: str = ''


def ejecutar_tareas(comando, etiqueta, tareas):
    """Corre `tareas` aislando los fallos, salvo dependencia declarada.

    `comando` es el `BaseCommand` que invoca — se usan su `stdout`/`stderr` para
    que la salida respete los flujos que reciba el cron.

    Lanza `CommandError` al terminar si alguna tarea falló o quedó omitida.
    """
    completadas = set()
    fallidas = []
    omitidas = []

    for tarea in tareas:
        if tarea.depende_de and tarea.depende_de not in completadas:
            omitidas.append(tarea)
            aviso = (
                f'{etiqueta}: {tarea.nombre} OMITIDA — depende de '
                f'{tarea.depende_de}, que no completó. {tarea.motivo}'
            ).strip()
            comando.stderr.write(comando.style.ERROR(aviso))
            logger.error(aviso)
            continue

        comando.stdout.write(f'--- {etiqueta}: {tarea.nombre} ---')
        try:
            call_command(tarea.nombre)
        except Exception as exc:  # noqa: BLE001  (D14: el fallo de una tarea no detiene a las demás; se registra abajo sin el mensaje, SEC-10)
            # Se captura Exception, no BaseException: una interrupción del
            # proceso (Ctrl-C, SystemExit) debe seguir cortando la corrida.
            fallidas.append(tarea)
            # SEC-10 (02/10/2026) — el NOMBRE de la excepción y la traza, nunca
            # su mensaje. Un IntegrityError de PostgreSQL trae en el mensaje
            # los valores de la fila («Key (cedula)=(…) already exists»), y
            # esto acaba en el log de Railway. Es la misma regla que ya sigue
            # `registrar_fallo_evaluacion` (D11). La traza sí se conserva: dice
            # en qué función y en qué línea falló sin mostrar ningún dato.
            nombre_error = exc.__class__.__name__
            comando.stderr.write(comando.style.ERROR(
                f'{etiqueta}: {tarea.nombre} FALLÓ ({nombre_error}) — las '
                f'tareas que no dependen de ella siguen corriendo.'
            ))
            logger.error(
                '%s: la tarea %s falló con %s.\n%s',
                etiqueta, tarea.nombre, nombre_error,
                ''.join(traceback.format_tb(exc.__traceback__)).rstrip(),
            )
        else:
            completadas.add(tarea.nombre)

    if fallidas or omitidas:
        partes = []
        if fallidas:
            partes.append(
                'fallaron: ' + ', '.join(t.nombre for t in fallidas)
            )
        if omitidas:
            partes.append(
                'omitidas por dependencia: '
                + ', '.join(t.nombre for t in omitidas)
            )
        raise CommandError(f'{etiqueta}: {"; ".join(partes)}.')

    comando.stdout.write(
        comando.style.SUCCESS(f'{etiqueta}: todas las tareas completadas.')
    )
