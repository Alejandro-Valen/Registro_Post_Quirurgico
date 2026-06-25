# Auditoría de Cierre — Sprint 3
**Fecha:** 21/06/2026
**Rama auditada:** sprint-3-whatsapp
**Auditores:** Claude Code (coherencia interna y lógica clínica) +
Codex (seguridad y escalabilidad, pasada web + pasada local)
**Veredicto:** el código es correcto y funcional. Ningún hallazgo
rompe lo que hoy funciona. **El merge a `Desarrollo` puede proceder.**
Lo que NO debe ocurrir es ir de `Desarrollo` a producción real con
pacientes sin resolver el Grupo A completo.

**Ruta recomendada:**
1. Merge `sprint-3-whatsapp` → `Desarrollo` (ahora)
2. Rama nueva `sprint-3-hardening` desde `Desarrollo`
3. Resolver Grupo A y Grupo B en `sprint-3-hardening`
4. Merge `sprint-3-hardening` → `Desarrollo`
5. Sprint 4 (dashboard) arranca sobre base endurecida

---

## GRUPO A — Obligatorio antes de exponer con pacientes reales

### A1 — Conversación abandonada no se reinicia al día siguiente
**Problema:** si un paciente abandona el cuestionario a mitad de flujo
(ej. en el paso 5/10) y al día siguiente intenta iniciar de nuevo, el
bot lo trata como si siguiera respondiendo la pregunta de ayer. Los
campos `temp_` de ayer persisten y se mezclan con los de hoy en un
solo `RegistroDiario` fechado hoy (temperatura de ayer + el resto de
hoy). El reinicio diario solo dispara si `estado == COMPLETADO`.
**Archivo:** `bot.py:186-188`
**Dirección:** extender la condición de reinicio para cubrir
conversaciones incompletas de un día calendario anterior — comparar
`fecha_actualizacion` (o un sello de día) contra `timezone.localdate()`
también cuando el estado está en pleno flujo, no solo en COMPLETADO.
**Decisión de diseño pendiente:** ¿reiniciar silenciosamente (el
paciente no se entera y empieza de cero) o avisar con un mensaje tipo
"Hemos reiniciado tu reporte de hoy, empecemos de nuevo"? El chat nuevo
presenta opciones al Arquitecto antes de implementar.

### A2 — FC y FR obligatorias bloquean al paciente sin dispositivo
**Problema:** `frecuencia_cardiaca` y `frecuencia_respiratoria` son
`null=True` en el modelo (diseñadas para "no capturado"), pero el bot
exige un número válido en rango (30-250 y 5-60) para avanzar. Un
paciente con la batería del oxímetro agotada o que no sabe tomarse el
pulso queda atascado en el paso 8 o 9 y no puede completar ningún
reporte del día.
**Archivo:** `bot.py:300-316`
**Dirección:** aceptar respuestas como "no sé", "no tengo" o "sin dato"
en los pasos de FC y FR, guardar `None` en el campo, y avanzar al
siguiente paso. El campo ya acepta null — solo falta que el parser del
bot lo permita.
**Decisión de diseño pendiente:** definir el vocabulario exacto de
"saltar" (¿solo "no sé"? ¿también "0"? ¿un comando especial?) y si se
muestra un mensaje de confirmación al paciente al saltar.

### A3 — Webhook sin idempotencia (reintentos de Twilio crean duplicados)
**Problema:** Twilio reintenta automáticamente el webhook si no recibe
respuesta 200 en tiempo. El endpoint no usa `MessageSid`/`SmsMessageSid`
para detectar mensajes ya procesados. Un reintento puede crear un segundo
`RegistroDiario` con las mismas respuestas, duplicando alertas clínicas.
**Archivo:** `views.py:20-23`
**Dirección:** persistir el `SmsMessageSid` de cada mensaje procesado
(campo nuevo en `ConversacionWhatsApp` o tabla de mensajes procesados) y
rechazar mensajes cuyo SID ya fue procesado antes de tocar ningún estado.
**Nota:** es distinto al gating de 2×/día — ese es de diseño; este es
de infraestructura (un mismo mensaje procesado dos veces).

### A4 — Sin bloqueo transaccional en el estado conversacional
**Problema:** dos mensajes del mismo paciente que llegan casi
simultáneamente (ej. doble tap en enviar) leen el mismo estado de
`ConversacionWhatsApp` sin bloqueo de fila. Ambos pueden avanzar el
flujo de forma inconsistente o generar dos `RegistroDiario` para el
mismo paso.
**Archivo:** `bot.py:182-211`
**Dirección:** envolver el procesamiento en `transaction.atomic()` y
cargar `ConversacionWhatsApp` con `select_for_update()` para que el
segundo mensaje espere a que el primero termine.

### A5 — Sin rate limiting en el webhook
**Problema:** no hay protección contra flood de mensajes válidos (ej.
paciente que envía mensajes repetidamente, o número de WhatsApp
comprometido). Cada mensaje dispara consultas a la BD y evaluación del
alert_engine. Sin límite, puede saturar la BD o generar alertas falsas.
**Archivo:** `views.py:13-23`
**Dirección:** agregar rate limiting por número de teléfono (`From`)
con una ventana temporal razonable (ej. máximo 20 mensajes por hora por
número). Puede implementarse con `django-ratelimit` o con un contador
en caché (Django cache framework).

### A6 — DEBUG=True en entorno con Twilio/ngrok real
**Problema:** el `.env` local tiene `DEBUG=True` mientras las
credenciales reales de Twilio están configuradas y el túnel de ngrok
está expuesto. Un error de Django en ese estado muestra stacktrace
completo con variables locales (incluyendo datos de pacientes) al
cliente que hizo la request.
**Archivo:** `.env` local (no commiteado) y `settings.py`
**Dirección:** separar configuración por entorno — `DEBUG=False` siempre
que haya credenciales reales de Twilio activas, sin excepción. Crear
`settings_local.py` para desarrollo y `settings_production.py` para
producción, con `DEBUG` hardcodeado a `False` en el de producción.

---

## GRUPO B — Hardening de producción (antes de abrir a más de 1 médico)

### B1 — settings.py sin configuración de producción
**Problema:** faltan `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
`SECURE_SSL_REDIRECT`, `HSTS`, `CSRF_TRUSTED_ORIGINS`.
**Archivo:** `settings.py`
**Dirección:** crear `settings_production.py` que extienda el base e
incluya todas las directivas de seguridad HTTPS de Django. Documentar
en el ROADMAP qué variable de entorno activa cada configuración.

### B2 — Sin LOGGING configurado — datos médicos pueden quedar en logs
**Problema:** Django sin logging explícito puede escribir en stdout el
`Body` del webhook (síntomas del paciente) y el `From` (teléfono) ante
cualquier excepción no capturada.
**Archivo:** `settings.py`
**Dirección:** configurar `LOGGING` en settings con handlers que filtren
PII/PHI. Agregar `@sensitive_post_parameters('From', 'Body')` al view
del webhook.

### B3 — Path síncrono del webhook puede causar timeout de Twilio
**Problema:** el webhook hace todo en secuencia (recibir → procesar bot
→ crear RegistroDiario → evaluar 8 reglas del alert_engine con múltiples
queries) antes de devolver 200 a Twilio. Twilio espera máximo 15 segundos
y reintenta si no hay respuesta — lo que a su vez dispara el problema A3.
**Archivo:** `bot.py:339-355`, `alert_engine.py:85-450`
**Dirección:** responder 200 a Twilio inmediatamente tras validar la
firma, y mover la evaluación del alert_engine a un job en background
(Celery + Redis, o Django-Q como alternativa más liviana). Esta es la
solución de fondo para A3 también.

### B4 — fecha_registro sin índice eficiente para los filtros clínicos
**Problema:** las 6 reglas de días calendario filtran por
`fecha_registro__date=dia`, que en PostgreSQL con `USE_TZ` genera
`(fecha_registro AT TIME ZONE ...)::date = ...` — una expresión de
función que un índice B-tree normal no puede usar. Con 10,000+ registros
son full table scans.
**Archivo:** `models.py:153`, `alert_engine.py` (múltiples líneas)
**Dirección (dos opciones, el chat nuevo elige):**
- Opción A: cambiar los filtros a rangos `fecha_registro__gte`/`__lt`
  con los límites del día en zona local (usables por índice B-tree) y
  agregar `db_index=True` a `fecha_registro`.
- Opción B: crear un índice funcional en PostgreSQL sobre la expresión
  de cast a fecha en la zona del proyecto. Requiere migración con
  `RunSQL`.

### B5 — Django Admin expuesto en /admin/ sin controles adicionales
**Problema:** la URL por defecto, sin 2FA, sin lockout de intentos,
sin restricción de IP. Con datos médicos reales, es el vector de ataque
más evidente.
**Archivo:** `urls.py:21`
**Dirección:** cambiar la URL del admin a algo no trivial, agregar
`django-axes` para lockout, considerar 2FA con `django-otp` o similar.
Para producción, restringir por IP o VPN.

### B6 — Admin sin scoping por médico
**Problema:** cualquier usuario staff ve todos los pacientes y alertas
de todos los médicos. La FK `medico_responsable→User` ya está lista —
solo falta el `get_queryset()` que filtre por `request.user`.
**Archivo:** `admin.py`
**Dirección:** en Sprint 4, agregar `get_queryset()` en `PacienteAdmin`,
`RegistroDiarioAdmin` y `AlertaAdmin` que filtre por
`medico_responsable=request.user` (con bypass para superuser).

### B7 — Cobertura de tests del webhook incompleta
**Problema:** no hay tests para header de firma ausente, header
malformado, body vacío, idempotencia (mismo MessageSid dos veces), ni
carrera concurrente.
**Archivo:** `tests.py:1238-1275`
**Dirección:** agregar casos negativos del webhook como parte del
hardening, especialmente idempotencia una vez que A3 esté implementado.

---

## GRUPO C — Backlog (sin fecha comprometida)

- **C1** — `evaluar_registro()` monolítica ~450 líneas; Regla 4 antes
  de Regla 3 en el archivo. Refactor: extraer cada regla a
  `_evaluar_X(registro)` y orquestar desde `evaluar_registro()`.
- **C2** — Choices no son constraints de BD; `objects.create()` no
  llama `full_clean()`. Agregar `CheckConstraint` para campos clínicos
  categóricos.
- **C3** — Django 6.0.5 → actualizar a 6.0.6 (última oficial con
  parches de seguridad).
- **C4** — Decimales truncados silenciosamente en parsers de FC/FR
  (ej. "78.5" → 78 sin avisar al paciente).
- **C5** — Mensaje de alerta no visible en `list_display` del Admin
  sin abrir el detalle.
- **C6** — 403 del webhook revela "Firma de Twilio inválida" (mejor
  devolver 403 genérico sin detalles).
- **C7** — Endpoint de contacto web sin rate limit ni validación de
  longitud.

---

## Lo que quedó limpio (no requiere acción)

- ✅ Las 8 reglas usan `timezone.localdate()` sin residuos de UTC.
- ✅ `_crear_registro()` pasa los 12 campos al create().
- ✅ `_limpiar_temporales()` limpia los 12 temp_ sin excepción.
- ✅ Todos los estados tienen handler; todos los handlers tienen estado.
- ✅ Regla 8 (FC) usa `is not None` explícito.
- ✅ El bot no crashea con mensajes de audio/imagen/sticker.
- ✅ Validación de firma de Twilio es fail-safe (falla cerrado).
- ✅ `medico_responsable` ya es FK a `auth.User` con `SET_NULL`.
- ✅ Todos los campos categóricos usan `choices=` en el modelo.
- ✅ Migraciones sin secretos ni `RunPython` riesgoso.
