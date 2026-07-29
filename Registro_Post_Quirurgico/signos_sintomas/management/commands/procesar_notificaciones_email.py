from django.core.management.base import BaseCommand, CommandError

from signos_sintomas.notificaciones import procesar_notificaciones_pendientes


class Command(BaseCommand):
    help = 'Envía notificaciones de alertas ALTA pendientes con reintentos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=50,
            help='Máximo de notificaciones por ejecución (por defecto: 50).',
        )

    def handle(self, *args, **options):
        limite = options['limite']
        if limite < 1:
            raise CommandError('--limite debe ser mayor o igual a 1.')

        resumen = procesar_notificaciones_pendientes(limite=limite)
        mensaje = (
            'Notificaciones: {candidatas} candidatas, {enviadas} enviadas, '
            '{errores} con reintento pendiente.'.format(**resumen)
        )
        if resumen['errores']:
            self.stderr.write(self.style.ERROR(mensaje))
            raise CommandError(
                'Una o más notificaciones no pudieron entregarse; '
                'permanecen en la bandeja para reintento.'
            )
        self.stdout.write(self.style.SUCCESS(mensaje))
