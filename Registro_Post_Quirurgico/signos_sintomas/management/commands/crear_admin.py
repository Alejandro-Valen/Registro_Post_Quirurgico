"""
Management command: crear_admin

Crea o actualiza un superusuario de forma idempotente a partir de variables de
entorno, para poder acceder al Admin en producción (Railway) sin shell
interactivo. Resuelve el caso en que el usuario quedó con credenciales
"sucias" (ej. con `< >` pegados por error): re-establece la contraseña exacta.

Lee:
    DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_PASSWORD
    DJANGO_SUPERUSER_EMAIL   (opcional)

Comportamiento:
- Si USERNAME o PASSWORD no están definidos: no hace nada (no-op seguro).
- Si están: garantiza que el usuario exista con is_staff/is_superuser=True y la
  contraseña indicada. RE-ESTABLECE la contraseña en cada corrida mientras la
  variable esté presente — por eso, tras obtener acceso, conviene QUITAR
  DJANGO_SUPERUSER_PASSWORD para que no sobreescriba cambios manuales.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea/actualiza un superusuario desde variables de entorno (idempotente)."

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

        if not username or not password:
            self.stdout.write(
                'crear_admin: sin DJANGO_SUPERUSER_USERNAME/PASSWORD, no se hace nada.'
            )
            return

        User = get_user_model()
        user, creado = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        if email:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        estado = 'creado' if creado else 'actualizado'
        self.stdout.write(
            self.style.SUCCESS(f'crear_admin: superusuario "{username}" {estado}.')
        )
