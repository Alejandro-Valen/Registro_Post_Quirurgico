from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Alerta, CheckInProgramado, Paciente, RegistroDiario


def _solo_propios(request):
    """True si el usuario debe ver solo sus propios datos (no superuser)."""
    return not request.user.is_superuser


def _historial_7_dias(paciente):
    """Devuelve HTML con tabla de los últimos 7 días de registros del paciente."""
    hace_7 = timezone.localdate() - timedelta(days=7)
    registros = (
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=hace_7)
        .order_by('-fecha_registro')
    )
    if not registros.exists():
        return '<p style="color:#6b7280;">Sin registros en los últimos 7 días.</p>'

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
    return tabla


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'medico_nombre',
                    'fecha_cirugia', 'activo']
    list_filter = ['activo', 'medico_responsable']
    search_fields = ['nombre_completo', 'telefono_whatsapp',
                     'medico_responsable__first_name',
                     'medico_responsable__last_name',
                     'medico_responsable__username']
    readonly_fields = ['historial_ultimos_7_dias']

    @admin.display(description='Historial últimos 7 días')
    def historial_ultimos_7_dias(self, obj):
        if obj.pk is None:
            return '—'
        return mark_safe(_historial_7_dias(obj))

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
