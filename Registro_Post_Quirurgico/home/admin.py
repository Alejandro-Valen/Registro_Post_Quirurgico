from django.contrib import admin

from .models import MensajeContacto


class TodasLasFechasListFilter(admin.DateFieldListFilter):
    def choices(self, changelist):
        for indice, choice in enumerate(super().choices(changelist)):
            if indice == 0:
                choice = {**choice, "display": "Todas las fechas"}
            yield choice


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "telefono",
        "medico_destinatario",
        "fecha_creacion",
        "revisado",
    )
    list_filter = (
        "revisado",
        ("fecha_creacion", TodasLasFechasListFilter),
    )
    search_fields = ("nombre", "telefono", "mensaje")
    readonly_fields = ("fecha_creacion",)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields
        return (
            "nombre",
            "telefono",
            "mensaje",
            "medico_destinatario",
            "fecha_creacion",
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(medico_destinatario=request.user)

    def has_view_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            return obj.medico_destinatario_id == request.user.id
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            return obj.medico_destinatario_id == request.user.id
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        # Los mensajes se crean desde el formulario público de contacto.
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
