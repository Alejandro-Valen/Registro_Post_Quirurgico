"""Pruebas de la configuración de arranque — Loop C, hallazgos 6 y 11.

Estas pruebas NO leen `django.conf.settings`: ese objeto ya quedó fijado cuando
arrancó la suite, con el `.env` de quien la ejecuta. Lo que se verifica aquí es
cómo el proyecto **decide** su configuración a partir del entorno, así que cada
caso carga una copia fresca del módulo de settings con las variables parcheadas.

La copia se ejecuta con un nombre propio y NO se registra en `sys.modules`: la
configuración real del proceso de pruebas queda intacta.
"""
import importlib.util
import os
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

_RUTA_PAQUETE = Path(__file__).resolve().parent

# Entorno mínimo y bien formado para producción. Cada prueba parte de aquí y
# daña UNA variable, para que el fallo señale sin ambigüedad a esa variable.
_ENTORNO_PRODUCCION_VALIDO = {
    'CSRF_TRUSTED_ORIGINS': 'https://ejemplo.up.railway.app',
    'REDIS_URL': 'redis://localhost:6379/1',
    'EMAIL_DELIVERY_PROVIDER': 'resend',
    'RESEND_API_KEY': 'clave-de-prueba-no-real',
    'RESEND_FROM_EMAIL': 'avisos@ejemplo.com',
}


def _cargar_settings(archivo, entorno, alias):
    """Ejecuta una copia del módulo de settings con `entorno` parcheado."""
    spec = importlib.util.spec_from_file_location(
        'Registro_Post_Quirurgico.{}'.format(alias),
        _RUTA_PAQUETE / archivo,
    )
    modulo = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, entorno):
        spec.loader.exec_module(modulo)
    return modulo


def _cargar_settings_base(entorno):
    return _cargar_settings('settings.py', entorno, 'copia_settings_base')


def _cargar_settings_produccion(entorno):
    return _cargar_settings(
        'settings_production.py', entorno, 'copia_settings_produccion'
    )


class ConfianzaCabecerasProxyTests(SimpleTestCase):
    """Hallazgo 6 — la confianza en cabeceras de proxy debe ser explícita.

    `USE_X_FORWARDED_HOST` y `SECURE_PROXY_SSL_HEADER` hacen que Django crea lo
    que digan `X-Forwarded-Host` y `X-Forwarded-Proto`. Hoy están activas en la
    configuración base, es decir en TODO despliegue, mientras la IP del cliente
    (`home.views._get_client_ip`) sí exige declarar la confianza. Un mismo
    interruptor debe gobernar las tres cabeceras.
    """

    def test_sin_confianza_declarada_no_se_honran_las_cabeceras(self):
        base = _cargar_settings_base({'TRUST_RAILWAY_PROXY': 'False'})

        self.assertFalse(base.USE_X_FORWARDED_HOST)
        self.assertIsNone(base.SECURE_PROXY_SSL_HEADER)

    def test_con_confianza_declarada_se_honran_las_cabeceras(self):
        """Railway y el túnel de ngrok deben seguir funcionando al declararlo.

        Sin `SECURE_PROXY_SSL_HEADER`, Django ve HTTP detrás del edge: con
        `SECURE_SSL_REDIRECT=True` eso es un bucle de redirecciones, y sin
        `USE_X_FORWARDED_HOST` la URL reconstruida no coincide con la que Twilio
        firmó.
        """
        base = _cargar_settings_base({'TRUST_RAILWAY_PROXY': 'True'})

        self.assertTrue(base.USE_X_FORWARDED_HOST)
        self.assertEqual(
            base.SECURE_PROXY_SSL_HEADER,
            ('HTTP_X_FORWARDED_PROTO', 'https'),
        )

    def test_el_interruptor_existe_en_la_configuracion_base(self):
        """Un solo interruptor para IP, host y esquema — también en desarrollo.

        Hoy `TRUST_RAILWAY_PROXY` solo se define en `settings_production`, así
        que en desarrollo `_get_client_ip` cae al `getattr(..., False)` y no hay
        forma de declarar la confianza al usar ngrok.
        """
        from django.conf import settings

        self.assertIsInstance(getattr(settings, 'TRUST_RAILWAY_PROXY', None), bool)


class VariablesEntornoVaciasTests(SimpleTestCase):
    """Hallazgo 11 — una variable definida pero vacía debe detener el arranque.

    `config('X')` solo falla cuando la variable NO existe. Si existe vacía
    devuelve '' y el proceso arranca con una configuración inválida que falla
    mucho después, lejos de la causa. El caso del placeholder pegado literal
    (`<...>`) ya ocurrió en Railway: fue la causa raíz del 403 de Twilio y de
    los login fallidos al Admin (BITACORA, 06/07/2026).
    """

    def test_secret_key_vacia_detiene_el_arranque(self):
        with self.assertRaises(ImproperlyConfigured) as cm:
            _cargar_settings_base({'SECRET_KEY': ''})

        self.assertIn('SECRET_KEY', str(cm.exception))

    def test_secret_key_con_placeholder_detiene_el_arranque(self):
        with self.assertRaises(ImproperlyConfigured) as cm:
            _cargar_settings_base({'SECRET_KEY': '<tu-clave-secreta>'})

        self.assertIn('SECRET_KEY', str(cm.exception))

    def test_credencial_de_base_de_datos_en_blanco_detiene_el_arranque(self):
        with self.assertRaises(ImproperlyConfigured) as cm:
            _cargar_settings_base({'DB_NAME': '   '})

        self.assertIn('DB_NAME', str(cm.exception))

    def test_entorno_base_bien_formado_carga_sin_errores(self):
        """Guarda contra una validación demasiado celosa: el .env real carga."""
        base = _cargar_settings_base({})

        self.assertTrue(base.SECRET_KEY)
        self.assertTrue(base.DATABASES['default']['NAME'])

    def test_clave_de_resend_vacia_detiene_el_arranque(self):
        entorno = dict(_ENTORNO_PRODUCCION_VALIDO, RESEND_API_KEY='')

        with self.assertRaises(ImproperlyConfigured) as cm:
            _cargar_settings_produccion(entorno)

        self.assertIn('RESEND_API_KEY', str(cm.exception))

    def test_origenes_csrf_vacios_detienen_el_arranque(self):
        """Sin CSRF_TRUSTED_ORIGINS el médico no puede ni entrar al panel.

        Con DEBUG=False y cookies seguras, el POST del login devuelve 403 sin
        explicación: el fallo aparece en la cara del médico, no al desplegar.
        """
        entorno = dict(_ENTORNO_PRODUCCION_VALIDO, CSRF_TRUSTED_ORIGINS='')

        with self.assertRaises(ImproperlyConfigured) as cm:
            _cargar_settings_produccion(entorno)

        self.assertIn('CSRF_TRUSTED_ORIGINS', str(cm.exception))

    def test_produccion_con_entorno_completo_carga_sin_errores(self):
        """Guarda contra una validación demasiado celosa: producción arranca."""
        produccion = _cargar_settings_produccion(dict(_ENTORNO_PRODUCCION_VALIDO))

        self.assertFalse(produccion.DEBUG)
        self.assertEqual(produccion.RESEND_FROM_EMAIL, 'avisos@ejemplo.com')
