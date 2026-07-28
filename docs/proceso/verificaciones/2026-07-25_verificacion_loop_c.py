# -*- coding: utf-8 -*-
"""Comprobación del Loop C — para que la ejecute el Arquitecto.

No es la suite del proyecto: es una verificación independiente que MUESTRA la
evidencia de cada corrección en pantalla, en vez de pedir que se confíe en un
punto verde. Corre sobre una base de datos de prueba desechable que Django crea
y destruye sola; no toca la base de desarrollo.

Cómo ejecutarla (PowerShell, desde la carpeta donde está manage.py):

    cd Registro_Post_Quirurgico
    $env:PYTHONPATH = "<carpeta-de-este-archivo>"
    python manage.py test verificacion_loop_c -v 2 --noinput
    Remove-Item Env:PYTHONPATH

Qué esperar: seis bloques con su evidencia impresa y "OK" al final.
"""
import importlib.util
import os
import pathlib
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from signos_sintomas import bot
from signos_sintomas.alert_engine import evaluar_registro
from signos_sintomas.models import CheckInProgramado, Paciente, RegistroDiario

RUTA_SETTINGS = pathlib.Path(settings.BASE_DIR) / "Registro_Post_Quirurgico"


def _medico_archivo():
    """Médico responsable de los pacientes de esta verificación (D12, Loop D).

    Añadido después de escrita: la migración 0028 impide que exista un paciente
    ACTIVO sin médico responsable, y los fixtures de aquí no lo pasaban. Es un
    ajuste de fixture, no de lo que la verificación comprueba — sus aserciones
    no cambiaron.
    """
    medico, _ = get_user_model().objects.get_or_create(
        username='medico_verificacion_loop_c',
        defaults={'is_staff': True, 'email': 'verificacion@ejemplo.com'},
    )
    return medico


def _titulo(texto):
    print("\n" + "=" * 72)
    print("  " + texto)
    print("=" * 72)


def _cargar_settings(archivo, entorno, alias):
    spec = importlib.util.spec_from_file_location(
        "Registro_Post_Quirurgico." + alias, RUTA_SETTINGS / archivo
    )
    modulo = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, entorno):
        spec.loader.exec_module(modulo)
    return modulo


class Verificacion1CabecerasDeProxy(TestCase):
    """Hallazgo 6 — Django ya no cree las cabeceras del proxy sin declararlo."""

    def test_la_confianza_en_el_proxy_es_explicita(self):
        _titulo("1. HALLAZGO 6 — confianza en cabeceras de proxy")

        sin = _cargar_settings("settings.py", {"TRUST_RAILWAY_PROXY": "False"}, "v_sin")
        con = _cargar_settings("settings.py", {"TRUST_RAILWAY_PROXY": "True"}, "v_con")

        print("  SIN declarar confianza (por defecto):")
        print("     USE_X_FORWARDED_HOST   = {}".format(sin.USE_X_FORWARDED_HOST))
        print("     SECURE_PROXY_SSL_HEADER = {}".format(sin.SECURE_PROXY_SSL_HEADER))
        print("  CON TRUST_RAILWAY_PROXY=True (Railway / ngrok):")
        print("     USE_X_FORWARDED_HOST   = {}".format(con.USE_X_FORWARDED_HOST))
        print("     SECURE_PROXY_SSL_HEADER = {}".format(con.SECURE_PROXY_SSL_HEADER))
        print("  -> Antes del Loop C, la primera columna decia True y una tupla:")
        print("     Django creia X-Forwarded-Host/Proto en TODO despliegue.")

        self.assertFalse(sin.USE_X_FORWARDED_HOST)
        self.assertIsNone(sin.SECURE_PROXY_SSL_HEADER)
        self.assertTrue(con.USE_X_FORWARDED_HOST)
        self.assertEqual(con.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))


class Verificacion2VariablesVacias(TestCase):
    """Hallazgo 11 — una variable vacía o con placeholder detiene el arranque."""

    ENTORNO_PROD = {
        "CSRF_TRUSTED_ORIGINS": "https://ejemplo.up.railway.app",
        "REDIS_URL": "redis://localhost:6379/1",
        "EMAIL_DELIVERY_PROVIDER": "resend",
        "RESEND_API_KEY": "clave-de-prueba",
        "RESEND_FROM_EMAIL": "avisos@ejemplo.com",
    }

    def test_el_arranque_se_detiene_nombrando_la_variable(self):
        _titulo("2. HALLAZGO 11 — variables de entorno vacias")

        casos_base = [
            ("SECRET_KEY vacia", {"SECRET_KEY": ""}),
            ("SECRET_KEY con placeholder", {"SECRET_KEY": "<tu-clave-secreta>"}),
            ("DB_NAME en blanco", {"DB_NAME": "   "}),
        ]
        for descripcion, entorno in casos_base:
            with self.assertRaises(ImproperlyConfigured) as cm:
                _cargar_settings("settings.py", entorno, "v_base")
            print("  {:<30} -> {}".format(descripcion, str(cm.exception)[:88] + "..."))

        casos_prod = [
            ("RESEND_API_KEY vacia", dict(self.ENTORNO_PROD, RESEND_API_KEY="")),
            ("CSRF_TRUSTED_ORIGINS vacia", dict(self.ENTORNO_PROD, CSRF_TRUSTED_ORIGINS="")),
        ]
        for descripcion, entorno in casos_prod:
            with self.assertRaises(ImproperlyConfigured) as cm:
                _cargar_settings("settings_production.py", entorno, "v_prod")
            print("  {:<30} -> {}".format(descripcion, str(cm.exception)[:88] + "..."))

        modulo = _cargar_settings("settings_production.py", dict(self.ENTORNO_PROD), "v_ok")
        print("  entorno completo y valido      -> carga sin errores (DEBUG={})".format(modulo.DEBUG))
        print("  -> Antes del Loop C, los cinco primeros arrancaban en silencio.")


class Verificacion3EstadoDelMotor(TestCase):
    """Hallazgo 7 — un fallo del motor en la ruta del bot queda registrado."""

    TELEFONO = "+573009998877"

    def test_el_fallo_queda_anotado_y_el_reporte_sobrevive(self):
        _titulo("3. HALLAZGO 7 — estado de error del motor en la ruta del bot")

        paciente = Paciente.objects.create(medico_responsable=_medico_archivo(),
            
            nombre_completo="Paciente Verificacion Loop C",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        checkin = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

        envia = lambda t: bot.procesar_mensaje("whatsapp:" + self.TELEFONO, t)
        with mock.patch(
            "signos_sintomas.evaluacion_alertas.evaluar_registro",
            side_effect=RuntimeError("temperatura 39.1 del paciente"),
        ):
            for mensaje in ["hola", "37.0", "3", "no", "si, 0", "nada", "78", "16"]:
                envia(mensaje)
            respuesta = envia("si")

        registro = RegistroDiario.objects.get(paciente=paciente)
        checkin.refresh_from_db()
        print("  El motor fallo con RuntimeError('temperatura 39.1 del paciente').")
        print("     estado de evaluacion   = {}".format(registro.estado_evaluacion_alertas))
        print("     intentos consumidos    = {}".format(registro.intentos_evaluacion_alertas))
        print("     error guardado         = '{}'".format(registro.ultimo_error_evaluacion_alertas))
        print("     (solo el NOMBRE de la excepcion: el mensaje puede llevar datos clinicos)")
        print("  El reporte del paciente NO se perdio:")
        print("     check-in               = {}".format(checkin.estado))
        print("     registro vinculado     = {}".format(checkin.registro_id == registro.pk))
        print("     el paciente recibio el cierre neutro = {}".format(respuesta == bot.MSG_CONFIRMACION))
        print("  -> Antes del Loop C: estado PENDIENTE, 0 intentos y error vacio.")

        self.assertEqual(registro.estado_evaluacion_alertas, RegistroDiario.EVALUACION_ERROR)
        self.assertEqual(registro.intentos_evaluacion_alertas, 1)
        self.assertEqual(registro.ultimo_error_evaluacion_alertas, "RuntimeError")
        self.assertNotIn("39.1", registro.ultimo_error_evaluacion_alertas)
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)


class Verificacion4FiltrosDelAdmin(TestCase):
    """Hallazgo 8 — el filtro lateral ya no revela otras cuentas médicas."""

    def test_un_medico_no_ve_las_cuentas_de_sus_colegas(self):
        _titulo("4. HALLAZGO 8 — filtros del Admin")

        User = get_user_model()
        medico_a = User.objects.create_user("dr_verif_a", password="x", is_staff=True)
        medico_b = User.objects.create_user("dr_verif_b", password="x", is_staff=True)
        superusuario = User.objects.create_superuser("super_verif", password="x")
        ct = ContentType.objects.get_for_model(Paciente)
        for medico in (medico_a, medico_b):
            medico.user_permissions.add(*Permission.objects.filter(content_type=ct))
        for indice, medico in enumerate((medico_a, medico_b), start=1):
            Paciente.objects.create(
                nombre_completo="Paciente verif {}".format(indice),
                telefono_whatsapp="+5730188800{}".format(indice),
                cedula="VERIF-000{}".format(indice),
                fecha_cirugia=timezone.localdate(),
                medico_responsable=medico,
            )

        url = reverse("admin:signos_sintomas_paciente_changelist")

        self.client.force_login(medico_a)
        html_medico = self.client.get(url).content.decode()
        self.client.force_login(superusuario)
        html_super = self.client.get(url).content.decode()

        print("  Entrando como dr_verif_a (medico, no superusuario):")
        print("     ve el filtro 'Por medico responsable' = {}".format(
            "medico_responsable__id__exact" in html_medico))
        print("     ve el usuario de su colega dr_verif_b = {}".format("dr_verif_b" in html_medico))
        print("     ve el usuario del superusuario        = {}".format("super_verif" in html_medico))
        print("     ve su propio paciente                 = {}".format("Paciente verif 1" in html_medico))
        print("     ve el paciente del colega             = {}".format("Paciente verif 2" in html_medico))
        print("  Entrando como superusuario:")
        print("     conserva el filtro por medico         = {}".format(
            "medico_responsable__id__exact" in html_super))
        print("  -> Antes del Loop C, el medico leia 'dr_verif_b' y 'super_verif'")
        print("     en la barra lateral. El listado de pacientes nunca estuvo expuesto.")

        self.assertNotIn("medico_responsable__id__exact", html_medico)
        self.assertNotIn("dr_verif_b", html_medico)
        self.assertNotIn("super_verif", html_medico)
        self.assertIn("Paciente verif 1", html_medico)
        self.assertNotIn("Paciente verif 2", html_medico)
        self.assertIn("medico_responsable__id__exact", html_super)


class Verificacion5HinchazonSinCambios(TestCase):
    """D10 — la regla de hinchazón se lee mejor y dispara exactamente igual."""

    def setUp(self):
        self.ahora = timezone.now()
        self.hoy = timezone.localdate(self.ahora)

    def _paciente(self, indice):
        """Un paciente por escenario: las alertas protegen sus registros
        (`Alerta.registro_origen` es PROTECT), así que no se pueden borrar
        entre escenario y escenario."""
        return Paciente.objects.create(medico_responsable=_medico_archivo(),
            
            nombre_completo="Paciente Hinchazon {}".format(indice),
            telefono_whatsapp="+57300777660{}".format(indice),
            fecha_cirugia=self.hoy,
        )

    def _reportar(self, paciente, nivel, dias_atras=0):
        registro = RegistroDiario.objects.create(
            paciente=paciente, temperatura=Decimal("37.0"), dolor_eva=2,
            tiene_drenaje=False, presencia_gases=True, episodios_nauseas=0,
            hinchazon_abdominal=nivel,
        )
        RegistroDiario.objects.filter(pk=registro.pk).update(
            fecha_registro=self.ahora - timedelta(days=dias_atras))
        registro.refresh_from_db()
        return registro

    def _severidad(self, registro):
        alertas = [a for a in evaluar_registro(registro, fecha_referencia=self.hoy)
                   if a.tipo == "ILEO_PARALITICO"]
        return alertas[0].severidad if alertas else "sin alerta"

    def test_la_condicion_media_dispara_igual_que_antes(self):
        _titulo("5. D10 — condicion MEDIA de hinchazon (comportamiento identico)")

        escenarios = [
            ("nada -> (sin dato) -> algo", [("nada", 2)], "algo", "MEDIA"),
            ("algo -> (sin dato) -> algo", [("algo", 2)], "algo", "sin alerta"),
            ("algo -> nada -> mucho     ", [("algo", 2), ("nada", 1)], "mucho", "BAJA"),
            ("nada -> mucho -> algo     ", [("nada", 2), ("mucho", 1)], "algo", "sin alerta"),
            ("nada -> nada -> algo      ", [("nada", 2), ("nada", 1)], "algo", "MEDIA"),
        ]
        for indice, (descripcion, previos, hoy_nivel, esperado) in enumerate(escenarios, start=1):
            paciente = self._paciente(indice)
            for nivel, dias in previos:
                self._reportar(paciente, nivel, dias_atras=dias)
            obtenido = self._severidad(self._reportar(paciente, hoy_nivel))
            print("  {}  ->  {:<12} (esperado {})".format(descripcion, obtenido, esperado))
            self.assertEqual(obtenido, esperado)

        print("  -> El primer escenario es el que la expresion vieja escondia: sin dato")
        print("     de ayer no puede comprobarse el 'sostenido' y aun asi alerta.")
        print("     Se conserva IDENTICO: cambiarlo seria mover un umbral clinico.")


class Verificacion6Medianoche(TestCase):
    """C7 — un escenario de varios días ya no depende de la hora de la corrida."""

    @freeze_time("2026-07-24 23:59:59.90-05:00", auto_tick_seconds=0.05)
    def test_un_escenario_de_tres_dias_resiste_el_cruce_de_medianoche(self):
        _titulo("6. C7 — blindaje contra la medianoche")

        ahora = timezone.now()
        hoy = timezone.localdate(ahora)
        paciente = Paciente.objects.create(medico_responsable=_medico_archivo(),
            
            nombre_completo="Paciente Medianoche",
            telefono_whatsapp="+573005554433",
            fecha_cirugia=hoy,
        )
        registros = []
        for dias_atras in (2, 1, 0):
            registro = RegistroDiario.objects.create(
                paciente=paciente, temperatura=Decimal("37.0"), dolor_eva=2,
                tiene_drenaje=False, presencia_gases=False, episodios_nauseas=0,
            )
            RegistroDiario.objects.filter(pk=registro.pk).update(
                fecha_registro=ahora - timedelta(days=dias_atras))
            registros.append(registro)
        registros[-1].refresh_from_db()

        alertas = [a for a in evaluar_registro(registros[-1], fecha_referencia=hoy)
                   if a.tipo == "ILEO_PARALITICO"]
        severidad = alertas[0].severidad if alertas else "sin alerta"

        print("  Reloj falso arrancando a 100 ms de la medianoche de Bogota,")
        print("  adelantando 50 ms por cada lectura (el cruce ocurre a mitad del escenario).")
        print("  Tres dias consecutivos sin gases -> {}".format(severidad))
        print("  -> El motor agrupa por fecha_registro__date y calcula con localdate():")
        print("     nunca tuvo el bug. Lo fragil eran los fixtures de las pruebas, y")
        print("     ahora las cinco clases afectadas corren con el reloj anclado.")

        self.assertEqual(severidad, "ALTA")
