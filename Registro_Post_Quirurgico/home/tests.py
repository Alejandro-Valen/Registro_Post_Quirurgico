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
