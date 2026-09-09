from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import MensajeContacto
from .views import _get_client_ip


class ClientIpTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(TRUST_RAILWAY_PROXY=False)
    def test_por_defecto_ignora_headers_spoofeables(self):
        """Sin confianza declarada, `X-Real-IP` no se cree aunque venga firmada
        por el edge: la IP del cliente es la que ve el socket.

        **Por qué el `override_settings` de arriba es obligatorio.** Sus cuatro
        hermanas fijan el valor en `True`; esta comprueba el caso contrario y
        hasta el 31/07/2026 no fijaba nada — **leía el del entorno de quien
        corriera la suite**. Pasaba en verde solo porque el `.env` de desarrollo
        trae `False`, y cayó en la primera corrida de la CI, que traía `True`.

        Lo que eso significaba, y es la razón real del arreglo: si alguien
        rompiera este default seguro, la prueba solo lo denunciaría en una
        máquina cuyo `.env` tuviera la variable en `False`. **La guarda de una
        decisión de seguridad no puede depender de un archivo que no está en el
        repositorio.**
        """
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.4',
            HTTP_X_REAL_IP='198.51.100.20',
            HTTP_X_RAILWAY_EDGE='railway/us-east4-eqdc4a',
        )

        self.assertEqual(
            _get_client_ip(request),
            '10.0.0.4',
            'Sin TRUST_RAILWAY_PROXY, _get_client_ip debe devolver REMOTE_ADDR '
            'y nunca una cabecera que cualquiera puede escribir.',
        )

    @override_settings(TRUST_RAILWAY_PROXY=True)
    def test_usa_x_real_ip_solo_con_edge_railway(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.4',
            HTTP_X_REAL_IP='198.51.100.20',
            HTTP_X_RAILWAY_EDGE='railway/us-east4-eqdc4a',
        )

        self.assertEqual(_get_client_ip(request), '198.51.100.20')

    @override_settings(TRUST_RAILWAY_PROXY=True)
    def test_header_railway_ausente_conserva_remote_addr(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.4',
            HTTP_X_REAL_IP='198.51.100.20',
        )

        self.assertEqual(_get_client_ip(request), '10.0.0.4')

    @override_settings(TRUST_RAILWAY_PROXY=True)
    def test_header_railway_malformado_conserva_remote_addr(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.4',
            HTTP_X_REAL_IP='198.51.100.20',
            HTTP_X_RAILWAY_EDGE='railway/../../falso',
        )

        self.assertEqual(_get_client_ip(request), '10.0.0.4')

    @override_settings(TRUST_RAILWAY_PROXY=True)
    def test_x_real_ip_malformada_conserva_remote_addr(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.4',
            HTTP_X_REAL_IP='valor-no-valido, 198.51.100.20',
            HTTP_X_RAILWAY_EDGE='railway/us-east4-eqdc4a',
        )

        self.assertEqual(_get_client_ip(request), '10.0.0.4')


class LandingTests(TestCase):
    def test_index_renderiza(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "home/index.html")
        self.assertTemplateUsed(resp, "home/base.html")

    def test_index_incluye_estaticos_y_landing(self):
        resp = self.client.get(reverse("home"))
        contenido = resp.content.decode()
        # CSS y JS del sistema de diseño
        self.assertIn("home/css/site.css", contenido)
        self.assertIn("home/js/pulse.js", contenido)
        # Titular de la landing del médico
        self.assertIn("Nadie deber", contenido)
        # Enlace al panel del médico (admin)
        self.assertContains(resp, "Acceso médico")

    def test_index_muestra_aviso_boceto(self):
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Boceto de presentaci")


class ContactoTests(TestCase):
    def test_contacto_renderiza(self):
        resp = self.client.get(reverse("contacto"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "home/contacto.html")
        self.assertTemplateUsed(resp, "home/base.html")

    def test_contacto_post_valido_crea_mensaje(self):
        resp = self.client.post(
            reverse("contacto"),
            {"nombre": "Ana Prueba", "telefono": "+57 300 000 0000", "mensaje": "Hola",
             "autorizacion_datos": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["mensaje_enviado"])
        self.assertEqual(MensajeContacto.objects.count(), 1)
        self.assertIsNone(MensajeContacto.objects.get().medico_destinatario)

    @override_settings(MEDICO_CONTACTO_USERNAME='medico_destino')
    def test_contacto_asigna_medico_staff_configurado(self):
        medico = get_user_model().objects.create_user(
            username='medico_destino',
            password='pass',
            is_staff=True,
        )

        self.client.post(
            reverse('contacto'),
            {'nombre': 'Ana', 'telefono': '+573000000001', 'mensaje': 'Hola',
             'autorizacion_datos': '1'},
        )

        self.assertEqual(
            MensajeContacto.objects.get().medico_destinatario,
            medico,
        )

    @override_settings(MEDICO_CONTACTO_USERNAME='usuario_inexistente')
    def test_contacto_configuracion_invalida_falla_cerrado(self):
        self.client.post(
            reverse('contacto'),
            {'nombre': 'Ana', 'telefono': '+573000000001', 'mensaje': 'Hola',
             'autorizacion_datos': '1'},
        )

        self.assertIsNone(MensajeContacto.objects.get().medico_destinatario)

    def test_contacto_post_incompleto_no_crea(self):
        resp = self.client.post(reverse("contacto"), {"nombre": "Ana"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["mensaje_enviado"])
        self.assertEqual(MensajeContacto.objects.count(), 0)

    def test_contacto_falla_cerrado_si_el_cache_no_responde(self):
        """D2 (punto 2): el formulario de contacto es la única puerta sin firma
        —cualquiera en internet puede tocarla— y el rate limit es su único
        control. Si el cache no responde, debe fallar CERRADO: no se crea el
        mensaje y se muestra el aviso amable. Lo contrario dejaría el formulario
        completamente abierto al abuso ante una caída de Redis.
        """
        from unittest.mock import MagicMock, patch

        cache_caido = MagicMock()
        cache_caido.incr.side_effect = ConnectionError('redis inalcanzable')
        with patch('home.views.cache', cache_caido):
            resp = self.client.post(
                reverse("contacto"),
                {
                    "nombre": "Ana",
                    "telefono": "+573000000009",
                    "mensaje": "Hola",
                },
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["error_rate_limit"])
        self.assertEqual(MensajeContacto.objects.count(), 0)


class SaludCheckTests(TestCase):
    """D2 (punto 5): endpoint /salud/ para un monitor externo.

    Verifica base de datos y cache; devuelve 200 o 503 SIN detalle en el cuerpo
    (no filtra qué falló ni la topología interna a quien lo consulte).
    """

    def test_salud_ok_devuelve_200_sin_detalle(self):
        resp = self.client.get('/salud/')
        self.assertEqual(resp.status_code, 200)
        # Sin detalle: no revela qué se comprobó ni el estado interno.
        self.assertNotIn(b'base de datos', resp.content.lower())
        self.assertNotIn(b'cache', resp.content.lower())

    def test_salud_cache_caido_devuelve_503(self):
        from unittest.mock import MagicMock, patch

        cache_caido = MagicMock()
        cache_caido.set.side_effect = ConnectionError('redis inalcanzable')
        with patch('home.views.cache', cache_caido):
            resp = self.client.get('/salud/')

        self.assertEqual(resp.status_code, 503)

    def test_salud_bd_caida_devuelve_503(self):
        from unittest.mock import MagicMock, patch

        conexion_caida = MagicMock()
        conexion_caida.cursor.side_effect = Exception('base de datos inalcanzable')
        with patch('home.views.connection', conexion_caida):
            resp = self.client.get('/salud/')

        self.assertEqual(resp.status_code, 503)


class MensajeContactoAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command('crear_medico', verbosity=0)
        self.medico = get_user_model().objects.create_user(
            username='medico_contacto', password='pass', is_staff=True,
        )
        self.medico.groups.add(Group.objects.get(name='Médicos'))
        self.mensaje = MensajeContacto.objects.create(
            nombre='Paciente interesado',
            telefono='+573001112233',
            mensaje='Necesito información.',
            medico_destinatario=self.medico,
        )
        self.client.force_login(self.medico)

    def test_medico_solo_puede_marcar_mensaje_como_revisado(self):
        url = f'/admin/home/mensajecontacto/{self.mensaje.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url, {
            'nombre': 'Nombre manipulado',
            'telefono': '000',
            'mensaje': 'Contenido manipulado',
            'revisado': 'on',
        })
        self.assertEqual(resp.status_code, 302)

        self.mensaje.refresh_from_db()
        self.assertEqual(self.mensaje.nombre, 'Paciente interesado')
        self.assertEqual(self.mensaje.telefono, '+573001112233')
        self.assertEqual(self.mensaje.mensaje, 'Necesito información.')
        self.assertTrue(self.mensaje.revisado)

    def test_medico_no_puede_borrar_mensaje(self):
        url = f'/admin/home/mensajecontacto/{self.mensaje.pk}/delete/'
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_filtro_fecha_usa_etiqueta_precisa(self):
        resp = self.client.get('/admin/home/mensajecontacto/')
        self.assertContains(resp, 'Todas las fechas')
        self.assertNotContains(resp, 'Cualquier fecha')

    def test_medico_no_ve_mensajes_ajenos_ni_sin_asignar(self):
        otro_medico = get_user_model().objects.create_user(
            username='medico_contacto_otro', password='pass', is_staff=True,
        )
        MensajeContacto.objects.create(
            nombre='Mensaje ajeno',
            telefono='+573001112244',
            mensaje='Solo para el otro médico.',
            medico_destinatario=otro_medico,
        )
        sin_asignar = MensajeContacto.objects.create(
            nombre='Mensaje sin asignar',
            telefono='+573001112255',
            mensaje='Solo para superusuario.',
        )

        resp = self.client.get('/admin/home/mensajecontacto/')

        self.assertContains(resp, 'Paciente interesado')
        self.assertNotContains(resp, 'Mensaje ajeno')
        self.assertNotContains(resp, 'Mensaje sin asignar')
        acceso_directo = self.client.get(
            f'/admin/home/mensajecontacto/{sin_asignar.pk}/change/'
        )
        self.assertEqual(acceso_directo.status_code, 302)
        self.assertRegex(acceso_directo.url, r'^/admin/')

    def test_superusuario_ve_mensaje_sin_asignar(self):
        sin_asignar = MensajeContacto.objects.create(
            nombre='Mensaje protegido',
            telefono='+573001112266',
            mensaje='Pendiente de asignación.',
        )
        superusuario = get_user_model().objects.create_superuser(
            username='super_contacto', password='pass',
        )
        self.client.force_login(superusuario)

        url = f'/admin/home/mensajecontacto/{sin_asignar.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)


class AutorizacionHabeasDataTests(TestCase):
    """SEC-03 / D23 — el formulario público no guarda nada sin autorización.

    Reproducido el 08/09/2026: un POST anónimo guardaba *"Tengo fiebre de 39 y
    el drenaje salió con pus desde ayer"* sin casilla de autorización, sin
    finalidad declarada, sin responsable identificado y sin retención. El
    artículo 6 de la Ley 1581/2012 exige autorización **explícita** para datos
    sensibles, y los de salud lo son.

    La comprobación es de SERVIDOR y no solo `required` en el HTML: un
    `required` se salta con un POST directo, que es exactamente como se
    reprodujo el hallazgo.
    """

    DATOS = {
        'nombre': 'Persona Anónima',
        'telefono': '+573001110000',
        'mensaje': 'Quiero información sobre el programa de seguimiento.',
    }

    def setUp(self):
        # El rate limit del formulario vive en el cache, y el cache NO se
        # limpia entre pruebas: sin esto, los POST de esta clase se comen el
        # cupo por hora de la IP de pruebas y hacen caer a `ContactoTests`,
        # que corre después. Pasó de verdad al añadir estas pruebas.
        cache.clear()
        self.addCleanup(cache.clear)

    def test_sin_la_casilla_no_se_guarda_nada(self):
        respuesta = self.client.post(reverse('contacto'), self.DATOS)
        self.assertEqual(MensajeContacto.objects.count(), 0)
        self.assertTrue(respuesta.context['error_autorizacion'])
        self.assertFalse(respuesta.context['mensaje_enviado'])

    def test_con_la_casilla_se_guarda_y_queda_la_prueba(self):
        """La otra dirección. Y la autorización hay que poder DEMOSTRARLA
        después, no solo recogerla: por eso se guarda su fecha."""
        respuesta = self.client.post(
            reverse('contacto'), {**self.DATOS, 'autorizacion_datos': '1'})
        self.assertTrue(respuesta.context['mensaje_enviado'])
        mensaje = MensajeContacto.objects.get()
        self.assertTrue(mensaje.autorizacion_datos)
        self.assertIsNotNone(mensaje.fecha_autorizacion)

    def test_la_casilla_no_viene_marcada_por_defecto(self):
        """Una casilla premarcada no es autorización: es un descuido del
        usuario. El Decreto 1377/2013 lo dice sin rodeos."""
        html = self.client.get(reverse('contacto')).content.decode()
        self.assertIn('name="autorizacion_datos"', html)
        marca = html.split('name="autorizacion_datos"')[1].split('>')[0]
        self.assertNotIn('checked', marca)

    def test_el_formulario_enlaza_la_politica_de_tratamiento(self):
        """Pedir permiso sin decir para qué ni ante quién no es autorización
        informada."""
        html = self.client.get(reverse('contacto')).content.decode()
        self.assertIn(reverse('politica_datos'), html)

    def test_el_formulario_ya_no_invita_a_contar_sintomas(self):
        """Recoger con permiso es legal; recoger menos es mejor.

        El marcador decía "Cuéntanos brevemente qué necesitas…", que en una web
        de seguimiento postoperatorio es una invitación directa a escribir el
        estado de salud — y este canal no tiene ni el control de acceso ni la
        retención del resto del sistema.
        """
        html = self.client.get(reverse('contacto')).content.decode()
        self.assertNotIn('Cuéntanos brevemente qué necesitas', html)
        plano = ' '.join(html.split())
        self.assertIn('no es un canal de atención médica', plano)

    def test_la_politica_de_tratamiento_responde(self):
        respuesta = self.client.get(reverse('politica_datos'))
        self.assertEqual(respuesta.status_code, 200)

    def test_la_politica_no_inventa_al_responsable(self):
        """Identificar mal al responsable del tratamiento es peor que declararlo
        pendiente. Los datos que faltan son los mismos corchetes de P-12."""
        html = self.client.get(reverse('politica_datos')).content.decode()
        self.assertIn('[por definir]', html)
        self.assertIn('Documento en preparación', html)
