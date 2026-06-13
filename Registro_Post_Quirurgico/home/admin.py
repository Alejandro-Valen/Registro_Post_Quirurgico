from django.contrib import admin

from .models import MensajeContacto


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "fecha_creacion", "revisado")
    list_filter = ("revisado", "fecha_creacion")
    search_fields = ("nombre", "telefono", "mensaje")
    readonly_fields = ("fecha_creacion",)
