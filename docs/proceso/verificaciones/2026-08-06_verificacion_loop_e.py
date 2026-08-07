"""Verificación del Loop E (D14) — la ejecuta el Arquitecto, no el agente.

QUÉ ES: cinco bloques que imprimen en pantalla la evidencia de que las tareas
del cron quedaron aisladas **sin perder la dependencia clínica**. No es la suite
del proyecto: es la comprobación independiente que exige el método
(`docs/proceso/metodo_de_trabajo.md`, regla 4) — *el agente que escribió el
código es el peor juez de si el código está bien*.

QUÉ NO ES: una repetición de las pruebas de E-1. Aquellas espían qué tareas
corrieron; el bloque 1 de aquí va más lejos y comprueba **el desenlace clínico**:
que el correo de la alerta ALTA sale de verdad, con datos reales en la base,
aunque la primera tarea del cron falle. Ver una tarea "correr" no es ver una
alerta entregada.

CÓMO SE CORRE, desde `Registro_Post_Quirurgico/` (PowerShell):

    cd Registro_Post_Quirurgico
    $env:PYTHONPATH = "../docs/proceso/verificaciones"
    python manage.py test 2026-08-06_verificacion_loop_e -v 2 --noinput
    Remove-Item Env:PYTHONPATH

Corre contra una base de datos de PRUEBA desechable. No toca producción ni la
base local de desarrollo.

QUÉ SE VERIFICA:

    1. D14  el correo de una alerta ALTA se entrega aunque falle la primera
            tarea del cron — el desenlace clínico, no solo "la tarea corrió"
    2. D14  la dependencia declarada se respeta: si falla la desactivación,
            NO se crean check-ins…
    3. D14  …y ese es justo el daño que evita — el check-in espurio que se
            habría creado termina en una alerta SILENCIO falsa
    4. D14  la corrida termina en error nombrando TODO lo que falló y lo que
            se omitió; no se rinde en la primera ni finge que salió bien
    5. D14  el aislamiento no se traga una interrupción del proceso: un
            KeyboardInterrupt sigue cortando la corrida

EL BLOQUE QUE HAY QUE MIRAR CON MÁS CUIDADO es el 3: es el único que demuestra
por qué "continuar ante el fallo" a secas —la corrección obvia— habría sido un
error clínico.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from signos_sintomas.cron_runner import TareaCron, ejecutar_tareas
from signos_sintomas.models import (
    Alerta,
    CheckInProgramado,
    NotificacionAlerta,
    Paciente,
)


def _titulo(texto):
    print("\n" + "=" * 72)
    print("  " + texto)
    print("=" * 72)


def _medico(username='dr_verif_e'):
    return get_user_model().objects.create_user(
        username=username,
        password='x',
        is_staff=True,
        email='{}@ejemplo.com'.format(username),
    )


def _paciente(medico, sufijo='1', **campos):
    valores = {
        'nombre_completo': 'Paciente Verificacion E{}'.format(sufijo),
        'telefono_whatsapp': '+5730199901{}'.format(sufijo),
        # Ojo: NO empieza por 'DEMO-'. `signals.py` corta la notificación de
        # los pacientes demo antes de mirar la severidad, y eso dejaría el
        # bloque 1 midiendo el guard en vez del cron.
        'cedula': 'VERIF-E-{}'.format(sufijo),
        'fecha_cirugia': timezone.localdate(),
        'medico_responsable': medico,
    }
    valores.update(campos)
    return Paciente.objects.create(**valores)


def _romper(nombre):
    """Parchea el `handle` de un management command para que falle.

    Se rompe **el comando de destino**, no el `call_command` del runner: así la
    verificación no depende de dónde viva el bucle que las despacha, y sigue
    siendo válida si mañana el runner se reescribe.
    """
    return patch(
        'signos_sintomas.management.commands.{}.Command.handle'.format(nombre),
        side_effect=RuntimeError('fallo forzado por la verificacion'),
    )


class Verificacion1LaAlertaSeEntregaIgual(TestCase):
    """El desenlace clínico: el correo sale aunque falle la primera tarea."""

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EMAIL_ALERTAS_DESTINATARIO='medico-de-guardia@ejemplo.com',
    )
    def test_el_correo_de_una_alerta_alta_sale_con_la_primera_tarea_rota(self):
        _titulo("1. D14 — el correo de la alerta ALTA sale igual")
        print("  Antes: un fallo persistente de cerrar_checkins_vencidos")
        print("  dejaba sin entregar los correos de TODO el ciclo, en las dos")
        print("  rutas a la vez (cron_operativo y cron_matutino).\n")

        medico = _medico()
        paciente = _paciente(medico)
        alerta = Alerta.objects.create(
            paciente=paciente,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Alerta de verificacion del Loop E.',
        )
        NotificacionAlerta.objects.all().delete()  # partir de un estado limpio
        notificacion = NotificacionAlerta.objects.create(
            alerta=alerta,
            destinatario='medico-de-guardia@ejemplo.com',
        )
        mail.outbox.clear()

        print("  Estado inicial de la notificacion : {}".format(
            notificacion.estado))
        print("  Correos en la bandeja             : {}".format(
            len(mail.outbox)))

        with _romper('cerrar_checkins_vencidos'):
            try:
                call_command(
                    'cron_operativo',
                    stdout=StringIO(),
                    stderr=StringIO(),
                )
            except CommandError as exc:
                print("\n  El cron termino en error, como debe:")
                print("    {}".format(exc))

        notificacion.refresh_from_db()
        print("\n  Estado final de la notificacion   : {}".format(
            notificacion.estado))
        print("  Correos en la bandeja             : {}".format(
            len(mail.outbox)))
        if mail.outbox:
            print("  Destinatario                      : {}".format(
                mail.outbox[0].to))

        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(len(mail.outbox), 1)

        print("\n  La alerta se entrego. Antes de D14 no salia ningun correo.")


class Verificacion2LaDependenciaSeRespeta(TestCase):
    """La excepción declarada: sin desactivación previa, no se crean check-ins."""

    def test_si_falla_la_desactivacion_no_nacen_checkins(self):
        _titulo("2. D14 — la dependencia clinica declarada se respeta")

        medico = _medico('dr_verif_e2')
        # Paciente que vence HOY: 10 días postoperatorios (P-5).
        paciente = _paciente(
            medico, '2',
            fecha_cirugia=timezone.localdate() - timezone.timedelta(days=10),
        )
        CheckInProgramado.objects.all().delete()

        print("  Paciente con 10 dias postoperatorios (vence hoy).")
        print("  Check-ins antes de correr el cron : {}".format(
            CheckInProgramado.objects.count()))

        salida_err = StringIO()
        with _romper('desactivar_pacientes_vencidos'):
            try:
                call_command(
                    'cron_matutino', stdout=StringIO(), stderr=salida_err)
            except CommandError as exc:
                print("\n  El cron termino en error:")
                print("    {}".format(exc))

        creados = CheckInProgramado.objects.filter(paciente=paciente).count()
        print("\n  Check-ins creados para ese paciente: {}".format(creados))
        print("\n  Lo que se escribio en stderr (lo que ve quien lea el log")
        print("  de Railway a las 6 AM):")
        for linea in salida_err.getvalue().splitlines():
            if linea.strip():
                print("    {}".format(linea.strip()))

        self.assertEqual(creados, 0)
        # El motivo clínico tiene que viajar al log, no quedarse en el código.
        self.assertIn('SILENCIO', salida_err.getvalue())

        print("\n  Cero check-ins, y el log dice POR QUE se omitio.")


class Verificacion3ElDanoQueEvita(TestCase):
    """Por qué 'continuar ante el fallo' a secas habría sido un error."""

    def test_el_checkin_espurio_termina_en_una_alerta_silencio_falsa(self):
        _titulo("3. D14 — el daño que evita la dependencia")
        print("  Este bloque NO prueba el codigo nuevo: prueba que la")
        print("  correccion obvia habria sido un error. Se simula lo que")
        print("  pasaria si crear_checkins_diarios corriera igual.\n")

        medico = _medico('dr_verif_e3')
        paciente = _paciente(
            medico, '3',
            fecha_cirugia=timezone.localdate() - timezone.timedelta(days=10),
        )
        CheckInProgramado.objects.all().delete()
        Alerta.objects.all().delete()

        # El paciente sigue activo porque la desactivación falló. Se le crea el
        # check-in a ciegas — exactamente lo que haría "continuar ante el fallo".
        checkin = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timezone.timedelta(hours=11),
        )
        print("  Check-in creado a ciegas, vencido hace 11 horas (gracia: 10).")
        print("  Estado: {}".format(checkin.estado))

        call_command(
            'cerrar_checkins_vencidos', stdout=StringIO(), stderr=StringIO())

        checkin.refresh_from_db()
        silencios = Alerta.objects.filter(paciente=paciente, tipo='SILENCIO')
        print("\n  Tras cerrar_checkins_vencidos:")
        print("    Estado del check-in   : {}".format(checkin.estado))
        print("    Alertas SILENCIO      : {}".format(silencios.count()))
        for alerta in silencios:
            print("    -> {} / {}".format(alerta.tipo, alerta.severidad))

        self.assertEqual(silencios.count(), 1)

        print("\n  Esa alerta es ESPURIA: el paciente ya no responde porque su")
        print("  seguimiento termino, no porque este en silencio clinico.")
        print("  Por eso el aislamiento del bloque 2 es selectivo y declarado.")


class Verificacion4ElResumenNombraTodo(TestCase):
    """No se rinde en la primera ni informa solo de una."""

    def test_el_error_final_nombra_los_dos_fallos_y_la_omision(self):
        _titulo("4. D14 — el resumen final nombra todo lo que salio mal")

        ejecutadas = []

        class ComandoFalso:
            """Recoge la salida sin depender de un management command real."""

            def __init__(self):
                self.stdout = StringIO()
                self.stderr = StringIO()
                self.style = type('E', (), {
                    'ERROR': staticmethod(lambda t: t),
                    'SUCCESS': staticmethod(lambda t: t),
                })()

        def tarea(nombre, falla=False):
            def correr(*args, **kwargs):
                ejecutadas.append(nombre)
                if falla:
                    raise RuntimeError('fallo forzado')
            return correr

        comando = ComandoFalso()
        tareas = [
            TareaCron('primera'),
            TareaCron('dependiente', depende_de='primera',
                      motivo='Motivo clinico de ejemplo.'),
            TareaCron('segunda'),
            TareaCron('tercera'),
        ]
        fallan = {'primera', 'tercera'}

        def despachar(nombre, *args, **kwargs):
            return tarea(nombre, falla=nombre in fallan)()

        with patch('signos_sintomas.cron_runner.call_command', despachar):
            with self.assertRaises(CommandError) as capturado:
                ejecutar_tareas(comando, 'cron_de_prueba', tareas)

        print("  Fallan 'primera' y 'tercera'. 'dependiente' depende de la")
        print("  primera, asi que debe omitirse. 'segunda' no depende de nadie.\n")
        print("  Tareas que corrieron : {}".format(ejecutadas))
        print("  Error final          : {}".format(capturado.exception))

        self.assertEqual(ejecutadas, ['primera', 'segunda', 'tercera'])
        mensaje = str(capturado.exception)
        for esperado in ('primera', 'tercera', 'dependiente'):
            self.assertIn(esperado, mensaje)

        print("\n  No se detuvo en 'primera', y el resumen nombra los dos")
        print("  fallos Y la omision. Un solo vistazo al log basta.")


class Verificacion5NoSeTragaUnaInterrupcion(TestCase):
    """Aislar fallos no puede volver el cron imposible de matar."""

    def test_un_keyboardinterrupt_sigue_cortando_la_corrida(self):
        _titulo("5. D14 — una interrupcion del proceso sigue cortando")
        print("  El runner captura Exception, no BaseException. Si capturara")
        print("  BaseException, un Ctrl-C o un SIGTERM de Railway se tragaria")
        print("  y el cron seguiria corriendo tareas mientras lo apagan.\n")

        ejecutadas = []

        class ComandoFalso:
            def __init__(self):
                self.stdout = StringIO()
                self.stderr = StringIO()
                self.style = type('E', (), {
                    'ERROR': staticmethod(lambda t: t),
                    'SUCCESS': staticmethod(lambda t: t),
                })()

        def despachar(nombre, *args, **kwargs):
            ejecutadas.append(nombre)
            if nombre == 'primera':
                raise KeyboardInterrupt('Ctrl-C simulado')

        tareas = [TareaCron('primera'), TareaCron('segunda')]

        with patch('signos_sintomas.cron_runner.call_command', despachar):
            with self.assertRaises(KeyboardInterrupt):
                ejecutar_tareas(ComandoFalso(), 'cron_de_prueba', tareas)

        print("  Tareas que corrieron : {}".format(ejecutadas))
        self.assertEqual(ejecutadas, ['primera'])

        print("\n  'segunda' NO corrio. La interrupcion se propago intacta.")
