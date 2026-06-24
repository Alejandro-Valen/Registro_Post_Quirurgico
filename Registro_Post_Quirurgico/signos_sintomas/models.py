from django.db import models


class Paciente(models.Model):
    """
    Representa a un paciente en seguimiento postquirúrgico remoto.
    """
    TIPO_CIRUGIA_CHOICES = [
        ('sugarbaker_hipec',    'Sugarbaker / HIPEC'),
        ('colectomia_electiva', 'Colectomía electiva'),
        ('otra',                'Otra cirugía colorrectal'),
    ]
    nombre_completo = models.CharField(max_length=200)
    telefono_whatsapp = models.CharField(
        max_length=20,
        unique=True,
        help_text="Formato internacional: +573001234567"
    )
    fecha_cirugia = models.DateField(
        help_text="Fecha de la cirugía a la que se le da seguimiento postoperatorio."
    )
    tipo_cirugia = models.CharField(
        max_length=30,
        choices=TIPO_CIRUGIA_CHOICES,
        null=True,
        blank=True,
        help_text="Tipo de cirugía realizada — dato descriptivo para estadística "
                  "e investigación futura. No afecta el alert_engine ni el flujo del bot."
    )
    medico_responsable = models.CharField(max_length=200)
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
    Captura la telemetría clínica diaria del paciente en seguimiento
    postoperatorio.
    """
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name='registros'
    )
    temperatura = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        help_text="Temperatura corporal en °C. Ej: 37.5"
    )
    dolor_eva = models.PositiveSmallIntegerField(
        help_text="Escala visual análoga del 1 al 10"
    )
    volumen_drenaje_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Volumen en ml — OPCIONAL, solo si el paciente lo midió"
    )
    ASPECTO_CHOICES = [
        ('seroso',      'Seroso'),
        ('hematico',    'Hemático'),
        ('turbio',      'Turbio'),
        ('purulento',   'Purulento'),
        ('fecaloide',   'Fecaloide'),
        ('sin_drenaje', 'Sin drenaje'),
    ]
    CANTIDAD_DRENAJE_CHOICES = [
        ('poco',        'Poco (menos de lo normal)'),
        ('normal',      'Normal (similar a días anteriores)'),
        ('mucho',       'Mucho (más de lo normal)'),
        ('sin_drenaje', 'No tengo drenaje'),
    ]
    tiene_drenaje = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            "¿El paciente tiene drenaje activo? "
            "null = no capturado (registros anteriores a esta versión). "
            "False = confirmado sin drenaje. True = tiene drenaje."
        )
    )
    aspecto_drenaje = models.CharField(
        max_length=20,
        choices=ASPECTO_CHOICES,
        default='sin_drenaje'
    )
    cantidad_drenaje = models.CharField(
        max_length=12,
        choices=CANTIDAD_DRENAJE_CHOICES,
        null=True,
        blank=True,
        help_text="Escala cualitativa reportada por el paciente vía WhatsApp"
    )
    presencia_gases = models.BooleanField(
        default=False,
        help_text="¿El paciente reportó presencia de gases?"
    )
    episodios_nauseas = models.PositiveSmallIntegerField(
        default=0,
        help_text="Número de episodios de náuseas o vómito en 24h"
    )
    tolero_liquidos = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            "¿El paciente toleró líquidos sin vomitar? "
            "null = no capturado (registros anteriores a esta versión). "
            "False = no toleró. True = toleró."
        )
    )
    HINCHAZON_CHOICES = [
        ('nada', 'Nada'),
        ('algo', 'Algo'),
        ('mucho', 'Mucho'),
    ]
    hinchazon_abdominal = models.CharField(
        max_length=5,
        choices=HINCHAZON_CHOICES,
        null=True,
        blank=True,
        help_text=(
            "Nivel de hinchazón/distensión abdominal auto-reportado. "
            "null = no capturado. Se evalúa por empeoramiento entre días."
        )
    )
    frecuencia_cardiaca = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Frecuencia cardíaca en lpm. null = no capturado. "
            "Solo se vigila taquicardia (FC alta), no bradicardia."
        )
    )
    frecuencia_respiratoria = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Frecuencia respiratoria en rpm. null = no capturado. "
            "SOLO DASHBOARD — no genera alerta (Outersterp 2025: 77% de "
            "falsas alertas provenían del sensor de FR)."
        )
    )
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
        from django.utils import timezone
        hoy = timezone.localdate()
        # Piso en 0: un registro en el día de la cirugía o anterior (paciente
        # pre-registrado con cirugía a futuro, o typo en fecha_cirugia) nunca
        # debe producir un dia_postoperatorio negativo — violaría el CHECK del
        # PositiveSmallIntegerField y haría crashear el save() del bot. Se
        # conserva el dato para revisión del médico en vez de rechazarlo.
        self.dia_postoperatorio = max(0, (hoy - self.paciente.fecha_cirugia).days)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.paciente.nombre_completo} — Día {self.dia_postoperatorio} — {self.fecha_registro}"


class Alerta(models.Model):
    """
    Registra cada evento crítico detectado por el alert_engine.
    """
    TIPO_CHOICES = [
        ('SEPSIS',            'Fiebre — Riesgo de Sepsis'),
        ('FUGA_ANASTOMOTICA', 'Drenaje Anormal — Posible Fuga Anastomótica'),
        ('ILEO_PARALITICO',   'Sin Tránsito Intestinal — Posible Íleo Paralítico'),
        ('DOLOR_AGUDO',       'Dolor Agudo Incontrolable'),
        ('INTOLERANCIA_ORAL', 'Intolerancia a Líquidos — Riesgo de Deshidratación'),
        ('TAQUICARDIA',       'Frecuencia Cardíaca Elevada — Taquicardia'),
    ]
    SEVERIDAD_CHOICES = [
        ('ALTA',  'Alta — Ir a urgencias'),
        ('MEDIA', 'Media — Llamar al médico'),
        ('BAJA',  'Baja — Monitorear'),
    ]
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name='alertas'
    )
    registro_origen = models.ForeignKey(
        RegistroDiario,
        on_delete=models.PROTECT,
        related_name='alertas',
        help_text="El registro diario que disparó esta alerta"
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    severidad = models.CharField(max_length=10, choices=SEVERIDAD_CHOICES)
    mensaje = models.TextField(
        help_text="Descripción automática generada por el alert_engine"
    )
    resuelta = models.BooleanField(
        default=False,
        help_text="El oncólogo marca esto cuando atiende la alerta"
    )
    fecha_alerta = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Cuándo fue atendida por el médico"
    )

    class Meta:
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        ordering = ["-fecha_alerta"]

    def __str__(self):
        estado = "Resuelta" if self.resuelta else "ACTIVA"
        return f"[{estado}] {self.get_tipo_display()} — {self.paciente.nombre_completo}"


class ConversacionWhatsApp(models.Model):
    """
    Mantiene el estado de la conversación diaria del bot con un paciente.

    Cada mensaje de WhatsApp (vía Twilio) llega como una petición HTTP
    independiente, así que el estado de la máquina de estados debe persistir
    en BD. Las respuestas se acumulan en campos 'temp_' hasta COMPLETADO,
    momento en que bot.py crea el RegistroDiario y dispara el alert_engine.
    """

    # --- Estados de la máquina (10 preguntas) ---
    ESTADO_INICIO            = 'INICIO'
    ESTADO_TEMPERATURA       = 'ESPERANDO_TEMPERATURA'
    ESTADO_DOLOR             = 'ESPERANDO_DOLOR'
    ESTADO_TIENE_DRENAJE     = 'ESPERANDO_TIENE_DRENAJE'
    ESTADO_ASPECTO_DRENAJE   = 'ESPERANDO_ASPECTO_DRENAJE'
    ESTADO_CANTIDAD_DRENAJE  = 'ESPERANDO_CANTIDAD_DRENAJE'
    ESTADO_GASES_NAUSEAS     = 'ESPERANDO_GASES_NAUSEAS'
    ESTADO_HINCHAZON         = 'ESPERANDO_HINCHAZON'
    ESTADO_FRECUENCIA_CARDIACA = 'ESPERANDO_FRECUENCIA_CARDIACA'
    ESTADO_FRECUENCIA_RESPIRATORIA = 'ESPERANDO_FRECUENCIA_RESPIRATORIA'
    ESTADO_TOLERANCIA_LIQUIDOS = 'ESPERANDO_TOLERANCIA_LIQUIDOS'
    ESTADO_COMPLETADO        = 'COMPLETADO'

    ESTADO_CHOICES = [
        (ESTADO_INICIO,           'Inicio'),
        (ESTADO_TEMPERATURA,      'Esperando temperatura'),
        (ESTADO_DOLOR,            'Esperando dolor EVA'),
        (ESTADO_TIENE_DRENAJE,    'Esperando si tiene drenaje'),
        (ESTADO_ASPECTO_DRENAJE,  'Esperando aspecto del drenaje'),
        (ESTADO_CANTIDAD_DRENAJE, 'Esperando cantidad del drenaje'),
        (ESTADO_GASES_NAUSEAS,    'Esperando gases y náuseas'),
        (ESTADO_HINCHAZON,        'Esperando hinchazón abdominal'),
        (ESTADO_FRECUENCIA_CARDIACA, 'Esperando frecuencia cardíaca'),
        (ESTADO_FRECUENCIA_RESPIRATORIA, 'Esperando frecuencia respiratoria'),
        (ESTADO_TOLERANCIA_LIQUIDOS, 'Esperando tolerancia a líquidos'),
        (ESTADO_COMPLETADO,       'Completado'),
    ]

    paciente = models.OneToOneField(
        Paciente,
        on_delete=models.PROTECT,
        related_name='conversacion',
        help_text="Cada paciente tiene una sola conversación activa con el bot"
    )
    estado = models.CharField(
        max_length=40,
        choices=ESTADO_CHOICES,
        default=ESTADO_INICIO,
    )

    # --- Respuestas parciales del día (se reinician en cada ciclo diario) ---
    temp_temperatura = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    temp_dolor_eva = models.PositiveSmallIntegerField(null=True, blank=True)
    temp_tiene_drenaje = models.BooleanField(null=True, blank=True)
    temp_aspecto_drenaje = models.CharField(
        max_length=20, choices=RegistroDiario.ASPECTO_CHOICES,
        null=True, blank=True
    )
    temp_cantidad_drenaje = models.CharField(
        max_length=12, choices=RegistroDiario.CANTIDAD_DRENAJE_CHOICES,
        null=True, blank=True
    )
    temp_volumen_drenaje_ml = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="ml extraídos del mensaje si el paciente los agregó (opcional)"
    )
    temp_presencia_gases = models.BooleanField(null=True, blank=True)
    temp_episodios_nauseas = models.PositiveSmallIntegerField(null=True, blank=True)
    temp_hinchazon_abdominal = models.CharField(
        max_length=5, null=True, blank=True
    )
    temp_frecuencia_cardiaca = models.PositiveSmallIntegerField(
        null=True, blank=True
    )
    temp_frecuencia_respiratoria = models.PositiveSmallIntegerField(
        null=True, blank=True
    )
    temp_tolero_liquidos = models.BooleanField(null=True, blank=True)

    # --- Control "un registro por día" ---
    fecha_ultimo_registro = models.DateField(
        null=True, blank=True,
        help_text="Día en que el paciente completó su último registro"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversación WhatsApp"
        verbose_name_plural = "Conversaciones WhatsApp"

    def __str__(self):
        return f"{self.paciente.nombre_completo} — {self.get_estado_display()}"