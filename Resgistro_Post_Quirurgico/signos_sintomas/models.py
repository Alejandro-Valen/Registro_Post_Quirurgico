from django.db import models

from django.db import models


class Paciente(models.Model):
    """
    Representa a un paciente postquirúrgico del programa Sugarbaker.
    Cada paciente tiene un canal de WhatsApp único para recibir
    el bot de monitoreo diario.
    """

    # Datos de identificación
    nombre_completo = models.CharField(max_length=200)
    telefono_whatsapp = models.CharField(
        max_length=20,
        unique=True,
        help_text="Formato internacional: +573001234567"
    )

    # Datos clínicos
    fecha_cirugia = models.DateField(
        help_text="Fecha de la cirugía Sugarbaker/HIPEC"
    )
    medico_responsable = models.CharField(max_length=200)

    # Control interno
    activo = models.BooleanField(
        default=True,
        help_text="Desactivar cuando el paciente termina el seguimiento"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.nombre_completo} — Dr. {self.medico_responsable}"