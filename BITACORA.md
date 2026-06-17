# Bitácora del Proyecto — MVP Sugarbaker
## Clínica Somer — Medellín, Colombia

---

## Sprint 0 — Configuración Base y Seguridad
**Fecha:** 09/06/2026
**Responsable:** Alejandro (Dev) + León (Arquitecto IA)
**Estado:** COMPLETADO ✅

### Qué se hizo
- Diagnóstico del repositorio existente — identificados 3 problemas críticos:
  SECRET_KEY expuesta en GitHub, SQLite en vez de PostgreSQL, zona horaria UTC
- Instaladas dependencias: `python-decouple`, `psycopg2-binary`
- Creado archivo `.env` con SECRET_KEY nueva en cada máquina (nunca sube a GitHub)
- Creado `.env.example` como plantilla para el equipo
- Modificado `settings.py`: SECRET_KEY y DEBUG desde `.env`, base de datos
  cambiada a PostgreSQL, zona horaria a `America/Bogota`, idioma a `es-co`
- Generado `requirements.txt` con `pip freeze`
- Actualizado `.gitignore` para excluir `.env`
- Creado `CLAUDE.md` con contexto clínico completo del proyecto
- Creado `BITACORA.md` (este archivo)
- Push exitoso a rama `Desarrollo`
- Verificación: `python manage.py check` → 0 errores

### Decisiones tomadas
- `python-decouple` sobre `django-environ` — sintaxis más limpia
- PostgreSQL desde el día 0 — no migrar datos clínicos reales después
- `America/Bogota` es crítico para que los timestamps de reportes sean
  clínicamente correctos
- `BigAutoField` como DEFAULT_AUTO_FIELD — soporta hasta 9 mil millones
  de registros vs 2 millones del AutoField estándar

### Problemas encontrados y resueltos
- SECRET_KEY ya había estado expuesta en repo público → rotada inmediatamente
- El `settings.py` modificado no se había incluido en el commit del compañero →
  León lo recreó directamente en su máquina

---

## Sprint 1 — Modelos Clínicos y Base de Datos
**Fecha:** 10/06/2026 — 11/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** COMPLETADO ✅

### Qué se hizo

**Modelos clínicos (signos_sintomas/models.py):**
- Creado modelo `Paciente` con campos: nombre_completo, telefono_whatsapp
  (único, formato +57...), fecha_cirugia, medico_responsable, activo,
  fecha_registro
- Creado modelo `RegistroDiario` con las 6 variables clínicas del protocolo
  Sugarbaker: temperatura, dolor_eva, volumen_drenaje_ml, aspecto_drenaje,
  presencia_gases, episodios_nauseas. Campo `dia_postoperatorio` calculado
  automáticamente al guardar
- Creado modelo `Alerta` con tipos SEPSIS, FUGA_ANASTOMOTICA, ILEO_PARALITICO,
  DOLOR_AGUDO y severidades ALTA, MEDIA, BAJA. Campo `resuelta` para que el
  oncólogo marque alertas atendidas

**Panel del oncólogo (signos_sintomas/admin.py):**
- Registrados los 3 modelos con `@admin.register`
- Configurados `list_display`, `list_filter` y `search_fields` para cada modelo
- El oncólogo puede filtrar alertas por tipo, severidad y estado de resolución

**Base de datos PostgreSQL:**
- Instalado PostgreSQL 18 en máquina de León
- Creada base de datos `sugarbaker_db` via pgAdmin 4
- Ejecutado `makemigrations` → generado `0001_initial.py`
- Ejecutado `migrate` → 3 tablas clínicas creadas físicamente en PostgreSQL
- Creado superusuario `admin` para el panel

**Verificación:**
- `python manage.py runserver` exitoso
- Panel en http://127.0.0.1:8000/admin/ muestra: Alertas, Pacientes,
  Registros Diarios — todos en español con opciones Añadir y Modificar

### Decisiones tomadas
- `on_delete=PROTECT` en ForeignKey — Django no permite borrar un paciente
  que tenga registros diarios. Crítico para integridad de datos clínicos
- Aspecto del drenaje como `choices` cerradas (no texto libre) — el
  alert_engine necesita valores exactos para evaluar red flags
- `dia_postoperatorio` calculado automáticamente en `save()` — el oncólogo
  no cuenta días manualmente, el sistema lo sabe
- `fecha_resolucion` nullable — una alerta puede estar activa indefinidamente
  hasta que el médico la resuelva

### Problemas encontrados y resueltos
- Carpeta del proyecto tenía typo (`Resgistro_` en vez de `Registro_`) →
  resuelto via merge con rama sprint-1-frontend del compañero
- Conflicto de merge en settings.py → resuelto manualmente conservando
  configuración correcta de León (PostgreSQL + decouple)
- León no tenía permisos de escritura en GitHub → compañero lo agregó
  como colaborador
- `.env` estaba en carpeta vieja después del renombrado → copiado a nueva
  ubicación con comando `copy`

### Pendiente para Sprint 2
- Crear `signos_sintomas/alert_engine.py` con las 4 reglas clínicas
- Merge final sprint-1-modelos → Desarrollo

---

## Sprint 2 — Motor de Alertas
**Fecha:** 12/06/2026 — 13/06/2026
**Responsable:** León (Arquitecto IA) + Codex
**Estado:** COMPLETADO ✅

### Objetivo
Implementar `alert_engine.py` con función `evaluar_registro(registro)` que
evalúa un `RegistroDiario` y crea automáticamente objetos `Alerta` cuando
detecta red flags del protocolo Sugarbaker/HIPEC.

### Qué se hizo
- Creado `signos_sintomas/alert_engine.py` con la función `evaluar_registro`.
- Implementadas las 4 reglas clínicas del protocolo Sugarbaker/HIPEC.
- Agregadas constantes clínicas auditables para umbrales y valores críticos.
- Creadas 7 pruebas unitarias para reglas, valores límite y caso sin alertas.
- Verificación: `python manage.py test signos_sintomas` → 7 pruebas OK.
- Verificación: `python manage.py check` → 0 errores.

### Cierre de Sprint 2
1. Sprint 2 completado y mergeado a `Desarrollo` vía PR #1 (commits `b10ef97`,
   `40a2895`, merge `3bb8f05`). Incluye la resolución de la duplicación de
   modelos clínicos en `home/models.py`.
2. **NOTA DE PROCESO:** el merge de PR #1 ocurrió sin revisión formal del
   Arquitecto IA, en contra de la convención del equipo ("Ningún código
   clínico entra a `Desarrollo` sin aprobación del Arquitecto"). **Lección
   aprendida:** todo PR debe esperar aprobación explícita del Arquitecto antes
   del merge.
3. Bug detectado post-merge en la Regla 3 (sin gases 3 días consecutivos): el
   filtro/orden usaba `fecha_registro` (timestamp) en vez de
   `dia_postoperatorio` (concepto clínico exacto). Corregido directo en
   `Desarrollo` en el commit `01b8a47`.
4. Sprint 2 ahora cerrado: 7 pruebas unitarias OK y fix de Regla 3 aplicado
   y verificado.

---

## Sprint 3 — Bot WhatsApp
**Fecha:** 13/06/2026 — 16/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** EN CURSO ⏳ (pasos 1-3 completados)

### Objetivo
Implementar el bot de WhatsApp que captura la telemetría diaria del paciente
mediante una máquina de estados, crea el `RegistroDiario` y dispara el
`alert_engine`. El paciente nunca ve alertas, solo confirmación neutra.

### Paso 1 — Modelos (commit `68950ef`)
- Creado modelo `ConversacionWhatsApp`: persiste el estado de la máquina de
  estados, necesario porque cada mensaje de Twilio llega como una petición HTTP
  independiente. Guarda respuestas parciales (`temp_*`) hasta COMPLETADO.
- Agregado campo `cantidad_drenaje` a `RegistroDiario` (escala cualitativa
  poco/normal/mucho/sin_drenaje). `volumen_drenaje_ml` pasa a opcional para los
  ml que el paciente agregue voluntariamente.
- `cantidad_drenaje` quedó `null=True` SIN default (decisión del Arquitecto):
  un registro antiguo en `null` = "dato no capturado" (honesto), no falsamente
  "sin drenaje".
- Migración `0002` generada y aplicada a `sugarbaker_db`.

### Paso 2 — Bot (commit `109afc7`)
- Creado `signos_sintomas/bot.py`: lógica pura `procesar_mensaje(telefono, texto)
  -> texto`, sin acoplamiento a HTTP/Twilio (testeable directo).
- Máquina de estados de 5 preguntas: temperatura → dolor → aspecto drenaje →
  cantidad drenaje (se omite si no hay drenaje) → gases+náuseas → COMPLETADO.
- Lenguaje coloquial, tuteo, tono cálido. Opciones de drenaje en lenguaje simple
  (no términos médicos). Extracción opcional de ml ("poco, 30ml").
- Dudas del paciente respondidas con predefinidos conservadores
  (fiebre/comer/dolor/fallback).
- Creado `signos_sintomas/knowledge_base.md` como placeholder (RAG diferido a
  FASE 5).
- **18 pruebas unitarias OK** (7 del alert_engine + 11 del bot);
  `manage.py check` sin errores.

### Decisiones tomadas
- Gases + náuseas en una sola pregunta (formato "sí, 0"), aprobado por el
  Arquitecto como clínicamente aceptable para pacientes en recuperación.
- Sin bloqueo horario en `bot.py`: el envío automático 7-10 AM Bogotá se maneja
  en FASE 4 con Celery.
- `_parse_gases_nauseas` usa `\bno se\b` con límite de palabra: "no sé" pide
  reintento, pero "no sentí náuseas" se acepta como respuesta válida.

### Paso 3 — Webhook Twilio (commit `832873d`)
- Creado `signos_sintomas/views.py` con la vista `webhook_whatsapp`
  (`@csrf_exempt` solo en esa vista + `@require_POST`): extrae `From`/`Body`,
  delega en `bot.procesar_mensaje` y responde en TwiML.
- Rellenado `signos_sintomas/urls.py` (`app_name='signos_sintomas'`, ruta
  `webhook/whatsapp/`). El `include` en las urls del proyecto ya existía → URL
  final `/signos_sintomas/webhook/whatsapp/`.
- Instalado `twilio==9.10.9` y actualizado `requirements.txt` con su cadena de
  dependencias (curado a mano — ver "Problemas encontrados").
- Agregadas claves Twilio a `.env.example` (`TWILIO_AUTH_TOKEN`,
  `TWILIO_ACCOUNT_SID`). El `.env` real nunca se commitea.
- **22 pruebas unitarias OK** (18 previas + 4 del webhook); `check` sin errores.

### Decisiones de seguridad — validación de firma (fail-safe / fail-clear)
- **Fail-safe:** `TWILIO_VALIDATE_SIGNATURE` por default `True`. Si la variable
  NO está en `.env`, la validación queda ACTIVA. Para desactivarla (solo pruebas
  locales) hay que escribir explícitamente `TWILIO_VALIDATE_SIGNATURE=False`. El
  código nunca tiene `default=False` → imposible "fallar abierto" por olvido.
- **Fail-clear:** si la validación está activa pero falta `TWILIO_AUTH_TOKEN`,
  `_firma_twilio_valida` levanta `ImproperlyConfigured` con un mensaje explícito,
  en vez de saltarse la validación o devolver un `403` engañoso. Cubre el
  escenario más peligroso: token olvidado en producción.
- **Secretos:** `TWILIO_AUTH_TOKEN` y `TWILIO_ACCOUNT_SID` viven solo en `.env`
  vía `python-decouple`, nunca hardcodeados en `settings.py` ni `views.py`.
- Ajuste de proxy para ngrok: `USE_X_FORWARDED_HOST=True` y
  `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')` para que
  `build_absolute_uri()` reconstruya la URL pública https que Twilio firmó.

### Los 4 tests del webhook
1. `test_post_valido_devuelve_twiml` — POST válido → 200 + TwiML con la pregunta.
2. `test_get_no_permitido` — GET → 405 (`require_POST`).
3. `test_firma_invalida_devuelve_403` — firma inválida con validación activa → 403.
4. `test_token_faltante_falla_seguro` — token vacío con validación activa →
   `ImproperlyConfigured` (verifica el fail-clear del escenario peligroso).

### Problemas encontrados y resueltos
- El entorno de Python es **global** (TensorFlow, Jupyter, cientos de paquetes),
  no un virtualenv limpio. `pip freeze` habría contaminado `requirements.txt`
  con dependencias ajenas → se curó a mano agregando solo `twilio` y su cadena
  (aiohttp, requests, PyJWT, etc.). Pendiente: virtualenv limpio en FASE 5.

### Riesgo conocido — pendiente de probar end-to-end
- La validación de firma detrás de **ngrok** depende de que
  `request.build_absolute_uri()` coincida EXACTAMENTE con la URL pública que
  Twilio firmó. Los settings de proxy ya están puestos, pero esto NO se ha
  probado contra Twilio real todavía. Verificar en la prueba end-to-end del
  paso 4 (con ngrok + número de WhatsApp real); si la firma falla por mismatch
  de URL, revisar host/esquema reconstruidos.

### Pendiente Sprint 3 (paso 4 — próxima sesión)
- Crear cuenta Twilio + activar sandbox WhatsApp.
- Poner `TWILIO_AUTH_TOKEN` / `TWILIO_ACCOUNT_SID` reales en el `.env` local.
- Exponer el webhook con ngrok y configurar la URL en la consola de Twilio.
- Prueba end-to-end con WhatsApp real (valida también el riesgo de firma de arriba).
- Merge `sprint-3-whatsapp` → `Desarrollo` (con aprobación del Arquitecto).

### Diferido a sprints posteriores
- **FASE 4:** envío automático matutino 7-10 AM Bogotá (Celery/cron) y
  notificación al médico por email/SMS.
- **FASE 5:** capa RAG que lea el `knowledge_base.md` real (pendiente acceso al
  Drive del médico).

---

## Sprint 4 — Dashboard y Notificaciones
**Fecha:** pendiente
**Estado:** EN COLA ⏳

---

## Sprint 5 — Producción
**Fecha:** pendiente
**Estado:** EN COLA ⏳
