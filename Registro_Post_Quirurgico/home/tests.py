from django.test import TestCase
from django.urls import reverse

from .models import MensajeContacto


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
            {"nombre": "Ana Prueba", "telefono": "+57 300 000 0000", "mensaje": "Hola"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["mensaje_enviado"])
        self.assertEqual(MensajeContacto.objects.count(), 1)

    def test_contacto_post_incompleto_no_crea(self):
        resp = self.client.post(reverse("contacto"), {"nombre": "Ana"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["mensaje_enviado"])
        self.assertEqual(MensajeContacto.objects.count(), 0)


class MensajeContactoAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
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
