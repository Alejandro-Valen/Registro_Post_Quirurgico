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
    
class RegistroDiario(models.Model):
    """
    Captura la telemetría clínica diaria del paciente post-Sugarbaker.
    Cada registro representa una respuesta completa al bot de WhatsApp.
    Es la tabla más importante del sistema — aquí viven los datos
    que el alert_engine evalúa para detectar complicaciones.
    """

    # Relación con el paciente
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name='registros'
    )

    # Variable 1: Temperatura
    temperatura = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        help_text="Temperatura corporal en °C. Ej: 37.5"
    )

    # Variable 2: Dolor EVA
    dolor_eva = models.PositiveSmallIntegerField(
        help_text="Escala visual análoga del 1 al 10"
    )

    # Variable 3: Drenaje
    volumen_drenaje_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Volumen del drenaje en mililitros"
    )

    ASPECTO_CHOICES = [
        ('seroso',    'Seroso'),
        ('hematico',  'Hemático'),
        ('purulento', 'Purulento'),
        ('fecaloide', 'Fecaloide'),
        ('sin_drenaje', 'Sin drenaje'),
    ]
    aspecto_drenaje = models.CharField(
        max_length=20,
        choices=ASPECTO_CHOICES,
        default='sin_drenaje'
    )

    # Variable 4: Tránsito intestinal
    presencia_gases = models.BooleanField(
        default=False,
        help_text="¿El paciente reportó presencia de gases?"
    )
    episodios_nauseas = models.PositiveSmallIntegerField(
        default=0,
        help_text="Número de episodios de náuseas o vómito en 24h"
    )

    # Control de tiempo
    fecha_registro = models.DateTimeField(auto_now_add=True)
    dia_postoperatorio = models.PositiveSmallIntegerField(
        editable=False,
        default=0
    )

    class Meta:
        verbose_name = "Registro Diario"
        verbose_name_plural = "Registros Diarios"
        ordering = ["-fecha_registro"]

    def save(self, *args, **kwargs):
        # Calcula automáticamente en qué día postoperatorio está el paciente
        delta = self.fecha_registro.date() if self.fecha_registro else __import__('django.utils.timezone', fromlist=['now']).now().date()
        from django.utils import timezone
        hoy = timezone.now().date()
        self.dia_postoperatorio = (hoy - self.paciente.fecha_cirugia).days
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.paciente.nombre_completo} — Día {self.dia_postoperatorio} — {self.fecha_registro}"