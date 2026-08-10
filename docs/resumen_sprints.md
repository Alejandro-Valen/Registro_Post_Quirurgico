# Resumen de entregas por sprint, bloque y loop

> **Qué es esto.** Un índice compacto de qué entregó cada etapa, para ubicarse
> sin leer los 197.000 caracteres de `BITACORA.md`. La cronología completa —con
> los problemas encontrados y cómo se resolvieron— vive en la BITÁCORA; esto es
> el mapa, no el territorio.
>
> **No es fuente de verdad sobre el sistema actual.** Describe lo que se hizo en
> su momento. Para saber cómo funciona el sistema hoy: `docs/reglas_clinicas.md`,
> `docs/modelos_datos.md`, `docs/bot_whatsapp.md` y el código.

---

## Sprint 5 — bloques (rama `sprint-5-produccion`)

Resumen de lo resuelto en `sprint-5-produccion` (Bloques 1-6):
- Bloque 1: campo `Paciente.cedula` (único, obligatorio para nuevos,
  migración 0014) + command `desactivar_pacientes_vencidos` (10 días
  postop, `--dry-run`, idempotente). 9 tests.
- Bloque 2: emojis eliminados de todos los mensajes de `bot.py` (P-11).
- Bloque 3: `TieneAlertaActivaFilter` en `PacienteAdmin` (usa
  `alertas__resuelta`, el `related_name` real) + historial configurable
  por días (`_historial_paciente`, selector `?dias=3/7/10`, actualizado en
  Loop 3). 8 tests.
- Bloque 4: gráficas Chart.js (temperatura/dolor/FC) en la ficha del
  paciente, con selector 3/7/10 días sin recarga de página, turno M/T
  por `CheckInProgramado.etiqueta` real (no por hora — decisión D2), y
  puntos rojos para alertas ALTA sin resolver. 9 tests.
- Bloque 5: SMTP real (`EMAIL_*` en `settings_production.py`) probado primero
  en local. La implementación inicial con datos identificables fue sustituida
  en el Loop 4 por una bandeja persistente, timeout y un correo genérico sin
  PHI/PII. Resend por API HTTPS quedó activo y con entrega real confirmada.
- Bloque 6: `docs/cron_setup.md` (4 commands, orden obligatorio:
  `desactivar_pacientes_vencidos` **antes** de `crear_checkins_diarios`)
  y `docs/transferencia_cuentas.md`.
- Correcciones pre-Bloque 7 (A-1 a A-4, 02/07/2026): guard
  `DIAS_GRACIA_INGRESO` + advertencia en Admin para ingreso tardío;
  `Paciente.clean()` exige cédula solo en pacientes nuevos (`cedula` es
  `blank=True` a nivel de campo a propósito); `seed_demo` aborta si
  `DEBUG=False` y su usuario demo ya no es superusuario; email de alerta
  ALTA con teléfono, cédula y hora en zona Bogotá. 12 tests.
- Bloque 7 (HABEAS DATA, 02/07/2026): `Paciente.consentimiento_informado`
  + `fecha_consentimiento` (auto-registrada en `PacienteAdmin.save_model`)
  + guard en `bot.py` que bloquea el flujo si el paciente no ha sido
  confirmado por su médico. Plantilla `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`
  ya aprobada por el Arquitecto, copiada sin modificar. 6 tests.
- Bloque A (post-Bloque 7, 02/07/2026): `Alerta.motivo_resolucion` +
  `motivo_resolucion_detalle` (migración 0017). La acción "Marcar como
  resuelta" del Admin muestra un formulario intermedio que exige elegir un
  motivo ("Otro" pide detalle); scoping por médico en cada paso. 6 tests.
- Bloque B (post-Bloque 7, 02/07/2026): mensaje de cierre del bot según
  severidad de las alertas del check-in (neutro / MEDIA / ALTA), sin
  revelar el tipo de alerta ni valores. `evaluar_registro` pasó a correr
  síncrono dentro de `_crear_registro` (savepoint defensivo: un fallo del
  engine nunca pierde el reporte del paciente). 8 tests.
- Bloque C (post-Bloque 7, 02/07/2026): **no-op verificado.** Se buscó
  limpiar restos de "Sugarbaker"/"HIPEC" en `index.html`; la auditoría
  confirmó que NO existen en `home` ni en ninguna plantilla — el único uso
  legítimo es la opción `sugarbaker_hipec` de `tipo_cirugia` en `models.py`
  (no se toca) y las migraciones (inmutables). Nada que limpiar.

---

## Sprint 5 — loops de confiabilidad y producción

- **Pausa segura y documentación:** `docs/README.md` clasifica fuentes vigentes,
  historia y documento legal canónico. El barrido del 21/07 actualizó despliegue,
  cron, transferencia, variables, RAG diferido y protocolo de reanudación. No
  hubo cambios funcionales, PR ni merge.
- **Panel del médico (Django Admin):** `/admin/` solo en desarrollo y ruta
  privada definida por `ADMIN_URL` en producción, con branding "calma clínica"
  (override de `admin/base_site.html` + `signos_sintomas/static/admin/css/panel_admin.css`
  que sobreescribe las variables del Admin) y un **tablero de triage** como
  índice (`admin/index_panel.html` extiende el índice real + template tag
  `{% panel_triage %}` en `signos_sintomas/templatetags/panel_admin.py`, scoping
  por médico). Todo el índice centrado en 1280px. NO se forkeó el admin: se
  conservan listas, filtros, búsqueda, gráficas y el flujo de resolver.
- **Alertas agrupadas por problema:** una alerta abierta por (paciente, tipo)
  con contador `veces` (badge ×N en tablero y Admin); correo ALTA solo al
  escalar. Ver sección "Modelos → Alerta".
- **Loop 2 de confiabilidad:** el `MessageSid` se reclama en PostgreSQL sin
  guardar teléfono ni Body; el avance del bot y el recibo se confirman en una
  misma transacción. Cada registro conserva el estado de su evaluación y el
  command `reintentar_evaluaciones_alertas` recupera PENDIENTE/ERROR. La BD
  garantiza una sola alerta abierta por paciente/tipo y la conversación queda
  ligada al check-in exacto para coordinarse con el cron.
- **Loop 3 de experiencia médica (cerrado):** validado con
  una cuenta staff de médico de privilegio mínimo (demo local). El tablero muestra pendientes
  acumulados hasta su resolución, prioriza gravedad/recurrencia/última detección,
  amplió su ancho y corrigió el contraste de la marca. Historial y gráficas
  usan periodos exactos 3/7/10; el historial Admin distingue seguimiento
  activado/desactivado. `MensajeContacto.medico_destinatario` limita cada
  mensaje al médico asignado; los mensajes sin asignar son solo para
  superusuario y el tablero muestra los pendientes propios sin exponer el
  cuerpo. `DeteccionAlerta` desglosa las detecciones nuevas de cada ×N por
  registro/check-in y conserva el contador anterior sin backfill ficticio.
  El filtro de fecha ahora dice "Todas las fechas". El detalle usa lenguaje de
  producto ("Detecciones de la alerta") y los seeds pueden limpiarse sin
  violar relaciones protegidas. **256 tests OK.**
- **Landing (P-12):** la página `/` (app `home`) se convirtió en la presentación
  del médico + sistema, con un **sistema de diseño compartido**
  (`home/static/home/css/site.css` + `home/static/home/js/pulse.js` +
  `home/templates/home/base.html`) que reusan `index.html` y `contacto.html`.
  Nav conectado a `/contacto/` y al Admin (enlace "Acceso médico" →
  `{% url 'admin:index' %}`). Contenido del médico en marcadores `[entre
  corchetes]` + flag `MOSTRAR_AVISO_BOCETO` en `home/views.py` (aviso de boceto
  que se apaga con los datos reales). 13 pruebas en `home/tests.py`, incluidas
  asignación y aislamiento de mensajes de contacto.
- **Demo del dashboard:** comando
  `signos_sintomas/management/commands/seed_demo_produccion.py` — idempotente y
  **seguro para producción** (a diferencia de `seed_demo`, bloqueado por A-3):
  `--confirmar` obligatorio, NO crea usuarios (asigna a un médico existente con
  `--medico` o al primer superusuario), pacientes marcados `DEMO — ` /
  cédula `DEMO-000X` / teléfono ficticio, y **reversible** con
  `--limpiar --confirmar`. Crea 2 pacientes de ejemplo con registros y alertas.
  En Railway se renovaron el 19/07: 2 activos, 18 registros, 10 alertas abiertas
  agrupadas y 36 detecciones, asignados temporalmente al superusuario `SeñorAL`;
  esos datos fueron posteriormente limpiados y no son datos clínicos reales.
- **Loop 4 de producción (21/07/2026):** Django y dependencias directas fijadas,
  CSP activo, Chart.js 4.5.1 servido localmente y correo ALTA desacoplado del
  webhook mediante `NotificacionAlerta` (migración 0024). El correo es genérico:
  solo ID opaco y enlace al panel, sin nombre, teléfono, cédula, síntomas ni
  mensaje clínico. Reintentos con timeout y espera creciente. Resend quedó
  integrado por API HTTPS con clave idempotente por alerta y validación de
  respuesta. Quedó activo y entregó el aviso controlado de la alerta demo #90
  a `correo-del-proyecto@ejemplo.com`; el Arquitecto lo confirmó en spam.
- **IP tras Railway:** el rate limit del formulario usa `X-Real-IP` solo con
  `TRUST_RAILWAY_PROXY=True`, marca `X-Railway-Edge` válida e IP bien formada;
  en cualquier otro caso conserva `REMOTE_ADDR`. No confía en
  `X-Forwarded-For`.
- **Loop 5 de validación (21/07/2026):** firma Twilio válida aceptada; dos
  requests simultáneos del mismo SID ejecutan el bot una sola vez; dos workers
  no duplican el correo; un fallo tras crear una alerta parcial revierte alerta
  y outbox; el flujo de 10 preguntas por webhook crea registro, alerta y
  notificación coherentes. La carga local completó 50 pacientes concurrentes,
  550 webhooks y 50 registros en 5,03 s, sin solicitudes de 15 s ni recibos
  incompletos. El Sandbox real completó un check-in normal con
  `medico_piloto`; los datos ficticios se eliminaron después de verificar.
- **Loop 6 de cierre técnico (21/07/2026):** se completaron por el Sandbox los
  tonos MEDIA y ALTA y se verificaron alerta, detección, registro, check-in,
  panel médico y correo real. Dos cuestionarios dentro de una hora alcanzaron
  el límite de 20 mensajes: el webhook ya no responde en silencio y devuelve
  una explicación neutra (`c12bfe5`). Un primer intento de Resend registró
  `OSError`; el outbox lo conservó PENDIENTE y el mismo comando de cron lo envió
  correctamente al reintentar, sin duplicarlo. Requests subió a 2.33.0 por
  PYSEC-2026-2275; `pip-audit` quedó limpio y los **280 tests** pasaron de nuevo.
  Se eliminaron transaccionalmente el paciente y todos los datos ficticios.
- **Estado Railway (21/07/2026):** web y ambos cron en `SUCCESS` sobre
  `0d12d88`; HTTPS 200, `/admin/` devuelve 404, la ruta privada redirige al
  login, CSP presente y Chart.js local responde 200. `check --deploy` remoto
  quedó sin issues. `cron-tarde` fue reutilizado temporalmente como
  `cron_operativo` cada 5 minutos por el límite del plan; ejecutó en vivo
  cierre, reintento del motor y bandeja de correo. La cuenta `medico_piloto`
  fue probada por el Arquitecto, conserva `staff=True`, `superuser=False` y el
  correo `correo-del-proyecto@ejemplo.com`; los pacientes ficticios del Loop 6
  ya fueron eliminados.

---

## Preguntas de arquitectura ya resueltas

Ambas preguntas de arquitectura que quedaban abiertas ya se resolvieron:
cron en **Linux** (Railway/Render, no Windows Task Scheduler) y SMTP con
**Gmail + contraseña de aplicación**.
