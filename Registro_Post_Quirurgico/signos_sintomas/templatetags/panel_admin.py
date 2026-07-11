"""
Template tag del tablero de triage del Admin (Panel del médico).

`{% panel_triage %}` calcula, con las alertas/check-ins/pacientes reales, lo que
el médico necesita ver de primero al entrar a /admin/. Respeta el scoping por
médico: un usuario staff no-superusuario solo ve lo de SUS pacientes; el
superusuario ve todo. No modifica nada — solo consulta y muestra.
"""

from django import template
from django.db.models import Count, Q
from django.utils import timezone

from signos_sintomas.models import Alerta, CheckInProgramado, Paciente

register = template.Library()

# Orden de gravedad para el triage (menor = más urgente).
_RANK_SEV = {'ALTA': 0, 'MEDIA': 1, 'BAJA': 2}

# Etiquetas del tipo de alerta en lenguaje del médico (para el tablero).
_DIAG_LABEL = {
    'SEPSIS':            'Fiebre — posible sepsis',
    'FUGA_ANASTOMOTICA': 'Fuga anastomótica',
    'ILEO_PARALITICO':   'Íleo paralítico',
    'DOLOR_AGUDO':       'Dolor agudo',
    'INTOLERANCIA_ORAL': 'Intolerancia oral',
    'TAQUICARDIA':       'Taquicardia',
    'SILENCIO':          'Sin respuesta',
}


def _pod(paciente, hoy):
    """Día postoperatorio del paciente hoy (piso en 0)."""
    return max(0, (hoy - paciente.fecha_cirugia).days)


@register.inclusion_tag('admin/panel_triage.html', takes_context=True)
def panel_triage(context):
    request = context['request']
    user = request.user
    hoy = timezone.localdate()

    pacientes = Paciente.objects.all()
    alertas = Alerta.objects.all()
    checkins = CheckInProgramado.objects.filter(fecha_dia=hoy)

    # Scoping por médico: el no-superusuario solo ve lo suyo.
    if not user.is_superuser:
        pacientes = pacientes.filter(medico_responsable=user)
        alertas = alertas.filter(paciente__medico_responsable=user)
        checkins = checkins.filter(paciente__medico_responsable=user)

    activos = pacientes.filter(activo=True)
    pendientes = alertas.filter(resuelta=False)

    total_checkins = checkins.count()
    respondidos = checkins.filter(estado=CheckInProgramado.ESTADO_COMPLETADO).count()
    kpi = {
        'alta':        pendientes.filter(severidad='ALTA').count(),
        'silencios':   checkins.filter(estado=CheckInProgramado.ESTADO_NO_RESPONDIDO).count(),
        'pendientes':  checkins.filter(estado=CheckInProgramado.ESTADO_PENDIENTE).count(),
        'respondidos': respondidos,
        'total':       total_checkins,
        'activos':     activos.count(),
        'pct':         int(round(100 * respondidos / total_checkins)) if total_checkins else 0,
    }

    # Triage: alertas sin resolver (menos SILENCIO), por gravedad y recientes.
    pend = list(
        pendientes.exclude(tipo='SILENCIO')
        .select_related('paciente', 'registro_origen')
        .order_by('-fecha_alerta')
    )
    pend.sort(key=lambda a: _RANK_SEV.get(a.severidad, 3))  # sort estable
    atencion = []
    for a in pend[:10]:
        if a.registro_origen_id:
            pod = a.registro_origen.dia_postoperatorio
        else:
            pod = _pod(a.paciente, hoy)
        atencion.append({
            'nombre':      a.paciente.nombre_completo,
            'paciente_id': a.paciente_id,
            'alerta_id':   a.id,
            'sev':         a.severidad.lower(),
            'sev_label':   a.severidad.capitalize(),
            'diag':        _DIAG_LABEL.get(a.tipo, a.get_tipo_display()),
            'pod':         pod,
            'telefono':    a.paciente.telefono_whatsapp,
            'fecha':       a.fecha_ultima_deteccion or a.fecha_alerta,
            'veces':       a.veces,
        })

    # Silencios de hoy.
    silencios = [
        {
            'nombre':      c.paciente.nombre_completo,
            'paciente_id': c.paciente_id,
            'pod':         _pod(c.paciente, hoy),
            'etiqueta':    c.get_etiqueta_display(),
        }
        for c in (checkins.filter(estado=CheckInProgramado.ESTADO_NO_RESPONDIDO)
                  .select_related('paciente')[:8])
    ]

    # Pacientes en seguimiento (activos), con conteo de alertas activas.
    tabla = (
        activos.annotate(
            n_alta=Count('alertas', filter=Q(alertas__resuelta=False, alertas__severidad='ALTA')),
            n_media=Count('alertas', filter=Q(alertas__resuelta=False, alertas__severidad='MEDIA')),
        ).order_by('-n_alta', '-n_media', 'nombre_completo')
    )
    pacientes_tabla = []
    for p in tabla[:12]:
        ult = (p.registros.order_by('-fecha_registro')
               .values_list('fecha_registro', flat=True).first())
        pacientes_tabla.append({
            'nombre':  p.nombre_completo,
            'id':      p.id,
            'pod':     _pod(p, hoy),
            'ultima':  timezone.localtime(ult) if ult else None,
            'cirugia': p.get_tipo_cirugia_display() if p.tipo_cirugia else '—',
            'n_alta':  p.n_alta,
            'n_media': p.n_media,
        })

    return {
        'kpi': kpi,
        'atencion': atencion,
        'silencios': silencios,
        'pacientes': pacientes_tabla,
        'hoy': hoy,
        'es_super': user.is_superuser,
    }
