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
    # --- Habeas data (SEC-03 · decisión D23, 08/09/2026) ---
    #
    # Hasta el 08/09/2026 este formulario guardaba nombre, teléfono y un
    # campo libre que invitaba a contar el estado de salud, SIN casilla de
    # autorización, sin finalidad declarada y sin retención. El artículo 6
    # de la Ley 1581/2012 exige autorización EXPLÍCITA para datos sensibles,
    # y los de salud lo son.
    #
    # No basta con pedir la casilla: hay que poder DEMOSTRAR después que se
    # pidió. Por eso se guarda el hecho y su fecha, no solo un booleano de
    # conveniencia que nadie pueda fechar.
    autorizacion_datos = models.BooleanField(
        default=False,
        verbose_name='Autorizó el tratamiento de sus datos',
        help_text=(
            'Marcada por la persona en el formulario público. Sin ella el '
            'envío se rechaza (Ley 1581/2012, art. 6).'
        ),
    )
    fecha_autorizacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de la autorización',
        help_text='Momento en que se marcó la casilla. Es la prueba de la autorización.',
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} - {self.fecha_creacion:%Y-%m-%d %H:%M}"
