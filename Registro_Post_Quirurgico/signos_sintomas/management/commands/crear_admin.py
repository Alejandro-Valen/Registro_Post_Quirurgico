"""
Management command: crear_admin

Crea un superusuario a partir de variables de entorno, para poder acceder al
Admin en producción (Railway) sin shell interactivo.

Lee:
    DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_PASSWORD
    DJANGO_SUPERUSER_EMAIL   (opcional)
    DJANGO_SUPERUSER_RESET   ('1' para reescribir la contraseña — ver abajo)

QUÉ HACE Y QUÉ NO (decisión D27, gemela de D15 y de `crear_medico`). Corre en
CADA arranque del servicio web (Dockerfile), así que la diferencia importa:

- Sin USERNAME o PASSWORD: no hace nada (no-op seguro).
- Si la cuenta no existe: la crea como superusuario con esa contraseña.
- Si existe y ya es superusuario: **no toca la contraseña.** Hasta el
  02/10/2026 la reescribía en cada arranque (SEC-05): la que eligiera el
  administrador no sobrevivía a un despliegue. Para rotarla —por ejemplo si se
  filtra— hay que pedirlo a propósito con DJANGO_SUPERUSER_RESET=1 en el
  servicio, reiniciar, y volver a quitar la variable. El correo solo se escribe
  si DJANGO_SUPERUSER_EMAIL trae valor.
- Si existe y NO es superusuario: **falla sin tocarla.** Antes la promovía a
  superusuario sin preguntar, fuera quien fuera (un médico, por ejemplo). El
  Dockerfile lo llama con `|| true`, así que el arranque sigue y el log lo dice.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea un superusuario desde variables de entorno; no reescribe uno existente."

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
        # Mismo convenio que DJANGO_MEDICO_RESET y RESET_AXES: exactamente '1'.
        forzar_contrasena = os.environ.get('DJANGO_SUPERUSER_RESET') == '1'

        if not username or not password:
            self.stdout.write(
                'crear_admin: sin DJANGO_SUPERUSER_USERNAME/PASSWORD, no se hace nada.'
            )
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()

        if user is None:
            User.objects.create_superuser(
                username=username, email=email, password=password,
            )
            detalle = 'creado'
        elif not user.is_superuser:
            raise CommandError(
                f'crear_admin: "{username}" ya existe y no es superusuario; no '
                f'se promueve. Usa otro nombre, o promuévela a mano desde el '
                f'Admin si de verdad debe serlo.'
            )
        else:
            if email:
                user.email = email
            if forzar_contrasena:
                user.set_password(password)
            user.save()
            detalle = (
                'contraseña reescrita por DJANGO_SUPERUSER_RESET=1'
                if forzar_contrasena else 'ya existía; contraseña sin tocar'
            )

        # El log del despliegue tiene que decir qué pasó con la contraseña: es
        # lo primero que se mira cuando alguien no puede entrar.
        self.stdout.write(
            self.style.SUCCESS(f'crear_admin: superusuario "{username}" — {detalle}.')
        )
