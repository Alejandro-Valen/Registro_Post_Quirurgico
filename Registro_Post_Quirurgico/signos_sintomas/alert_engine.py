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

# Escalera de dolor (EVA) por ventana de dia_postoperatorio.
# Decisión Arquitecto, jun 2026. Base: Delaney 2008, Lee 2022,
# Outersterp 2025, Coeckelberghs 2025.
VENTANAS_DOLOR = [
    # (dia_postoperatorio_max_inclusive, eva_baja_min, eva_media_min, eva_alta_min)
    (2,    5, 7, 9),   # POD 1-2
    (5,    4, 6, 8),   # POD 3-5
    (None, 3, 5, 7),   # POD 6+ (None = sin límite superior)
]
DOLOR_DIAS_TENDENCIA = 2
DOLOR_DELTA_TENDENCIA = 3


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


def evaluar_registro(registro):
    alertas_creadas = []

    # Regla 1: Temperatura — escalera por días calendario.
    # Decisión Arquitecto, jun 2026. Base: Outersterp 2025 (>37.9°C umbral
    # de notificación en monitoreo domiciliario, no solo criterio de alta
    # hospitalaria como en otros estudios).
    if registro.temperatura >= TEMPERATURA_ALTA:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje=(
                f"Temperatura de {registro.temperatura}°C detectada. "
                "Posible cuadro de sepsis — ir a urgencias."
            )
        )
        alertas_creadas.append(alerta)
    elif TEMPERATURA_SUBFEBRICULA_MIN <= registro.temperatura < TEMPERATURA_ALTA:
        hoy = timezone.localdate(registro.fecha_registro)
        dias_con_subfebricula = set()
        for offset in range(DIAS_SUBFEBRICULA_PERSISTENTE):
            dia = hoy - timedelta(days=offset)
            existe = RegistroDiario.objects.filter(
                paciente=registro.paciente,
                fecha_registro__date=dia,
                temperatura__gte=TEMPERATURA_SUBFEBRICULA_MIN,
                temperatura__lt=TEMPERATURA_ALTA,
            ).exists()
            if existe:
                dias_con_subfebricula.add(dia)
        if len(dias_con_subfebricula) >= DIAS_SUBFEBRICULA_PERSISTENTE:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='SEPSIS',
                severidad='MEDIA',
                mensaje=(
                    f"Subfebrícula ({registro.temperatura}°C) persistente "
                    f"por {DIAS_SUBFEBRICULA_PERSISTENTE} días consecutivos. "
                    "Llamar al médico."
                )
            )
            alertas_creadas.append(alerta)
    # < 37.5°C: sin alerta, el valor queda en RegistroDiario para el
    # dashboard del médico.

    # Regla 2: Drenaje anormal — solo evalúa si el paciente tiene drenaje activo.
    # tiene_drenaje=None → registro anterior a esta versión, no se evalúa.
    # Escalera: seroso→BAJA, turbio/hemático→MEDIA, purulento/fecaloide→ALTA.
    if registro.tiene_drenaje is True:
        if registro.aspecto_drenaje in DRENAJES_ALTA:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='FUGA_ANASTOMOTICA',
                severidad='ALTA',
                mensaje=(
                    f"Drenaje {registro.aspecto_drenaje} detectado. "
                    "Posible fuga anastomótica — ir a urgencias."
                )
            )
            alertas_creadas.append(alerta)
        elif registro.aspecto_drenaje in DRENAJES_MEDIA:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='FUGA_ANASTOMOTICA',
                severidad='MEDIA',
                mensaje=(
                    f"Drenaje {registro.aspecto_drenaje} detectado. "
                    "Requiere seguimiento — llamar al médico."
                )
            )
            alertas_creadas.append(alerta)
        elif registro.aspecto_drenaje in DRENAJES_BAJA:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='FUGA_ANASTOMOTICA',
                severidad='BAJA',
                mensaje=(
                    "Drenaje seroso detectado. "
                    "Aspecto dentro de lo esperado — monitorear."
                )
            )
            alertas_creadas.append(alerta)
    # tiene_drenaje=False o None → sin alerta de drenaje.

    # Regla 4: Náuseas/vómito — suma diaria + persistencia entre días.
    # Decisión Arquitecto, jun 2026. Suma: Lee 2022 y Outersterp 2025
    # tratan cualquier episodio como señal (no se espera acumulación de
    # 3+ como la regla anterior). Persistencia 4+ días: Delaney 2008
    # (íleo en 27.8% de pacientes con estancia 4+ días vs 11% general) —
    # mismo orden de magnitud que el umbral ALTA de la Regla 3 (gases).
    hoy_nauseas = timezone.localdate(registro.fecha_registro)
    total_episodios_hoy = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date=hoy_nauseas,
    ).aggregate(total=models.Sum('episodios_nauseas'))['total'] or 0

    severidad_por_suma = None
    if total_episodios_hoy >= NAUSEAS_ALTA_MIN:
        severidad_por_suma = 'ALTA'
    elif total_episodios_hoy >= NAUSEAS_MEDIA_MIN:
        severidad_por_suma = 'MEDIA'
    elif total_episodios_hoy >= NAUSEAS_BAJA_MIN:
        severidad_por_suma = 'BAJA'

    dias_con_nauseas_consecutivos = 0
    dia_revisado = hoy_nauseas
    while True:
        hubo_nauseas_ese_dia = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
            episodios_nauseas__gte=1,
        ).exists()
        if not hubo_nauseas_ese_dia:
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

    ORDEN_SEVERIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3, None: 0}
    severidad_final = max(
        severidad_por_suma, severidad_por_persistencia,
        key=lambda s: ORDEN_SEVERIDAD[s]
    )

    if severidad_final is not None:
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
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad=severidad_final,
            mensaje=mensaje
        )
        alertas_creadas.append(alerta)

    # Regla 3: Ausencia de gases — escalera por días calendario consecutivos.
    # Decisión Arquitecto, jun 2026. El paciente ya demostró función
    # intestinal al momento del alta (criterio ERAS estándar); dejar de
    # tener gases en casa es una regresión, no un estado normal. Un día
    # cuenta como "con gases" si hubo al menos un registro positivo en
    # cualquier check-in de ese día.
    hoy_gases = timezone.localdate(registro.fecha_registro)
    dias_sin_gases_consecutivos = 0
    dia_revisado = hoy_gases
    while True:
        hubo_gases_ese_dia = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
            presencia_gases=True,
        ).exists()
        existe_registro_ese_dia = RegistroDiario.objects.filter(
            paciente=registro.paciente,
            fecha_registro__date=dia_revisado,
        ).exists()
        if not existe_registro_ese_dia:
            break
        if hubo_gases_ese_dia:
            break
        dias_sin_gases_consecutivos += 1
        if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_ALTA:
            break
        dia_revisado = dia_revisado - timedelta(days=1)

    if dias_sin_gases_consecutivos >= DIAS_SIN_GASES_ALTA:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='ALTA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
                "consecutivos. Posible íleo paralítico severo — ir a urgencias."
            )
        )
        alertas_creadas.append(alerta)
    elif dias_sin_gases_consecutivos >= DIAS_SIN_GASES_MEDIA:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='MEDIA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} días "
                "consecutivos. Llamar al médico."
            )
        )
        alertas_creadas.append(alerta)
    elif dias_sin_gases_consecutivos >= DIAS_SIN_GASES_BAJA:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='BAJA',
            mensaje=(
                f"Paciente sin gases por {dias_sin_gases_consecutivos} día(s). "
                "Monitorear."
            )
        )
        alertas_creadas.append(alerta)

    # Regla 5: Dolor (DOLOR_AGUDO) — escalera por ventana de
    # dia_postoperatorio + capa de tendencia alcista.
    # Decisión Arquitecto, jun 2026. La tolerancia de dolor esperado baja
    # con el tiempo (Coeckelberghs 2025); EVA>=4 replicado en 3 estudios
    # independientes (Delaney 2008, Lee 2022, Outersterp 2025) como
    # umbral de atención. La tendencia captura subidas que la tabla por
    # sí sola no vería (ej. EVA 5 en POD5 es "BAJA" por tabla, pero si
    # ayer era EVA 2, el salto de 3 puntos es señal real).
    severidad_por_tabla = _severidad_dolor_por_ventana(
        registro.dia_postoperatorio, registro.dolor_eva
    )

    hoy_dolor = timezone.localdate(registro.fecha_registro)
    ORDEN_SEVERIDAD_DOLOR = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3, None: 0}
    promedio_reciente = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date__gte=hoy_dolor - timedelta(days=DOLOR_DIAS_TENDENCIA - 1),
        fecha_registro__date__lte=hoy_dolor,
    ).aggregate(promedio=models.Avg('dolor_eva'))['promedio']

    promedio_anterior = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__date__gte=hoy_dolor - timedelta(days=(DOLOR_DIAS_TENDENCIA * 2) - 1),
        fecha_registro__date__lt=hoy_dolor - timedelta(days=DOLOR_DIAS_TENDENCIA - 1),
    ).aggregate(promedio=models.Avg('dolor_eva'))['promedio']

    severidad_por_tendencia = None
    delta_tendencia = None
    if promedio_reciente is not None and promedio_anterior is not None:
        delta_tendencia = float(promedio_reciente) - float(promedio_anterior)
        if delta_tendencia >= DOLOR_DELTA_TENDENCIA:
            severidad_base = severidad_por_tabla or 'BAJA'
            siguiente_nivel = {
                'BAJA': 'MEDIA', 'MEDIA': 'ALTA', 'ALTA': 'ALTA',
            }
            severidad_por_tendencia = siguiente_nivel[severidad_base]

    severidad_dolor_final = max(
        severidad_por_tabla, severidad_por_tendencia,
        key=lambda s: ORDEN_SEVERIDAD_DOLOR[s]
    )

    if severidad_dolor_final is not None:
        mensaje = (
            f"Dolor EVA {registro.dolor_eva}/10 en día postoperatorio "
            f"{registro.dia_postoperatorio}."
        )
        if severidad_por_tendencia is not None and (
            ORDEN_SEVERIDAD_DOLOR[severidad_por_tendencia]
            > ORDEN_SEVERIDAD_DOLOR[severidad_por_tabla]
        ):
            mensaje += (
                f" Tendencia al alza detectada (delta {delta_tendencia:.1f} "
                "puntos vs. periodo anterior)."
            )
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='DOLOR_AGUDO',
            severidad=severidad_dolor_final,
            mensaje=mensaje
        )
        alertas_creadas.append(alerta)

    # Regla 6: Intolerancia a líquidos — escalera por días calendario.
    # Decisión Arquitecto, jun 2026. Base: tolerancia oral es criterio de
    # alta en todos los ERAS revisados; deshidratación = causa #1 de
    # readmisión (Lawrence 2013). Arranca en MEDIA (no BAJA) porque no
    # retener líquidos ni un día ya es señal directa hacia deshidratación.
    # Un día cuenta como "toleró" si hubo al menos un registro positivo.
    # Solo evalúa si el registro actual tiene el dato capturado.
    if registro.tolero_liquidos is False:
        hoy_liquidos = timezone.localdate(registro.fecha_registro)
        dias_sin_tolerar = 0
        dia_revisado = hoy_liquidos
        while True:
            toleraba_ese_dia = RegistroDiario.objects.filter(
                paciente=registro.paciente,
                fecha_registro__date=dia_revisado,
                tolero_liquidos=True,
            ).exists()
            existe_registro_ese_dia = RegistroDiario.objects.filter(
                paciente=registro.paciente,
                fecha_registro__date=dia_revisado,
            ).exists()
            if not existe_registro_ese_dia:
                break
            if toleraba_ese_dia:
                break
            dias_sin_tolerar += 1
            if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_ALTA:
                break
            dia_revisado = dia_revisado - timedelta(days=1)

        if dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_ALTA:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='INTOLERANCIA_ORAL',
                severidad='ALTA',
                mensaje=(
                    f"Paciente sin tolerar líquidos por {dias_sin_tolerar} "
                    "días consecutivos. Riesgo de deshidratación — ir a "
                    "urgencias."
                )
            )
            alertas_creadas.append(alerta)
        elif dias_sin_tolerar >= DIAS_SIN_TOLERAR_LIQUIDOS_MEDIA:
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='INTOLERANCIA_ORAL',
                severidad='MEDIA',
                mensaje=(
                    "Paciente no toleró líquidos hoy. Vigilar hidratación "
                    "— llamar al médico."
                )
            )
            alertas_creadas.append(alerta)

    # Regla 7: Hinchazón abdominal — empeoramiento entre días.
    # Decisión Arquitecto, jun 2026. Distensión = signo cardinal de íleo.
    # Prioriza especificidad: casi todos tienen algo de hinchazón post-op,
    # así que solo el empeoramiento sostenido o "mucho" prolongado alertan.
    # Severidad final = la más alta entre las condiciones que apliquen.
    if registro.hinchazon_abdominal in HINCHAZON_NIVELES:
        hoy_h = timezone.localdate(registro.fecha_registro)
        nivel_hoy = _nivel_hinchazon_dia(registro.paciente, hoy_h)
        nivel_ayer = _nivel_hinchazon_dia(
            registro.paciente, hoy_h - timedelta(days=1)
        )
        nivel_antier = _nivel_hinchazon_dia(
            registro.paciente, hoy_h - timedelta(days=2)
        )

        severidad_hinchazon = None

        # --- Condición BAJA: empeoramiento puntual (hoy > ayer) ---
        if nivel_ayer is not None and nivel_hoy is not None:
            if nivel_hoy > nivel_ayer:
                severidad_hinchazon = 'BAJA'

        # --- Condición MEDIA: empeoramiento verificado (hoy > antier) que
        #     se mantuvo sin bajar en la ventana de los últimos > 2 días ---
        if nivel_antier is not None and nivel_hoy is not None:
            if nivel_hoy > nivel_antier and (
                nivel_ayer is None or nivel_ayer >= nivel_antier
            ) and nivel_hoy >= (nivel_ayer if nivel_ayer is not None else nivel_hoy):
                # empeoró respecto al punto de partida y no bajó en el medio
                severidad_hinchazon = 'MEDIA'

        # --- Condición ALTA: "mucho" (2) sostenido 4 días consecutivos ---
        dias_mucho = 0
        dia_rev = hoy_h
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

        if severidad_hinchazon is not None:
            mensajes_h = {
                'BAJA': "Aumento leve de la hinchazón abdominal respecto a "
                        "ayer. Monitorear.",
                'MEDIA': "Hinchazón abdominal en aumento sostenido sin "
                         "mejorar. Posible íleo — llamar al médico.",
                'ALTA': "Hinchazón abdominal severa (nivel máximo) sostenida "
                        "varios días. Posible íleo paralítico — ir a "
                        "urgencias.",
            }
            alerta = Alerta.objects.create(
                paciente=registro.paciente,
                registro_origen=registro,
                tipo='ILEO_PARALITICO',
                severidad=severidad_hinchazon,
                mensaje=mensajes_h[severidad_hinchazon],
            )
            alertas_creadas.append(alerta)

    return alertas_creadas

