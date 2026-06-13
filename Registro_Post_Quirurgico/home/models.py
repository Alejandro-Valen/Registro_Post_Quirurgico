"""
Modelos de la app home.

<<<<<<< HEAD

class MensajeContacto(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "mensaje de contacto"
        verbose_name_plural = "mensajes de contacto"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} - {self.fecha_creacion:%Y-%m-%d %H:%M}"
=======
Los modelos clínicos viven exclusivamente en signos_sintomas.models.
"""
>>>>>>> origin/Desarrollo
