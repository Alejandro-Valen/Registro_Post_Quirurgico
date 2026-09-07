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
