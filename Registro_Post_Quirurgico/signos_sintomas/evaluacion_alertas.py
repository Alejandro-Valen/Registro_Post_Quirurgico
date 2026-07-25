"""Ejecución auditable y reintentable del motor de alertas."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .alert_engine import evaluar_registro
from .models import Alerta, RegistroDiario


def evaluar_registro_con_estado(registro, fecha_referencia=None):
    """Evalúa un registro y conserva el resultado operativo en la BD.

    Los cambios parciales del motor se ejecutan en un savepoint. Si ocurre una
    excepción, se revierten las alertas parciales pero se conserva el estado
    ERROR para que el registro pueda reintentarse sin perderse en silencio.
    """
    error = None
    alertas = []

    with transaction.atomic():
        registro_bloqueado = (
            RegistroDiario.objects.select_for_update()
            .get(pk=registro.pk)
        )
        if (
            registro_bloqueado.estado_evaluacion_alertas
            == RegistroDiario.EVALUACION_COMPLETADA
        ):
            return list(
                Alerta.objects.filter(registro_origen=registro_bloqueado)
            )

        registro_bloqueado.estado_evaluacion_alertas = (
            RegistroDiario.EVALUACION_PROCESANDO
        )
        registro_bloqueado.intentos_evaluacion_alertas += 1
        registro_bloqueado.fecha_ultima_evaluacion_alertas = timezone.now()
        registro_bloqueado.ultimo_error_evaluacion_alertas = ''
        registro_bloqueado.save(update_fields=[
            'estado_evaluacion_alertas',
            'intentos_evaluacion_alertas',
            'fecha_ultima_evaluacion_alertas',
            'ultimo_error_evaluacion_alertas',
        ])

        try:
            with transaction.atomic():
                alertas = evaluar_registro(
                    registro_bloqueado,
                    fecha_referencia=fecha_referencia,
                )
        except Exception as exc:
            error = exc
            registro_bloqueado.estado_evaluacion_alertas = (
                RegistroDiario.EVALUACION_ERROR
            )
            registro_bloqueado.ultimo_error_evaluacion_alertas = (
                type(exc).__name__[:100]
            )
        else:
            registro_bloqueado.estado_evaluacion_alertas = (
                RegistroDiario.EVALUACION_COMPLETADA
            )
            registro_bloqueado.ultimo_error_evaluacion_alertas = ''

        registro_bloqueado.fecha_ultima_evaluacion_alertas = timezone.now()
        registro_bloqueado.save(update_fields=[
            'estado_evaluacion_alertas',
            'fecha_ultima_evaluacion_alertas',
            'ultimo_error_evaluacion_alertas',
        ])

    if error is not None:
        raise error
    return alertas


def registrar_fallo_evaluacion(registro, exc):
    """Deja constancia de un fallo cuya constancia original fue revertida.

    `evaluar_registro_con_estado` persiste el estado ERROR antes de relanzar,
    pero quien la llama puede envolverla en su propio savepoint —lo hace
    `bot._crear_registro` para que un fallo del motor nunca pierda el reporte
    del paciente—. La excepción al salir de ese savepoint revierte también la
    constancia del fallo, y el registro queda idéntico a uno que nunca pasó por
    el motor (hallazgo 7). Este helper la vuelve a escribir desde fuera del
    savepoint ya revertido.

    Se escribe con un UPDATE condicional en vez de `save()`: no debe pisar un
    estado COMPLETADA que otro proceso haya alcanzado mientras tanto. Solo se
    guarda el NOMBRE de la excepción, nunca su mensaje, que puede llevar datos
    clínicos del paciente.
    """
    return (
        RegistroDiario.objects
        .filter(pk=registro.pk)
        .exclude(estado_evaluacion_alertas=RegistroDiario.EVALUACION_COMPLETADA)
        .update(
            estado_evaluacion_alertas=RegistroDiario.EVALUACION_ERROR,
            intentos_evaluacion_alertas=F('intentos_evaluacion_alertas') + 1,
            ultimo_error_evaluacion_alertas=type(exc).__name__[:100],
            fecha_ultima_evaluacion_alertas=timezone.now(),
        )
    )
