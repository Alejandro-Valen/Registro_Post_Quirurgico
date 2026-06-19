from datetime import timedelta
from decimal import Decimal

from django.db import models

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
        hoy = registro.fecha_registro.date()
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
    hoy_nauseas = registro.fecha_registro.date()
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
    hoy_gases = registro.fecha_registro.date()
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

    return alertas_creadas

