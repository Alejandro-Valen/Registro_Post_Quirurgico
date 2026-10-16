"""D28 (15/10/2026) — cuándo se creó cada turno, y el help_text de registro_origen.

El campo se añade en DOS pasos a propósito. Un solo `AddField` con
`default=timezone.now` rellenaría cada turno existente con la hora en que corre
esta migración: una fecha de creación inventada, que haría pasar por recientes
turnos de hace semanas. Es justo lo que D3 y la migración 0019 se negaron a
hacer —no se hace backfill de datos que nadie observó—. Así que:

1. `AddField` SIN default: los turnos existentes quedan con NULL, que
   `cerrar_checkins_vencidos` lee como «no se sabe» y trata con la regla de
   siempre (desde la hora programada).
2. `AlterField` con el default: a partir de aquí, cada turno nuevo lo registra.
   Cambiar el default no toca las filas que ya existen.
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signos_sintomas', '0032_indice_turnos_pendientes'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkinprogramado',
            name='fecha_creacion',
            field=models.DateTimeField(
                blank=True, editable=False, null=True,
                help_text='Momento en que el turno se creó. Vacío en los anteriores al 15/10/2026.',
            ),
        ),
        migrations.AlterField(
            model_name='checkinprogramado',
            name='fecha_creacion',
            field=models.DateTimeField(
                blank=True, default=django.utils.timezone.now, editable=False, null=True,
                help_text='Momento en que el turno se creó. Vacío en los anteriores al 15/10/2026.',
            ),
        ),
        migrations.AlterField(
            model_name='alerta',
            name='registro_origen',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='alertas', to='signos_sintomas.registrodiario',
                help_text=(
                    'El ÚLTIMO registro diario que detectó este problema, no el que lo '
                    'originó (cada detección está en DeteccionAlerta). Vacío en '
                    'SILENCIO y AUXILIO, que no salen de un registro.'
                ),
            ),
        ),
    ]
