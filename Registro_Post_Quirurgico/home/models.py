from django.conf import settings
from django.db import models

# Los modelos clínicos viven exclusivamente en signos_sintomas/models.py

class MensajeContacto(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField()
    medico_destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mensajes_contacto",
        verbose_name="Médico destinatario",
        help_text=(
            "Médico que puede consultar y marcar este mensaje. "
            "Sin asignar significa visible solo para el superusuario."
        ),
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} - {self.fecha_creacion:%Y-%m-%d %H:%M}"
