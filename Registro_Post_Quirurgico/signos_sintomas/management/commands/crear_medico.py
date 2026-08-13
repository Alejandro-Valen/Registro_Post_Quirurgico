"""Configura el rol médico y, opcionalmente, crea una cuenta desde entorno.

Variables opcionales para crear/actualizar la cuenta:
    DJANGO_MEDICO_USERNAME
    DJANGO_MEDICO_PASSWORD
    DJANGO_MEDICO_EMAIL
    DJANGO_MEDICO_RESET     ('1' para reescribir credenciales — ver abajo)

Sin credenciales, el comando solo garantiza que el grupo y sus permisos
existan. Esto permite preparar el rol sin guardar contraseñas en el código.

QUÉ REESCRIBE Y QUÉ NO (decisión D15, ver
docs/decisiones_correccion_auditoria.md). Este comando corre en CADA arranque
del servicio web (Dockerfile y nixpacks.toml), así que la diferencia importa:

- La contraseña se fija **solo al crear** la cuenta. Si el médico la cambia
  desde el Admin, le sobrevive a los despliegues. Para rotarla —por ejemplo si
  se filtra— hay que pedirlo a propósito con DJANGO_MEDICO_RESET=1 en el
  servicio, reiniciar, y volver a quitar la variable.
- El correo solo se escribe si DJANGO_MEDICO_EMAIL trae valor. Nunca se vacía:
  es el destinatario de las alertas (ver signos_sintomas/notificaciones.py).
- Los grupos y los permisos individuales SÍ se reescriben en cada arranque, a
  propósito: el privilegio mínimo es declarativo y la cuenta vuelve siempre al
  perfil aprobado. Para darle más permisos al médico se cambia PERMISOS_MEDICO
  aquí abajo, no la cuenta desde el Admin.
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
        # Mismo convenio que RESET_AXES en el Dockerfile: exactamente '1'.
        forzar_credenciales = os.environ.get('DJANGO_MEDICO_RESET') == '1'

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

        if email:
            user.email = email
        user.is_staff = True
        user.is_superuser = False
        if creado or forzar_credenciales:
            user.set_password(password)
        user.save()
        user.groups.set([grupo])
        user.user_permissions.clear()

        # El log del despliegue tiene que decir qué pasó con la contraseña: es
        # lo primero que se mira cuando alguien no puede entrar.
        if creado:
            detalle = 'creada con privilegio mínimo'
        elif forzar_credenciales:
            detalle = 'credenciales reescritas por DJANGO_MEDICO_RESET=1'
        else:
            detalle = 'permisos al día; contraseña sin tocar'
        self.stdout.write(self.style.SUCCESS(
            f'crear_medico: cuenta "{username}" — {detalle}.'
        ))
