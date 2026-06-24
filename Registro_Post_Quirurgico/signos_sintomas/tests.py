from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import bot
from .alert_engine import evaluar_registro
from .models import Alerta, ConversacionWhatsApp, Paciente, RegistroDiario


class AlertEngineTests(TestCase):
    def test_temperatura_alta_crea_alerta_sepsis(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Prueba",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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

    def test_drenaje_purulento_crea_alerta_fuga_anastomotica(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Drenaje",
            telefono_whatsapp="+573004445566",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nauseas",
            telefono_whatsapp="+573007778899",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Gases",
            telefono_whatsapp="+573006661122",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Estable",
            telefono_whatsapp="+573005551234",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Multiple",
            telefono_whatsapp="+573005550000",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Limite",
            telefono_whatsapp="+573005559999",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Seroso",
            telefono_whatsapp="+573001110001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hematico",
            telefono_whatsapp="+573001110002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Turbio",
            telefono_whatsapp="+573001110003",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Drenaje",
            telefono_whatsapp="+573001110004",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Legacy",
            telefono_whatsapp="+573001110005",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Temp Alta",
            telefono_whatsapp="+573008880001",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Subfebricula Un Dia",
            telefono_whatsapp="+573008880002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Subfebricula Persistente",
            telefono_whatsapp="+573008880003",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Temp Normal",
            telefono_whatsapp="+573008880004",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Gases Un Dia",
            telefono_whatsapp="+573008880010",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Gases Dos Dias",
            telefono_whatsapp="+573008880011",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dos Checkins Mismo Dia",
            telefono_whatsapp="+573008880012",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Gases Parcial",
            telefono_whatsapp="+573008880013",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nausea Baja",
            telefono_whatsapp="+573008880020",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nausea Alta",
            telefono_whatsapp="+573008880021",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nausea Suma Dia",
            telefono_whatsapp="+573008880022",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nausea Persistente",
            telefono_whatsapp="+573008880023",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Sin Nauseas",
            telefono_whatsapp="+573008880024",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Nausea Persistente Larga",
            telefono_whatsapp="+573008880025",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dolor POD1",
            telefono_whatsapp="+573008880030",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dolor POD1 Alto",
            telefono_whatsapp="+573008880031",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dolor POD6",
            telefono_whatsapp="+573008880032",
            fecha_cirugia=timezone.localdate() - timedelta(days=6),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dolor POD6 Bajo",
            telefono_whatsapp="+573008880033",
            fecha_cirugia=timezone.localdate() - timedelta(days=6),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Dolor Tendencia",
            telefono_whatsapp="+573008880034",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente No Tolera Liquidos",
            telefono_whatsapp="+573008880050",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente No Tolera Dos Dias",
            telefono_whatsapp="+573008880051",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Tolera Liquidos",
            telefono_whatsapp="+573008880052",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Liquidos Null",
            telefono_whatsapp="+573008880053",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Puntual",
            telefono_whatsapp="+573008880060",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "nada", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "BAJA")

    def test_hinchazon_empeoramiento_sostenido_crea_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Sostenido",
            telefono_whatsapp="+573008880061",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "MEDIA")

    def test_hinchazon_subida_progresiva_crea_media(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Progresiva",
            telefono_whatsapp="+573008880062",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "nada", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "MEDIA")

    def test_hinchazon_fluctuacion_que_mejora_no_crea_media(self):
        # antier algo, ayer mucho, hoy algo → hoy bajó, no escala.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Fluctua",
            telefono_whatsapp="+573008880063",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "mucho", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 0)

    def test_hinchazon_estable_no_crea_alerta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Estable",
            telefono_whatsapp="+573008880064",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "algo", dias_atras=2)
        self._crear_hinchazon(paciente, "algo", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "algo")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 0)

    def test_hinchazon_mucho_4_dias_crea_alta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Mucho 4d",
            telefono_whatsapp="+573008880065",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        self._crear_hinchazon(paciente, "mucho", dias_atras=3)
        self._crear_hinchazon(paciente, "mucho", dias_atras=2)
        self._crear_hinchazon(paciente, "mucho", dias_atras=1)
        reg_hoy = self._crear_hinchazon(paciente, "mucho")
        alertas = evaluar_registro(reg_hoy)
        ileo = [a for a in alertas if a.tipo == "ILEO_PARALITICO"]
        self.assertEqual(len(ileo), 1)
        self.assertEqual(ileo[0].severidad, "ALTA")

    def test_hinchazon_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Hinchazon Null",
            telefono_whatsapp="+573008880066",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 100",
            telefono_whatsapp="+573008880070",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 100))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 0)

    def test_fc_101_crea_baja(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 101",
            telefono_whatsapp="+573008880071",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 101))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_109_crea_baja(self):
        # Borde superior de BAJA (109).
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 109",
            telefono_whatsapp="+573008880072",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 109))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_110_crea_media(self):
        # Borde inferior de MEDIA (110) — umbral CREWS 2022.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 110",
            telefono_whatsapp="+573008880073",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 110))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_149_crea_media(self):
        # Borde superior de MEDIA (149).
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 149",
            telefono_whatsapp="+573008880074",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 149))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_150_crea_alta(self):
        # Borde inferior de ALTA (150) — escalamiento inmediato.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 150",
            telefono_whatsapp="+573008880075",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, 150))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "ALTA")

    def test_fc_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC Null",
            telefono_whatsapp="+573008880076",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        alertas = evaluar_registro(self._crear_fc(paciente, None))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 0)

    def test_frecuencia_respiratoria_no_genera_alerta(self):
        # FR es solo-dashboard: aunque el valor sea alto (30 rpm) y el
        # resto del registro sea neutro, el alert_engine NO debe generar
        # ninguna alerta. (Outersterp 2025: 77% de falsas alertas venían
        # del sensor de FR — decisión de no evaluarla.)
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FR Alta",
            telefono_whatsapp="+573008880080",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Cirugia Futura",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() + timedelta(days=1),
            medico_responsable="Medico Prueba",
        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_hoy_da_dia_cero(self):
        # Borde exacto: cirugía hoy → POD 0 (el día de la cirugía).
        # Aquí el .days ya es 0 natural, sin intervención del clamp.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Cirugia Hoy",
            telefono_whatsapp="+573009990002",
            fecha_cirugia=timezone.localdate(),
            medico_responsable="Medico Prueba",
        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_pasada_calcula_dia_correcto(self):
        # Camino normal: el clamp NO debe alterar el cálculo positivo.
        # Operado hace 5 días → POD 5. Guarda contra un max(0, ...) mal
        # escrito que aplastara también los valores válidos.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente POD5",
            telefono_whatsapp="+573009990003",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable="Medico Prueba",
        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 5)


class BotWhatsAppTests(TestCase):
    TELEFONO = "+573001112233"
    TELEFONO_TWILIO = "whatsapp:+573001112233"

    def _crear_paciente(self):
        return Paciente.objects.create(
            nombre_completo="Paciente Bot",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            medico_responsable="Medico Prueba",
        )

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
        respuesta = bot.procesar_mensaje(self.TELEFONO_TWILIO, "hola")
        self.assertEqual(respuesta, bot.MSG_PREGUNTA_TEMPERATURA)
        conv = ConversacionWhatsApp.objects.get()
        self.assertEqual(conv.estado, ConversacionWhatsApp.ESTADO_TEMPERATURA)

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
        self.assertIsNone(conv.temp_temperatura)  # parciales limpiados

    def test_alerta_no_se_muestra_al_paciente(self):
        self._crear_paciente()
        respuesta = self._completar_flujo(temperatura="38.5")  # dispara SEPSIS
        # La alerta se crea para el oncólogo...
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 1)
        # ...pero el paciente solo ve la confirmación neutra.
        self.assertEqual(respuesta, bot.MSG_CONFIRMACION)
        self.assertNotIn("sepsis", respuesta.lower())
        self.assertNotIn("alerta", respuesta.lower())

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


class WebhookWhatsAppTests(TestCase):
    def setUp(self):
        self.url = reverse('signos_sintomas:webhook_whatsapp')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_post_valido_devuelve_twiml(self):
        Paciente.objects.create(
            nombre_completo="Paciente Webhook",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
            medico_responsable="Medico Prueba",
        )
        respuesta = self.client.post(
            self.url, {'From': 'whatsapp:+573001112233', 'Body': 'hola'}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')
        self.assertIn('temperatura', respuesta.content.decode().lower())

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
