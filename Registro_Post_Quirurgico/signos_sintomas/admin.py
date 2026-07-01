from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Alerta, CheckInProgramado, Paciente, RegistroDiario


def _solo_propios(request):
    """True si el usuario debe ver solo sus propios datos (no superuser)."""
    return not request.user.is_superuser


DIAS_HISTORIAL_DEFAULT = 7
DIAS_HISTORIAL_OPCIONES = [7, 14, 30]


def _clamp_dias_historial(valor):
    """Convierte el parámetro ?dias= de la URL a un entero seguro (1-90)."""
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return DIAS_HISTORIAL_DEFAULT
    return max(1, min(dias, 90))


def _selector_dias_historial(dias_actual):
    """Enlaces '7 días / 14 días / 30 días' — P-8: historial configurable por el médico."""
    enlaces = []
    for dias in DIAS_HISTORIAL_OPCIONES:
        if dias == dias_actual:
            enlaces.append(f'<strong>{dias} días</strong>')
        else:
            enlaces.append(f'<a href="?dias={dias}">{dias} días</a>')
    return f'<p style="margin:0 0 6px;">Ver: {" · ".join(enlaces)}</p>'


def _historial_paciente(paciente, dias=DIAS_HISTORIAL_DEFAULT):
    """Devuelve HTML con selector de rango + tabla de registros del paciente."""
    selector = _selector_dias_historial(dias)
    desde = timezone.localdate() - timedelta(days=dias)
    registros = (
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=desde)
        .order_by('-fecha_registro')
    )
    if not registros.exists():
        return selector + f'<p style="color:#6b7280;">Sin registros en los últimos {dias} días.</p>'

    filas = []
    for r in registros:
        fecha = r.fecha_registro.strftime('%d/%m %H:%M')
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
    list_filter = ['activo', 'tipo_cirugia', 'medico_responsable', TieneAlertaActivaFilter]
    search_fields = ['nombre_completo', 'cedula', 'telefono_whatsapp',
                     'medico_responsable__first_name',
                     'medico_responsable__last_name',
                     'medico_responsable__username']
    readonly_fields = ['historial_paciente']

    def get_readonly_fields(self, request, obj=None):
        # Captura ?dias= de la URL para que historial_paciente() lo use al
        # renderizar — los readonly_fields solo reciben `obj`, no `request`.
        self._dias_historial = _clamp_dias_historial(request.GET.get('dias'))
        return super().get_readonly_fields(request, obj)

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
        """B6: médico no-superuser solo puede asignarse a sí mismo como responsable."""
        if db_field.name == 'medico_responsable' and _solo_propios(request):
            kwargs['queryset'] = get_user_model().objects.filter(pk=request.user.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.medico_responsable == request.user
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.medico_responsable == request.user
        return super().has_delete_permission(request, obj)


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'temperatura', 'dolor_eva',
                    'aspecto_drenaje', 'presencia_gases', 'fecha_registro']
    list_filter = ['aspecto_drenaje', 'presencia_gases']
    search_fields = ['paciente__nombre_completo']

    def get_queryset(self, request):
        """B6: solo registros de pacientes propios del médico. Superuser ve todos."""
        qs = super().get_queryset(request)
        if _solo_propios(request):
            return qs.filter(paciente__medico_responsable=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """B6: dropdown de paciente limitado a los del médico actual."""
        if db_field.name == 'paciente' and _solo_propios(request):
            kwargs['queryset'] = Paciente.objects.filter(
                medico_responsable=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.paciente.medico_responsable == request.user
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and _solo_propios(request):
            return obj.paciente.medico_responsable == request.user
        return super().has_delete_permission(request, obj)


_COLORES_SEVERIDAD = {
    'ALTA':  ('#7f1d1d', '#fee2e2'),   # rojo oscuro texto, rojo claro fondo
    'MEDIA': ('#78350f', '#fef3c7'),   # ámbar oscuro texto, ámbar claro fondo
    'BAJA':  ('#14532d', '#dcfce7'),   # verde oscuro texto, verde claro fondo
}


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'tipo', 'severidad_badge',
                    'resuelta', 'fecha_alerta', 'mensaje_corto']
    list_filter = ['tipo', 'severidad', 'resuelta']
    search_fields = ['paciente__nombre_completo']
    actions = ['marcar_resuelta']

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
        from django.utils import timezone as tz
        actualizadas = queryset.filter(resuelta=False).update(
            resuelta=True,
            fecha_resolucion=tz.now(),
        )
        self.message_user(
            request,
            f'{actualizadas} alerta(s) marcadas como resueltas.',
        )

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
    list_filter   = ['estado', 'etiqueta', 'fecha_dia']
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

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
