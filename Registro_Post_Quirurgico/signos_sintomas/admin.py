from django.contrib import admin
from .models import Paciente, RegistroDiario, Alerta


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'medico_nombre',
                    'fecha_cirugia', 'activo']
    list_filter = ['activo', 'medico_responsable']
    search_fields = ['nombre_completo', 'telefono_whatsapp',
                     'medico_responsable__first_name',
                     'medico_responsable__last_name',
                     'medico_responsable__username']

    @admin.display(description='Médico responsable')
    def medico_nombre(self, obj):
        if obj.medico_responsable is None:
            return '— Sin asignar'
        return obj.medico_responsable.get_full_name() or obj.medico_responsable.username

    def get_queryset(self, request):
        """B6: cada médico solo ve sus propios pacientes. Superuser ve todos."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(medico_responsable=request.user)


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'temperatura', 'dolor_eva',
                    'aspecto_drenaje', 'presencia_gases', 'fecha_registro']
    list_filter = ['aspecto_drenaje', 'presencia_gases']
    search_fields = ['paciente__nombre_completo']

    def get_queryset(self, request):
        """B6: solo registros de pacientes propios del médico. Superuser ve todos."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(paciente__medico_responsable=request.user)


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'tipo', 'severidad',
                    'resuelta', 'fecha_alerta', 'mensaje_corto']
    list_filter = ['tipo', 'severidad', 'resuelta']
    search_fields = ['paciente__nombre_completo']

    @admin.display(description='Mensaje')
    def mensaje_corto(self, obj):
        return obj.mensaje[:80] + '…' if len(obj.mensaje) > 80 else obj.mensaje

    def get_queryset(self, request):
        """B6: solo alertas de pacientes propios del médico. Superuser ve todos."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(paciente__medico_responsable=request.user)