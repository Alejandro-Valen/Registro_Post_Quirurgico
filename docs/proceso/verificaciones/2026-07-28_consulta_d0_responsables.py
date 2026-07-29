"""
D-0 — Compuerta del Loop D: ¿hay pacientes activos sin quien los atienda?

QUÉ HACE: cuenta. No escribe, no modifica, no borra. Es seguro correrlo contra
producción — es la misma disciplina de D7 (ficha en
`docs/decisiones_correccion_auditoria.md`): contar antes de actuar.

POR QUÉ EXISTE: el paso D-6 del Loop D añade un `CheckConstraint` que exige
`activo=True` → `medico_responsable` no nulo (decisión D12, capa 4). El
`Dockerfile` encadena `migrate --noinput && gunicorn`, así que una migración que
alguna fila existente viole NO produce un error en el log: **deja el contenedor
sin arrancar.** Si este script devuelve algo distinto de cero, se arreglan los
datos ANTES de escribir la migración.

CÓMO SE CORRE, en la consola del servicio web de Railway:

    python Registro_Post_Quirurgico/manage.py shell

y se pega el bloque de abajo. (En local es lo mismo desde
`Registro_Post_Quirurgico/`.)

NOTA SOBRE LA SALIDA: imprime `pk`s, nunca nombres ni teléfonos — decisión D11.
La salida de este script se pega en una conversación, así que no debe contener
identidad de nadie.
"""

# --- pegar desde aquí ---
from django.contrib.auth import get_user_model
from django.db.models import Q

from signos_sintomas.models import Paciente

User = get_user_model()
activos = Paciente.objects.filter(activo=True)

# (A) Huérfanos: la compuerta dura. Debe dar 0 para poder añadir la restricción.
sin_medico = activos.filter(medico_responsable__isnull=True)

# (B) Sin atención efectiva: el médico existe pero no puede verlo ni recibir su
#     alerta. No bloquea la migración, pero es el mismo daño clínico.
sin_atencion = activos.filter(
    Q(medico_responsable__is_active=False)
    | Q(medico_responsable__is_staff=False)
    | Q(medico_responsable__email='')
)

print('=' * 60)
print('D-0 — compuerta del Loop D')
print('=' * 60)
print(f'  pacientes totales             : {Paciente.objects.count()}')
print(f'  pacientes ACTIVOS             : {activos.count()}')
print()
print(f'  (A) activos SIN medico        : {sin_medico.count()}   <- debe ser 0')
print(f'      pks: {sorted(sin_medico.values_list("pk", flat=True))}')
print()
print(f'  (B) activos SIN atencion util : {sin_atencion.count()}')
for p in sin_atencion.select_related('medico_responsable'):
    m = p.medico_responsable
    print(f'      paciente pk={p.pk} -> medico pk={m.pk} '
          f'activo={m.is_active} staff={m.is_staff} correo={bool(m.email)}')
print()
print('  Cuentas medicas (contexto):')
for u in User.objects.all().order_by('pk'):
    print(f'      pk={u.pk} activo={u.is_active} staff={u.is_staff} '
          f'super={u.is_superuser} correo={bool(u.email)} '
          f'pacientes_activos={u.pacientes.filter(activo=True).count()}')
print('=' * 60)
# --- hasta aquí ---
