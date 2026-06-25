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


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'temperatura', 'dolor_eva',
                    'aspecto_drenaje', 'presencia_gases', 'fecha_registro']
    list_filter = ['aspecto_drenaje', 'presencia_gases']
    search_fields = ['paciente__nombre_completo']


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'tipo', 'severidad',
                    'resuelta', 'fecha_alerta']
    list_filter = ['tipo', 'severidad', 'resuelta']
    search_fields = ['paciente__nombre_completo']