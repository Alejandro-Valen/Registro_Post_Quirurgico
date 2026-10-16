"""DB-04 — cada restricción de la base, vista fallar por su nombre.

La auditoría del 07/09/2026 encontró que 19 de las 25 restricciones de entonces
nunca se habían visto fallar. Al volver a contarlas el 15/10/2026 eran 31, y
**ninguna** aparecía por su nombre en las pruebas: las catorce que esperan un
`IntegrityError` no dicen cuál, así que pueden pasar porque saltó otra.

Aquí cada caso viola UNA restricción saltándose la validación de Django
—`update()` o `create()` directo— y exige que PostgreSQL la rechace **citando
su nombre**. Y `test_cada_restriccion_del_modelo_tiene_su_caso` cierra la
puerta: una restricción nueva sin caso aquí pone la suite en rojo.

Es la defensa de último recurso: si mañana un formulario, el bot o un comando
deja pasar un dato imposible, esto es lo que impide que llegue a la tabla.
"""

from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from ..models import (
    Alerta,
    CheckInProgramado,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RecepcionWebhookTwilio,
    RegistroDiario,
)
from .soporte import medico_de_pruebas


class RestriccionesDeLaBaseTests(TestCase):

    def setUp(self):
        self.medico = medico_de_pruebas('dr_restricciones')
        self.paciente = Paciente.objects.create(
            nombre_completo='Paciente Restricciones',
            telefono_whatsapp='+573009990001',
            fecha_cirugia=timezone.localdate() - timedelta(days=2),
            medico_responsable=self.medico,
        )
        self.registro = RegistroDiario.objects.create(
            paciente=self.paciente,
            temperatura=Decimal('36.8'), dolor_eva=0,
            aspecto_drenaje='sin_drenaje', presencia_gases=True,
            episodios_nauseas=0,
        )
        self.alerta = Alerta.objects.create(
            paciente=self.paciente, registro_origen=self.registro,
            tipo='SEPSIS', severidad='ALTA', mensaje='prueba', resuelta=False,
        )
        self.checkin = CheckInProgramado.objects.create(
            paciente=self.paciente, fecha_dia=timezone.localdate(), orden=1,
            etiqueta=CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now(),
        )
        # La señal ya la crea al nacer una alerta ALTA (uno a uno con la alerta).
        self.notificacion, _ = NotificacionAlerta.objects.get_or_create(alerta=self.alerta)
        self.webhook = RecepcionWebhookTwilio.objects.create(message_sid='SMrestricciones')

    # -- Atajos: una violación es un UPDATE de un campo sobre una fila válida --

    def _upd(self, objeto, **campos):
        return lambda: type(objeto).objects.filter(pk=objeto.pk).update(**campos)

    def _casos(self):
        p, r, a = self.paciente, self.registro, self.alerta
        c, n, w = self.checkin, self.notificacion, self.webhook
        return {
            # Paciente
            'paciente_tipo_cirugia_valido': self._upd(p, tipo_cirugia='inventada'),
            'paciente_activo_con_medico_responsable':
                self._upd(p, activo=True, medico_responsable=None),
            # RegistroDiario
            'registrodiario_aspecto_drenaje_valido': self._upd(r, aspecto_drenaje='verde'),
            'registrodiario_cantidad_drenaje_valido': self._upd(r, cantidad_drenaje='litros'),
            'registrodiario_hinchazon_abdominal_valido': self._upd(r, hinchazon_abdominal='poco'),
            'registro_estado_evaluacion_valido': self._upd(r, estado_evaluacion_alertas='OTRO'),
            'registro_temperatura_en_rango': self._upd(r, temperatura=Decimal('45.1')),
            'registro_dolor_eva_en_rango': self._upd(r, dolor_eva=11),
            'registro_episodios_nauseas_en_rango': self._upd(r, episodios_nauseas=21),
            'registro_frecuencia_cardiaca_en_rango': self._upd(r, frecuencia_cardiaca=251),
            'registro_frecuencia_respiratoria_en_rango': self._upd(r, frecuencia_respiratoria=61),
            'registro_volumen_drenaje_en_rango': self._upd(r, volumen_drenaje_ml=5001),
            # Alerta
            'alerta_tipo_valido': self._upd(a, tipo='GRIPA'),
            'alerta_severidad_valida': self._upd(a, severidad='CRITICA'),
            'alerta_veces_positivo': self._upd(a, veces=0),
            'alerta_motivo_resolucion_valido': self._upd(a, motivo_resolucion='PORQUESI'),
            'alerta_resuelta_con_cierre': self._upd(a, resuelta=True),
            'alerta_otro_con_detalle': self._upd(
                a, motivo_resolucion='OTRO', motivo_resolucion_detalle=''),
            'unique_alerta_abierta_paciente_tipo': lambda: Alerta.objects.create(
                paciente=p, registro_origen=r, tipo='SEPSIS', severidad='MEDIA',
                mensaje='duplicada', resuelta=False),
            # NotificacionAlerta
            'notificacion_alerta_estado_valido': self._upd(n, estado='PERDIDA'),
            'notificacion_alerta_envio_coherente': self._upd(n, estado='ENVIADA', fecha_envio=None),
            # DeteccionAlerta
            'deteccion_fuente_unica': lambda: DeteccionAlerta.objects.create(
                alerta=a, registro=r, checkin=c, severidad_detectada='ALTA',
                mensaje_detectado='dos fuentes'),
            'deteccion_severidad_valida': lambda: DeteccionAlerta.objects.create(
                alerta=a, registro=r, severidad_detectada='CRITICA',
                mensaje_detectado='severidad inventada'),
            'unique_det_alerta_registro': lambda: [DeteccionAlerta.objects.create(
                alerta=a, registro=r, severidad_detectada='ALTA',
                mensaje_detectado='repetida') for _ in range(2)],
            'unique_det_alerta_checkin': lambda: [DeteccionAlerta.objects.create(
                alerta=a, checkin=c, severidad_detectada='ALTA',
                mensaje_detectado='repetida') for _ in range(2)],
            # CheckInProgramado
            'unique_checkin_paciente_dia_orden': lambda: CheckInProgramado.objects.create(
                paciente=p, fecha_dia=c.fecha_dia, orden=1,
                etiqueta=CheckInProgramado.ETIQUETA_MANANA, hora_programada=timezone.now()),
            'checkin_estado_valido': self._upd(c, estado='OLVIDADO'),
            'checkin_etiqueta_valida': self._upd(c, etiqueta='NOCHE'),
            'checkin_turno_coherente': self._upd(c, orden=2),
            # RecepcionWebhookTwilio
            'webhook_twilio_estado_valido': self._upd(w, estado='PERDIDO'),
            'webhook_twilio_intentos_positivo': self._upd(w, intentos=0),
        }

    # Restricciones que no pueden fallar SOLAS, porque otra las cubre: cualquier
    # estado inventado viola también la coherencia de envío, y cualquier
    # etiqueta inventada, la coherencia del turno. PostgreSQL reporta la que
    # evalúa primero, así que sin esto la prueba pasaría o fallaría por el orden.
    # Para verlas caer por sí mismas se quita la que las cubre DENTRO de la
    # transacción de la prueba: en PostgreSQL el DDL es transaccional y se
    # deshace solo al salir.
    CUBIERTAS_POR = {
        'notificacion_alerta_estado_valido': (NotificacionAlerta, 'notificacion_alerta_envio_coherente'),
        'checkin_etiqueta_valida': (CheckInProgramado, 'checkin_turno_coherente'),
    }

    def test_cada_restriccion_rechaza_su_violacion_por_su_nombre(self):
        for nombre, violar in self._casos().items():
            with self.subTest(restriccion=nombre):
                with self.assertRaises(IntegrityError) as error, transaction.atomic():
                    if nombre in self.CUBIERTAS_POR:
                        modelo, cubridora = self.CUBIERTAS_POR[nombre]
                        with connection.cursor() as cursor:
                            # Las llaves foráneas de Django son DEFERRABLE y las
                            # filas de setUp dejan sus comprobaciones pendientes;
                            # con ellas pendientes no se puede alterar la tabla.
                            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                            cursor.execute(
                                f'ALTER TABLE "{modelo._meta.db_table}" '
                                f'DROP CONSTRAINT "{cubridora}"')
                    violar()
                self.assertIn(nombre, str(error.exception))

    def test_cada_restriccion_del_modelo_tiene_su_caso(self):
        """Una restricción nueva sin caso aquí es una restricción que nadie ha
        visto fallar: eso es justo lo que encontró DB-04."""
        declaradas = {
            restriccion.name
            for modelo in apps.get_app_config('signos_sintomas').get_models()
            for restriccion in modelo._meta.constraints
        }
        self.assertEqual(declaradas, set(self._casos()))

    def test_los_valores_del_borde_si_entran(self):
        """La otra dirección: los límites de los rangos son válidos. Una
        restricción que rechazara 45.0 °C o EVA 10 borraría datos reales."""
        RegistroDiario.objects.filter(pk=self.registro.pk).update(
            temperatura=Decimal('45.0'), dolor_eva=10, episodios_nauseas=20,
            frecuencia_cardiaca=250, frecuencia_respiratoria=60,
            volumen_drenaje_ml=5000,
        )
        RegistroDiario.objects.filter(pk=self.registro.pk).update(
            temperatura=Decimal('30.0'), dolor_eva=0, episodios_nauseas=0,
            frecuencia_cardiaca=30, frecuencia_respiratoria=5,
        )
        Paciente.objects.filter(pk=self.paciente.pk).update(
            activo=False, medico_responsable=None)


class IndicesDeLaBaseTests(TestCase):
    """DB-09: los dos comandos del cron buscan, en TODOS los pacientes, los
    turnos PENDIENTE cuya hora ya pasó (`cerrar_checkins_vencidos`,
    `enviar_recordatorios`). Sin índice, cada corrida recorre la tabla entera,
    que crece dos filas por paciente y día y nunca se purga.
    """

    def test_turnos_pendientes_indexados_por_hora(self):
        with connection.cursor() as cursor:
            restricciones = connection.introspection.get_constraints(
                cursor, CheckInProgramado._meta.db_table)
        indice = restricciones.get('checkin_pendiente_por_hora')
        self.assertIsNotNone(indice, 'falta el índice de turnos pendientes')
        self.assertTrue(indice['index'])
        self.assertEqual(indice['columns'], ['hora_programada'])
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT indexdef FROM pg_indexes WHERE indexname = %s',
                ['checkin_pendiente_por_hora'])
            definicion = cursor.fetchone()[0]
        # Parcial: solo los pendientes. Los cerrados son la inmensa mayoría y
        # ninguna consulta caliente los busca por hora.
        self.assertIn("WHERE ((estado)::text = 'PENDIENTE'", definicion)
