from datetime import datetime, time as hora_del_dia, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from . import bot
from .alert_engine import evaluar_registro

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
from .models import (
    Alerta,
    CheckInProgramado,
    ConversacionWhatsApp,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RecepcionWebhookTwilio,
    RegistroDiario,
)


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
            'email': '{}@ejemplo.com'.format(username),
        },
    )
    return medico


@freeze_time(ANCLA_MEDIANOCHE)
class AlertEngineTests(TestCase):
    def test_temperatura_alta_crea_alerta_sepsis(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Prueba",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("38.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(Alerta.objects.count(), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "ALTA")
        deteccion = DeteccionAlerta.objects.get(alerta=alertas[0])
        self.assertEqual(deteccion.registro, registro)
        self.assertIsNone(deteccion.checkin)
        self.assertEqual(deteccion.severidad_detectada, 'ALTA')

    def test_drenaje_purulento_crea_alerta_fuga_anastomotica(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Drenaje",
            telefono_whatsapp="+573004445566",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=True,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_nauseas_mayor_a_tres_crea_alerta_ileo_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nauseas",
            telefono_whatsapp="+573007778899",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=4,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "ILEO_PARALITICO")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_tres_dias_consecutivos_sin_gases_crea_alerta_ileo_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Gases",
            telefono_whatsapp="+573006661122",
            fecha_cirugia=timezone.localdate(),        )
        anteayer = timezone.now() - timedelta(days=2)
        ayer = timezone.now() - timedelta(days=1)

        r1 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=False,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=r1.pk).update(fecha_registro=anteayer)

        r2 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=False,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=r2.pk).update(fecha_registro=ayer)

        r3 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=False,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(r3)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "ILEO_PARALITICO")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_registro_sin_red_flags_no_crea_alertas(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Estable",
            telefono_whatsapp="+573005551234",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])
        self.assertEqual(Alerta.objects.count(), 0)

    def test_registro_con_varias_red_flags_crea_varias_alertas(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Multiple",
            telefono_whatsapp="+573005550000",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("38.5"),
            dolor_eva=4,
            tiene_drenaje=True,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=4,
        )

        alertas = evaluar_registro(registro)
        tipos_alerta = {alerta.tipo for alerta in alertas}

        self.assertEqual(len(alertas), 3)
        self.assertEqual(Alerta.objects.count(), 3)
        self.assertEqual(
            tipos_alerta,
            {"SEPSIS", "FUGA_ANASTOMOTICA", "ILEO_PARALITICO"},
        )

    def test_valores_limite_no_crean_alertas(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Limite",
            telefono_whatsapp="+573005559999",
            fecha_cirugia=timezone.localdate(),        )
        # 37.4°C: justo por debajo del umbral de subfebrícula (37.5°C)
        # episodios_nauseas=0: con la regla nueva cualquier episodio >= 1
        # genera alerta, se usa 0 para mantener la intención original del test
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.4"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])
        self.assertEqual(Alerta.objects.count(), 0)

    def test_drenaje_seroso_con_tiene_drenaje_crea_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Seroso",
            telefono_whatsapp="+573001110001",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "BAJA")

    def test_drenaje_hematico_crea_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hematico",
            telefono_whatsapp="+573001110002",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="hematico",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_drenaje_turbio_crea_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Turbio",
            telefono_whatsapp="+573001110003",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=True,
            aspecto_drenaje="turbio",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "FUGA_ANASTOMOTICA")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_sin_drenaje_no_genera_alerta_drenaje(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Drenaje",
            telefono_whatsapp="+573001110004",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje="sin_drenaje",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])

    def test_tiene_drenaje_null_no_genera_alerta_drenaje(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Legacy",
            telefono_whatsapp="+573001110005",
            fecha_cirugia=timezone.localdate(),        )
        # tiene_drenaje=None simula un registro anterior a esta versión
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            aspecto_drenaje="purulento",
            presencia_gases=True,
            episodios_nauseas=0,
        )

        alertas = evaluar_registro(registro)

        self.assertEqual(alertas, [])

    def test_temperatura_379_crea_alerta_sepsis_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Temp Alta",
            telefono_whatsapp="+573008880001",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.9"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "ALTA")

    def test_subfebricula_un_solo_dia_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Subfebricula Un Dia",
            telefono_whatsapp="+573008880002",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.6"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(alertas, [])

    def test_subfebricula_dos_dias_consecutivos_crea_alerta_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Subfebricula Persistente",
            telefono_whatsapp="+573008880003",
            fecha_cirugia=timezone.localdate(),        )
        ayer = timezone.now() - timedelta(days=1)
        registro_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.6"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=registro_ayer.pk).update(
            fecha_registro=ayer
        )
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.7"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_hoy)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].tipo, "SEPSIS")
        self.assertEqual(alertas[0].severidad, "MEDIA")

    def test_temperatura_normal_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Temp Normal",
            telefono_whatsapp="+573008880004",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("36.8"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(alertas, [])

    def test_un_dia_sin_gases_crea_alerta_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Gases Un Dia",
            telefono_whatsapp="+573008880010",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_gases = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_gases), 1)
        self.assertEqual(alertas_gases[0].severidad, "BAJA")

    def test_dos_dias_consecutivos_sin_gases_crea_alerta_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Gases Dos Dias",
            telefono_whatsapp="+573008880011",
            fecha_cirugia=timezone.localdate(),        )
        ayer = timezone.now() - timedelta(days=1)
        registro_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=registro_ayer.pk).update(
            fecha_registro=ayer
        )
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_hoy)
        alertas_gases = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_gases), 1)
        self.assertEqual(alertas_gases[0].severidad, "MEDIA")

    def test_dos_registros_mismo_dia_sin_gases_cuenta_como_un_dia(self):
        # Caso clave del nuevo modelo de 2 check-ins/día: 2 registros del
        # MISMO día sin gases deben contar como 1 día, no como "2 días".
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dos Checkins Mismo Dia",
            telefono_whatsapp="+573008880012",
            fecha_cirugia=timezone.localdate(),        )
        RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        registro_2 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_2)
        alertas_gases = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_gases), 1)
        self.assertEqual(alertas_gases[0].severidad, "BAJA")

    def test_gases_en_un_checkin_del_dia_anula_alerta_ese_dia(self):
        # Si hubo al menos un positivo en el día, ese día cuenta como
        # "con gases" — sin importar que otro check-in del mismo día
        # haya sido negativo.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Gases Parcial",
            telefono_whatsapp="+573008880013",
            fecha_cirugia=timezone.localdate(),        )
        RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        registro_2 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_2)
        alertas_gases = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_gases), 0)

    def test_un_episodio_nausea_crea_alerta_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nausea Baja",
            telefono_whatsapp="+573008880020",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=1,
        )
        alertas = evaluar_registro(registro)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 1)
        self.assertEqual(alertas_nauseas[0].severidad, "BAJA")

    def test_cinco_episodios_nausea_crea_alerta_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nausea Alta",
            telefono_whatsapp="+573008880021",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=5,
        )
        alertas = evaluar_registro(registro)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 1)
        self.assertEqual(alertas_nauseas[0].severidad, "ALTA")

    def test_nauseas_suma_dos_checkins_mismo_dia(self):
        # Caso clave del modelo de 2 check-ins/día: 2 registros del mismo
        # día con 2 episodios cada uno deben SUMAR 4 → MEDIA, no contarse
        # por separado como 2+2 sin sumar.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nausea Suma Dia",
            telefono_whatsapp="+573008880022",
            fecha_cirugia=timezone.localdate(),        )
        RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=2,
        )
        registro_2 = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=2,
        )
        alertas = evaluar_registro(registro_2)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 1)
        self.assertEqual(alertas_nauseas[0].severidad, "MEDIA")

    def test_nauseas_persistencia_dos_dias_escala_a_media(self):
        # 1 episodio ayer + 1 episodio hoy (cada uno solo daría BAJA por
        # suma) → la persistencia de 2 días consecutivos escala a MEDIA.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nausea Persistente",
            telefono_whatsapp="+573008880023",
            fecha_cirugia=timezone.localdate(),        )
        ayer = timezone.now() - timedelta(days=1)
        registro_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=1,
        )
        RegistroDiario.objects.filter(pk=registro_ayer.pk).update(
            fecha_registro=ayer
        )
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=1,
        )
        alertas = evaluar_registro(registro_hoy)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 1)
        self.assertEqual(alertas_nauseas[0].severidad, "MEDIA")

    def test_sin_nauseas_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Nauseas",
            telefono_whatsapp="+573008880024",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 0)

    def test_nauseas_persistencia_cuatro_dias_escala_a_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nausea Persistente Larga",
            telefono_whatsapp="+573008880025",
            fecha_cirugia=timezone.localdate(),        )
        for dias_atras in [3, 2, 1]:
            fecha = timezone.now() - timedelta(days=dias_atras)
            reg = RegistroDiario.objects.create(
                paciente=paciente,
                temperatura=Decimal("37.0"),
                dolor_eva=3,
                tiene_drenaje=False,
                presencia_gases=True,
                episodios_nauseas=1,
            )
            RegistroDiario.objects.filter(pk=reg.pk).update(fecha_registro=fecha)
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=1,
        )
        alertas = evaluar_registro(registro_hoy)
        alertas_nauseas = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(alertas_nauseas), 1)
        self.assertEqual(alertas_nauseas[0].severidad, "ALTA")

    def test_dolor_pod1_eva6_crea_alerta_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dolor POD1",
            telefono_whatsapp="+573008880030",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=6,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_dolor = [a for a in alertas if a.tipo == "DOLOR_AGUDO"]
        self.assertEqual(len(alertas_dolor), 1)
        self.assertEqual(alertas_dolor[0].severidad, "BAJA")

    def test_dolor_pod1_eva9_crea_alerta_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dolor POD1 Alto",
            telefono_whatsapp="+573008880031",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=9,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_dolor = [a for a in alertas if a.tipo == "DOLOR_AGUDO"]
        self.assertEqual(len(alertas_dolor), 1)
        self.assertEqual(alertas_dolor[0].severidad, "ALTA")

    def test_dolor_pod6_eva6_crea_alerta_media(self):
        # En POD6+, EVA 6 cae en rango MEDIA (5-6), distinto a POD1-2
        # donde EVA 6 sería BAJA. Verifica que la ventana correcta aplique.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dolor POD6",
            telefono_whatsapp="+573008880032",
            fecha_cirugia=timezone.localdate() - timedelta(days=6),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=6,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_dolor = [a for a in alertas if a.tipo == "DOLOR_AGUDO"]
        self.assertEqual(len(alertas_dolor), 1)
        self.assertEqual(alertas_dolor[0].severidad, "MEDIA")

    def test_dolor_pod6_eva2_no_crea_alerta(self):
        # EVA 2 en POD6+ está por debajo del umbral BAJA (3) — sin alerta.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dolor POD6 Bajo",
            telefono_whatsapp="+573008880033",
            fecha_cirugia=timezone.localdate() - timedelta(days=6),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        alertas_dolor = [a for a in alertas if a.tipo == "DOLOR_AGUDO"]
        self.assertEqual(len(alertas_dolor), 0)

    def test_dolor_tendencia_alcista_escala_severidad(self):
        # POD5: EVA 2 y 2 (promedio 2) hace 3-4 días, luego EVA 5 hoy y
        # ayer (promedio 5) -> delta = 3, debe escalar un nivel sobre lo
        # que daría la tabla sola (POD3-5, EVA5 = BAJA por tabla -> sube
        # a MEDIA por tendencia).
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dolor Tendencia",
            telefono_whatsapp="+573008880034",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),        )
        for dias_atras, eva in [(3, 2), (2, 2)]:
            fecha = timezone.now() - timedelta(days=dias_atras)
            reg = RegistroDiario.objects.create(
                paciente=paciente,
                temperatura=Decimal("37.0"),
                dolor_eva=eva,
                tiene_drenaje=False,
                presencia_gases=True,
                episodios_nauseas=0,
            )
            RegistroDiario.objects.filter(pk=reg.pk).update(fecha_registro=fecha)
        fecha_ayer = timezone.now() - timedelta(days=1)
        reg_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=5,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        RegistroDiario.objects.filter(pk=reg_ayer.pk).update(fecha_registro=fecha_ayer)
        registro_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=5,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro_hoy)
        alertas_dolor = [a for a in alertas if a.tipo == "DOLOR_AGUDO"]
        self.assertEqual(len(alertas_dolor), 1)
        self.assertEqual(alertas_dolor[0].severidad, "MEDIA")

    def test_no_tolero_liquidos_un_dia_crea_alerta_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente No Tolera Liquidos",
            telefono_whatsapp="+573008880050",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            tolero_liquidos=False,
        )
        alertas = evaluar_registro(registro)
        alertas_oral = [a for a in alertas if a.tipo == "INTOLERANCIA_ORAL"]
        self.assertEqual(len(alertas_oral), 1)
        self.assertEqual(alertas_oral[0].severidad, "MEDIA")

    def test_no_tolero_liquidos_dos_dias_crea_alerta_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente No Tolera Dos Dias",
            telefono_whatsapp="+573008880051",
            fecha_cirugia=timezone.localdate(),        )
        ayer = timezone.now() - timedelta(days=1)
        reg_ayer = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            tolero_liquidos=False,
        )
        RegistroDiario.objects.filter(pk=reg_ayer.pk).update(fecha_registro=ayer)
        reg_hoy = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            tolero_liquidos=False,
        )
        alertas = evaluar_registro(reg_hoy)
        alertas_oral = [a for a in alertas if a.tipo == "INTOLERANCIA_ORAL"]
        self.assertEqual(len(alertas_oral), 1)
        self.assertEqual(alertas_oral[0].severidad, "ALTA")

    def test_tolero_liquidos_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Tolera Liquidos",
            telefono_whatsapp="+573008880052",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            tolero_liquidos=True,
        )
        alertas = evaluar_registro(registro)
        alertas_oral = [a for a in alertas if a.tipo == "INTOLERANCIA_ORAL"]
        self.assertEqual(len(alertas_oral), 0)

    def test_tolero_liquidos_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Liquidos Null",
            telefono_whatsapp="+573008880053",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            tolero_liquidos=None,
        )
        alertas = evaluar_registro(registro)
        alertas_oral = [a for a in alertas if a.tipo == "INTOLERANCIA_ORAL"]
        self.assertEqual(len(alertas_oral), 0)

    # --- Regla 7: hinchazón abdominal ---
    # Valores neutros en gases (True) y náuseas (0) para que la única
    # alerta ILEO_PARALITICO posible sea la de hinchazón.

    def _crear_hinchazon(self, paciente, nivel, dias_atras=0):
        reg = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            hinchazon_abdominal=nivel,
        )
        if dias_atras:
            fecha = timezone.now() - timedelta(days=dias_atras)
            RegistroDiario.objects.filter(pk=reg.pk).update(fecha_registro=fecha)
        return reg

    def test_hinchazon_empeoramiento_puntual_crea_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Puntual",
            telefono_whatsapp="+573008880060",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "nada", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "BAJA")

    def test_hinchazon_empeoramiento_sostenido_crea_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Sostenido",
            telefono_whatsapp="+573008880061",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "MEDIA")

    def test_hinchazon_subida_progresiva_crea_media(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Progresiva",
            telefono_whatsapp="+573008880062",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "nada", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "MEDIA")

    def test_hinchazon_fluctuacion_que_mejora_no_crea_media(self):
        # antier algo, ayer mucho, hoy algo → hoy bajó, no escala.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Fluctua",
            telefono_whatsapp="+573008880063",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "mucho", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 0)

    def test_hinchazon_estable_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Estable",
            telefono_whatsapp="+573008880064",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 0)

    def test_hinchazon_mucho_4_dias_crea_alta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Mucho 4d",
            telefono_whatsapp="+573008880065",
            fecha_cirugia=timezone.localdate(),        )
        self._crear_hinchazon(paciente, "mucho", dias_atras=3)
        self._crear_hinchazon(paciente, "mucho", dias_atras=2)
        self._crear_hinchazon(paciente, "mucho", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "ALTA")

    def test_hinchazon_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon Null",
            telefono_whatsapp="+573008880066",
            fecha_cirugia=timezone.localdate(),        )
        reg_hoy = self._crear_hinchazon(paciente, None)
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 0)

    # --- Regla 8: frecuencia cardíaca (taquicardia) ---

    def _crear_fc(self, paciente, fc):
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            frecuencia_cardiaca=fc,
        )

    def test_fc_100_no_crea_alerta(self):
        # Borde inferior: 100 lpm está por debajo del umbral BAJA (101).
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 100",
            telefono_whatsapp="+573008880070",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 100))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 0)

    def test_fc_101_crea_baja(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 101",
            telefono_whatsapp="+573008880071",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 101))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_109_crea_baja(self):
        # Borde superior de BAJA (109).
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 109",
            telefono_whatsapp="+573008880072",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 109))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_110_crea_media(self):
        # Borde inferior de MEDIA (110) — umbral CREWS 2022.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 110",
            telefono_whatsapp="+573008880073",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 110))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_149_crea_media(self):
        # Borde superior de MEDIA (149).
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 149",
            telefono_whatsapp="+573008880074",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 149))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_150_crea_alta(self):
        # Borde inferior de ALTA (150) — escalamiento inmediato.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC 150",
            telefono_whatsapp="+573008880075",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 150))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "ALTA")

    def test_fc_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FC Null",
            telefono_whatsapp="+573008880076",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, None))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 0)

    def test_frecuencia_respiratoria_no_genera_alerta(self):
        # FR es solo-dashboard: aunque el valor sea alto (30 rpm) y el
        # resto del registro sea neutro, el alert_engine NO debe generar
        # ninguna alerta. (Outersterp 2025: 77% de falsas alertas venían
        # del sensor de FR — decisión de no evaluarla.)
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FR Alta",
            telefono_whatsapp="+573008880080",
            fecha_cirugia=timezone.localdate(),        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            frecuencia_respiratoria=30,
        )
        alertas = evaluar_registro(registro)
        self.assertEqual(alertas, [])


class RegistroDiarioModelTests(TestCase):
    """Cálculo de dia_postoperatorio en RegistroDiario.save().
    El campo es PositiveSmallIntegerField (CHECK >= 0): el save nunca debe
    producir un valor negativo, ni siquiera con fecha_cirugia futura."""

    def _crear_registro(self, paciente):
        # Valores neutros: ninguna regla del alert_engine se dispara,
        # así el único factor bajo prueba es dia_postoperatorio.
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )

    def test_fecha_cirugia_futura_no_crashea_y_da_dia_cero(self):
        # Regresión del bug de producción: paciente pre-registrado con
        # cirugía programada a futuro. (hoy - mañana).days = -1 violaría el
        # CHECK del PositiveSmallIntegerField y haría crashear el save().
        # El clamp a 0 lo evita y conserva el registro para el médico.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Cirugia Futura",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() + timedelta(days=1),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_hoy_da_dia_cero(self):
        # Borde exacto: cirugía hoy → POD 0 (el día de la cirugía).
        # Aquí el .days ya es 0 natural, sin intervención del clamp.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Cirugia Hoy",
            telefono_whatsapp="+573009990002",
            fecha_cirugia=timezone.localdate(),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_pasada_calcula_dia_correcto(self):
        # Camino normal: el clamp NO debe alterar el cálculo positivo.
        # Operado hace 5 días → POD 5. Guarda contra un max(0, ...) mal
        # escrito que aplastara también los valores válidos.
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente POD5",
            telefono_whatsapp="+573009990003",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 5)

    def test_registro_historico_usa_su_fecha_y_congela_el_pod(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Histórico",
            telefono_whatsapp="+573009990004",
            fecha_cirugia=timezone.localdate() - timedelta(days=10),
        )
        fecha_historica = timezone.now() - timedelta(days=4)
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            fecha_registro=fecha_historica,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        self.assertEqual(registro.dia_postoperatorio, 6)

        paciente.fecha_cirugia = timezone.localdate() - timedelta(days=20)
        paciente.save()
        registro.temperatura = Decimal("37.1")
        registro.save()
        registro.refresh_from_db()

        self.assertEqual(registro.dia_postoperatorio, 6)


class BotWhatsAppTests(TestCase):
    TELEFONO = "+573001112233"
    TELEFONO_TWILIO = "whatsapp:+573001112233"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Bot",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        # Bloque 3: el bot requiere CheckInProgramado PENDIENTE para iniciar el flujo.
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def _completar_flujo(self, gases_nauseas="sí, 0", temperatura="37.0",
                         tiene_drenaje="sí", aspecto="1", cantidad="normal",
                         hinchazon="nada", frecuencia_cardiaca="78",
                         frecuencia_respiratoria="16", tolero_liquidos="sí"):
        """Recorre las 10 preguntas y devuelve la respuesta final del bot."""
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")          # -> temperatura
        bot.procesar_mensaje(self.TELEFONO_TWILIO, temperatura)     # -> dolor
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")             # -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, tiene_drenaje)   # -> aspecto (si sí)
        bot.procesar_mensaje(self.TELEFONO_TWILIO, aspecto)         # -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, cantidad)        # -> gases/nauseas
        bot.procesar_mensaje(self.TELEFONO_TWILIO, gases_nauseas)   # -> hinchazón
        bot.procesar_mensaje(self.TELEFONO_TWILIO, hinchazon)       # -> frecuencia cardíaca
        bot.procesar_mensaje(self.TELEFONO_TWILIO, frecuencia_cardiaca)      # -> frecuencia respiratoria
        bot.procesar_mensaje(self.TELEFONO_TWILIO, frecuencia_respiratoria)  # -> tolerancia líquidos
        return bot.procesar_mensaje(self.TELEFONO_TWILIO, tolero_liquidos)

    def test_paciente_no_registrado(self):
        respuesta = bot.procesar_mensaje("whatsapp:+570000000000", "hola")
        self.assertEqual(respuesta, bot.MSG_NO_REGISTRADO)
        self.assertEqual(ConversacionWhatsApp.objects.count(), 0)

    def test_primer_mensaje_inicia_cuestionario(self):
        self._crear_paciente()
        checkin = CheckInProgramado.objects.get()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertEqual(conv.checkin_actual, checkin)

    def test_flujo_completo_crea_registro(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(
            temperatura="37.0", aspecto="1", cantidad="normal", gases_nauseas="sí, 0"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        self.assertEqual(RegistroDiario.objects.count(), 1)
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.temperatura, Decimal("37.0"))
        self.assertEqual(registro.dolor_eva, 3)
        self.assertTrue(registro.tiene_drenaje)
        self.assertEqual(registro.aspecto_drenaje, "seroso")  # opción "1"
        self.assertEqual(registro.cantidad_drenaje, "normal")
        self.assertTrue(registro.presencia_gases)
        self.assertEqual(registro.episodios_nauseas, 0)
        self.assertEqual(registro.hinchazon_abdominal, "nada")
        self.assertEqual(registro.frecuencia_cardiaca, 78)
        self.assertEqual(registro.frecuencia_respiratoria, 16)
        self.assertTrue(registro.tolero_liquidos)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_COMPLETADO)
        self.assertIsNone(conv.checkin_actual)
        self.assertIsNone(conv.temp_temperatura)  # parciales limpiados
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )

    def test_alerta_no_se_muestra_al_paciente(self):
        # Bloque B: evaluar_registro ahora corre de forma síncrona dentro de
        # _crear_registro, así que la alerta ya existe al armar la respuesta.
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # dispara SEPSIS (ALTA)
        # La alerta se crea para el oncólogo...
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)
        # ...y el paciente recibe el cierre de severidad ALTA, pero SIN ver el
        # tipo de alerta ni los valores que la dispararon.
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)
        self.assertNotIn("sepsis", respuesta.lower())
        self.assertNotIn("alerta", respuesta.lower())
        self.assertNotIn("38.5", respuesta)

    def test_temperatura_invalida_reintenta(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no sé")
        self.assertEqual(respuesta, bot.MSG_REINTENTO_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_sin_drenaje_salta_pregunta_cantidad(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")           # dolor -> tiene_drenaje
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no")  # no tiene drenaje
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_GASES_NAUSEAS)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_GASES_NAUSEAS)
        self.assertFalse(conv.temp_tiene_drenaje)
        self.assertEqual(conv.temp_aspecto_drenaje, "sin_drenaje")
        self.assertEqual(conv.temp_cantidad_drenaje, "sin_drenaje")

    def test_extraccion_ml_opcional(self):
        self._crear_paciente()
        self._completar_flujo(aspecto="1", cantidad="poco, 30ml")
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.cantidad_drenaje, "poco")
        self.assertEqual(registro.volumen_drenaje_ml, 30)

    def test_ya_registrado_hoy(self):
        self._crear_paciente()
        self._completar_flujo()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_YA_REGISTRADO)
        self.assertEqual(RegistroDiario.objects.count(), 1)

    def test_duda_fiebre_responde_predefinido(self):
        self._crear_paciente()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "¿es normal tener fiebre?")
        self.assertEqual(respuesta, bot.RESP_FIEBRE)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_duda_desconocida_responde_fallback(self):
        self._crear_paciente()
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "¿puedo bañarme hoy?")
        self.assertEqual(respuesta, bot.RESP_FALLBACK)

    def test_respuestas_predefinidas_no_revelan_umbrales_clinicos(self):
        """Ninguna respuesta al paciente puede contener un umbral clínico (D4).

        Regla de diseño no negociable del bot (CLAUDE.md): el paciente nunca ve
        los valores que disparan una alerta. Un umbral en la FAQ además puede
        contradecir al motor —RESP_FIEBRE decía 38 °C mientras el motor alerta
        desde 37.9— y le pide al paciente que se auto-evalúe cuando el sistema
        ya lo está midiendo dos veces al día.

        Este test no vigila una redacción concreta: vigila que no vuelva a
        aparecer una cifra clínica, sea cual sea el texto que apruebe el médico.
        """
        import re

        patron_umbral = re.compile(
            r'\d+([.,]\d+)?\s*(°\s*)?(c\b|grados|lpm|rpm|/10)',
            re.IGNORECASE,
        )
        for nombre in ('RESP_FIEBRE', 'RESP_COMER', 'RESP_DOLOR', 'RESP_FALLBACK'):
            texto = getattr(bot, nombre)
            encontrado = patron_umbral.search(texto)
            self.assertIsNone(
                encontrado,
                f'{nombre} expone un umbral clínico al paciente: '
                f'{encontrado.group(0) if encontrado else ""!r}',
            )

    def test_gases_nauseas_ambiguo_reintenta(self):
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")      # dolor -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")     # tiene_drenaje -> aspecto
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")      # aspecto -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal") # cantidad -> gases/nauseas
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "no sé")
        self.assertEqual(respuesta, bot.MSG_REINTENTO_GASES_NAUSEAS)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_GASES_NAUSEAS)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_fc_saltar_guarda_none_y_avanza(self):
        # A2: paciente sin oxímetro usa palabra de salto en FC → None, avanza a FR.
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí, 0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "nada")
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "saltar")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_FRECUENCIA_RESPIRATORIA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertIsNone(conv.temp_frecuencia_cardiaca)
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_RESPIRATORIA)

    def test_fr_omitir_guarda_none_y_flujo_completa(self):
        # A2: paciente usa "omitir" en FR → None guardado en RegistroDiario.
        self._crear_paciente()
        respuesta = self._completar_flujo(
            frecuencia_cardiaca="78", frecuencia_respiratoria="omitir"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        registro = RegistroDiario.objects.get()
        self.assertEqual(registro.frecuencia_cardiaca, 78)
        self.assertIsNone(registro.frecuencia_respiratoria)

    def test_flujo_completo_sin_fc_ni_fr_crea_registro_con_nulls(self):
        # A2: ambas variables saltadas → RegistroDiario creado con FC=None, FR=None.
        self._crear_paciente()
        respuesta = self._completar_flujo(
            frecuencia_cardiaca="no sé", frecuencia_respiratoria="sin dato"
        )
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        registro = RegistroDiario.objects.get()
        self.assertIsNone(registro.frecuencia_cardiaca)
        self.assertIsNone(registro.frecuencia_respiratoria)

    def test_fc_fuera_de_rango_reintenta(self):
        # Un valor fuera del rango 30-250 lpm se rechaza y pide reintento,
        # sin avanzar de estado ni crear registro.
        self._crear_paciente()
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.0")
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "3")        # dolor -> tiene_drenaje
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí")       # tiene_drenaje -> aspecto
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "1")        # aspecto -> cantidad
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "normal")   # cantidad -> gases/nauseas
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "sí, 0")    # gases -> hinchazón
        bot.procesar_mensaje(self.TELEFONO_TWILIO, "nada")     # hinchazón -> frecuencia cardíaca
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "999")  # fuera de rango
        self.assertEqual(respuesta, bot.MSG_REINTENTO_FRECUENCIA_CARDIACA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(
            conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA
        )
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_sin_checkin_pendiente_muestra_mensaje(self):
        """Bloque 3: si no hay CheckInProgramado PENDIENTE hoy, el bot devuelve MSG_SIN_CHECKIN."""
        Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin CheckIn",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        # Sin CheckInProgramado → el bot responde MSG_SIN_CHECKIN y no crea RegistroDiario
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_SIN_CHECKIN)
        self.assertEqual(RegistroDiario.objects.count(), 0)

    def test_ya_registrado_via_checkin_completado(self):
        """Bloque 3: si el CheckInProgramado del día ya está COMPLETADO, responde MSG_YA_REGISTRADO."""
        self._crear_paciente()
        # Completar el flujo → checkin queda COMPLETADO
        self._completar_flujo()
        # Nuevo mensaje del mismo día
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_YA_REGISTRADO)

    def test_checkin_vinculado_al_registro_al_completar(self):
        """Bloque 3: al completar el flujo, el CheckInProgramado queda COMPLETADO y vinculado al RegistroDiario."""
        self._crear_paciente()
        self._completar_flujo()
        registro = RegistroDiario.objects.get()
        checkin = CheckInProgramado.objects.get()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(checkin.registro, registro)
        self.assertIsNotNone(checkin.fecha_respuesta)

    def test_con_dos_turnos_completa_el_checkin_fijado_al_iniciar(self):
        paciente = self._crear_paciente()
        primero = CheckInProgramado.objects.get(orden=1)
        segundo = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=2,
            etiqueta=CheckInProgramado.ETIQUETA_TARDE,
            hora_programada=timezone.now(),
        )

        self._completar_flujo()

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertIsNotNone(primero.registro_id)
        self.assertEqual(segundo.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertIsNone(segundo.registro_id)


@freeze_time(ANCLA_MEDIANOCHE)
class BotMensajeCierreAlertaTests(TestCase):
    """Bloque B — mensaje de cierre del bot según severidad de las alertas
    generadas por el check-in. El paciente nunca ve el tipo de alerta ni los
    valores; solo una recomendación de acción tranquilizadora."""

    TELEFONO = "+573001114455"
    TELEFONO_TWILIO = "whatsapp:+573001114455"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Cierre",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def _completar_flujo(self, temperatura="37.0", aspecto="1", gases_nauseas="sí, 0"):
        """Recorre las 10 preguntas con drenaje presente. Devuelve la respuesta final."""
        env = lambda t: bot.procesar_mensaje(self.TELEFONO_TWILIO, t)
        env("hola")            # -> temperatura
        env(temperatura)       # -> dolor
        env("3")               # -> tiene_drenaje
        env("sí")              # -> aspecto
        env(aspecto)           # -> cantidad
        env("normal")          # -> gases/nauseas
        env(gases_nauseas)     # -> hinchazón
        env("nada")            # -> frecuencia cardíaca
        env("78")              # -> frecuencia respiratoria
        env("16")              # -> tolerancia líquidos
        return env("sí")

    # --- Unidad: selección de mensaje según severidad máxima ---

    def test_mensaje_cierre_sin_alertas_es_confirmacion(self):
        self.assertEqual(bot._mensaje_cierre([]), bot.MSG_CONFIRMACION)

    def test_mensaje_cierre_solo_baja_es_confirmacion(self):
        from types import SimpleNamespace
        alertas = [SimpleNamespace(severidad='BAJA')]
        self.assertEqual(bot._mensaje_cierre(alertas), bot.MSG_CONFIRMACION)

    def test_mensaje_cierre_media_y_alta_prioriza_alta(self):
        from types import SimpleNamespace
        alertas = [SimpleNamespace(severidad='MEDIA'), SimpleNamespace(severidad='ALTA')]
        self.assertEqual(bot._mensaje_cierre(alertas), bot.MSG_CIERRE_ALERTA_ALTA)

    # --- Integración: a través del flujo real + motor de alertas ---

    def test_flujo_drenaje_seroso_baja_devuelve_confirmacion(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(aspecto="1")  # seroso -> FUGA BAJA
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)

    def test_flujo_drenaje_turbio_media_devuelve_cierre_media(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(aspecto="3")  # turbio -> FUGA MEDIA
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_MEDIA)

    def test_flujo_temperatura_alta_devuelve_cierre_alta(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # SEPSIS ALTA
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)

    def test_flujo_media_y_alta_devuelve_cierre_alta(self):
        self._crear_paciente()
        # temperatura 38.5 (SEPSIS ALTA) + drenaje turbio (FUGA MEDIA) -> ALTA
        respuesta = self._completar_flujo(temperatura="38.5", aspecto="3")
        self.assertEqual(respuesta, bot.MSG_CIERRE_ALERTA_ALTA)

    def test_mensajes_cierre_no_revelan_clasificacion_clinica(self):
        for msg in (bot.MSG_CIERRE_ALERTA_MEDIA, bot.MSG_CIERRE_ALERTA_ALTA):
            low = msg.lower()
            for prohibida in ('sepsis', 'fuga', 'taquicardia', 'alerta', 'riesgo', 'ileo'):
                self.assertNotIn(prohibida, low)


class ConsentimientoInformadoTests(TestCase):
    """Bloque 7 — consentimiento informado HABEAS DATA (P-15, 01/07/2026)."""

    TELEFONO = "+573006661111"
    TELEFONO_TWILIO = "whatsapp:+573006661111"

    def _crear_paciente(self, consentimiento_informado):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Consentimiento",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=consentimiento_informado,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def test_sin_consentimiento_bot_responde_mensaje_neutro_y_no_inicia_flujo(self):
        self._crear_paciente(consentimiento_informado=False)
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_SIN_CONSENTIMIENTO)
        self.assertFalse(ConversacionWhatsApp.objects.exists())

    def test_con_consentimiento_flujo_normal_continua(self):
        self._crear_paciente(consentimiento_informado=True)
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)

    def test_consentimiento_informado_false_por_default(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Default",
            telefono_whatsapp="+573006661112",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertFalse(paciente.consentimiento_informado)
        self.assertIsNone(paciente.fecha_consentimiento)


class ConsentimientoInformadoAdminTests(TestCase):
    """Bloque 7 — auto-registro/limpieza de fecha_consentimiento vía Admin."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_consentimiento', password='pass')
        self.client.force_login(self.medico)
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Admin Consentimiento",
            cedula="700111222",
            telefono_whatsapp="+573006661113",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )

    def _url_change(self):
        return f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/'

    def _post_change(self, **overrides):
        data = {
            'nombre_completo': self.paciente.nombre_completo,
            'cedula': self.paciente.cedula,
            'telefono_whatsapp': self.paciente.telefono_whatsapp,
            'fecha_cirugia': self.paciente.fecha_cirugia.isoformat(),
            'medico_responsable': self.medico.pk,
        }
        data.update(overrides)
        return self.client.post(self._url_change(), data, follow=True)

    def test_marcar_consentimiento_registra_fecha_automaticamente(self):
        self.assertIsNone(self.paciente.fecha_consentimiento)
        self._post_change(consentimiento_informado='on')
        self.paciente.refresh_from_db()
        self.assertTrue(self.paciente.consentimiento_informado)
        self.assertIsNotNone(self.paciente.fecha_consentimiento)

    def test_desmarcar_consentimiento_limpia_fecha(self):
        self._post_change(consentimiento_informado='on')
        self.paciente.refresh_from_db()
        self.assertIsNotNone(self.paciente.fecha_consentimiento)

        self._post_change()  # sin 'consentimiento_informado' -> checkbox desmarcado
        self.paciente.refresh_from_db()
        self.assertFalse(self.paciente.consentimiento_informado)
        self.assertIsNone(self.paciente.fecha_consentimiento)

    def test_fecha_consentimiento_es_readonly_en_el_form(self):
        resp = self.client.get(self._url_change())
        self.assertNotContains(resp, 'name="fecha_consentimiento"')


class ParseEnteroRangoDecimalTests(TestCase):
    """C4 — _parse_entero_rango rechaza decimales con punto y coma."""

    def test_punto_decimal_devuelve_none(self):
        self.assertIsNone(bot._parse_entero_rango("78.5", 30, 250))

    def test_coma_decimal_devuelve_none(self):
        self.assertIsNone(bot._parse_entero_rango("78,5", 30, 250))

    def test_entero_valido_pasa(self):
        self.assertEqual(bot._parse_entero_rango("78", 30, 250), 78)

    def test_fc_decimal_pide_reintento(self):
        """Flujo real: paciente escribe "78.5" en la pregunta de FC → reintento."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Decimal FC",
            telefono_whatsapp="+573007778881",
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
        from signos_sintomas import bot as b
        conv = ConversacionWhatsApp.objects.create(
            paciente=paciente,
            checkin_actual=checkin,
            estado=ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA,
        )
        respuesta = b.procesar_mensaje("+573007778881", "78.5")
        self.assertIn("latidos", respuesta.lower())
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_FRECUENCIA_CARDIACA)


class BotAbandonoConversacionTests(TestCase):
    """A1 — Conversación abandonada a mitad de flujo en un día anterior."""

    TELEFONO = "+573001119999"
    TELEFONO_TWILIO = "whatsapp:+573001119999"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Abandono",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        return paciente

    def test_conversacion_en_flujo_ayer_reinicia_con_aviso(self):
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.temp_temperatura = Decimal("37.0")
        conv.save()
        # Simular que la última actualización fue ayer
        ayer = timezone.now() - timedelta(days=1)
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(fecha_actualizacion=ayer)

        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")

        self.assertIn("ayer no pudimos terminar", respuesta)
        self.assertEqual(RegistroDiario.objects.count(), 0)
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)
        self.assertIsNone(conv.temp_temperatura)

    def test_inicio_incompleto_ayer_no_es_abandono(self):
        # Estado INICIO desde días anteriores: no es "flujo" → no envía aviso.
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(days=1)
        )

        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")

        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        self.assertNotIn("ayer no pudimos terminar", respuesta)

    def test_despues_de_aviso_flujo_normal_continua(self):
        # Después del reinicio con aviso, el bot espera temperatura.
        paciente = self._crear_paciente()
        conv = ConversacionWhatsApp.objects.create(paciente=paciente)
        conv.estado = ConversacionWhatsApp.ESTADO_DOLOR
        conv.temp_temperatura = Decimal("37.0")
        conv.save()
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(days=1)
        )

        bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")  # recibe aviso
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "37.2")  # temperatura

        self.assertEqual(respuesta, bot.MSG_PREGUNTA_DOLOR)
        conv.refresh_from_db()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_DOLOR)
        self.assertEqual(conv.temp_temperatura, Decimal("37.2"))


class WebhookWhatsAppTests(TestCase):
    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_post_valido_devuelve_twiml(self):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Webhook",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        # Bloque 3: el bot requiere CheckInProgramado PENDIENTE para iniciar el flujo
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        respuesta = self.client.post(
            self.url,
            {
                'From': 'whatsapp:+573001112233',
                'Body': 'hola',
                'MessageSid': 'SMwebhookvalido0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertIn('temperatura', respuesta.content.decode().lower())

    @override_settings(
        TWILIO_VALIDATE_SIGNATURE=True,
        TWILIO_AUTH_TOKEN='token_prueba_firma_valida',
    )
    def test_firma_twilio_valida_permite_procesar(self):
        from twilio.request_validator import RequestValidator

        payload = {
            'From': 'whatsapp:+573009999991',
            'Body': 'hola',
            'MessageSid': 'SMfirmavalida0001',
        }
        firma = RequestValidator(
            'token_prueba_firma_valida'
        ).compute_signature(f'http://testserver{self.url}', payload)

        respuesta = self.client.post(
            self.url,
            payload,
            HTTP_X_TWILIO_SIGNATURE=firma,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertEqual(
            RecepcionWebhookTwilio.objects.get().estado,
            RecepcionWebhookTwilio.ESTADO_COMPLETADO,
        )

    def test_get_no_permitido(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 405)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='token_falso')
    def test_firma_invalida_devuelve_403(self):
        respuesta = self.client.post(
            self.url,
            {'From': 'whatsapp:+573001112233', 'Body': 'hola'},
            HTTP_X_TWILIO_SIGNATURE='firma_invalida',
        )
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='')
    def test_token_faltante_falla_seguro(self):
        # Escenario peligroso: validación activa pero token olvidado en .env.
        # Debe fallar con error claro de configuración, no saltarse la validación.
        with self.assertRaises(ImproperlyConfigured):
            self.client.post(
                self.url, {'From': 'whatsapp:+573001112233', 'Body': 'hola'}
            )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=True, TWILIO_AUTH_TOKEN='token_falso')
    def test_header_ausente_devuelve_403(self):
        # Sin X-Twilio-Signature en el request → la firma vacía no valida → 403.
        respuesta = self.client.post(
            self.url,
            {'From': 'whatsapp:+573001112233', 'Body': 'hola'},
            # No se incluye HTTP_X_TWILIO_SIGNATURE
        )
        self.assertEqual(respuesta.status_code, 403)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_body_vacio_devuelve_twiml(self):
        # Body ausente / vacío no debe romper el webhook; paciente desconocido
        # recibe respuesta amable.
        respuesta = self.client.post(
            self.url,
            {
                'From': 'whatsapp:+573009999999',
                'Body': '',
                'MessageSid': 'SMbodyvacio0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_sid_ausente_devuelve_400_sin_procesar(self):
        from unittest.mock import patch

        with patch('signos_sintomas.views.procesar_mensaje') as procesar:
            respuesta = self.client.post(
                self.url,
                {'From': 'whatsapp:+573009999999', 'Body': 'hola'},
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.content, b'')
        procesar.assert_not_called()
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), 0)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_idempotencia_mismo_sid_ignora_segundo_mensaje(self):
        # Twilio puede reintentar un webhook con el mismo MessageSid.
        # El segundo mensaje con el mismo SID debe devolver TwiML vacío sin
        # ejecutar la lógica del bot de nuevo.
        Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Idempotencia",
            telefono_whatsapp="+573002223344",
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            consentimiento_informado=True,
        )
        payload = {
            'From': 'whatsapp:+573002223344',
            'Body': 'hola',
            'MessageSid': 'SMidempotencia0001',
        }
        primera = self.client.post(self.url, payload)
        segunda = self.client.post(self.url, payload)

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        # Segunda respuesta es TwiML vacío (sin <Message>)
        self.assertNotIn(b'<Message>', segunda.content)
        # Primera sí tiene contenido
        self.assertIn(b'<Message>', primera.content)
        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMidempotencia0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 1)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_error_del_bot_deja_recepcion_reintentable(self):
        from unittest.mock import patch

        payload = {
            'From': 'whatsapp:+573002223355',
            'Body': 'contenido sensible que no debe persistirse',
            'MessageSid': 'SMreintento0001',
        }
        with patch(
            'signos_sintomas.views.procesar_mensaje',
            side_effect=RuntimeError('detalle sensible'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)

        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMreintento0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_ERROR)

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='Reporte recibido',
        ) as procesar:
            respuesta = self.client.post(self.url, payload)

        self.assertEqual(respuesta.status_code, 200)
        procesar.assert_called_once()
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 2)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_fallo_antes_de_confirmar_recibo_revierte_el_avance_del_bot(self):
        from unittest.mock import patch

        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Atomicidad Webhook',
            telefono_whatsapp='+573002223388',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            consentimiento_informado=True,
        )
        CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        payload = {
            'From': 'whatsapp:+573002223388',
            'Body': 'hola',
            'MessageSid': 'SMatomicidad0001',
        }

        with patch(
            'signos_sintomas.views._marcar_recepcion_completada',
            side_effect=RuntimeError('caída antes del commit'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)

        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMatomicidad0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_ERROR)
        self.assertFalse(ConversacionWhatsApp.objects.filter(paciente=paciente).exists())

        respuesta = self.client.post(self.url, payload)

        self.assertEqual(respuesta.status_code, 200)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 2)
        conversacion = ConversacionWhatsApp.objects.get(paciente=paciente)
        self.assertEqual(
            conversacion.estado,
            ConversacionWhatsApp.ESTADO_TEMPERATURA,
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_sid_en_proceso_devuelve_503_para_que_twilio_reintente(self):
        from unittest.mock import patch

        RecepcionWebhookTwilio.objects.create(message_sid='SMenproceso0001')

        with patch('signos_sintomas.views.procesar_mensaje') as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573002223366',
                    'Body': 'hola',
                    'MessageSid': 'SMenproceso0001',
                },
            )

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta['Retry-After'], '30')
        procesar.assert_not_called()

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_token_idempotencia_se_guarda_sin_datos_medicos(self):
        from unittest.mock import patch

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='Reporte recibido',
        ):
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573002223377',
                    'Body': 'dolor 9 y fiebre',
                    'MessageSid': 'SMtoken0001',
                },
                HTTP_I_TWILIO_IDEMPOTENCY_TOKEN='token-reintento-1',
            )

        self.assertEqual(respuesta.status_code, 200)
        recepcion = RecepcionWebhookTwilio.objects.get(message_sid='SMtoken0001')
        self.assertEqual(recepcion.idempotency_token, 'token-reintento-1')
        valores = ' '.join(str(valor) for valor in recepcion.__dict__.values())
        self.assertNotIn('dolor 9', valores)
        self.assertNotIn('+573002223377', valores)

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_rate_limit_excedido_informa_sin_procesar_el_mensaje(self):
        """Superado el límite, el mensaje no se procesa y el paciente recibe
        orientación.

        POR QUÉ CAMBIÓ (no es un ajuste, cambió el requisito — D2 punto 3):
        antes la verificación del rate limit ocurría DESPUÉS de reclamar el
        SID, así que un mensaje limitado dejaba una fila COMPLETADO en
        RecepcionWebhookTwilio. Ahora la verificación ocurre ANTES de reclamar
        el SID, de modo que un mensaje limitado no debe dejar fila alguna. La
        aserción sobre la fila se invirtió para reflejarlo; las de la respuesta
        al paciente no cambian.
        """
        from signos_sintomas.views import _LIMITE_MENSAJES_HORA, _MSG_RATE_LIMIT
        telefono = 'whatsapp:+573005556677'
        # Forzar el contador de cache directamente al límite
        clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
        cache.set(clave, _LIMITE_MENSAJES_HORA, 3600)

        respuesta = self.client.post(
            self.url,
            {
                'From': telefono,
                'Body': 'hola',
                'MessageSid': 'SMratelimit0001',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(b'<Message>', respuesta.content)
        self.assertIn(_MSG_RATE_LIMIT.encode(), respuesta.content)
        self.assertFalse(
            RecepcionWebhookTwilio.objects.filter(
                message_sid='SMratelimit0001',
            ).exists()
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_webhook_falla_abierto_si_el_cache_no_responde(self):
        """D2 (punto 1): si el cache no responde, el webhook NO puede dejar sin
        respuesta al paciente. La firma de Twilio sigue protegiendo la puerta,
        así que se procesa el mensaje (fallar abierto) en vez de devolver 500.
        """
        from unittest.mock import MagicMock, patch

        cache_caido = MagicMock()
        cache_caido.incr.side_effect = ConnectionError('redis inalcanzable')
        with patch('signos_sintomas.views.cache', cache_caido), patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='respuesta del bot',
        ) as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': 'whatsapp:+573001112299',
                    'Body': 'hola',
                    'MessageSid': 'SMcachecaido0001',
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        procesar.assert_called_once()

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_limite_por_hora_permite_mas_de_veinte_mensajes(self):
        """D2 (punto 4): el límite sube de 20 a 60. 30 mensajes en una hora ya
        no bloquean al paciente — un cuestionario completo son ~11 mensajes y
        la población objetivo (personas mayores, recién operadas) reintenta.
        """
        from unittest.mock import patch

        from signos_sintomas.views import _MSG_RATE_LIMIT

        telefono = 'whatsapp:+573005556699'
        clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
        cache.set(clave, 30, 3600)

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            return_value='respuesta del bot',
        ) as procesar:
            respuesta = self.client.post(
                self.url,
                {
                    'From': telefono,
                    'Body': 'hola',
                    'MessageSid': 'SMlimite60000001',
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(_MSG_RATE_LIMIT.encode(), respuesta.content)
        procesar.assert_called_once()


class WebhookFlujoCompletoTests(TestCase):
    TELEFONO = '+573006660001'

    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')
        medico = get_user_model().objects.create_user(
            username='medico_flujo_webhook',
            password='pass',
            email='medico-flujo@test.com',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo='Paciente Flujo Webhook',
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
            medico_responsable=medico,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_recorrido_completo_por_webhook_crea_registro_alerta_y_outbox(self):
        respuestas = [
            'hola', '38.5', '3', 'sí', '1', 'normal',
            'sí, 0', 'nada', '78', '16', 'sí',
        ]

        ultima_respuesta = None
        for indice, texto in enumerate(respuestas, start=1):
            ultima_respuesta = self.client.post(
                self.url,
                {
                    'From': f'whatsapp:{self.TELEFONO}',
                    'Body': texto,
                    'MessageSid': f'SMflujocompleto{indice:04d}',
                },
            )
            self.assertEqual(ultima_respuesta.status_code, 200)

        self.assertIn('urgencias', ultima_respuesta.content.decode().lower())
        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.checkin.refresh_from_db()
        conversacion = ConversacionWhatsApp.objects.get(paciente=self.paciente)
        alerta = Alerta.objects.get(paciente=self.paciente, tipo='SEPSIS')
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)

        self.assertEqual(registro.temperatura, Decimal('38.5'))
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(self.checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(self.checkin.registro, registro)
        self.assertEqual(conversacion.estado, ConversacionWhatsApp.ESTADO_COMPLETADO)
        self.assertEqual(alerta.severidad, 'ALTA')
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.destinatario, 'medico-flujo@test.com')
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), len(respuestas))
        self.assertFalse(
            RecepcionWebhookTwilio.objects.exclude(
                estado=RecepcionWebhookTwilio.ESTADO_COMPLETADO,
            ).exists()
        )


class WebhookConcurrenciaTests(TransactionTestCase):
    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_dos_requests_simultaneos_del_mismo_sid_procesan_una_vez(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from django.test import Client

        iniciado = Event()
        liberar = Event()
        url = reverse('signos_sintomas:webhook_whatsapp')
        payload = {
            'From': 'whatsapp:+573006660002',
            'Body': 'hola',
            'MessageSid': 'SMconcurrente0001',
        }

        def procesar_lento(*args, **kwargs):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el primer worker.')
            return 'Reporte recibido'

        def enviar():
            close_old_connections()
            try:
                return Client().post(url, payload)
            finally:
                close_old_connections()

        with patch(
            'signos_sintomas.views.procesar_mensaje',
            side_effect=procesar_lento,
        ) as procesar:
            with ThreadPoolExecutor(max_workers=2) as executor:
                primera_futura = executor.submit(enviar)
                self.assertTrue(iniciado.wait(timeout=10))
                segunda = executor.submit(enviar).result(timeout=10)
                liberar.set()
                primera = primera_futura.result(timeout=10)

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 503)
        self.assertEqual(segunda['Retry-After'], '30')
        procesar.assert_called_once()
        recepcion = RecepcionWebhookTwilio.objects.get(
            message_sid='SMconcurrente0001'
        )
        self.assertEqual(recepcion.estado, RecepcionWebhookTwilio.ESTADO_COMPLETADO)
        self.assertEqual(recepcion.intentos, 1)


class WebhookCargaTests(TransactionTestCase):
    PACIENTES = 50

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_rafaga_50_pacientes_responde_antes_del_timeout_twilio(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from time import perf_counter

        from django.test import Client

        url = reverse('signos_sintomas:webhook_whatsapp')
        barrera = Barrier(self.PACIENTES)
        respuestas = [
            'hola', '37.0', '3', 'sí', '1', 'normal',
            'sí, 0', 'nada', '78', '16', 'sí',
        ]
        for indice in range(self.PACIENTES):
            telefono = f'+5730077{indice:05d}'
            paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
                nombre_completo=f'Paciente Carga {indice:02d}',
                telefono_whatsapp=telefono,
                fecha_cirugia=timezone.localdate() - timedelta(days=2),
                consentimiento_informado=True,
            )
            CheckInProgramado.objects.create(
                paciente=paciente,
                fecha_dia=timezone.localdate(),
                orden=1,
                etiqueta=CheckInProgramado.ETIQUETA_MANANA,
                hora_programada=timezone.now(),
            )

        def enviar(indice):
            close_old_connections()
            try:
                telefono = f'+5730077{indice:05d}'
                barrera.wait(timeout=20)
                cliente = Client()
                resultados_paciente = []
                for paso, texto in enumerate(respuestas, start=1):
                    inicio = perf_counter()
                    respuesta = cliente.post(
                        url,
                        {
                            'From': f'whatsapp:{telefono}',
                            'Body': texto,
                            'MessageSid': f'SMcarga{indice:03d}{paso:02d}',
                        },
                    )
                    resultados_paciente.append(
                        (respuesta.status_code, perf_counter() - inicio)
                    )
                return resultados_paciente
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=self.PACIENTES) as executor:
            lotes = list(executor.map(enviar, range(self.PACIENTES)))

        resultados = [resultado for lote in lotes for resultado in lote]
        estados = [estado for estado, _ in resultados]
        duraciones = [duracion for _, duracion in resultados]
        total_webhooks = self.PACIENTES * len(respuestas)
        self.assertEqual(estados, [200] * total_webhooks)
        self.assertLess(max(duraciones), 15)
        self.assertEqual(RecepcionWebhookTwilio.objects.count(), total_webhooks)
        self.assertEqual(ConversacionWhatsApp.objects.count(), self.PACIENTES)
        self.assertEqual(RegistroDiario.objects.count(), self.PACIENTES)
        self.assertEqual(
            CheckInProgramado.objects.filter(
                estado=CheckInProgramado.ESTADO_COMPLETADO,
            ).count(),
            self.PACIENTES,
        )
        self.assertFalse(
            RecepcionWebhookTwilio.objects.exclude(
                estado=RecepcionWebhookTwilio.ESTADO_COMPLETADO,
            ).exists()
        )


class EvaluacionAlertasPersistenteTests(TestCase):
    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Evaluacion Persistente',
            telefono_whatsapp='+573002224400',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.2'),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )

    def test_evaluacion_exitosa_queda_completada(self):
        from .evaluacion_alertas import evaluar_registro_con_estado

        alertas = evaluar_registro_con_estado(self.registro)

        self.registro.refresh_from_db()
        self.assertEqual(
            self.registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(self.registro.intentos_evaluacion_alertas, 1)
        self.assertIsNotNone(self.registro.fecha_ultima_evaluacion_alertas)
        self.assertEqual(self.registro.ultimo_error_evaluacion_alertas, '')
        self.assertEqual([alerta.tipo for alerta in alertas], ['SEPSIS'])

    def test_error_se_persiste_sin_texto_sensible_y_admite_reintento(self):
        from unittest.mock import patch

        from .evaluacion_alertas import evaluar_registro_con_estado

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=RuntimeError('paciente reporta dolor 9'),
        ):
            with self.assertRaises(RuntimeError):
                evaluar_registro_con_estado(self.registro)

        self.registro.refresh_from_db()
        self.assertEqual(
            self.registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )
        self.assertEqual(self.registro.intentos_evaluacion_alertas, 1)
        self.assertEqual(self.registro.ultimo_error_evaluacion_alertas, 'RuntimeError')
        self.assertNotIn('dolor 9', self.registro.ultimo_error_evaluacion_alertas)

        alertas = evaluar_registro_con_estado(self.registro)

        self.registro.refresh_from_db()
        self.assertEqual(
            self.registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(self.registro.intentos_evaluacion_alertas, 2)
        self.assertEqual(self.registro.ultimo_error_evaluacion_alertas, '')
        self.assertEqual([alerta.tipo for alerta in alertas], ['SEPSIS'])

    def test_error_revierte_alertas_parciales_antes_de_marcar_reintento(self):
        from unittest.mock import patch

        from .evaluacion_alertas import evaluar_registro_con_estado

        def crear_parcial_y_fallar(registro, fecha_referencia=None):
            Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='SEPSIS',
                severidad='ALTA',
                mensaje='Alerta parcial que debe revertirse',
            )
            raise RuntimeError('detalle clínico que no debe persistir')

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=crear_parcial_y_fallar,
        ):
            with self.assertRaises(RuntimeError):
                evaluar_registro_con_estado(self.registro)

        self.registro.refresh_from_db()
        self.assertEqual(
            self.registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )
        self.assertEqual(self.registro.ultimo_error_evaluacion_alertas, 'RuntimeError')
        self.assertFalse(Alerta.objects.filter(registro_origen=self.registro).exists())
        self.assertFalse(NotificacionAlerta.objects.exists())


class ReintentarEvaluacionesAlertasCommandTests(TestCase):
    def _registro(self, telefono):
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Reintento Command',
            telefono_whatsapp=telefono,
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
        )
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal('37.0'),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )

    def test_procesa_pendientes_y_errores_una_vez(self):
        from django.core.management import call_command

        pendiente = self._registro('+573002224411')
        con_error = self._registro('+573002224412')
        RegistroDiario.objects.filter(pk=con_error.pk).update(
            estado_evaluacion_alertas=RegistroDiario.EVALUACION_ERROR,
            ultimo_error_evaluacion_alertas='RuntimeError',
        )

        call_command('reintentar_evaluaciones_alertas', verbosity=0)

        pendiente.refresh_from_db()
        con_error.refresh_from_db()
        self.assertEqual(
            pendiente.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(
            con_error.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(pendiente.intentos_evaluacion_alertas, 1)
        self.assertEqual(con_error.intentos_evaluacion_alertas, 1)

    def test_un_error_no_impide_procesar_el_siguiente(self):
        from unittest.mock import patch

        from django.core.management import call_command

        primero = self._registro('+573002224413')
        segundo = self._registro('+573002224414')

        def evaluar(registro, fecha_referencia=None):
            if registro.pk == primero.pk:
                raise RuntimeError('dato sensible que no debe persistirse')
            return []

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=evaluar,
        ):
            call_command('reintentar_evaluaciones_alertas', verbosity=0)

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(
            primero.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )
        self.assertEqual(primero.ultimo_error_evaluacion_alertas, 'RuntimeError')
        self.assertEqual(
            segundo.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )

    def test_limite_restringe_cantidad_procesada(self):
        from django.core.management import call_command

        registros = [
            self._registro('+573002224421'),
            self._registro('+573002224422'),
        ]

        call_command('reintentar_evaluaciones_alertas', limite=1, verbosity=0)

        estados = list(
            RegistroDiario.objects.filter(pk__in=[r.pk for r in registros])
            .order_by('pk')
            .values_list('estado_evaluacion_alertas', flat=True)
        )
        self.assertEqual(
            estados,
            [RegistroDiario.EVALUACION_COMPLETADA, RegistroDiario.EVALUACION_PENDIENTE],
        )

    def test_no_reintenta_tras_diez_intentos_de_evaluacion(self):
        """D6: la evaluación de un registro no se reintenta para siempre. Tras
        10 intentos deja de recogerse — un fallo que sobrevive 10 intentos es
        de configuración, no transitorio, y reintentar en bucle solo esconde
        el problema (además evita el desbordamiento del contador).
        """
        from django.core.management import call_command

        registro = self._registro('+573002224431')
        RegistroDiario.objects.filter(pk=registro.pk).update(
            estado_evaluacion_alertas=RegistroDiario.EVALUACION_ERROR,
            intentos_evaluacion_alertas=10,
            ultimo_error_evaluacion_alertas='RuntimeError',
        )

        call_command('reintentar_evaluaciones_alertas', verbosity=0)

        registro.refresh_from_db()
        self.assertEqual(registro.intentos_evaluacion_alertas, 10)
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )

class PacienteMedicoFKTests(TestCase):
    """Tests de la relación ForeignKey Paciente → auth.User (medico_responsable)."""

    def _crear_paciente(self, **kwargs):
        kwargs.setdefault('medico_responsable', medico_de_pruebas())
        return Paciente.objects.create(
            nombre_completo="Paciente FK Test",
            telefono_whatsapp="+573000000001",
            fecha_cirugia=timezone.localdate(),
            **kwargs,
        )

    def test_paciente_con_medico_fk(self):
        User = get_user_model()
        medico = User.objects.create_user(
            username='dr_test', password='x', first_name='Carlos', last_name='López'
        )
        paciente = self._crear_paciente(medico_responsable=medico)
        paciente.refresh_from_db()
        self.assertEqual(paciente.medico_responsable, medico)
        self.assertIn(paciente, medico.pacientes.all())

    def test_str_con_medico_nombre_completo(self):
        User = get_user_model()
        medico = User.objects.create_user(
            username='dr_str', password='x', first_name='Ana', last_name='Ruiz'
        )
        paciente = self._crear_paciente(medico_responsable=medico)
        self.assertEqual(str(paciente), "Paciente FK Test — Dr. Ana Ruiz")

    def test_str_con_medico_sin_nombre_usa_username(self):
        User = get_user_model()
        medico = User.objects.create_user(username='dr_noname', password='x')
        paciente = self._crear_paciente(medico_responsable=medico)
        self.assertEqual(str(paciente), "Paciente FK Test — Dr. dr_noname")

    def test_str_sin_medico(self):
        """Solo una ficha INACTIVA puede no tener responsable (D12).

        Antes el paciente se creaba activo. Desde la migración 0028 la base lo
        rechaza: `activo` es la palabra que hace el invariante cumplible, y las
        filas históricas conservan lo que tengan, incluido NULL.
        """
        paciente = self._crear_paciente(medico_responsable=None, activo=False)

        self.assertEqual(str(paciente), "Paciente FK Test — Sin médico asignado")

    def test_no_se_puede_borrar_un_medico_con_pacientes(self):
        """D12 (capa 2) — esta prueba afirmaba lo contrario.

        Se llamaba `test_set_null_al_borrar_usuario` y verificaba que borrar la
        cuenta del médico dejara al paciente con `medico_responsable=None`. Eso
        era exactamente el hallazgo: el paciente quedaba huérfano e invisible,
        en silencio. La prueba documentaba el defecto como si fuera el contrato.
        """
        from django.db.models import ProtectedError

        User = get_user_model()
        medico = User.objects.create_user(username='dr_delete', password='x')
        paciente = self._crear_paciente(medico_responsable=medico)

        with self.assertRaises(ProtectedError):
            medico.delete()

        paciente.refresh_from_db()
        self.assertEqual(paciente.medico_responsable, medico)


class AdminScopingTests(TestCase):
    """Tests de scoping del admin por médico responsable (B6 + D2 + D5)."""

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico_a = User.objects.create_user(
            username='dr_a', password='pass', is_staff=True
        )
        self.medico_b = User.objects.create_user(
            username='dr_b', password='pass', is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username='super', password='pass'
        )
        # Los usuarios staff necesitan permisos explícitos de modelo para
        # acceder al admin — sin esto los 403 vendrían de falta de permiso
        # general, no del scoping por médico (falso positivo en tests).
        for model in (
            Paciente,
            RegistroDiario,
            Alerta,
            CheckInProgramado,
            NotificacionAlerta,
        ):
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            self.medico_a.user_permissions.add(*perms)
            self.medico_b.user_permissions.add(*perms)

        self.paciente_a = Paciente.objects.create(
            nombre_completo="Paciente del Doctor A",
            telefono_whatsapp="+573010000001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico_a,
        )
        self.paciente_b = Paciente.objects.create(
            nombre_completo="Paciente del Doctor B",
            telefono_whatsapp="+573010000002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico_b,
        )
        _campos_base = dict(
            temperatura=Decimal('37.0'),
            dolor_eva=3,
            aspecto_drenaje='sin_drenaje',
            presencia_gases=True,
            episodios_nauseas=0,
        )
        self.registro_a = RegistroDiario.objects.create(
            paciente=self.paciente_a, **_campos_base
        )
        self.registro_b = RegistroDiario.objects.create(
            paciente=self.paciente_b, **_campos_base
        )
        self.alerta_a = Alerta.objects.create(
            paciente=self.paciente_a,
            registro_origen=self.registro_a,
            tipo='SEPSIS', severidad='BAJA', mensaje='Alerta A',
        )
        self.alerta_b = Alerta.objects.create(
            paciente=self.paciente_b,
            registro_origen=self.registro_b,
            tipo='SEPSIS', severidad='BAJA', mensaje='Alerta B',
        )
        self.notificacion_a = NotificacionAlerta.objects.create(
            alerta=self.alerta_a,
            destinatario='operaciones@test.com',
        )
        self.deteccion_a = DeteccionAlerta.objects.create(
            alerta=self.alerta_a,
            registro=self.registro_a,
            severidad_detectada='BAJA',
            mensaje_detectado='Detalle clínico A',
        )
        self.deteccion_b = DeteccionAlerta.objects.create(
            alerta=self.alerta_b,
            registro=self.registro_b,
            severidad_detectada='BAJA',
            mensaje_detectado='Detalle clínico B',
        )
        self.checkin_a = CheckInProgramado.objects.create(
            paciente=self.paciente_a,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        self.checkin_b = CheckInProgramado.objects.create(
            paciente=self.paciente_b,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    def _login(self, user):
        self.client.force_login(user)

    # ------------------------------------------------------------------ #
    # PacienteAdmin                                                        #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_pacientes_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todos_en_changelist_paciente(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_paciente_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_medico_puede_editar_su_propio_paciente(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_superuser_puede_editar_cualquier_paciente(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    # ------------------------------------------------------------------ #
    # RegistroDiarioAdmin                                                  #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_registros_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/registrodiario/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todos_en_changelist_registro(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/registrodiario/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_registro_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_superuser_puede_editar_cualquier_registro(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_medico_ve_registro_propio_pero_no_puede_modificarlo(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/registrodiario/{self.registro_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {'temperatura': '39.9'})
        self.assertEqual(resp.status_code, 403)
        self.registro_a.refresh_from_db()
        self.assertEqual(self.registro_a.temperatura, Decimal('37.0'))

    def test_medico_no_puede_borrar_paciente_propio(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/paciente/{self.paciente_a.pk}/delete/'
        self.assertEqual(self.client.get(url).status_code, 403)

    # ------------------------------------------------------------------ #
    # AlertaAdmin                                                          #
    # ------------------------------------------------------------------ #

    def test_medico_ve_solo_sus_alertas_en_changelist(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertNotContains(resp, "Paciente del Doctor B")

    def test_superuser_ve_todas_las_alertas_en_changelist(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Paciente del Doctor A")
        self.assertContains(resp, "Paciente del Doctor B")

    def test_medico_no_puede_editar_alerta_ajena(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_b.pk}/change/'
        resp = self.client.get(url)
        # El objeto no está en el queryset del médico → Django admin redirige
        # (302). En Django 6 el destino es /admin/ (índice). Lo relevante para
        # seguridad: el formulario de edición NUNCA se renderiza (no 200).
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_medico_no_puede_borrar_alerta_propia(self):
        # Alertas son registros clínicos; has_delete_permission retorna False
        # para cualquier no-superuser → 403 en la vista de borrado.
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/delete/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_superuser_puede_acceder_a_alerta_ajena(self):
        self._login(self.superuser)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_b.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_formulario_alerta_no_permite_resolver_directamente(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/change/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'name="resuelta"')

        self.client.post(url, {'resuelta': 'on'})
        self.alerta_a.refresh_from_db()
        self.assertFalse(self.alerta_a.resuelta)

    def test_detalle_detecciones_es_solo_lectura_y_respeta_scoping(self):
        self._login(self.medico_a)

        resp = self.client.get(
            f'/admin/signos_sintomas/alerta/{self.alerta_a.pk}/change/'
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Detecciones de la alerta')
        self.assertContains(resp, 'Detalle clínico A')
        self.assertNotContains(resp, 'Detalle clínico B')
        self.assertNotContains(resp, 'name="detecciones-0-mensaje_detectado"')

    def test_medico_ve_checkin_propio_pero_no_puede_modificarlo(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/checkinprogramado/{self.checkin_a.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {'estado': CheckInProgramado.ESTADO_NO_RESPONDIDO})
        self.assertEqual(resp.status_code, 403)
        self.checkin_a.refresh_from_db()
        self.assertEqual(self.checkin_a.estado, CheckInProgramado.ESTADO_PENDIENTE)

    def test_medico_no_puede_ver_checkin_ajeno(self):
        self._login(self.medico_a)
        url = f'/admin/signos_sintomas/checkinprogramado/{self.checkin_b.pk}/change/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertRegex(resp.url, r'^/admin/')

    def test_filtro_fecha_checkin_usa_etiqueta_precisa(self):
        self._login(self.medico_a)
        resp = self.client.get('/admin/signos_sintomas/checkinprogramado/')
        self.assertContains(resp, 'Todas las fechas')
        self.assertNotContains(resp, 'Cualquier fecha')

    def test_medico_no_puede_ver_bandeja_tecnica_de_notificaciones(self):
        self._login(self.medico_a)
        lista = self.client.get('/admin/signos_sintomas/notificacionalerta/')
        detalle = self.client.get(
            f'/admin/signos_sintomas/notificacionalerta/{self.notificacion_a.pk}/change/'
        )
        self.assertEqual(lista.status_code, 403)
        self.assertEqual(detalle.status_code, 403)

    def test_superuser_puede_auditar_bandeja_de_notificaciones(self):
        self._login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/notificacionalerta/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.notificacion_a.alerta_id)


class AlertaAdminAccionesTests(TestCase):
    """Bloque 5A — Colores severidad + acción marcar_resuelta en AlertaAdmin."""

    def setUp(self):
        User = get_user_model()
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        self.superuser = User.objects.create_superuser(
            username='super5a', password='pass',
        )
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente 5A",
            telefono_whatsapp="+573019990001",
            fecha_cirugia=timezone.localdate(),
        )
        campos = dict(
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        self.registro = RegistroDiario.objects.create(paciente=self.paciente, **campos)
        self.alerta = Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre test',
        )

    def test_changelist_contiene_badge_severidad(self):
        """La lista de alertas renderiza el badge de severidad con HTML coloreado."""
        self.client.force_login(self.superuser)
        resp = self.client.get('/admin/signos_sintomas/alerta/')
        self.assertEqual(resp.status_code, 200)
        # El badge usa border-radius como parte del estilo — confirma que se renderizó HTML
        self.assertContains(resp, 'border-radius')

    def test_accion_marcar_resuelta(self):
        """Bloque A: marcar_resuelta con el paso 'aplicar' + motivo actualiza
        la alerta, registra fecha_resolucion y guarda el motivo."""
        self.client.force_login(self.superuser)
        self.client.post(
            '/admin/signos_sintomas/alerta/',
            {
                'action': 'marcar_resuelta',
                'aplicar': '1',
                '_selected_action': [str(self.alerta.pk)],
                'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
                'motivo_resolucion_detalle': '',
            },
        )
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertIsNotNone(self.alerta.fecha_resolucion)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_CONTACTO)


class AlertaMotivoResolucionTests(TestCase):
    """Bloque A — motivo de resolución obligatorio con formulario intermedio."""

    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(username='super_motivo', password='pass')
        self.medico = User.objects.create_user(
            username='dr_motivo', password='pass', is_staff=True,
        )
        self.otro_medico = User.objects.create_user(
            username='dr_otro', password='pass', is_staff=True,
        )
        self._dar_permisos(self.medico)
        self._dar_permisos(self.otro_medico)
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Motivo",
            telefono_whatsapp="+573018880001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        self.alerta = Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre test',
        )

    def _dar_permisos(self, user):
        from django.contrib.auth.models import Permission
        perms = Permission.objects.filter(
            content_type__app_label='signos_sintomas',
            content_type__model='alerta',
        )
        user.user_permissions.add(*perms)

    def _post_accion(self, extra):
        data = {
            'action': 'marcar_resuelta',
            '_selected_action': [str(self.alerta.pk)],
        }
        data.update(extra)
        return self.client.post('/admin/signos_sintomas/alerta/', data)

    def test_motivo_resolucion_null_por_default(self):
        """Una alerta recién creada no tiene motivo de resolución."""
        self.assertIsNone(self.alerta.motivo_resolucion)

    def test_base_de_datos_rechaza_cierre_sin_motivo_y_fecha(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alerta.objects.filter(pk=self.alerta.pk).update(resuelta=True)

    def test_modelo_rechaza_cierre_sin_motivo_y_fecha(self):
        self.alerta.resuelta = True
        with self.assertRaises(ValidationError):
            self.alerta.full_clean()

    def test_accion_sin_aplicar_muestra_formulario_intermedio(self):
        self.client.force_login(self.superuser)
        resp = self._post_accion({})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'motivo de resolución')
        self.assertEqual(
            resp.content.decode().count('<h1>Selecciona el motivo de resolución</h1>'),
            1,
        )
        self.assertContains(resp, 'admin/js/motivo_resolucion.js')
        self.assertNotContains(resp, 'DOMContentLoaded')
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_aplicar_con_motivo_valido_resuelve_y_guarda_motivo(self):
        self.client.force_login(self.superuser)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_URGENCIAS,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_URGENCIAS)

    def test_motivo_otro_sin_detalle_no_resuelve(self):
        self.client.force_login(self.superuser)
        resp = self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_OTRO,
            'motivo_resolucion_detalle': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'detalle cuando el motivo es')
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_motivo_otro_con_detalle_resuelve_y_guarda_detalle(self):
        self.client.force_login(self.superuser)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_OTRO,
            'motivo_resolucion_detalle': 'Resuelto en control presencial.',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.motivo_resolucion, Alerta.MOTIVO_OTRO)
        self.assertEqual(
            self.alerta.motivo_resolucion_detalle, 'Resuelto en control presencial.'
        )

    def test_medico_no_resuelve_alertas_de_pacientes_ajenos(self):
        """El otro médico no es responsable de este paciente → no la resuelve."""
        self.client.force_login(self.otro_medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.resuelta)

    def test_resolver_registra_quien_resolvio(self):
        """D3: al resolver, la alerta guarda QUIÉN la resolvió. Sin este dato,
        una decisión clínica (p.ej. marcar una fuga como falso positivo) queda
        sin atribución el día que entre un segundo médico o se transfiera el
        sistema — datos que no se capturan no son recuperables.
        """
        self.client.force_login(self.medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertEqual(self.alerta.resuelta_por, self.medico)

    def test_resolver_escribe_en_el_historial_del_admin(self):
        """D3: la resolución deja una entrada en el historial de Django (el
        botón "Historial" de la alerta), imposible con queryset.update() a
        secas. Se registra con el usuario que resolvió.
        """
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        self.client.force_login(self.medico)
        self._post_accion({
            'aplicar': '1',
            'motivo_resolucion': Alerta.MOTIVO_CONTACTO,
            'motivo_resolucion_detalle': '',
        })
        ct = ContentType.objects.get_for_model(Alerta)
        entradas = LogEntry.objects.filter(
            content_type=ct,
            object_id=str(self.alerta.pk),
            user=self.medico,
        )
        self.assertTrue(entradas.exists())


class AlertaEmailNotificacionTests(TestCase):
    """Bandeja durable para avisar al médico por una alerta ALTA."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dr_email', password='pass', email='dr@test.com',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Email",
            cedula="800111222",
            telefono_whatsapp="+573019990002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )

    def _crear_alerta_alta(self):
        return Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Fiebre alta de prueba.',
        )

    def test_alerta_alta_se_encola_sin_conexion_de_red(self):
        from django.core import mail
        alerta = self._crear_alerta_alta()

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.destinatario, self.medico.email)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.intentos, 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PANEL_MEDICO_URL='https://ejemplo.test/acceso-seguro/')
    def test_procesador_envia_aviso_sin_datos_medicos(self):
        from django.core import mail
        from django.core.management import call_command

        alerta = self._crear_alerta_alta()
        call_command('procesar_notificaciones_email', verbosity=0)

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.medico.email])
        self.assertIn('Alerta clínica alta', correo.subject)
        self.assertIn(f'alerta #{alerta.pk}', correo.body)
        self.assertIn('https://ejemplo.test/acceso-seguro/', correo.body)
        self.assertNotIn(self.paciente.nombre_completo, correo.body)
        self.assertNotIn(self.paciente.telefono_whatsapp, correo.body)
        self.assertNotIn(self.paciente.cedula, correo.body)
        self.assertNotIn(alerta.mensaje, correo.body)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(notificacion.intentos, 1)
        self.assertIsNotNone(notificacion.fecha_envio)

    def test_procesador_es_idempotente_para_notificacion_enviada(self):
        from django.core import mail
        from django.core.management import call_command

        self._crear_alerta_alta()
        call_command('procesar_notificaciones_email', verbosity=0)
        call_command('procesar_notificaciones_email', verbosity=0)
        self.assertEqual(len(mail.outbox), 1)

    def test_fallo_externo_programa_reintento_sin_perder_la_fila(self):
        from unittest.mock import patch
        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        with patch(
            'signos_sintomas.notificaciones.send_mail',
            side_effect=TimeoutError('detalle que no debe persistirse'),
        ):
            with self.assertRaises(CommandError):
                call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.intentos, 1)
        self.assertEqual(notificacion.ultimo_error, 'TimeoutError')
        self.assertGreater(notificacion.proximo_intento, timezone.now())
        self.assertNotIn('detalle', notificacion.ultimo_error)

    def test_notificacion_se_marca_fallida_tras_agotar_reintentos(self):
        """D6: el correo de alerta ALTA no se reintenta para siempre. Tras 10
        intentos fallidos la notificación queda en estado terminal FALLIDA en
        vez de reprogramarse — un correo de alerta ALTA que falla de forma
        permanente es información clínica que no llegó, y debe hacerse visible,
        no reintentarse en silencio.
        """
        from unittest.mock import patch

        from .notificaciones import procesar_notificaciones_pendientes

        alerta = self._crear_alerta_alta()
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        # Ya acumuló 9 intentos fallidos; el décimo también falla.
        NotificacionAlerta.objects.filter(pk=notificacion.pk).update(
            intentos=9,
            proximo_intento=timezone.now() - timedelta(seconds=1),
        )

        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=TimeoutError('fallo externo persistente'),
        ):
            procesar_notificaciones_pendientes()

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.intentos, 10)
        self.assertEqual(notificacion.estado, 'FALLIDA')

    def test_notificacion_pendiente_se_puede_reintentar(self):
        from django.core import mail
        from django.core.management import call_command

        alerta = self._crear_alerta_alta()
        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        NotificacionAlerta.objects.filter(pk=notificacion.pk).update(
            intentos=2,
            proximo_intento=timezone.now() - timedelta(seconds=1),
        )

        call_command('procesar_notificaciones_email', verbosity=0)

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(notificacion.intentos, 3)
        self.assertEqual(len(mail.outbox), 1)

    def test_limite_invalido_es_rechazado(self):
        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', limite=0, verbosity=0)

    def test_alerta_media_no_se_encola(self):
        Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS',
            severidad='MEDIA',
            mensaje='Subfebrícula.',
        )
        self.assertEqual(NotificacionAlerta.objects.count(), 0)

    def test_alerta_alta_sin_destinatario_queda_pendiente_hasta_configurarlo(self):
        """El destinatario vacío ya no llega por un paciente sin médico.

        Se llamaba `..._sin_medico_...` y creaba un paciente ACTIVO con
        `medico_responsable=None`. Desde D12 ese estado no existe: la base lo
        rechaza. Pero el daño que la prueba protege —una alerta ALTA cuyo aviso
        no tiene a dónde ir— sigue siendo alcanzable por la vía que ahora es la
        única: un médico **sin correo configurado**. Es una de las cuatro
        condiciones que vigila la capa 3 de D12.

        Las aserciones no cambian: destinatario vacío, `CommandError`, y la
        notificación PENDIENTE con `ultimo_error='DestinatarioNoConfigurado'`.
        """
        from django.core.management import CommandError, call_command

        medico_sin_correo = get_user_model().objects.create_user(
            username='dr_sin_correo', password='x', is_staff=True,
        )
        paciente_sin_medico = Paciente.objects.create(
            nombre_completo="Sin Médico",
            telefono_whatsapp="+573019990003",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=medico_sin_correo,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente_sin_medico,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=paciente_sin_medico,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Sin medico.',
        )
        notificacion = NotificacionAlerta.objects.get()
        self.assertEqual(notificacion.destinatario, '')

        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion.refresh_from_db()
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'DestinatarioNoConfigurado')

    def test_backend_sin_entrega_confirmada_programa_reintento(self):
        from unittest.mock import patch
        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        with patch('signos_sintomas.notificaciones.send_mail', return_value=0):
            with self.assertRaises(CommandError):
                call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'EntregaEmailNoConfirmada')

    @override_settings(
        EMAIL_DELIVERY_PROVIDER='resend',
        RESEND_API_KEY='re_clave_prueba',
        RESEND_FROM_EMAIL='Seguimiento <onboarding@resend.dev>',
        EMAIL_TIMEOUT=7,
        PANEL_MEDICO_URL='https://ejemplo.test/acceso-seguro/',
    )
    def test_resend_entrega_por_https_con_idempotencia_y_sin_datos_clinicos(self):
        from unittest.mock import Mock, patch
        from django.core.management import call_command

        respuesta = Mock()
        respuesta.json.return_value = {'id': 'email_123'}
        alerta = self._crear_alerta_alta()

        with patch(
            'signos_sintomas.notificaciones.requests.post',
            return_value=respuesta,
        ) as post:
            call_command('procesar_notificaciones_email', verbosity=0)

        llamada = post.call_args
        self.assertEqual(llamada.args[0], 'https://api.resend.com/emails')
        self.assertEqual(llamada.kwargs['timeout'], 7)
        self.assertEqual(
            llamada.kwargs['headers']['Idempotency-Key'],
            f'alerta-alta-{alerta.pk}',
        )
        carga = llamada.kwargs['json']
        self.assertEqual(carga['to'], [self.medico.email])
        self.assertIn(f'alerta #{alerta.pk}', carga['text'])
        self.assertNotIn(self.paciente.nombre_completo, carga['text'])
        self.assertNotIn(self.paciente.telefono_whatsapp, carga['text'])
        self.assertNotIn(self.paciente.cedula, carga['text'])
        self.assertNotIn(alerta.mensaje, carga['text'])

    @override_settings(
        EMAIL_DELIVERY_PROVIDER='resend',
        RESEND_API_KEY='',
        RESEND_FROM_EMAIL='Seguimiento <onboarding@resend.dev>',
    )
    def test_resend_sin_clave_conserva_notificacion_pendiente(self):
        from django.core.management import CommandError, call_command

        alerta = self._crear_alerta_alta()
        with self.assertRaises(CommandError):
            call_command('procesar_notificaciones_email', verbosity=0)

        notificacion = NotificacionAlerta.objects.get(alerta=alerta)
        self.assertEqual(notificacion.estado, NotificacionAlerta.ESTADO_PENDIENTE)
        self.assertEqual(notificacion.ultimo_error, 'ProveedorEmailNoConfigurado')

    def test_notificacion_solo_al_alcanzar_alta_no_en_recurrencia(self):
        def _reg(fc):
            return RegistroDiario.objects.create(
                paciente=self.paciente,
                temperatura=Decimal('37.0'), dolor_eva=2,
                aspecto_drenaje='sin_drenaje', presencia_gases=True,
                episodios_nauseas=0, frecuencia_cardiaca=fc,
            )

        evaluar_registro(_reg(120))
        self.assertEqual(NotificacionAlerta.objects.count(), 0)

        evaluar_registro(_reg(150))
        self.assertEqual(NotificacionAlerta.objects.count(), 1)

        evaluar_registro(_reg(155))
        self.assertEqual(NotificacionAlerta.objects.count(), 1)
        self.assertEqual(Alerta.objects.filter(tipo='TAQUICARDIA').count(), 1)


class NotificacionConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        medico = get_user_model().objects.create_user(
            username='medico_notificacion_concurrente',
            password='pass',
            email='medico-concurrente@test.com',
        )
        paciente = Paciente.objects.create(
            nombre_completo='Paciente Notificacion Concurrente',
            telefono_whatsapp='+573006660003',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            medico_responsable=medico,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal('38.5'),
            dolor_eva=2,
            tiene_drenaje=False,
            aspecto_drenaje='sin_drenaje',
            presencia_gases=True,
            episodios_nauseas=0,
        )
        alerta = Alerta.objects.create(
            paciente=paciente,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Prueba de concurrencia',
        )
        self.notificacion = NotificacionAlerta.objects.get(alerta=alerta)

    def test_dos_workers_no_envian_la_misma_notificacion_dos_veces(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from .notificaciones import procesar_notificaciones_pendientes

        iniciado = Event()
        liberar = Event()

        def enviar_lento(notificacion):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el primer worker.')

        def procesar():
            close_old_connections()
            try:
                return procesar_notificaciones_pendientes(limite=1)
            finally:
                close_old_connections()

        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=enviar_lento,
        ) as enviar:
            with ThreadPoolExecutor(max_workers=2) as executor:
                primero_futuro = executor.submit(procesar)
                self.assertTrue(iniciado.wait(timeout=10))
                segundo = executor.submit(procesar).result(timeout=10)
                liberar.set()
                primero = primero_futuro.result(timeout=10)

        self.notificacion.refresh_from_db()
        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(primero['enviadas'], 1)
        self.assertEqual(segundo['enviadas'], 0)
        self.assertEqual(self.notificacion.estado, NotificacionAlerta.ESTADO_ENVIADA)
        self.assertEqual(self.notificacion.intentos, 1)

    def test_el_envio_no_bloquea_la_fila_del_paciente(self):
        """Hallazgo 2: el envío de correo es una llamada de red potencialmente
        lenta. No debe mantener bloqueada la fila del paciente —sólo la de la
        notificación (of=('self',))— para no frenar el webhook del paciente,
        que necesita esa fila. Con el bloqueo del join completo, una transacción
        concurrente sobre el paciente esperaría a que terminara el envío.
        """
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from django.db import OperationalError

        from .notificaciones import procesar_notificaciones_pendientes

        paciente_pk = self.notificacion.alerta.paciente_id

        iniciado = Event()
        liberar = Event()

        def enviar_lento(notificacion):
            iniciado.set()
            if not liberar.wait(timeout=10):
                raise TimeoutError('La prueba no liberó el worker.')

        def procesar():
            close_old_connections()
            try:
                return procesar_notificaciones_pendientes(limite=1)
            finally:
                close_old_connections()

        paciente_bloqueado = {}
        with patch(
            'signos_sintomas.notificaciones._enviar',
            side_effect=enviar_lento,
        ):
            with ThreadPoolExecutor(max_workers=1) as executor:
                futuro = executor.submit(procesar)
                self.assertTrue(iniciado.wait(timeout=10))
                # Envío en curso → la notificación está bloqueada. Otra
                # transacción intenta bloquear la fila del paciente sin esperar.
                try:
                    with transaction.atomic():
                        Paciente.objects.select_for_update(nowait=True).get(
                            pk=paciente_pk,
                        )
                    paciente_bloqueado['valor'] = False
                except OperationalError:
                    paciente_bloqueado['valor'] = True
                finally:
                    liberar.set()
                    futuro.result(timeout=10)

        self.assertFalse(
            paciente_bloqueado['valor'],
            'El envío de correo mantuvo bloqueada la fila del paciente.',
        )


class CacheProductionConfigTests(TestCase):
    """D1 — Detecta dependencia redis faltante cuando producción usa RedisCache."""

    def test_redis_importable_para_settings_produccion(self):
        try:
            import redis  # noqa: F401
        except ImportError:
            self.fail(
                "Paquete 'redis' no instalado. "
                "settings_production.py usa RedisCache y requiere redis>=5. "
                "Instalar con: pip install 'redis>=5'"
            )

    def test_django_tiene_parche_de_seguridad_6_0_7(self):
        import django

        self.assertGreaterEqual(django.VERSION[:3], (6, 0, 7))

    def test_produccion_aplica_csp_sin_scripts_inline(self):
        """Cambió en el Loop C (hallazgo 11): ya no importa el módulo tal cual.

        `settings_production` ahora exige CSRF_TRUSTED_ORIGINS y REDIS_URL al
        cargarse —una variable vacía debe detener el arranque— y el .env de
        desarrollo no las tiene, así que el import directo fallaba aquí. La
        prueba carga el módulo con un entorno de producción mínimo y válido; lo
        que verifica (CSP y timeout de correo) no cambió.
        """
        from django.utils.csp import CSP
        from Registro_Post_Quirurgico.tests_configuracion import (
            ENTORNO_PRODUCCION_VALIDO,
            cargar_settings_produccion,
        )

        settings_production = cargar_settings_produccion(
            dict(ENTORNO_PRODUCCION_VALIDO)
        )

        self.assertIn(
            'django.middleware.csp.ContentSecurityPolicyMiddleware',
            settings_production.MIDDLEWARE,
        )
        self.assertEqual(settings_production.SECURE_CSP['script-src'], [CSP.SELF])
        self.assertNotIn(
            CSP.UNSAFE_INLINE,
            settings_production.SECURE_CSP['script-src'],
        )
        self.assertEqual(settings_production.EMAIL_TIMEOUT, 10)


class CheckInProgramadoModelTests(TestCase):
    """Bloque 1 — Modelo CheckInProgramado: constraints, defaults y relaciones."""

    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente CheckIn",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
        )
        self.hoy = timezone.localdate()
        self.hora_programada = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)

    def _crear_checkin(self, orden=1, etiqueta=CheckInProgramado.ETIQUETA_MANANA, **kwargs):
        defaults = dict(
            paciente=self.paciente,
            fecha_dia=self.hoy,
            orden=orden,
            etiqueta=etiqueta,
            hora_programada=self.hora_programada,
        )
        defaults.update(kwargs)
        return CheckInProgramado.objects.create(**defaults)

    def test_creacion_exitosa_campos_validos(self):
        checkin = self._crear_checkin()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertEqual(checkin.etiqueta, CheckInProgramado.ETIQUETA_MANANA)
        self.assertEqual(checkin.orden, 1)
        self.assertIsNone(checkin.fecha_respuesta)
        self.assertIsNone(checkin.registro)

    def test_estado_default_es_pendiente(self):
        checkin = self._crear_checkin(orden=2, etiqueta=CheckInProgramado.ETIQUETA_TARDE)
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)

    def test_unique_constraint_mismo_paciente_dia_orden(self):
        self._crear_checkin(orden=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear_checkin(orden=1)

    def test_dos_checkins_mismo_dia_distinto_orden_permitidos(self):
        manana = self._crear_checkin(orden=1, etiqueta=CheckInProgramado.ETIQUETA_MANANA)
        tarde  = self._crear_checkin(orden=2, etiqueta=CheckInProgramado.ETIQUETA_TARDE)
        self.assertEqual(CheckInProgramado.objects.filter(paciente=self.paciente, fecha_dia=self.hoy).count(), 2)
        self.assertNotEqual(manana.pk, tarde.pk)

    def test_fecha_dia_no_es_auto_now_add(self):
        ayer = self.hoy - timedelta(days=1)
        checkin = self._crear_checkin(fecha_dia=ayer)
        checkin.refresh_from_db()
        self.assertEqual(checkin.fecha_dia, ayer)

    def test_registro_onetooone_puede_asignarse(self):
        from decimal import Decimal
        checkin = self._crear_checkin()
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=3,
            aspecto_drenaje="seroso",
            presencia_gases=True,
            episodios_nauseas=0,
        )
        checkin.registro = registro
        checkin.estado = CheckInProgramado.ESTADO_COMPLETADO
        checkin.fecha_respuesta = timezone.now()
        checkin.save()
        checkin.refresh_from_db()
        self.assertEqual(checkin.registro.pk, registro.pk)
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertIsNotNone(checkin.fecha_respuesta)

    def test_str_representacion(self):
        checkin = self._crear_checkin()
        self.assertIn(str(self.hoy), str(checkin))
        self.assertIn('MAÑANA', str(checkin))
        self.assertIn('PENDIENTE', str(checkin))


@freeze_time(ANCLA_MEDIANOCHE)
class AlertFechaReferenciaTests(TestCase):
    """Bloque 2A — parámetro fecha_referencia en evaluar_registro (decisión 0-①)."""

    def _paciente(self, tel):
        return Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente FechaRef",
            telefono_whatsapp=tel,
            fecha_cirugia=timezone.localdate() - timedelta(days=10),
        )

    def _reg_sin_gases(self, paciente, dias_atras=0):
        reg = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=False,
            episodios_nauseas=0,
        )
        if dias_atras:
            RegistroDiario.objects.filter(pk=reg.pk).update(
                fecha_registro=timezone.now() - timedelta(days=dias_atras)
            )
        return reg

    def test_sin_fecha_referencia_usa_fecha_local_del_registro(self):
        """Backward compat: evaluar_registro sin fecha_referencia usa la
        fecha local del registro. Un día sin gases → BAJA ILEO_PARALITICO."""
        paciente = self._paciente("+573008889001")
        reg = self._reg_sin_gases(paciente)
        alertas = evaluar_registro(reg)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "BAJA")

    def test_fecha_referencia_explicita_cambia_agrupamiento(self):
        """Cruce de medianoche: registro con fecha_registro=hoy pertenece al
        check-in de ayer. Con fecha_referencia=ayer el engine busca
        fecha_registro__date=ayer. El registro nocturno (fecha_registro=hoy)
        no entra en ese grupo → 2 días sin gases (ayer+antier) → MEDIA,
        en vez de 3 días (hoy+ayer+antier) → ALTA que daría sin fecha_referencia."""
        paciente = self._paciente("+573008889002")
        ayer = timezone.localdate() - timedelta(days=1)

        self._reg_sin_gases(paciente, dias_atras=2)  # antier
        self._reg_sin_gases(paciente, dias_atras=1)  # ayer
        reg_nocturno = self._reg_sin_gases(paciente, dias_atras=0)  # fecha_registro=hoy

        alertas = evaluar_registro(reg_nocturno, fecha_referencia=ayer)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "MEDIA")  # 2 días (antier+ayer)

    def test_sin_fecha_referencia_tres_dias_da_alta(self):
        """Control: mismo setup con fecha_referencia=hoy (default) agrupa
        hoy+ayer+antier → ALTA (3 días sin gases)."""
        paciente = self._paciente("+573008889003")
        self._reg_sin_gases(paciente, dias_atras=2)
        self._reg_sin_gases(paciente, dias_atras=1)
        reg_hoy = self._reg_sin_gases(paciente)

        alertas = evaluar_registro(reg_hoy)  # default = hoy
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "ALTA")  # 3 días


class AlertDeduplicacionTests(TestCase):
    """Agrupación de alertas por problema (decisión Arquitecto 10/07/2026):
    una sola alerta ABIERTA por (paciente, tipo); las recurrencias la
    ACTUALIZAN (contador `veces` + severidad máxima), no crean filas nuevas.
    Reemplaza la deduplicación por día del Bloque 2B (Opción A+)."""

    def _paciente(self, tel):
        return Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Dedup",
            telefono_whatsapp=tel,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
        )

    def _reg_fc(self, paciente, fc):
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            frecuencia_cardiaca=fc,
        )

    def _reg_temp(self, paciente, temp):
        return RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal(str(temp)),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )

    def test_recurrencia_misma_severidad_sube_contador(self):
        """Dos check-ins el mismo día con la misma condición y severidad:
        no se crea otra alerta — se actualiza la abierta y sube el contador."""
        paciente = self._paciente("+573008881001")
        alertas1 = evaluar_registro(self._reg_fc(paciente, 150))  # ALTA TAQUICARDIA
        self.assertEqual(len([a for a in alertas1 if a.tipo == "TAQUICARDIA"]), 1)

        alertas2 = evaluar_registro(self._reg_fc(paciente, 155))  # también ALTA → actualiza
        taqui2 = [a for a in alertas2 if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui2), 1)
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)
        self.assertEqual(taqui2[0].veces, 2)
        self.assertEqual(taqui2[0].detecciones.count(), 2)

    def test_escalamiento_intradiario_actualiza_misma_alerta(self):
        """Mañana BAJA → tarde MEDIA (mismo día): la alerta abierta sube a
        MEDIA y el contador a 2, sin crear una segunda fila."""
        paciente = self._paciente("+573008881002")
        alertas1 = evaluar_registro(self._reg_fc(paciente, 105))  # BAJA
        self.assertEqual([a for a in alertas1 if a.tipo == "TAQUICARDIA"][0].severidad, "BAJA")

        alertas2 = evaluar_registro(self._reg_fc(paciente, 120))  # MEDIA > BAJA → escala
        taqui2 = [a for a in alertas2 if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui2), 1)
        self.assertEqual(taqui2[0].severidad, "MEDIA")
        self.assertEqual(taqui2[0].veces, 2)
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

    def test_severidad_menor_no_baja_pero_cuenta(self):
        """Mañana ALTA → tarde BAJA del mismo tipo: la alerta NO baja de
        severidad (se queda ALTA), pero la recurrencia sí suma al contador."""
        paciente = self._paciente("+573008881003")
        evaluar_registro(self._reg_fc(paciente, 150))  # ALTA
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

        alertas2 = evaluar_registro(self._reg_fc(paciente, 103))  # BAJA → no baja severidad
        taqui2 = [a for a in alertas2 if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui2), 1)
        self.assertEqual(taqui2[0].severidad, "ALTA")
        self.assertEqual(taqui2[0].veces, 2)
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

    def test_recurrencia_entre_dias_actualiza_alerta(self):
        """Recurrencia entre días: SEPSIS ayer + SEPSIS hoy = UNA sola alerta
        abierta con el contador en 2 (antes creaba una por día)."""
        paciente = self._paciente("+573008881004")
        ayer = timezone.localdate() - timedelta(days=1)

        reg_ayer = self._reg_temp(paciente, "38.0")
        RegistroDiario.objects.filter(pk=reg_ayer.pk).update(
            fecha_registro=timezone.now() - timedelta(days=1)
        )
        evaluar_registro(reg_ayer, fecha_referencia=ayer)
        # Simular que la alerta fue creada ayer (en producción sí lo sería)
        Alerta.objects.filter(paciente=paciente, tipo="SEPSIS").update(
            fecha_alerta=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)

        alertas_hoy = evaluar_registro(self._reg_temp(paciente, "38.1"))
        sepsis_hoy = [a for a in alertas_hoy if a.tipo == "SEPSIS"]
        self.assertEqual(len(sepsis_hoy), 1)
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)
        self.assertEqual(sepsis_hoy[0].veces, 2)

    def test_diferentes_tipos_mismo_dia_no_se_bloquean(self):
        """SEPSIS e ILEO_PARALITICO son tipos distintos: coexisten en el mismo día."""
        paciente = self._paciente("+573008881005")
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("38.0"),  # SEPSIS ALTA
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=False,  # ILEO BAJA
            episodios_nauseas=0,
        )
        alertas = evaluar_registro(registro)
        tipos = {a.tipo for a in alertas}
        self.assertIn("SEPSIS", tipos)
        self.assertIn("ILEO_PARALITICO", tipos)

    def test_gases_baja_y_nauseas_alta_mismo_checkin_una_ileo_alta(self):  # noqa: E501
        """Gases=False (BAJA) y nauseas=5 (ALTA) en el MISMO registro:
        _evaluar_gases abre ILEO, _evaluar_nauseas la sube a ALTA — es UNA
        sola alerta ILEO (misma detección/check-in), con severidad ALTA y
        contador 1 (no cuenta doble dentro del mismo check-in)."""
        paciente = self._paciente("+573008881006")
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=False,  # → ILEO BAJA
            episodios_nauseas=5,    # → ILEO ALTA
        )
        alertas = evaluar_registro(registro)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "ALTA")
        self.assertEqual(ileo[0].veces, 1)
        self.assertEqual(Alerta.objects.filter(tipo="ILEO_PARALITICO").count(), 1)
        detalle = ileo[0].detecciones.get()
        self.assertEqual(detalle.registro, registro)
        self.assertEqual(detalle.severidad_detectada, 'ALTA')

        # D5: el detalle conserva TODOS los signos concurrentes, no solo el más
        # grave. Distensión sola puede ser muchas cosas; ausencia de tránsito
        # más vómito es el cuadro de íleo — la evidencia convergente es más
        # fuerte que la suma de sus partes y el médico debe poder verla.
        self.assertIn('episodios de náuseas', detalle.mensaje_detectado)
        self.assertIn('sin gases', detalle.mensaje_detectado)
        # El signo más grave encabeza; el titular de la alerta no cambia.
        self.assertTrue(
            detalle.mensaje_detectado.startswith('5 episodios de náuseas'),
            f'El signo ALTA debe encabezar el detalle: {detalle.mensaje_detectado!r}',
        )
        self.assertNotIn('sin gases', ileo[0].mensaje)

    def test_reevaluar_no_duplica_los_signos_concurrentes(self):
        """Reintentar el motor sobre el mismo registro no repite el texto (D5).

        `reintentar_evaluaciones_alertas` vuelve a correr las ocho reglas sobre
        un registro en estado PENDIENTE/ERROR. La acumulación debe ser
        idempotente o el detalle crecería en cada reintento.
        """
        paciente = self._paciente("+573008881016")
        registro = RegistroDiario.objects.create(
            paciente=paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=False,   # → ILEO BAJA
            episodios_nauseas=5,     # → ILEO ALTA
        )

        evaluar_registro(registro)
        evaluar_registro(registro)
        evaluar_registro(registro)

        alerta = Alerta.objects.get(tipo="ILEO_PARALITICO")
        detalle = alerta.detecciones.get()
        self.assertEqual(alerta.veces, 1)
        self.assertEqual(detalle.mensaje_detectado.count('sin gases'), 1)
        self.assertEqual(detalle.mensaje_detectado.count('episodios de náuseas'), 1)

    def test_reintentar_mismo_registro_no_duplica_detalle_ni_contador(self):
        paciente = self._paciente("+573008881008")
        registro = self._reg_fc(paciente, 150)

        primera = evaluar_registro(registro)
        segunda = evaluar_registro(registro)

        alerta = [a for a in segunda if a.tipo == 'TAQUICARDIA'][0]
        self.assertEqual([a for a in primera if a.tipo == 'TAQUICARDIA'][0].pk, alerta.pk)
        self.assertEqual(alerta.veces, 1)
        self.assertEqual(alerta.detecciones.count(), 1)

    def test_alerta_legacy_conserva_contador_y_desglosa_solo_lo_nuevo(self):
        paciente = self._paciente("+573008881009")
        registro_anterior = self._reg_fc(paciente, 150)
        alerta = Alerta.objects.create(
            paciente=paciente,
            registro_origen=registro_anterior,
            tipo='TAQUICARDIA',
            severidad='ALTA',
            mensaje='Contador previo sin desglose',
            veces=4,
            fecha_ultima_deteccion=registro_anterior.fecha_registro,
        )

        registro_nuevo = self._reg_fc(paciente, 152)
        resultado = evaluar_registro(registro_nuevo)

        alerta = [a for a in resultado if a.tipo == 'TAQUICARDIA'][0]
        self.assertEqual(alerta.veces, 5)
        self.assertEqual(alerta.detecciones.count(), 1)
        self.assertEqual(alerta.detecciones.get().registro, registro_nuevo)

    def test_resolver_y_recurrencia_crea_alerta_nueva(self):
        """Si el médico resuelve la alerta y el problema reaparece después,
        se abre una alerta NUEVA (evento nuevo), no se reabre la vieja."""
        paciente = self._paciente("+573008881007")
        evaluar_registro(self._reg_fc(paciente, 150))  # ALTA
        alerta = Alerta.objects.get(tipo="TAQUICARDIA")
        self.assertEqual(alerta.veces, 1)

        alerta.resuelta = True          # el médico la atiende
        alerta.fecha_resolucion = timezone.now()
        alerta.motivo_resolucion = Alerta.MOTIVO_CONTACTO
        alerta.save()

        alertas2 = evaluar_registro(self._reg_fc(paciente, 152))  # reaparece
        taqui = [a for a in alertas2 if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertFalse(taqui[0].resuelta)
        self.assertEqual(taqui[0].veces, 1)  # arranca de cero
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 2)


class AlertDeduplicacionConcurrenteTests(TransactionTestCase):
    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Concurrencia Alertas',
            telefono_whatsapp='+573008881099',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
        )
        self.registros = [
            RegistroDiario.objects.create(
                paciente=self.paciente,
                temperatura=Decimal('38.0'),
                dolor_eva=2,
                tiene_drenaje=False,
                presencia_gases=True,
                episodios_nauseas=0,
            )
            for _ in range(2)
        ]

    def test_bd_impide_dos_alertas_abiertas_del_mismo_tipo(self):
        Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registros[0],
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Primera',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alerta.objects.create(
                    paciente=self.paciente,
                    registro_origen=self.registros[1],
                    tipo='SEPSIS',
                    severidad='ALTA',
                    mensaje='Segunda',
                )

    def test_dos_workers_convergen_en_una_alerta_abierta(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from .alert_engine import _registrar_alerta

        barrera = Barrier(2)

        def registrar(registro_pk):
            close_old_connections()
            try:
                registro = RegistroDiario.objects.get(pk=registro_pk)
                barrera.wait(timeout=5)
                alerta = _registrar_alerta(
                    registro,
                    'SEPSIS',
                    'ALTA',
                    'Detección concurrente',
                )
                return alerta.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(
                registrar,
                [registro.pk for registro in self.registros],
            ))

        self.assertEqual(resultados[0], resultados[1])
        alertas = Alerta.objects.filter(
            paciente=self.paciente,
            tipo='SEPSIS',
            resuelta=False,
        )
        self.assertEqual(alertas.count(), 1)
        self.assertEqual(alertas.get().veces, 2)


class DeteccionAlertaConstraintTests(TestCase):
    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Evidencia',
            telefono_whatsapp='+573008881198',
            fecha_cirugia=timezone.localdate(),
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        self.alerta = Alerta.objects.create(
            paciente=self.paciente,
            registro_origen=self.registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje='Prueba de evidencia',
        )

    def test_bd_exige_exactamente_una_fuente(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeteccionAlerta.objects.create(
                    alerta=self.alerta,
                    severidad_detectada='ALTA',
                    mensaje_detectado='Sin fuente',
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeteccionAlerta.objects.create(
                    alerta=self.alerta,
                    registro=self.registro,
                    checkin=self.checkin,
                    severidad_detectada='ALTA',
                    mensaje_detectado='Dos fuentes',
                )

    def test_bd_impide_repetir_fuente_en_la_misma_alerta(self):
        DeteccionAlerta.objects.create(
            alerta=self.alerta,
            registro=self.registro,
            severidad_detectada='ALTA',
            mensaje_detectado='Primera',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeteccionAlerta.objects.create(
                    alerta=self.alerta,
                    registro=self.registro,
                    severidad_detectada='ALTA',
                    mensaje_detectado='Duplicada',
                )


@freeze_time(ANCLA_MEDIANOCHE)
class SchedulerTests(TestCase):
    """Bloque 4 — Management commands del scheduler y alerta SILENCIO."""

    def _paciente(self, tel="+573009990001"):
        return Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Scheduler",
            telefono_whatsapp=tel,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            activo=True,
        )

    def _checkin(self, paciente, orden=1, etiqueta=None, dias_atras=0,
                 estado=CheckInProgramado.ESTADO_PENDIENTE, horas_atras=0):
        if etiqueta is None:
            etiqueta = (
                CheckInProgramado.ETIQUETA_TARDE
                if orden == 2 else CheckInProgramado.ETIQUETA_MANANA
            )
        fecha_dia = timezone.localdate() - timedelta(days=dias_atras)
        hora_prog = timezone.now() - timedelta(hours=horas_atras)
        ci = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=fecha_dia,
            orden=orden,
            etiqueta=etiqueta,
            hora_programada=hora_prog,
            estado=estado,
        )
        return ci

    # -------------------------------------------------------------------------
    # crear_checkins_diarios
    # -------------------------------------------------------------------------

    def test_crear_checkins_crea_dos_por_paciente(self):
        """Crea 2 check-ins (mañana y tarde) para el paciente activo de hoy."""
        from django.core.management import call_command
        self._paciente()
        call_command('crear_checkins_diarios', verbosity=0)
        self.assertEqual(CheckInProgramado.objects.count(), 2)
        ordenes = set(CheckInProgramado.objects.values_list('orden', flat=True))
        self.assertEqual(ordenes, {1, 2})

    def test_crear_checkins_es_idempotente(self):
        """Llamar el comando dos veces no duplica check-ins."""
        from django.core.management import call_command
        self._paciente()
        call_command('crear_checkins_diarios', verbosity=0)
        call_command('crear_checkins_diarios', verbosity=0)
        self.assertEqual(CheckInProgramado.objects.count(), 2)

    def test_crear_checkins_ignora_pacientes_inactivos(self):
        """Pacientes con activo=False no reciben check-ins."""
        from django.core.management import call_command
        paciente = self._paciente()
        paciente.activo = False
        paciente.save()
        call_command('crear_checkins_diarios', verbosity=0)
        self.assertEqual(CheckInProgramado.objects.count(), 0)

    # -------------------------------------------------------------------------
    # cerrar_checkins_vencidos y alerta SILENCIO
    # -------------------------------------------------------------------------

    def test_checkin_pendiente_dentro_de_gracia_no_se_cierra(self):
        """Check-in con < 10 horas desde hora_programada: no se toca."""
        from django.core.management import call_command
        paciente = self._paciente()
        self._checkin(paciente, horas_atras=5)  # 5 h < 10 h de gracia
        call_command('cerrar_checkins_vencidos', verbosity=0)
        checkin = CheckInProgramado.objects.get()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_checkin_vencido_con_conversacion_reciente_no_se_cierra(self):
        """El cron no marca silencio mientras el paciente está respondiendo."""
        from django.core.management import call_command

        paciente = self._paciente()
        checkin = self._checkin(paciente, horas_atras=11)
        ConversacionWhatsApp.objects.create(
            paciente=paciente,
            checkin_actual=checkin,
            estado=ConversacionWhatsApp.ESTADO_DOLOR,
            temp_temperatura=Decimal('37.0'),
        )

        call_command('cerrar_checkins_vencidos', verbosity=0)

        checkin.refresh_from_db()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_PENDIENTE)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_conversacion_abandonada_fuera_de_gracia_si_se_cierra(self):
        from django.core.management import call_command

        paciente = self._paciente()
        checkin = self._checkin(paciente, horas_atras=11)
        conversacion = ConversacionWhatsApp.objects.create(
            paciente=paciente,
            checkin_actual=checkin,
            estado=ConversacionWhatsApp.ESTADO_DOLOR,
            temp_temperatura=Decimal('37.0'),
        )
        ConversacionWhatsApp.objects.filter(pk=conversacion.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(hours=11),
        )

        call_command('cerrar_checkins_vencidos', verbosity=0)

        checkin.refresh_from_db()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)
        self.assertEqual(Alerta.objects.filter(tipo='SILENCIO').count(), 1)

    def test_silencios_repetidos_actualizan_una_sola_alerta_abierta(self):
        from django.core.management import call_command

        paciente = self._paciente()
        primero = self._checkin(paciente, orden=1, dias_atras=1, horas_atras=24)
        call_command('cerrar_checkins_vencidos', verbosity=0)
        primero.refresh_from_db()
        self.assertEqual(primero.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)

        segundo = self._checkin(paciente, orden=2, horas_atras=11)
        call_command('cerrar_checkins_vencidos', verbosity=0)

        segundo.refresh_from_db()
        alerta = Alerta.objects.get(paciente=paciente, tipo='SILENCIO')
        self.assertEqual(segundo.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)
        self.assertFalse(alerta.resuelta)
        self.assertEqual(alerta.veces, 2)
        self.assertEqual(alerta.detecciones.count(), 2)
        self.assertSetEqual(
            set(alerta.detecciones.values_list('checkin_id', flat=True)),
            {primero.pk, segundo.pk},
        )

    def test_checkin_vencido_se_cierra_y_crea_alerta_silencio_baja(self):
        """1 check-in sin respuesta → racha 1 → SILENCIO BAJA."""
        from django.core.management import call_command
        paciente = self._paciente()
        self._checkin(paciente, horas_atras=11)  # > 10 h → vencido
        call_command('cerrar_checkins_vencidos', verbosity=0)
        checkin = CheckInProgramado.objects.get()
        self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)
        alerta = Alerta.objects.get(tipo='SILENCIO')
        self.assertEqual(alerta.severidad, 'BAJA')
        self.assertIsNone(alerta.registro_origen)
        self.assertEqual(alerta.detecciones.get().checkin, checkin)

    def test_mismo_checkin_silencio_no_duplica_deteccion(self):
        from .alert_engine import registrar_alerta_silencio

        paciente = self._paciente('+573009990099')
        checkin = self._checkin(paciente, horas_atras=11)

        primera = registrar_alerta_silencio(checkin, 'BAJA', 'Sin respuesta')
        segunda = registrar_alerta_silencio(checkin, 'MEDIA', 'Persiste sin respuesta')

        segunda.refresh_from_db()
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.veces, 1)
        self.assertEqual(segunda.severidad, 'MEDIA')
        self.assertEqual(segunda.detecciones.count(), 1)
        self.assertEqual(
            segunda.detecciones.get().severidad_detectada,
            'MEDIA',
        )

    def test_dos_checkins_consecutivos_dan_silencio_media(self):
        """2 check-ins NO_RESPONDIDO consecutivos → racha 2 → SILENCIO MEDIA."""
        from django.core.management import call_command
        paciente = self._paciente()
        # Ayer: ya estaba NO_RESPONDIDO
        ci_ayer = self._checkin(paciente, orden=1, dias_atras=1, horas_atras=25)
        ci_ayer.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
        ci_ayer.save()
        # Hoy: vence ahora
        self._checkin(paciente, orden=1, horas_atras=11)
        call_command('cerrar_checkins_vencidos', verbosity=0)
        alerta = Alerta.objects.filter(tipo='SILENCIO').order_by('-fecha_alerta').first()
        self.assertEqual(alerta.severidad, 'MEDIA')

    def test_tres_checkins_consecutivos_dan_silencio_media(self):
        """3 check-ins NO_RESPONDIDO consecutivos → racha 3 → SILENCIO MEDIA.

        Antes de la decisión D1 este caso esperaba ALTA, porque la escalera era
        1/2/3. Con dos check-ins diarios, una racha de 3 es día y medio de
        silencio; el umbral ALTA se movió a 4 para que corresponda a dos días
        calendario completos. El caso ALTA lo cubre
        test_escalera_silencio_con_scheduler_real_llega_a_alta.
        """
        from django.core.management import call_command
        paciente = self._paciente()
        for orden, dias in [(1, 2), (2, 1)]:
            ci = self._checkin(paciente, orden=orden, dias_atras=dias, horas_atras=50)
            ci.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
            ci.save()
        self._checkin(paciente, orden=1, horas_atras=11)
        call_command('cerrar_checkins_vencidos', verbosity=0)
        alerta = Alerta.objects.filter(tipo='SILENCIO').order_by('-fecha_alerta').first()
        self.assertEqual(alerta.severidad, 'MEDIA')

    def test_checkin_completado_rompe_racha(self):
        """Un check-in COMPLETADO entre medias reinicia la racha → SILENCIO BAJA."""
        from django.core.management import call_command
        paciente = self._paciente()
        # Anteayer: NO_RESPONDIDO
        ci_viejo = self._checkin(paciente, orden=1, dias_atras=2, horas_atras=50)
        ci_viejo.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
        ci_viejo.save()
        # Ayer: COMPLETADO → rompe la racha
        ci_completado = self._checkin(paciente, orden=2, dias_atras=1, horas_atras=25)
        ci_completado.estado = CheckInProgramado.ESTADO_COMPLETADO
        ci_completado.save()
        # Hoy: vence ahora → racha debe ser 1 (solo este)
        self._checkin(paciente, orden=1, horas_atras=11)
        call_command('cerrar_checkins_vencidos', verbosity=0)
        alerta = Alerta.objects.filter(tipo='SILENCIO').order_by('-fecha_alerta').first()
        self.assertEqual(alerta.severidad, 'BAJA')

    # -------------------------------------------------------------------------
    # Escalera de SILENCIO con el scheduler real (D1)
    #
    # Los tests de racha de arriba prefijan los turnos previos a mano y dejan un
    # ÚNICO check-in pendiente. El scheduler real nunca produce ese estado: crea
    # dos turnos por día y siempre deja alguno PENDIENTE. Estos casos reproducen
    # esa realidad — por eso son los que detectan el subconteo de la racha.
    # -------------------------------------------------------------------------

    def _turnos_vencidos(self, paciente, dias):
        """Crea los 2 turnos de cada día indicado, vencidos y sin responder."""
        creados = []
        for dias_atras in dias:
            for orden in (1, 2):
                creados.append(self._checkin(
                    paciente,
                    orden=orden,
                    dias_atras=dias_atras,
                    # Muy por encima de las 10 h de gracia.
                    horas_atras=24 * dias_atras + 12,
                ))
        return creados

    def _correr_scheduler_matutino(self, paciente):
        """Ejecuta crear_checkins_diarios + cerrar_checkins_vencidos, en ese orden.

        Es la secuencia real de `cron_matutino`. Los turnos de hoy que crea el
        scheduler quedan a las 7:00 y 14:00; en producción el cron corre a las
        6:00 AM, así que ambos están todavía en el futuro y ninguno vence en esa
        misma corrida. Aquí se normalizan a "recién programados" para que el
        resultado no dependa de la hora en que se ejecute la suite — sin eso, un
        test corrido por la tarde cerraría también el turno de la mañana de hoy.
        """
        from django.core.management import call_command

        call_command('crear_checkins_diarios', verbosity=0)
        CheckInProgramado.objects.filter(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
        ).update(hora_programada=timezone.now())
        call_command('cerrar_checkins_vencidos', verbosity=0)

    def test_escalera_silencio_con_scheduler_real_llega_a_alta(self):
        """Paciente con 2 días completos sin responder → SILENCIO ALTA.

        Reproduce la secuencia exacta de cron_matutino: crear_checkins_diarios
        deja los turnos de HOY en PENDIENTE y solo después corre el cierre. Esos
        turnos pendientes no deben interrumpir el conteo de la racha.
        """
        paciente = self._paciente()
        self._turnos_vencidos(paciente, dias=[2, 1])   # 4 turnos perdidos

        self._correr_scheduler_matutino(paciente)   # deja 2 de hoy PENDIENTE

        self.assertEqual(
            CheckInProgramado.objects.filter(
                paciente=paciente,
                estado=CheckInProgramado.ESTADO_NO_RESPONDIDO,
            ).count(),
            4,
            'Los 4 turnos vencidos deben cerrarse como NO_RESPONDIDO.',
        )
        alerta = Alerta.objects.get(paciente=paciente, tipo='SILENCIO')
        self.assertEqual(
            alerta.severidad,
            'ALTA',
            'Cuatro turnos consecutivos sin responder (2 días completos) deben '
            'escalar a ALTA; los turnos de hoy, aún pendientes, no rompen la racha.',
        )
        self.assertEqual(alerta.veces, 4)

    def test_dos_turnos_perdidos_dan_media_pese_a_turnos_pendientes(self):
        """Racha 2 → MEDIA, con turnos posteriores todavía pendientes."""
        paciente = self._paciente()
        self._turnos_vencidos(paciente, dias=[1])   # 2 turnos perdidos

        self._correr_scheduler_matutino(paciente)

        alerta = Alerta.objects.get(paciente=paciente, tipo='SILENCIO')
        self.assertEqual(alerta.severidad, 'MEDIA')
        self.assertEqual(alerta.veces, 2)

    def test_tres_turnos_perdidos_todavia_no_alcanzan_alta(self):
        """Racha 3 → MEDIA. ALTA exige 4 (dos días calendario completos, D1)."""
        paciente = self._paciente()
        self._turnos_vencidos(paciente, dias=[1])
        # Un tercer turno perdido, del día anterior por la tarde.
        self._checkin(paciente, orden=2, dias_atras=2, horas_atras=24 * 2 + 12)

        self._correr_scheduler_matutino(paciente)

        alerta = Alerta.objects.get(paciente=paciente, tipo='SILENCIO')
        self.assertEqual(
            alerta.severidad,
            'MEDIA',
            'El umbral ALTA es 4 turnos, no 3 (decisión D1).',
        )
        self.assertEqual(alerta.veces, 3)

    def test_turno_anterior_pendiente_no_interrumpe_la_racha(self):
        """Un PENDIENTE anterior (cron caído) se ignora y el conteo sigue.

        Se prueba `_calcular_racha` directamente: montar este estado con el
        command exigiría que el propio cron dejara un turno sin cerrar, y
        entonces el resultado dependería del orden de cierre en vez de aislar
        la regla. Base clínica (D1): un check-in de un día pasado ya no puede
        responderse —el bot solo sirve los de hoy— así que terminará en
        NO_RESPONDIDO; una falla de infraestructura no debe degradar una alerta.
        """
        from signos_sintomas.management.commands.cerrar_checkins_vencidos import (
            _calcular_racha,
        )

        paciente = self._paciente()
        # Días -3 y -2 sin responder, ya cerrados: 4 turnos.
        for dias_atras in (3, 2):
            for orden in (1, 2):
                ci = self._checkin(
                    paciente, orden=orden, dias_atras=dias_atras,
                    horas_atras=24 * dias_atras + 12,
                )
                ci.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
                ci.save(update_fields=['estado'])

        # Día -1 mañana: el cron no alcanzó a cerrarlo y sigue PENDIENTE.
        self._checkin(paciente, orden=1, dias_atras=1, horas_atras=36)
        # Día -1 tarde: el que se está cerrando ahora.
        ci_tarde = self._checkin(paciente, orden=2, dias_atras=1, horas_atras=30)

        self.assertEqual(
            _calcular_racha(paciente, ci_tarde),
            5,
            'El turno pendiente por una falla del cron debe ignorarse y el '
            'conteo continuar: 4 turnos cerrados + el actual = 5.',
        )


class CheckInConcurrenciaTests(TransactionTestCase):
    def test_inicio_del_bot_y_cierre_cron_no_dejan_estado_contradictorio(self):
        from concurrent.futures import ThreadPoolExecutor
        from io import StringIO
        from threading import Barrier

        from django.core.management import call_command

        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo='Paciente Carrera CheckIn',
            telefono_whatsapp='+573009991100',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            consentimiento_informado=True,
        )
        checkin = CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timedelta(hours=11),
        )
        barrera = Barrier(2)

        def iniciar_bot():
            close_old_connections()
            try:
                barrera.wait(timeout=5)
                return bot.procesar_mensaje('whatsapp:+573009991100', 'hola')
            finally:
                close_old_connections()

        def cerrar_vencidos():
            close_old_connections()
            try:
                barrera.wait(timeout=5)
                call_command(
                    'cerrar_checkins_vencidos',
                    stdout=StringIO(),
                    verbosity=0,
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            respuesta_futura = executor.submit(iniciar_bot)
            cierre_futuro = executor.submit(cerrar_vencidos)
            respuesta = respuesta_futura.result(timeout=10)
            cierre_futuro.result(timeout=10)

        checkin.refresh_from_db()
        conversacion = ConversacionWhatsApp.objects.get(paciente=paciente)
        if checkin.estado == CheckInProgramado.ESTADO_PENDIENTE:
            self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
            self.assertEqual(
                conversacion.estado,
                ConversacionWhatsApp.ESTADO_TEMPERATURA,
            )
            self.assertEqual(conversacion.checkin_actual, checkin)
            self.assertFalse(Alerta.objects.filter(tipo='SILENCIO').exists())
        else:
            self.assertEqual(checkin.estado, CheckInProgramado.ESTADO_NO_RESPONDIDO)
            self.assertEqual(respuesta, bot.MSG_SIN_CHECKIN)
            self.assertEqual(conversacion.estado, ConversacionWhatsApp.ESTADO_INICIO)
            self.assertIsNone(conversacion.checkin_actual)
            self.assertTrue(Alerta.objects.filter(tipo='SILENCIO').exists())


class PacienteCedulaTests(TestCase):
    """Sprint 5, Bloque 1A — campo cedula (P-4: identificador único, obligatorio)."""

    def test_paciente_sin_cedula_no_rompe_creacion(self):
        """Registros legado (sin cedula) siguen pudiéndose crear — null permitido."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Legado",
            telefono_whatsapp="+573001112222",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertIsNone(paciente.cedula)

    def test_cedula_duplicada_viola_unicidad(self):
        Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Uno",
            cedula="123456789",
            telefono_whatsapp="+573001112223",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
                    nombre_completo="Paciente Dos",
                    cedula="123456789",
                    telefono_whatsapp="+573001112224",
                    fecha_cirugia=timezone.localdate(),
                )

    def test_dos_pacientes_sin_cedula_no_violan_unicidad(self):
        """NULL no cuenta como duplicado en la restricción unique (Postgres)."""
        Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Cedula 1",
            telefono_whatsapp="+573001112225",
            fecha_cirugia=timezone.localdate(),
        )
        Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Sin Cedula 2",
            telefono_whatsapp="+573001112226",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertEqual(Paciente.objects.count(), 2)

    # -----------------------------------------------------------------
    # A-2: full_clean() exige cédula en pacientes nuevos
    # -----------------------------------------------------------------

    def test_full_clean_sin_cedula_en_paciente_nuevo_lanza_error(self):
        paciente = Paciente(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nuevo Sin Cedula",
            telefono_whatsapp="+573001112227",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(ValidationError) as ctx:
            paciente.full_clean()
        self.assertIn('cedula', ctx.exception.message_dict)

    def test_full_clean_con_cedula_en_paciente_nuevo_no_lanza_error(self):
        paciente = Paciente(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Nuevo Con Cedula",
            cedula="999888777",
            telefono_whatsapp="+573001112228",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar

    def test_full_clean_paciente_existente_sin_cedula_no_lanza_error(self):
        """Pacientes migrados (ya tienen pk) no se les exige cédula retroactivamente."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Legado Existente",
            telefono_whatsapp="+573001112229",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar — ya tiene pk


class CronMatutinoCommandTests(TestCase):
    """Comando cron_matutino — corre las tareas de la mañana en orden."""

    def test_llama_las_cinco_tareas_en_orden(self):
        from unittest.mock import patch
        from django.core.management import call_command
        with patch(
            'signos_sintomas.management.commands.cron_matutino.call_command'
        ) as mock_call:
            call_command('cron_matutino', verbosity=0)
        llamadas = [c.args[0] for c in mock_call.call_args_list]
        self.assertEqual(llamadas, [
            'desactivar_pacientes_vencidos',
            'crear_checkins_diarios',
            'cerrar_checkins_vencidos',
            'enviar_recordatorios',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])

    def test_corre_sin_error_con_bd_vacia(self):
        from django.core.management import call_command
        # Con 0 pacientes las tareas deben correr sin lanzar excepción.
        call_command('cron_matutino', verbosity=0)


class CronOperativoCommandTests(TestCase):
    """Cron frecuente: vencimientos, motor recuperable y bandeja de correo."""

    def test_llama_las_tareas_en_orden(self):
        from unittest.mock import patch
        from django.core.management import call_command

        with patch(
            'signos_sintomas.management.commands.cron_operativo.call_command'
        ) as mock_call:
            call_command('cron_operativo', verbosity=0)

        self.assertEqual(
            [llamada.args[0] for llamada in mock_call.call_args_list],
            [
                'cerrar_checkins_vencidos',
                'reintentar_evaluaciones_alertas',
                'procesar_notificaciones_email',
            ],
        )

    def test_corre_sin_error_con_bd_vacia(self):
        from django.core.management import call_command

        call_command('cron_operativo', verbosity=0)


class CrearAdminCommandTests(TestCase):
    """Comando crear_admin — superusuario idempotente desde variables de entorno."""

    def test_no_op_sin_variables(self):
        import os
        from unittest.mock import patch
        from django.core.management import call_command
        with patch.dict(os.environ):
            os.environ.pop('DJANGO_SUPERUSER_USERNAME', None)
            os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
            call_command('crear_admin', verbosity=0)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_crea_superusuario_con_password_limpia(self):
        import os
        from unittest.mock import patch
        from django.core.management import call_command
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'jefe',
            'DJANGO_SUPERUSER_PASSWORD': 'clave-limpia-123',
            'DJANGO_SUPERUSER_EMAIL': 'jefe@x.com',
        }):
            call_command('crear_admin', verbosity=0)
        u = get_user_model().objects.get(username='jefe')
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)
        self.assertTrue(u.check_password('clave-limpia-123'))

    def test_actualiza_password_de_usuario_existente(self):
        import os
        from unittest.mock import patch
        from django.core.management import call_command
        User = get_user_model()
        User.objects.create_user(username='jefe', password='vieja')
        with patch.dict(os.environ, {
            'DJANGO_SUPERUSER_USERNAME': 'jefe',
            'DJANGO_SUPERUSER_PASSWORD': 'nueva-clave-456',
        }):
            call_command('crear_admin', verbosity=0)
        u = User.objects.get(username='jefe')
        self.assertTrue(u.check_password('nueva-clave-456'))
        self.assertTrue(u.is_superuser)


class CrearMedicoCommandTests(TestCase):
    """El rol médico se crea de forma reproducible y con privilegio mínimo."""

    PERMISOS_ESPERADOS = {
        'add_paciente', 'change_paciente', 'view_paciente',
        'view_registrodiario',
        'change_alerta', 'view_alerta',
        'view_checkinprogramado',
        'change_mensajecontacto', 'view_mensajecontacto',
    }

    def test_sin_credenciales_configura_solo_el_grupo(self):
        import os
        from unittest.mock import patch
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        with patch.dict(os.environ, {}, clear=True):
            call_command('crear_medico', verbosity=0)

        grupo = Group.objects.get(name='Médicos')
        self.assertSetEqual(
            set(grupo.permissions.values_list('codename', flat=True)),
            self.PERMISOS_ESPERADOS,
        )
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_crea_staff_no_superusuario_sin_permisos_extra(self):
        import os
        from unittest.mock import patch
        from django.core.management import call_command

        entorno = {
            'DJANGO_MEDICO_USERNAME': 'doctora',
            'DJANGO_MEDICO_PASSWORD': 'clave-medica-segura',
            'DJANGO_MEDICO_EMAIL': 'doctora@example.com',
        }
        with patch.dict(os.environ, entorno, clear=True):
            call_command('crear_medico', verbosity=0)

        user = get_user_model().objects.get(username='doctora')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('clave-medica-segura'))
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['Médicos'])
        self.assertEqual(user.user_permissions.count(), 0)
        self.assertTrue(user.has_perm('signos_sintomas.change_alerta'))
        self.assertFalse(user.has_perm('signos_sintomas.delete_alerta'))
        self.assertFalse(user.has_perm('signos_sintomas.change_registrodiario'))

    def test_rechaza_convertir_un_superusuario_existente(self):
        import os
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError

        user = get_user_model().objects.create_superuser(
            username='jefe', password='clave-original',
        )
        entorno = {
            'DJANGO_MEDICO_USERNAME': 'jefe',
            'DJANGO_MEDICO_PASSWORD': 'otra-clave',
        }
        with patch.dict(os.environ, entorno, clear=True):
            with self.assertRaises(CommandError):
                call_command('crear_medico', verbosity=0)

        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('clave-original'))


class SeedDemoTests(TestCase):
    """A-3 — guard de entorno y usuario demo sin superuser."""

    def test_seed_demo_con_debug_false_no_crea_nada(self):
        from django.core.management import call_command
        with override_settings(DEBUG=False):
            call_command('seed_demo', verbosity=0)
        self.assertFalse(Paciente.objects.filter(telefono_whatsapp='+573001234567').exists())
        self.assertFalse(get_user_model().objects.filter(username='demo_medico').exists())

    def test_seed_demo_con_debug_true_crea_usuario_staff_no_superuser(self):
        from django.core.management import call_command
        with override_settings(DEBUG=True):
            call_command('seed_demo', verbosity=0)
        medico = get_user_model().objects.get(username='demo_medico')
        self.assertTrue(medico.is_staff)
        self.assertFalse(medico.is_superuser)
        self.assertTrue(medico.groups.filter(name='Médicos').exists())
        self.assertTrue(medico.has_perm('signos_sintomas.view_registrodiario'))
        self.assertFalse(medico.has_perm('signos_sintomas.change_registrodiario'))
        paciente = Paciente.objects.get(telefono_whatsapp='+573001234567')
        self.assertEqual(paciente.cedula, 'DEMO-LOCAL-001')
        self.assertFalse(
            NotificacionAlerta.objects.filter(alerta__paciente=paciente).exists()
        )
        self.assertTrue(paciente.consentimiento_informado)
        self.assertIsNotNone(paciente.fecha_consentimiento)
        self.assertEqual(
            list(RegistroDiario.objects.order_by('fecha_registro').values_list(
                'dia_postoperatorio', flat=True,
            )),
            list(range(1, 11)),
        )

    def test_seed_demo_borrar_recrea_relaciones_protegidas(self):
        from django.core.management import call_command

        with override_settings(DEBUG=True):
            call_command('seed_demo', verbosity=0)
            paciente_anterior = Paciente.objects.get(
                telefono_whatsapp='+573001234567'
            )
            self.assertGreater(
                DeteccionAlerta.objects.filter(
                    alerta__paciente=paciente_anterior,
                ).count(),
                0,
            )

            call_command('seed_demo', '--borrar', verbosity=0)

        paciente_nuevo = Paciente.objects.get(
            telefono_whatsapp='+573001234567'
        )
        self.assertNotEqual(paciente_nuevo.pk, paciente_anterior.pk)
        self.assertEqual(paciente_nuevo.registros.count(), 10)
        self.assertGreater(
            DeteccionAlerta.objects.filter(
                alerta__paciente=paciente_nuevo,
            ).count(),
            0,
        )

    def test_seed_demo_limpiar_borra_sin_recrear(self):
        from django.core.management import call_command

        with override_settings(DEBUG=True):
            call_command('seed_demo', verbosity=0)
            call_command('seed_demo', '--limpiar', verbosity=0)

        self.assertFalse(
            Paciente.objects.filter(telefono_whatsapp='+573001234567').exists()
        )
        self.assertTrue(
            get_user_model().objects.filter(username='demo_medico').exists()
        )

    def test_seed_produccion_limpia_solo_sus_demos_con_detecciones(self):
        from django.core.management import call_command

        medico = get_user_model().objects.create_user(
            username='medico_seed_prod',
            password='pass',
            is_staff=True,
        )
        call_command(
            'seed_demo_produccion',
            '--confirmar',
            '--medico',
            medico.username,
            verbosity=0,
        )
        demos = Paciente.objects.filter(cedula__in=['DEMO-0001', 'DEMO-0002'])
        self.assertEqual(demos.count(), 2)
        self.assertGreater(
            DeteccionAlerta.objects.filter(alerta__paciente__in=demos).count(),
            0,
        )
        self.assertEqual(
            NotificacionAlerta.objects.filter(alerta__paciente__in=demos).count(),
            0,
        )

        call_command(
            'seed_demo_produccion',
            '--limpiar',
            '--confirmar',
            verbosity=0,
        )

        self.assertFalse(demos.exists())


@freeze_time(ANCLA_MEDIANOCHE)
class DesactivarPacientesVencidosTests(TestCase):
    """Sprint 5, Bloque 1B — desactivación automática a 10 días postop (P-5)."""

    def _paciente(self, dias_cirugia, tel, activo=True):
        """Por defecto simula que el paciente se registró el día de su cirugía
        (fecha_registro = fecha_cirugia), para no disparar el guard de
        ingreso tardío (A-1, DIAS_GRACIA_INGRESO) en tests que no lo prueban."""
        paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Vencimiento",
            telefono_whatsapp=tel,
            fecha_cirugia=timezone.localdate() - timedelta(days=dias_cirugia),
            activo=activo,
        )
        Paciente.objects.filter(pk=paciente.pk).update(
            fecha_registro=timezone.now() - timedelta(days=dias_cirugia)
        )
        paciente.refresh_from_db()
        return paciente

    def test_paciente_con_10_dias_se_desactiva(self):
        from django.core.management import call_command
        paciente = self._paciente(dias_cirugia=10, tel="+573002220001")
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertFalse(paciente.activo)

    def test_paciente_con_9_dias_no_se_desactiva(self):
        from django.core.management import call_command
        paciente = self._paciente(dias_cirugia=9, tel="+573002220002")
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertTrue(paciente.activo)

    def test_paciente_ya_inactivo_no_se_toca(self):
        """Desactivado manualmente por el médico antes de los 10 días: no lo reprocesa."""
        from django.core.management import call_command
        paciente = self._paciente(dias_cirugia=3, tel="+573002220003", activo=False)
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertFalse(paciente.activo)

    def test_dry_run_no_modifica_bd(self):
        from django.core.management import call_command
        paciente = self._paciente(dias_cirugia=10, tel="+573002220004")
        call_command('desactivar_pacientes_vencidos', '--dry-run', verbosity=0)
        paciente.refresh_from_db()
        self.assertTrue(paciente.activo)

    def test_segunda_ejecucion_mismo_dia_es_idempotente(self):
        from django.core.management import call_command
        paciente = self._paciente(dias_cirugia=12, tel="+573002220005")
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertFalse(paciente.activo)

    def test_scheduler_no_crea_checkins_tras_desactivacion(self):
        """crear_checkins_diarios, corrido después, ignora al paciente recién desactivado."""
        from django.core.management import call_command
        self._paciente(dias_cirugia=10, tel="+573002220006")
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        call_command('crear_checkins_diarios', verbosity=0)
        self.assertEqual(CheckInProgramado.objects.count(), 0)

    # -----------------------------------------------------------------
    # A-1: guard de ingreso tardío (DIAS_GRACIA_INGRESO)
    # -----------------------------------------------------------------

    def _paciente_con_fecha_registro(self, dias_cirugia, dias_en_sistema, tel):
        paciente = self._paciente(dias_cirugia=dias_cirugia, tel=tel)
        fecha_registro = timezone.now() - timedelta(days=dias_en_sistema)
        Paciente.objects.filter(pk=paciente.pk).update(fecha_registro=fecha_registro)
        paciente.refresh_from_db()
        return paciente

    def test_pod12_registrado_hoy_no_se_desactiva(self):
        from django.core.management import call_command
        paciente = self._paciente_con_fecha_registro(
            dias_cirugia=12, dias_en_sistema=0, tel="+573002220007"
        )
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertTrue(paciente.activo)

    def test_pod12_registrado_hace_3_dias_se_desactiva(self):
        from django.core.management import call_command
        paciente = self._paciente_con_fecha_registro(
            dias_cirugia=12, dias_en_sistema=3, tel="+573002220008"
        )
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertFalse(paciente.activo)

    def test_pod8_no_se_desactiva_sin_importar_dias_en_sistema(self):
        from django.core.management import call_command
        paciente = self._paciente_con_fecha_registro(
            dias_cirugia=8, dias_en_sistema=5, tel="+573002220009"
        )
        call_command('desactivar_pacientes_vencidos', verbosity=0)
        paciente.refresh_from_db()
        self.assertTrue(paciente.activo)


class PacienteAdminIngresoTardioAdvertenciaTests(TestCase):
    """A-1 — advertencia en el Admin al crear un paciente con POD ya avanzado."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_a1', password='pass')
        self.client.force_login(self.medico)

    def _post_nuevo_paciente(self, dias_cirugia, tel, cedula):
        return self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Ingreso Tardío',
                'cedula': cedula,
                'telefono_whatsapp': tel,
                'fecha_cirugia': (timezone.localdate() - timedelta(days=dias_cirugia)).isoformat(),
            },
            follow=True,
        )

    def test_advierte_si_pod_es_mayor_o_igual_a_8(self):
        resp = self._post_nuevo_paciente(dias_cirugia=9, tel="+573002230001", cedula="900000001")
        self.assertContains(resp, "días postoperatorios")

    def test_no_advierte_si_pod_es_menor_a_8(self):
        resp = self._post_nuevo_paciente(dias_cirugia=3, tel="+573002230002", cedula="900000002")
        self.assertNotContains(resp, "días postoperatorios")


class PacienteAdminFiltrosHistorialTests(TestCase):
    """Sprint 5, Bloque 3 — filtro de alertas activas e historial configurable (P-8)."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_bloque3', password='pass')
        self.paciente_con_alerta = Paciente.objects.create(
            nombre_completo="Paciente Con Alerta Activa",
            telefono_whatsapp="+573020000001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        self.paciente_sin_alerta = Paciente.objects.create(
            nombre_completo="Paciente Sin Alerta Activa",
            telefono_whatsapp="+573020000002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        registro = RegistroDiario.objects.create(
            paciente=self.paciente_con_alerta,
            temperatura=Decimal('38.0'),
            dolor_eva=3,
            aspecto_drenaje='sin_drenaje',
            presencia_gases=True,
            episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente_con_alerta,
            registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre',
            resuelta=False,
        )
        self.client.force_login(self.medico)

    # -------------------------------------------------------------------
    # TieneAlertaActivaFilter
    # -------------------------------------------------------------------

    def test_filtro_alerta_activa_si_muestra_solo_pacientes_con_alerta_sin_resolver(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/?alerta_activa=si')
        self.assertContains(resp, "Paciente Con Alerta Activa")
        self.assertNotContains(resp, "Paciente Sin Alerta Activa")

    def test_filtro_alerta_activa_no_excluye_pacientes_con_alerta_pendiente(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/?alerta_activa=no')
        self.assertContains(resp, "Paciente Sin Alerta Activa")
        self.assertNotContains(resp, "Paciente Con Alerta Activa")

    def test_sin_filtro_muestra_ambos_pacientes(self):
        resp = self.client.get('/admin/signos_sintomas/paciente/')
        self.assertContains(resp, "Paciente Con Alerta Activa")
        self.assertContains(resp, "Paciente Sin Alerta Activa")

    # -------------------------------------------------------------------
    # Historial configurable por días
    # -------------------------------------------------------------------

    def _url_change(self, paciente):
        return f'/admin/signos_sintomas/paciente/{paciente.pk}/change/'

    def test_historial_default_es_7_dias(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta))
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_respeta_parametro_dias_de_la_url(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=10')
        self.assertContains(resp, '<strong>10 días</strong>', html=False)

    def test_historial_valor_invalido_usa_default(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=abc')
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_rechaza_periodo_fuera_de_las_opciones(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=30')
        self.assertContains(resp, '<strong>7 días</strong>', html=False)

    def test_historial_de_3_dias_no_incluye_un_cuarto_dia(self):
        for desplazamiento in (1, 2, 3):
            registro = RegistroDiario.objects.create(
                paciente=self.paciente_con_alerta,
                temperatura=Decimal('37.0'),
                dolor_eva=2,
                aspecto_drenaje='sin_drenaje',
                presencia_gases=True,
                episodios_nauseas=0,
            )
            fecha = timezone.datetime.combine(
                timezone.localdate() - timedelta(days=desplazamiento),
                timezone.datetime.min.time(),
                tzinfo=timezone.get_current_timezone(),
            ) + timedelta(hours=8)
            RegistroDiario.objects.filter(pk=registro.pk).update(fecha_registro=fecha)

        from .admin import _historial_paciente

        contenido = _historial_paciente(self.paciente_con_alerta, dias=3)
        fecha_incluida = (timezone.localdate() - timedelta(days=2)).strftime('%d/%m')
        fecha_excluida = (timezone.localdate() - timedelta(days=3)).strftime('%d/%m')
        self.assertIn(fecha_incluida, contenido)
        self.assertNotIn(fecha_excluida, contenido)


class PanelTriageExperienciaTests(TestCase):
    """Loop 3: pendientes acumulados, prioridad y scoping en el tablero."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command('crear_medico', verbosity=0)
        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dr_panel', password='pass', is_staff=True,
        )
        self.otro_medico = User.objects.create_user(
            username='dr_panel_otro', password='pass', is_staff=True,
        )
        grupo = Group.objects.get(name='Médicos')
        self.medico.groups.add(grupo)
        self.otro_medico.groups.add(grupo)
        self.client.force_login(self.medico)

    def _paciente(self, nombre, telefono, cedula, medico=None):
        return Paciente.objects.create(
            nombre_completo=nombre,
            cedula=cedula,
            telefono_whatsapp=telefono,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable=medico or self.medico,
        )

    def _alerta(self, paciente, veces, fecha, severidad='ALTA'):
        return Alerta.objects.create(
            paciente=paciente,
            tipo='SEPSIS',
            severidad=severidad,
            mensaje='Alerta de prueba',
            veces=veces,
            fecha_ultima_deteccion=fecha,
        )

    def test_muestra_alerta_antigua_mientras_siga_sin_resolver(self):
        propio = self._paciente(
            'Paciente pendiente anterior', '+573040000001', 'PANEL-001',
        )
        ajeno = self._paciente(
            'Paciente ajeno invisible', '+573040000002', 'PANEL-002',
            medico=self.otro_medico,
        )
        self._alerta(propio, 1, timezone.now() - timedelta(days=3))
        self._alerta(ajeno, 1, timezone.now())

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Seguimiento que requiere atención')
        self.assertContains(resp, 'Paciente pendiente anterior')
        self.assertNotContains(resp, 'Paciente ajeno invisible')
        self.assertContains(resp, '1 pendiente')

    def test_prioriza_recurrencia_dentro_de_la_misma_severidad(self):
        menos = self._paciente(
            'Paciente recurrencia menor', '+573040000003', 'PANEL-003',
        )
        mas = self._paciente(
            'Paciente recurrencia mayor', '+573040000004', 'PANEL-004',
        )
        self._alerta(menos, 2, timezone.now())
        self._alerta(mas, 5, timezone.now() - timedelta(days=1))

        contenido = self.client.get('/admin/').content.decode()

        self.assertLess(
            contenido.index('Paciente recurrencia mayor'),
            contenido.index('Paciente recurrencia menor'),
        )

    def test_panel_muestra_solo_mensajes_de_contacto_asignados_al_medico(self):
        from home.models import MensajeContacto

        MensajeContacto.objects.create(
            nombre='Contacto propio visible',
            telefono='+573040000010',
            mensaje='Contenido sensible que no va en el tablero',
            medico_destinatario=self.medico,
        )
        MensajeContacto.objects.create(
            nombre='Contacto ajeno invisible',
            telefono='+573040000011',
            mensaje='Otro contenido',
            medico_destinatario=self.otro_medico,
        )
        MensajeContacto.objects.create(
            nombre='Contacto sin asignar invisible',
            telefono='+573040000012',
            mensaje='Pendiente del superusuario',
        )

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Mensajes de contacto')
        self.assertContains(resp, 'Contacto propio visible')
        self.assertNotContains(resp, 'Contacto ajeno invisible')
        self.assertNotContains(resp, 'Contacto sin asignar invisible')
        self.assertNotContains(resp, 'Contenido sensible que no va en el tablero')

    def test_avisa_de_correos_de_alerta_sin_entregar_propios(self):
        """D6: un correo de alerta ALTA que agotó los reintentos (FALLIDA) es
        información clínica que no llegó. El tablero debe avisarlo —también al
        médico— en vez de que el fallo quede enterrado en la bandeja.
        """
        propio = self._paciente(
            'Paciente correo fallido', '+573040000030', 'PANEL-030',
        )
        alerta = self._alerta(propio, 1, timezone.now())
        NotificacionAlerta.objects.update_or_create(
            alerta=alerta,
            defaults={
                'estado': NotificacionAlerta.ESTADO_FALLIDA,
                'intentos': 10,
            },
        )

        resp = self.client.get('/admin/')

        self.assertContains(resp, 'Correos de alerta sin entregar')

    def test_no_avisa_de_correos_fallidos_de_pacientes_ajenos(self):
        """El aviso de FALLIDA respeta el scoping por médico: un correo fallido
        de un paciente de otro médico no aparece en este tablero.
        """
        ajeno = self._paciente(
            'Paciente ajeno correo', '+573040000031', 'PANEL-031',
            medico=self.otro_medico,
        )
        alerta = self._alerta(ajeno, 1, timezone.now())
        NotificacionAlerta.objects.update_or_create(
            alerta=alerta,
            defaults={
                'estado': NotificacionAlerta.ESTADO_FALLIDA,
                'intentos': 10,
            },
        )

        resp = self.client.get('/admin/')

        self.assertNotContains(resp, 'Correos de alerta sin entregar')


class PacienteAdminHistorialCambiosTests(TestCase):
    """Loop 3: el historial distingue activación y desactivación."""

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(
            username='dr_historial_estado', password='pass',
        )
        self.paciente = Paciente.objects.create(
            nombre_completo='Paciente Historial Estado',
            cedula='HIST-ESTADO-001',
            telefono_whatsapp='+573040000005',
            fecha_cirugia=timezone.localdate(),
            tipo_cirugia='otra',
            medico_responsable=self.medico,
            activo=True,
        )
        self.client.force_login(self.medico)

    def _guardar(self, activo):
        datos = {
            'nombre_completo': self.paciente.nombre_completo,
            'cedula': self.paciente.cedula,
            'telefono_whatsapp': self.paciente.telefono_whatsapp,
            'fecha_cirugia': self.paciente.fecha_cirugia.isoformat(),
            'tipo_cirugia': self.paciente.tipo_cirugia,
            'medico_responsable': str(self.medico.pk),
            '_save': 'Grabar',
        }
        if activo:
            datos['activo'] = 'on'
        return self.client.post(
            f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/',
            datos,
        )

    def _ultimo_mensaje(self):
        from django.contrib.admin.models import LogEntry
        return LogEntry.objects.filter(
            object_id=str(self.paciente.pk),
        ).latest('action_time').get_change_message()

    def test_historial_indica_seguimiento_desactivado(self):
        self.assertEqual(self._guardar(activo=False).status_code, 302)
        self.assertEqual(self._ultimo_mensaje(), 'Seguimiento desactivado.')

    def test_historial_indica_seguimiento_activado(self):
        Paciente.objects.filter(pk=self.paciente.pk).update(activo=False)
        self.paciente.refresh_from_db()
        self.assertEqual(self._guardar(activo=True).status_code, 302)
        self.assertEqual(self._ultimo_mensaje(), 'Seguimiento activado.')


class GraficaSignosVitalesTests(TestCase):
    """
    Sprint 5, Bloque 4 (rediseño 01/07/2026) — gráficas Chart.js con
    selector de período 3/7/10 días independiente del historial en
    tabla, turno M/T por CheckInProgramado real, y puntos de alerta.
    """

    def setUp(self):
        User = get_user_model()
        self.medico = User.objects.create_superuser(username='dr_bloque4', password='pass')
        self.paciente = Paciente.objects.create(
            nombre_completo="Paciente Grafica",
            telefono_whatsapp="+573030000001",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            medico_responsable=self.medico,
        )
        self.client.force_login(self.medico)

    def _url_change(self):
        return f'/admin/signos_sintomas/paciente/{self.paciente.pk}/change/'

    def _extraer_datos(self, contenido):
        import html
        import json
        import re
        match = re.search(r'data-graficas="([^"]+)"', contenido)
        self.assertIsNotNone(match, "No se encontró el JSON de las gráficas")
        return json.loads(html.unescape(match.group(1)))

    def test_sin_registros_no_carga_chartjs_desde_cdn(self):
        resp = self.client.get(self._url_change())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sin datos para graficar")
        self.assertNotContains(resp, "cdn.jsdelivr.net/npm/chart.js")

    def test_fc_nula_se_serializa_como_null_no_como_cero(self):
        """Bug reportado en la revisión visual: FC no capturada debía viajar
        como null (hueco en la línea), nunca como 0 (caída falsa a tierra)."""
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.2'), dolor_eva=6,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=1,
            frecuencia_cardiaca=None,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['fcs'], [None])
        self.assertNotIn(0, datos['7']['fcs'])

    def test_los_3_periodos_estan_precalculados_en_una_sola_carga(self):
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(set(datos.keys()), {'3', '7', '10'})
        for periodo in ('3', '7', '10'):
            self.assertEqual(datos[periodo]['temps'], [37.0])

    def test_turno_usa_etiqueta_del_checkin_no_la_hora_de_respuesta(self):
        """Decisión D2 (Sprint 3.6): el turno lo fija el evento programado,
        nunca la hora en que el paciente respondió."""
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        # Paciente respondió a las 3pm (T) al check-in que el sistema programó
        # como MAÑANA — el turno mostrado debe ser M, no T.
        RegistroDiario.objects.filter(pk=registro.pk).update(
            fecha_registro=timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)
        )
        CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
            estado=CheckInProgramado.ESTADO_COMPLETADO,
            registro=registro,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertTrue(datos['7']['labels'][0].endswith(' M'))

    def test_registro_legado_sin_checkin_usa_hora_local_como_respaldo(self):
        """Sin CheckInProgramado vinculado (dato legado), se usa la hora en
        zona horaria de Bogotá, no UTC — de lo contrario el respaldo
        clasifica mal registros creados en la mañana bogotana."""
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        # 8am Bogotá (UTC-5) = 13:00 UTC — con .hour crudo (UTC) esto daría
        # "T" incorrectamente; con timezone.localtime() da "M" correcto.
        ocho_am_bogota_en_utc = timezone.now().replace(hour=13, minute=0, second=0, microsecond=0)
        RegistroDiario.objects.filter(pk=registro.pk).update(fecha_registro=ocho_am_bogota_en_utc)
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertTrue(datos['7']['labels'][0].endswith(' M'))

    def test_alerta_alta_sin_resolver_marca_el_indice(self):
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.5'), dolor_eva=8,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente, registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre alta', resuelta=False,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['alertas_idx'], [0])

    def test_alerta_alta_resuelta_no_marca_el_indice(self):
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('38.5'), dolor_eva=8,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        Alerta.objects.create(
            paciente=self.paciente, registro_origen=registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='Fiebre alta', resuelta=True,
            fecha_resolucion=timezone.now(),
            motivo_resolucion=Alerta.MOTIVO_CONTACTO,
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['alertas_idx'], [])

    def test_carga_chartjs_y_logica_desde_estaticos_locales(self):
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change())
        self.assertContains(resp, 'admin/js/vendor/chart.umd.min.js')
        self.assertContains(resp, 'admin/js/graficas_signos_vitales.js')
        self.assertNotContains(resp, 'cdn.jsdelivr.net')
        self.assertNotContains(resp, 'onclick=')

    def test_distribucion_y_licencia_chartjs_existen_en_staticfiles(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find('admin/js/vendor/chart.umd.min.js'))
        self.assertIsNotNone(finders.find('admin/js/vendor/Chart.js-LICENSE.md'))

    def test_selector_de_grafica_es_independiente_del_historial(self):
        """El ?dias= de la URL controla el historial en tabla (Bloque 3B);
        la gráfica siempre trae los 3 períodos precalculados, sin depender
        de ese parámetro."""
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change() + '?dias=10')
        self.assertContains(resp, '<strong>10 días</strong>', html=False)
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(set(datos.keys()), {'3', '7', '10'})


class HinchazonCondicionMediaTests(TestCase):
    """D10 — fija el comportamiento ACTUAL de la condición MEDIA de la Regla 7.

    Estas pruebas nacen en verde a propósito: no denuncian un defecto, retratan
    lo que el código hace hoy para que la expresión pueda reescribirse de forma
    legible sin cambiar cuándo dispara la alerta. Mover ese umbral es una
    decisión clínica del médico, no una limpieza de código (D10).

    La condición encadena tres comparaciones y dos se vuelven trivialmente
    verdaderas cuando falta el dato de ayer (`nivel_ayer is None or ...` y
    `nivel_hoy >= nivel_hoy`), así que la verificación de "sostenido"
    desaparece justo cuando no hay con qué verificarla. Cada caso de abajo aísla
    una de las comparaciones.

    Los fixtures se anclan a un único `now()` y la evaluación recibe la fecha de
    referencia explícita: así el resultado no cambia si la corrida cruza la
    medianoche de Bogotá.
    """

    def setUp(self):
        self.ahora = timezone.now()
        self.hoy = timezone.localdate(self.ahora)
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Hinchazon D10",
            telefono_whatsapp="+573008881010",
            fecha_cirugia=self.hoy,
        )

    def _reportar(self, nivel, dias_atras=0):
        """Reporte con valores neutros salvo la hinchazón: aísla la Regla 7."""
        registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal("37.0"),
            dolor_eva=2,
            tiene_drenaje=False,
            presencia_gases=True,
            episodios_nauseas=0,
            hinchazon_abdominal=nivel,
        )
        RegistroDiario.objects.filter(pk=registro.pk).update(
            fecha_registro=self.ahora - timedelta(days=dias_atras)
        )
        registro.refresh_from_db()
        return registro

    def _severidad_ileo(self, registro):
        alertas = evaluar_registro(registro, fecha_referencia=self.hoy)
        ileo = [a for a in alertas if a.tipo == 'ILEO_PARALITICO']
        return ileo[0].severidad if ileo else None

    def test_sin_dato_de_ayer_el_empeoramiento_contra_antier_dispara_media(self):
        """El hueco de ayer deja la condición reducida a hoy > antier.

        Es el caso que la expresión actual esconde: sin dato de ayer no puede
        comprobarse que el empeoramiento se haya sostenido, y aun así alerta.
        Queda fijado tal cual — cambiarlo es decisión del médico.
        """
        self._reportar("nada", dias_atras=2)
        hoy = self._reportar("algo")

        self.assertEqual(self._severidad_ileo(hoy), 'MEDIA')

    def test_sin_dato_de_ayer_y_sin_empeoramiento_no_dispara(self):
        """Aun sin ayer, sigue exigiéndose que hoy supere a antier."""
        self._reportar("algo", dias_atras=2)
        hoy = self._reportar("algo")

        self.assertIsNone(self._severidad_ileo(hoy))

    def test_una_bajada_en_el_medio_rompe_el_sostenido_y_deja_baja(self):
        """Con dato de ayer, `ayer >= antier` sí cumple su función.

        algo -> nada -> mucho empeora contra antier, pero bajó en el camino:
        no es un empeoramiento sostenido. Queda la BAJA por el salto de ayer a
        hoy, que es una condición distinta.
        """
        self._reportar("algo", dias_atras=2)
        self._reportar("nada", dias_atras=1)
        hoy = self._reportar("mucho")

        self.assertEqual(self._severidad_ileo(hoy), 'BAJA')

    def test_mejora_respecto_de_ayer_no_dispara_media(self):
        """Con dato de ayer, `hoy >= ayer` sí cumple su función.

        nada -> mucho -> algo supera a antier y nunca bajó de él, pero hoy
        mejoró respecto de ayer: la tendencia no está sostenida.
        """
        self._reportar("nada", dias_atras=2)
        self._reportar("mucho", dias_atras=1)
        hoy = self._reportar("algo")

        self.assertIsNone(self._severidad_ileo(hoy))

    def test_secuencia_no_decreciente_con_aumento_neto_dispara_media(self):
        """Frontera `ayer == antier`: la secuencia plana-y-luego-sube alerta."""
        self._reportar("nada", dias_atras=2)
        self._reportar("nada", dias_atras=1)
        hoy = self._reportar("algo")

        self.assertEqual(self._severidad_ileo(hoy), 'MEDIA')


class BotEstadoEvaluacionMotorTests(TestCase):
    """Hallazgo 7 — un fallo del motor en la ruta del bot debe quedar registrado.

    `evaluar_registro_con_estado` guarda con cuidado el estado ERROR, el nombre
    de la excepción y el intento consumido, y RECIÉN DESPUÉS relanza. Pero en
    `bot._crear_registro` esa llamada vive dentro de un savepoint defensivo: la
    excepción sale de ese `atomic`, el savepoint se revierte y se lleva consigo
    las tres cosas. El registro queda como si el motor nunca se hubiera
    ejecutado.

    Lo que se pierde no es el reporte del paciente (ese está a salvo, y esa
    parte se verifica aquí también) sino el rastro del fallo: en el Admin el
    registro se ve PENDIENTE, igual que uno que todavía no ha pasado por el
    motor, y `ultimo_error_evaluacion_alertas` queda vacío.
    """

    TELEFONO = "+573001119977"
    TELEFONO_TWILIO = "whatsapp:+573001119977"

    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo="Paciente Estado Motor",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            consentimiento_informado=True,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )

    def _completar_flujo(self):
        """Recorre las 10 preguntas sin drenaje. Devuelve la respuesta final."""
        env = lambda t: bot.procesar_mensaje(self.TELEFONO_TWILIO, t)
        env("hola")     # -> temperatura
        env("37.0")     # -> dolor
        env("3")        # -> tiene_drenaje
        env("no")       # -> gases/náuseas (omite aspecto y cantidad)
        env("sí, 0")    # -> hinchazón
        env("nada")     # -> frecuencia cardíaca
        env("78")       # -> frecuencia respiratoria
        env("16")       # -> tolerancia líquidos
        return env("sí")

    def test_fallo_del_motor_deja_el_registro_marcado_como_error(self):
        from unittest.mock import patch

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=RuntimeError('temperatura 39.1 del paciente'),
        ):
            respuesta = self._completar_flujo()

        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_ERROR,
        )
        self.assertEqual(registro.intentos_evaluacion_alertas, 1)
        self.assertEqual(registro.ultimo_error_evaluacion_alertas, 'RuntimeError')
        self.assertNotIn('39.1', registro.ultimo_error_evaluacion_alertas)
        self.assertIsNotNone(registro.fecha_ultima_evaluacion_alertas)

        # El reporte del paciente nunca se pierde por un fallo del motor.
        self.checkin.refresh_from_db()
        self.assertEqual(self.checkin.estado, CheckInProgramado.ESTADO_COMPLETADO)
        self.assertEqual(self.checkin.registro_id, registro.pk)
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)

    def test_registro_fallido_en_el_bot_se_recupera_con_el_command(self):
        """El motor no evaluó nada, así que el registro debe volver a la cola.

        Nace en verde: hoy el registro queda PENDIENTE, que el command también
        recoge. Está aquí para que la corrección del estado ERROR no rompa la
        recuperación — es la mitad del hallazgo que NO debe cambiar.
        """
        from unittest.mock import patch

        from django.core.management import call_command

        with patch(
            'signos_sintomas.evaluacion_alertas.evaluar_registro',
            side_effect=RuntimeError('fallo transitorio del motor'),
        ):
            self._completar_flujo()

        call_command('reintentar_evaluaciones_alertas', verbosity=0)

        registro = RegistroDiario.objects.get(paciente=self.paciente)
        self.assertEqual(
            registro.estado_evaluacion_alertas,
            RegistroDiario.EVALUACION_COMPLETADA,
        )
        self.assertEqual(registro.ultimo_error_evaluacion_alertas, '')


class AdminFiltrosNoExponenOtrasCuentasTests(TestCase):
    """Hallazgo 8 — el filtro lateral no debe revelar las demás cuentas médicas.

    El aislamiento por médico resistió las 15 comprobaciones de la auditoría:
    ningún dato de paciente se filtra. La fuga es de otra naturaleza y menor —
    `PacienteAdmin.list_filter` incluye `medico_responsable`, y ese filtro se
    construye con TODOS los usuarios de la base, no con los que el médico puede
    ver. Un médico lee ahí los nombres de usuario de sus colegas y del
    superusuario.
    """

    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico_a = User.objects.create_user(
            username='dr_filtro_a', password='pass', is_staff=True
        )
        self.medico_b = User.objects.create_user(
            username='dr_filtro_b', password='pass', is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            username='super_filtro', password='pass'
        )
        ct = ContentType.objects.get_for_model(Paciente)
        for medico in (self.medico_a, self.medico_b):
            medico.user_permissions.add(*Permission.objects.filter(content_type=ct))

        for indice, medico in enumerate((self.medico_a, self.medico_b), start=1):
            Paciente.objects.create(
                nombre_completo="Paciente del filtro {}".format(indice),
                telefono_whatsapp="+57301999000{}".format(indice),
                cedula="FILTRO-000{}".format(indice),
                fecha_cirugia=timezone.localdate(),
                medico_responsable=medico,
            )

    def _url_listado(self):
        return reverse('admin:signos_sintomas_paciente_changelist')

    def test_medico_no_ve_en_el_filtro_las_cuentas_de_los_demas(self):
        self.client.force_login(self.medico_a)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        # El marcador ancla el fallo al filtro lateral y no a otra parte de la
        # página: es el querystring que arma RelatedFieldListFilter.
        self.assertNotIn('medico_responsable__id__exact', contenido)
        self.assertNotIn('dr_filtro_b', contenido)
        self.assertNotIn('super_filtro', contenido)

    def test_superusuario_conserva_el_filtro_por_medico(self):
        """El filtro es útil para el superusuario: la corrección no debe borrarlo."""
        self.client.force_login(self.superuser)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        self.assertIn('medico_responsable__id__exact', contenido)
        self.assertIn('dr_filtro_a', contenido)
        self.assertIn('dr_filtro_b', contenido)

    def test_medico_sigue_viendo_solo_sus_pacientes(self):
        """Nace en verde: es el aislamiento que ya funciona y no debe romperse."""
        self.client.force_login(self.medico_a)

        resp = self.client.get(self._url_listado())

        contenido = resp.content.decode()
        self.assertIn('Paciente del filtro 1', contenido)
        self.assertNotIn('Paciente del filtro 2', contenido)


# ===========================================================================
# Loop D — D-1: pruebas en rojo de la auditoría de cierre (27/07/2026)
# Fichas D11, D12 y D13 en docs/decisiones_correccion_auditoria.md
# ===========================================================================


class SalidaOperativaSinIdentidadTests(TestCase):
    """D11 — la salida nominal de un comando no lleva identidad del paciente.

    Invariante: ninguna salida que el sistema escribe deliberadamente —stdout,
    stderr o logs— contiene el nombre ni el teléfono de un paciente. Railway
    conserva esa salida, y quien tiene derecho a saber a quién le pasó algo
    entra al panel autenticado.

    POR QUÉ ESTE GUARDIÁN FUERZA EL NIVEL INFO. En producción el logger
    `signos_sintomas` está en WARNING, así que la línea de `enviar_recordatorios`
    con nombre y teléfono hoy no se emite. Un guardián que corriera con la
    configuración normal **pasaría en verde con el defecto puesto**: sería una
    prueba verde que no prueba nada, el mismo fallo que dejó viva la escalera de
    SILENCIO durante seis loops. Lo que hay que atrapar no es "se emite PHI",
    es "se escribió código que emitiría PHI si alguien baja un nivel de log".
    """

    NOMBRE = 'Nombre Inconfundible De Prueba'
    TELEFONO = '+573009998877'

    def setUp(self):
        self.paciente = Paciente.objects.create(medico_responsable=medico_de_pruebas(), 
            nombre_completo=self.NOMBRE,
            telefono_whatsapp=self.TELEFONO,
            cedula='PHI-0001',
            fecha_cirugia=timezone.localdate() - timedelta(days=12),
        )
        # fecha_registro es auto_now_add: se retrasa con UPDATE para superar el
        # guard DIAS_GRACIA_INGRESO de desactivar_pacientes_vencidos.
        Paciente.objects.filter(pk=self.paciente.pk).update(
            fecha_registro=timezone.now() - timedelta(days=5)
        )

    def _todo_lo_que_escribe(self, comando):
        """stdout + stderr + logs del comando, con el logger forzado a INFO."""
        from io import StringIO

        from django.core.management import call_command

        salida, errores = StringIO(), StringIO()
        with self.assertLogs('signos_sintomas', level='INFO') as capturado:
            call_command(comando, stdout=salida, stderr=errores)
        return '\n'.join(
            [salida.getvalue(), errores.getvalue(), *capturado.output]
        )

    def test_desactivar_pacientes_vencidos_no_nombra_al_paciente(self):
        escrito = self._todo_lo_que_escribe('desactivar_pacientes_vencidos')

        self.assertNotIn(self.NOMBRE, escrito)

    def test_desactivar_pacientes_vencidos_identifica_al_paciente_por_pk(self):
        """Retirar el nombre no puede dejar la salida inservible para operar."""
        escrito = self._todo_lo_que_escribe('desactivar_pacientes_vencidos')

        self.assertIn('pk={}'.format(self.paciente.pk), escrito)

    def test_enviar_recordatorios_no_expone_nombre_ni_telefono(self):
        CheckInProgramado.objects.create(
            paciente=self.paciente,
            fecha_dia=timezone.localdate(),
            orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timedelta(hours=1),
        )

        escrito = self._todo_lo_que_escribe('enviar_recordatorios')

        self.assertNotIn(self.NOMBRE, escrito)
        self.assertNotIn(self.TELEFONO, escrito)


class PacienteActivoExigeMedicoTests(TestCase):
    """D12 — todo paciente ACTIVO tiene un médico que puede atenderlo.

    Un paciente activo sin médico responsable no es un pendiente visible: es un
    paciente invisible. Desaparece del listado del médico, desaparece de los KPI
    del tablero (el médico ve ceros, no un hueco) y su alerta ALTA queda con
    destinatario vacío. Cuatro capas, cada una tapa lo que las otras no ven.
    """

    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        User = get_user_model()
        self.medico = User.objects.create_user(
            username='dra_d12',
            password='pass',
            is_staff=True,
            email='dra_d12@ejemplo.com',
        )
        ct = ContentType.objects.get_for_model(Paciente)
        self.medico.user_permissions.add(
            *Permission.objects.filter(content_type=ct)
        )

    def test_el_admin_no_deja_nacer_un_paciente_activo_sin_medico(self):
        """Capa 1 — la puerta de entrada de todos los días.

        El desplegable nace vacío y con una sola opción posible (el propio
        médico). Dejarlo así es el camino de menor resistencia, no un descuido
        rebuscado. Da igual si el formulario lo rechaza o si se lo asigna solo:
        lo que no puede quedar es un paciente activo sin responsable.
        """
        self.client.force_login(self.medico)

        self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Sin Responsable',
                'cedula': 'D12-0001',
                'telefono_whatsapp': '+573007770001',
                'fecha_cirugia': timezone.localdate().isoformat(),
                # `activo` es un checkbox: omitirlo crea el paciente INACTIVO y
                # la prueba pasaría en verde sin haber probado nada.
                'activo': 'on',
            },
            follow=True,
        )

        self.assertFalse(
            Paciente.objects.filter(
                activo=True, medico_responsable__isnull=True
            ).exists()
        )

    def test_el_admin_asigna_al_medico_que_guarda_en_vez_de_rechazarlo(self):
        """Añadida en D-4 para fijar CUÁL de los dos mecanismos se eligió.

        El invariante de arriba se cumpliría igual rechazando el formulario.
        Se eligió asignar: el médico no-superusuario solo puede elegirse a sí
        mismo, así que un error de validación sería un obstáculo por un campo
        con una única opción posible. Esta prueba impide que la corrección
        derive hacia el rechazo sin que nadie lo decida.
        """
        self.client.force_login(self.medico)

        self.client.post(
            '/admin/signos_sintomas/paciente/add/',
            {
                'nombre_completo': 'Paciente Asignado Solo',
                'cedula': 'D12-0005',
                'telefono_whatsapp': '+573007770005',
                'fecha_cirugia': timezone.localdate().isoformat(),
                'activo': 'on',
            },
            follow=True,
        )

        paciente = Paciente.objects.get(cedula='D12-0005')
        self.assertEqual(paciente.medico_responsable, self.medico)

    def test_borrar_la_cuenta_del_medico_no_deja_pacientes_huerfanos(self):
        """Capa 2 — la puerta de atrás.

        Con on_delete=SET_NULL, borrar una cuenta de médico convierte a todos
        sus pacientes en huérfanos invisibles, en silencio. Quién atendió a un
        paciente es historia clínica, no configuración.
        """
        from django.db.models import ProtectedError

        Paciente.objects.create(
            nombre_completo='Paciente Con Responsable',
            telefono_whatsapp='+573007770002',
            cedula='D12-0002',
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )

        with self.assertRaises(ProtectedError):
            self.medico.delete()

    def test_la_base_rechaza_un_paciente_activo_sin_medico(self):
        """Capa 4 — la garantía, para lo que no pasa por el Admin.

        Un script, el shell o una carga de datos no ven el formulario. La
        restricción vive en la base y no se puede esquivar.
        """
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paciente.objects.create(
                    nombre_completo='Paciente De Script',
                    telefono_whatsapp='+573007770003',
                    cedula='D12-0003',
                    fecha_cirugia=timezone.localdate(),
                    medico_responsable=None,
                    activo=True,
                )

    def test_un_paciente_inactivo_sin_medico_sigue_siendo_valido(self):
        """NACE EN VERDE A PROPÓSITO: congela el alcance de la restricción.

        La palabra *activo* es la que hace el invariante cumplible. Exigir el
        médico en las filas históricas obligaría a inventarles uno — fabricar
        una atribución clínica, justo lo que D3 se negó a hacer. Esta prueba
        existe para que la capa 4 no se escriba como NOT NULL.
        """
        paciente = Paciente.objects.create(
            nombre_completo='Paciente Histórico',
            telefono_whatsapp='+573007770004',
            cedula='D12-0004',
            fecha_cirugia=timezone.localdate() - timedelta(days=30),
            medico_responsable=None,
            activo=False,
        )

        self.assertIsNone(paciente.medico_responsable)

    def test_el_seed_de_produccion_se_niega_sin_medico_usable(self):
        """El comando que hoy fabrica huérfanos: advierte y crea igual."""
        from io import StringIO

        from django.core.management import call_command

        get_user_model().objects.all().delete()

        call_command(
            'seed_demo_produccion', '--confirmar',
            stdout=StringIO(), stderr=StringIO(),
        )

        self.assertFalse(
            Paciente.objects.filter(cedula__startswith='DEMO-').exists()
        )
