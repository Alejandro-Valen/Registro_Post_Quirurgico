from django.apps import AppConfig


class SignosSintomasConfig(AppConfig):
    name = 'signos_sintomas'

    def ready(self):
        import signos_sintomas.signals  # noqa: F401
