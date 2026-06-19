from datetime import timedelta
from decimal import Decimal

from .models import Alerta, RegistroDiario


TEMPERATURA_ALTA = Decimal('37.9')           # Outersterp 2025
TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.5')
DIAS_SUBFEBRICULA_PERSISTENTE = 2

# Escalera de severidad por aspecto de drenaje (decisión Arquitectos jun 2026)
# Base: Lee 2022, Gignoux 2018, Coeckelberghs 2025
DRENAJES_ALTA  = ('purulento', 'fecaloide')
DRENAJES_MEDIA = ('turbio', 'hematico')
DRENAJES_BAJA  = ('seroso',)

EPISODIOS_NAUSEAS_ILEO = 3
REGISTROS_SIN_GASES_ILEO = 3

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

    # Regla 4: Más de 3 episodios de náuseas o vómito en 24h
    if registro.episodios_nauseas > EPISODIOS_NAUSEAS_ILEO:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='MEDIA',
            mensaje=f"{registro.episodios_nauseas} episodios de náuseas/vómito en 24h. Posible íleo paralítico."
        )
        alertas_creadas.append(alerta)

    # Regla 3: Sin gases por 3 días postoperatorios consecutivos
    ultimos_registros = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        dia_postoperatorio__lte=registro.dia_postoperatorio
    ).order_by('-dia_postoperatorio', '-fecha_registro')[:REGISTROS_SIN_GASES_ILEO]
    if len(ultimos_registros) == REGISTROS_SIN_GASES_ILEO and all(
        not registro_diario.presencia_gases
        for registro_diario in ultimos_registros
    ):
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='ILEO_PARALITICO',
            severidad='ALTA',
            mensaje="Paciente sin gases por 3 registros consecutivos. Posible íleo paralítico severo."
        )
        alertas_creadas.append(alerta)

    return alertas_creadas

