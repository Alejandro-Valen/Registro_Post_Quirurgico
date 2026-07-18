from django.contrib import admin

from .models import MensajeContacto


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "fecha_creacion", "revisado")
    list_filter = ("revisado", "fecha_creacion")
    search_fields = ("nombre", "telefono", "mensaje")
    readonly_fields = ("fecha_creacion",)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields
        return ("nombre", "telefono", "mensaje", "fecha_creacion")

    def has_add_permission(self, request):
        # Los mensajes se crean desde el formulario público de contacto.
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
