import json
from datetime import timedelta

from django import forms as django_forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .management.commands.desactivar_pacientes_vencidos import DIAS_SEGUIMIENTO
from .models import (
    Alerta,
    CheckInProgramado,
    DeteccionAlerta,
    NotificacionAlerta,
    Paciente,
    RecepcionWebhookTwilio,
    RegistroDiario,
)


class MotivoResolucionForm(django_forms.Form):
    """Formulario intermedio de la acción 'Marcar como resuelta' (Bloque A).
    Captura el motivo obligatorio y, solo para 'Otro', un detalle libre.

    Los pk seleccionados NO viajan en el form: se leen de request.POST
    ('_selected_action', el mismo nombre que usa el admin) y se re-filtran
    por permisos en la acción, para no confiar en input del cliente."""
    motivo_resolucion = django_forms.ChoiceField(
        choices=Alerta.MOTIVOS_RESOLUCION_USUARIO,
        initial=Alerta.MOTIVO_CONTACTO,
        label='Motivo de resolución',
    )
    motivo_resolucion_detalle = django_forms.CharField(
        max_length=500,
        required=False,
        label='Detalle (solo si seleccionó "Otro")',
        widget=django_forms.Textarea(attrs={'rows': 2}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('motivo_resolucion') == Alerta.MOTIVO_OTRO \
                and not cleaned.get('motivo_resolucion_detalle'):
            raise django_forms.ValidationError(
                'Debes especificar el detalle cuando el motivo es "Otro".'
            )
        return cleaned


def _solo_propios(request):
    """True si el usuario debe ver solo sus propios datos (no superuser)."""
    return not request.user.is_superuser


class MedicoResponsableListFilter(admin.RelatedFieldListFilter):
    """Filtro por médico responsable, visible solo para el superusuario.

    El filtro estándar de Django se arma con TODOS los usuarios de la base, no
    con los que el usuario puede ver: a un médico le mostraba en la barra
    lateral los nombres de cuenta de sus colegas y del superusuario (hallazgo
    8). El listado en sí nunca estuvo comprometido — sigue acotado a sus
    pacientes— y por eso mismo el filtro tampoco le sirve de nada.

    Sin opciones, `has_output()` da False y el Admin no dibuja el filtro. Para
    el superusuario no cambia nada: conserva la lista completa y la opción
    "sin asignar". Si un médico llega con el parámetro escrito a mano en la
    URL, se ignora y el `get_queryset` del ModelAdmin lo sigue acotando.
    """

    def field_choices(self, field, request, model_admin):
        if _solo_propios(request):
            return []
        return super().field_choices(field, request, model_admin)


class TodasLasFechasListFilter(admin.DateFieldListFilter):
    def choices(self, changelist):
        for indice, choice in enumerate(super().choices(changelist)):
            if indice == 0:
                choice = {**choice, 'display': 'Todas las fechas'}
            yield choice


DIAS_HISTORIAL_DEFAULT = 7
DIAS_HISTORIAL_OPCIONES = [3, 7, 10]


def _clamp_dias_historial(valor):
    """Acepta solo los periodos definidos para el seguimiento de 10 días."""
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return DIAS_HISTORIAL_DEFAULT
    return dias if dias in DIAS_HISTORIAL_OPCIONES else DIAS_HISTORIAL_DEFAULT


def _selector_dias_historial(dias_actual):
    """Enlaces 3/7/10 días, alineados con la ventana de seguimiento."""
    enlaces = []
    for dias in DIAS_HISTORIAL_OPCIONES:
        if dias == dias_actual:
            enlaces.append(f'<strong>{dias} días</strong>')
        else:
            enlaces.append(f'<a href="?dias={dias}">{dias} días</a>')
    return f'<p style="margin:0 0 6px;">Ver: {" · ".join(enlaces)}</p>'


def _turnos_por_registro(registros):
    """
    Mapa {registro.pk: 'M'/'T'} usando el CheckInProgramado vinculado —
    el turno lo fija el evento programado, nunca la hora en que el
    paciente respondió (decisión D2, Sprint 3.6: ROADMAP FASE 3.6).
    Fallback por hora (< 12 = mañana) solo para registros legado sin
    CheckInProgramado vinculado (datos previos a Sprint 4).
    """
    etiqueta_por_registro = dict(
        CheckInProgramado.objects
        .filter(registro__in=registros)
        .values_list('registro_id', 'etiqueta')
    )
    turnos = {}
    for r in registros:
        etiqueta = etiqueta_por_registro.get(r.pk)
        if etiqueta == CheckInProgramado.ETIQUETA_MANANA:
            turnos[r.pk] = 'M'
        elif etiqueta == CheckInProgramado.ETIQUETA_TARDE:
            turnos[r.pk] = 'T'
        else:
            # USE_TZ=True: fecha_registro llega en UTC — convertir a hora
            # local (Bogotá) antes de comparar, o el respaldo clasifica
            # mal el turno de registros creados cerca de medianoche/mañana.
            hora_local = timezone.localtime(r.fecha_registro).hour
            turnos[r.pk] = 'M' if hora_local < 12 else 'T'
    return turnos


def _historial_paciente(paciente, dias=DIAS_HISTORIAL_DEFAULT):
    """Devuelve HTML con selector de rango + tabla de registros del paciente."""
    selector = _selector_dias_historial(dias)
    desde = timezone.localdate() - timedelta(days=dias - 1)
    registros = list(
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=desde)
        .order_by('-fecha_registro')
    )
    if not registros:
        return selector + f'<p style="color:#6b7280;">Sin registros en los últimos {dias} días.</p>'

    turnos = _turnos_por_registro(registros)
    filas = []
    for r in registros:
        fecha = timezone.localtime(r.fecha_registro).strftime('%d/%m') + f' {turnos[r.pk]}'
        filas.append(
            f'<tr>'
            f'<td>{fecha}</td>'
            f'<td>POD {r.dia_postoperatorio}</td>'
            f'<td>{r.temperatura} °C</td>'
            f'<td>{r.dolor_eva}/10</td>'
            f'<td>{"Sí" if r.presencia_gases else "No"}</td>'
            f'<td>{r.episodios_nauseas}</td>'
            f'<td>{r.get_aspecto_drenaje_display() if r.tiene_drenaje else "—"}</td>'
            f'<td>{"Sí" if r.tolero_liquidos else ("No" if r.tolero_liquidos is False else "—")}</td>'
            f'<td>{r.frecuencia_cardiaca if r.frecuencia_cardiaca else "—"} lpm</td>'
            f'</tr>'
        )

    tabla = (
        '<table style="width:100%;border-collapse:collapse;font-size:0.85em;">'
        '<thead><tr style="background:#f3f4f6;">'
        '<th>Fecha</th><th>POD</th><th>Temp.</th><th>Dolor EVA</th>'
        '<th>Gases</th><th>Náuseas</th><th>Drenaje</th><th>Toleró liq.</th>'
        '<th>FC</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(filas) + '</tbody>'
        '</table>'
    )
    return selector + tabla


DIAS_GRAFICA_OPCIONES = [3, 7, 10]


def _datos_grafica(paciente, dias):
    """
    Arma los datos (labels/temps/evas/fcs/alertas_idx) para graficar los
    últimos `dias` días de un paciente. Todo lo que va a JSON pasa por
    json.dumps() en el llamador — nunca se interpola directo en el HTML.
    """
    desde = timezone.localdate() - timedelta(days=dias - 1)
    registros = list(
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=desde)
        .order_by('fecha_registro')
    )
    if not registros:
        return {'labels': [], 'temps': [], 'evas': [], 'fcs': [], 'alertas_idx': []}

    turnos = _turnos_por_registro(registros)
    # Una sola query batched — evita N+1 y no depende del related_name
    # equivocado ("alerta_set") que traía el borrador original.
    ids_con_alerta_alta = set(
        Alerta.objects
        .filter(registro_origen__in=registros, severidad='ALTA', resuelta=False)
        .values_list('registro_origen_id', flat=True)
    )

    labels, temps, evas, fcs, alertas_idx = [], [], [], [], []
    for i, r in enumerate(registros):
        labels.append(timezone.localtime(r.fecha_registro).strftime('%d/%m') + f' {turnos[r.pk]}')
        temps.append(float(r.temperatura))
        evas.append(r.dolor_eva)
        fcs.append(r.frecuencia_cardiaca)  # None se serializa como null — Chart.js abre un hueco, no cae a 0
        if r.pk in ids_con_alerta_alta:
            alertas_idx.append(i)

    return {'labels': labels, 'temps': temps, 'evas': evas, 'fcs': fcs, 'alertas_idx': alertas_idx}


_HTML_GRAFICAS_TEMPLATE = """
<div class="js-graficas-signos" data-paciente="{paciente_id}"
     data-graficas="{datos}" style="margin-top:8px;">
  <div style="margin-bottom:12px;font-size:0.85em;">
    Ver:
    <button type="button" class="js-grafica-periodo" data-dias="3"
            aria-pressed="false" style="border:0;background:none;padding:0;color:#6b7280;cursor:pointer;">3 días</button> ·
    <button type="button" class="js-grafica-periodo" data-dias="7"
            aria-pressed="true" style="border:0;background:none;padding:0;font-weight:600;color:#374151;cursor:pointer;">7 días</button> ·
    <button type="button" class="js-grafica-periodo" data-dias="10"
            aria-pressed="false" style="border:0;background:none;padding:0;color:#6b7280;cursor:pointer;">10 días</button>
  </div>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;display:flex;justify-content:space-between;">
    <span>Temperatura (°C)</span>
    <span style="color:#fca5a5;">- - umbral fiebre: 37.9°C</span>
  </div>
  <canvas data-serie="temperatura" height="90" style="width:100%;margin-bottom:16px;"></canvas>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;">Dolor EVA (1-10)</div>
  <canvas data-serie="dolor" height="90" style="width:100%;margin-bottom:16px;"></canvas>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;display:flex;justify-content:space-between;">
    <span>Frecuencia cardíaca (lpm)</span>
    <span style="color:#6b7280;">- - 101 lpm  · - - 110 lpm</span>
  </div>
  <canvas data-serie="frecuencia" height="90" style="width:100%;margin-bottom:8px;"></canvas>
  <p style="font-size:0.75em;color:#9ca3af;margin:4px 0 0;">
    Puntos rojos = alerta ALTA sin resolver ese registro. Huecos en la
    línea = el paciente no midió ese dato ese día (no es un valor de 0).
  </p>
</div>
"""


def _grafica_signos_vitales(paciente):
    """
    Devuelve HTML con 3 gráficas Chart.js (temperatura, dolor EVA, FC) con
    selector de período 3/7/10 días que cambia en el navegador sin
    recargar la página (P-9, rediseño 01/07/2026).

    Los 3 períodos se precalculan en Python y se serializan una sola vez
    con json.dumps() en un objeto DATOS — nunca se interpola una lista
    Python directo en el HTML/JS (regla de seguridad, BITACORA 01/07/2026).
    """
    tiene_datos = RegistroDiario.objects.filter(paciente=paciente).exists()
    if not tiene_datos:
        return '<p style="color:#6b7280;">Sin datos para graficar todavía.</p>'

    datos = {str(dias): _datos_grafica(paciente, dias) for dias in DIAS_GRAFICA_OPCIONES}
    return format_html(
        _HTML_GRAFICAS_TEMPLATE,
        datos=json.dumps(datos, separators=(',', ':')),
        paciente_id=paciente.pk,
    )


class TieneAlertaActivaFilter(admin.SimpleListFilter):
    """Filtro de pacientes por alertas sin resolver."""
    title = 'alertas activas'
    parameter_name = 'alerta_activa'

    def lookups(self, request, model_admin):
        return [
            ('si', 'Con alertas sin resolver'),
            ('no', 'Sin alertas pendientes'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'si':
            return queryset.filter(alertas__resuelta=False).distinct()
        if self.value() == 'no':
            return queryset.exclude(alertas__resuelta=False).distinct()
        return queryset


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'cedula', 'medico_nombre',
                    'fecha_cirugia', 'activo']
    list_filter = [
        'activo',
        'tipo_cirugia',
        ('medico_responsable', MedicoResponsableListFilter),
        TieneAlertaActivaFilter,
    ]
    search_fields = ['nombre_completo', 'cedula', 'telefono_whatsapp',
                     'medico_responsable__first_name',
                     'medico_responsable__last_name',
                     'medico_responsable__username']
    readonly_fields = ['fecha_consentimiento', 'grafica_signos_vitales', 'historial_paciente']

    class Media:
        js = (
            'admin/js/vendor/chart.umd.min.js',
            'admin/js/graficas_signos_vitales.js',
        )

    def get_readonly_fields(self, request, obj=None):
        # Captura ?dias= de la URL para que historial_paciente() lo use al
        # renderizar — los readonly_fields solo reciben `obj`, no `request`.
        # La gráfica (grafica_signos_vitales) tiene su propio selector de
        # período independiente, en el navegador — no usa este parámetro.
        self._dias_historial = _clamp_dias_historial(request.GET.get('dias'))
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        """A-1: advierte al médico si registra un paciente con ingreso tardío
        — el comando desactivar_pacientes_vencidos lo desactivaría pronto.
        Bloque 7 (HABEAS DATA): registra/limpia fecha_consentimiento en
        sincronía con el checkbox de consentimiento_informado.
        D12 (capa 1): última red antes de la base — un médico no-superusuario
        solo puede asignarse a sí mismo, así que no tiene sentido rechazarle el
        guardado por un campo cuya única opción posible es él."""
        if obj.activo and obj.medico_responsable_id is None and _solo_propios(request):
            obj.medico_responsable = request.user
        if not change:
            dias_post = (timezone.localdate() - obj.fecha_cirugia).days
            if dias_post >= DIAS_SEGUIMIENTO - 2:
                messages.warning(
                    request,
                    f"Advertencia: este paciente tiene {dias_post} días postoperatorios. "
                    f"El sistema lo desactivará automáticamente en cuanto alcance "
                    f"{DIAS_SEGUIMIENTO} días. Considere si el seguimiento remoto es "
                    f"apropiado para este caso."
                )
        if obj.consentimiento_informado and not obj.fecha_consentimiento:
            obj.fecha_consentimiento = timezone.now()
        elif not obj.consentimiento_informado and obj.fecha_consentimiento:
            obj.fecha_consentimiento = None
        super().save_model(request, obj, form, change)

    def construct_change_message(self, request, form, formsets, add=False):
        """Nombra explícitamente el cambio de estado en el historial Admin."""
        if not add and 'activo' in form.changed_data:
            estado = 'activado' if form.cleaned_data.get('activo') else 'desactivado'
            otros = [
                str(form.fields[campo].label)
                for campo in form.changed_data
                if campo != 'activo' and campo in form.fields
            ]
            mensaje = f'Seguimiento {estado}.'
            if otros:
                mensaje += f' Otros campos modificados: {", ".join(otros)}.'
            return mensaje
        return super().construct_change_message(request, form, formsets, add)

    @admin.display(description='Evolución signos vitales')
    def grafica_signos_vitales(self, obj):
        if obj.pk is None:
            return '—'
        return _grafica_signos_vitales(obj)

    @admin.display(description='Historial del paciente')
    def historial_paciente(self, obj):
        if obj.pk is None:
            return '—'
        dias = getattr(self, '_dias_historial', DIAS_HISTORIAL_DEFAULT)
        return mark_safe(_historial_paciente(obj, dias=dias))

    @admin.display(description='Médico responsable')
    def medico_nombre(self, obj):
        if obj.medico_responsable is None:
            return '— Sin asignar'
        return obj.medico_responsable.get_full_name() or obj.medico_responsable.username

    def get_queryset(self, request):
        """B6: cada médico solo ve sus propios pacientes. Superuser ve todos."""
        qs = super().get_queryset(request)
        if _solo_propios(request):
            return qs.filter(medico_responsable=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """B6: médico no-superuser solo puede asignarse a sí mismo como responsable.

        D12 (capa 1): además queda preseleccionado. El desplegable nacía vacío
        con una sola opción posible, y dejarlo así era el camino de menor
        resistencia — no un descuido rebuscado.
        """
        if db_field.name == 'medico_responsable' and _solo_propios(request):
            kwargs['queryset'] = get_user_model().objects.filter(pk=request.user.pk)
            kwargs['initial'] = request.user.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        """D12 (capa 1) — un paciente ACTIVO no puede quedarse sin responsable.

        La validación vive en el formulario, no solo en la base, para que el
        error se vea como un mensaje del campo y no como un IntegrityError. El
        superusuario conserva la libertad de dejarlo vacío en una ficha
        inactiva: las filas históricas no llevan responsable y exigírselo
        obligaría a inventarles uno.
        """
        form = super().get_form(request, obj, **kwargs)
        usuario = request.user

        class FormConResponsable(form):
            def clean(self):
                datos = super().clean()
                if datos.get('activo') and not datos.get('medico_responsable'):
                    if _solo_propios(request):
                        # Solo puede ser él mismo: se asigna en vez de estorbar.
                        datos['medico_responsable'] = usuario
                    else:
                        self.add_error(
                            'medico_responsable',
                            'Un paciente activo necesita un médico responsable: '
                            'sin él desaparece del listado y de los indicadores '
                            'del tablero, y sus alertas no llegan a nadie. '
                            'Asigna uno, o desmarca "activo" si es una ficha '
                            'histórica.',
                        )
                return datos

        return FormConResponsable

    def has_change_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.medico_responsable == request.user
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # El seguimiento se cierra con activo=False. El borrado elimina
        # trazabilidad clínica y queda reservado para mantenimiento excepcional.
        return request.user.is_superuser


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'temperatura', 'dolor_eva',
                    'aspecto_drenaje', 'presencia_gases',
                    'estado_evaluacion_alertas', 'fecha_registro']
    list_filter = [
        'estado_evaluacion_alertas',
        'aspecto_drenaje',
        'presencia_gases',
    ]
    search_fields = ['paciente__nombre_completo']

    def get_queryset(self, request):
        """B6: solo registros de pacientes propios del médico. Superuser ve todos."""
        qs = super().get_queryset(request)
        if _solo_propios(request):
            return qs.filter(paciente__medico_responsable=request.user)
        return qs

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ['fecha_registro', 'dia_postoperatorio']
        return [campo.name for campo in self.model._meta.fields]

    def has_add_permission(self, request):
        # Los registros se originan exclusivamente en el flujo de WhatsApp.
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(RecepcionWebhookTwilio)
class RecepcionWebhookTwilioAdmin(admin.ModelAdmin):
    list_display = [
        'message_sid',
        'estado',
        'intentos',
        'fecha_recepcion',
        'fecha_actualizacion',
    ]
    list_filter = ['estado']
    search_fields = ['message_sid']
    readonly_fields = [campo.name for campo in RecepcionWebhookTwilio._meta.fields]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificacionAlerta)
class NotificacionAlertaAdmin(admin.ModelAdmin):
    list_display = [
        'alerta_id',
        'estado',
        'intentos',
        'proximo_intento',
        'fecha_envio',
    ]
    list_filter = ['estado']
    readonly_fields = [campo.name for campo in NotificacionAlerta._meta.fields]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


_COLORES_SEVERIDAD = {
    'ALTA':  ('#7f1d1d', '#fee2e2'),   # rojo oscuro texto, rojo claro fondo
    'MEDIA': ('#78350f', '#fef3c7'),   # ámbar oscuro texto, ámbar claro fondo
    'BAJA':  ('#14532d', '#dcfce7'),   # verde oscuro texto, verde claro fondo
}


class DeteccionAlertaInline(admin.TabularInline):
    model = DeteccionAlerta
    verbose_name_plural = 'Detecciones de la alerta'
    fields = (
        'fecha_deteccion',
        'severidad_detectada',
        'fuente_deteccion',
        'mensaje_detectado',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False

    @admin.display(description='Fuente')
    def fuente_deteccion(self, obj):
        if obj.registro_id:
            return f'Registro diario #{obj.registro_id}'
        return f'Check-in #{obj.checkin_id}'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('registro', 'checkin')

    def has_view_permission(self, request, obj=None):
        if not request.user.is_active or not request.user.is_staff:
            return False
        if obj is not None and not request.user.is_superuser:
            return obj.paciente.medico_responsable_id == request.user.id
        return True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'tipo', 'severidad_badge', 'recurrencia',
                    'resuelta', 'resuelta_por', 'fecha_alerta', 'mensaje_corto']
    list_filter = ['tipo', 'severidad', 'resuelta']
    search_fields = ['paciente__nombre_completo']
    actions = ['marcar_resuelta']
    readonly_fields = [
        *[campo.name for campo in Alerta._meta.fields],
        'cobertura_detecciones',
    ]
    inlines = [DeteccionAlertaInline]

    def has_add_permission(self, request):
        # Las alertas son resultados del motor clínico, no entradas manuales.
        return False

    @admin.display(description='Recurrencia', ordering='veces')
    def recurrencia(self, obj):
        """Contador de check-ins en que se ha detectado el problema mientras
        la alerta sigue abierta. ×1 = primera vez; ×N resalta persistencia."""
        if obj.veces <= 1:
            return format_html('<span style="color:#6b7280;">×{}</span>', obj.veces)
        # Resalta la persistencia: cuantas más veces, más notorio.
        fondo = '#fee2e2' if obj.veces >= 3 else '#fef3c7'
        texto = '#7f1d1d' if obj.veces >= 3 else '#78350f'
        return format_html(
            '<span title="Detectada en {n} check-ins" style="'
            'background:{fondo};color:{texto};padding:2px 8px;border-radius:4px;'
            'font-weight:bold;font-size:0.85em;">×{n}</span>',
            n=obj.veces, fondo=fondo, texto=texto,
        )

    @admin.display(description='Cobertura del desglose')
    def cobertura_detecciones(self, obj):
        detalladas = obj.detecciones.count()
        anteriores = max(obj.veces - detalladas, 0)
        if anteriores:
            etiqueta_anteriores = (
                'detección anterior' if anteriores == 1
                else 'detecciones anteriores'
            )
            etiqueta_detalladas = (
                'detección' if detalladas == 1 else 'detecciones'
            )
            return format_html(
                'El contador conserva <strong>{}</strong> {} sin desglose '
                'individual. El desglose empieza desde esta versión e incluye '
                '<strong>{}</strong> {}.',
                anteriores,
                etiqueta_anteriores,
                detalladas,
                etiqueta_detalladas,
            )
        return format_html(
            '<strong>{}</strong> de <strong>{}</strong> detecciones tienen detalle.',
            detalladas,
            obj.veces,
        )

    @admin.display(description='Severidad', ordering='severidad')
    def severidad_badge(self, obj):
        color_texto, color_fondo = _COLORES_SEVERIDAD.get(
            obj.severidad, ('#374151', '#f3f4f6')
        )
        return format_html(
            '<span style="'
            'background:{fondo};color:{texto};'
            'padding:2px 8px;border-radius:4px;'
            'font-weight:bold;font-size:0.85em;'
            '">{label}</span>',
            fondo=color_fondo,
            texto=color_texto,
            label=obj.get_severidad_display(),
        )

    @admin.display(description='Mensaje')
    def mensaje_corto(self, obj):
        return obj.mensaje[:80] + '…' if len(obj.mensaje) > 80 else obj.mensaje

    @admin.action(description='Marcar como resuelta')
    def marcar_resuelta(self, request, queryset):
        """Bloque A: muestra un formulario intermedio para capturar el motivo
        de resolución (obligatorio) antes de marcar las alertas como resueltas.

        Scoping: un médico no-superuser solo puede resolver alertas de sus
        propios pacientes — se re-filtra por permisos en cada paso, nunca se
        confía en los pk que llegan del cliente.
        """
        if _solo_propios(request):
            queryset = queryset.filter(paciente__medico_responsable=request.user)

        contexto = {
            **self.admin_site.each_context(request),
            'alertas': queryset,
            'title': 'Selecciona el motivo de resolución',
            'accion': 'marcar_resuelta',
        }
        plantilla = 'admin/signos_sintomas/alerta/motivo_resolucion.html'

        # Paso 1: primera vez que se dispara la acción → mostrar formulario.
        if 'aplicar' not in request.POST:
            contexto['form'] = MotivoResolucionForm()
            return TemplateResponse(request, plantilla, contexto)

        # Paso 2: formulario enviado → validar y aplicar.
        form = MotivoResolucionForm(request.POST)
        if not form.is_valid():
            contexto['form'] = form
            return TemplateResponse(request, plantilla, contexto)

        motivo = form.cleaned_data['motivo_resolucion']
        detalle = form.cleaned_data['motivo_resolucion_detalle']
        # Capturar las alertas antes del update para poder registrarlas en el
        # historial una por una (queryset.update() no dispara log_change).
        pendientes = list(queryset.filter(resuelta=False))
        actualizadas = queryset.filter(resuelta=False).update(
            resuelta=True,
            fecha_resolucion=timezone.now(),
            motivo_resolucion=motivo,
            motivo_resolucion_detalle=detalle or None,
            resuelta_por=request.user,
        )
        # D3: el historial de Django no se escribe con queryset.update(). Se
        # registra explícitamente para que el botón "Historial" de cada alerta
        # funcione y quede constancia de quién resolvió.
        for alerta in pendientes:
            self.log_change(
                request,
                alerta,
                f'Marcada como resuelta (motivo: {motivo}).',
            )
        self.message_user(
            request,
            f'{actualizadas} alerta(s) marcadas como resueltas.',
        )
        # Devolver None es lo que le dice al Admin que vuelva al listado. Se
        # escribe explícito porque las otras ramas de esta acción sí devuelven
        # una respuesta (el formulario intermedio del motivo).
        return None

    def get_queryset(self, request):
        """B6: solo alertas de pacientes propios del médico. Superuser ve todos."""
        qs = super().get_queryset(request)
        if _solo_propios(request):
            return qs.filter(paciente__medico_responsable=request.user)
        return qs

    def has_change_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.paciente.medico_responsable == request.user
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Alertas son registros clínicos del sistema — la trazabilidad es
        # obligatoria. Solo superuser puede borrarlas; el flujo correcto para
        # médicos es marcar 'resuelta=True', no eliminar el registro.
        return request.user.is_superuser


@admin.register(CheckInProgramado)
class CheckInProgramadoAdmin(admin.ModelAdmin):
    list_display  = ['paciente', 'fecha_dia', 'etiqueta', 'orden',
                     'estado', 'hora_programada', 'fecha_respuesta']
    list_filter   = [
        'estado',
        'etiqueta',
        ('fecha_dia', TodasLasFechasListFilter),
    ]
    search_fields = ['paciente__nombre_completo']
    readonly_fields = ['hora_programada', 'fecha_respuesta', 'fecha_dia',
                       'orden', 'etiqueta', 'registro']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if _solo_propios(request):
            return qs.filter(paciente__medico_responsable=request.user)
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Para el médico son eventos operativos de solo lectura. El superusuario
        # conserva una vía de mantenimiento excepcional.
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# --- Branding del Admin (identidad "calma clínica") + tablero de triage ---
# El texto de la cabecera y el título de la página de inicio. El índice usa una
# plantilla propia (admin/index_panel.html) que EXTIENDE el índice real de
# Django e inyecta el tablero encima con {{ block.super }} — no se pierde nada
# del admin (lista de apps, barra lateral, acciones recientes).
admin.site.site_header = 'Seguimiento Postquirúrgico'
admin.site.site_title = 'Seguimiento Postquirúrgico'
admin.site.index_title = 'Panel del médico'
admin.site.index_template = 'admin/index_panel.html'
