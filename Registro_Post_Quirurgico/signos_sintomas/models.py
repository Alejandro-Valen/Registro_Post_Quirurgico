from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q


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
    cedula = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Cédula",
        help_text=(
            "Número de documento de identidad — identificador principal del "
            "paciente (P-4, decisión 01/07/2026). Obligatorio para pacientes "
            "nuevos (exigido por clean(), A-2); null solo permitido en "
            "registros previos a esta versión. blank=True a nivel de campo "
            "porque full_clean() no debe fallar para pacientes existentes "
            "sin cédula — la exigencia para pacientes nuevos vive en clean()."
        ),
    )
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
    medico_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pacientes',
        help_text="Usuario del sistema (médico) responsable del paciente. "
                  "Debe existir como usuario en Django Admin."
    )
    activo = models.BooleanField(
        default=True,
        help_text="Desactivar cuando el paciente termina el seguimiento"
    )
    consentimiento_informado = models.BooleanField(
        default=False,
        verbose_name="Consentimiento informado",
        help_text=(
            "El paciente autorizó el tratamiento de sus datos de salud (Ley 1581/2012). "
            "Marcar solo después de obtener la firma física del formato de consentimiento. "
            "Desmarcar si el paciente revoca su autorización."
        ),
    )
    fecha_consentimiento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de consentimiento",
        help_text="Se registra automáticamente al marcar el consentimiento informado.",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["-fecha_registro"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(tipo_cirugia__isnull=True)
                    | Q(tipo_cirugia__in=['sugarbaker_hipec', 'colectomia_electiva', 'otra'])
                ),
                name='paciente_tipo_cirugia_valido',
            ),
        ]

    def clean(self):
        """A-2: exige cédula en pacientes nuevos. Los pacientes migrados
        (pk existente, cedula=None) quedan como están — no se les exige
        retroactivamente."""
        super().clean()
        if self.pk is None and not self.cedula:
            raise ValidationError({
                'cedula': 'La cédula es obligatoria para pacientes nuevos.'
            })

    def __str__(self):
        if self.medico_responsable is None:
            return f"{self.nombre_completo} — Sin médico asignado"
        medico = (self.medico_responsable.get_full_name()
                  or self.medico_responsable.username)
        return f"{self.nombre_completo} — Dr. {medico}"


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
    fecha_registro = models.DateTimeField(auto_now_add=True, db_index=True)
    dia_postoperatorio = models.PositiveSmallIntegerField(
        editable=False,
        default=0
    )

    class Meta:
        verbose_name = "Registro Diario"
        verbose_name_plural = "Registros Diarios"
        ordering = ["-fecha_registro"]
        constraints = [
            CheckConstraint(
                condition=Q(aspecto_drenaje__in=[
                    'seroso', 'hematico', 'turbio', 'purulento', 'fecaloide', 'sin_drenaje',
                ]),
                name='registrodiario_aspecto_drenaje_valido',
            ),
            CheckConstraint(
                condition=(
                    Q(cantidad_drenaje__isnull=True)
                    | Q(cantidad_drenaje__in=['poco', 'normal', 'mucho', 'sin_drenaje'])
                ),
                name='registrodiario_cantidad_drenaje_valido',
            ),
            CheckConstraint(
                condition=(
                    Q(hinchazon_abdominal__isnull=True)
                    | Q(hinchazon_abdominal__in=['nada', 'algo', 'mucho'])
                ),
                name='registrodiario_hinchazon_abdominal_valido',
            ),
        ]

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
        ('SILENCIO',          'Paciente Sin Respuesta — Check-in No Completado'),
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
        null=True,
        blank=True,
        help_text="El registro diario que disparó esta alerta. Null para alertas SILENCIO (sin respuesta)."
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
    veces = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Detecciones",
        help_text=(
            "En cuántos check-ins se ha detectado este problema mientras la "
            "alerta sigue abierta (contador de recurrencia). 1 = primera vez."
        ),
    )
    fecha_ultima_deteccion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última detección",
        help_text=(
            "Último check-in en que se volvió a detectar el problema. "
            "fecha_alerta = primera detección; esta = la más reciente."
        ),
    )
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Cuándo fue atendida por el médico"
    )

    # Motivo de resolución (Bloque A, 02/07/2026) — el médico lo selecciona
    # obligatoriamente al marcar la alerta como resuelta. Útil para ajustar
    # umbrales clínicos con datos reales en el futuro.
    MOTIVO_CONTACTO    = 'CONTACTO'
    MOTIVO_URGENCIAS   = 'URGENCIAS'
    MOTIVO_MEDICACION  = 'MEDICACION'
    MOTIVO_FP_MEDICION = 'FP_MEDICION'
    MOTIVO_FP_RANGO    = 'FP_RANGO'
    MOTIVO_ESPONTANEO  = 'ESPONTANEO'
    MOTIVO_OTRO        = 'OTRO'

    MOTIVOS_RESOLUCION = [
        (MOTIVO_CONTACTO,    'Atendido — contacté al paciente'),
        (MOTIVO_URGENCIAS,   'Atendido — derivado a urgencias'),
        (MOTIVO_MEDICACION,  'Atendido — ajuste de medicación'),
        (MOTIVO_FP_MEDICION, 'Falso positivo — error de medición del paciente'),
        (MOTIVO_FP_RANGO,    'Falso positivo — dato fuera de rango esperado'),
        (MOTIVO_ESPONTANEO,  'Resuelto espontáneamente — sin intervención'),
        (MOTIVO_OTRO,        'Otro'),
    ]

    motivo_resolucion = models.CharField(
        max_length=20,
        choices=MOTIVOS_RESOLUCION,
        null=True,
        blank=True,
        verbose_name='Motivo de resolución',
        help_text=(
            'Por qué se marcó esta alerta como resuelta. '
            'Útil para ajustar umbrales clínicos con datos reales en el futuro.'
        ),
    )
    motivo_resolucion_detalle = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='Detalle del motivo',
        help_text='Solo requerido cuando el motivo es "Otro".',
    )

    class Meta:
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        ordering = ["-fecha_alerta"]
        constraints = [
            CheckConstraint(
                condition=Q(tipo__in=[
                    'SEPSIS', 'FUGA_ANASTOMOTICA', 'ILEO_PARALITICO',
                    'DOLOR_AGUDO', 'INTOLERANCIA_ORAL', 'TAQUICARDIA', 'SILENCIO',
                ]),
                name='alerta_tipo_valido',
            ),
            CheckConstraint(
                condition=Q(severidad__in=['ALTA', 'MEDIA', 'BAJA']),
                name='alerta_severidad_valida',
            ),
        ]

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


class CheckInProgramado(models.Model):
    """
    Representa un evento de check-in programado para un paciente activo.

    El scheduler crea 2 instancias por paciente activo cada día (mañana y
    tarde). El bot las completa cuando el paciente responde. Si el paciente
    no responde, el scheduler las cierra como NO_RESPONDIDO y el engine
    genera una alerta de silencio.

    Decisiones de diseño (cerradas Sprint 4 — no re-discutir):
    - fecha_dia se congela al crear; nunca se recalcula en save() para evitar
      el bug de cruce de medianoche.
    - El turno se etiqueta por evento (lo fija el scheduler), nunca por la
      hora en que el paciente responde.
    - Solo se persisten datos crudos (hora_programada, fecha_respuesta);
      latencia y % tardío se derivan en el dashboard.
    """

    ESTADO_PENDIENTE     = 'PENDIENTE'
    ESTADO_COMPLETADO    = 'COMPLETADO'
    ESTADO_NO_RESPONDIDO = 'NO_RESPONDIDO'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE,     'Pendiente'),
        (ESTADO_COMPLETADO,    'Completado'),
        (ESTADO_NO_RESPONDIDO, 'No respondido'),
    ]

    ETIQUETA_MANANA = 'MAÑANA'
    ETIQUETA_TARDE  = 'TARDE'
    ETIQUETA_CHOICES = [
        (ETIQUETA_MANANA, 'Mañana'),
        (ETIQUETA_TARDE,  'Tarde'),
    ]

    paciente        = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT,
        related_name='checkins',
    )
    fecha_dia       = models.DateField(
        help_text="Día calendario del evento. Se congela al crear — no se recalcula en save()."
    )
    orden           = models.PositiveSmallIntegerField(
        help_text="Posición del check-in en el día: 1=mañana, 2=tarde. Clave robusta del sistema."
    )
    etiqueta        = models.CharField(
        max_length=10,
        choices=ETIQUETA_CHOICES,
        help_text="Etiqueta legible para el médico. La fija el scheduler al crear el evento."
    )
    hora_programada = models.DateTimeField(
        help_text="Momento en que el sistema disparó (o debía disparar) el prompt al paciente."
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento en que el paciente completó el flujo. null = aún no respondió."
    )
    estado          = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDIENTE,
    )
    registro        = models.OneToOneField(
        RegistroDiario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkin',
        help_text="RegistroDiario creado al completar el flujo. Se vincula en transacción atómica."
    )

    class Meta:
        verbose_name        = "Check-in Programado"
        verbose_name_plural = "Check-ins Programados"
        ordering            = ['fecha_dia', 'orden']
        constraints = [
            models.UniqueConstraint(
                fields=['paciente', 'fecha_dia', 'orden'],
                name='unique_checkin_paciente_dia_orden',
            ),
            CheckConstraint(
                condition=Q(estado__in=['PENDIENTE', 'COMPLETADO', 'NO_RESPONDIDO']),
                name='checkin_estado_valido',
            ),
            CheckConstraint(
                condition=Q(etiqueta__in=['MAÑANA', 'TARDE']),
                name='checkin_etiqueta_valida',
            ),
        ]

    def __str__(self):
        return f"{self.paciente} — {self.fecha_dia} {self.etiqueta} ({self.estado})"