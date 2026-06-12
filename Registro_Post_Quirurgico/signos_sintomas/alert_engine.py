from decimal import Decimal

from .models import Alerta, RegistroDiario


TEMPERATURA_SEPSIS = Decimal('38.0')
DRENAJES_FUGA_ANASTOMOTICA = ('purulento', 'fecaloide')
EPISODIOS_NAUSEAS_ILEO = 3
REGISTROS_SIN_GASES_ILEO = 3

def evaluar_registro(registro):
    alertas_creadas = []

    # Regla 1: Fiebre alta (Riesgo de Sepsis)
    if registro.temperatura >= TEMPERATURA_SEPSIS:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='SEPSIS',
            severidad='ALTA',
            mensaje=f"Temperatura de {registro.temperatura}°C detectada. Posible cuadro de sepsis."
        )
        alertas_creadas.append(alerta)

    # Regla 2: Drenaje purulento o fecaloide (Posible fuga anastomótica)
    if registro.aspecto_drenaje in DRENAJES_FUGA_ANASTOMOTICA:
        alerta = Alerta.objects.create(
            paciente=registro.paciente,
            registro_origen=registro,
            tipo='FUGA_ANASTOMOTICA',
            severidad='ALTA',
            mensaje=f"Drenaje {registro.aspecto_drenaje} detectado. Posible fuga anastomótica."
        )
        alertas_creadas.append(alerta)

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

    # Regla 3: Sin gases por 3 registros consecutivos
    ultimos_registros = RegistroDiario.objects.filter(
        paciente=registro.paciente,
        fecha_registro__lte=registro.fecha_registro
    ).order_by('-fecha_registro')[:REGISTROS_SIN_GASES_ILEO]
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

