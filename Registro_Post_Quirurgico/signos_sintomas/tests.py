from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import bot
from .alert_engine import evaluar_registro
from .models import Alerta, CheckInProgramado, ConversacionWhatsApp, Paciente, RegistroDiario


class AlertEngineTests(TestCase):
    def test_temperatura_alta_crea_alerta_sepsis(self):
        paciente = Paciente.objects.create(
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

    def test_drenaje_purulento_crea_alerta_fuga_anastomotica(self):
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 100",
            telefono_whatsapp="+573008880070",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 100))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 0)

    def test_fc_101_crea_baja(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 101",
            telefono_whatsapp="+573008880071",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 101))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_109_crea_baja(self):
        # Borde superior de BAJA (109).
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 109",
            telefono_whatsapp="+573008880072",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 109))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "BAJA")

    def test_fc_110_crea_media(self):
        # Borde inferior de MEDIA (110) — umbral CREWS 2022.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 110",
            telefono_whatsapp="+573008880073",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 110))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_149_crea_media(self):
        # Borde superior de MEDIA (149).
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 149",
            telefono_whatsapp="+573008880074",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 149))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "MEDIA")

    def test_fc_150_crea_alta(self):
        # Borde inferior de ALTA (150) — escalamiento inmediato.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente FC 150",
            telefono_whatsapp="+573008880075",
            fecha_cirugia=timezone.localdate(),        )
        alertas = evaluar_registro(self._crear_fc(paciente, 150))
        taqui = [a for a in alertas if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui), 1)
        self.assertEqual(taqui[0].severidad, "ALTA")

    def test_fc_null_no_crea_alerta(self):
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Cirugia Futura",
            telefono_whatsapp="+573009990001",
            fecha_cirugia=timezone.localdate() + timedelta(days=1),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_hoy_da_dia_cero(self):
        # Borde exacto: cirugía hoy → POD 0 (el día de la cirugía).
        # Aquí el .days ya es 0 natural, sin intervención del clamp.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Cirugia Hoy",
            telefono_whatsapp="+573009990002",
            fecha_cirugia=timezone.localdate(),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 0)

    def test_fecha_cirugia_pasada_calcula_dia_correcto(self):
        # Camino normal: el clamp NO debe alterar el cálculo positivo.
        # Operado hace 5 días → POD 5. Guarda contra un max(0, ...) mal
        # escrito que aplastara también los valores válidos.
        paciente = Paciente.objects.create(
            nombre_completo="Paciente POD5",
            telefono_whatsapp="+573009990003",
            fecha_cirugia=timezone.localdate() - timedelta(days=5),        )
        registro = self._crear_registro(paciente)
        self.assertEqual(registro.dia_postoperatorio, 5)


class BotWhatsAppTests(TestCase):
    TELEFONO = "+573001112233"
    TELEFONO_TWILIO = "whatsapp:+573001112233"

    def _crear_paciente(self):
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Bot",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
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
        # B3: evaluar_registro corre vía on_commit (post-commit en producción).
        # captureOnCommitCallbacks(execute=True) lo ejecuta síncronamente en tests.
        self._crear_paciente()
        with self.captureOnCommitCallbacks(execute=True):
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
        Paciente.objects.create(
            nombre_completo="Paciente Sin CheckIn",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
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
        Paciente.objects.create(
            nombre_completo="Paciente Decimal FC",
            telefono_whatsapp="+573007778881",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
        )
        from signos_sintomas import bot as b
        conv = ConversacionWhatsApp.objects.create(
            paciente=Paciente.objects.get(telefono_whatsapp="+573007778881"),
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Abandono",
            telefono_whatsapp=self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
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
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Webhook",
            telefono_whatsapp="+573001112233",
            fecha_cirugia=timezone.localdate() - timedelta(days=3),
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
            {'From': 'whatsapp:+573009999999', 'Body': ''},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/xml')

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_idempotencia_mismo_sid_ignora_segundo_mensaje(self):
        # Twilio puede reintentar un webhook con el mismo MessageSid.
        # El segundo mensaje con el mismo SID debe devolver TwiML vacío sin
        # ejecutar la lógica del bot de nuevo.
        Paciente.objects.create(
            nombre_completo="Paciente Idempotencia",
            telefono_whatsapp="+573002223344",
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
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

    @override_settings(TWILIO_VALIDATE_SIGNATURE=False)
    def test_rate_limit_excedido_devuelve_twiml_vacio(self):
        # Más de _LIMITE_MENSAJES_HORA (20) mensajes del mismo número en una
        # hora → los mensajes excedentes reciben TwiML vacío sin procesar.
        from signos_sintomas.views import _LIMITE_MENSAJES_HORA
        telefono = 'whatsapp:+573005556677'
        # Forzar el contador de cache directamente al límite
        clave = 'rl_wh_{}'.format(telefono.replace('+', '').replace(':', ''))
        cache.set(clave, _LIMITE_MENSAJES_HORA, 3600)

        respuesta = self.client.post(
            self.url,
            {'From': telefono, 'Body': 'hola'},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(b'<Message>', respuesta.content)


class PacienteMedicoFKTests(TestCase):
    """Tests de la relación ForeignKey Paciente → auth.User (medico_responsable)."""

    def _crear_paciente(self, **kwargs):
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
        paciente = self._crear_paciente()
        self.assertEqual(str(paciente), "Paciente FK Test — Sin médico asignado")

    def test_set_null_al_borrar_usuario(self):
        User = get_user_model()
        medico = User.objects.create_user(username='dr_delete', password='x')
        paciente = self._crear_paciente(medico_responsable=medico)
        medico.delete()
        paciente.refresh_from_db()
        self.assertIsNone(paciente.medico_responsable)


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
        for model in (Paciente, RegistroDiario, Alerta):
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


class AlertaAdminAccionesTests(TestCase):
    """Bloque 5A — Colores severidad + acción marcar_resuelta en AlertaAdmin."""

    def setUp(self):
        User = get_user_model()
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        self.superuser = User.objects.create_superuser(
            username='super5a', password='pass',
        )
        self.paciente = Paciente.objects.create(
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
        """La acción marcar_resuelta actualiza la alerta y registra fecha_resolucion."""
        self.client.force_login(self.superuser)
        self.client.post(
            '/admin/signos_sintomas/alerta/',
            {
                'action': 'marcar_resuelta',
                '_selected_action': [str(self.alerta.pk)],
            },
        )
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.resuelta)
        self.assertIsNotNone(self.alerta.fecha_resolucion)


class AlertaEmailNotificacionTests(TestCase):
    """Bloque 5C — Email al médico cuando se crea alerta ALTA."""

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

    def test_alerta_alta_envia_email(self):
        """Al crear alerta ALTA con médico+email, se envía un email vía on_commit."""
        from django.core import mail
        with self.captureOnCommitCallbacks(execute=True):
            Alerta.objects.create(
                paciente=self.paciente,
                registro_origen=self.registro,
                tipo='SEPSIS',
                severidad='ALTA',
                mensaje='Fiebre alta de prueba.',
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ALERTA ALTA', mail.outbox[0].subject)
        self.assertIn('dr@test.com', mail.outbox[0].to)

    def test_alerta_alta_email_incluye_telefono_cedula_y_hora_local(self):
        """A-4: el cuerpo del email trae teléfono, cédula y hora en zona Bogotá."""
        from django.core import mail
        with self.captureOnCommitCallbacks(execute=True):
            alerta = Alerta.objects.create(
                paciente=self.paciente,
                registro_origen=self.registro,
                tipo='SEPSIS',
                severidad='ALTA',
                mensaje='Fiebre alta de prueba.',
            )
        cuerpo = mail.outbox[0].body
        self.assertIn(self.paciente.telefono_whatsapp, cuerpo)
        self.assertIn(self.paciente.cedula, cuerpo)
        self.assertIn(
            timezone.localtime(alerta.fecha_alerta).strftime('%d/%m/%Y %H:%M'),
            cuerpo,
        )
        self.assertIn('─', cuerpo)

    def test_alerta_alta_email_sin_cedula_muestra_no_registrada(self):
        """Paciente legado sin cédula: el email no debe fallar ni mostrar 'None'."""
        from django.core import mail
        paciente_sin_cedula = Paciente.objects.create(
            nombre_completo="Sin Cedula",
            telefono_whatsapp="+573019990004",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=self.medico,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente_sin_cedula,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        with self.captureOnCommitCallbacks(execute=True):
            Alerta.objects.create(
                paciente=paciente_sin_cedula,
                registro_origen=registro,
                tipo='SEPSIS',
                severidad='ALTA',
                mensaje='Fiebre alta de prueba.',
            )
        cuerpo = mail.outbox[0].body
        self.assertIn('No registrada', cuerpo)
        self.assertNotIn('Cédula:   None', cuerpo)

    def test_alerta_media_no_envia_email(self):
        """Solo las alertas ALTA envían email — MEDIA y BAJA no."""
        from django.core import mail
        with self.captureOnCommitCallbacks(execute=True):
            Alerta.objects.create(
                paciente=self.paciente,
                registro_origen=self.registro,
                tipo='SEPSIS',
                severidad='MEDIA',
                mensaje='Subfebrícula.',
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_alerta_alta_sin_medico_no_falla(self):
        """Alerta ALTA en paciente sin médico responsable no lanza excepción."""
        from django.core import mail
        paciente_sin_medico = Paciente.objects.create(
            nombre_completo="Sin Médico",
            telefono_whatsapp="+573019990003",
            fecha_cirugia=timezone.localdate(),
            medico_responsable=None,
        )
        registro = RegistroDiario.objects.create(
            paciente=paciente_sin_medico,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        with self.captureOnCommitCallbacks(execute=True):
            Alerta.objects.create(
                paciente=paciente_sin_medico,
                registro_origen=registro,
                tipo='SEPSIS',
                severidad='ALTA',
                mensaje='Sin medico.',
            )
        self.assertEqual(len(mail.outbox), 0)


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


class CheckInProgramadoModelTests(TestCase):
    """Bloque 1 — Modelo CheckInProgramado: constraints, defaults y relaciones."""

    def setUp(self):
        self.paciente = Paciente.objects.create(
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


class AlertFechaReferenciaTests(TestCase):
    """Bloque 2A — parámetro fecha_referencia en evaluar_registro (decisión 0-①)."""

    def _paciente(self, tel):
        return Paciente.objects.create(
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
    """Bloque 2B — deduplicación Opción A+: una alerta por tipo/día,
    escalamiento intra-día permitido (decisión 0-②)."""

    def _paciente(self, tel):
        return Paciente.objects.create(
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

    def test_misma_severidad_mismo_dia_bloquea_duplicado(self):
        """Dos check-ins el mismo día con la misma condición y severidad:
        el segundo no crea una alerta duplicada del mismo tipo."""
        paciente = self._paciente("+573008881001")
        alertas1 = evaluar_registro(self._reg_fc(paciente, 150))  # ALTA TAQUICARDIA
        self.assertEqual(len([a for a in alertas1 if a.tipo == "TAQUICARDIA"]), 1)

        alertas2 = evaluar_registro(self._reg_fc(paciente, 155))  # también ALTA → bloqueado
        self.assertEqual(len([a for a in alertas2 if a.tipo == "TAQUICARDIA"]), 0)
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

    def test_escalamiento_intradiario_crea_alerta_mayor(self):
        """Mañana BAJA → tarde MEDIA: la MEDIA no es bloqueada porque su
        severidad es mayor. Opción A+ permite escalamiento intra-día."""
        paciente = self._paciente("+573008881002")
        alertas1 = evaluar_registro(self._reg_fc(paciente, 105))  # BAJA
        self.assertEqual([a for a in alertas1 if a.tipo == "TAQUICARDIA"][0].severidad, "BAJA")

        alertas2 = evaluar_registro(self._reg_fc(paciente, 120))  # MEDIA > BAJA → no bloqueado
        taqui2 = [a for a in alertas2 if a.tipo == "TAQUICARDIA"]
        self.assertEqual(len(taqui2), 1)
        self.assertEqual(taqui2[0].severidad, "MEDIA")
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 2)

    def test_severidad_menor_mismo_dia_bloqueada(self):
        """Mañana ALTA → tarde BAJA del mismo tipo: la BAJA es bloqueada.
        Una alerta no puede 'bajar' de severidad una vez alcanzada."""
        paciente = self._paciente("+573008881003")
        evaluar_registro(self._reg_fc(paciente, 150))  # ALTA
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

        alertas2 = evaluar_registro(self._reg_fc(paciente, 103))  # BAJA → bloqueado
        self.assertEqual(len([a for a in alertas2 if a.tipo == "TAQUICARDIA"]), 0)
        self.assertEqual(Alerta.objects.filter(tipo="TAQUICARDIA").count(), 1)

    def test_diferentes_dias_no_se_bloquean(self):
        """La deduplicación es diaria: ALTA ayer NO bloquea ALTA hoy.
        Se parchea fecha_alerta al día anterior porque auto_now_add siempre
        pone el timestamp de ahora — en producción la alerta de ayer fue
        creada realmente ayer, aquí hay que simularlo con update()."""
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
        self.assertEqual(len([a for a in alertas_hoy if a.tipo == "SEPSIS"]), 1)
        self.assertEqual(Alerta.objects.filter(tipo="SEPSIS").count(), 2)

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

    def test_gases_baja_y_nauseas_alta_mismo_dia_generan_dos_ileo(self):  # noqa: E501
        """Gases=False (BAJA) y nauseas=5 (ALTA) en el mismo registro:
        _evaluar_gases crea ILEO BAJA, luego _evaluar_nauseas prueba ALTA →
        ALTA > BAJA → no bloqueada → se crean 2 alertas ILEO (escalamiento
        intra-evaluación, Opción A+ lo permite porque la severidad sube)."""
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
        self.assertEqual(len(ileo), 2)
        severidades = {a.severidad for a in ileo}
        self.assertIn("BAJA", severidades)
        self.assertIn("ALTA", severidades)


class SchedulerTests(TestCase):
    """Bloque 4 — Management commands del scheduler y alerta SILENCIO."""

    def _paciente(self, tel="+573009990001"):
        return Paciente.objects.create(
            nombre_completo="Paciente Scheduler",
            telefono_whatsapp=tel,
            fecha_cirugia=timezone.localdate() - timedelta(days=5),
            activo=True,
        )

    def _checkin(self, paciente, orden=1, etiqueta=None, dias_atras=0,
                 estado=CheckInProgramado.ESTADO_PENDIENTE, horas_atras=0):
        if etiqueta is None:
            etiqueta = CheckInProgramado.ETIQUETA_MANANA
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

    def test_tres_checkins_consecutivos_dan_silencio_alta(self):
        """3+ check-ins NO_RESPONDIDO consecutivos → racha 3 → SILENCIO ALTA."""
        from django.core.management import call_command
        paciente = self._paciente()
        for orden, dias in [(1, 2), (2, 1)]:
            ci = self._checkin(paciente, orden=orden, dias_atras=dias, horas_atras=50)
            ci.estado = CheckInProgramado.ESTADO_NO_RESPONDIDO
            ci.save()
        self._checkin(paciente, orden=1, horas_atras=11)
        call_command('cerrar_checkins_vencidos', verbosity=0)
        alerta = Alerta.objects.filter(tipo='SILENCIO').order_by('-fecha_alerta').first()
        self.assertEqual(alerta.severidad, 'ALTA')

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


class PacienteCedulaTests(TestCase):
    """Sprint 5, Bloque 1A — campo cedula (P-4: identificador único, obligatorio)."""

    def test_paciente_sin_cedula_no_rompe_creacion(self):
        """Registros legado (sin cedula) siguen pudiéndose crear — null permitido."""
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Legado",
            telefono_whatsapp="+573001112222",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertIsNone(paciente.cedula)

    def test_cedula_duplicada_viola_unicidad(self):
        Paciente.objects.create(
            nombre_completo="Paciente Uno",
            cedula="123456789",
            telefono_whatsapp="+573001112223",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Paciente.objects.create(
                    nombre_completo="Paciente Dos",
                    cedula="123456789",
                    telefono_whatsapp="+573001112224",
                    fecha_cirugia=timezone.localdate(),
                )

    def test_dos_pacientes_sin_cedula_no_violan_unicidad(self):
        """NULL no cuenta como duplicado en la restricción unique (Postgres)."""
        Paciente.objects.create(
            nombre_completo="Paciente Sin Cedula 1",
            telefono_whatsapp="+573001112225",
            fecha_cirugia=timezone.localdate(),
        )
        Paciente.objects.create(
            nombre_completo="Paciente Sin Cedula 2",
            telefono_whatsapp="+573001112226",
            fecha_cirugia=timezone.localdate(),
        )
        self.assertEqual(Paciente.objects.count(), 2)

    # -----------------------------------------------------------------
    # A-2: full_clean() exige cédula en pacientes nuevos
    # -----------------------------------------------------------------

    def test_full_clean_sin_cedula_en_paciente_nuevo_lanza_error(self):
        paciente = Paciente(
            nombre_completo="Paciente Nuevo Sin Cedula",
            telefono_whatsapp="+573001112227",
            fecha_cirugia=timezone.localdate(),
        )
        with self.assertRaises(ValidationError) as ctx:
            paciente.full_clean()
        self.assertIn('cedula', ctx.exception.message_dict)

    def test_full_clean_con_cedula_en_paciente_nuevo_no_lanza_error(self):
        paciente = Paciente(
            nombre_completo="Paciente Nuevo Con Cedula",
            cedula="999888777",
            telefono_whatsapp="+573001112228",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar

    def test_full_clean_paciente_existente_sin_cedula_no_lanza_error(self):
        """Pacientes migrados (ya tienen pk) no se les exige cédula retroactivamente."""
        paciente = Paciente.objects.create(
            nombre_completo="Paciente Legado Existente",
            telefono_whatsapp="+573001112229",
            fecha_cirugia=timezone.localdate(),
        )
        paciente.full_clean()  # no debe lanzar — ya tiene pk


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


class DesactivarPacientesVencidosTests(TestCase):
    """Sprint 5, Bloque 1B — desactivación automática a 10 días postop (P-5)."""

    def _paciente(self, dias_cirugia, tel, activo=True):
        """Por defecto simula que el paciente se registró el día de su cirugía
        (fecha_registro = fecha_cirugia), para no disparar el guard de
        ingreso tardío (A-1, DIAS_GRACIA_INGRESO) en tests que no lo prueban."""
        paciente = Paciente.objects.create(
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
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=30')
        self.assertContains(resp, '<strong>30 días</strong>', html=False)

    def test_historial_valor_invalido_usa_default(self):
        resp = self.client.get(self._url_change(self.paciente_con_alerta) + '?dias=abc')
        self.assertContains(resp, '<strong>7 días</strong>', html=False)


class GraficaSignosVitalesTests(TestCase):
    """
    Sprint 5, Bloque 4 (rediseño 01/07/2026) — gráficas Chart.js con
    selector de período 7/14/30 días independiente del historial en
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
        import json
        import re
        match = re.search(r'var DATOS = (.+?);\s*var pid', contenido)
        self.assertIsNotNone(match, "No se encontró el objeto DATOS embebido en el HTML")
        return json.loads(match.group(1))

    def test_sin_registros_no_carga_chartjs(self):
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
        self.assertEqual(set(datos.keys()), {'7', '14', '30'})
        for periodo in ('7', '14', '30'):
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
        )
        resp = self.client.get(self._url_change())
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(datos['7']['alertas_idx'], [])

    def test_carga_version_fija_de_chartjs(self):
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change())
        self.assertContains(resp, "chart.js@4.4.0")

    def test_selector_de_grafica_es_independiente_del_historial(self):
        """El ?dias= de la URL controla el historial en tabla (Bloque 3B);
        la gráfica siempre trae los 3 períodos precalculados, sin depender
        de ese parámetro."""
        RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('37.0'), dolor_eva=2,
            aspecto_drenaje='sin_drenaje', presencia_gases=True, episodios_nauseas=0,
        )
        resp = self.client.get(self._url_change() + '?dias=30')
        self.assertContains(resp, '<strong>30 días</strong>', html=False)
        datos = self._extraer_datos(resp.content.decode())
        self.assertEqual(set(datos.keys()), {'7', '14', '30'})
