from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from .models import Alerta, RegistroDiario


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

# Orden de severidad usado por múltiples reglas y por la deduplicación
# de alertas (decisión 0-② Sprint 4 — Opción A+).
ORDEN_SEVERIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3, None: 0}


def _deduplicar(paciente, tipo, severidad, fecha_referencia):
    """Opción A+ (decisión 0-② Sprint 4): retorna True si ya existe una
    alerta del mismo tipo/día con severidad igual o mayor.
    Si retorna True, el llamador debe omitir la creación de la alerta."""
    alertas_hoy = Alerta.objects.filter(
        paciente=paciente,
        tipo=tipo,
        fecha_alerta__date=fecha_referencia,
    ).values_list('severidad', flat=True)
    nueva_orden = ORDEN_SEVERIDAD[severidad]
    return any(ORDEN_SEVERIDAD[s] >= nueva_orden for s in alertas_hoy)


def _severidad_dolor_por_ventana(dia_postoperatorio, dolor_eva):
    """Devuelve 'ALTA', 'MEDIA', 'BAJA' o None según la ventana de
    dia_postoperatorio y el valor de dolor_eva."""
    for dia_max, eva_baja, eva_media, eva_alta in VENTANAS_DOLOR:
        if dia_max is None or dia_postoperatorio <= dia_max:
            if dolor_eva >= eva_alta:
                return 'ALTA'
            elif dolor_eva >= eva_media:
                return 'MEDIA'
            elif dolor_eva >= eva_baja:
                return 'BAJA'
            else:
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
    hospitalaria como en otros estudios)."""
    if registro.temperatura >= TEMPERATURA_ALTA:
        if _deduplicar(registro.paciente, 'SEPSIS', 'ALTA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje=(
                f"Temperatura de {registro.temperatura}°C detectada. "
                "Posible cuadro de sepsis — ir a urgencias."
            )
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
            if _deduplicar(registro.paciente, 'SEPSIS', 'MEDIA', fecha_referencia):
                return []
            return [Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='SEPSIS',
                severidad='MEDIA',
                mensaje=(
                    f"Subfebrícula ({registro.temperatura}°C) persistente "
                    f"por {DIAS_SUBFEBRICULA_PERSISTENTE} días consecutivos. "
                    "Llamar al médico."
                )
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
        if _deduplicar(registro.paciente, 'FUGA_ANASTOMOTICA', 'ALTA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='FUGA_ANASTOMOTICA',
            severidad='ALTA',
            mensaje=(
                f"Drenaje {registro.aspecto_drenaje} detectado. "
                "Posible fuga anastomótica — ir a urgencias."
            )
        )]
    if registro.aspecto_drenaje in DRENAJES_MEDIA:
        if _deduplicar(registro.paciente, 'FUGA_ANASTOMOTICA', 'MEDIA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='FUGA_ANASTOMOTICA',
            severidad='MEDIA',
            mensaje=(
                f"Drenaje {registro.aspecto_drenaje} detectado. "
                "Requiere seguimiento — llamar al médico."
            )
        )]
    if registro.aspecto_drenaje in DRENAJES_BAJA:
        if _deduplicar(registro.paciente, 'FUGA_ANASTOMOTICA', 'BAJA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='FUGA_ANASTOMOTICA',
            severidad='BAJA',
            mensaje=(
                "Drenaje seroso detectado. "
                "Aspecto dentro de lo esperado — monitorear."
            )
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
        if _deduplicar(registro.paciente, 'ILEO_PARALITICO', 'ALTA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='ALTA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
                "consecutivos. Posible íleo paralítico severo — ir a urgencias."
            )
        )]
    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_MEDIA:
        if _deduplicar(registro.paciente, 'ILEO_PARALITICO', 'MEDIA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='MEDIA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
                "consecutivos. Llamar al médico."
            )
        )]
    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_BAJA:
        if _deduplicar(registro.paciente, 'ILEO_PARALITICO', 'BAJA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='BAJA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} día(s). "
                "Monitorear."
            )
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

    if _deduplicar(registro.paciente, 'ILEO_PARALITICO', severidad_final, fecha_referencia):
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
    return [Alerta.objects.create(
        paciente=registro.paciente,
        registro_origen=registro,
        tipo='ILEO_PARALITICO',
        severidad=severidad_final,
        mensaje=mensaje
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

    if _deduplicar(registro.paciente, 'DOLOR_AGUDO', severidad_final, fecha_referencia):
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
    return [Alerta.objects.create(
        paciente=registro.paciente,
        registro_origen=registro,
        tipo='DOLOR_AGUDO',
        severidad=severidad_final,
        mensaje=mensaje
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
        if _deduplicar(registro.paciente, 'INTOLERANCIA_ORAL', 'ALTA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='INTOLERANCIA_ORAL',
            severidad='ALTA',
            mensaje=(
                f"Paciente sin tolerar líquidos por {dias_sin_tolerar} "
                "días consecutivos. Riesgo de deshidratación — ir a "
                "urgencias."
            )
        )]
    if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_MEDIA:
        if _deduplicar(registro.paciente, 'INTOLERANCIA_ORAL', 'MEDIA', fecha_referencia):
            return []
        return [Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='INTOLERANCIA_ORAL',
            severidad='MEDIA',
            mensaje=(
                "Paciente no toleró líquidos hoy. Vigilar hidratación "
                "— llamar al médico."
            )
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
    if nivel_ayer is not None and nivel_hoy is not None:
        if nivel_hoy > nivel_ayer:
            severidad_hinchazon = 'BAJA'

    # Condición MEDIA: empeoramiento verificado (hoy > antier) que
    # se mantuvo sin bajar en la ventana de los últimos > 2 días
    if nivel_antier is not None and nivel_hoy is not None:
        if nivel_hoy > nivel_antier and (
            nivel_ayer is None or nivel_ayer >= nivel_antier
        ) and nivel_hoy >= (nivel_ayer if nivel_ayer is not None else nivel_hoy):
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

    if _deduplicar(registro.paciente, 'ILEO_PARALITICO', severidad_hinchazon, fecha_referencia):
        return []

    mensajes_h = {
        'BAJA': "Aumento leve de la hinchazón abdominal respecto a ayer. Monitorear.",
        'MEDIA': "Hinchazón abdominal en aumento sostenido sin mejorar. "
                 "Posible íleo — llamar al médico.",
        'ALTA': "Hinchazón abdominal severa (nivel máximo) sostenida varios días. "
                "Posible íleo paralítico — ir a urgencias.",
    }
    return [Alerta.objects.create(
        paciente=registro.paciente,
        registro_origen=registro,
        tipo='ILEO_PARALITICO',
        severidad=severidad_hinchazon,
        mensaje=mensajes_h[severidad_hinchazon],
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

    if _deduplicar(registro.paciente, 'TAQUICARDIA', severidad_fc, fecha_referencia):
        return []

    mensajes_fc = {
        'BAJA': f"Frecuencia cardíaca de {fc} lpm (taquicardia leve). Monitorear.",
        'MEDIA': f"Frecuencia cardíaca de {fc} lpm. Requiere evaluación — llamar al médico.",
        'ALTA': f"Frecuencia cardíaca de {fc} lpm (taquicardia severa). Escalar — ir a urgencias.",
    }
    return [Alerta.objects.create(
        paciente=registro.paciente,
        registro_origen=registro,
        tipo='TAQUICARDIA',
        severidad=severidad_fc,
        mensaje=mensajes_fc[severidad_fc],
    )]


def evaluar_registro(registro, fecha_referencia=None):
    """Orquesta las 8 reglas clínicas y retorna todas las alertas creadas.

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
    return alertas
