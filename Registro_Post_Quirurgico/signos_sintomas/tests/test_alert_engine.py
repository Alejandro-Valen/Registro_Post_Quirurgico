"""Reglas clinicas del motor de alertas (alert_engine.py).

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from ..alert_engine import _severidad_dolor_por_ventana, evaluar_registro
from ..models import (
    Alerta,
    DeteccionAlerta,
    Paciente,
    RegistroDiario,
)
from .soporte import ANCLA_MEDIANOCHE, medico_de_pruebas


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


@freeze_time(ANCLA_MEDIANOCHE)
class FronterasDeUmbralTests(TestCase):
    """El valor que dispara cada umbral, y el inmediatamente inferior que NO.

    **Por que existe.** El 07/09/2026 se ejecuto un sabotaje de una linea sobre
    `alert_engine.py`: quitar `'fecaloide'` de `DRENAJES_ALTA`. Las 344 pruebas
    de entonces quedaron **en verde** con el motor clinico roto — un paciente
    podia reportar contenido intestinal por el drenaje y no generarse ninguna
    alerta. La auditoria de calidad de pruebas midio el patron detras: de las 30
    severidades del sistema solo 15 tenian el caso frontera, y `dolor_eva` nunca
    valia 7 ni `episodios_nauseas` 3 en toda la suite.

    **Que hace esta clase.** Aplica a las demas familias de reglas el patron que
    la Regla 8 (frecuencia cardiaca) ya tenia en casa: por cada umbral, el valor
    que dispara y el valor justo por debajo, que es el que de verdad ancla la
    constante. Sin la mitad inferior, mover el umbral no rompe nada.

    **Que NO hace.** No fija ningun umbral nuevo ni revisa los existentes: ancla
    los que ya decidio el Arquitecto y documenta `docs/reglas_clinicas.md`.

    **Como se verificaron.** Cada prueba se dio por buena solo despues de
    aplicarle su sabotaje y **verla caer**; el registro sabotaje por sabotaje
    esta en `proceso/verificaciones/2026-09-08_verificacion_umbrales.py`. Una
    prueba de frontera que nace en verde no sabe lo que dice saber.
    """

    def setUp(self):
        self.medico = medico_de_pruebas()
        self.telefonos_usados = 0

    def _paciente(self, dias_desde_cirugia=5):
        """Paciente nuevo con telefono unico y un dia postoperatorio conocido.

        `dia_postoperatorio` lo congela `RegistroDiario.save()` al crear el
        registro, restando `fecha_cirugia` de la fecha de ESE momento — que con
        el ancla de reloj es siempre hoy. Por eso el POD se controla desde aqui,
        retrocediendo la fecha de cirugia, y no tocando el registro.
        """
        self.telefonos_usados += 1
        return Paciente.objects.create(
            medico_responsable=self.medico,
            nombre_completo=f"Paciente Frontera {self.telefonos_usados}",
            telefono_whatsapp=f"+57300{self.telefonos_usados:07d}",
            fecha_cirugia=timezone.localdate() - timedelta(days=dias_desde_cirugia),
        )

    def _registro(self, paciente, dias_atras=0, **campos):
        """Registro clinicamente NEUTRO salvo los campos que la prueba mueva.

        Neutro quiere decir que ninguna de las ocho reglas dispara: 37.0 grados,
        EVA 2 (por debajo del piso de la ventana mas sensible, POD 6+), con
        gases, sin nauseas, sin drenaje y sin frecuencia cardiaca. Asi la alerta
        que aparezca solo puede venir de la variable que la prueba movio, y una
        asercion de "no hay alerta" significa algo.

        `dias_atras` retro-fecha el registro DESPUES de crearlo, que es como lo
        hacen el resto de las pruebas multidia: el motor agrupa por
        `fecha_registro__date`.
        """
        valores = {
            'temperatura': Decimal("37.0"),
            'dolor_eva': 2,
            'tiene_drenaje': False,
            'presencia_gases': True,
            'episodios_nauseas': 0,
        }
        valores.update(campos)
        registro = RegistroDiario.objects.create(paciente=paciente, **valores)
        if dias_atras:
            RegistroDiario.objects.filter(pk=registro.pk).update(
                fecha_registro=timezone.now() - timedelta(days=dias_atras)
            )
            registro.refresh_from_db()
        return registro

    def _severidades(self, registro, tipo):
        return [a.severidad for a in evaluar_registro(registro) if a.tipo == tipo]

    # --- Regla 2: drenaje ---

    def test_drenaje_fecaloide_crea_fuga_alta(self):
        """El sabotaje del 07/09/2026: quitar 'fecaloide' de DRENAJES_ALTA.

        Contenido intestinal saliendo por el drenaje es una fuga anastomotica
        franca — el peor signo que captura el sistema. No tenia ni una prueba.
        """
        paciente = self._paciente()
        registro = self._registro(
            paciente, tiene_drenaje=True, aspecto_drenaje='fecaloide'
        )
        self.assertEqual(self._severidades(registro, 'FUGA_ANASTOMOTICA'), ['ALTA'])

    # --- Regla 1: temperatura ---

    def test_temperatura_378_un_dia_no_crea_alerta(self):
        """Frontera inferior de SEPSIS/ALTA (37.9).

        37.8 cae en la banda de subfebricula, que con un solo dia no alerta:
        el registro no debe producir NINGUNA alerta de sepsis. Es la prueba que
        ancla el 37.9 — sin ella, bajar el umbral a 37.8 no rompe nada.
        """
        paciente = self._paciente()
        registro = self._registro(paciente, temperatura=Decimal("37.8"))
        self.assertEqual(self._severidades(registro, 'SEPSIS'), [])

    def test_temperatura_375_dos_dias_crea_sepsis_media(self):
        """Frontera inferior de la banda de subfebricula (37.5)."""
        paciente = self._paciente()
        self._registro(paciente, dias_atras=1, temperatura=Decimal("37.5"))
        hoy = self._registro(paciente, temperatura=Decimal("37.5"))
        self.assertEqual(self._severidades(hoy, 'SEPSIS'), ['MEDIA'])

    def test_temperatura_374_dos_dias_no_crea_alerta(self):
        """El valor justo por debajo de la subfebricula, con el mismo escenario.

        Mismo montaje que la prueba anterior cambiando solo una decima: si el
        piso de la banda bajara a 37.4, esta prueba lo denuncia.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=1, temperatura=Decimal("37.4"))
        hoy = self._registro(paciente, temperatura=Decimal("37.4"))
        self.assertEqual(self._severidades(hoy, 'SEPSIS'), [])

    def test_subfebricula_con_hueco_de_un_dia_no_crea_alerta(self):
        """Decision D8: los dos dias de la Regla 1b son CONSECUTIVOS.

        Antier 37.6, ayer sin ningun reporte, hoy 37.6. Son dos dias con dato
        de subfebricula, pero no dos dias seguidos: el dia sin reporte es un
        desconocido genuino y contar a traves de el inventaria un hecho clinico.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=2, temperatura=Decimal("37.6"))
        hoy = self._registro(paciente, temperatura=Decimal("37.6"))
        self.assertEqual(self._severidades(hoy, 'SEPSIS'), [])

    # --- Regla 3: gases ---

    def test_gases_hueco_de_un_dia_corta_el_conteo(self):
        """Decision D8 sobre la Regla 3, la unica de dias que llega hasta ALTA.

        Cuatro dias de calendario: tres sin gases y uno sin ningun reporte en
        medio. Contando dias con dato serian tres — ALTA, "ir a urgencias".
        Contando dias consecutivos son dos: MEDIA. El hueco corta.

        Sin esta prueba, borrar la guarda `if not existe_registro: break` de
        `_evaluar_gases` no rompe nada, y el sistema empieza a mandar pacientes
        a urgencias por dias que nunca reportaron.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=3, presencia_gases=False)
        # dias_atras=2 se deja vacio a proposito: es el hueco.
        self._registro(paciente, dias_atras=1, presencia_gases=False)
        hoy = self._registro(paciente, presencia_gases=False)
        self.assertEqual(self._severidades(hoy, 'ILEO_PARALITICO'), ['MEDIA'])

    # --- Regla 4: nauseas ---

    def test_nauseas_dos_episodios_crea_baja(self):
        """Frontera superior de BAJA (1-2 episodios)."""
        paciente = self._paciente()
        registro = self._registro(paciente, episodios_nauseas=2)
        self.assertEqual(self._severidades(registro, 'ILEO_PARALITICO'), ['BAJA'])

    def test_nauseas_tres_episodios_crea_media(self):
        """Frontera inferior de MEDIA (NAUSEAS_MEDIA_MIN = 3).

        `episodios_nauseas` no valia 3 en ninguna de las 344 pruebas: subir la
        constante a 4 pasaba sin que cayera nada.
        """
        paciente = self._paciente()
        registro = self._registro(paciente, episodios_nauseas=3)
        self.assertEqual(self._severidades(registro, 'ILEO_PARALITICO'), ['MEDIA'])

    def test_nauseas_persistencia_tres_dias_no_escala_a_alta(self):
        """Frontera inferior de la Regla 4e (DIAS_NAUSEAS_ALTA = 4).

        Tres dias seguidos con nauseas se quedan en MEDIA por persistencia. La
        prueba que ya existia usaba cuatro dias y daba ALTA; sin esta, bajar el
        umbral a tres convertiria en "ir a urgencias" un cuadro que el
        Arquitecto decidio que se llama por telefono.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=2, episodios_nauseas=1)
        self._registro(paciente, dias_atras=1, episodios_nauseas=1)
        hoy = self._registro(paciente, episodios_nauseas=1)
        self.assertEqual(self._severidades(hoy, 'ILEO_PARALITICO'), ['MEDIA'])

    def test_nauseas_hueco_de_un_dia_corta_la_persistencia(self):
        """Decision D8 sobre la Regla 4d.

        Antier y hoy con nauseas, ayer sin ningun reporte: la persistencia vale
        1, no 2, asi que manda la suma del dia (1 episodio -> BAJA) y no la
        escalada a MEDIA.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=2, episodios_nauseas=1)
        hoy = self._registro(paciente, episodios_nauseas=1)
        self.assertEqual(self._severidades(hoy, 'ILEO_PARALITICO'), ['BAJA'])

    # --- Regla 5: dolor ---

    def test_dolor_pod2_eva7_crea_media(self):
        """Frontera inferior de MEDIA en la ventana POD 0-2 (EVA 7).

        `dolor_eva` no valia 7 en ninguna de las 344 pruebas. El sabotaje
        `VENTANAS_DOLOR (2, 5, 7, 9) -> (2, 5, 8, 9)` pasaba sin que cayera
        nada: un paciente con dolor 7 en el segundo dia postoperatorio quedaba
        clasificado BAJA, "monitorear", en vez de MEDIA, "llamar al medico".
        """
        paciente = self._paciente(dias_desde_cirugia=2)
        registro = self._registro(paciente, dolor_eva=7)
        self.assertEqual(self._severidades(registro, 'DOLOR_AGUDO'), ['MEDIA'])

    def test_dolor_pod2_eva4_no_crea_alerta(self):
        """Frontera inferior de toda la ventana POD 0-2 (BAJA arranca en 5)."""
        paciente = self._paciente(dias_desde_cirugia=2)
        registro = self._registro(paciente, dolor_eva=4)
        self.assertEqual(self._severidades(registro, 'DOLOR_AGUDO'), [])

    def test_matriz_de_ventanas_de_dolor(self):
        """Las tres ventanas completas, y los saltos entre ellas.

        Se ejercita `_severidad_dolor_por_ventana` directamente porque es la
        tabla clinica en si; el cableado hacia `evaluar_registro` ya lo fijan
        las dos pruebas end-to-end de arriba y las de `AlertEngineTests`.

        Las dos ultimas parejas son las fronteras ENTRE ventanas: el mismo EVA
        cambia de severidad al cruzar de POD 2 a POD 3 y de POD 5 a POD 6, que
        es lo que hace util tener tres ventanas en vez de una.
        """
        casos = [
            # POD 0-2 -> BAJA 5 / MEDIA 7 / ALTA 9
            (2, 4, None), (2, 5, 'BAJA'), (2, 6, 'BAJA'), (2, 7, 'MEDIA'),
            (2, 8, 'MEDIA'), (2, 9, 'ALTA'), (2, 10, 'ALTA'),
            # POD 3-5 -> BAJA 4 / MEDIA 6 / ALTA 8
            (3, 3, None), (3, 4, 'BAJA'), (3, 5, 'BAJA'), (3, 6, 'MEDIA'),
            (3, 7, 'MEDIA'), (3, 8, 'ALTA'),
            (5, 3, None), (5, 4, 'BAJA'), (5, 7, 'MEDIA'), (5, 8, 'ALTA'),
            # POD 6+ -> BAJA 3 / MEDIA 5 / ALTA 7
            (6, 2, None), (6, 3, 'BAJA'), (6, 4, 'BAJA'), (6, 5, 'MEDIA'),
            (6, 6, 'MEDIA'), (6, 7, 'ALTA'),
            (30, 2, None), (30, 3, 'BAJA'), (30, 7, 'ALTA'),
            # Fronteras ENTRE ventanas: el mismo EVA, un dia de diferencia.
            (2, 4, None), (3, 4, 'BAJA'),
            (5, 3, None), (6, 3, 'BAJA'),
        ]
        for pod, eva, esperada in casos:
            with self.subTest(pod=pod, eva=eva):
                self.assertEqual(_severidad_dolor_por_ventana(pod, eva), esperada)

    def test_dolor_tendencia_delta_dos_no_escala(self):
        """Frontera inferior de la Regla 5b (DOLOR_DELTA_TENDENCIA = 3).

        Promedio de 3 hace dos y tres dias, promedio de 5 ayer y hoy: la subida
        es de 2 puntos y NO debe escalar. Por tabla, POD 5 con EVA 5 es BAJA, y
        BAJA se queda. La prueba que ya existia probaba delta 3 y si escalaba;
        esta es la mitad que faltaba.
        """
        paciente = self._paciente(dias_desde_cirugia=5)
        for dias_atras, eva in ((3, 3), (2, 3), (1, 5)):
            self._registro(paciente, dias_atras=dias_atras, dolor_eva=eva)
        hoy = self._registro(paciente, dolor_eva=5)
        self.assertEqual(self._severidades(hoy, 'DOLOR_AGUDO'), ['BAJA'])

    # --- Regla 6: tolerancia a liquidos ---

    def test_liquidos_hueco_de_un_dia_corta_el_conteo(self):
        """Decision D8 sobre la Regla 6.

        Antier no tolero, ayer sin ningun reporte, hoy no tolera: son dos dias
        con dato pero no dos consecutivos, asi que la alerta es MEDIA ("vigilar
        hidratacion") y no ALTA ("ir a urgencias").
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=2, tolero_liquidos=False)
        hoy = self._registro(paciente, tolero_liquidos=False)
        self.assertEqual(self._severidades(hoy, 'INTOLERANCIA_ORAL'), ['MEDIA'])

    # --- Regla 7: hinchazon ---

    def test_hinchazon_mucho_tres_dias_no_escala_a_alta(self):
        """Frontera inferior de la Regla 7c (DIAS_HINCHAZON_MUCHO_ALTA = 4).

        Tres dias seguidos en "mucho" no alertan por ninguna de las tres
        clausulas: no hay empeoramiento contra ayer ni contra antier —el nivel
        no sube, ya esta en el techo— y no se alcanzan los cuatro dias. Bajar
        el umbral a tres pasaba sin que cayera nada.
        """
        paciente = self._paciente()
        self._registro(paciente, dias_atras=2, hinchazon_abdominal='mucho')
        self._registro(paciente, dias_atras=1, hinchazon_abdominal='mucho')
        hoy = self._registro(paciente, hinchazon_abdominal='mucho')
        self.assertEqual(self._severidades(hoy, 'ILEO_PARALITICO'), [])
