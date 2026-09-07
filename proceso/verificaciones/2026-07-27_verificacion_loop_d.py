"""Verificación del Loop D — la ejecuta el Arquitecto, no el agente.

QUÉ ES: siete bloques que imprimen en pantalla la evidencia de que las
correcciones del Loop D hacen lo que dicen. No es la suite del proyecto: es la
comprobación independiente que exige el método (`proceso/metodo_de_trabajo.md`,
regla 4) — *el agente que escribió el código es el peor juez de si el código
está bien*.

QUÉ NO ES: una prueba de humo. Cada bloque intenta **romper** el invariante y
muestra qué pasa. Si un bloque pasa sin imprimir nada raro, mirá igual lo que
imprimió: varias correcciones de hoy se detectaron porque un verde estaba
midiendo otra cosa.

CÓMO SE CORRE, desde `Registro_Post_Quirurgico/` (PowerShell):

    cd Registro_Post_Quirurgico
    $env:PYTHONPATH = "../proceso/verificaciones"
    python manage.py test 2026-07-27_verificacion_loop_d -v 2 --noinput
    Remove-Item Env:PYTHONPATH

Corre contra una base de datos de PRUEBA desechable. No toca producción ni la
base local de desarrollo.

QUÉ SE VERIFICA, y contra qué ficha:

    1. D13  la firma de Twilio no depende del entorno en producción
    2. D11  ningún comando operativo escribe nombre ni teléfono de un paciente
    3. D12  capa 1 — el Admin no deja nacer un paciente activo sin responsable
    4. D12  capa 2 — no se puede borrar la cuenta de un médico con pacientes
    5. D12  capa 4 — la base rechaza el paciente activo sin médico…
                     …y sigue aceptando la ficha histórica inactiva
    6. D12  capa 3 — el tablero avisa de los pacientes sin atención efectiva
    7. D12  el seed de producción se niega a fabricar huérfanos
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from signos_sintomas.models import CheckInProgramado, Paciente
from signos_sintomas.templatetags.panel_admin import panel_triage


def _titulo(texto):
    print("\n" + "=" * 72)
    print("  " + texto)
    print("=" * 72)


def _medico(username, **campos):
    """Médico usable por defecto: activo, is_staff y con correo."""
    valores = {
        'is_staff': True,
        'email': '{}@ejemplo.com'.format(username),
    }
    valores.update(campos)
    return get_user_model().objects.create_user(
        username=username, password='x', **valores
    )


def _paciente(medico, sufijo, **campos):
    valores = {
        'nombre_completo': 'Paciente Verificacion {}'.format(sufijo),
        'telefono_whatsapp': '+5730199900{}'.format(sufijo),
        'cedula': 'VERIF-D-{}'.format(sufijo),
        'fecha_cirugia': timezone.localdate(),
        'medico_responsable': medico,
    }
    valores.update(campos)
    return Paciente.objects.create(**valores)


class Verificacion1FirmaDeTwilio(TestCase):
    """D13 — en producción la validación de firma deja de leerse del entorno."""

    def test_ninguna_variable_de_entorno_puede_apagar_la_cerradura(self):
        from Registro_Post_Quirurgico.tests_configuracion import (
            ENTORNO_PRODUCCION_VALIDO,
            cargar_produccion_sobre_base_fresca,
        )

        _titulo("1. D13 — la firma de Twilio no depende del entorno")
        print("  La firma es la UNICA cerradura del webhook: URL publica,")
        print("  sin login y exenta de CSRF.\n")

        casos = [
            ('variable AUSENTE', dict(ENTORNO_PRODUCCION_VALIDO)),
            ('variable VACIA', dict(ENTORNO_PRODUCCION_VALIDO,
                                    TWILIO_VALIDATE_SIGNATURE='')),
            ('variable en False', dict(ENTORNO_PRODUCCION_VALIDO,
                                       TWILIO_VALIDATE_SIGNATURE='False')),
        ]
        for etiqueta, entorno in casos:
            produccion = cargar_produccion_sobre_base_fresca(entorno)
            print("  {:<20} -> TWILIO_VALIDATE_SIGNATURE = {}".format(
                etiqueta, produccion.TWILIO_VALIDATE_SIGNATURE))
            self.assertTrue(produccion.TWILIO_VALIDATE_SIGNATURE)

        print("\n  Las tres dan True. Antes, las dos ultimas daban False.")


class Verificacion2SalidaSinIdentidad(TestCase):
    """D11 — ningún comando operativo escribe identidad del paciente."""

    def test_los_comandos_operativos_no_nombran_a_nadie(self):
        _titulo("2. D11 — la salida operativa no lleva identidad del paciente")

        medico = _medico('dr_verif_phi')
        paciente = _paciente(
            medico, '1',
            fecha_cirugia=timezone.localdate() - timezone.timedelta(days=12),
        )
        Paciente.objects.filter(pk=paciente.pk).update(
            fecha_registro=timezone.now() - timezone.timedelta(days=5)
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timezone.timedelta(hours=1),
        )

        print("  Paciente de prueba: pk={} nombre={!r} telefono={!r}\n".format(
            paciente.pk, paciente.nombre_completo, paciente.telefono_whatsapp))

        for comando in ('enviar_recordatorios', 'desactivar_pacientes_vencidos'):
            salida, errores = StringIO(), StringIO()
            # Nivel INFO forzado A PROPOSITO: en produccion el logger esta en
            # WARNING, asi que una comprobacion con la configuracion normal
            # pasaria en verde con el defecto puesto.
            with self.assertLogs('signos_sintomas', level='INFO') as capturado:
                call_command(comando, stdout=salida, stderr=errores)
            escrito = '\n'.join(
                [salida.getvalue(), errores.getvalue(), *capturado.output]
            )
            print("  --- {} (stdout + stderr + logs a INFO) ---".format(comando))
            for linea in escrito.splitlines():
                if linea.strip():
                    print("    " + linea)
            self.assertNotIn(paciente.nombre_completo, escrito)
            self.assertNotIn(paciente.telefono_whatsapp, escrito)
            print()

        print("  Ni el nombre ni el telefono aparecen. El paciente se ubica")
        print("  por pk, que es lo que ya usa el resto del sistema.")


class Verificacion3PuertaDeEntrada(TestCase):
    """D12 capa 1 — el Admin no deja nacer un paciente activo sin responsable."""

    def test_el_medico_que_guarda_queda_como_responsable(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        _titulo("3. D12 capa 1 — la puerta de entrada (formulario del Admin)")

        medico = _medico('dra_verif_admin')
        ct = ContentType.objects.get_for_model(Paciente)
        medico.user_permissions.add(*Permission.objects.filter(content_type=ct))
        self.client.force_login(medico)

        print("  Se guarda el formulario SIN elegir medico responsable,")
        print("  como medico no-superusuario ({}).\n".format(medico.username))

        self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Formulario',
                'cedula': 'VERIF-D-FORM',
                'telefono_whatsapp': '+573019990099',
                'fecha_cirugia': timezone.localdate().isoformat(),
                'activo': 'on',
            },
            follow=True,
        )

        guardado = Paciente.objects.filter(cedula='VERIF-D-FORM').first()
        print("  Paciente creado : {}".format(bool(guardado)))
        print("  Responsable     : {}".format(
            guardado.medico_responsable if guardado else '—'))
        huerfanos = Paciente.objects.filter(
            activo=True, medico_responsable__isnull=True
        ).count()
        print("  Activos sin medico en la base: {}".format(huerfanos))

        self.assertIsNotNone(guardado)
        self.assertEqual(guardado.medico_responsable, medico)
        self.assertEqual(huerfanos, 0)


class Verificacion4PuertaDeAtras(TestCase):
    """D12 capa 2 — la cuenta de un médico con pacientes no se puede borrar."""

    def test_borrar_al_medico_falla_en_vez_de_dejar_huerfanos(self):
        _titulo("4. D12 capa 2 — la puerta de atras (borrado de la cuenta)")

        medico = _medico('dr_verif_borrado')
        paciente = _paciente(medico, '2')
        print("  Paciente pk={} asignado a {}\n".format(
            paciente.pk, medico.username))

        try:
            medico.delete()
            resultado = 'SE BORRO (mal)'
        except ProtectedError:
            resultado = 'ProtectedError — Django se niega'

        print("  Intento de borrar la cuenta -> {}".format(resultado))
        paciente.refresh_from_db()
        print("  Responsable del paciente tras el intento: {}".format(
            paciente.medico_responsable))

        self.assertEqual(resultado, 'ProtectedError — Django se niega')
        self.assertEqual(paciente.medico_responsable, medico)
        print("\n  Antes era SET_NULL: el paciente quedaba huerfano en silencio.")
        print("  Regla operativa: las cuentas no se borran, se DESACTIVAN, y")
        print("  antes se reasignan sus pacientes activos.")


class Verificacion5GarantiaEnLaBase(TestCase):
    """D12 capa 4 — la restricción de la migración 0028."""

    def test_la_base_rechaza_el_activo_y_acepta_la_ficha_historica(self):
        _titulo("5. D12 capa 4 — la garantia (CheckConstraint, migracion 0028)")
        print("  CHECK (NOT activo OR medico_responsable_id IS NOT NULL)")
        print("  Se intenta esquivar el Admin creando desde el ORM.\n")

        try:
            with transaction.atomic():
                Paciente.objects.create(
                    nombre_completo='Paciente De Script',
                    telefono_whatsapp='+573019990098',
                    cedula='VERIF-D-SCRIPT',
                    fecha_cirugia=timezone.localdate(),
                    medico_responsable=None,
                    activo=True,
                )
            activo = 'SE CREO (mal)'
        except IntegrityError:
            activo = 'IntegrityError — la base lo rechaza'
        print("  Paciente ACTIVO sin medico   -> {}".format(activo))
        self.assertEqual(activo, 'IntegrityError — la base lo rechaza')

        historico = Paciente.objects.create(
            nombre_completo='Ficha Historica',
            telefono_whatsapp='+573019990097',
            cedula='VERIF-D-HIST',
            fecha_cirugia=timezone.localdate() - timezone.timedelta(days=40),
            medico_responsable=None,
            activo=False,
        )
        print("  Paciente INACTIVO sin medico -> creado, pk={}".format(historico.pk))
        self.assertIsNone(historico.medico_responsable)

        print("\n  Las dos cosas importan. La restriccion es condicional a")
        print("  proposito: un NOT NULL obligaria a inventarle un medico a")
        print("  cada ficha historica, que es fabricar una atribucion clinica.")


class Verificacion6AvisoDelTablero(TestCase):
    """D12 capa 3 — el aviso de pacientes sin atención efectiva."""

    def _contador_del_tablero(self):
        peticion = RequestFactory().get('/')
        peticion.user = get_user_model().objects.create_superuser(
            username='super_verif_{}'.format(timezone.now().timestamp()),
            password='x', email='sv@ejemplo.com',
        )
        return panel_triage({'request': peticion})['sin_atencion']

    def test_las_tres_condiciones_avisan_y_el_medico_sano_no(self):
        _titulo("6. D12 capa 3 — el aviso del tablero")
        print("  Cubre lo que ninguna otra capa impide: el medico EXISTE pero")
        print("  no puede atender. El campo esta lleno; nadie mira al paciente.\n")

        casos = [
            ('cuenta desactivada', {'is_active': False}),
            ('sin acceso al panel', {'is_staff': False}),
            ('sin correo', {'email': ''}),
        ]
        for indice, (etiqueta, defecto) in enumerate(casos, start=3):
            medico = _medico('dr_verif_{}'.format(indice), **defecto)
            paciente = _paciente(medico, str(indice))
            contador = self._contador_del_tablero()
            print("  medico {:<20} -> aviso cuenta {} paciente(s)".format(
                etiqueta, contador))
            self.assertEqual(contador, 1)
            paciente.delete()
            medico.delete()

        sano = _medico('dr_verif_sano')
        _paciente(sano, '9')
        contador = self._contador_del_tablero()
        print("  medico {:<20} -> aviso cuenta {} paciente(s)".format(
            'que SI puede atender', contador))
        self.assertEqual(contador, 0)

        print("\n  El ultimo caso es el que importa tanto como los otros tres:")
        print("  un aviso que salta siempre no es un aviso, es ruido que se")
        print("  aprende a ignorar.")

    def test_el_aviso_se_ve_en_el_panel(self):
        _titulo("6b. El aviso es VISIBLE, no solo un numero en el contexto")

        medico = _medico('dr_verif_invisible', email='')
        _paciente(medico, '8')
        superusuario = get_user_model().objects.create_superuser(
            username='super_verif_visible', password='x', email='sv2@ejemplo.com',
        )
        self.client.force_login(superusuario)

        respuesta = self.client.get(reverse('admin:index'))
        visible = 'sin atención efectiva' in respuesta.content.decode()

        print("  Texto 'pacientes activos sin atencion efectiva' en el panel: {}"
              .format(visible))
        self.assertTrue(visible)


class Verificacion7SeedDeProduccion(TestCase):
    """D12 — el comando que fabricaba huérfanos."""

    def test_el_seed_se_niega_con_una_cuenta_que_no_sirve(self):
        _titulo("7. D12 — seed_demo_produccion se niega a fabricar huerfanos")

        escenarios = [
            ('sin ningun usuario en la base', None),
            ('--medico sin acceso al panel', {'is_staff': False}),
            ('--medico sin correo', {'email': ''}),
        ]
        for etiqueta, defecto in escenarios:
            get_user_model().objects.all().delete()
            Paciente.objects.all().delete()
            argumentos = ['--confirmar']
            if defecto is not None:
                cuenta = _medico('dr_seed_verif', **defecto)
                argumentos += ['--medico', cuenta.username]

            errores = StringIO()
            call_command('seed_demo_produccion', *argumentos,
                         stdout=StringIO(), stderr=errores)
            creados = Paciente.objects.filter(cedula__startswith='DEMO-').count()

            print("  {:<32} -> demos creados: {}".format(etiqueta, creados))
            primera_linea = errores.getvalue().strip().splitlines()
            if primera_linea:
                print("      {}".format(primera_linea[0][:110]))
            self.assertEqual(creados, 0)

        print("\n  Antes: el primer caso advertia y creaba los pacientes SIN")
        print("  medico; los otros dos los creaban con una cuenta inutil, y")
        print("  ni la restriccion ni el aviso de huerfanos los detectaban.")
