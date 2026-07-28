"""D12 (capa 2) — medico_responsable pasa de SET_NULL a PROTECT.

Borrar la cuenta de un médico convertía a todos sus pacientes en huérfanos
invisibles, en silencio. PROTECT obliga a reasignarlos antes.

NO GENERA SQL. Verificado con `sqlmigrate signos_sintomas 0027`: la salida es
`-- (no-op)`. `on_delete` es una regla que Django aplica en Python al borrar,
no una restricción de la base, así que esta migración solo actualiza el estado
del historial de migraciones. No reescribe la tabla ni puede fallar por datos
existentes — a diferencia de la 0028, que sí añade una restricción real.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signos_sintomas', '0026_notificacion_estado_fallida'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='paciente',
            name='medico_responsable',
            field=models.ForeignKey(blank=True, help_text='Usuario del sistema (médico) responsable del paciente. Debe existir como usuario en Django Admin. Obligatorio mientras el paciente esté activo.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='pacientes', to=settings.AUTH_USER_MODEL),
        ),
    ]
