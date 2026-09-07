from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from signos_sintomas.evaluacion_alertas import evaluar_registro_con_estado
from signos_sintomas.models import RegistroDiario

# Tope de reintentos de evaluación (D6). Un registro cuya evaluación falla 10
# veces no se recupera reintentando: la causa es un defecto reproducible, no un
# fallo transitorio. Dejar de recogerlo evita el bucle silencioso y el
# desbordamiento del contador de intentos.
MAX_INTENTOS_EVALUACION = 10


class Command(BaseCommand):
    help = 'Reintenta registros cuya evaluación de alertas quedó pendiente o falló.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=100,
            help='Máximo de registros por ejecución (por defecto: 100).',
        )

    def handle(self, *args, **options):
        limite = options['limite']
        if limite < 1:
            raise CommandError('--limite debe ser mayor o igual a 1.')

        estados_reintentables = [
            RegistroDiario.EVALUACION_PENDIENTE,
            RegistroDiario.EVALUACION_ERROR,
        ]
        candidatos = list(
            RegistroDiario.objects.filter(
                estado_evaluacion_alertas__in=estados_reintentables,
                intentos_evaluacion_alertas__lt=MAX_INTENTOS_EVALUACION,
            )
            .order_by('fecha_registro', 'pk')
            .values_list('pk', flat=True)[:limite]
        )

        completados = 0
        errores = 0
        for registro_pk in candidatos:
            with transaction.atomic():
                registro = (
                    RegistroDiario.objects.select_for_update(skip_locked=True)
                    .filter(
                        pk=registro_pk,
                        estado_evaluacion_alertas__in=estados_reintentables,
                    )
                    .first()
                )
                if registro is None:
                    continue

                try:
                    checkin = registro.checkin
                except RegistroDiario.checkin.RelatedObjectDoesNotExist:
                    fecha_referencia = None
                else:
                    fecha_referencia = checkin.fecha_dia

                try:
                    evaluar_registro_con_estado(
                        registro,
                        fecha_referencia=fecha_referencia,
                    )
                except Exception as exc:  # noqa: BLE001  (un registro malo no puede detener el lote)
                    errores += 1
                    self.stderr.write(
                        f'Evaluación registro pk={registro.pk} falló con {type(exc).__name__}.'
                    )
                else:
                    completados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Evaluaciones procesadas: {completados} completadas, {errores} con error.'
            )
        )
