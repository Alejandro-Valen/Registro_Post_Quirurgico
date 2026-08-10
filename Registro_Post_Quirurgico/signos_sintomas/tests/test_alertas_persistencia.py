"""Persistencia de alertas: cola de evaluacion, deduplicacion y evidencia.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from ..alert_engine import evaluar_registro
from ..models import (
    Alerta,
    CheckInProgramado,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RegistroDiario,
)
from .soporte import medico_de_pruebas


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
        from ..evaluacion_alertas import evaluar_registro_con_estado

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

        from ..evaluacion_alertas import evaluar_registro_con_estado

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

        from ..evaluacion_alertas import evaluar_registro_con_estado

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

        from ..alert_engine import _registrar_alerta

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
