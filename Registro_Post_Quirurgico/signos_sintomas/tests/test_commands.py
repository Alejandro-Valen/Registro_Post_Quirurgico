"""Management commands, incluidos los que corren en el cron.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time

from .. import bot
from ..models import (
    Alerta,
    CheckInProgramado,
    ConversacionWhatsApp,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RegistroDiario,
)
from .soporte import ANCLA_MEDIANOCHE, EspiaDeTareasCronMixin, medico_de_pruebas


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
        return CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=fecha_dia,
            orden=orden,
            etiqueta=etiqueta,
            hora_programada=hora_prog,
            estado=estado,
        )

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
        from ..alert_engine import registrar_alerta_silencio

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

class CronMatutinoCommandTests(EspiaDeTareasCronMixin, TestCase):
    """Comando cron_matutino — corre las tareas de la mañana en orden."""

    def test_corre_las_seis_tareas_en_orden(self):
        """El orden es clínico, no cosmético — ver el docstring del comando.

        Se observan las tareas que corrieron de verdad, no las llamadas que
        recibió un mock: el requisito es el orden de ejecución y no debe
        depender de dónde viva el bucle que las despacha.
        """
        ejecutadas = self.espiar_tareas([
            'desactivar_pacientes_vencidos',
            'crear_checkins_diarios',
            'cerrar_checkins_vencidos',
            'enviar_recordatorios',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])

        fallo = self.correr_cron('cron_matutino')

        self.assertIsNone(fallo)
        self.assertEqual(ejecutadas, [
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

    def test_fallo_de_desactivar_omite_crear_checkins_pero_no_el_resto(self):
        """Dependencia clínica declarada — D14, la excepción a la regla.

        `crear_checkins_diarios` NO debe correr si `desactivar_pacientes_vencidos`
        falló: un paciente que vence hoy recibiría un check-in que quedaría
        PENDIENTE para siempre y generaría una alerta SILENCIO espuria. Esa es
        la mitad que ya se cumple hoy, por accidente, porque el cron se detiene
        en la primera excepción.

        La otra mitad es el requisito: ninguna de las cuatro tareas restantes
        depende de esa desactivación, así que todas —incluida la entrega de los
        correos de alerta ALTA— tienen que correr igual, y la corrida debe
        terminar en error diciendo qué falló y qué se omitió.
        """
        from django.core.management.base import CommandError

        ejecutadas = self.espiar_tareas(
            [
                'desactivar_pacientes_vencidos',
                'crear_checkins_diarios',
                'cerrar_checkins_vencidos',
                'enviar_recordatorios',
                'reintentar_evaluaciones_alertas',
                'procesar_notificaciones_email',
            ],
            fallan=('desactivar_pacientes_vencidos',),
        )

        fallo = self.correr_cron('cron_matutino')

        # La dependencia clínica se respeta: no se crean check-ins a ciegas.
        self.assertNotIn('crear_checkins_diarios', ejecutadas)
        # Y el aislamiento: lo que no depende de la que falló, corre.
        self.assertEqual(ejecutadas, [
            'desactivar_pacientes_vencidos',
            'cerrar_checkins_vencidos',
            'enviar_recordatorios',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])
        # La corrida no finge que todo salió bien.
        self.assertIsInstance(fallo, CommandError)
        self.assertIn('desactivar_pacientes_vencidos', str(fallo))
        self.assertIn('crear_checkins_diarios', str(fallo))

    def test_el_error_final_nombra_todas_las_tareas_que_fallaron(self):
        """No se rinde en la primera ni informa solo de una — D14.

        Dos fallos sin dependientes: las seis tareas corren igual y el resumen
        final nombra a las dos, para que el log de Railway diga qué revisar.
        """
        from django.core.management.base import CommandError

        ejecutadas = self.espiar_tareas(
            [
                'desactivar_pacientes_vencidos',
                'crear_checkins_diarios',
                'cerrar_checkins_vencidos',
                'enviar_recordatorios',
                'reintentar_evaluaciones_alertas',
                'procesar_notificaciones_email',
            ],
            fallan=('cerrar_checkins_vencidos', 'reintentar_evaluaciones_alertas'),
        )

        fallo = self.correr_cron('cron_matutino')

        self.assertEqual(len(ejecutadas), 6, f'corrieron {ejecutadas}')
        self.assertIn('procesar_notificaciones_email', ejecutadas)
        self.assertIsInstance(fallo, CommandError)
        self.assertIn('cerrar_checkins_vencidos', str(fallo))
        self.assertIn('reintentar_evaluaciones_alertas', str(fallo))

class CronOperativoCommandTests(EspiaDeTareasCronMixin, TestCase):
    """Cron frecuente: vencimientos, motor recuperable y bandeja de correo."""

    def test_corre_las_tareas_en_orden(self):
        """Igual que en cron_matutino: se observa lo que corrió, no un mock."""
        ejecutadas = self.espiar_tareas([
            'cerrar_checkins_vencidos',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])

        fallo = self.correr_cron('cron_operativo')

        self.assertIsNone(fallo)
        self.assertEqual(ejecutadas, [
            'cerrar_checkins_vencidos',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])

    def test_corre_sin_error_con_bd_vacia(self):
        from django.core.management import call_command

        call_command('cron_operativo', verbosity=0)

    def test_fallo_de_la_primera_no_impide_entregar_las_alertas(self):
        """Un fallo operativo no puede costar los correos de alerta ALTA — D14.

        Las tres tareas de este cron están juntas porque el plan de Railway no
        daba para más servicios, no por una razón clínica: ninguna depende de
        otra. Si `cerrar_checkins_vencidos` falla de forma persistente, las
        alertas ALTA ya generadas tienen que entregarse igual — hoy no salen en
        todo el ciclo, y `cron_matutino` tampoco las rescata porque lleva la
        misma tarea por delante.
        """
        from django.core.management.base import CommandError

        ejecutadas = self.espiar_tareas(
            [
                'cerrar_checkins_vencidos',
                'reintentar_evaluaciones_alertas',
                'procesar_notificaciones_email',
            ],
            fallan=('cerrar_checkins_vencidos',),
        )

        fallo = self.correr_cron('cron_operativo')

        self.assertEqual(ejecutadas, [
            'cerrar_checkins_vencidos',
            'reintentar_evaluaciones_alertas',
            'procesar_notificaciones_email',
        ])
        self.assertIsInstance(fallo, CommandError)
        self.assertIn('cerrar_checkins_vencidos', str(fallo))

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
        with patch.dict(os.environ, entorno, clear=True), self.assertRaises(CommandError):
            call_command('crear_medico', verbosity=0)

        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('clave-original'))

    # --- D15: qué reescribe el comando en cada arranque, y qué no ---

    ENTORNO_MEDICO = {
        'DJANGO_MEDICO_USERNAME': 'doctora',
        'DJANGO_MEDICO_PASSWORD': 'clave-del-operador',
        'DJANGO_MEDICO_EMAIL': 'doctora@example.com',
    }

    def _arrancar(self, **extra):
        """Simula un arranque del servicio web: crear_medico con su entorno."""
        import os
        from unittest.mock import patch

        from django.core.management import call_command

        entorno = dict(self.ENTORNO_MEDICO, **extra)
        with patch.dict(os.environ, entorno, clear=True):
            call_command('crear_medico', verbosity=0)

    def test_no_reescribe_la_password_de_una_cuenta_existente(self):
        """La contraseña que el médico elige sobrevive al siguiente arranque."""
        self._arrancar()

        User = get_user_model()
        medica = User.objects.get(username='doctora')
        medica.set_password('la-que-eligio-ella')  # cambio desde el Admin
        medica.save()

        self._arrancar()  # despliegue o reinicio del servicio

        medica.refresh_from_db()
        self.assertTrue(medica.check_password('la-que-eligio-ella'))
        self.assertFalse(medica.check_password('clave-del-operador'))

    def test_reset_explicito_si_reescribe_la_password(self):
        """DJANGO_MEDICO_RESET=1 es la vía para rotar una contraseña filtrada."""
        self._arrancar()

        User = get_user_model()
        medica = User.objects.get(username='doctora')
        medica.set_password('la-que-eligio-ella')
        medica.save()

        self._arrancar(DJANGO_MEDICO_RESET='1')

        medica.refresh_from_db()
        self.assertTrue(medica.check_password('clave-del-operador'))

    def test_sin_variable_de_email_no_borra_el_correo(self):
        """El correo es el destinatario de las alertas: no se vacía solo."""
        self._arrancar()

        User = get_user_model()
        entorno_sin_email = {
            'DJANGO_MEDICO_USERNAME': 'doctora',
            'DJANGO_MEDICO_PASSWORD': 'clave-del-operador',
        }
        import os
        from unittest.mock import patch

        from django.core.management import call_command
        with patch.dict(os.environ, entorno_sin_email, clear=True):
            call_command('crear_medico', verbosity=0)

        medica = User.objects.get(username='doctora')
        self.assertEqual(medica.email, 'doctora@example.com')

    def test_los_permisos_si_vuelven_al_perfil_aprobado_en_cada_arranque(self):
        """Decisión deliberada de D15: el privilegio mínimo es declarativo.

        A diferencia de la contraseña, un permiso concedido a mano NO sobrevive
        al arranque. Esta prueba nace en verde a propósito — fija como requisito
        un comportamiento que hoy ya existe, para que nadie lo cambie sin
        decidirlo.
        """
        from django.contrib.auth.models import Permission

        self._arrancar()

        User = get_user_model()
        medica = User.objects.get(username='doctora')
        medica.user_permissions.add(
            Permission.objects.get(codename='delete_alerta')
        )
        self.assertTrue(medica.has_perm('signos_sintomas.delete_alerta'))

        self._arrancar()

        medica = User.objects.get(username='doctora')  # sin caché de permisos
        self.assertEqual(medica.user_permissions.count(), 0)
        self.assertFalse(medica.has_perm('signos_sintomas.delete_alerta'))
        self.assertEqual(
            list(medica.groups.values_list('name', flat=True)), ['Médicos'],
        )

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
            # D12: sin correo, el comando ahora rechaza la cuenta — un médico
            # que no recibe las alertas no puede ser responsable de nadie.
            email='medico_seed_prod@ejemplo.com',
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

        self.assertIn(f'pk={self.paciente.pk}', escrito)

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
