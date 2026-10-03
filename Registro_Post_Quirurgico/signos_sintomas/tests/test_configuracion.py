"""Configuracion de produccion que las pruebas deben proteger.

Extraido de signos_sintomas/tests.py sin cambiar una sola prueba
(refactor del 10/08/2026)."""

from django.test import TestCase


class CacheProductionConfigTests(TestCase):
    """D1 — Detecta dependencia redis faltante cuando producción usa RedisCache."""

    def test_redis_importable_para_settings_produccion(self):
        try:
            import redis  # noqa: F401
        except ImportError:
            self.fail(
                "Paquete 'redis' no instalado. "
                "settings_production.py usa RedisCache y requiere redis>=5. "
                "Instalar con: pip install 'redis>=5'"
            )

    def test_django_tiene_parche_de_seguridad_6_0_7(self):
        import django

        self.assertGreaterEqual(django.VERSION[:3], (6, 0, 7))

    def test_produccion_aplica_csp_sin_scripts_inline(self):
        """Cambió en el Loop C (hallazgo 11): ya no importa el módulo tal cual.

        `settings_production` ahora exige CSRF_TRUSTED_ORIGINS y REDIS_URL al
        cargarse —una variable vacía debe detener el arranque— y el .env de
        desarrollo no las tiene, así que el import directo fallaba aquí. La
        prueba carga el módulo con un entorno de producción mínimo y válido; lo
        que verifica (CSP y timeout de correo) no cambió.
        """
        from django.utils.csp import CSP

        from Registro_Post_Quirurgico.tests_configuracion import (
            ENTORNO_PRODUCCION_VALIDO,
            cargar_settings_produccion,
        )

        settings_production = cargar_settings_produccion(
            dict(ENTORNO_PRODUCCION_VALIDO)
        )

        self.assertIn(
            'django.middleware.csp.ContentSecurityPolicyMiddleware',
            settings_production.MIDDLEWARE,
        )
        self.assertEqual(settings_production.SECURE_CSP['script-src'], [CSP.SELF])
        self.assertNotIn(
            CSP.UNSAFE_INLINE,
            settings_production.SECURE_CSP['script-src'],
        )
        self.assertEqual(settings_production.EMAIL_TIMEOUT, 10)


class SesionDelPanelTrasUnLoginRealTests(TestCase):
    """SEC-15 visto desde fuera: lo que recibe el navegador tras entrar al panel.

    La prueba de configuración (`tests_configuracion.SesionDelPanelCaducaTests`)
    mira los valores. Esta mira el EFECTO, con un inicio de sesión real por el
    formulario del Admin: que la cookie sea de sesión, sin fecha (muere al
    cerrar el navegador), y que el servidor guarde la caducidad a las 8 horas.
    """

    def test_la_cookie_muere_con_el_navegador_y_el_servidor_corta_a_las_ocho_horas(self):
        from datetime import timedelta

        from django.conf import settings
        from django.contrib.auth import get_user_model
        from django.contrib.sessions.models import Session
        from django.urls import reverse
        from django.utils import timezone

        get_user_model().objects.create_user(
            'medico_sesion', password='clave-de-prueba-larga-1', is_staff=True)

        respuesta = self.client.post(reverse('admin:login'), {
            'username': 'medico_sesion',
            'password': 'clave-de-prueba-larga-1',
            'next': reverse('admin:index'),
        })

        self.assertEqual(respuesta.status_code, 302)   # entró
        cookie = respuesta.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(cookie['max-age'], '')        # sin fecha: cookie de sesión
        self.assertEqual(cookie['expires'], '')
        restante = (
            Session.objects.get(session_key=cookie.value).expire_date
            - timezone.now()
        )
        self.assertLessEqual(restante, timedelta(hours=8))
        self.assertGreater(restante, timedelta(hours=7, minutes=59))
