"""Configura el rol médico y, opcionalmente, crea una cuenta desde entorno.

Variables opcionales para crear/actualizar la cuenta:
    DJANGO_MEDICO_USERNAME
    DJANGO_MEDICO_PASSWORD
    DJANGO_MEDICO_EMAIL

Sin credenciales, el comando solo garantiza que el grupo y sus permisos
existan. Esto permite preparar el rol sin guardar contraseñas en el código.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


NOMBRE_GRUPO_MEDICOS = 'Médicos'

PERMISOS_MEDICO = {
    ('signos_sintomas', 'paciente'): {'add', 'change', 'view'},
    ('signos_sintomas', 'registrodiario'): {'view'},
    ('signos_sintomas', 'alerta'): {'change', 'view'},
    ('signos_sintomas', 'checkinprogramado'): {'view'},
    ('home', 'mensajecontacto'): {'change', 'view'},
}


def obtener_permisos_medico():
    permisos = []
    for (app_label, model), acciones in PERMISOS_MEDICO.items():
        codenames = [f'{accion}_{model}' for accion in acciones]
        encontrados = list(Permission.objects.filter(
            content_type__app_label=app_label,
            content_type__model=model,
            codename__in=codenames,
        ))
        if len(encontrados) != len(codenames):
            hallados = {perm.codename for perm in encontrados}
            faltantes = sorted(set(codenames) - hallados)
            raise CommandError(
                f'No se encontraron permisos requeridos: {", ".join(faltantes)}.'
            )
        permisos.extend(encontrados)
    return permisos


class Command(BaseCommand):
    help = 'Configura el grupo Médicos y crea una cuenta de privilegio mínimo.'

    @transaction.atomic
    def handle(self, *args, **options):
        grupo, _ = Group.objects.get_or_create(name=NOMBRE_GRUPO_MEDICOS)
        grupo.permissions.set(obtener_permisos_medico())

        username = os.environ.get('DJANGO_MEDICO_USERNAME')
        password = os.environ.get('DJANGO_MEDICO_PASSWORD')
        email = os.environ.get('DJANGO_MEDICO_EMAIL', '')

        if not username and not password:
            self.stdout.write(
                'crear_medico: grupo "Médicos" configurado; '
                'sin credenciales, no se crea ninguna cuenta.'
            )
            return
        if not username or not password:
            raise CommandError(
                'DJANGO_MEDICO_USERNAME y DJANGO_MEDICO_PASSWORD deben '
                'definirse juntos.'
            )

        User = get_user_model()
        user, creado = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        if user.is_superuser:
            raise CommandError(
                f'crear_medico: "{username}" ya es superusuario; usa otro nombre.'
            )

        user.email = email
        user.is_staff = True
        user.is_superuser = False
        user.set_password(password)
        user.save()
        user.groups.set([grupo])
        user.user_permissions.clear()

        estado = 'creada' if creado else 'actualizada'
        self.stdout.write(self.style.SUCCESS(
            f'crear_medico: cuenta "{username}" {estado} con privilegio mínimo.'
        ))
