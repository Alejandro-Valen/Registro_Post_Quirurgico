from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from .models import Alerta, DeteccionAlerta, RegistroDiario

TEMPERATURA_ALTA = Decimal('37.9')           # Outersterp 2025
TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.5')
DIAS_SUBFEBRICULA_PERSISTENTE = 2

# Escalera de severidad por aspecto de drenaje (decisión Arquitectos jun 2026)
# Base: Lee 2022, Gignoux 2018, Coeckelberghs 2025
DRENAJES_ALTA  = ('purulento', 'fecaloide')
DRENAJES_MEDIA = ('turbio', 'hematico')
DRENAJES_BAJA  = ('seroso',)

NAUSEAS_BAJA_MIN = 1
NAUSEAS_MEDIA_MIN = 3
NAUSEAS_ALTA_MIN = 5
DIAS_NAUSEAS_MEDIA = 2
DIAS_NAUSEAS_ALTA  = 4
DIAS_SIN_GASES_BAJA  = 1
DIAS_SIN_GASES_MEDIA = 2
DIAS_SIN_GASES_ALTA  = 3

DIAS_SIN_TOLERAR_LIQUIDOS_MEDIA = 1
DIAS_SIN_TOLERAR_LIQUIDOS_ALTA  = 2

HINCHAZON_NIVELES = {'nada': 0, 'algo': 1, 'mucho': 2}
DIAS_HINCHAZON_MUCHO_ALTA = 4
DIAS_HINCHAZON_MEDIA = 2  # el empeoramiento debe mantenerse > 2 días

FC_BAJA_MIN  = 101  # 101-109: taquicardia leve
FC_MEDIA_MIN = 110  # 110-149: intervención (CREWS 2022, Cleveland NCT04574908)
FC_ALTA_MIN  = 150  # >=150: escalamiento inmediato (protocolos hospitalarios)

# Escalera de dolor (EVA) por ventana de dia_postoperatorio.
# Decisión Arquitecto, jun 2026. Base: Delaney 2008, Lee 2022,
# Outersterp 2025, Coeckelberghs 2025.
# La primera ventana cubre POD 0-2: dia_postoperatorio=0 no ocurre en
# operación normal (cirugías de 9+ horas, alta siempre al día siguiente)
# pero la condición <=2 lo cubre de forma defensiva — decisión 0-⑤ Sprint 4.
VENTANAS_DOLOR = [
    # (dia_postoperatorio_max_inclusive, eva_baja_min, eva_media_min, eva_alta_min)
    (2,    5, 7, 9),   # POD 0-2 (defensivo: 0 no ocurre en práctica)
    (5,    4, 6, 8),   # POD 3-5
    (None, 3, 5, 7),   # POD 6+ (None = sin límite superior)
]
DOLOR_DIAS_TENDENCIA = 2
DOLOR_DELTA_TENDENCIA = 3

# Orden de severidad usado por múltiples reglas y por la agrupación de alertas.
ORDEN_SEVERIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3, None: 0}


def _obtener_o_crear_alerta_abierta(
    paciente,
    tipo,
    severidad,
    mensaje,
    registro_origen=None,
    fecha_deteccion=None,
):
    abierta = (
        Alerta.objects.select_for_update()
        .filter(paciente=paciente, tipo=tipo, resuelta=False)
        .order_by('-fecha_alerta')
        .first()
    )
    if abierta is not None:
        return abierta, False

    try:
        # El savepoint permite recuperarse si otro worker crea la misma alerta
        # entre el SELECT anterior y este INSERT.
        with transaction.atomic():
            alerta = Alerta.objects.create(
                paciente=paciente,
                registro_origen=registro_origen,
                tipo=tipo,
                severidad=severidad,
                mensaje=mensaje,
                veces=1,
                fecha_ultima_deteccion=fecha_deteccion or timezone.now(),
            )
        return alerta, True
    except IntegrityError as error:
        try:
            alerta = (
                Alerta.objects.select_for_update()
                .get(paciente=paciente, tipo=tipo, resuelta=False)
            )
        except Alerta.DoesNotExist as exc:
            # Se encadenan las dos: el IntegrityError es la causa real, y que
            # además no aparezca la alerta que lo provocó es información que
            # conviene conservar para diagnosticar la carrera.
            raise error from exc
        return alerta, False


SEPARADOR_SIGNOS = '\n· '


def _acumular_signo(texto_actual, mensaje, encabeza):
    """Suma un signo concurrente al detalle sin duplicarlo.

    Un mismo check-in puede disparar varias reglas del mismo tipo — solo ocurre
    con ILEO_PARALITICO, que producen las Reglas 3 (gases), 4 (náuseas) y 7
    (hinchazón). Antes se conservaba únicamente el mensaje más grave, así que el
    médico veía un signo aislado cuando el paciente tenía el cuadro completo.

    Idempotente: `reintentar_evaluaciones_alertas` vuelve a correr las ocho
    reglas sobre un registro PENDIENTE/ERROR, y el texto no debe crecer en cada
    reintento.
    """
    partes = [p for p in texto_actual.split(SEPARADOR_SIGNOS) if p]
    if mensaje in partes:
        return texto_actual
    if encabeza:
        partes.insert(0, mensaje)
    else:
        partes.append(mensaje)
    return SEPARADOR_SIGNOS.join(partes)


def _registrar_detalle_deteccion(
    alerta,
    severidad,
    mensaje,
    fecha_deteccion,
    *,
    registro=None,
    checkin=None,
):
    """Crea una evidencia idempotente por fuente y conserva su máximo nivel.

    La severidad de la detección es la máxima observada; el mensaje acumula
    todos los signos concurrentes, encabezado por el más grave (decisión D5).
    """
    if (registro is None) == (checkin is None):
        raise ValueError('La detección requiere exactamente una fuente.')

    fuente = {'registro': registro} if registro is not None else {'checkin': checkin}
    detalle, creado = DeteccionAlerta.objects.get_or_create(
        alerta=alerta,
        **fuente,
        defaults={
            'severidad_detectada': severidad,
            'mensaje_detectado': mensaje,
            'fecha_deteccion': fecha_deteccion,
        },
    )
    if creado:
        return detalle, creado

    es_mas_grave = (
        ORDEN_SEVERIDAD[severidad]
        > ORDEN_SEVERIDAD[detalle.severidad_detectada]
    )
    texto = _acumular_signo(detalle.mensaje_detectado, mensaje, es_mas_grave)

    campos = []
    if texto != detalle.mensaje_detectado:
        detalle.mensaje_detectado = texto
        campos.append('mensaje_detectado')
    if es_mas_grave:
        detalle.severidad_detectada = severidad
        campos.append('severidad_detectada')
    if campos:
        detalle.save(update_fields=campos)
    return detalle, creado


@transaction.atomic
def _registrar_alerta(registro, tipo, severidad, mensaje):
    """Registra una detección clínica como Alerta, AGRUPANDO POR PROBLEMA
    (decisión Arquitecto, 10/07/2026):

    - Si el paciente ya tiene una alerta ABIERTA (sin resolver) del mismo
      `tipo`, la ACTUALIZA en vez de crear otra: sube el contador `veces`
      (cuántos check-ins la han detectado), la `fecha_ultima_deteccion`, y la
      severidad si esta es MAYOR (la severidad = la máxima alcanzada mientras
      está abierta; nunca baja sola).
    - Si no hay ninguna abierta, crea una nueva (`veces`=1).
    - Si el médico ya resolvió la alerta y el problema reaparece en un check-in
      posterior, se crea una NUEVA (es un evento nuevo).

    Dedup dentro del MISMO check-in: si la alerta abierta ya fue tocada por
    este mismo `registro` (otra regla del mismo check-in la registró), no se
    vuelve a contar — solo se sube la severidad si aplica.

    Reemplaza a la antigua deduplicación por día (Opción A+): ahora hay a lo
    sumo UNA alerta abierta por (paciente, tipo). NO cambia ninguna regla ni
    umbral clínico — solo cómo se almacenan las detecciones."""
    paciente = registro.paciente
    fecha_deteccion = registro.fecha_registro
    abierta, creada = _obtener_o_crear_alerta_abierta(
        paciente,
        tipo,
        severidad,
        mensaje,
        registro_origen=registro,
        fecha_deteccion=fecha_deteccion,
    )
    _, detalle_creado = _registrar_detalle_deteccion(
        abierta,
        severidad,
        mensaje,
        fecha_deteccion,
        registro=registro,
    )
    if creada:
        return abierta

    primera_vez_este_checkin = (
        detalle_creado and abierta.registro_origen_id != registro.id
    )
    orden_previa = ORDEN_SEVERIDAD[abierta.severidad]

    # Severidad = máxima alcanzada; el mensaje refleja ese nivel más grave.
    if ORDEN_SEVERIDAD[severidad] > orden_previa:
        abierta.severidad = severidad
        abierta.mensaje = mensaje

    # registro_origen marca el último check-in que tocó la alerta; se actualiza
    # una vez por check-in (así dos reglas del mismo check-in no cuentan doble).
    if primera_vez_este_checkin:
        abierta.veces += 1
        abierta.fecha_ultima_deteccion = fecha_deteccion
        abierta.registro_origen = registro

    # Bandera para signals.py: el correo de alerta ALTA se envía solo cuando la
    # alerta ALCANZA ALTA (creación ALTA o escalada a ALTA), no en cada
    # recurrencia. Aquí marcamos la escalada; la creación la detecta `created`.
    abierta._escalo_a_alta = (
        abierta.severidad == 'ALTA' and orden_previa < ORDEN_SEVERIDAD['ALTA']
    )
    abierta.save()
    return abierta


@transaction.atomic
def registrar_alerta_silencio(checkin, severidad, mensaje):
    """Agrupa una detección de silencio sin crear alertas abiertas duplicadas."""
    fecha_deteccion = timezone.now()
    abierta, creada = _obtener_o_crear_alerta_abierta(
        checkin.paciente,
        'SILENCIO',
        severidad,
        mensaje,
        fecha_deteccion=fecha_deteccion,
    )
    _, detalle_creado = _registrar_detalle_deteccion(
        abierta,
        severidad,
        mensaje,
        fecha_deteccion,
        checkin=checkin,
    )
    if creada:
        return abierta

    orden_previa = ORDEN_SEVERIDAD[abierta.severidad]
    if ORDEN_SEVERIDAD[severidad] > orden_previa:
        abierta.severidad = severidad
        abierta.mensaje = mensaje

    if detalle_creado:
        abierta.veces += 1
        abierta.fecha_ultima_deteccion = fecha_deteccion
    abierta._escalo_a_alta = (
        abierta.severidad == 'ALTA'
        and orden_previa < ORDEN_SEVERIDAD['ALTA']
    )
    abierta.save()
    return abierta


def registrar_alerta_auxilio(paciente, mensaje):
    """Registra la petición de auxilio de un paciente como alerta ALTA (D21).

    **No la produce el motor de reglas.** Las otras siete alertas son
    conclusiones sobre telemetría; esta es una petición de socorro de la
    persona, sin clasificación clínica detrás. Por eso tiene tipo propio: si se
    metiera en SEPSIS o en DOLOR_AGUDO, el sistema estaría diagnosticando —lo
    que este proyecto promete no hacer— y además ensuciaría las estadísticas de
    esos tipos.

    **Sin `DeteccionAlerta`, a diferencia de las demás.** Una detección exige
    exactamente una fuente —un `RegistroDiario` o un `CheckInProgramado`— y aquí
    no hay ninguna de las dos: el paciente escribió una palabra, en cualquier
    momento, fuera del cuestionario o a mitad de él. Inventarle una fuente sería
    falsear la evidencia. El contador `veces` sí se lleva, para que dos gritos
    de auxilio no se vean como uno.

    Severidad siempre ALTA: no hay grados en pedir socorro.
    """
    fecha_deteccion = timezone.now()
    alerta, creada = _obtener_o_crear_alerta_abierta(
        paciente,
        'AUXILIO',
        'ALTA',
        mensaje,
        fecha_deteccion=fecha_deteccion,
    )
    if creada:
        alerta._escalo_a_alta = False   # ya nació ALTA: el post_save la notifica
        return alerta

    alerta.veces += 1
    alerta.fecha_ultima_deteccion = fecha_deteccion
    alerta.mensaje = mensaje
    # Una alerta de auxilio ya abierta sigue siendo ALTA; no re-escala, así que
    # no se vuelve a notificar por correo. La cuenta de `veces` es lo que le
    # dice al médico que el paciente insistió.
    alerta._escalo_a_alta = False
    alerta.save()
    return alerta


def _severidad_dolor_por_ventana(dia_postoperatorio, dolor_eva):
    """Devuelve 'ALTA', 'MEDIA', 'BAJA' o None según la ventana de
    dia_postoperatorio y el valor de dolor_eva."""
    for dia_max, eva_baja, eva_media, eva_alta in VENTANAS_DOLOR:
        if dia_max is None or dia_postoperatorio <= dia_max:
            if dolor_eva >= eva_alta:
                return 'ALTA'
            if dolor_eva >= eva_media:
                return 'MEDIA'
            if dolor_eva >= eva_baja:
                return 'BAJA'
            return None
    return None


def _nivel_hinchazon_dia(paciente, dia):
    """Nivel numérico máximo de hinchazón reportado por el paciente en
    un día calendario. None si no hay dato ese día."""
    registros = RegistroDiario.objects.filter(
        paciente=paciente,
        fecha_registro__date=dia,
        hinchazon_abdominal__isnull=False,
    )
    niveles = [
        HINCHAZON_NIVELES[r.hinchazon_abdominal]
        for r in registros
        if r.hinchazon_abdominal in HINCHAZON_NIVELES
    ]
    return max(niveles) if niveles else None


def _evaluar_temperatura(registro, fecha_referencia):
    """Regla 1: Temperatura — escalera por días calendario.
    Decisión Arquitecto, jun 2026. Base: Outersterp 2025 (>37.9°C umbral
    de notificación en monitoreo domiciliario, no solo criterio de alta
    hospitalaria como en otros estudios).

    Sin dato no se evalua (decision D20): desde el 08/09/2026 el paciente
    que no tiene termometro puede saltar la pregunta y reportar las otras
    nueve variables. Un dia sin temperatura es un desconocido genuino,
    igual que un dia sin reporte para las reglas de dias consecutivos (D8),
    y el tratamiento es el mismo que la Regla 8 le da a una frecuencia
    cardiaca ausente: no alertar en vez de inventar un hecho clinico."""
    if registro.temperatura is None:
        return []

    if registro.temperatura >= TEMPERATURA_ALTA:
        return [_registrar_alerta(
            registro, 'SEPSIS', 'ALTA',
            f"Temperatura de {registro.temperatura}°C detectada. "
            "Posible cuadro de sepsis — ir a urgencias."
        )]

    if TEMPERATURA_SUBFEBRICULA_MIN <= registro.temperatura < TEMPERATURA_ALTA:
        dias_con_subfebricula = set()
        for offset in range(DIAS_SUBFEBRICULA_PERSISTENTE):
            dia = fecha_referencia - timedelta(days=offset)
            existe = RegistroDiario.objects.filter(
                paciente=registro.paciente,
                fecha_registro__date=dia,
                temperatura__gte=TEMPERATURA_SUBFEBRICULA_MIN,
                temperatura__lt=TEMPERATURA_ALTA,
            ).exists()
            if existe:
                dias_con_subfebricula.add(dia)
        if len(dias_con_subfebricula) >= DIAS_SUBFEBRICULA_PERSISTENTE:
            return [_registrar_alerta(
                registro, 'SEPSIS', 'MEDIA',
                f"Subfebrícula ({registro.temperatura}°C) persistente "
                f"por {DIAS_SUBFEBRICULA_PERSISTENTE} días consecutivos. "
                "Llamar al médico."
            )]

    # < 37.5°C o subfebrícula de un solo día: sin alerta.
    return []


def _evaluar_drenaje(registro, fecha_referencia):
    """Regla 2: Drenaje anormal — solo evalúa si el paciente tiene drenaje activo.
    tiene_drenaje=None → registro anterior a esta versión, no se evalúa.
    Escalera: seroso→BAJA, turbio/hemático→MEDIA, purulento/fecaloide→ALTA."""
    if registro.tiene_drenaje is not True:
        return []

    if registro.aspecto_drenaje in DRENAJES_ALTA:
        return [_registrar_alerta(
            registro, 'FUGA_ANASTOMOTICA', 'ALTA',
            f"Drenaje {registro.aspecto_drenaje} detectado. "
            "Posible fuga anastomótica — ir a urgencias."
        )]
    if registro.aspecto_drenaje in DRENAJES_MEDIA:
        return [_registrar_alerta(
            registro, 'FUGA_ANASTOMOTICA', 'MEDIA',
            f"Drenaje {registro.aspecto_drenaje} detectado. "
            "Requiere seguimiento — llamar al médico."
        )]
    if registro.aspecto_drenaje in DRENAJES_BAJA:
        return [_registrar_alerta(
            registro, 'FUGA_ANASTOMOTICA', 'BAJA',
            "Drenaje seroso detectado. "
            "Aspecto dentro de lo esperado — monitorear."
        )]
    return []


def _evaluar_gases(registro, fecha_referencia):
    """Regla 3: Ausencia de gases — escalera por días calendario consecutivos.
    Decisión Arquitecto, jun 2026. El paciente ya demostró función
    intestinal al momento del alta (criterio ERAS estándar); dejar de
    tener gases en casa es una regresión, no un estado normal. Un día
    cuenta como "con gases" si hubo al menos un registro positivo en
    cualquier check-in de ese día."""
    dias_sin_gases_consecutivos = 0
    dia_revisado = fecha_referencia
    while True:
        hubo_gases = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
            presencia_gases=True,
        ).exists()
        existe_registro = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
        ).exists()
        if not existe_registro:
            break
        if hubo_gases:
            break
        dias_sin_gases_consecutivos += 1
        if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_ALTA:
            break
        dia_revisado = dia_revisado - timedelta(days=1)

    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_ALTA:
        return [_registrar_alerta(
            registro, 'ILEO_PARALITICO', 'ALTA',
            f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
            "consecutivos. Posible íleo paralítico severo — ir a urgencias."
        )]
    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_MEDIA:
        return [_registrar_alerta(
            registro, 'ILEO_PARALITICO', 'MEDIA',
            f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
            "consecutivos. Llamar al médico."
        )]
    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_BAJA:
        return [_registrar_alerta(
            registro, 'ILEO_PARALITICO', 'BAJA',
            f"Paciente sin gases por {dias_sin_gases_consecutivos} día(s). "
            "Monitorear."
        )]
    return []


def _evaluar_nauseas(registro, fecha_referencia):
    """Regla 4: Náuseas/vómito — suma diaria + persistencia entre días.
    Decisión Arquitecto, jun 2026. Suma: Lee 2022 y Outersterp 2025
    tratan cualquier episodio como señal (no se espera acumulación de
    3+ como la regla anterior). Persistencia 4+ días: Delaney 2008
    (íleo en 27.8% de pacientes con estancia 4+ días vs 11% general) —
    mismo orden de magnitud que el umbral ALTA de la Regla 3 (gases)."""
    total_episodios_hoy = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date=fecha_referencia,
    ).aggregate(total=models.Sum('episodios_nauseas'))['total'] or 0

    severidad_por_suma = None
    if total_episodios_hoy >= NAUSEAS_ALTA_MIN:
        severidad_por_suma = 'ALTA'
    elif total_episodios_hoy >= NAUSEAS_MEDIA_MIN:
        severidad_por_suma = 'MEDIA'
    elif total_episodios_hoy >= NAUSEAS_BAJA_MIN:
        severidad_por_suma = 'BAJA'

    dias_con_nauseas_consecutivos = 0
    dia_revisado = fecha_referencia
    while True:
        hubo_nauseas = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
            episodios_nauseas__gte=1,
        ).exists()
        if not hubo_nauseas:
            break
        dias_con_nauseas_consecutivos += 1
        if dias_con_nauseas_consecutivos >= DIAS_NAUSEAS_ALTA:
            break
        dia_revisado = dia_revisado - timedelta(days=1)

    severidad_por_persistencia = None
    if dias_con_nauseas_consecutivos >= DIAS_NAUSEAS_ALTA:
        severidad_por_persistencia = 'ALTA'
    elif dias_con_nauseas_consecutivos >= DIAS_NAUSEAS_MEDIA:
        severidad_por_persistencia = 'MEDIA'

    severidad_final = max(
        severidad_por_suma, severidad_por_persistencia,
        key=lambda s: ORDEN_SEVERIDAD[s]
    )

    if severidad_final is None:
        return []

    mensaje = f"{total_episodios_hoy} episodios de náuseas/vómito hoy."
    gano_por_persistencia = (
        ORDEN_SEVERIDAD[severidad_por_persistencia]
        > ORDEN_SEVERIDAD[severidad_por_suma]
    )
    if gano_por_persistencia and severidad_por_persistencia == 'ALTA':
        mensaje += (
            f" Náuseas persistentes por {dias_con_nauseas_consecutivos} "
            "días consecutivos. Posible complicación progresiva — "
            "ir a urgencias."
        )
    elif gano_por_persistencia and severidad_por_persistencia == 'MEDIA':
        mensaje += (
            f" Náuseas persistentes por {dias_con_nauseas_consecutivos} "
            "días consecutivos. Llamar al médico."
        )
    return [_registrar_alerta(
        registro, 'ILEO_PARALITICO', severidad_final, mensaje
    )]


def _evaluar_dolor(registro, fecha_referencia):
    """Regla 5: Dolor (DOLOR_AGUDO) — escalera por ventana de
    dia_postoperatorio + capa de tendencia alcista.
    Decisión Arquitecto, jun 2026. La tolerancia de dolor esperado baja
    con el tiempo (Coeckelberghs 2025); EVA>=4 replicado en 3 estudios
    independientes (Delaney 2008, Lee 2022, Outersterp 2025) como
    umbral de atención. La tendencia captura subidas que la tabla por
    sí sola no vería (ej. EVA 5 en POD5 es "BAJA" por tabla, pero si
    ayer era EVA 2, el salto de 3 puntos es señal real)."""
    severidad_por_tabla = _severidad_dolor_por_ventana(
        registro.dia_postoperatorio, registro.dolor_eva
    )

    promedio_reciente = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date__gte=fecha_referencia - timedelta(days=DOLOR_DIAS_TENDENCIA - 1),
        fecha_registro__date__lte=fecha_referencia,
    ).aggregate(promedio=models.Avg('dolor_eva'))['promedio']

    promedio_anterior = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date__gte=fecha_referencia - timedelta(days=(DOLOR_DIAS_TENDENCIA * 2) - 1),
        fecha_registro__date__lt=fecha_referencia - timedelta(days=DOLOR_DIAS_TENDENCIA - 1),
    ).aggregate(promedio=models.Avg('dolor_eva'))['promedio']

    severidad_por_tendencia = None
    delta_tendencia = None
    if promedio_reciente is not None and promedio_anterior is not None:
        delta_tendencia = float(promedio_reciente) - float(promedio_anterior)
        if delta_tendencia >= DOLOR_DELTA_TENDENCIA:
            severidad_base = severidad_por_tabla or 'BAJA'
            siguiente_nivel = {'BAJA': 'MEDIA', 'MEDIA': 'ALTA', 'ALTA': 'ALTA'}
            severidad_por_tendencia = siguiente_nivel[severidad_base]

    severidad_final = max(
        severidad_por_tabla, severidad_por_tendencia,
        key=lambda s: ORDEN_SEVERIDAD[s]
    )

    if severidad_final is None:
        return []

    mensaje = (
        f"Dolor EVA {registro.dolor_eva}/10 en día postoperatorio "
        f"{registro.dia_postoperatorio}."
    )
    if severidad_por_tendencia is not None and (
        ORDEN_SEVERIDAD[severidad_por_tendencia]
        > ORDEN_SEVERIDAD[severidad_por_tabla]
    ):
        mensaje += (
            f" Tendencia al alza detectada (delta {delta_tendencia:.1f} "
            "puntos vs. periodo anterior)."
        )
    return [_registrar_alerta(
        registro, 'DOLOR_AGUDO', severidad_final, mensaje
    )]


def _evaluar_tolerancia_liquidos(registro, fecha_referencia):
    """Regla 6: Intolerancia a líquidos — escalera por días calendario.
    Decisión Arquitecto, jun 2026. Base: tolerancia oral es criterio de
    alta en todos los ERAS revisados; deshidratación = causa #1 de
    readmisión (Lawrence 2013). Arranca en MEDIA (no BAJA) porque no
    retener líquidos ni un día ya es señal directa hacia deshidratación.
    Un día cuenta como "toleró" si hubo al menos un registro positivo.
    Solo evalúa si el registro actual tiene el dato capturado."""
    if registro.tolero_liquidos is not False:
        return []

    dias_sin_tolerar = 0
    dia_revisado = fecha_referencia
    while True:
        toleraba = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
            tolero_liquidos=True,
        ).exists()
        existe_registro = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
        ).exists()
        if not existe_registro:
            break
        if toleraba:
            break
        dias_sin_tolerar += 1
        if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_ALTA:
            break
        dia_revisado = dia_revisado - timedelta(days=1)

    if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_ALTA:
        return [_registrar_alerta(
            registro, 'INTOLERANCIA_ORAL', 'ALTA',
            f"Paciente sin tolerar líquidos por {dias_sin_tolerar} "
            "días consecutivos. Riesgo de deshidratación — ir a "
            "urgencias."
        )]
    if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_MEDIA:
        return [_registrar_alerta(
            registro, 'INTOLERANCIA_ORAL', 'MEDIA',
            "Paciente no toleró líquidos hoy. Vigilar hidratación "
            "— llamar al médico."
        )]
    return []


def _evaluar_hinchazon(registro, fecha_referencia):
    """Regla 7: Hinchazón abdominal — empeoramiento entre días.
    Decisión Arquitecto, jun 2026. Distensión = signo cardinal de íleo.
    Prioriza especificidad: casi todos tienen algo de hinchazón post-op,
    así que solo el empeoramiento sostenido o "mucho" prolongado alertan.
    Severidad final = la más alta entre las condiciones que apliquen."""
    if registro.hinchazon_abdominal not in HINCHAZON_NIVELES:
        return []

    nivel_hoy    = _nivel_hinchazon_dia(registro.paciente, fecha_referencia)
    nivel_ayer   = _nivel_hinchazon_dia(registro.paciente, fecha_referencia - timedelta(days=1))
    nivel_antier = _nivel_hinchazon_dia(registro.paciente, fecha_referencia - timedelta(days=2))

    severidad_hinchazon = None

    # Condición BAJA: empeoramiento puntual (hoy > ayer)
    # Los dos `if` NO se funden en uno a propósito: el primero pregunta si hay
    # dato y el segundo si empeoró, que en clínica son preguntas distintas —
    # "no sé" no es "no empeoró". Ver D8 y las pruebas de caracterización de
    # `HinchazonCondicionMediaTests`.
    if nivel_ayer is not None and nivel_hoy is not None:  # noqa: SIM102
        if nivel_hoy > nivel_ayer:
            severidad_hinchazon = 'BAJA'

    # Condición MEDIA: empeoramiento verificado contra antier (hoy > antier)
    # que además no bajó en el camino.
    #
    # Con dato de ayer, "sin bajar" es la secuencia no decreciente
    # antier <= ayer <= hoy: eso es el "sostenido" de la regla documentada.
    #
    # SIN dato de ayer no hay con qué comprobar el sostenimiento, y la
    # condición se reduce a hoy > antier. Es el comportamiento que este código
    # ya tenía: la expresión anterior lo escondía tras dos comparaciones que se
    # volvían trivialmente verdaderas en ese caso (`nivel_ayer is None or ...`
    # y `nivel_hoy >= nivel_hoy`). Se conserva idéntico a propósito —
    # cambiar cuándo dispara la alerta es mover un umbral clínico y requiere
    # validación del médico (decisión D10). Lo fija
    # HinchazonCondicionMediaTests.
    if nivel_antier is not None and nivel_hoy is not None:
        empeoro_contra_antier = nivel_hoy > nivel_antier
        if nivel_ayer is None:
            se_mantuvo_sin_bajar = True
        else:
            se_mantuvo_sin_bajar = nivel_antier <= nivel_ayer <= nivel_hoy
        if empeoro_contra_antier and se_mantuvo_sin_bajar:
            severidad_hinchazon = 'MEDIA'

    # Condición ALTA: "mucho" (2) sostenido 4 días consecutivos
    dias_mucho = 0
    dia_rev = fecha_referencia
    while True:
        nivel_dia = _nivel_hinchazon_dia(registro.paciente, dia_rev)
        if nivel_dia is None:
            break
        if nivel_dia < HINCHAZON_NIVELES['mucho']:
            break
        dias_mucho += 1
        if dias_mucho >= DIAS_HINCHAZON_MUCHO_ALTA:
            break
        dia_rev = dia_rev - timedelta(days=1)
    if dias_mucho >= DIAS_HINCHAZON_MUCHO_ALTA:
        severidad_hinchazon = 'ALTA'

    if severidad_hinchazon is None:
        return []

    mensajes_h = {
        'BAJA': "Aumento leve de la hinchazón abdominal respecto a ayer. Monitorear.",
        'MEDIA': "Hinchazón abdominal en aumento sostenido sin mejorar. "
                 "Posible íleo — llamar al médico.",
        'ALTA': "Hinchazón abdominal severa (nivel máximo) sostenida varios días. "
                "Posible íleo paralítico — ir a urgencias.",
    }
    return [_registrar_alerta(
        registro, 'ILEO_PARALITICO', severidad_hinchazon,
        mensajes_h[severidad_hinchazon]
    )]


def _evaluar_frecuencia_cardiaca(registro, fecha_referencia):
    """Regla 8: Frecuencia cardíaca elevada (taquicardia) — valor absoluto.
    Decisión Arquitecto, jun 2026. Solo se vigila FC alta, no bradicardia.
    Sin lógica de días calendario: el valor por sí solo ya es significativo.
    Base: Outersterp 2025 (>100 lpm monitoreo domiciliario), CREWS 2022
    (110 lpm, 75% sensibilidad para fuga/sangrado), Cleveland NCT04574908
    (>110 umbral de intervención), protocolos hospitalarios (>150 escalamiento)."""
    if registro.frecuencia_cardiaca is None:
        return []

    fc = registro.frecuencia_cardiaca
    if fc >= FC_ALTA_MIN:
        severidad_fc = 'ALTA'
    elif fc >= FC_MEDIA_MIN:
        severidad_fc = 'MEDIA'
    elif fc >= FC_BAJA_MIN:
        severidad_fc = 'BAJA'
    else:
        return []

    mensajes_fc = {
        'BAJA': f"Frecuencia cardíaca de {fc} lpm (taquicardia leve). Monitorear.",
        'MEDIA': f"Frecuencia cardíaca de {fc} lpm. Requiere evaluación — llamar al médico.",
        'ALTA': f"Frecuencia cardíaca de {fc} lpm (taquicardia severa). Escalar — ir a urgencias.",
    }
    return [_registrar_alerta(
        registro, 'TAQUICARDIA', severidad_fc, mensajes_fc[severidad_fc]
    )]


def evaluar_registro(registro, fecha_referencia=None):
    """Orquesta las 8 reglas clínicas y retorna todas las alertas creadas
    O actualizadas en esta evaluación (instancias únicas).

    fecha_referencia: fecha calendario que el engine usa como 'hoy' para
    agrupar registros por día. Default: fecha local del registro.
    El bot pasa checkin.fecha_dia para corregir cruces de medianoche
    (decisión 0-① Sprint 4)."""
    if fecha_referencia is None:
        fecha_referencia = timezone.localdate(registro.fecha_registro)

    alertas = []
    alertas += _evaluar_temperatura(registro, fecha_referencia)
    alertas += _evaluar_drenaje(registro, fecha_referencia)
    alertas += _evaluar_gases(registro, fecha_referencia)
    alertas += _evaluar_nauseas(registro, fecha_referencia)
    alertas += _evaluar_dolor(registro, fecha_referencia)
    alertas += _evaluar_tolerancia_liquidos(registro, fecha_referencia)
    alertas += _evaluar_hinchazon(registro, fecha_referencia)
    alertas += _evaluar_frecuencia_cardiaca(registro, fecha_referencia)

    # Una misma alerta puede ser devuelta por 2 reglas del mismo tipo en el
    # mismo check-in (p. ej. ILEO por gases y por hinchazón). Devolver una sola
    # instancia por alerta, y que sea la ÚLTIMA que la tocó — así refleja la
    # severidad final (la primera instancia quedaría desactualizada en memoria).
    ultima = {}
    orden = []
    for a in alertas:
        if a.pk not in ultima:
            orden.append(a.pk)
        ultima[a.pk] = a
    return [ultima[pk] for pk in orden]
