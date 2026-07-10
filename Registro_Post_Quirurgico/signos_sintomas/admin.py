import json
from datetime import timedelta

from django import forms as django_forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Alerta, CheckInProgramado, Paciente, RegistroDiario
from .management.commands.desactivar_pacientes_vencidos import DIAS_SEGUIMIENTO


class MotivoResolucionForm(django_forms.Form):
    """Formulario intermedio de la acción 'Marcar como resuelta' (Bloque A).
    Captura el motivo obligatorio y, solo para 'Otro', un detalle libre.

    Los pk seleccionados NO viajan en el form: se leen de request.POST
    ('_selected_action', el mismo nombre que usa el admin) y se re-filtran
    por permisos en la acción, para no confiar en input del cliente."""
    motivo_resolucion = django_forms.ChoiceField(
        choices=Alerta.MOTIVOS_RESOLUCION,
        initial=Alerta.MOTIVO_CONTACTO,
        label='Motivo de resolución',
    )
    motivo_resolucion_detalle = django_forms.CharField(
        max_length=500,
        required=False,
        label='Detalle (solo si seleccionó "Otro")',
        widget=django_forms.Textarea(attrs={'rows': 2}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('motivo_resolucion') == Alerta.MOTIVO_OTRO \
                and not cleaned.get('motivo_resolucion_detalle'):
            raise django_forms.ValidationError(
                'Debes especificar el detalle cuando el motivo es "Otro".'
            )
        return cleaned


def _solo_propios(request):
    """True si el usuario debe ver solo sus propios datos (no superuser)."""
    return not request.user.is_superuser


DIAS_HISTORIAL_DEFAULT = 7
DIAS_HISTORIAL_OPCIONES = [7, 14, 30]


def _clamp_dias_historial(valor):
    """Convierte el parámetro ?dias= de la URL a un entero seguro (1-90)."""
    try:
        dias = int(valor)
    except (TypeError, ValueError):
        return DIAS_HISTORIAL_DEFAULT
    return max(1, min(dias, 90))


def _selector_dias_historial(dias_actual):
    """Enlaces '7 días / 14 días / 30 días' — P-8: historial configurable por el médico."""
    enlaces = []
    for dias in DIAS_HISTORIAL_OPCIONES:
        if dias == dias_actual:
            enlaces.append(f'<strong>{dias} días</strong>')
        else:
            enlaces.append(f'<a href="?dias={dias}">{dias} días</a>')
    return f'<p style="margin:0 0 6px;">Ver: {" · ".join(enlaces)}</p>'


def _turnos_por_registro(registros):
    """
    Mapa {registro.pk: 'M'/'T'} usando el CheckInProgramado vinculado —
    el turno lo fija el evento programado, nunca la hora en que el
    paciente respondió (decisión D2, Sprint 3.6: ROADMAP FASE 3.6).
    Fallback por hora (< 12 = mañana) solo para registros legado sin
    CheckInProgramado vinculado (datos previos a Sprint 4).
    """
    etiqueta_por_registro = dict(
        CheckInProgramado.objects
        .filter(registro__in=registros)
        .values_list('registro_id', 'etiqueta')
    )
    turnos = {}
    for r in registros:
        etiqueta = etiqueta_por_registro.get(r.pk)
        if etiqueta == CheckInProgramado.ETIQUETA_MANANA:
            turnos[r.pk] = 'M'
        elif etiqueta == CheckInProgramado.ETIQUETA_TARDE:
            turnos[r.pk] = 'T'
        else:
            # USE_TZ=True: fecha_registro llega en UTC — convertir a hora
            # local (Bogotá) antes de comparar, o el respaldo clasifica
            # mal el turno de registros creados cerca de medianoche/mañana.
            hora_local = timezone.localtime(r.fecha_registro).hour
            turnos[r.pk] = 'M' if hora_local < 12 else 'T'
    return turnos


def _historial_paciente(paciente, dias=DIAS_HISTORIAL_DEFAULT):
    """Devuelve HTML con selector de rango + tabla de registros del paciente."""
    selector = _selector_dias_historial(dias)
    desde = timezone.localdate() - timedelta(days=dias)
    registros = list(
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=desde)
        .order_by('-fecha_registro')
    )
    if not registros:
        return selector + f'<p style="color:#6b7280;">Sin registros en los últimos {dias} días.</p>'

    turnos = _turnos_por_registro(registros)
    filas = []
    for r in registros:
        fecha = timezone.localtime(r.fecha_registro).strftime('%d/%m') + f' {turnos[r.pk]}'
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
    return selector + tabla


DIAS_GRAFICA_OPCIONES = [7, 14, 30]


def _datos_grafica(paciente, dias):
    """
    Arma los datos (labels/temps/evas/fcs/alertas_idx) para graficar los
    últimos `dias` días de un paciente. Todo lo que va a JSON pasa por
    json.dumps() en el llamador — nunca se interpola directo en el HTML.
    """
    desde = timezone.localdate() - timedelta(days=dias)
    registros = list(
        RegistroDiario.objects
        .filter(paciente=paciente, fecha_registro__date__gte=desde)
        .order_by('fecha_registro')
    )
    if not registros:
        return {'labels': [], 'temps': [], 'evas': [], 'fcs': [], 'alertas_idx': []}

    turnos = _turnos_por_registro(registros)
    # Una sola query batched — evita N+1 y no depende del related_name
    # equivocado ("alerta_set") que traía el borrador original.
    ids_con_alerta_alta = set(
        Alerta.objects
        .filter(registro_origen__in=registros, severidad='ALTA', resuelta=False)
        .values_list('registro_origen_id', flat=True)
    )

    labels, temps, evas, fcs, alertas_idx = [], [], [], [], []
    for i, r in enumerate(registros):
        labels.append(timezone.localtime(r.fecha_registro).strftime('%d/%m') + f' {turnos[r.pk]}')
        temps.append(float(r.temperatura))
        evas.append(r.dolor_eva)
        fcs.append(r.frecuencia_cardiaca)  # None se serializa como null — Chart.js abre un hueco, no cae a 0
        if r.pk in ids_con_alerta_alta:
            alertas_idx.append(i)

    return {'labels': labels, 'temps': temps, 'evas': evas, 'fcs': fcs, 'alertas_idx': alertas_idx}


_JS_GRAFICAS_TEMPLATE = """
<div id="graficas-__PID__" style="margin-top:8px;">
  <div style="margin-bottom:12px;font-size:0.85em;">
    Ver:
    <a href="#" onclick="cambiarPeriodo___PID__(7,this);return false;"
       style="font-weight:600;color:#374151;">7 días</a> ·
    <a href="#" onclick="cambiarPeriodo___PID__(14,this);return false;"
       style="color:#6b7280;">14 días</a> ·
    <a href="#" onclick="cambiarPeriodo___PID__(30,this);return false;"
       style="color:#6b7280;">30 días</a>
  </div>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;display:flex;justify-content:space-between;">
    <span>Temperatura (°C)</span>
    <span style="color:#fca5a5;">- - umbral fiebre: 37.9°C</span>
  </div>
  <canvas id="temp-__PID__" height="90" style="width:100%;margin-bottom:16px;"></canvas>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;">Dolor EVA (1-10)</div>
  <canvas id="eva-__PID__" height="90" style="width:100%;margin-bottom:16px;"></canvas>

  <div style="margin-bottom:4px;font-size:0.8em;color:#6b7280;display:flex;justify-content:space-between;">
    <span>Frecuencia cardíaca (lpm)</span>
    <span style="color:#6b7280;">- - 101 lpm  · - - 110 lpm</span>
  </div>
  <canvas id="fc-__PID__" height="90" style="width:100%;margin-bottom:8px;"></canvas>
  <p style="font-size:0.75em;color:#9ca3af;margin:4px 0 0;">
    Puntos rojos = alerta ALTA sin resolver ese registro. Huecos en la
    línea = el paciente no midió ese dato ese día (no es un valor de 0).
  </p>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
(function() {
  var DATOS = __CTX__;
  var pid = "__PID__";
  var charts = {};

  function puntoColor(idx, alertasIdx) {
    return alertasIdx.indexOf(idx) !== -1 ? '#dc2626' : 'transparent';
  }
  function puntoRadio(idx, alertasIdx, valor) {
    if (valor === null || valor === undefined) return 0;
    return alertasIdx.indexOf(idx) !== -1 ? 5 : 3;
  }

  var optsBase = {
    responsive: true,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 10 }, maxRotation: 45 } },
      y: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 10 } } }
    }
  };

  function init() {
    var d = DATOS['7'];

    charts.temp = new Chart(document.getElementById('temp-' + pid), {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [
          {
            label: 'Temperatura', data: d.temps, borderColor: '#dc2626', borderWidth: 2,
            pointBackgroundColor: d.temps.map(function(v, i) { return puntoColor(i, d.alertas_idx); }),
            pointRadius: d.temps.map(function(v, i) { return puntoRadio(i, d.alertas_idx, v); }),
            tension: 0.3, spanGaps: false
          },
          {
            label: 'Umbral fiebre', data: d.labels.map(function() { return 37.9; }),
            borderColor: '#fca5a5', borderWidth: 1, borderDash: [4, 4], pointRadius: 0, tension: 0
          }
        ]
      },
      options: Object.assign({}, optsBase, {
        scales: Object.assign({}, optsBase.scales, {
          y: Object.assign({}, optsBase.scales.y, { min: 35, max: 40, ticks: { stepSize: 0.5, font: { size: 10 } } })
        })
      })
    });

    charts.eva = new Chart(document.getElementById('eva-' + pid), {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [{
          label: 'Dolor EVA', data: d.evas, borderColor: '#f59e0b', borderWidth: 2,
          pointBackgroundColor: d.evas.map(function(v, i) { return puntoColor(i, d.alertas_idx); }),
          pointRadius: d.evas.map(function(v, i) { return puntoRadio(i, d.alertas_idx, v); }),
          tension: 0.3, spanGaps: false
        }]
      },
      options: Object.assign({}, optsBase, {
        scales: Object.assign({}, optsBase.scales, {
          y: Object.assign({}, optsBase.scales.y, { min: 0, max: 10, ticks: { stepSize: 2, font: { size: 10 } } })
        })
      })
    });

    charts.fc = new Chart(document.getElementById('fc-' + pid), {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [
          {
            label: 'FC', data: d.fcs, borderColor: '#3b82f6', borderWidth: 2,
            pointBackgroundColor: d.fcs.map(function(v, i) { return puntoColor(i, d.alertas_idx); }),
            pointRadius: d.fcs.map(function(v, i) { return puntoRadio(i, d.alertas_idx, v); }),
            tension: 0.3, spanGaps: false
          },
          {
            label: 'Taquicardia leve', data: d.labels.map(function() { return 101; }),
            borderColor: '#fcd34d', borderWidth: 1, borderDash: [3, 3], pointRadius: 0
          },
          {
            label: 'Taquicardia', data: d.labels.map(function() { return 110; }),
            borderColor: '#f87171', borderWidth: 1, borderDash: [3, 3], pointRadius: 0
          }
        ]
      },
      options: optsBase
    });
  }

  window.cambiarPeriodo___PID__ = function(dias, link) {
    document.querySelectorAll('#graficas-' + pid + ' a').forEach(function(a) {
      a.style.fontWeight = '';
      a.style.color = '#6b7280';
    });
    link.style.fontWeight = '600';
    link.style.color = '#374151';

    var d = DATOS[String(dias)];
    if (!d) { return; }

    ['temp', 'eva', 'fc'].forEach(function(tipo) {
      var chart = charts[tipo];
      if (!chart) { return; }
      var dataMap = { temp: d.temps, eva: d.evas, fc: d.fcs };
      chart.data.labels = d.labels;
      chart.data.datasets[0].data = dataMap[tipo];
      chart.data.datasets[0].pointBackgroundColor = dataMap[tipo].map(
        function(v, i) { return puntoColor(i, d.alertas_idx); }
      );
      chart.data.datasets[0].pointRadius = dataMap[tipo].map(
        function(v, i) { return puntoRadio(i, d.alertas_idx, v); }
      );
      for (var j = 1; j < chart.data.datasets.length; j++) {
        var val = chart.data.datasets[j].data[0];
        chart.data.datasets[j].data = d.labels.map(function() { return val; });
      }
      chart.update();
    });
  };

  if (typeof Chart !== 'undefined') {
    init();
  } else {
    document.currentScript.previousElementSibling.addEventListener('load', init);
  }
})();
</script>
"""


def _grafica_signos_vitales(paciente):
    """
    Devuelve HTML con 3 gráficas Chart.js (temperatura, dolor EVA, FC) con
    selector de período 7/14/30 días que cambia en el navegador sin
    recargar la página (P-9, rediseño 01/07/2026).

    Los 3 períodos se precalculan en Python y se serializan una sola vez
    con json.dumps() en un objeto DATOS — nunca se interpola una lista
    Python directo en el HTML/JS (regla de seguridad, BITACORA 01/07/2026).
    """
    tiene_datos = RegistroDiario.objects.filter(paciente=paciente).exists()
    if not tiene_datos:
        return '<p style="color:#6b7280;">Sin datos para graficar todavía.</p>'

    datos = {str(dias): _datos_grafica(paciente, dias) for dias in DIAS_GRAFICA_OPCIONES}
    ctx = json.dumps(datos)

    return (
        _JS_GRAFICAS_TEMPLATE
        .replace('__CTX__', ctx)
        .replace('__PID__', str(paciente.pk))
    )


class TieneAlertaActivaFilter(admin.SimpleListFilter):
    """Filtro de pacientes por alertas sin resolver."""
    title = 'alertas activas'
    parameter_name = 'alerta_activa'

    def lookups(self, request, model_admin):
        return [
            ('si', 'Con alertas sin resolver'),
            ('no', 'Sin alertas pendientes'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'si':
            return queryset.filter(alertas__resuelta=False).distinct()
        if self.value() == 'no':
            return queryset.exclude(alertas__resuelta=False).distinct()
        return queryset


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'cedula', 'medico_nombre',
                    'fecha_cirugia', 'activo']
    list_filter = ['activo', 'tipo_cirugia', 'medico_responsable', TieneAlertaActivaFilter]
    search_fields = ['nombre_completo', 'cedula', 'telefono_whatsapp',
                     'medico_responsable__first_name',
                     'medico_responsable__last_name',
                     'medico_responsable__username']
    readonly_fields = ['fecha_consentimiento', 'grafica_signos_vitales', 'historial_paciente']

    def get_readonly_fields(self, request, obj=None):
        # Captura ?dias= de la URL para que historial_paciente() lo use al
        # renderizar — los readonly_fields solo reciben `obj`, no `request`.
        # La gráfica (grafica_signos_vitales) tiene su propio selector de
        # período independiente, en el navegador — no usa este parámetro.
        self._dias_historial = _clamp_dias_historial(request.GET.get('dias'))
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        """A-1: advierte al médico si registra un paciente con ingreso tardío
        — el comando desactivar_pacientes_vencidos lo desactivaría pronto.
        Bloque 7 (HABEAS DATA): registra/limpia fecha_consentimiento en
        sincronía con el checkbox de consentimiento_informado."""
        if not change:
            dias_post = (timezone.localdate() - obj.fecha_cirugia).days
            if dias_post >= DIAS_SEGUIMIENTO - 2:
                messages.warning(
                    request,
                    f"Advertencia: este paciente tiene {dias_post} días postoperatorios. "
                    f"El sistema lo desactivará automáticamente en cuanto alcance "
                    f"{DIAS_SEGUIMIENTO} días. Considere si el seguimiento remoto es "
                    f"apropiado para este caso."
                )
        if obj.consentimiento_informado and not obj.fecha_consentimiento:
            obj.fecha_consentimiento = timezone.now()
        elif not obj.consentimiento_informado and obj.fecha_consentimiento:
            obj.fecha_consentimiento = None
        super().save_model(request, obj, form, change)

    @admin.display(description='Evolución signos vitales')
    def grafica_signos_vitales(self, obj):
        if obj.pk is None:
            return '—'
        return mark_safe(_grafica_signos_vitales(obj))

    @admin.display(description='Historial del paciente')
    def historial_paciente(self, obj):
        if obj.pk is None:
            return '—'
        dias = getattr(self, '_dias_historial', DIAS_HISTORIAL_DEFAULT)
        return mark_safe(_historial_paciente(obj, dias=dias))

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
    readonly_fields = ['fecha_alerta', 'fecha_resolucion', 'registro_origen',
                       'motivo_resolucion', 'motivo_resolucion_detalle']

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
        """Bloque A: muestra un formulario intermedio para capturar el motivo
        de resolución (obligatorio) antes de marcar las alertas como resueltas.

        Scoping: un médico no-superuser solo puede resolver alertas de sus
        propios pacientes — se re-filtra por permisos en cada paso, nunca se
        confía en los pk que llegan del cliente.
        """
        if _solo_propios(request):
            queryset = queryset.filter(paciente__medico_responsable=request.user)

        contexto = {
            **self.admin_site.each_context(request),
            'alertas': queryset,
            'title': 'Selecciona el motivo de resolución',
            'accion': 'marcar_resuelta',
        }
        plantilla = 'admin/signos_sintomas/alerta/motivo_resolucion.html'

        # Paso 1: primera vez que se dispara la acción → mostrar formulario.
        if 'aplicar' not in request.POST:
            contexto['form'] = MotivoResolucionForm()
            return TemplateResponse(request, plantilla, contexto)

        # Paso 2: formulario enviado → validar y aplicar.
        form = MotivoResolucionForm(request.POST)
        if not form.is_valid():
            contexto['form'] = form
            return TemplateResponse(request, plantilla, contexto)

        motivo = form.cleaned_data['motivo_resolucion']
        detalle = form.cleaned_data['motivo_resolucion_detalle']
        actualizadas = queryset.filter(resuelta=False).update(
            resuelta=True,
            fecha_resolucion=timezone.now(),
            motivo_resolucion=motivo,
            motivo_resolucion_detalle=detalle or None,
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


# --- Branding del Admin (identidad "calma clínica") + tablero de triage ---
# El texto de la cabecera y el título de la página de inicio. El índice usa una
# plantilla propia (admin/index_panel.html) que EXTIENDE el índice real de
# Django e inyecta el tablero encima con {{ block.super }} — no se pierde nada
# del admin (lista de apps, barra lateral, acciones recientes).
admin.site.site_header = 'Seguimiento Postquirúrgico'
admin.site.site_title = 'Seguimiento Postquirúrgico'
admin.site.index_title = 'Panel del médico'
admin.site.index_template = 'admin/index_panel.html'
