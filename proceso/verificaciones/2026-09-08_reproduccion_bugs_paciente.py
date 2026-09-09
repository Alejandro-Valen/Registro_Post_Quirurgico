"""Reproducción de los bugs que tocan al paciente — 08/09/2026.

QUÉ ES: ocho bloques que **ejecutan** los hallazgos que la auditoría del
07/09/2026 dejó solo trazados, y muestran en pantalla lo que de verdad pasa. La
regla del proyecto es que un hallazgo trazado es una hipótesis: hasta que no se
reproduce, no se toca nada.

QUÉ NO ES: la suite. Estos bloques **no fallan** cuando el bug existe — lo
imprimen. Están escritos para leerse, no para dar un semáforo. La guardia de
cada corrección vive en `signos_sintomas/tests/` y en `home/tests.py`, y que
esas pruebas puedan ponerse en rojo lo comprueba
`2026-09-08_verificacion_bugs_paciente.py`.

SE CORRE EN LOS DOS ESTADOS, y ahí está su valor. Antes de los arreglos imprime
los ocho bugs; después imprime el comportamiento corregido. **La segunda
corrida no es un trámite:** destapó que la palabra de auxilio, recién escrita,
seguía sin atrapar el caso que originó la decisión —"estoy sangrando mucho,
necesito ayuda"— porque comparaba el mensaje completo contra la lista. Las
pruebas de ese momento pasaban; volver a ejecutar esto fue lo que lo vio.

CÓMO SE CORRE, desde la raíz del repositorio (PowerShell):

    cd Registro_Post_Quirurgico
    $env:PYTHONPATH = "../proceso/verificaciones"
    ..\.venv\Scripts\python.exe manage.py test 2026-09-08_reproduccion_bugs_paciente -v 2 --noinput
    Remove-Item Env:PYTHONPATH

Corre contra una base de datos de PRUEBA desechable.

QUÉ SE REPRODUCE, y contra qué hallazgo:

    1. DB-02 / UX-B05  el parser de temperatura trunca en silencio
    2. DB-01           cero validadores de rango: el webhook revienta
    3. UX-B04 / BE-07  el paciente sin termómetro y el paciente sin dolor
                       no pueden avanzar
    4. UX-B01          no hay palabra de auxilio: una urgencia se guarda
                       como telemetría y el bot sigue preguntando
    5. BE-01           el turno de la tarde negado al que abandonó el de
                       la mañana
    6. UX-P01          el tablero dice "todo bajo control" con una ALTA
                       sin resolver en su propio indicador
    7. consentimiento  revocarlo no detiene la generación de datos
    8. SEC-03          el formulario público recoge datos de salud sin
                       autorización de habeas data
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from home.models import MensajeContacto
from signos_sintomas import bot
from signos_sintomas.models import (
    Alerta,
    CheckInProgramado,
    ConversacionWhatsApp,
    Paciente,
    RegistroDiario,
)


def titulo(numero, texto):
    print()
    print('=' * 78)
    print(f'{numero} · {texto}')
    print('=' * 78)


class ReproduccionBugsPaciente(TestCase):
    TELEFONO = '+573001112233'
    WA = 'whatsapp:+573001112233'

    def _medico(self):
        medico, _ = get_user_model().objects.get_or_create(
            username='medico_repro',
            defaults={'is_staff': True, 'email': 'medico_repro@ejemplo.com'},
        )
        return medico

    def _paciente(self, telefono=None, dias=5, consentimiento=True):
        return Paciente.objects.create(
            medico_responsable=self._medico(),
            nombre_completo='Paciente Reproducción',
            telefono_whatsapp=telefono or self.TELEFONO,
            fecha_cirugia=timezone.localdate() - timedelta(days=dias),
            consentimiento_informado=consentimiento,
        )

    def _checkin(self, paciente, orden=1, etiqueta=None, horas_atras=0):
        return CheckInProgramado.objects.create(
            paciente=paciente,
            fecha_dia=timezone.localdate(),
            orden=orden,
            etiqueta=etiqueta or CheckInProgramado.ETIQUETA_MANANA,
            hora_programada=timezone.now() - timedelta(hours=horas_atras),
        )

    # ------------------------------------------------------------------
    def test_1_parser_de_temperatura_trunca_en_silencio(self):
        titulo(1, 'DB-02 — el parser de temperatura trunca en silencio')

        print('Lo que el paciente teclea, y lo que el sistema entiende:')
        for entrada in ['37.9', '37,9', '379', '37 9', '375', '38']:
            valor = bot._parse_temperatura(entrada)
            alerta = 'SEPSIS/ALTA' if valor and valor >= Decimal('37.9') else 'ninguna'
            print(f'   "{entrada:<5}"  ->  {str(valor):<6}  ->  alerta: {alerta}')

        print()
        print('Y de punta a punta, con un paciente con 37,9 de fiebre real que')
        print('teclea sin separador (lo mas natural desde un celular):')
        paciente = self._paciente()
        self._checkin(paciente)
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '379')          # temperatura
        bot.procesar_mensaje(self.WA, '3')            # dolor
        bot.procesar_mensaje(self.WA, 'no')           # sin drenaje
        bot.procesar_mensaje(self.WA, 'si, 0')        # gases/nauseas
        bot.procesar_mensaje(self.WA, 'nada')         # hinchazon
        bot.procesar_mensaje(self.WA, '78')           # FC
        bot.procesar_mensaje(self.WA, '16')           # FR
        respuesta = bot.procesar_mensaje(self.WA, 'si')  # liquidos

        registro = RegistroDiario.objects.first()
        if registro is None:
            print('   no se creo ningun registro: el bot pidio la temperatura')
            print('   de nuevo en vez de inventarse un valor.')
        else:
            print(f'   guardado en la ficha : {registro.temperatura} °C')
            print(f'   alertas generadas    : {Alerta.objects.count()}')
            print(f'   el paciente recibe   : {respuesta[:60]}...')
        print()
        print('   ANTES (07-08/09/2026): guardaba 37,0, cero alertas y mensaje')
        print('   de cierre normal. Ni el paciente ni el medico podian notarlo,')
        print('   porque 37,0 es un valor perfectamente creible.')

    # ------------------------------------------------------------------
    def test_2_sin_validadores_de_rango_el_webhook_revienta(self):
        titulo(2, 'DB-01 — cero validadores de rango')

        print('El parser de gases/nauseas no tiene techo:')
        for entrada in ['si, 0', 'si, 3', 'si, 99999']:
            print(f'   "{entrada:<11}" -> {bot._parse_gases_nauseas(entrada)}')

        print()
        print('Y episodios_nauseas es un PositiveSmallIntegerField (techo 32767).')
        print('Guardar 99999 en la base:')
        paciente = self._paciente()
        try:
            with transaction.atomic():
                RegistroDiario.objects.create(
                    paciente=paciente,
                    temperatura=Decimal('37.0'),
                    dolor_eva=3,
                    tiene_drenaje=False,
                    presencia_gases=True,
                    episodios_nauseas=99999,
                )
            print('   se guardo sin protestar (la base no puso techo)')
        except Exception as exc:            # noqa: BLE001 — es lo que se observa
            print(f'   {type(exc).__name__}: {str(exc).splitlines()[0][:90]}')
            print()
            print('   En el webhook eso es un 500: el paciente escribe y no')
            print('   recibe NINGUNA respuesta. No sabe si su reporte entro.')

    # ------------------------------------------------------------------
    def test_3_el_paciente_sin_termometro_y_sin_dolor_no_pueden_avanzar(self):
        titulo(3, 'UX-B04 / BE-07 — no hay salida para quien no puede medir')

        print('Paciente sin termometro, intentando saltar la pregunta.')
        print('(cada intento arranca su propia conversacion, para que uno no')
        print(' arrastre el estado del anterior)')
        for i, intento in enumerate(['saltar', 'no tengo termometro',
                                     'no se', 'no puedo']):
            ConversacionWhatsApp.objects.all().delete()
            CheckInProgramado.objects.all().delete()
            Paciente.objects.all().delete()
            paciente = self._paciente()
            self._checkin(paciente)
            bot.procesar_mensaje(self.WA, 'hola')
            r = bot.procesar_mensaje(self.WA, intento)
            atascado = r == bot.MSG_REINTENTO_TEMPERATURA
            estado = 'ATASCADO (reintento)' if atascado else 'avanza -> ' + r[:38]
            print(f'   "{intento:<22}" -> {estado}')

        print()
        print('Y el paciente que hoy no tiene dolor:')
        ConversacionWhatsApp.objects.all().delete()
        CheckInProgramado.objects.all().delete()
        Paciente.objects.all().delete()
        paciente = self._paciente()
        self._checkin(paciente)
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        r = bot.procesar_mensaje(self.WA, '0')
        rechazado = r == bot.MSG_REINTENTO_DOLOR
        print(f'   responde "0" -> {"RECHAZADO (el rango era 1-10)" if rechazado else "aceptado"}')
        print()
        print('   ANTES: `saltar` funcionaba en pulso y respiracion pero NO en')
        print('   temperatura, y el "0" se rechazaba. El paciente no podia')
        print('   reportar NADA, y su turno vencido generaba una alerta')
        print('   SILENCIO: el sistema acusaba de no responder a quien lo')
        print('   estaba intentando.')

    # ------------------------------------------------------------------
    def test_4_no_hay_palabra_de_auxilio(self):
        titulo(4, 'UX-B01 — una urgencia se guarda como telemetria')

        paciente = self._paciente()
        self._checkin(paciente)
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        bot.procesar_mensaje(self.WA, '3')
        bot.procesar_mensaje(self.WA, 'no')
        bot.procesar_mensaje(self.WA, 'si, 0')

        grito = 'estoy sangrando mucho, necesito ayuda'
        respuesta = bot.procesar_mensaje(self.WA, grito)
        conv = ConversacionWhatsApp.objects.get()
        print(f'   El paciente escribe : "{grito}"')
        print(f'   El bot lo guarda como hinchazon = {conv.temp_hinchazon_abdominal!r}')
        print(f'   Y responde          : {respuesta[:60]}...')
        print(f'   Alertas AUXILIO     : {Alerta.objects.filter(tipo="AUXILIO").count()}')
        print()
        print('   ANTES: no existia ninguna palabra que sacara al paciente del')
        print('   cuestionario. En cualquier estado, un grito de auxilio se')
        print('   parseaba como el dato que tocaba en ese momento.')

    # ------------------------------------------------------------------
    def test_5_el_turno_de_la_tarde_negado(self):
        titulo(5, 'BE-01 — el turno de la tarde que el bot niega')

        paciente = self._paciente()
        manana = self._checkin(paciente, orden=1, horas_atras=11)
        self._checkin(paciente, orden=2,
                      etiqueta=CheckInProgramado.ETIQUETA_TARDE, horas_atras=1)

        print('Manana: el paciente empieza el reporte y lo abandona a mitad.')
        bot.procesar_mensaje(self.WA, 'hola')
        bot.procesar_mensaje(self.WA, '37.0')
        conv = ConversacionWhatsApp.objects.get()
        print(f'   estado de la conversacion: {conv.estado}')

        # Pasan las horas sin que responda. El cron NO cierra un turno con
        # conversacion viva y reciente (guarda deliberada), asi que hay que
        # envejecer la conversacion para reproducir el caso real: el paciente
        # dejo el movil y volvio por la tarde.
        ConversacionWhatsApp.objects.filter(pk=conv.pk).update(
            fecha_actualizacion=timezone.now() - timedelta(hours=11))

        print()
        print('Once horas despues, el cron cierra el turno de la manana:')
        salida = StringIO()
        call_command('cerrar_checkins_vencidos', stdout=salida, stderr=StringIO())
        manana.refresh_from_db()
        print(f'   turno manana -> {manana.estado}')

        print()
        print('El paciente vuelve por la tarde. Su turno de tarde esta PENDIENTE:')
        pendientes = CheckInProgramado.objects.filter(
            paciente=paciente, estado=CheckInProgramado.ESTADO_PENDIENTE)
        print(f'   turnos PENDIENTE ahora mismo: {pendientes.count()} '
              f'({[c.etiqueta for c in pendientes]})')
        r1 = bot.procesar_mensaje(self.WA, 'hola')
        print(f'   1er mensaje -> {r1[:70]}')
        print(f'   ¿es el "no tienes reporte pendiente"? -> {r1 == bot.MSG_SIN_CHECKIN}')
        r2 = bot.procesar_mensaje(self.WA, 'hola')
        print(f'   2do mensaje -> {r2[:70]}')
        print()
        print('   ANTES: al primer mensaje se le decia "no tienes un reporte')
        print('   pendiente" —FALSO— justo cuando volvia a colaborar, y solo lo')
        print('   recuperaba si insistia con un segundo mensaje.')
    # ------------------------------------------------------------------
    def test_6_el_tablero_dice_todo_bajo_control_con_una_alta(self):
        titulo(6, 'UX-P01 — el tablero se contradice a si mismo')

        from signos_sintomas.templatetags.panel_admin import panel_triage

        paciente = self._paciente()
        Alerta.objects.create(
            paciente=paciente, tipo='SILENCIO', severidad='ALTA',
            mensaje='Paciente sin responder 4 turnos consecutivos.',
            veces=1, fecha_ultima_deteccion=timezone.now(),
        )

        peticion = RequestFactory().get('/admin/')
        peticion.user = self._medico()
        ctx = panel_triage({'request': peticion})

        print(f'   Alertas ALTA sin resolver, segun su propio KPI : {ctx["kpi"]["alta"]}')
        print(f'   Filas en la lista de atencion                  : {len(ctx["atencion"])}')
        print()
        if ctx['kpi']['alta'] > 0 and not ctx['atencion']:
            print('   El medico ve el numero 1 en rojo arriba, y justo debajo')
            print('   la frase "Sin alertas pendientes. Todo bajo control."')
            print()
            print('   Causa: la lista excluye tipo=SILENCIO, pero el KPI no.')
            print('   Pasa SIEMPRE que la unica ALTA es de tipo SILENCIO — es')
            print('   decir, con el paciente que lleva dos dias sin responder.')

    # ------------------------------------------------------------------
    def test_7_revocar_el_consentimiento_no_detiene_la_generacion_de_datos(self):
        titulo(7, 'Consentimiento revocado: el sistema sigue generando datos')

        paciente = self._paciente(consentimiento=True)
        print('El medico revoca el consentimiento del paciente:')
        paciente.consentimiento_informado = False
        paciente.save()

        r = bot.procesar_mensaje(self.WA, 'hola')
        print(f'   el bot al paciente -> {r[:55]}...  (bien: lo frena)')

        print()
        print('Pero el cron sigue su curso:')
        salida = StringIO()
        call_command('crear_checkins_diarios', stdout=salida, stderr=StringIO())
        creados = CheckInProgramado.objects.filter(paciente=paciente).count()
        print(f'   check-ins creados para el ...  {creados}')

        CheckInProgramado.objects.filter(paciente=paciente).update(
            hora_programada=timezone.now() - timedelta(hours=11))
        call_command('cerrar_checkins_vencidos', stdout=salida, stderr=StringIO())
        silencios = Alerta.objects.filter(paciente=paciente, tipo='SILENCIO').count()
        no_respondidos = CheckInProgramado.objects.filter(
            paciente=paciente, estado=CheckInProgramado.ESTADO_NO_RESPONDIDO).count()
        print(f'   turnos marcados NO RESPONDIDO  {no_respondidos}')
        print(f'   alertas SILENCIO generadas     {silencios}')
        detenidos = CheckInProgramado.objects.filter(
            paciente=paciente,
            estado=CheckInProgramado.ESTADO_SIN_CONSENTIMIENTO).count()
        print(f'   turnos detenidos (D22)         {detenidos}')
        print()
        print('   ANTES: `crear_checkins_diarios` filtraba por activo=True y NO')
        print('   miraba el consentimiento. Se seguian produciendo registros')
        print('   clinicos y alertas sobre una persona que retiro su permiso, y')
        print('   el medico recibia correos por su silencio.')

    # ------------------------------------------------------------------
    def test_8_el_formulario_publico_recoge_salud_sin_autorizacion(self):
        titulo(8, 'SEC-03 — datos de salud sin autorizacion de habeas data')

        campos = {c.name for c in MensajeContacto._meta.get_fields()}
        print(f'   Campos de MensajeContacto: {sorted(campos)}')
        print()
        for nombre in ('autorizacion_datos', 'acepta_tratamiento', 'consentimiento'):
            print(f'   ¿existe {nombre}? -> {nombre in campos}')

        respuesta = self.client.post('/contacto/', {
            'nombre': 'Paciente Anonimo',
            'telefono': '+573001110000',
            'mensaje': 'Tengo fiebre de 39 y el drenaje salio con pus desde ayer.',
        }, follow=True)
        guardados = MensajeContacto.objects.count()
        print()
        print(f'   POST al formulario -> HTTP {respuesta.status_code}')
        print(f'   mensajes guardados -> {guardados}')
        if guardados:
            m = MensajeContacto.objects.first()
            print(f'   contenido guardado -> {m.mensaje[:60]}...')
        print()
        print('   ANTES: se almacenaba un dato sensible de salud sin casilla de')
        print('   autorizacion, sin finalidad declarada, sin responsable')
        print('   identificado y sin politica de retencion. El articulo 6 de la')
        print('   Ley 1581/2012 exige autorizacion EXPLICITA para datos')
        print('   sensibles. El formato de consentimiento del proyecto cubre al')
        print('   paciente ya inscrito, no a quien escribe por la web.')
