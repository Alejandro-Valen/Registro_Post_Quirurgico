"""Piezas compartidas por los modulos de prueba de signos_sintomas.

No lleva pruebas y su nombre no casa con el patron `test*.py`, asi que
el descubridor de Django no lo recorre: no puede mover el conteo de la
suite en ninguna direccion."""

from datetime import datetime
from datetime import time as hora_del_dia

from django.contrib.auth import get_user_model
from django.utils import timezone

# --- Ancla de reloj para las pruebas que arman escenarios de varios días ---
#
# Varias clases construyen sus fixtures leyendo el reloj más de una vez: el
# registro de "anteayer", el de "ayer", la fecha que el modelo pone solo al
# crear el de hoy, y la que el motor usa al evaluar. Si la corrida cruza la
# medianoche de Bogotá entre dos de esas lecturas, "ayer" y "hoy" caen el mismo
# día y la prueba falla sin que nada esté mal en el sistema: el motor agrupa por
# `fecha_registro__date` y calcula con `localdate()`, que es lo correcto.
#
# Es fragilidad de las pruebas, y estaba medida: con un reloj falso que cruza la
# medianoche a distintas profundidades del escenario caían 14 pruebas de cinco
# clases (Loop C; el Loop B había contado 17 con otro arnés).
#
# El ancla congela el reloj de esas clases en el PEOR instante del día —un
# segundo antes de la medianoche— calculado una sola vez al importar el módulo.
# Todas las lecturas devuelven el mismo instante: el escenario es coherente por
# construcción y además queda probado en el borde, que es donde antes se rompía.
#
# Se aplica clase por clase, nunca global: congelar el reloj rompería las
# pruebas que necesitan que el tiempo avance (márgenes del webhook, backoff de
# reintentos).
ANCLA_MEDIANOCHE = datetime.combine(
    timezone.localdate(),
    hora_del_dia(23, 59, 59),
).replace(tzinfo=timezone.get_current_timezone())


def medico_de_pruebas(username='medico_fixture'):
    """Médico responsable por defecto de los pacientes de las pruebas (D12).

    Desde la migración 0028 un paciente ACTIVO no puede existir sin médico
    responsable: la base lo rechaza. Las pruebas que solo necesitan "un
    paciente" para ejercitar el motor, el bot o el scheduler no tienen por qué
    ocuparse de eso, así que este helper les da uno usable —activo, `is_staff`
    y con correo, las tres condiciones de la capa 3— sin ruido en el fixture.

    Se crea con `get_or_create` porque varias pruebas arman más de un paciente
    y todos pueden compartir el mismo responsable.

    Cuando lo que se prueba ES la relación con el médico (asignación, borrado,
    aislamiento entre médicos, ficha histórica sin responsable), el fixture pasa
    su propio `medico_responsable` explícito y no usa este helper.
    """
    medico, _ = get_user_model().objects.get_or_create(
        username=username,
        defaults={
            'is_staff': True,
            'email': f'{username}@ejemplo.com',
        },
    )
    return medico


class EspiaDeTareasCronMixin:
    """Observa qué management commands corrieron de verdad dentro de un cron.

    Reemplaza el `handle` de cada tarea por un espía que anota su nombre y, si
    se le pide, lanza. Se espía **el comando de destino**, no el `call_command`
    del runner: así la prueba afirma "la tarea corrió" en vez de "un mock
    recibió una llamada", y no depende de dónde viva el bucle que las ejecuta.
    """

    def espiar_tareas(self, tareas, fallan=()):
        from contextlib import ExitStack
        from unittest.mock import patch

        ejecutadas = []

        def espia_de(nombre):
            def espia(*args, **kwargs):
                ejecutadas.append(nombre)
                if nombre in fallan:
                    raise RuntimeError(f'fallo simulado de {nombre}')
                # Devolver None: BaseCommand.execute escribe lo que retorne
                # handle, y un MagicMock rompería el OutputWrapper.
                return
            return espia

        pila = ExitStack()
        self.addCleanup(pila.close)
        for nombre in tareas:
            pila.enter_context(patch(
                f'signos_sintomas.management.commands.{nombre}.Command.handle',
                side_effect=espia_de(nombre),
            ))
        return ejecutadas

    def correr_cron(self, comando):
        """Corre el cron y devuelve (ejecutadas ya observadas, excepción o None).

        El fallo se captura en vez de dejarlo propagar para poder afirmar
        primero lo clínico —qué tareas alcanzaron a correr— y solo después cómo
        terminó la corrida. Si se dejara escapar, la prueba fallaría por el tipo
        de la excepción y nunca llegaría a mirar lo que importa.
        """
        import io

        from django.core.management import call_command

        try:
            call_command(comando, stdout=io.StringIO(), stderr=io.StringIO())
        except Exception as exc:  # noqa: BLE001 — se inspecciona más abajo
            return exc
        return None
