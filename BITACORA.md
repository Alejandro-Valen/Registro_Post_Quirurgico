# Bitácora del Proyecto — Sistema de Monitoreo Posquirúrgico Remoto

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

## Sesión: Sprint 3 - Conexión Twilio + ngrok end-to-end
**Fecha:** 16/06/2026 — 17/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** PASO 4 funcional ✅ (prueba real exitosa; pendiente solo el merge)

### Qué se logró
Prueba real end-to-end exitosa: mensaje de WhatsApp real → webhook → bot →
`RegistroDiario` → `alert_engine` → `Alerta`, verificado contra la base de datos.
Las 5 preguntas funcionaron, incluyendo reintentos correctos ante respuestas
ambiguas.

### Cronología de errores y cómo se resolvieron

**1. ERROR: "Invalid HTTP_HOST header" (400 Bad Request)**
- **Causa:** `ALLOWED_HOSTS` vacío en `settings.py` rechazaba el dominio de ngrok.
- **Solución:** `ALLOWED_HOSTS` configurable por `.env` usando `decouple` + `Csv()`,
  con comodín de subdominio `.ngrok-free.dev` para no editar cada vez que ngrok
  reinicia el túnel (el subdominio cambia en plan free). Commit `de48db9`.
- **Lección:** en producción esto debe ser el dominio real, nunca un wildcard `'*'`.

**2. ERROR: "403 Forbidden" en el webhook tras resolver lo anterior**
- **Causa raíz:** `TWILIO_AUTH_TOKEN` en `.env` era el TEST Auth Token (de la
  sección "Test Credentials" en Twilio Console), pero el Sandbox de WhatsApp firma
  sus webhooks con el AUTH TOKEN PRIMARIO (Live), no con el de pruebas. Es una
  confusión muy común y nada intuitiva en Twilio.
- **Cómo se diagnosticó:** se agregó un log temporal en `_firma_twilio_valida` que
  imprimía `build_absolute_uri()`, `scheme`, `get_host()`, `request.POST` completo
  y los primeros 8 caracteres del token. Esto descartó los problemas de http/https
  y de parseo del body, dejando claro que el problema era el token incorrecto.
  (El log temporal se removió después; no dejó rastro en el código commiteado.)
- **Solución:** usar el Auth Token primario, ubicado en Twilio Console → Account
  Dashboard (NO en la sección de Sandbox, NI en "API keys & tokens", NI en
  "General Settings" — ahí solo aparece a veces el Account SID).
- **RUTA EXACTA para encontrarlo la próxima vez:** Twilio Console → clic en
  "Twilio Home" (logo superior izquierdo) → "CONSOLE" → "Account Dashboard" en el
  menú lateral → sección "Account Info" con el Auth Token primario y botón "Show".
- **Lección crítica:** documentado en `.env.example` con un comentario explícito de
  que debe ser el Auth Token PRIMARIO, nunca el de Test Credentials, para
  conexiones con el Sandbox de WhatsApp.

**3. CONFUSIÓN: navegación en Twilio Console para encontrar el Auth Token primario**
- Se intentó sin éxito en: `/us1/account/manage-account/general-settings` (solo
  mostró el Account SID), la sección "API keys & tokens" (mostró API Keys, no el
  Auth Token), y búsquedas en la barra superior que devolvieron enlaces a
  documentación en vez de la pantalla real.
- La ruta que funcionó: **Twilio Home → Console → Account Dashboard.**

### Sobre ngrok — notas para la próxima sesión
- El plan free de ngrok genera un subdominio nuevo cada vez que se reinicia el
  túnel (ej. `trifle-agnostic-roping.ngrok-free.dev`) — por eso el comodín
  `.ngrok-free.dev` en `ALLOWED_HOSTS` evita tener que editar `.env` cada vez.
- El webhook de Twilio en el Sandbox ("When a message comes in") debe configurarse
  con la URL completa:
  `https://[subdominio].ngrok-free.dev/signos_sintomas/webhook/whatsapp/`
  con método POST.
- Cada vez que se reinicia ngrok en plan free, el subdominio cambia, así que hay
  que volver a actualizar esa URL en Twilio Console → Sandbox Settings.
- ngrok requiere autenticación con authtoken (cuenta gratuita en ngrok.com) antes
  de poder usar `ngrok http 8000`.
- **IMPORTANTE:** nunca compartir el authtoken de ngrok ni el Auth Token de Twilio
  en chats o capturas de pantalla — si esto ocurre, regenerarlos inmediatamente
  desde sus respectivos dashboards.

### Verificación final de datos clínicos
Registro de prueba: temperatura=37.6, dolor_eva=4, aspecto=sin_drenaje (opción 5),
gases=False, náuseas=4.

| Campo / Resultado | Esperado | Guardado en BD |
|-------------------|----------|----------------|
| temperatura | 37.6 | 37.6 ✅ |
| dolor_eva | 4 | 4 ✅ |
| aspecto_drenaje | sin_drenaje | sin_drenaje ✅ |
| cantidad_drenaje | sin_drenaje (auto, se saltó pregunta 3B) | sin_drenaje ✅ |
| volumen_drenaje_ml | None (no se midió) | None ✅ |
| presencia_gases | False | False ✅ |
| episodios_nauseas | 4 | 4 ✅ |
| dia_postoperatorio | calculado | 7 ✅ |
| Alerta generada | ILEO_PARALITICO / MEDIA (Regla 4: náuseas>3) | 1 alerta, ILEO_PARALITICO / MEDIA ✅ |

Validación cruzada (correcto que NO dispararan): temp 37.6 < 38.0 → sin SEPSIS;
aspecto sin_drenaje → sin FUGA_ANASTOMOTICA; 1 solo registro sin gases → sin ÍLEO
severo (Regla 3 exige 3 días). El paciente recibió solo la confirmación neutra; la
alerta quedó únicamente en BD para el oncólogo.

### Pendiente Sprint 3
- Merge `sprint-3-whatsapp` → `Desarrollo` (con aprobación del Arquitecto). Es lo
  único que falta para cerrar el Sprint 3.

> **Merge POSPUESTO deliberadamente (decisión del Arquitecto, 16/06/2026):** no se
> mergea todavía. Los PDFs clínicos del médico llegan ~18/06/2026 y podrían
> modificar los **umbrales del `alert_engine`**, no solo el `knowledge_base.md`.
> Mergear ahora obligaría a repetir el merge tras la auditoría. Plan: esperar los
> PDFs → auditar reglas del `alert_engine` → ajustar si aplica → luego mergear.
> Queda registrado para que conste que es una decisión consciente, no un olvido.

---

## Sesión: campo `tipo_cirugia` en Paciente
**Fecha:** 17/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** COMPLETADO ✅ (commit `1c379f8`)

### Qué se hizo
- Agregado campo `tipo_cirugia` al modelo `Paciente`: `CharField(max_length=30,
  null=True, blank=True)` con choices `sugarbaker_hipec` / `colectomia_electiva` /
  `otra` (cirugía colorrectal).
- Generalizado el docstring de `Paciente` ("paciente en seguimiento postquirúrgico
  remoto", ya no exclusivo de Sugarbaker) y el `help_text` de `fecha_cirugia`.
- Migración `0003_paciente_tipo_cirugia_alter_paciente_fecha_cirugia` generada y
  aplicada a `sugarbaker_db`.

### Por qué
- `tipo_cirugia` es un **dato descriptivo para estadística e investigación futura**.
  **No afecta el `alert_engine` ni el flujo del bot.**
- `null=True/blank=True` SIN default: un paciente sin valor = "no capturado"
  (honesto). El paciente de prueba existente quedó en `tipo_cirugia=None`, no se le
  inventó un valor.

### Verificación
- Migración aplicada sin pedir default (por `null=True`).
- 22/22 tests OK · `manage.py check` sin errores.

> Nota: la actualización de alcance/afiliación institucional en CLAUDE.md y ROADMAP
> es un paso aparte posterior; aquí solo se documenta el cambio de modelo.

---

## Sesión: Generalización de Alcance, Marca y Auditoría de Literatura (Sprint 3.5)
**Fecha:** 17/06/2026 — 18/06/2026
**Responsable:** Alejo y León (Arquitectos IA) con Claude (chat) y Claude Code
**Estado:** ✅ Completado

### Qué se hizo
Tras recibir y auditar 15 archivos del médico proponente (9 PDFs
científicos sobre ERAS/alta temprana colorrectal, 2 transcripciones de
presentaciones suyas, y 4 documentos institucionales/académicos —
fichas técnicas de Universidad CES, preproyecto formal, slide deck), se
resolvió la pregunta de alcance del proyecto y se generalizó todo el
código, la documentación y el branding que asumían exclusividad
Sugarbaker/HIPEC o afiliación institucional formal.

Trabajo concreto:
- Auditoría completa de los 15 archivos, organizada en 4 documentos de
  referencia en `docs/auditoria_literatura/` (análisis de los 9 PDFs
  documento por documento, análisis de las 2 transcripciones, análisis
  de los 4 archivos institucionales restantes, y la síntesis cruzada de
  umbrales clínicos vs. el `alert_engine` actual).
- Campo `tipo_cirugia` agregado a `Paciente` (descriptivo, sin lógica
  clínica — no alimenta `alert_engine` ni bot).
- Generalización de marca y afiliación: título y descripción del
  proyecto, callout de agentes IA, docstrings de `models.py`/`bot.py`,
  título de `knowledge_base.md`, templates HTML públicos (`index.html`,
  `contacto.html`), `.env.example`.
- Base de datos local renombrada de `sugarbaker_db` a
  `registro_postquirurgico_db`, con verificación de integridad de datos.
- `CLAUDE.md` y `ROADMAP_MVP_SUGARBAKER.md` actualizados para reflejar
  el alcance real y el estado actual del proyecto.

### Decisiones tomadas y su justificación
1. **Alcance ampliado a ERAS/cirugía colorrectal en general, no
   exclusivo de Sugarbaker/HIPEC.** Respaldado por evidencia múltiple:
   ninguno de los 9 PDFs trata HIPEC específicamente; el título oficial
   del proyecto registrado ante el comité de ética de Universidad CES es
   "Programa de cirugías colorrectales con seguimiento ambulatorio
   remoto"; el criterio de inclusión formal (ECOG 0-1, sin
   comorbilidades significativas) describe un perfil de paciente
   distinto al típico de Sugarbaker/HIPEC. Sugarbaker se mantiene como
   uno de los tipos de cirugía soportados (campo `tipo_cirugia`), no
   como el único.
2. **`tipo_cirugia` como campo descriptivo, no como clases separadas por
   tipo de cirugía.** Se prefirió la opción de menor complejidad: un
   campo `null=True/blank=True` que no cambia el comportamiento del bot
   ni del `alert_engine`, pensado para estadística/investigación futura.
3. **Sin afiliación institucional formal por ahora.** El proyecto no
   tiene vínculo formalizado con ninguna clínica o universidad a la
   fecha; se removieron las menciones a "Clínica Somer" del código y la
   documentación en consecuencia.
4. **Enfoque exclusivamente de software, sin hardware de monitoreo
   continuo.** Respaldado por evidencia reciente (2025) de que el
   monitoreo continuo de signos vitales por hardware no demostró valor
   predictivo adicional sobre cuestionario + llamada telefónica.
5. **Base de datos local renombrada a `registro_postquirurgico_db`**
   (coincide con el nombre del repositorio), ejecutado vía `psql` con
   verificación de integridad de datos (conteos de
   `Paciente`/`RegistroDiario`/`Alerta` antes y después, sin pérdida).
6. **Checkboxes históricos del ROADMAP no se reescriben** (ej. "Crear
   base de datos sugarbaker_db en pgAdmin" se mantiene tal cual) — es
   registro fiel de lo que pasó en su momento, no documentación de
   estado actual.

### Problemas o conflictos encontrados
Ninguno bloqueante. Único hallazgo relevante: el código de producción
(no solo la documentación) tenía menciones de marca Sugarbaker en
lugares de alta visibilidad que no estaban en el radar inicial —
específicamente el `<h2>` del header en `index.html` y `contacto.html`
(las plantillas públicas del sitio web), además de docstrings en
`models.py` y `bot.py`. Se corrigieron en el mismo paso que la
generalización de documentación.

### Pendiente para la próxima sesión
**Paso exacto:** fase de decisiones de arquitectura clínica del
`alert_engine` — punto de partida en
`docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md`. Puntos
concretos a decidir: umbral de fiebre (38.0 actual vs. 37.9 de
Outersterp 2025), si la regla de "3 días sin gases" se mantiene (sin
respaldo literal en ningún PDF), umbral de náuseas (>3 actual vs.
cualquier episodio en estudios recientes), si `aspecto_drenaje` sigue
siendo la variable principal de fuga anastomótica (varios ERAS modernos
no usan drenaje), el gap de `DOLOR_AGUDO` sin regla implementada
(candidato: EVA≥4, repetido en 3 estudios), y la frecuencia de
check-ins (1×/día actual vs. el patrón de 2-3×/día de los estudios más
recientes). El merge `sprint-3-whatsapp` → `Desarrollo` sigue pospuesto
hasta cerrar esa fase.

---

## Sesión: Implementación campo tiene_drenaje + escalera BAJA/MEDIA/ALTA alert_engine
**Fecha:** 18/06/2026
**Responsable:** Alejo y León (Arquitectos IA) con Claude Code
**Estado:** COMPLETADO ✅ (3 commits, push a sprint-3-whatsapp)

### Qué se hizo
Implementación completa del campo `tiene_drenaje` y de la escalera de severidad
por aspecto de drenaje en el `alert_engine` — primera decisión de arquitectura
clínica que surge de la auditoría de literatura (Sprint 3.5).

**PASO 1 — models.py:**
- Agrega choice `'turbio'` a `ASPECTO_CHOICES` en `RegistroDiario` (entre
  hemático y purulento).
- Agrega campo `tiene_drenaje = BooleanField(null=True, blank=True)` ANTES de
  `aspecto_drenaje` en `RegistroDiario`. Semántica: null=no capturado (registros
  anteriores a esta versión), False=confirmado sin drenaje, True=tiene drenaje.
- Agrega constante `ESTADO_TIENE_DRENAJE = 'ESPERANDO_TIENE_DRENAJE'` a
  `ConversacionWhatsApp`.
- Agrega `(ESTADO_TIENE_DRENAJE, 'Esperando si tiene drenaje')` a `ESTADO_CHOICES`
  (entre DOLOR y ASPECTO_DRENAJE).
- Agrega campo `temp_tiene_drenaje = BooleanField(null=True, blank=True)` a
  `ConversacionWhatsApp` (antes de `temp_aspecto_drenaje`).
- Migración `0004` generada y aplicada a `registro_postquirurgico_db`.

**PASO 2 — alert_engine.py (Regla 2 reescrita):**
- Reemplaza `DRENAJES_FUGA_ANASTOMOTICA` por tres constantes:
  `DRENAJES_ALTA = ('purulento', 'fecaloide')`,
  `DRENAJES_MEDIA = ('turbio', 'hematico')`,
  `DRENAJES_BAJA = ('seroso',)`.
- La Regla 2 evalúa SOLO si `registro.tiene_drenaje is True`. Si `tiene_drenaje`
  es `None` (registro legado) o `False` (sin drenaje), no genera ninguna alerta.
- Escalera: seroso→BAJA, turbio/hemático→MEDIA, purulento/fecaloide→ALTA.

**PASO 3 — bot.py (nuevo estado en máquina de estados):**
- Máquina pasa de 5 a 6 preguntas.
- Nuevo bloque `ESTADO_TIENE_DRENAJE` entre DOLOR y ASPECTO_DRENAJE.
- Si el paciente responde "no": `temp_tiene_drenaje=False`, `temp_aspecto_drenaje=
  'sin_drenaje'`, `temp_cantidad_drenaje='sin_drenaje'`, y salta directamente a
  GASES_NAUSEAS (se omiten preguntas 4 y 5 sobre drenaje).
- Si responde "sí": `temp_tiene_drenaje=True`, avanza a ASPECTO_DRENAJE.
- `_parse_aspecto` actualizado: 1=seroso, 2=hemático, 3=turbio, 4=purulento,
  5=fecaloide (el nuevo menú ya no incluye "sin drenaje" como opción).
- Mensajes renumerados (3️⃣→6️⃣).
- `tiene_drenaje` agregado al `RegistroDiario.objects.create()` y a
  `_limpiar_temporales()`.

**PASO 4 — tests.py (suite de 22 → 27 tests):**
- 4 tests existentes actualizados con `tiene_drenaje=True/False` explícito.
- `_completar_flujo` actualizado a 6 pasos.
- `test_sin_drenaje_salta_pregunta_cantidad` reescrito: ahora envía "no" en el
  estado `TIENE_DRENAJE` (antes enviaba "5" en ASPECTO_DRENAJE).
- `test_gases_nauseas_ambiguo_reintenta` actualizado con el paso "sí" nuevo.
- `test_flujo_completo_crea_registro` verifica `registro.tiene_drenaje is True`.
- 5 tests nuevos en `AlertEngineTests`:
  `test_drenaje_seroso_con_tiene_drenaje_crea_baja`,
  `test_drenaje_hematico_crea_media`,
  `test_drenaje_turbio_crea_media`,
  `test_sin_drenaje_no_genera_alerta_drenaje`,
  `test_tiene_drenaje_null_no_genera_alerta_drenaje`.

### Decisiones tomadas y su justificación
1. **`tiene_drenaje` como campo separado (BooleanField nullable) en lugar de
   depender de `aspecto_drenaje='sin_drenaje'.`** Razón: la pregunta de si el
   paciente tiene drenaje es clínicamente distinta de cómo se ve ese drenaje. Un
   campo dedicado hace la semántica explícita y permite que el `alert_engine`
   tenga una guarda limpia (`is True`) sin parsear el valor de aspecto.
2. **`null=True` para backward compatibility.** Los registros legados (anteriores
   a esta versión) quedaron con `tiene_drenaje=None`. El motor de alertas trata
   `None` igual que `False`: sin alerta. Honesto y sin efecto en datos clínicos ya
   existentes.
3. **Escalera de severidad por aspecto:** seroso→BAJA, turbio/hemático→MEDIA,
   purulento/fecaloide→ALTA. Base: Lee 2022, Gignoux 2018, Coeckelberghs 2025
   (citados en `SINTESIS_CRUZADA_UMBRALES.md`).
4. **Menú de aspecto rediseñado (5 opciones sin "sin drenaje"):** como la pregunta
   de aspecto solo se muestra si `tiene_drenaje=True`, la opción "No tengo drenaje"
   ya no tiene sentido en ese contexto. Se rediseñó el menú para incluir 'turbio'
   como opción 3 y quedar con 5 opciones clínicas claras.

### Verificación
- 27/27 tests OK · `manage.py check` 0 errores · `migrate` OK.

### Pendiente para la próxima sesión
**Próximo paso:** continuar con las decisiones de arquitectura clínica del
`alert_engine` según `SINTESIS_CRUZADA_UMBRALES.md`:
- Umbral de fiebre (38.0 actual vs. 37.9 de Outersterp 2025).
- Regla de "3 días sin gases": ¿mantener o ajustar?
- Umbral de náuseas: >3 actual vs. cualquier episodio en estudios recientes.
- Gap de `DOLOR_AGUDO`: sin regla implementada (candidato: EVA≥4).
- Frecuencia de check-ins: 1×/día vs. 2-3×/día de estudios recientes.
- Merge `sprint-3-whatsapp` → `Desarrollo` (sigue pospuesto hasta cerrar
  las decisiones del `alert_engine`).

---

## Sprint 3.6 — Reescritura Alert Engine: Temperatura, Gases y Náuseas
**Fecha:** 18-19/06/2026
**Responsable:** León (Arquitecto IA) + Claude Code
**Estado:** COMPLETADO ✅ (Dolor pendiente)

### Qué se construyó

**Regla 1 — Temperatura (Regla 1 reescrita):**
- Escalera ALTA (≥37.9°C) / MEDIA (subfebrícula 37.5–37.8°C persistente 2 días calendario).
- Lógica de días calendario: agrupa por `fecha_registro__date`, no por número de registro.
- Constantes: `TEMPERATURA_ALTA=37.9`, `TEMPERATURA_SUBFEBRICULA_MIN=37.5`, `DIAS_SUBFEBRICULA_PERSISTENTE=2`.
- 4 tests nuevos; `test_valores_limite_no_crean_alertas` actualizado (37.9→37.4).

**Regla 3 — Gases (Regla 3 reescrita):**
- Escalera BAJA/MEDIA/ALTA por 1/2/3 días calendario consecutivos sin gases.
- While-loop hacia atrás: cuenta días sin gases, se detiene al encontrar gases o ausencia total de registro.
- Constantes: `DIAS_SIN_GASES_BAJA=1`, `DIAS_SIN_GASES_MEDIA=2`, `DIAS_SIN_GASES_ALTA=3`.
- 4 tests nuevos; `test_tres_registros_sin_gases_...` renombrado y reescrito para usar 3 días calendario distintos.

**Regla 4 — Náuseas (Regla 4 reescrita):**
- Suma diaria de episodios (1-2→BAJA, 3-4→MEDIA, 5+→ALTA).
- Capa de persistencia: 2 días calendario consecutivos → MEDIA mínimo; 4 días → ALTA.
- Severidad final = max(suma, persistencia) vía `ORDEN_SEVERIDAD`.
- Usa `models.Sum('episodios_nauseas')` para agrupar check-ins del mismo día.
- Constantes: `NAUSEAS_BAJA_MIN=1`, `NAUSEAS_MEDIA_MIN=3`, `NAUSEAS_ALTA_MIN=5`, `DIAS_NAUSEAS_MEDIA=2`, `DIAS_NAUSEAS_ALTA=4`.
- 6 tests nuevos; `test_registro_sin_red_flags_no_crea_alertas` corregido (episodios_nauseas 1→0).

**Suite:** 41 tests OK (27 previos + 14 nuevos de este sprint).

### Decisiones tomadas

1. **Umbral de temperatura: 37.9°C (Outersterp 2025).** El estudio usa ≥37.9°C como umbral de notificación domiciliaria — más conservador que el 38.0°C histórico del proyecto. Adoptado para ALTA. La subfebrícula (37.5–37.8°C) se considera MEDIA solo si persiste 2 días calendario.

2. **Gases como escalera de 3 niveles.** El paciente ya demostró función intestinal al ser dado de alta (criterio ERAS estándar); no tener gases en casa es una regresión. 1 día sin gases → BAJA (señal temprana), 2 días → MEDIA, 3 días → ALTA. El umbral ALTA de 3 días no tiene respaldo literal en los PDFs revisados pero se mantiene por consistencia clínica.

3. **Náuseas: cualquier episodio es señal (BAJA desde 1).** Lee 2022 y Outersterp 2025 tratan cualquier episodio como dato relevante en monitoreo domiciliario. El umbral anterior (>3) era demasiado conservador para detección temprana.

4. **Persistencia de náuseas: escalón en 4 días (ALTA).** Delaney 2008: pacientes con estancia ≥4 días tenían íleo en 27.8% vs. 11% general. Ese orden de magnitud justifica un escalón ALTA independiente del conteo diario.

5. **Frecuencia de check-ins: 2×/día (decisión de arquitectura).** Todos los modelos de días (Reglas 1, 3, 4) agrupan por `fecha_registro__date`. Si el bot hace 2 preguntas por día, los 2 registros del mismo día cuentan como 1 día, no como 2. La lógica ya está implementada anticipando ese modelo (FASE 4).

6. **Import `from django.db import models`:** necesario para `models.Sum()` en Regla 4. Añadido al `alert_engine.py`.

### Problemas encontrados y resueltos

- **`test_registro_sin_red_flags_no_crea_alertas` fallaba:** con `NAUSEAS_BAJA_MIN=1`, un registro con `episodios_nauseas=1` ya genera BAJA. Solución: cambiar a 0 (Opción A del Arquitecto) — el test de "sin alertas" usa 0 episodios, lo que es coherente con la nueva regla.
- **Namespace `hoy` vs `hoy_gases`:** Regla 1 usa `hoy` dentro de su bloque `elif`; Regla 3 usa `hoy_gases`. No es una colisión de ámbito (son bloques secuenciales) pero se nombró diferente para claridad de lectura.
- **`auto_now_add` en tests:** `fecha_registro` no se puede setear en `.create()`. Solución ya establecida: `RegistroDiario.objects.filter(pk=...).update(fecha_registro=past_datetime)` inmediatamente después de crear.

### Próximo paso

- Implementar Regla 5 — `DOLOR_AGUDO` (escalera por `dia_postoperatorio` + tendencia alcista). Decidida, no implementada.
- Merge `sprint-3-whatsapp` → `Desarrollo` (pospuesto hasta implementar DOLOR_AGUDO para hacer un solo merge).

---

## Sesión: Dolor (DOLOR_AGUDO) — cierre de las 5 reglas del alert_engine
**Fecha:** 19/06/2026
**Responsable:** León (Arquitecto IA) con Claude (chat) y Claude Code
**Estado:** COMPLETADO ✅ (commits `acd0d64`, `f0ba511`, push a sprint-3-whatsapp)

### Qué se hizo
Se implementó la Regla 5 (Dolor/`DOLOR_AGUDO`) — la última de las 5
variables de la fase de decisiones de arquitectura clínica del
`alert_engine` (Sprint 3.6). A diferencia de las otras 4 reglas (que
usan días calendario), esta usa `dia_postoperatorio` como base, ya que
la tolerancia de dolor esperado disminuye con el tiempo de recuperación.

Combina dos capas: (1) escalera por ventana de `dia_postoperatorio`
(POD 1-2, POD 3-5, POD 6+, cada una con su propio umbral BAJA/MEDIA/
ALTA), y (2) una capa de tendencia alcista que compara el promedio de
dolor de los últimos 2 días contra el promedio de los 2 días
anteriores — si sube 3+ puntos, escala un nivel de severidad sobre lo
que diera la tabla, sin bajar nunca una severidad ya alcanzada (mismo
patrón ya usado en Náuseas).

Con esto se cierran las 5 reglas clínicas del `alert_engine` bajo el
modelo de alta sensibilidad: drenaje, temperatura, gases, náuseas y
dolor.

### Decisiones tomadas y su justificación
1. **Ventanas decrecientes por `dia_postoperatorio` en vez de un
   umbral fijo:** un EVA de 6 es normal en POD1 pero anómalo en POD7;
   Coeckelberghs 2025 documenta la trayectoria descendente esperada
   del dolor con el tiempo, lo cual respalda umbrales más estrictos a
   medida que avanza la recuperación.
2. **EVA>=4/5 como referencia central de los umbrales BAJA:** valor
   replicado en 3 estudios independientes (Delaney 2008, Lee 2022,
   Outersterp 2025) — el dato más consistente de toda la auditoría de
   literatura.
3. **Capa de tendencia con delta>=3, sobre promedio de 2 días (no
   valor aislado):** decisión explícita del Arquitecto para evitar
   sobre-sensibilidad a picos momentáneos de dolor (un solo reporte
   "dramático" no dispara la tendencia); el promedio de 2 días actúa
   como filtro natural. Sin respaldo literal en los PDFs — es
   construcción propia, igual que el escalón de persistencia de 4 días
   en Náuseas.

### Verificación
46/46 tests OK (41 anteriores + 5 nuevos de dolor) · `manage.py check`
sin errores. Verificado a mano el cálculo de las ventanas de promedio
móvil (sin solape, sin hueco entre periodo reciente y periodo
anterior). Confirmado que ningún test existente de las otras 4 reglas
colisiona con la nueva Regla 5 (todos usan `dolor_eva` ≤ 4, por debajo
del umbral BAJA mínimo de cualquier ventana).

### Pendiente para la próxima sesión
**Las 5 reglas clínicas del alert_engine están completas.** Quedan 2
pasos antes del merge a `Desarrollo`: (1) implementar en `bot.py` la
frecuencia de check-ins ya decidida (2×/día fijo — requiere campo
nuevo en `ConversacionWhatsApp` para distinguir check-in de
mañana/tarde); (2) repaso final de `alert_engine.py` completo (las 5
reglas juntas — legibilidad, consistencia, posible refactor si el
archivo creció demasiado). Variables nuevas de la literatura (FC/FR,
RH/antecedentes) siguen pausadas, sin fecha.

---

## Bug corregido: zona horaria en cálculo de fechas + clamp de dia_postoperatorio
**Fecha:** 19/06/2026 (detectado en sesión nocturna, ~9pm Bogotá)
**Severidad:** Alta — dos bugs de fechas, ambos por confundir UTC con
America/Bogota (TIME_ZONE del proyecto, USE_TZ=True)
**Commit:** `ff8bdc4`

### Bug 1 — Zona horaria en reglas de días calendario
`registro.fecha_registro.date()` y `timezone.now().date()` devuelven la
fecha en UTC, pero los filtros `fecha_registro__date` de Django operan
en America/Bogota. Durante la ventana ~19:00–23:59 hora Bogotá (cuando
UTC ya cambió de día pero Bogotá no), las reglas de días calendario de
temperatura, gases, náuseas y dolor no encontraban los registros del
día actual — generando 0 alertas donde debía haber 1 o más. Silencioso
y dependiente de la hora: por eso pasó desapercibido en sesiones
diurnas (UTC y Bogotá coinciden en fecha de día).

### Bug 2 — dia_postoperatorio negativo (bug de producción)
`dia_postoperatorio = (hoy - fecha_cirugia).days` puede dar negativo si
`fecha_cirugia` es futura (paciente pre-registrado con cirugía
programada, o error de captura en el admin), violando el CHECK de
`PositiveSmallIntegerField` y crasheando el `save()` — el bot se caería
y se perdería el reporte del paciente. Destapado al unificar la zona
horaria del modelo con la de los tests.

### Cómo se detectó
Durante la verificación final de la sincronización de documentación de
Dolor (Sprint 3.6), en horario nocturno, 12 tests fallaron de forma
sistemática (0 alertas donde se esperaba 1+). Claude Code diagnosticó
la causa raíz antes de modificar nada; el análisis del bug 2 surgió
como consecuencia del fix del bug 1.

### Fix
- `timezone.localdate()` en vez de `.date()` directo o
  `timezone.now().date()`, en las 4 reglas de `alert_engine.py` y en el
  cálculo de `dia_postoperatorio` de `models.py`.
- Clamp `max(0, (hoy - fecha_cirugia).days)`: un registro en el día de
  la cirugía o anterior queda en día 0, conservándose para revisión del
  médico en vez de rechazarse (decisión de diseño: en un sistema de
  telemetría, preservar el dato del paciente le gana a proteger la
  invariante del campo descartándolo).
- Limpieza de paso: definición redundante de `ORDEN_SEVERIDAD_DOLOR` en
  la Regla 5 (estaba dos veces, idéntica).
- Tests: 26 ocurrencias de `fecha_cirugia=timezone.now().date()` →
  `timezone.localdate()`; nueva clase `RegistroDiarioModelTests` con 3
  tests de regresión (cirugía futura, cirugía hoy, cirugía pasada).

### Verificación
49/49 tests OK, corridos en el mismo horario nocturno donde el bug se
manifestaba (condiciones reales). `manage.py check` limpio.

### Lección para el equipo
Todo cálculo de "fecha de hoy" en este proyecto usa
`timezone.localdate()`, nunca `.date()` sobre datetime aware ni
`timezone.now().date()`. Quedó registrado como norma en el Protocolo de
Cierre de CLAUDE.md.

### Pendientes que surgieron de este fix (registrados en ROADMAP, FASE 3.6, para la etapa del bot)
- Evitar alertas duplicadas con 2 check-ins/día.
- Gating pre-operatorio: no evaluar registros de pacientes aún no
  operados (dia_postoperatorio=0 por clamp) con reglas post-op.

---

## Decisión de arquitectura: bot 2×/día como evento (CheckInProgramado)
**Fecha:** 22/06/2026
**Responsable:** Alejo y León (Arquitectos), con Claude (chat) y Claude Code
**Estado:** ARQUITECTURA CERRADA ✅ — implementación trasladada a Sprint 4
**Commit (especificación):** `d5e90bd` (ROADMAP, FASE 3.6 y handoff en FASE 4)

### Contexto
El Paso 1 del cierre de Sprint 3 era "implementar el bot 2×/día", y la idea
de partida era barata: un campo nuevo en `ConversacionWhatsApp` que marcara
si el check-in en curso era de mañana o de tarde. Al sentarnos a diseñarlo,
la decisión escaló: lo que parecía un campo terminó siendo un rediseño
arquitectónico. La narrativa de por qué está aquí; la especificación cerrada
(decisiones D1–D5 + esquema del modelo) ya quedó en el ROADMAP — esta entrada
no la repite, la explica.

### Por qué se descartó el campo único
El problema de fondo es que la respuesta del paciente es **estocástica**: no
controlamos cuándo contesta, ni si contesta. Un campo de turno en la
conversación deduce la etiqueta de la hora en que llega el mensaje, y eso
abre tres fallos que no son casos de borde, son el comportamiento normal:

1. **Etiqueta semánticamente falsa.** Si el turno se infiere de la hora de
   respuesta, un paciente que contesta el check-in de la mañana a las 4 PM
   queda registrado como "tarde". La etiqueta describiría cuándo respondió,
   no qué se le preguntó — justo al revés de lo que el médico necesita leer.
2. **Mezcla AM/PM.** Dos respuestas que caen en la misma franja (p. ej. las
   dos en la tarde, porque el paciente ignoró el prompt matutino) colisionan:
   el sistema no sabe cuál es "la de la mañana".
3. **Cruce de medianoche.** Si el día del check-in se recalcula en `save()`
   con la fecha del momento, una respuesta que llega pasada la medianoche se
   contabiliza en el día equivocado — el mismo tipo de bug de fecha que ya
   nos mordió con la zona horaria (ver entrada anterior).

### La decisión
El check-in deja de ser un atributo de la conversación y pasa a ser un
**evento de primera clase**: un modelo nuevo, `CheckInProgramado`, que el
sistema **agenda** (no el paciente). El evento **nace etiquetado** —
chequeo 1 = mañana, chequeo 2 = tarde — porque la etiqueta la fija el prompt
que el sistema envía, no la hora en que el paciente reacciona. El paciente
responde cuando pueda; la etiqueta del evento no se mueve. Las 5 decisiones
cerradas (evento vs. campo, etiqueta por evento, persistir solo dato crudo,
`estado` como hecho cualitativo, escalabilidad a N vía `orden`) están como
D1–D5 en el ROADMAP — no se re-discuten en Sprint 4, se implementan.

### Por qué el diseño resuelve los cuatro casos sin ambigüedad
La clave es que un evento agendado tiene una identidad propia (paciente +
día + orden) **antes** de que el paciente haga nada. Entonces los cuatro
cruces de responde/no-responde × mañana/tarde dejan de ser ambiguos:

- **Mañana, responde / Tarde, responde:** el `RegistroDiario` se cuelga del
  evento correcto vía su `orden`/`etiqueta` — no importa a qué hora llegó.
- **Mañana, no responde / Tarde, no responde:** el evento queda en
  `NO_RESPONDIDO`. El silencio no es un dato faltante ni un hueco: es el
  **resultado** de un evento que existió, se etiquetó y venció.

Dicho de otro modo: el dato y el silencio son los dos desenlaces válidos de
un evento que ya nació con nombre. Antes, sin evento, el silencio era
invisible (no hay fila que falte si nunca se esperó una).

### Decisión clínica nueva: alerta de silencio del paciente
De hacer el silencio un hecho de primera clase sale una alerta que antes no
existía: si un `CheckInProgramado` pasa a `NO_RESPONDIDO`, el equipo médico
debe **contactar al paciente**. Un paciente que deja de responder es señal
clínica por sí misma (deterioro, hospitalización, abandono del seguimiento).
Esta alerta **depende del scheduler** — solo una tarea programada puede
detectar la *ausencia* de respuesta; el bot, que únicamente reacciona a
mensajes entrantes, nunca "ve" un silencio. Por eso va a Sprint 4. Queda
como **decisión abierta**: su severidad, y si dispara con un silencio o con
dos consecutivos.

### Frontera de alcance (Sprint 3 vs. Sprint 4)
Sprint 3 cierra la **decisión** documentada y congelada; no toca código de
dominio todavía. Sprint 4 **ejecuta** la unidad completa —modelo
`CheckInProgramado` + scheduler (Celery beat/cron) + refactor de `bot.py` +
alerta de silencio + los 2 gatings del alert_engine— porque todo eso cuelga
de la dependencia con Celery y no tiene sentido partirlo. El único trabajo de
implementación que permanece en Sprint 3 es el Paso 1b (seguridad del
webhook), que no depende del scheduler.

### Riesgos anotados para Sprint 4 (del cruce contra el código real)
Al contrastar el diseño con los modelos actuales, tres puntos que conviene
tener presentes antes de implementar:

1. **Tres "fechas de hoy" que pueden divergir.** `CheckInProgramado.fecha_dia`
   (congelado al agendar), `RegistroDiario.fecha_registro` (`auto_now_add` al
   completar el flujo) y `dia_postoperatorio` (calculado con `localdate()` en
   `save()`) son tres relojes distintos. Si el paciente responde el check-in
   de la mañana pasada la medianoche, `fecha_registro` cae en el día
   siguiente al `fecha_dia` del evento. Como el alert_engine agrupa las reglas
   de días calendario por `fecha_registro__date`, hay que **decidir cuál
   fecha es la autoritativa** para esas reglas: la del evento (`fecha_dia`) o
   la del registro. D3 ya manda congelar `fecha_dia`; falta extender ese
   criterio al alert_engine.
2. **"Un registro por día" debe volverse "un registro por check-in".** El
   guard actual (`ConversacionWhatsApp.fecha_ultimo_registro` → "ya
   registramos tus datos de hoy") bloquearía el segundo check-in del día. El
   refactor del bot tiene que reescribir esa guarda en términos del evento
   `PENDIENTE`, no de la fecha.
3. **El `OneToOne` exige vincular al crear.** Hoy `RegistroDiario` nace suelto
   en el bot; con el nuevo modelo, al completar el flujo hay que asociarlo al
   `CheckInProgramado` PENDIENTE del día. Conviene que ese vínculo sea
   transaccional con la creación del registro para no dejar eventos
   COMPLETADO sin `registro`, ni registros huérfanos.

### Lección para el equipo
Cuando el dato de entrada es estocástico (el paciente responde cuando quiere,
o no responde), la etiqueta y la fecha deben fijarse en el momento en que el
**sistema** crea el evento, no en el momento en que el **usuario** reacciona.
Modelar el check-in como evento agendado —no como atributo de la
conversación— es lo que hace que el silencio sea representable. Es la misma
disciplina de la norma de zona horaria: la verdad de "qué día/turno es esto"
la pone el sistema, no el reloj de la respuesta.

### Pendientes que siguen en Sprint 3
- **Paso 1b:** mini-revisión de seguridad del webhook/secretos Twilio
  (validación de firma en `views.py`, manejo de secretos en `settings`) — no
  depende del scheduler, por eso queda en este sprint.
- **Paso 2:** variables nuevas de la literatura (FC/FR, RH/antecedentes) —
  analizar los artículos en `/docs` y decidir si entran antes o después del
  merge.
- **Paso 3:** auditoría de cierre en dos frentes (Claude Code: coherencia y
  deuda técnica; Codex: seguridad adversarial + escalabilidad; síntesis
  priorizada en chat).
- **Paso 4:** resolver lo bloqueante de la síntesis y merge
  `sprint-3-whatsapp` → `Desarrollo` con aprobación del Arquitecto.

---

## Sesión: Variable nueva — Tolerancia a líquidos (Regla 6)
**Fecha:** 20/06/2026
**Responsable:** León (Arquitecto IA) con Claude (chat) y Claude Code
**Estado:** COMPLETADO ✅ (commits 96f81c4, b13aacb, 0ad58d1)

### Qué se hizo
Primera de las 4 variables nuevas del Paso 2 (Sprint 3). Se agregó
`tolero_liquidos` (booleano nullable) a RegistroDiario, un tipo de
alerta nuevo INTOLERANCIA_ORAL, una pregunta al final del flujo del bot
("¿Ha podido tomar líquidos sin vomitar?"), y la Regla 6 en el
alert_engine.

### Decisiones tomadas y su justificación
1. **Booleano (sí/no), no escala.** La tolerancia a líquidos es
   binaria en lo que importa clínicamente (¿retiene líquidos o no?); el
   matiz de "cuánto" ya lo aproxima episodios_nauseas.
2. **Tipo de alerta nuevo INTOLERANCIA_ORAL, no reutilizar
   ILEO_PARALITICO.** Para granularidad en el dashboard futuro e
   investigación — permite filtrar/contar por causa específica en vez
   de colapsar tres síntomas (gases, náuseas, líquidos) en un solo
   tipo genérico.
3. **Escalera MEDIA(1 día)/ALTA(2 días), arranca en MEDIA no BAJA.**
   La deshidratación es la causa #1 de readmisión (Lawrence 2013, 25%);
   no retener líquidos ni un día ya es señal directa hacia
   deshidratación, por eso no hay escalón BAJA y el techo ALTA llega a
   los 2 días (no 3 como gases) — comprimido a propósito porque la
   deshidratación se instala rápido.
4. **Lógica de días calendario** (igual que gases): un día cuenta como
   "toleró" si hubo al menos un registro positivo. Queda lista para el
   2×/día del Sprint 4 sin retrabajo.

### Base clínica
Tolerancia oral = criterio de alta en todos los ERAS revisados; Lawrence
2013 (deshidratación = causa #1 de readmisión); Delaney 2008 (tolera sin
vómito como criterio de alta). Sin umbral numérico heredado para
telemetría post-alta — la escalera de días es construcción propia con
respaldo conceptual.

### Verificación
53/53 tests OK (49 previos + 4 nuevos). manage.py check limpio.
Auditado contra el repo: la creación del RegistroDiario se MOVIÓ al
nuevo paso (ESTADO_TOLERANCIA_LIQUIDOS) sin duplicarse — sigue
centralizada en el helper `_crear_registro`, que ahora también persiste
`tolero_liquidos`; gases/náuseas dejó de ser el paso final y solo avanza
el estado. El flujo del bot pasó de 6 a 7 preguntas; los comentarios de
referencia dentro del código (docstring de bot.py y "N preguntas" en
models.py) se actualizaron en el mismo cambio.

### Pendiente para la próxima sesión
Siguiente variable del Paso 2: **hinchazón abdominal**. Luego FC
(dispositivo del médico, pregunta directa) y FR (solo-dashboard, sin
alerta — Outersterp 2025 reporta 77% de falsas alertas). Estado de
herida (fotos) y antecedentes quedan fuera de Sprint 3.

---

## Sesión: Variable nueva — Hinchazón abdominal (Regla 7)
**Fecha:** 22/06/2026
**Responsable:** León (Arquitecto IA) con Claude (chat) y Claude Code
**Estado:** COMPLETADO ✅ (commits 556251d, 5129d80, bc723cc)

### Qué se hizo
Segunda de las 4 variables nuevas del Paso 2 (Sprint 3). Se agregó
`hinchazon_abdominal` (CharField nada/algo/mucho, nullable) a
RegistroDiario, una pregunta intermedia en el flujo del bot ("¿Cómo
siente la hinchazón o distensión de su abdomen hoy?"), y la Regla 7 en el
alert_engine. El flujo del bot pasó de 7 a 8 preguntas: hinchazón se
intercaló entre gases/náuseas (6️⃣) y tolerancia a líquidos (que pasó de
7️⃣ a 8️⃣, sigue siendo la última). A diferencia de tolerancia a líquidos
(tipo nuevo INTOLERANCIA_ORAL), hinchazón **reusa ILEO_PARALITICO**: la
distensión es convergente con gases y náuseas como signo del mismo
cuadro.

### Decisiones tomadas y su justificación
1. **Escala ordinal nada/algo/mucho, no booleano.** A diferencia de
   tolerancia a líquidos (binaria), la hinchazón importa por su
   *trayectoria*: lo clínicamente relevante no es "hay o no hay" sino si
   está empeorando. Se mapea internamente a niveles 0/1/2 para poder
   comparar entre días.
2. **La escalera prioriza ESPECIFICIDAD a propósito (baja sensibilidad).**
   Casi todos los pacientes tienen algo de hinchazón post-operatoria
   normal; alertar por el valor absoluto generaría una avalancha de
   falsos positivos. Por eso la regla NO alerta por "tiene hinchazón"
   sino por **empeoramiento** o por **"mucho" prolongado**. La hinchazón
   estable —incluso en nivel alto— no alerta: es el estado esperado.
3. **Tres condiciones, severidad = la más alta que aplique** (mismo
   patrón de "no duplicar, tomar el máximo" ya usado en náuseas):
   - **BAJA — empeoramiento puntual:** el nivel de hoy es mayor que el de
     ayer. Señal temprana, solo monitorear.
   - **MEDIA — empeoramiento verificado y sostenido:** hoy es
     estrictamente mayor que antier (empeoró contra el punto de partida)
     Y no hubo una bajada en el medio (ayer no bajó respecto a antier, y
     hoy no bajó respecto a ayer). La doble condición evita que una
     fluctuación que sube y baja (p. ej. algo→mucho→algo) se confunda con
     un empeoramiento real: solo dispara si la tendencia se mantiene.
   - **ALTA — "mucho" sostenido 4 días calendario consecutivos:**
     distensión severa persistente, el umbral más fuerte de íleo.
4. **Lógica de días calendario** (como gases/náuseas/líquidos): "el nivel
   de un día" es el máximo reportado ese día. Con 1×/día es trivial, pero
   queda listo para el 2×/día del Sprint 4 sin retrabajo.

### Base clínica
La distensión abdominal es un signo cardinal del íleo paralítico, por eso
la alerta es de tipo ILEO_PARALITICO (convergente con gases y náuseas).
El auto-reporte del paciente (PROM — patient-reported outcome measure) es
el método viable por WhatsApp: no hay medición objetiva remota, así que
se captura la percepción del paciente en lenguaje natural. No hay umbral
numérico heredado de la literatura para distensión auto-reportada
post-alta; la escalera por empeoramiento es construcción propia, diseñada
para maximizar especificidad dado que la hinchazón basal post-op es casi
universal.

### Verificación
60/60 tests OK (53 previos + 7 nuevos de hinchazón). manage.py check
limpio. La condición MEDIA —la más delicada— se validó contra los 5 casos
de borde antes de implementar: empeoramiento sostenido (algo/algo/mucho)
y subida progresiva (nada/algo/mucho) → MEDIA; fluctuación que mejora
(algo/mucho/algo), bajada en el medio (mucho/algo/mucho) y estable
(algo/algo/algo) → no MEDIA. La lógica booleana `hoy>antier ∧ ayer≥antier
∧ hoy≥ayer` refleja exactamente la definición. Cada test usa valores
neutros en gases (True) y náuseas (0) para aislar la alerta de hinchazón,
ya que las tres comparten el tipo ILEO_PARALITICO.

### Pendiente para la próxima sesión
Quedan 2 de las 4 variables nuevas del Paso 2: **frecuencia cardíaca (FC)**
—dispositivo provisto por el médico, pregunta directa— y **frecuencia
respiratoria (FR)** —solo-dashboard, sin alerta, porque Outersterp 2025
reporta 77% de falsas alertas con FR. Después del Paso 2 siguen el repaso
final de alert_engine.py, la implementación de 2×/día en bot.py (con los
2 gatings) y el merge a Desarrollo.

---

## Sesión: Variables nuevas FC y FR — cierre del Paso 2 (4/4)
**Fecha:** 24/06/2026
**Responsable:** León (Arquitecto IA) con Claude (chat) y Claude Code
**Estado:** COMPLETADO ✅ (FC: commits 03ed352, 2c3de80, 7088ade · FR:
commits 1189e47, e97c765)

### Qué se hizo
Se implementaron las dos últimas variables nuevas del Paso 2:
**frecuencia cardíaca (FC)** y **frecuencia respiratoria (FR)**, ambas
constantes vitales que el paciente mide con un dispositivo provisto por
el médico (pregunta directa, sin condicional). Con esto cierra el Paso 2
(4/4: tolerancia a líquidos, hinchazón, FC, FR) y el flujo del bot pasó
de 8 a 10 preguntas. Se agruparon FC (8️⃣) y FR (9️⃣) juntas, antes de
tolerancia a líquidos (🔟, última), por ser ambas mediciones con
dispositivo.

La diferencia de fondo entre las dos: **FC genera alerta (Regla 8,
tipo nuevo TAQUICARDIA); FR NO genera ninguna alerta** — se captura solo
para el dashboard del médico.

### Decisiones de diseño y su justificación

**FC — tipo de alerta nuevo TAQUICARDIA (no reusar SEPSIS):**
La taquicardia es etiológicamente inespecífica — signo temprano de
sepsis, pero también de sangrado/fuga, hipovolemia, dolor, arritmia.
Etiquetarla SEPSIS afirmaría una causa que el dato por sí solo no
establece (de hecho CREWS 2022 la asocia a fuga/sangrado, no a sepsis).
Coherente con el principio ya fijado en INTOLERANCIA_ORAL (granularidad
para dashboard e investigación) y con "la IA NO diagnostica": un tipo
propio presenta la señal cruda y deja que el médico la correlacione.

**FC — escalera por valor absoluto, sin días calendario:**
A diferencia de temperatura/gases/náuseas/hinchazón, el valor de FC por
sí solo ya es clínicamente significativo, así que no se evalúa
persistencia ni ventana de días. Umbrales: 101-109 BAJA (taquicardia
leve, probablemente fisiológica), 110-149 MEDIA (umbral de intervención),
>=150 ALTA (escalamiento inmediato). Solo se vigila FC alta, no
bradicardia (decisión del Arquitecto). Parser del bot: rango 30-250 lpm
para descartar errores de tipeo.

**FR — solo dashboard, sin regla en el alert_engine:**
Decisión explícita del Arquitecto de NO generar alerta con FR.
Outersterp 2025 halló que el **77% de las falsas alertas** provenían del
sensor de frecuencia respiratoria. Generar alertas con FR introduciría
más ruido que señal y erosionaría la confianza del médico en el sistema.
Se captura y almacena para que el médico la lea en contexto, pero el
`alert_engine` no la toca (cero reglas nuevas para FR). Parser del bot:
rango 5-60 rpm.

### Base clínica y referencias
- **FC > 100 lpm** como umbral de monitoreo domiciliario: Outersterp 2025
  (en `docs/auditoria_literatura/`).
- **FC 110 lpm, 75% de sensibilidad para fuga/sangrado:** Estudio CREWS,
  Hospital Catharina 2022 — https://pubmed.ncbi.nlm.nih.gov/35850957/
- **FC > 110 lpm como umbral de intervención:** Cleveland Clinic
  NCT04574908 —
  https://cdn.clinicaltrials.gov/large-docs/08/NCT04574908/Prot_SAP_002.pdf
- **FC > 150 lpm escalamiento inmediato:** protocolos hospitalarios —
  https://med-linket-corp.com/blogs/news/hospital-monitor-alarms
- **FR como fuente de falsas alertas (77%):** Outersterp 2025 (en
  `docs/auditoria_literatura/`) — fundamento de la decisión de no alertar
  con FR.

### Verificación
69/69 tests OK (60 previos + 8 de FC + 1 de FR). `manage.py check` limpio.
- FC: 8 tests — escalera en los bordes exactos (100 sin alerta, 101 y 109
  BAJA, 110 y 149 MEDIA, 150 ALTA, null sin alerta) + 1 de reintento por
  valor fuera de rango en el bot.
- FR: 1 test que confirma que un valor alto (FR=30) con el resto del
  registro neutro NO genera ninguna alerta (prueba de que es solo-dashboard).
- Tests previos del alert_engine intactos: FC y FR son nullable y FR no
  tiene regla; la de FC solo dispara con `is not None`.

### Nota técnica resuelta durante la implementación
Al agregar el estado `ESPERANDO_FRECUENCIA_RESPIRATORIA` (33 caracteres),
el campo `estado` de `ConversacionWhatsApp` (max_length=30) quedó corto y
`manage.py check` lo detectó (fields.E009). Se amplió `max_length` a 40
(incluido en la migración 0008). Lección: al nombrar estados largos,
vigilar el `max_length` del CharField que los almacena.

### Pendiente para la próxima sesión
**El Paso 2 (variables nuevas) está completo — las 4 entraron.** Quedan,
antes del merge a Desarrollo: (1) implementar la frecuencia de check-ins
2×/día en bot.py (arquitectura CheckInProgramado ya cerrada, ver entrada
del 22/06), resolviendo los 2 gatings pendientes (deduplicación de
alertas y gating pre-operatorio); (2) repaso final de `alert_engine.py`
completo (8 reglas juntas); (3) auditoría de cierre en dos frentes
(Claude Code + Codex); (4) merge `sprint-3-whatsapp` → `Desarrollo`.

---

## Sesión: Cambio de medico_responsable a ForeignKey(User)
**Fecha:** 24/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** COMPLETADO ✅ (commits eb4a41a, 164492f)

### Qué se hizo
Se cambió el campo `medico_responsable` del modelo `Paciente` de
`CharField(max_length=200)` (un string libre con el nombre del médico) a
`ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True,
blank=True, related_name='pacientes')`. Con esto el médico pasa a ser un
usuario real de Django con acceso al admin, y la relación se puede usar en
el dashboard de Sprint 4 para filtrar alertas por médico.

Cambios concretos:
- **models.py:** import `settings`, nueva definición del FK, `__str__`
  actualizado para usar `get_full_name()/username` del User, o "Sin médico
  asignado" si el FK es None.
- **admin.py:** se reemplazó `medico_responsable` en `list_display` por un
  método `medico_nombre()` decorado con `@admin.display` que muestra nombre
  completo o username, y "— Sin asignar" si es None. `search_fields`
  extendido para buscar por `first_name`, `last_name` y `username` del médico.
- **Migración 0009:** editada manualmente para usar `RemoveField + AddField`
  en vez del `AlterField` autogenerado. El motivo: la BD de desarrollo tenía
  pacientes existentes con el string "Medico Prueba" en la columna varchar —
  un `AlterField` intentaría castear ese string a integer (la nueva columna FK
  es un entero), lo que falla en PostgreSQL. `RemoveField + AddField` descarta
  la columna vieja y crea la nueva FK nullable, dejando a todos los pacientes
  existentes con `medico_responsable=NULL`. Verificado en shell: el paciente
  "Alejandro Valencia" quedó con `medico_responsable: None`.
- **tests.py:** eliminadas las 55 ocurrencias de
  `medico_responsable="Medico Prueba"` (era el valor de prueba del string
  viejo — pasar un string a un FK lanza `ValueError`). Como ningún test
  existente prueba el valor del médico, `None` es el valor correcto para todos.
  Se agregaron 5 tests nuevos en la clase `PacienteMedicoFKTests`: FK y
  `related_name` funcionan, `__str__` con nombre completo, `__str__` con
  username (fallback), `__str__` sin médico, y `on_delete=SET_NULL` verificado
  al borrar el User. Suite final: **74 tests OK**.

### Origen del cambio
La recomendación de pasar `medico_responsable` a FK provino de una revisión
de Gemini al código del modelo. El Arquitecto la evaluó y la aprobó como
mejora de diseño necesaria para Sprint 4 (dashboard por médico,
autenticación real en admin).

### Pendiente para la próxima sesión
Sin cambios respecto al cierre anterior: (1) implementar 2×/día en `bot.py`
con arquitectura CheckInProgramado; (2) repaso final de `alert_engine.py`
completo (8 reglas juntas); (3) auditoría de cierre en dos frentes
(Claude Code + Codex); (4) merge `sprint-3-whatsapp` → `Desarrollo`.
Sincronización de docs de este cambio: commits `docs:` en esta misma sesión.

---

## Auditoría de cierre Sprint 3 — Veredicto y hallazgos
**Fecha:** 24/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code (coherencia y lógica clínica) + Codex (seguridad y escalabilidad, pasada web + pasada local)
**Estado:** COMPLETADO ✅ — ver `docs/proceso/auditorias/2026-06_informe_sprint3_cierre.md`

### Qué se auditó y quién

Se realizó una auditoría de cierre en dos frentes sobre la rama
`sprint-3-whatsapp` antes de su merge a `Desarrollo`. Claude Code revisó
coherencia interna: que todos los estados del bot tengan handler, que
`_crear_registro()` y `_limpiar_temporales()` operen sobre los mismos 12
campos, que todas las reglas del `alert_engine` usen `timezone.localdate()`
sin residuos de UTC, y que la lógica clínica sea consistente con las
decisiones de arquitectura registradas en CLAUDE.md y el ROADMAP. Codex
hizo una pasada adversarial de seguridad y escalabilidad: revisó el
manejo de secretos Twilio, la validación del webhook, race conditions y
la capacidad de respuesta ante carga.

### El veredicto

**El código es correcto y funcional. El merge a `Desarrollo` puede
proceder.** Lo que produjo la auditoría no es deuda de corrección
(el sistema hace lo que dice que hace, los 74 tests pasan), sino deuda
de robustez: problemas que no rompen lo que hoy funciona pero que sí
romperían a escala con pacientes reales.

**Lo que NO debe ocurrir es ir de `Desarrollo` a producción real con
pacientes sin resolver el Grupo A completo.** Producción con Grupo A
pendiente pone datos médicos reales en riesgo.

### Hallazgos por grupo

**Grupo A — Obligatorio antes de pacientes reales (6 hallazgos):**
El más importante es la conversación abandonada (A1): si un paciente
deja el cuestionario a mitad y retoma al día siguiente, el bot mezcla
datos de ambos días en un solo registro. Le sigue el bloqueo por FC/FR
(A2): los campos son `null=True` en el modelo —diseñados para captura
opcional— pero el parser del bot exige un número válido, lo que deja
atascado a cualquier paciente sin oxímetro disponible. Los otros cuatro
(idempotencia del webhook ante reintentos de Twilio, ausencia de
`select_for_update()` para mensajes simultáneos, falta de rate limiting,
y `DEBUG=True` con Twilio real activo) son todos problemas de
infraestructura que ningún test de lógica de negocio puede detectar —
de ahí el valor de la pasada de Codex.

**Grupo B — Hardening de producción (7 hallazgos):**
Settings sin directivas HTTPS, ausencia de logging filtrado para
PHI/PII, el path síncrono del webhook que puede exceder el timeout de
Twilio (y que, al hacerlo, dispara los reintentos de A3), la ausencia
de un índice eficiente para los filtros de días calendario que son el
corazón del `alert_engine`, el admin en la URL por defecto sin 2FA ni
lockout, el admin que aún muestra todos los pacientes a cualquier
médico (la FK `medico_responsable→User` ya existe; falta el
`get_queryset()` que la aplique), y tests del webhook que no cubren los
casos negativos más importantes.

**Grupo C — Backlog sin fecha comprometida (7 ítems):**
Deuda cosmética y técnica menor: la función `evaluar_registro()` creció
a ~450 líneas (candidata a extracción de sub-funciones por regla),
choices sin `CheckConstraint` en BD, actualización de Django 6.0.5→6.0.6,
decimales truncados silenciosamente en los parsers de FC/FR, el mensaje
de alerta invisible en `list_display` del admin, un 403 que revela más
detalles de los necesarios, y el endpoint de contacto web sin rate limit.

### Estado final del sistema al cierre

- **74 tests OK** — 49 del alert_engine (8 reglas, 2 bugs de zona
  horaria corregidos) + 11 del bot + 4 del webhook + 10 de modelos.
- **8 reglas clínicas activas** — drenaje (Regla 2, escalera por
  aspecto), temperatura (Regla 1, ALTA/MEDIA por subfebrícula),
  gases (Regla 3, escalera por días consecutivos), náuseas (Regla 4,
  suma diaria + persistencia), dolor (Regla 5, ventanas por
  dia_postoperatorio + tendencia), tolerancia a líquidos (Regla 6,
  INTOLERANCIA_ORAL), hinchazón abdominal (Regla 7, ILEO_PARALITICO
  por empeoramiento), frecuencia cardíaca (Regla 8, TAQUICARDIA por
  valor absoluto). FR capturada y almacenada, sin regla.
- **4 variables nuevas del Paso 2** completamente integradas:
  `tolero_liquidos`, `hinchazon_abdominal`, `frecuencia_cardiaca`,
  `frecuencia_respiratoria`.
- **`medico_responsable` como FK** a `auth.User` con `SET_NULL`
  (commit `eb4a41a`) — base para el scoping del dashboard en Sprint 4.
- **Flujo del bot en 10 preguntas** (temperatura, dolor, drenaje ×2,
  gases+náuseas, hinchazón, FC, FR, tolerancia a líquidos).
- **Documentación sincronizada:** CLAUDE.md, ROADMAP y BITACORA
  reflejan el estado real del código. `docs/proceso/auditorias/2026-06_informe_sprint3_cierre.md`
  creado en la raíz del repo con el detalle técnico de cada hallazgo.

### Próximo paso

1. **Merge `sprint-3-whatsapp` → `Desarrollo`** con aprobación del Arquitecto.
2. **Rama `sprint-3-hardening`** desde `Desarrollo` para resolver Grupo A
   y Grupo B antes de cualquier exposición con pacientes reales. Ruta de
   entrada sugerida: A2 (FC/FR skipeable) → A1 (reinicio de conversación
   abandonada) → A3+A4 (idempotencia y lock transaccional, naturalmente
   acoplados).
3. **Sprint 4 (dashboard + CheckInProgramado + Celery)** arranca sobre
   la base ya endurecida, no antes.

---

## Merge: Sprint 3 → Desarrollo
**Fecha:** 24/06/2026
**Commit de merge:** 94ff710
**Estado:** ✅ Completado — cero conflictos, 74/74 tests OK.

Sprint 3 integrado a Desarrollo. Incluye: bot de WhatsApp (10
preguntas), 8 reglas del alert_engine bajo modelo de alta sensibilidad,
4 variables nuevas (tolerancia a líquidos, hinchazón abdominal, FC, FR),
medico_responsable como ForeignKey(User), fix de zona horaria, y
auditoría de cierre completa (ver AUDITORIA_SPRINT3_CIERRE.md).

Próxima rama: sprint-3-hardening (Grupo A y B de la auditoría antes
de producción real), luego Sprint 4 (dashboard del médico).

---

## Sprint 3-Hardening — Seguridad y Robustez Pre-Producción
**Fecha:** 25/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Rama:** `sprint-3-hardening`
**Estado:** COMPLETADO ✅ — 88/88 tests OK

### Qué se hizo

Se resolvieron los 20 hallazgos del Grupo A, B y C de
`docs/proceso/auditorias/2026-06_informe_sprint3_cierre.md`, en orden A1→A6, B1→B7, C1→C7.
Cada hallazgo tiene su commit individual en la rama.

**Grupo A — Lógica y seguridad del bot:**

- **A1 — Conversación abandonada:** Si el paciente dejó un registro
  incompleto el día anterior, el bot detecta el desfase
  (`timezone.localdate(conv.fecha_actualizacion) < hoy`), limpia los
  temporales y reinicia con un mensaje de aviso. Decisión: Option B
  (warn + reset).

- **A2 — FC y FR no saltables:** El paciente puede escribir "saltar",
  "omitir", "no sé", "no puedo", "no tengo" o "sin dato". El bot
  guarda `None` y avanza. Las palabras de salto se muestran en la
  pregunta del chat. Decisión del Arquitecto: mostrar las opciones
  predefinidas en el mismo mensaje.

- **A3 — Idempotencia:** `views.py` cachea el `MessageSid` por 5 min
  y devuelve TwiML vacío si el SID ya fue procesado.

- **A4 — Race condition:** `procesar_mensaje()` ejecuta dentro de
  `transaction.atomic()` con `select_for_update()` sobre
  `ConversacionWhatsApp`.

- **A5 — Rate limiting:** 20 mensajes/hora por número de teléfono
  (cache.incr + fallback a set para primer mensaje).

- **A6 — Settings de entorno:** Separados `settings_local.py` y
  `settings_production.py` con todos los headers de seguridad HTTPS.

**Grupo B — Infraestructura y datos:**

- **B1:** Headers HTTPS en `settings_production.py` (HSTS 31536000 s,
  SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SSL_REDIRECT, NOSNIFF,
  X_FRAME_OPTIONS=DENY).
- **B2:** LOGGING configurado (WARNING para django, ERROR para
  django.request). `@sensitive_post_parameters` en el webhook.
- **B3:** `evaluar_registro()` invocado con `transaction.on_commit()`.
  Test actualizado con `captureOnCommitCallbacks(execute=True)`.
- **B4:** `db_index=True` en `fecha_registro` + índice funcional
  `CAST(... AT TIME ZONE 'America/Bogota' AS date)` via RunSQL.
- **B5:** URL del admin configurable por `ADMIN_URL`. `django-axes 7.0.1`:
  5 fallos → bloqueo 1 hora.
- **B6:** `get_queryset()` en los 3 admins filtra por médico responsable;
  superuser ve todo.
- **B7:** 4 tests nuevos del webhook (header ausente, body vacío,
  idempotencia, rate limit).

**Grupo C — Backlog:**

- **C1 — Refactor alert_engine:** `evaluar_registro()` queda como
  orquestador de 8 llamadas `_evaluar_X(registro)`. Reglas 3 y 4
  estaban invertidas en el archivo — corregido. `ORDEN_SEVERIDAD`
  promovido a constante de módulo.

- **C2 — CheckConstraint:** 6 constraints PostgreSQL en `Paciente`,
  `RegistroDiario` y `Alerta` para campos categóricos clínicos.
  Nullable: `Q(campo__isnull=True) | Q(campo__in=[...])`.

- **C3 — Django 6.0.6:** Actualización desde 6.0.5. `requirements.txt`
  regenerado.

- **C4 — Decimales truncados en FC/FR:** `_parse_entero_rango()` ahora
  detecta `\d+[.,]\d+` y devuelve `None` → bot pide reintento en lugar
  de truncar silenciosamente. 4 tests nuevos.

- **C5 — Mensaje en list_display:** `AlertaAdmin` muestra `mensaje_corto`
  (primeros 80 chars) sin abrir el detalle.

- **C6 — 403 genérico:** `HttpResponseForbidden()` sin body para no
  revelar que el endpoint valida firma de Twilio.

- **C7 — Rate limit en contacto:** 5 envíos/hora por IP en
  `home/views.py`. Campos truncados a max_length del modelo
  (nombre 100, teléfono 30, mensaje 2000). Template muestra aviso
  si se supera el límite.

**Grupo D — Auditoría post-hardening (segunda pasada Codex):**

Después del Grupo C se corrió una auditoría Codex adicional que encontró
4 hallazgos bloqueantes. Se resolvieron en la misma sesión antes del merge.

- **D1 — RedisCache sin paquete redis:** `settings_production.py` usaba
  `RedisCache` pero `redis` no estaba en `requirements-runtime.txt` ni en
  `requirements.txt`. Agregado `redis>=5` en ambos archivos. Test nuevo:
  `CacheProductionConfigTests.test_redis_importable_para_settings_produccion`
  verifica que `import redis` no falla.

- **D2 — AlertaAdmin sin protección de borrado por objeto:** `has_delete_permission`
  en `AlertaAdmin` retornaba True para el médico propietario. Cambiado a
  `return request.user.is_superuser` incondicionalmente — las alertas son
  registros clínicos con trazabilidad obligatoria; el médico solo puede marcar
  `resuelta=True`, nunca borrar.

- **D3 — `X-Forwarded-For` spoofeable:** `_get_client_ip()` en `home/views.py`
  usaba `HTTP_X_FORWARDED_FOR` como fuente primaria. Reemplazado por `REMOTE_ADDR`
  únicamente. **Pendiente de producción (no bloquea el merge):** el proxy/balanceador
  Nginx debe configurarse con `proxy_set_header REMOTE_ADDR $remote_addr;` para
  que `REMOTE_ADDR` refleje la IP real del cliente, no la del proxy. Esto se
  resuelve en el Sprint de despliegue (FASE 5), no en el código de Django.

- **D4 — `requirements.txt` duplicado y desactualizado:** reorganizados en dos
  archivos con responsabilidades claras: `requirements-runtime.txt` (6 deps
  directas, lo que va a producción) y `requirements.txt` (pip freeze completo,
  para reproducir el entorno exacto de desarrollo).

- **D5 — Tests de scoping admin incompletos:** expandida la clase
  `AdminScopingTests` con cobertura completa de `RegistroDiarioAdmin` y
  `AlertaAdmin` (changelist y URL directa) además de `PacienteAdmin`.

**Fix adicional — Aserciones de redirect en Django 6:**

Los tests de acceso ajeno (`test_medico_no_puede_editar_*`) asercionaban que
el redirect iba al changelist del modelo (`/admin/signos_sintomas/<model>/`).
En Django 6.0.6, `_get_obj_does_not_exist_redirect` redirige al índice del
admin (`/admin/`) cuando el objeto no está en el queryset del usuario.
Corregido: se usa `assertRegex(resp.url, r'^/admin/')` en lugar del path
específico del changelist. La propiedad de seguridad verificada es la misma:
el formulario (status 200) nunca se renderiza para objetos ajenos.

**Resultado final:** 103 tests OK, `manage.py check --deploy` con
`settings_production`: 0 issues. Auditoría Codex: ✅ APROBADO.

### Decisiones clínicas tomadas
Ninguna. El hardening es de infraestructura, seguridad y calidad de
código, no clínico.

### Problemas encontrados y resueltos

1. **B3 — `on_commit` no dispara en TestCase:** `TestCase` envuelve
   cada test en una transacción que nunca hace commit. Solución:
   `captureOnCommitCallbacks(execute=True)`.

2. **B4 — `::date` falla en RunSQL:** psycopg2 interpreta `::` como
   operador de Python. Solución: `CAST(... AS date)`.

3. **B2 — Traceback en tests por LOGGING:** `test_token_faltante_falla_seguro`
   imprime un ERROR al stdout porque `ImproperlyConfigured` se levanta
   intencionalmente. Comportamiento esperado; 103 tests pasan.

4. **Edit tool — "2 matches":** Al intentar parchear `has_delete_permission` en
   `AlertaAdmin` (D2), el mismo bloque de código existía en `RegistroDiarioAdmin`.
   Edit no puede distinguirlos con `replace_all=false`. Solución: reescritura
   completa de `admin.py` con la herramienta Write.

5. **AdminScopingTests — Staff sin permisos → 403:** Un usuario con
   `is_staff=True` pero sin permisos de modelo asignados recibe 403 al intentar
   acceder al admin. Solución: asignar permisos explícitos via `Permission +
   ContentType` en el `setUp` de los tests.

### Próximo paso

1. ~~Merge `sprint-3-hardening` → `Desarrollo`~~ ✅ Completado.
2. **Sprint 4** — Dashboard médico (panel de alertas, notificación por
   email ante alerta ALTA, CheckInProgramado). Arranca sobre la base
   ya endurecida. Rama: `sprint-4-dashboard`.

---

## Sprint 4 — Dashboard y Notificaciones
**Fecha:** 26/06/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** COMPLETADO ✅ — Bloques 0, 1, 2A, 2B, 3, 4, 5A, 5B, 5C, 6 completados. 135 tests OK.

### Qué se hizo

**Bloque 0 — Decisiones arquitectónicas (cerradas en esta sesión):**
Se tomaron 5 decisiones de diseño que desbloquean toda la implementación
del Sprint 4. Ninguna implica código — son las decisiones que definen
cómo se escribe el código de los bloques siguientes.

Adicionalmente se generó un prompt de contexto para uso en chats externos
(Claude chat / Codex) que resume el estado del proyecto y las decisiones
tomadas. Se marcaron como completados los Pasos 3 y 4 de FASE 3.6 que
faltaban en el ROADMAP.

### Decisiones tomadas

**0-① Fecha autoritativa:**
`evaluar_registro(registro, fecha_referencia=None)` — parámetro opcional.
Default: `timezone.localdate(registro.fecha_registro)`. El bot pasa
`fecha_referencia=checkin.fecha_dia` al completar el flujo. Corrige el
bug de cruce de medianoche en reglas de persistencia (temperatura
subfebril, gases, náuseas, líquidos, hinchazón). → Bloque 2A.

**0-② Deduplicación de alertas (Opción A+):**
Una alerta por tipo/día. Si ya existe una del mismo tipo con severidad
igual o mayor ese día, no se duplica. Si la nueva severidad es mayor
(escalamiento intra-día), sí se crea. Comparación con
`_ORDEN_SEVERIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3}`. → Bloque 2B.

**0-③ Alerta de silencio:**
Tipo `SILENCIO` nuevo en `Alerta.tipo`. Racha check a check: 1 → BAJA,
2 consecutivos → MEDIA, 3+ → ALTA. Racha se rompe con COMPLETADO.
El Arquitecto propuso BAJA para el primer silencio (vs. MEDIA original)
— más tolerante con olvidos puntuales, coherente con la escalera del
engine. → Bloque 4.

**0-④ Scheduler (Opción A — management commands):**
Tres commands: `crear_checkins_diarios` (6:00 AM),
`enviar_recordatorios` (7:00 AM), `cerrar_checkins_vencidos` (18:00 y
06:00 AM). Horas de gracia: 10 horas. Celery diferido a Sprint 5.
Migración posible sin retrabajo: decorar con `@shared_task`. → Bloque 4.

**0-⑤ Gating POD 0 (Opción A):**
`_evaluar_dolor()` usará `dia_postoperatorio <= 2` en lugar de
`in [1, 2]`. Cambio defensivo de 1 línea. Justificación clínica:
dia_postoperatorio=0 es imposible en operación normal — cirugías de 9+
horas, alta siempre al día siguiente o después. → Bloque 2A.

### Problemas encontrados y resueltos

Ningún bug en esta sesión. Aclaración clave: el "gating pre-operatorio"
del ROADMAP sonaba como decisión compleja pero resultó ser una 1 línea
defensiva. La clarificación fue que dia_postoperatorio=0 no ocurre en
operación real porque el alta siempre llega después del día de cirugía.

---

### Bloque 1 — CheckInProgramado (26/06/2026, sesión 2)

**Qué se hizo:**
- Modelo `CheckInProgramado` agregado al final de `models.py`. Campos:
  `paciente` (FK PROTECT), `fecha_dia` (DateField, no auto), `orden`
  (PositiveSmallInt), `etiqueta` (MAÑANA/TARDE), `hora_programada`,
  `fecha_respuesta` (null), `estado` (PENDIENTE/COMPLETADO/NO_RESPONDIDO),
  `registro` (OneToOne a RegistroDiario, null). Constraints: UniqueConstraint
  (paciente+fecha_dia+orden) + 2 CheckConstraints en BD para estado y etiqueta.
- Migración `0012_checkin_programado` generada con `makemigrations` y aplicada
  exitosamente.
- `CheckInProgramadoAdmin` en `admin.py`: `readonly_fields` para todos los
  campos de sistema, `has_add_permission=False` (los crea el scheduler),
  `has_delete_permission` solo superuser. Scoping por médico responsable.
- 7 tests en `CheckInProgramadoModelTests` (constraints, defaults, OneToOne,
  str, etc.). Suite: **110 tests OK**.
- Commit: `b445b9b` en `sprint-4-dashboard`.

---

### Bloques 2A y 2B — alert_engine.py refactor (26/06/2026, sesión 2)

**Qué se hizo:**

**Bloque 2A — fecha_referencia:**
- `evaluar_registro(registro, fecha_referencia=None)` — la firma cambió. Si
  `fecha_referencia=None`, el default es `timezone.localdate(registro.fecha_registro)`.
- Las 6 funciones privadas con lógica de días calendario reciben ahora
  `fecha_referencia` como parámetro en lugar de computar
  `timezone.localdate(registro.fecha_registro)` cada una por su cuenta.
  Esto corrige el bug de cruce de medianoche: el bot puede pasar
  `fecha_referencia=checkin.fecha_dia` y el engine agrupa correctamente.
- Las 2 funciones sin lógica de fechas (`_evaluar_drenaje`,
  `_evaluar_frecuencia_cardiaca`) también reciben `fecha_referencia` para
  que puedan pasar la fecha a `_deduplicar` sin requerir otro parámetro.
- Gating POD 0 (decisión 0-⑤): la condición `dia_postoperatorio <= 2` ya
  existía en `VENTANAS_DOLOR`. Solo se actualizó el comentario de la tupla
  para que diga "POD 0-2" en lugar de "POD 1-2". No hubo cambio de lógica.
- 3 tests en `AlertFechaReferenciaTests`: backward compat, cruce de medianoche
  da MEDIA en vez de ALTA, control con default ALTA.

**Bloque 2B — Deduplicación Opción A+:**
- Nueva función `_deduplicar(paciente, tipo, severidad, fecha_referencia)`:
  filtra `Alerta` por `paciente`, `tipo` y `fecha_alerta__date=fecha_referencia`,
  retorna `True` si ya existe una alerta de igual o mayor severidad (usando
  `ORDEN_SEVERIDAD` que ya existía en el engine). Si `True`, el llamador hace
  `return []` sin crear la alerta.
- Guard insertado antes de cada `Alerta.objects.create()` en las 8 funciones
  privadas. Permite escalamiento intra-día (BAJA→MEDIA→ALTA) pero bloquea
  duplicados y retrocesos (ALTA→MEDIA bloqueada).
- 6 tests en `AlertDeduplicacionTests`: misma severidad bloqueada, escalamiento
  intra-día pasa, severidad menor bloqueada, días distintos no se bloquean
  (requiere `update()` en `fecha_alerta` para simular alert de ayer), tipos
  distintos coexisten, gases+náuseas mismo día generan ILEO BAJA + ALTA.
- Suite total: **119 tests OK**.
- Commit: `c7baeee` en `sprint-4-dashboard`.

**Problemas encontrados y resueltos:**

1. **Reescritura total del engine vs. ediciones parciales:** dada la cantidad
   de cambios (todos los `def _evaluar_*` tocados), se optó por reescribir
   el archivo completo. Previene errores de edición parcial.

2. **Test `test_diferentes_dias_no_se_bloquean` fallaba (0 != 1):** la
   deduplicación filtra por `fecha_alerta__date`, pero `fecha_alerta` es
   `auto_now_add=True` — se crea con el timestamp actual. En el test, la
   alerta "de ayer" se creaba con `fecha_alerta=ahora=hoy`, así que la
   deduplicación de "hoy" la encontraba y bloqueaba la nueva. Solución:
   `Alerta.objects.filter(...).update(fecha_alerta=timezone.now() - timedelta(days=1))`
   después de crear la alerta "de ayer", simulando que fue creada ayer.

---

### Bloque 3 — bot.py refactor (26/06/2026, sesión 3)

**Qué se hizo:**

- `_procesar_con_conv` completamente reemplazado. Nueva lógica:
  1. Si estado != INICIO/COMPLETADO y `fecha_actualizacion` < hoy → abandono:
     limpiar temporales, buscar CheckInProgramado PENDIENTE hoy. Si existe →
     ESTADO_TEMPERATURA (next msg = temperatura). Si no → ESTADO_INICIO.
  2. Si en flujo hoy → `_procesar_respuesta_flujo` (sin cambios).
  3. FAQ siempre disponible (no depende de check-in).
  4. Si hay CheckInProgramado PENDIENTE → poner ESTADO_TEMPERATURA + devolver
     MSG_PREGUNTA_TEMPERATURA.
  5. Si hay CheckInProgramado COMPLETADO hoy → devolver MSG_YA_REGISTRADO.
  6. Si no hay ninguno → devolver MSG_SIN_CHECKIN.
- `_crear_registro` completamente reemplazado. Vincula el RegistroDiario al
  CheckInProgramado PENDIENTE (SELECT orden ASC) dentro de la misma llamada:
  `checkin.registro = registro; checkin.estado = COMPLETADO;
  checkin.fecha_respuesta = now(); checkin.save()`. Luego llama
  `evaluar_registro(registro, fecha_referencia=checkin.fecha_dia)`.
- MSG_YA_REGISTRADO y MSG_SIN_CHECKIN actualizados con mensajes que dejan
  la puerta abierta para la futura integración de IA/RAG.
- Tests actualizados: `_crear_paciente` en `BotWhatsAppTests` y
  `BotAbandonoConversacionTests` crean CheckInProgramado PENDIENTE.
  `WebhookWhatsAppTests.test_post_valido` también actualizado.
- 3 tests nuevos: MSG_SIN_CHECKIN (sin checkin, sin RegistroDiario),
  MSG_YA_REGISTRADO (vía checkin COMPLETADO), vínculo checkin↔registro.
- Suite: **122 tests OK**. Commit: `dafd319`.

**Decisión de arquitectura tomada (sesión 3):**
- MSG_SIN_CHECKIN = "Por ahora no tienes un reporte pendiente. Te escribiré
  cuando sea la hora 🌿 Si tienes alguna duda sobre tu recuperación, puedes
  preguntarme aquí." — formulado para que la futura integración de IA/RAG
  sea un reemplazo del final de la frase, sin retrabajo de flujo.
- MSG_YA_REGISTRADO = "¡Tus datos de hoy ya están registrados! ✅ Si tienes
  alguna duda sobre tu recuperación, puedes escribirme aquí 🌿"

**Problema encontrado y resuelto:**
- `test_sin_checkin_pendiente_muestra_mensaje` fallaba: el test asumía que
  no se creaba `ConversacionWhatsApp`, pero `procesar_mensaje` siempre la
  crea vía `get_or_create`. La aserción correcta es que no se crea
  `RegistroDiario`, no que la conversación no exista.
- `test_post_valido_devuelve_twiml` fallaba: el test del webhook no creaba
  CheckInProgramado → bot devolvía MSG_SIN_CHECKIN. Solución: agregar
  `CheckInProgramado.objects.create(...)` en el setUp del test.

---

### Bloque 4 — Scheduler + alerta SILENCIO (26/06/2026, sesión 3)

**Qué se hizo:**

**Modelo:**
- `Alerta.tipo`: nuevo choice `SILENCIO` (paciente sin respuesta).
- `Alerta.registro_origen`: ahora `null=True, blank=True` — las alertas
  SILENCIO no tienen RegistroDiario (el paciente no respondió).
- `CheckConstraint alerta_tipo_valido` actualizado para incluir SILENCIO.
- Migración `0013_bloque4_silencio_registro_origen_nullable` generada y aplicada.

**Management commands (signos_sintomas/management/commands/):**
- `crear_checkins_diarios.py`: `get_or_create` de 2 CheckInProgramado por
  paciente activo (orden=1 MAÑANA 7:00, orden=2 TARDE 14:00). Idempotente.
  Loguea resumen. Cron: 6:00 AM Bogotá.
- `enviar_recordatorios.py`: stub — loguea los check-ins PENDIENTE con
  hora_programada <= ahora. La llamada real a Twilio está diferida a Sprint 5.
  Cron: 7:00 AM Bogotá.
- `cerrar_checkins_vencidos.py`: cierra PENDIENTE con >10 h desde
  hora_programada → NO_RESPONDIDO + alerta SILENCIO. Función `_calcular_racha`:
  cuenta NO_RESPONDIDO consecutivos anteriores al actual (orden cronológico
  estricto: fecha_dia + orden), racha incluye el actual. Corte al primer
  COMPLETADO o PENDIENTE anterior. `_severidad_silencio`: racha 1 → BAJA,
  2 → MEDIA, 3+ → ALTA. Cron: 18:00 y 06:00 AM Bogotá.

**Tests:** 8 nuevos en `SchedulerTests`. Suite: **130 tests OK**.
Commits: Bloque 4 en `c7593cc`.

---

### Bloques 5A, 5B, 5C — Admin dashboard + email (26/06/2026, sesión 3)

**Bloque 5A — Colores en admin + acción marcar_resuelta:**
- `AlertaAdmin.severidad_badge()`: badge HTML inline con `format_html`.
  ALTA=rojo (#7f1d1d fondo #fee2e2), MEDIA=ámbar (#78350f fondo #fef3c7),
  BAJA=verde (#14532d fondo #dcfce7). Funciona sin CSS extra — todo inline.
- `marcar_resuelta`: acción admin para selección múltiple. Actualiza
  `resuelta=True` + `fecha_resolucion=timezone.now()` con un solo `queryset.update()`.
- 2 tests: badge en changelist contiene `border-radius`, acción actualiza alerta.

**Bloque 5B — Historial 7 días en ficha de paciente:**
- `_historial_7_dias(paciente)`: función que genera tabla HTML con los últimos
  7 días de RegistroDiario: fecha, POD, temperatura, dolor EVA, gases, náuseas,
  drenaje, tolerancia líquidos, FC. Usa `mark_safe`.
- `PacienteAdmin.historial_ultimos_7_dias`: campo `readonly_field` que llama
  la función anterior. Se muestra en el formulario de cambio del paciente en
  el admin. Sin templates extra — HTML en Python.

**Bloque 5C — Email al médico por alerta ALTA:**
- `signals.py`: señal `post_save` en `Alerta`. Si `created=True` y
  `severidad='ALTA'` y el paciente tiene médico con email: agenda
  `send_mail` en `on_commit`. Si no tiene médico o email, loguea WARNING.
  `fail_silently=False` — errores se loguean, no se silencian.
- `apps.py`: `ready()` importa signals para registrarlas al arrancar.
- `settings_local.py`: `EMAIL_BACKEND = console` + `DEFAULT_FROM_EMAIL`
  para dev (evita errores de conexión SMTP).
- 3 tests: email enviado por ALTA, MEDIA no envía, paciente sin médico no falla.
- Suite: **135 tests OK**. Commit: `4bbddb4`.

---

### Bloque 6 — Seed demo (26/06/2026, sesión 3)

**Qué se hizo:**
- `seed_demo.py`: management command con 10 días de RegistroDiario para
  paciente ficticio Camilo Andrés Rueda Vargas (tel +573001234567).
  Datos diseñados para mostrar variedad clínica: fiebre día 3 (SEPSIS ALTA),
  drenaje turbio día 5 (FUGA MEDIA), drenaje purulento día 9 (FUGA ALTA),
  intolerancia oral día 6, taquicardia leve día 7. El alert_engine genera
  27 alertas automáticamente al correr el seed.
- Crea superuser `demo_medico / demo1234` si no existe.
- Opción `--borrar` para eliminar y recrear desde cero.
- Crea CheckInProgramado COMPLETADO por día para que el historial sea
  consistente con el modelo de datos real.
- Idempotente: si el paciente demo ya existe, no re-crea (sin `--borrar`).
- Suite: **135 tests OK**. Commit: `ea4a739`.

### Decisiones tomadas en sesión 3

- **Mejoras futuras documentadas en ROADMAP:** vista separada historial paciente
  (URL/template propios con gráficas — Sprint 5+), integración IA/RAG en bot
  (NotebookLM / sistema RAG — prerequisito: decidir umbrales alert_engine).
- **Vista historial Opción A:** historial como `readonly_field` en la ficha
  del paciente del admin. Sin URL/template propios (diferidos a Sprint 5+).
- **Email Opción A+:** señal `post_save` con `on_commit` — garantiza que la
  alerta existe en BD antes de enviar el email. El campo `medico_responsable`
  puede ser null → la señal maneja ese caso con WARNING, sin excepción.

### Pendiente para Sprint 5

- Merge `sprint-4-dashboard → Desarrollo` (con aprobación del Arquitecto).
- Configurar cron del SO (Windows Task Scheduler o Linux cron) para los
  3 management commands del scheduler.
- Configurar SMTP real en `settings_production.py`.
- Proxy Nginx con `proxy_set_header REMOTE_ADDR` (pendiente de Sprint 3).
- Twilio saliente en `enviar_recordatorios` (stub → llamada real).
- RAG / IA en el bot (prerequisito: decisiones de umbrales alert_engine).

---

## Sprint 5 — Producción
**Fecha:** 01/07/2026 (sesión de apertura)
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** EN CURSO ⏳ — merge de Sprint 4 confirmado, auditoría de ROADMAP hecha, pendientes de decisión antes de escribir código.

### Qué se hizo

- **Merge `sprint-4-dashboard → Desarrollo`:** fast-forward limpio
  (`f4a476b..353ec60`), sin conflictos, 135 tests OK post-merge. Push
  confirmado a `origin/Desarrollo`.
- **Rama `sprint-5-produccion`** creada desde `Desarrollo` y pusheada.
- **Auditoría completa del ROADMAP** contra el historial real de git y el
  filesystem: se encontraron y corrigieron 4 desincronizaciones (ver abajo).
- **Recibido documento externo** "Instrucciones para Claude Code — Sprint 5"
  (generado en una sesión de chat de Claude.ai, no en Claude Code), con 13
  decisiones de producto propuestas (P-1 a P-13) y 7 bloques de
  implementación. Se comparó contra el estado real del código — ver
  hallazgos de seguridad/discrepancias abajo. **Ninguna de las 13 decisiones
  ni los 7 bloques se implementó todavía** — quedan pendientes de
  confirmación explícita del Arquitecto en esta sesión, según el protocolo
  del proyecto (ningún cambio clínico/de producto se ejecuta sin
  aprobación explícita en sesión con el agente de código).

### Desincronizaciones encontradas y corregidas en el ROADMAP

1. Encabezado del archivo y de FASE 4 seguían diciendo `sprint-4-dashboard`
   / "EN CURSO" — corregido a `sprint-5-produccion` / "COMPLETADA".
2. FASE 3: el checkbox de merge `sprint-3-whatsapp → Desarrollo` seguía sin
   marcar pese a que esos commits ya estaban en `Desarrollo` desde antes de
   `sprint-3-hardening` (confirmado con `git log Desarrollo --oneline`).
3. FASE 3.6: los ítems "alerta de silencio" y "gating del alert_engine (2
   políticas)" seguían sin marcar, pero ambos ya se resolvieron en Sprint 4
   (Bloques 4 y 2B respectivamente) — marcados `[x]` con referencia cruzada.
4. FASE 4, Bloque 5B: el checkbox decía "historial y **gráfica**
   temperatura/dolor" marcado como hecho, pero `admin.py` solo implementa
   una tabla de texto (`_historial_7_dias`) — no hay ningún `Chart.js` ni
   `<canvas>` en el código. Se anotó la imprecisión sin desmarcar el bloque
   (el resto de lo prometido sí está hecho).
5. **Estructura del Proyecto Django** (árbol de carpetas) actualizada
   contra el filesystem real: faltaban `management/commands/` completo,
   `signals.py`, `settings_local.py`, `settings_production.py`, `docs/`,
   `requirements-runtime.txt`, migraciones 0003-0013, entre otros.

### Hallazgos de seguridad/riesgo en el documento externo recibido

- **`settings_production.py` ya existe** (creado en Sprint 3-Hardening,
  commits `6ad4f80` y hallazgos D1-D5) con `DEBUG=False`, `SECURE_SSL_REDIRECT`,
  HSTS, cookies seguras y cache Redis obligatoria para multi-worker. El
  documento externo pide "crear" ese archivo con una versión más simple que
  **no incluye ninguna de esas directivas** — ejecutarlo tal cual
  sobreescribiría y regresionaría hardening ya construido y probado. Si se
  agrega SMTP real en Sprint 5, debe ser un **append** a las variables
  `EMAIL_*` existentes, nunca un reemplazo del archivo.
- **Ejemplo de código del Bloque 4 (gráficas Chart.js)** en el documento
  externo interpola `fechas`, `temperaturas`, `dolores` y `fcs` directamente
  en un f-string dentro de un `<script>`, pese a que el propio documento
  dice "escaparse con `json.dumps()` — nunca f-string directo". El código
  de ejemplo no sigue su propia regla. Si se implementa, los datos deben ir
  con `json.dumps(...)`, no interpolación directa de listas Python en JS.
- **13 decisiones de producto (P-1 a P-13)** propuestas en el documento
  externo tocan reglas de negocio y datos de paciente (cédula obligatoria,
  desactivación automática a 10 días, eliminación de emojis, email
  solo-ALTA, etc.). Como fueron decididas en una sesión de chat aparte, no
  en sesión con Claude Code, y el protocolo del proyecto exige aprobación
  explícita en sesión antes de escribir código clínico/de producto, se
  reportan pero **no se marcan como definitivas en ROADMAP/CLAUDE.md**
  hasta que el Arquitecto las confirme aquí.
- El paso "1A — merge `sprint-4-dashboard → Desarrollo --no-ff`" del
  documento es redundante: ya se hizo (ver arriba), aunque por
  fast-forward en vez de `--no-ff` (sin commit de merge dedicado). No se
  reescribió el historial de git para agregar el merge commit — reescribir
  historia ya pusheada es una operación destructiva que no se justifica
  solo por preferencia estética de topología de git.

### Decisiones de producto — confirmadas explícitamente en sesión (01/07/2026)

El Arquitecto confirmó en esta sesión, una por una, las 13 decisiones de
producto del documento externo (ahora P-1 a P-15 — ver tabla completa en
`ROADMAP_MONITOREO_POSQUIRURGICO.md`, sección FASE 5). Con esto queda
satisfecho el requisito del protocolo de "aprobación explícita en sesión"
para estas decisiones, y ya se documentaron como definitivas en el ROADMAP.

**Corrección durante la confirmación:** el Arquitecto había incluido
inicialmente una decisión sobre ampliar las respuestas predefinidas del
bot fuera de horario (15-20 respuestas validadas por el médico). Al
revisarla, indicó que fue un error de transcripción — **no aplica**. Se
mantiene la versión original del documento (P-10): el bot conserva las
respuestas predefinidas actuales sin ampliar, RAG diferido a Sprint 6. Sin
este error se habría escrito contenido nuevo hacia `knowledge_base.md`/
`bot.py` sin base real — vale la pena recordar en próximas sesiones
confirmar dos veces cualquier decisión que toque contenido clínico antes
de darla por definitiva.

**Agregado nuevo respecto al documento original:** el Arquitecto confirmó
explícitamente que HABEAS DATA (P-15) es parte del alcance de Sprint 5
—no un "nice to have" diferido— con consentimiento informado mínimo
requerido antes de que cualquier paciente real use el sistema.

### Últimas 2 preguntas de arquitectura — resueltas en sesión (01/07/2026)

- **Cron:** Linux (Railway/Render, ya era el destino de deploy decidido en
  el ROADMAP — no había nada nuevo que decidir). Windows Task Scheduler
  descartado.
- **SMTP:** Gmail con contraseña de aplicación — coherente con cuentas del
  equipo y bajo volumen de correo (solo alertas ALTA).

Con esto no quedan preguntas de arquitectura abiertas para Sprint 5.

### Bloque 1 — Cédula y desactivación automática (01/07/2026)

**Qué se hizo:**
- **1A — Campo `cedula` en `Paciente`:** `CharField(max_length=20,
  unique=True, null=True, blank=False)`. `null=True` para no romper
  pacientes ni tests existentes (incluye el paciente demo de `seed_demo`);
  `blank=False` para que sea obligatorio en el Admin/formularios de
  pacientes nuevos, según P-4. Migración `0014_paciente_cedula.py`.
  Agregado a `list_display` y `search_fields` de `PacienteAdmin`.
- **1B — `desactivar_pacientes_vencidos`:** management command nuevo,
  mismo estilo que `crear_checkins_diarios`. `DIAS_SEGUIMIENTO = 10`
  (P-5). Usa `timezone.localdate()`. Flag `--dry-run` que loguea sin
  modificar BD. Solo actúa sobre `Paciente.objects.filter(activo=True)`,
  así que es idempotente sin lógica extra (correrlo dos veces el mismo
  día no reprocesa a quien ya desactivó). La desactivación manual desde
  el Admin (`activo=False`) sigue funcionando igual, sin cambios.
- **9 tests nuevos:** `PacienteCedulaTests` (3: creación sin cédula,
  unicidad violada, dos pacientes sin cédula no chocan entre sí —
  confirma que Postgres no trata NULL=NULL como duplicado) y
  `DesactivarPacientesVencidosTests` (6: POD 10 se desactiva, POD 9 no,
  paciente ya inactivo no se toca, `--dry-run` no modifica BD, segunda
  ejecución el mismo día es idempotente, `crear_checkins_diarios` no crea
  check-ins para el paciente recién desactivado).
- Verificado con `--dry-run` contra la BD de desarrollo real: detectó
  correctamente a "Camilo Andrés Rueda Vargas" (POD 15, del seed_demo) y
  a otro paciente de prueba con POD 21 — no se ejecutó el comando sin
  `--dry-run` para no alterar los datos demo existentes.
- Suite: **144 tests OK** (135 + 9). `manage.py check` limpio.
  `manage.py migrate` aplicado sin errores.

### Bloque 2 — Eliminar emojis del bot (01/07/2026)

**Qué se hizo:**
- Se quitaron todos los emojis de los mensajes `MSG_*` en `bot.py`: los
  marcadores numerados (`1️⃣`…`🔟`) pasaron a texto plano (`"1. "`…`"10. "`),
  y el resto de emojis decorativos (🌿, ✅, 👋) se eliminaron sin
  reemplazo, según la regla del documento (solo cambia presentación, no
  contenido clínico ni lógica).
- Quedó un `①` en un comentario interno de `models.py`
  (`# ... decisión 0-①`) — no es un mensaje visible al paciente, se dejó
  intacto por estar fuera de alcance del Bloque 2.
- Los tests existentes verifican los mensajes con `assertIn` sobre
  substrings, no con igualdad exacta de string — no requirieron cambios.
- Suite: **144 tests OK** sin modificaciones a `tests.py` (P-11).

### Bloque 3 — Filtros de PacienteAdmin e historial configurable (01/07/2026)

**Qué se hizo:**
- **3A — Filtros:** se agregó `tipo_cirugia` a `list_filter` (ya existía
  `activo` y `medico_responsable`) y un `SimpleListFilter` nuevo,
  `TieneAlertaActivaFilter`, con dos opciones: "Con alertas sin resolver" /
  "Sin alertas pendientes". **Corrección respecto al documento externo:**
  el ejemplo usaba `alerta__resuelta` — el `related_name` real del FK
  `Alerta.paciente` es `alertas` (plural), así que el filtro real usa
  `alertas__resuelta`. Con el nombre equivocado el filtro habría
  reventado con `FieldError` en producción.
- **3B — Historial configurable:** `_historial_7_dias(paciente)` se
  renombró a `_historial_paciente(paciente, dias=7)`. Se agregó un
  selector de rango (7 / 14 / 30 días) como enlaces `?dias=N` insertados
  en el propio HTML del campo de solo lectura — el médico cambia el
  rango recargando la página de detalle del paciente, sin necesidad de
  un template nuevo. Como los métodos de `readonly_fields` en Django
  Admin solo reciben `obj` (no `request`), se usó el hook
  `get_readonly_fields(request, obj)` — que sí recibe `request` — para
  leer `?dias=` de la URL y guardarlo en `self._dias_historial` antes de
  que se renderice el campo. Valor inválido o fuera de rango (< 1 o >
  90) cae al default de 7.
- **6 tests nuevos** (`PacienteAdminFiltrosHistorialTests`): filtro
  `alerta_activa=si`/`no`/sin filtro, historial default 7 días, respeta
  `?dias=30`, valor inválido usa el default.
- Suite: **150 tests OK** (144 + 6). `manage.py check` limpio.

### Bloque 4 — Gráficas Chart.js, con rediseño post-revisión visual (01/07/2026)

**Contexto:** se implementó una primera versión (3 gráficas separadas,
`json.dumps()`, selector acoplado al `?dias=` del historial). Antes de
commitear, el Arquitecto trajo una segunda instrucción externa con
capturas de pantalla señalando dos "bugs" y pidiendo un rediseño visual
completo (turnos M/T en vez de hora exacta, puntos de alerta en rojo,
selector sin recarga de página, líneas de umbral más finas).

**Auditoría de la segunda instrucción antes de implementar (no se copió
tal cual):**
- El **"Bug 1" (FC nula graficada como 0) no existía** en el código ya
  escrito — la primera versión ya pasaba `frecuencia_cardiaca` crudo
  (con `None`, nunca `or 0`) y `spanGaps: true`. Se verificó con test
  antes de aceptar el diagnóstico.
- El código de ejemplo de la instrucción traía **el mismo tipo de error
  que ya se había corregido en el Bloque 3**: `.prefetch_related('alerta_set')`
  — el `related_name` real es `alertas`. Además hacía una query de
  `Alerta` por cada registro dentro de un loop (N+1). Se reemplazó por
  una sola query batched contra `registro_origen`, más precisa que
  adivinar por coincidencia de fecha.
- **Determinar el turno por la hora de respuesta (`hora < 12`) contradecía
  la decisión D2, ya cerrada en Sprint 3.6**, que existe justo para evitar
  esto ("el turno lo fija el evento programado, nunca la hora en que el
  paciente responde"). Se implementó usando `CheckInProgramado.etiqueta`
  real, vinculado por FK, con respaldo por hora solo para registros
  legado sin check-in vinculado.
- **Se encontró un bug adicional no reportado por nadie**, al tocar esa
  misma lógica: el respaldo por hora y las fechas de la tabla de
  historial usaban `fecha_registro.hour` / `.strftime()` directo sobre un
  datetime aware — con `USE_TZ=True` eso es hora **UTC**, no Bogotá. Un
  registro de las 8am Bogotá (13:00 UTC) se habría clasificado como
  turno "T" en vez de "M". Corregido con `timezone.localtime()` en los
  dos lugares. Es el mismo tipo de error que la "Norma de zona horaria"
  de CLAUDE.md ya advierte para cálculos de fecha — aquí aplicaba
  también a la hora, no solo a la fecha.
- No se usó el patrón de f-string gigante con doble-llaves (`{{`/`}}`)
  que traía el ejemplo para todo el bloque JS — alto riesgo de romper por
  una llave mal escapada en un bloque tan largo. Se separó en una
  plantilla de texto plano con dos placeholders (`__PID__`, `__CTX__`)
  reemplazados por `.replace()`, sin arriesgar el parseo de Python.

**Qué quedó implementado (versión final, la que se commiteó):**
- 3 `<canvas>` independientes (temperatura, dolor EVA, FC), cada uno con
  su propio `Chart()`.
- Selector 7/14/30 días **sin recargar la página** — los 3 rangos vienen
  precalculados como un solo objeto `DATOS` serializado con `json.dumps()`.
  Independiente del selector del historial en tabla (Bloque 3B), que
  sigue con `?dias=` y recarga de página.
- Puntos rojos = alerta ALTA sin resolver en ese registro exacto.
- Turno M/T por `CheckInProgramado.etiqueta`, con respaldo por hora local
  (Bogotá) para datos legado.
- Líneas de umbral punteadas y finas (37.9°C, 101/110 lpm) en vez de
  zonas de fondo — evita depender de un plugin adicional de Chart.js.
- Chart.js con versión fijada (`4.4.0`) vía CDN, no "latest".
- **9 tests nuevos** (`GraficaSignosVitalesTests`, reemplazan los 3 de la
  primera versión). **159 tests OK.** `manage.py check` limpio.
- Verificado contra los datos reales del seed_demo: con la ventana de "7
  días" solo se ven 3 de los 10 registros del paciente demo — **no es un
  bug**, es correcto: `seed_demo` fija fechas del 17-26 de junio de 2026
  y con la fecha real del sistema (01/07/2026) esos registros ya quedan
  entre 5 y 14 días atrás. Con "14 días" o "30 días" se ven los 10.
- **No verificado:** la renderización real de Chart.js en un navegador
  (fuera de las herramientas de esta sesión). Sí se verificó con el test
  client de Django que el HTML/JSON generado es válido y trae los
  valores esperados.

**Hallazgo colateral, explorando el flujo real del médico (no bloqueante,
sin acción tomada todavía):** `demo_medico` (creado por `seed_demo`) es
**superusuario** — ve todo `/admin/` (Usuarios, Grupos, pacientes de
cualquier médico), a diferencia de una cuenta de médico real (staff,
no-superuser), que solo ve 4 modelos (Alertas, Pacientes, Registros
Diarios, Check-ins Programados) y solo sus propios pacientes — verificado
creando y luego borrando una cuenta de prueba no-superuser. Queda
pendiente decidir si conviene una segunda cuenta demo no-superusuario
para poder probar la experiencia real de un médico sin tener que armar la
cuenta a mano cada vez.

### Bloque 5 — SMTP real, probado con alerta ALTA real (01/07/2026)

**Qué se hizo:**
- Se agregaron las variables de email (`EMAIL_BACKEND`, `EMAIL_HOST`,
  `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
  `DEFAULT_FROM_EMAIL`) al final de `settings_production.py` — **append**,
  no reemplazo del archivo (ya traía DEBUG=False, HSTS, cookies seguras y
  cache Redis desde Sprint 3-Hardening). `EMAIL_HOST_USER` y
  `EMAIL_HOST_PASSWORD` sin default en `config()`, para que falle fuerte
  si faltan en el `.env` de producción en vez de arrancar sin poder
  notificar alertas.
- Plantilla agregada a `.env.example` (sin secretos reales), con nota de
  usar una cuenta de Gmail dedicada al proyecto y contraseña de
  aplicación (no la contraseña normal de la cuenta).
- **Protocolo de seguridad seguido durante toda la prueba:** el Arquitecto
  agregó los valores reales directamente en su `.env` local — Claude Code
  nunca leyó ni imprimió la contraseña. Para diagnosticar problemas se
  usó solo longitud de string y presencia de espacios/comillas (nunca el
  valor en sí).
- **Troubleshooting real durante la prueba** (vale la pena dejarlo
  registrado): el primer intento falló con `535 5.7.8 BadCredentials` de
  Gmail. Diagnóstico sin exponer el secreto: la contraseña de aplicación
  tenía 18 caracteres con espacios — Google la muestra agrupada en
  bloques de 4 para lectura humana (`abcd efgh ijkl mnop`), pero el
  `.env` necesita el bloque de 16 caracteres sin espacios. Segundo
  intento con espacios quitados dio 15 caracteres (se perdió uno al
  editar) — también falló la validación previa. Al volver a generar/copiar
  la contraseña completa desde Google (16 caracteres, sin espacios), el
  envío fue exitoso.
- **Prueba real end-to-end:** se creó un paciente y un médico de prueba
  temporales (`dr_prueba_smtp`, email `seguimientolionalejo@gmail.com`),
  se disparó una `Alerta` real de severidad ALTA corriendo con
  `DJANGO_SETTINGS_MODULE=...settings_production`, y el correo llegó
  correctamente a la bandeja — confirmado por el Arquitecto. Los datos de
  prueba (paciente, registros, alertas, usuario) se eliminaron después de
  confirmar.
- Suite: **159 tests OK** (sin tests nuevos — el envío SMTP real no se
  puede probar con `manage.py test`, que usa `EMAIL_BACKEND=locmem`; la
  lógica del signal ya tiene cobertura desde Sprint 4,
  `AlertaEmailNotificacionTests`). `manage.py check` limpio.

**Mejora futura anotada, no implementada (pedida por el Arquitecto):**
rediseñar el formato del correo de alerta ALTA — mejor estructura visual
(HTML en vez de texto plano) y agregar datos de contacto del paciente
(teléfono, posiblemente cédula) al cuerpo del mensaje. Hoy el correo solo
trae nombre del paciente, tipo de alerta, severidad, fecha y el mensaje
del `alert_engine`.

### Bloque 6 — Documentación de despliegue: cron y transferencia (01/07/2026)

**Qué se hizo:**
- **`docs/cron_setup.md`:** documenta los **4** management commands que
  necesitan cron en producción — los 3 originales del scheduler
  (`crear_checkins_diarios`, `enviar_recordatorios`,
  `cerrar_checkins_vencidos`) más `desactivar_pacientes_vencidos`
  (Bloque 1, no contemplado en el plan original de Sprint 4). Horarios
  convertidos a UTC (Bogotá es UTC-5 fijo, sin horario de verano),
  `MAILTO` para que cualquier fallo llegue por email (mecanismo de P-3),
  y una nota sobre el servicio nativo de Cron Jobs de Railway como
  alternativa al crontab tradicional.
- **Orden obligatorio documentado:** `desactivar_pacientes_vencidos`
  **antes** de `crear_checkins_diarios` (5 minutos antes, no en el mismo
  minuto, porque cron no garantiza el orden entre tareas programadas al
  mismo tiempo).
- **Bug de documentación encontrado y corregido al escribir esto:** el
  docstring de `desactivar_pacientes_vencidos.py` (escrito en el Bloque
  1) decía que el command corre *después* de `crear_checkins_diarios` —
  pero esa misma línea explicaba el propósito de evitar que un paciente
  reciba un check-in el día que vence, algo que **solo se cumple
  corriendo antes**, no después. El test `test_scheduler_no_crea_checkins_tras_desactivacion`
  ya prueba (y siempre probó) el orden correcto; solo el comentario
  estaba mal. Corregido para decir "antes", con la explicación completa
  del riesgo (checkin que queda PENDIENTE para siempre → alerta SILENCIO
  espuria para un paciente ya inactivo).
- **`docs/transferencia_cuentas.md`:** protocolo de transferencia de
  cuentas al médico al momento de la venta (P-1/P-2/P-13), tabla de
  cuentas del proyecto con su estado actual real (Railway/Render
  pendiente de elegir, Twilio activo en sandbox, Gmail probado el mismo
  día, Redis pendiente de contratar), manual mínimo de operación para el
  médico, y recordatorio de que HABEAS DATA (Bloque 7) bloquea el uso con
  pacientes reales, no el resto del despliegue técnico.
- Suite: **159 tests OK** (sin tests nuevos — este bloque es solo
  documentación y un comentario corregido, sin cambios de comportamiento).
  `manage.py check` limpio.

### Pendiente para continuar Sprint 5

- Bloque 7: consentimiento informado mínimo (P-15) — contenido lo redacta
  o valida el médico.
- Mejora futura: rediseño del formato del correo de alerta ALTA + datos
  de contacto del paciente (ver nota del Bloque 5 arriba).

---

## Cierre de sesión — 01/07/2026 (Sprint 5, Bloques 1-6)

**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** Sprint 5 en curso — Bloques 1 a 6 completos, 159 tests OK.
Rama activa: `sprint-5-produccion`, sincronizada con `origin` (working
tree limpio, sin cambios pendientes de commit).

**Resumen de la sesión (orden cronológico):**
1. Confirmado el merge `sprint-4-dashboard → Desarrollo` (fast-forward)
   y creada `sprint-5-produccion`.
2. Auditoría completa del ROADMAP contra el historial real de git —
   corregidas 4 desincronizaciones y actualizada la estructura de
   carpetas contra el filesystem real.
3. Recibido y auditado un documento externo de instrucciones para
   Sprint 5 (13 decisiones de producto + 7 bloques). Se detectaron y
   corrigieron varios problemas antes de implementar: `settings_production.py`
   ya existía con más hardening del que el documento proponía crear;
   ejemplos de código con `related_name` inexistente (`alerta_set` en
   vez de `alertas`); un enfoque de turno por hora que contradecía la
   decisión D2 ya cerrada del proyecto.
4. Las 13 decisiones de producto (P-1 a P-15) se confirmaron
   explícitamente en esta sesión — con una corrección del propio
   Arquitecto (descartó una decisión sobre ampliar el FAQ del bot que
   había sido un error de transcripción).
5. Bloques 1-6 implementados, cada uno con su propia auditoría de
   seguridad/coherencia antes de escribir código, tests dedicados, y
   commits separados de código y documentación:
   - Bloque 1: cédula + desactivación automática a 10 días.
   - Bloque 2: emojis eliminados del bot.
   - Bloque 3: filtros de `PacienteAdmin` + historial configurable.
   - Bloque 4: gráficas Chart.js — con un rediseño completo a mitad de
     camino tras revisión visual del Arquitecto, que además destapó un
     bug real de zona horaria (UTC vs. Bogotá) no reportado por nadie.
   - Bloque 5: SMTP real, probado end-to-end con una alerta ALTA real
     (troubleshooting de contraseña de aplicación de Gmail sin exponer
     el secreto en ningún momento).
   - Bloque 6: documentación de cron y transferencia de cuentas — de
     paso se corrigió un docstring que documentaba el orden de ejecución
     al revés de lo correcto.
6. Total de tests: **135 → 159** (24 nuevos). `manage.py check` limpio
   en todo momento. `manage.py check --deploy` con `settings_production`
   también limpio (con valores de `.env` de desarrollo, no de un dominio
   real todavía).

**Decisiones clave tomadas:**
- Cron en Linux (Railway/Render), no Windows Task Scheduler.
- SMTP con Gmail + contraseña de aplicación.
- Las 13 decisiones de producto P-1 a P-15 (ver tabla en ROADMAP FASE 5).

**Problemas encontrados y resueltos (no omitir ninguno, son el valor real de esta bitácora):**
- Error 535 `BadCredentials` de Gmail — causado por la contraseña de
  aplicación pegada con espacios (18 caracteres en vez de 16), y luego
  por un carácter faltante al quitarlos (15 en vez de 16). Resuelto
  regenerando/copiando la contraseña completa. Diagnosticado sin
  exponer el valor real en ningún momento (solo longitud y presencia de
  espacios).
- `related_name` equivocado (`alerta_set` en vez de `alertas`) propuesto
  en instrucciones externas, en dos bloques distintos (3 y 4) — mismo
  tipo de error, corregido ambas veces antes de implementar.
- Bug de zona horaria (UTC vs. Bogotá) en el cálculo de turno M/T y en
  las fechas del historial — no reportado por nadie, encontrado al
  auditar el rediseño del Bloque 4.
- Docstring incorrecto en `desactivar_pacientes_vencidos.py` sobre el
  orden de ejecución respecto a `crear_checkins_diarios` — encontrado al
  escribir `docs/cron_setup.md` (Bloque 6).

**Qué queda pendiente para la próxima sesión — paso exacto:**
1. **Bloque 7 (HABEAS DATA):** consentimiento informado mínimo antes de
   pacientes reales. Requiere que el Arquitecto decida/valide el
   contenido del texto de consentimiento (con el médico) antes de tocar
   código — no se inventa contenido legal/clínico. Una vez aprobado:
   agregar campos `consentimiento_informado` y `fecha_consentimiento` a
   `Paciente` + guard en `bot.py` que impida iniciar el flujo si el
   paciente no ha consentido.
2. Mejora futura anotada (no bloqueante): rediseñar el formato del
   correo de alerta ALTA (HTML, mejor estructura) y agregar datos de
   contacto del paciente al cuerpo del mensaje (`signals.py`).
3. Resto de Sprint 5 sin empezar: desplegar en Railway/Render, Twilio
   saliente real en `enviar_recordatorios`, monitoreo externo básico,
   ajuste de Nginx `REMOTE_ADDR`.
4. Hallazgo pendiente de decidir (no bloqueante): `demo_medico` es
   superusuario y no representa la experiencia real de un médico —
   evaluar si conviene una segunda cuenta demo no-superusuario.

---

## Cierre de sesión — 02/07/2026 (Sprint 5 — correcciones pre-Bloque 7 + Bloque 7 HABEAS DATA)

**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** Sprint 5 con Parte A (correcciones pre-Bloque 7) y Bloque 7
(HABEAS DATA) completos. **177 tests OK.** Rama activa: `sprint-5-produccion`,
sincronizada con `origin`.

**Resumen de la sesión (orden cronológico):**
1. Recibido un documento externo de instrucciones ("Pre-Bloque 7 + Bloque 7")
   con 5 correcciones de auditoría (A-1 a A-4, más el commit A-5) y la
   implementación del Bloque 7. Antes de tocar código se verificó el estado
   real del repo contra lo que el documento afirmaba (rama, 159 tests,
   `manage.py check` limpio) — coincidía. También se confirmó que
   `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` (la plantilla de consentimiento
   que el documento decía ya aprobada) existía y su contenido coincidía con
   lo descrito.
2. Se encontró y eliminó (con confirmación del Arquitecto)
   `CONTEXTO_TRANSFERENCIA_DECISIONES_ARQUITECTURA.md`, un archivo suelto sin
   trackear, de la era Sprint 3 (17/06/2026), ya completamente obsoleto.
3. **A-1 (ingreso tardío):** el Arquitecto eligió implementar **ambas
   opciones** — guard `DIAS_GRACIA_INGRESO=2` en
   `desactivar_pacientes_vencidos` (no desactiva a un paciente hasta que
   lleve al menos 2 días registrado en el sistema) + advertencia en
   `PacienteAdmin.save_model` cuando se crea un paciente con POD ≥ 8.
4. **A-2 (validación de cédula):** agregado `Paciente.clean()` que exige
   cédula solo para pacientes nuevos (`pk is None`). **Bug real detectado
   en el diseño original del documento:** proponía dejar `cedula` con
   `blank=False` a nivel de campo, pero eso hace que `full_clean()` falle
   para *cualquier* paciente sin cédula — incluidos los migrados/legado —
   no solo los nuevos como se pretendía. Corregido cambiando el campo a
   `blank=True` y dejando toda la exigencia de "obligatorio para nuevos"
   en el `clean()` personalizado (migración `0015`).
5. **A-3 (seed_demo):** agregado guard que aborta el comando si
   `DEBUG=False`; la cuenta demo pasó de `create_superuser` a
   `create_user(is_staff=True, is_superuser=False)` — de paso resuelve el
   hallazgo pendiente de la sesión anterior (`demo_medico` no representaba
   la experiencia real de un médico).
6. **A-4 (email de alerta ALTA):** el cuerpo ahora incluye teléfono y
   cédula del paciente y la hora en zona Bogotá (`timezone.localtime`,
   nunca el datetime crudo en UTC) — resuelve la mejora anotada como
   pendiente en el Bloque 5. Asunto también mejorado.
7. Suite tras Parte A: **171 tests OK** (159 + 12 nuevos). Commit `fix:` y
   push.
8. **Bloque 7 (HABEAS DATA):** el Arquitecto confirmó en esta misma sesión
   que el texto de `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` ya está
   generado y aprobado como plantilla — se copió tal cual a `docs/` sin
   reescribirlo. Implementados los campos `Paciente.consentimiento_informado`
   (default `False`) y `fecha_consentimiento` (migración `0016`),
   auto-registro/limpieza de la fecha en `PacienteAdmin.save_model`, y un
   guard al inicio de `bot.procesar_mensaje` que devuelve un mensaje neutro
   (sin mencionar "consentimiento" ni "datos") si el paciente no ha sido
   confirmado por su médico.
9. El guard de consentimiento rompió 22 tests existentes del bot/webhook
   (todos asumían pacientes ya "operativos" sin marcar el campo, que ahora
   nace en `False`). Corregido agregando `consentimiento_informado=True`
   a los fixtures de paciente en `BotWhatsAppTests`, `BotAbandonoConversacionTests`,
   `ParseEnteroRangoDecimalTests` y `WebhookWhatsAppTests` — son tests de
   la máquina de estados y del webhook, no del consentimiento en sí, así
   que la corrección es consistente con lo que cada test pretende probar.
10. Suite final: **177 tests OK** (171 + 6 nuevos de Bloque 7).
    `manage.py check` limpio en todo momento. Commit `feat:` y push.

**Decisiones clave tomadas:**
- A-1: ambas opciones (guard en el comando + advertencia en Admin) — no
  son mutuamente excluyentes.
- Texto del consentimiento informado: confirmado como ya aprobado por el
  Arquitecto en esta sesión (no se redactó contenido nuevo).
- `CONTEXTO_TRANSFERENCIA_DECISIONES_ARQUITECTURA.md` (obsoleto, Sprint 3):
  eliminado con confirmación explícita.

**Problemas encontrados y resueltos (no omitir ninguno):**
- Documento de instrucciones con un error real de diseño en A-2: `cedula
  blank=False` rompía `full_clean()` para pacientes legado sin cédula,
  contradiciendo el propio objetivo de "obligatorio solo para nuevos".
  Detectado al escribir el test de paciente existente sin cédula, antes de
  que llegara a producción. Corregido con `blank=True` + `clean()`.
- El guard de consentimiento informado (Bloque 7) tenía blast radius
  amplio: 22 tests de sesiones anteriores fallaron porque asumían
  pacientes sin necesidad de consentimiento explícito. Se corrigieron los
  fixtures (no la lógica del guard, que es la esperada) tras confirmar que
  ninguno de esos tests trataba sobre consentimiento — todos probaban
  comportamiento de la máquina de estados o del webhook.

**Qué queda pendiente para la próxima sesión — paso exacto:**
1. Resto de Sprint 5 sin empezar: desplegar en Railway/Render, Twilio
   saliente real en `enviar_recordatorios`, monitoreo externo básico,
   ajuste de Nginx `REMOTE_ADDR`.
2. Antes del primer paciente real: verificar en el Admin, con un caso de
   prueba, el flujo completo de consentimiento (marcar → bot responde
   normal; desmarcar → bot vuelve a bloquear) en un entorno lo más
   parecido a producción posible (no solo en tests).
3. `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` sigue teniendo campos entre
   corchetes (`[Nombre del médico]`, `[correo]`, etc.) pendientes de
   completar con los datos reales del médico/institución antes de
   imprimirse para el primer paciente real.

---

## Sesión 02/07/2026 (tarde) — Post-Bloque 7: Bloques A, B, C

**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** Bloques A y B implementados; C verificado como no-op. **191 tests
OK.** Rama activa: `sprint-5-produccion`, todo pusheado.

**Qué se hizo:**
- **Bloque A — Motivo de resolución en Alerta.** Se agregaron dos campos a
  `Alerta`: `motivo_resolucion` (7 opciones fijas + "Otro") y
  `motivo_resolucion_detalle` (texto libre, requerido solo si el motivo es
  "Otro"). Migración `0017`. La acción del Admin "Marcar como resuelta" dejó
  de resolver de un clic: ahora muestra un **formulario intermedio**
  (`TemplateResponse` + template `admin/signos_sintomas/alerta/motivo_resolucion.html`)
  donde el médico elige obligatoriamente el motivo antes de confirmar. El
  campo de detalle se muestra/oculta con JS según el motivo. El scoping por
  médico (un no-superuser solo resuelve alertas de sus propios pacientes) se
  aplica en cada paso, re-filtrando por permisos sin confiar en los pk que
  llegan del cliente. Los campos de resolución quedan readonly en el detalle.
  6 tests nuevos + actualización del test existente `test_accion_marcar_resuelta`
  al flujo de dos pasos.
- **Bloque B — Tono de cierre del bot según severidad.** Cuando un check-in
  genera alertas MEDIA o ALTA, el bot cierra con una recomendación de acción
  al paciente: MEDIA → "contacta a tu médico en las próximas horas"; ALTA →
  "comunícate con tu médico o ve a urgencias". Tono tranquilizador; **nunca**
  menciona el tipo de alerta ni los valores. BAJA y sin alertas mantienen el
  cierre neutro (`MSG_CONFIRMACION`). 8 tests nuevos.
- **Bloque C — Limpieza de Sugarbaker en index.html: NO-OP.** Ver decisiones.

**Decisiones tomadas:**
- **Bloque B, ubicación de la evaluación de alertas (decisión de León:
  savepoint defensivo).** Para poder elegir el mensaje de cierre según la
  severidad, el bot necesita conocer las alertas ANTES de responder. Hoy
  `evaluar_registro` corría diferido en `transaction.on_commit` — es decir,
  DESPUÉS de que el bot ya respondió (la premisa del documento de
  instrucciones era correcta, verificada contra el código). Se movió a
  ejecución **síncrona** dentro de `_crear_registro`, que ahora devuelve
  `(registro, alertas_nuevas)`. La evaluación va dentro de un **savepoint**
  (`with transaction.atomic()` anidado) con `try/except`: si el motor de
  alertas fallara (bug futuro), se descarta solo la evaluación —el
  RegistroDiario y el check-in COMPLETADO SIEMPRE quedan guardados y el
  paciente recibe el cierre neutro—. Esto es más robusto que el diseño
  anterior (donde un fallo del engine en on_commit podía 500 tras guardar el
  registro, o dejar alertas sin crear) y que la versión simple del documento
  (que perdería el registro del paciente en un rollback). Django descarta los
  callbacks `on_commit` registrados dentro de un savepoint que se revierte,
  así que un fallo de evaluación tampoco dispara emails espurios.
- **Bloque C es un no-op verificado, no se inventaron cambios.** El documento
  pedía limpiar restos de "Sugarbaker"/"HIPEC" de `home/templates/home/index.html`.
  Auditoría (`grep -i` sobre todo el repo): NO hay ninguna mención en
  `index.html` ni en ninguna plantilla de `home`. Las únicas apariciones son
  la opción legítima `sugarbaker_hipec` del campo `tipo_cirugia` en
  `models.py` (que el propio documento dice NO tocar) y tres migraciones
  (inmutables). No había nada que limpiar; se documenta como verificado y no
  se tocó código. Se consultó a León antes de saltarlo.

**Problemas / observaciones:**
- El cambio de Bloque B rompió a propósito el test `test_alerta_no_se_muestra_al_paciente`,
  que afirmaba que un check-in con fiebre alta (SEPSIS ALTA) devolvía
  `MSG_CONFIRMACION`. Bajo Bloque B ese caso ahora devuelve
  `MSG_CIERRE_ALERTA_ALTA`. Se actualizó el test preservando su intención
  real (el paciente no ve el tipo de alerta ni los valores): ahora verifica
  que la respuesta es el cierre ALTA y que NO contiene "sepsis", "alerta" ni
  el valor "38.5".
- La premisa técnica del documento (que `evaluar_registro` corría en
  on_commit) resultó CORRECTA esta vez —se verificó en `bot.py` antes de
  actuar— a diferencia de sesiones anteriores donde las premisas externas
  tenían errores. Se deja anotado que la auditoría previa sigue siendo
  obligatoria aunque a veces confirme que el documento estaba bien.

**Tests al cerrar:** 191 OK (177 → +6 Bloque A → 183 → +8 Bloque B → 191).
`manage.py check` limpio.

**Commits:** `a04a7d4` (feat Bloque A), `b7d86c3` (feat Bloque B), + este
`docs`. Bloque C sin commit de código (no-op).

**Qué queda pendiente — paso exacto:**
1. **Prueba manual real por WhatsApp (canal Twilio):** completar un check-in
   con datos que disparen una alerta MEDIA y otra ALTA, y confirmar que
   llegan `MSG_CIERRE_ALERTA_MEDIA` / `MSG_CIERRE_ALERTA_ALTA` al teléfono.
   Los tests cubren la lógica, no el canal.
2. Escalamiento automático MEDIA→ALTA: **diferido a Sprint 6** (decisión del
   documento, no implementado en esta sesión).
3. Resto de Sprint 5: desplegar en Railway/Render, Twilio saliente real en
   `enviar_recordatorios`, monitoreo externo, Nginx `REMOTE_ADDR`, y
   completar los campos entre corchetes del formato de consentimiento.

---

## Sesión 03–04/07/2026 — Revisión de ROADMAP + preparación y despliegue en Railway (EN CURSO)

**Responsable:** León (Arquitecto IA) con Claude Code; Alejandro ejecutando las
acciones de infraestructura en Railway.
**Estado:** Repo **preparado para deploy** y despliegue en Railway **en curso**
(pendiente de terminar). **191 tests OK**, `manage.py check` limpio.

### 1. Revisión de checkboxes del ROADMAP

Se auditaron los 12 checkboxes `[ ]` del ROADMAP contra el código real. **Dos
estaban cumplidos pero sin marcar**, ahora marcados (commit `1329171`):
- **Duración del seguimiento / desactivación automática de `Paciente.activo`**
  → resuelto en Sprint 5 Bloque 1 + A-1 (`desactivar_pacientes_vencidos`).
- **Interfaz del médico para gestionar alertas** → resuelto entre Sprint 4
  Bloque 5A (badge de severidad, marcar resuelta) y Sprint 5 Bloque A (motivo
  con opciones de falso positivo).
- **P-12 (landing del médico)** se dejó sin marcar: existe `index.html` como
  landing general, pero no una presentación específica del médico — decisión
  pendiente del Arquitecto.

### 2. Preparación del repo para Railway (parte código)

Commits `9fd25cf` (config) y `8a573f0` (docs). Cambios:
- **`nixpacks.toml`** (raíz) — instala desde `requirements-runtime.txt`,
  `collectstatic` en build, `migrate`+`gunicorn --chdir` en start.
- **`.python-version` = 3.13**.
- **`requirements-runtime.txt`** — agregados `gunicorn` y `whitenoise`.
- **`STATIC_ROOT`** en `settings.py`; **WhiteNoise** (middleware + STORAGES
  manifest comprimido) en `settings_production.py`.
- **Bug de doc corregido:** el docstring de `settings_production.py` decía que
  la variable era `DJANGO_ALLOWED_HOSTS`, pero el código real lee
  `ALLOWED_HOSTS`. Habría hecho perder tiempo en la sesión en vivo.
- **`staticfiles/`** a `.gitignore`.
- **`docs/railway_deploy.md`** — guía de referencia con las variables de
  entorno exactas y el orden de pasos.
- Verificado: `collectstatic` recoge 130 estáticos sin errores; 191 tests OK.
  WhiteNoise no se probó local (no instalado en el entorno global de León).

### 3. Despliegue en vivo en Railway — problemas encontrados y resueltos

**Contexto de estructura (clave):** `manage.py` NO está en la raíz del repo
sino en la subcarpeta `Registro_Post_Quirurgico/`, y los `requirements` están
en la raíz. Además `requirements.txt` es el `pip freeze` completo de la máquina
Windows de León (incluye `pywin32`, `winrt-*`) → rompería el build en Linux; por
eso el deploy usa `requirements-runtime.txt`.

Secuencia de problemas (todos reales, todos resueltos):
1. **Otro chat de Claude (con screenshots) recomendó un fix peligroso:** crear
   Procfile y "agregar gunicorn y dj-database-url a `requirements.txt`". Se
   auditó y se **rechazó**: ese chat no sabía que `requirements.txt` es el freeze
   con paquetes solo-Windows; instalar ese archivo rompería el build. Además no
   usamos `dj-database-url` (leemos `DB_*` con decouple). Se le explicó a León
   por qué no ejecutarlo tal cual.
2. **Primer deploy: "No start command detected".** Causa: Railway usó su builder
   nuevo **Railpack**, que **ignora `nixpacks.toml`**. Fix: cambiar el Builder a
   **Nixpacks** en Settings. Con eso Railway leyó nuestro `nixpacks.toml` (el
   plan mostró exactamente nuestros comandos).
3. **Segundo deploy: `pip: command not found` (exit 127).** Causa: peculiaridad
   de Nix — al personalizar el paso de instalación, `pip`/`ensurepip` no quedan
   en el PATH. Pelear con Nix (venv, ensurepip) es un pozo sin fondo en nixpkgs.
   **Fix definitivo: `Dockerfile`** (`python:3.13-slim`, pip garantizado) — build
   determinista, inmune al builder de Railway, con el layout de subcarpeta y
   `requirements-runtime.txt` controlados explícitamente. Commit `f05344b`.
   `collectstatic`/`migrate`/`gunicorn` corren en el ARRANQUE (en un build de
   Docker en Railway las variables del servicio no están disponibles; en runtime
   sí). Se conservó `nixpacks.toml` como fallback inerte.

**Estado de Railway al cerrar:** proyecto creado (entorno "production"),
PostgreSQL y Redis provisionados (activos), servicio web conectado a la rama
`sprint-5-produccion`, dominio público generado. **Pendiente:** cambiar el
Builder a **Dockerfile**, cargar las variables de entorno, y redesplegar.

### Qué queda pendiente — pasos exactos del siguiente bloque de Railway

1. **Builder → Dockerfile** (servicio web → Settings → Build → Builder).
2. **Cargar variables** (Variables → Raw Editor), incluyendo el truco
   `ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}}` y
   `CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}` para no depender de
   copiar el dominio a mano; `DB_*` con `${{Postgres.*}}` y `REDIS_URL` con
   `${{Redis.REDIS_URL}}`; `SECRET_KEY` nuevo, `EMAIL_*`, `TWILIO_AUTH_TOKEN`,
   `DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_production`. Lista
   completa en `docs/railway_deploy.md`.
3. **Redesplegar** y verificar build + arranque (pasar el log si falla).
4. **`createsuperuser`** desde la shell del servicio en Railway.
5. Abrir la URL pública `/admin/` y confirmar que carga con estilos.
6. **Cron jobs** (los 4 de `docs/cron_setup.md`, orden:
   `desactivar_pacientes_vencidos` antes de `crear_checkins_diarios`).
7. **Webhook de Twilio** → apuntar a la URL de Railway (Auth Token primario).
8. Antes del primer paciente real: prueba manual del bot por WhatsApp (tono
   MEDIA/ALTA + flujo de consentimiento) y completar los `[corchetes]` del
   formato HABEAS DATA.

**Nota sobre Twilio (aclaración de esta sesión):** el Auth Token primario NO
caduca; la restricción de 72 h del plan gratis es del **Sandbox de WhatsApp**
(cada teléfono de prueba debe re-enviar el `join ...` cada 72 h de
inactividad), no de la credencial ni del despliegue.

---

## Sesión 06/07/2026 — Despliegue en Railway COMPLETADO (app viva end-to-end)

**Responsable:** León (Arquitecto IA) guiando; Alejandro ejecutando en Railway;
Claude Code guiando clic por clic y resolviendo el código.
**Estado:** **App desplegada y funcional en producción.** URL:
`registropostquirurgico-production-1f96.up.railway.app`. **194 tests OK.**

### Qué se logró
- App Django corriendo en Railway con **Dockerfile** (build determinista).
- PostgreSQL + Redis provisionados; **migraciones aplicadas** en la nube.
- Estáticos servidos con **WhiteNoise** (Admin con estilos).
- **Bot de WhatsApp respondiendo end-to-end** (WhatsApp → Twilio → Railway →
  Django → bot → respuesta). Verificado: un número no registrado recibe
  `MSG_NO_REGISTRADO`.
- **Acceso al Admin** resuelto y **limpieza de seguridad** hecha.

### Secuencia de problemas y soluciones (lo valioso — no omitir ninguno)
1. **"No start command detected" (Railpack).** Railway usó por defecto su
   builder nuevo **Railpack**, que **ignora `nixpacks.toml`**. Se cambió el
   Builder a **Nixpacks** en Settings → leyó bien nuestro plan.
2. **`pip: command not found` (Nixpacks/Nix).** Al personalizar la instalación,
   Nix no deja `pip`/`ensurepip` en el PATH. Pelear con Nix es un pozo sin
   fondo → se pivoteó a un **`Dockerfile`** (`python:3.13-slim`, pip
   garantizado). `collectstatic`/`migrate` corren en el ARRANQUE porque en un
   build de Docker en Railway las variables del servicio no están disponibles.
3. **"couldn't locate the dockerfile".** Railway estaba reconstruyendo un
   **commit viejo** (sin Dockerfile) al hacer "Redeploy" sobre un deployment
   anterior. Un commit vacío NO disparó deploy (Railway ignora commits sin
   cambios de archivos); se resolvió con un commit real / desplegando el último
   commit.
4. **`Bad Request (400)` / ALLOWED_HOSTS.** El `${{RAILWAY_PUBLIC_DOMAIN}}` no
   quedó apuntando al dominio visitado. Se **fijó el dominio a mano** en
   `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.
5. **Nadie podía entrar al Admin.** La BD estaba vacía (sin usuarios); `demo_medico`
   no se crea en producción (guard A-3). Se creó el superusuario desde variables
   `DJANGO_SUPERUSER_*` en el arranque. **`createsuperuser --noinput` NO
   actualiza usuarios existentes**, así que cuando las credenciales quedaron
   "sucias" no había forma de corregir → se creó el comando **`crear_admin`**
   (idempotente: crea o re-establece la contraseña exacta; no-op sin variables).
6. **Bloqueo de `django-axes`.** Tras varios intentos fallidos, axes bloqueó la
   IP (5 intentos → 1 h). Se agregó el interruptor **`RESET_AXES=1`** que corre
   `axes_reset` al arranque; se quita después para no debilitar la protección.
7. **La causa raíz de los login fallidos y del 403 de Twilio: los `< >`.** Los
   placeholders `<...>` de las instrucciones se pegaron **literalmente** en las
   variables (token, y muy probablemente usuario/contraseña). El
   `TWILIO_AUTH_TOKEN` con `< >` daba **403 exacto** en el webhook (la firma no
   coincidía). Al dejar los valores **pelados** (sin `< >`, sin comillas, sin
   espacios) y re-crear el admin con `crear_admin`, todo funcionó. **Lección:
   en Railway las variables van con el valor crudo, nunca entre `< >` ni
   comillas.**

### Decisiones clave
- **Builder = Dockerfile** (no Nixpacks/Railpack) — determinista, inmune a los
  cambios de builder de Railway. `nixpacks.toml` queda como fallback inerte.
- Comando **`crear_admin`** como forma soportada de gestionar el superusuario en
  producción sin shell interactivo.
- `requirements.txt` (freeze Windows) **nunca** se usa para deploy; el Dockerfile
  instala `requirements-runtime.txt`.

### Limpieza de seguridad (hecha)
- Superusuario creado con contraseña limpia (vía `crear_admin`), login exitoso.
- Variables **`RESET_AXES`** y **`DJANGO_SUPERUSER_PASSWORD`** eliminadas
  (axes restaurado; sin contraseña suelta en variables). Quedan
  `DJANGO_SUPERUSER_USERNAME`/`EMAIL` (inofensivas — `crear_admin` no toca nada
  sin el password).

### Tests
194 OK (191 previos + 3 de `crear_admin`). `manage.py check` limpio.

### Commits de la sesión
`9fd25cf`, `8a573f0`, `f05344b` (prep + Dockerfile), `ab9b397` (trigger),
`aaf4aba`, `2ef5092` (superuser/axes al arranque), `8efb0ef` (`crear_admin`),
+ este cierre `docs`.

### Aclaración importante para producción (discutida en sesión)
El bot responde mientras (a) **Railway** siga corriendo (tiene **costo mensual
por uso** — sin plan/pago se suspende) y (b) el **canal de Twilio** siga activo.
Hoy usan el **Sandbox de WhatsApp** (solo pruebas: regla 72 h, número
compartido). Para pacientes reales hace falta la **API de WhatsApp Business**
(número propio aprobado por Meta + **facturación de Twilio por conversación**).
Los **cron jobs NO mantienen el bot vivo** — automatizan el flujo diario
(crear check-ins, etc.). Hoy el sistema es **reactivo** (responde cuando el
paciente escribe); el recordatorio saliente sigue siendo stub. Requisitos del
piloto real listados en ROADMAP (FASE 5, sección "Requisitos para piloto real").

### Qué queda pendiente — paso exacto para retomar
1. **Bloque 6 — Cron jobs** en Railway (crear servicios cron; propuesta
   simplificada de 2 servicios). Es lo más laborioso; se pausó aquí.
2. Requisitos del piloto real con pacientes (ver ROADMAP): plan de pago Railway,
   WhatsApp Business en Twilio, HABEAS DATA completo, prueba WhatsApp con
   paciente de prueba + check-in.

---

## Sesión 08/07/2026 — Cron jobs en Railway COMPLETADO

**Responsable:** León (Arquitecto IA) guiando; Alejandro ejecutando en Railway;
Claude Code guiando y resolviendo el código.
**Estado:** **Los dos servicios cron funcionan en Railway.** **196 tests OK.**

### Qué se logró
- **`cron-manana`** (`0 11 * * *` UTC = 6:00 AM Bogotá): corre las 4 tareas
  matutinas en orden.
- **`cron-tarde`** (`0 23 * * *` UTC = 6:00 PM Bogotá): corre
  `cerrar_checkins_vencidos`.
- Ambos verificados en vivo (con horario temporal `*/5 * * * *`): logs limpios,
  "0" en todo (aún sin pacientes), sin errores.

### Cómo funciona el cron en Railway (para la próxima vez)
Un cron en Railway es **un servicio aparte** que usa el mismo repo/Dockerfile,
pero con **"Custom Start Command"** propio (corre un comando y termina, no
gunicorn) y un **"Cron Schedule"** (en **UTC**). Cada servicio cron necesita
**sus propias variables de entorno** (se pegan las mismas del web salvo
ALLOWED_HOSTS/superusuario). El horario va en UTC: Bogotá es UTC−5, así que
6 AM = 11:00 UTC y 6 PM = 23:00 UTC. **Mínimo de intervalo: 5 minutos** (no
acepta `* * * * *`; para probar se usa `*/5 * * * *`).

### Problemas y soluciones (lo valioso)
1. **El `&&` en el Custom Start Command solo corría el PRIMER comando.** El
   servicio quedaba "Completed" (exit 0) pero solo ejecutaba
   `desactivar_pacientes_vencidos`; el resto de la cadena `&&` se descartaba.
   **Solución: comando único `cron_matutino`** (nuevo, `signos_sintomas/
   management/commands/cron_matutino.py`) que corre las 4 tareas por dentro con
   `call_command` secuencial — orden garantizado (`desactivar` antes de
   `crear_checkins`), y testeable. 2 tests nuevos. El Custom Start Command del
   cron mañana quedó en `python Registro_Post_Quirurgico/manage.py cron_matutino`.
2. **Cambiar el Custom Start Command no bastaba** — hay que **redesplegar** el
   servicio cron para que el nuevo comando (y el nuevo código) tomen efecto; si
   no, las siguientes corridas seguían usando el comando viejo.
3. **Fecha del resumen en UTC (cosmético).** `cerrar_checkins_vencidos` y
   `enviar_recordatorios` imprimían la fecha del resumen con `ahora.date()`
   (UTC) → el log mostraba 07-09 en la noche de Bogotá. **La lógica ya era
   correcta** (compara instantes con `timezone.now()`, no fechas); solo se
   cambió la línea de resumen a `timezone.localdate()` (norma del proyecto).
   Sin efecto clínico.

### Tests
196 OK (194 previos + 2 de `cron_matutino`). `manage.py check` limpio.

### Commits de la sesión
`0fc869c` (comando `cron_matutino` + tests), `86a0640` (fix cosmético de fecha
en logs de cron), + este cierre `docs`.

### Qué queda pendiente — próxima sesión
**Toda la parte técnica del despliegue y la automatización está COMPLETA.** Lo
siguiente NO es infraestructura, sino **tener algo que mostrarle al médico** y
preparar el piloto:
1. **Landing page de presentación del médico (P-12).** Trabajo de front-end en
   la app `home` — una página pulida para presentar el sistema/médico. Es el
   entregable "para mostrar al médico".
2. **Preparar una demo del dashboard** con datos de ejemplo (ojo: `seed_demo`
   NO corre en producción por el guard A-3; para la demo hay que crear 1-2
   pacientes de ejemplo a mano en el Admin, o correr el flujo real por WhatsApp
   con un número de prueba para generar datos).
3. Resto de requisitos del piloto real (ROADMAP): plan de pago Railway, pasar a
   WhatsApp Business, HABEAS DATA.

---

## Sesión 10/07/2026 — Landing del médico (P-12) + demo del dashboard (seed seguro)

**Sprint:** 5 (Producción) · **Responsable:** León (Arquitecto) + Claude Code ·
**Estado:** ✅ Completado en código (pendiente el deploy a Railway).

### Qué se hizo
- **Landing de presentación del médico (P-12)** — front-end en la app `home`.
  Decisión con el Arquitecto: convertir la página principal `/` en la
  presentación del médico + sistema (no una página aparte). Flujo: primero un
  **boceto en un Artifact** para aprobación visual, luego portado a Django.
  - **Sistema de diseño compartido nuevo** (fin del CSS copiado-pegado entre
    plantillas): `home/static/home/css/site.css` (tokens de color en `:root`,
    temas claro y oscuro, componentes) + `home/static/home/js/pulse.js` (línea
    de pulso del hero, respeta `prefers-reduced-motion`).
  - **Plantilla base** `home/templates/home/base.html` (head, header/nav, footer,
    bloques) que comparten `index.html` (landing) y `contacto.html` (rearmada,
    formulario intacto).
  - Nav conectado: Inicio · El especialista · Cómo funciona · Contacto ·
    **Acceso médico** → `{% url 'admin:index' %}` (antes era link muerto `#`).
  - Identidad visual "calma clínica": verde petróleo + coral, tipografía serif
    con carácter, motivo de telemetría/pulso — deliberadamente lejos del azul
    genérico anterior. Guías aplicadas: skill `artifact-design` + auditoría de la
    skill oficial **Anthropic Frontend Design** y las **Vercel Web Interface
    Guidelines**.
  - Contenido del médico en **marcadores `[entre corchetes]`** + flag
    `MOSTRAR_AVISO_BOCETO` en `home/views.py` (aviso de "boceto" que se apaga con
    los datos reales). Espacios documentados para logo/identidad.
  - **6 smoke tests** en `home/tests.py` (antes vacío).
- **Comando seed seguro para la demo del dashboard**:
  `signos_sintomas/management/commands/seed_demo_produccion.py`. Crea **2
  pacientes de ejemplo** (uno de evolución complicada, otro leve) con registros
  y alertas para mostrar el panel. A diferencia de `seed_demo` (bloqueado en prod
  por A-3), este SÍ puede correr en producción de forma segura: **no crea
  usuarios/contraseñas** (asigna a un médico existente con `--medico` o al primer
  superusuario), exige `--confirmar`, marca los pacientes de forma inconfundible
  (prefijo `DEMO — `, cédula `DEMO-000X`, teléfono ficticio `+57555000000X`) y es
  **reversible** con `--limpiar --confirmar`.

### Decisiones
- Landing = la página `/` (no una página aparte): es lo que ve cualquier
  visitante; menos páginas, más impacto.
- El contenido del médico NO se inventa: placeholders marcados hasta que el
  Arquitecto traiga nombre/especialidad/bio/foto/logo/colores.
- Demo con comando seed seguro (no a mano): reproducible y borrable.

### Problemas y soluciones (lo valioso)
1. **Comentario `{# … #}` multilínea se imprimía como texto** en el header (y el
   `{% static %}` de dentro llegó a resolverse), descuadrando la marca. Causa: en
   Django los comentarios `{# #}` son de **una sola línea**; uno multilínea no se
   comenta. Solución: `{% comment %}…{% endcomment %}`. Verificado.
2. **El runserver servía la plantilla vieja** tras editar (proceso `--noreload`,
   plantilla ya parseada al arranque). Solución: reiniciar el servidor. Recordar:
   con `--noreload` hay que reiniciar para ver cambios de plantilla.
3. **`WARNING` "Alerta ALTA sin médico o sin email"** al correr el seed en local:
   correcto — el superusuario `admin` local no tiene email, así que no se envía la
   notificación. En producción el médico SÍ necesita email configurado.

### Limpieza de datos locales
Se borraron de la base **LOCAL** (no producción) los ejemplos viejos que
confundían: paciente manual "Alejandro Valencia", paciente "Camilo Andrés Rueda
Vargas" (del `seed_demo`) y el usuario `demo_medico` — respetando el orden por las
FK `PROTECT` (Alerta → CheckInProgramado → RegistroDiario → ConversacionWhatsApp
→ Paciente). Quedaron solo los 2 pacientes DEMO nuevos. Producción nunca tuvo
estos (`seed_demo` está bloqueado allá).

### Tests
**202 OK** (196 previos + 6 de `home`). `manage.py check` limpio.
`collectstatic --dry-run` descubre `site.css` y `pulse.js`.

### Commits de la sesión
`feat:` landing + comando seed + tests; `docs:` este cierre (BITACORA + CLAUDE +
ROADMAP).

### Qué queda pendiente — próxima sesión
1. **Deploy a Railway** de estos cambios: `git push` a la rama que observa el
   servicio web (Settings → Source). El Dockerfile corre `collectstatic`+`migrate`
   en el arranque; la landing NO añade migraciones. Luego correr
   `seed_demo_produccion --confirmar` en el Shell del servicio para poblar la demo.
2. **Datos reales del médico**: reemplazar los `[corchetes]`, subir logo/colores y
   poner `MOSTRAR_AVISO_BOCETO = False`.
3. Resto de requisitos del piloto real (plan Railway, WhatsApp Business, HABEAS
   DATA).

### Follow-up (mismo 10/07/2026) — SMTP en Railway + fix del seed

Al **poblar la demo en producción** (desde la terminal del contenedor de
Railway), `seed_demo_produccion --confirmar` se **colgó tras crear al primer
paciente** (María). Traceback: la señal de `Alerta` envía el correo de alerta
ALTA con `send_mail` **síncrono** (SMTP, `fail_silently=False`, `signals.py:72`);
la conexión a `smtp.gmail.com` **se quedó bloqueada en `socket.connect`** desde el
contenedor → nunca llegó al 2º paciente. Causa probable: **Railway bloquea el
puerto SMTP saliente** en el plan actual.

**Fix aplicado (seed):** el comando ahora **silencia el envío de correos**
mientras crea los datos de ejemplo (`EMAIL_BACKEND` → `dummy` en un try/finally
alrededor del loop, restaurándolo al final). Los pacientes y alertas se crean
igual; no se toca SMTP. Verificado en local (crea los 2, 44 alertas). Commit
`fix:`. **Recuperación en Railway:** tras redesplegar, en una terminal NUEVA del
contenedor: `seed_demo_produccion --limpiar --confirmar` (borra a María a medias)
y luego `seed_demo_produccion --confirmar` (crea los 2).

**⚠️ Pendiente CRÍTICO (no resuelto) — correos de alerta ALTA reales:** si el
SMTP saliente está bloqueado en Railway, **las notificaciones ALTA reales al
médico tampoco saldrán**. Es una feature clave del piloto. A decidir: migrar de
Gmail SMTP a una **API HTTP de correo** (Resend/SendGrid/Mailgun) o habilitar
SMTP en Railway; y hacer el envío con **timeout / no bloqueante** (hoy un fallo
de SMTP cuelga el hilo). Anotado también en la lista "Por resolver" de CLAUDE.md.

### Follow-up (mismo 10/07/2026) — Branding + tablero de triage del Admin

El médico entra a `/admin/` (ese es su dashboard). Se mejoró **sin forkear el
admin**, conservando toda la funcionalidad (listas, filtros, búsqueda, gráficas
del Sprint 4, flujo de resolver, scoping por médico):
- **Branding "calma clínica"**: `admin.site.site_header/site_title/index_title`
  + override de `templates/admin/base_site.html` que carga
  `signos_sintomas/static/admin/css/panel_admin.css`. El CSS **sobreescribe las
  variables propias del Admin de Django** (cabecera, enlaces, botones) — aditivo
  y reversible. Se agregó `TEMPLATES['DIRS'] = [BASE_DIR/'templates']` en
  settings para poder sobreescribir plantillas del Admin.
- **Tablero de triage como índice**: `admin.site.index_template =
  'admin/index_panel.html'`, que **extiende el índice real de Django** e inyecta
  el panel con `{{ block.super }}` (así no se pierde la lista de apps ni la barra
  lateral). Datos vía template tag `{% panel_triage %}`
  (`signos_sintomas/templatetags/panel_admin.py`) con **scoping por médico**:
  KPIs (alertas ALTA sin resolver, silencios, check-ins de hoy, pacientes
  activos), lista "necesita atención ahora" (por gravedad, con enlaces reales al
  admin), silencios y tabla de pacientes en seguimiento.
- Flujo usado (igual que la landing): **boceto en Artifact** aprobado por León,
  luego portado al admin real. Se centró el índice en un marco de **1280px**
  (`body.dashboard #content`) a pedido del Arquitecto (se veía pegado a la
  izquierda). Commit `feat` `5e2daee`.

**Aclaración importante que surgió:** el Artifact es una **maqueta estática**
(no interactúa); la funcionalidad real vive en el Django Admin, que se conserva
intacta — solo se suma el tablero y se repinta.

### Follow-up (mismo 10/07/2026) — Agrupación de alertas por problema + contador

**Duda del Arquitecto:** en "Necesita atención" un paciente aparecía muchas
veces. Diagnóstico con datos: NO era un bug del motor — eran alertas distintas
(mismo tipo disparado en varios días + varios tipos); la deduplicación vieja
(Bloque 2B) solo actuaba dentro de un mismo check-in. **Decisión tomada en
sesión (León):** que la alerta se **actualice** en vez de crear una por día, con
un **contador de recurrencia**.

- **Modelo `Alerta`**: campos `veces` (nº de check-ins que detectaron el
  problema) y `fecha_ultima_deteccion` (migración **0018**). `severidad` = la
  **máxima** alcanzada mientras la alerta está abierta.
- **`alert_engine`**: nuevo helper `_registrar_alerta` reemplaza
  `_deduplicar`+`create` en las 8 reglas. Si hay alerta abierta del mismo
  `(paciente, tipo)`, la actualiza (sube `veces`/fecha, y severidad si es mayor;
  nunca baja). Dedup dentro del mismo check-in: dos reglas del mismo tipo cuentan
  **una** detección (marca por `registro_origen`). Si el médico **resuelve** y el
  problema reaparece → alerta **nueva**. `evaluar_registro` devuelve instancias
  únicas (la última que tocó cada alerta, para reflejar la severidad final —
  bug encontrado: la primera instancia quedaba desactualizada en memoria).
  **NINGUNA regla ni umbral clínico cambió.**
- **`signals.py`**: el correo de alerta ALTA se envía solo al **alcanzar ALTA**
  (creación o escalada, marcada con `_escalo_a_alta`), **no** en cada
  recurrencia. Alivia el spam y el tema del SMTP.
- **Admin**: columna "Recurrencia" (badge ×N, resaltado si ≥3). **Tablero**:
  badge ×N junto al nombre.
- **Tests**: se reescribieron los 5 de la deduplicación vieja a la nueva
  semántica + 2 nuevos (correo-solo-al-escalar y resolver→reaparecer-crea-nueva).
  **204 OK.**
- **Demo re-sembrada** en local: **María pasó de 29 alertas → 6** (una por
  problema, con su ×N). Commits `feat` `128c537` y `docs` `3bdd27e`.

### Estado al cierre (10/07/2026)
**204 tests OK**, `check` limpio. Todo pusheado a `sprint-5-produccion` (HEAD
`3bdd27e`). Commits de la sesión: `b335ff2` (feat landing+seed), `cb1f0ba`
(docs), `0c9825f` (fix seed SMTP), `b7bfb90` (docs pendientes), `5e2daee` (feat
panel/branding), `128c537` (feat agrupación), `3bdd27e` (docs), + este cierre.

### Pendiente para la próxima sesión
1. ~~Deploy a Railway del acumulado + re-seed de la demo~~ **✅ HECHO
   (10/07/2026)**: el acumulado de la sesión quedó desplegado en Railway y la
   demo re-sembrada (`--limpiar --confirmar` → `--confirmar`) con las alertas ya
   agrupadas (contador ×N).
2. **[CRÍTICO] Correo de alerta ALTA en producción** — SMTP saliente bloqueado
   en Railway (migrar a API HTTP de correo o habilitar SMTP; ver "Por resolver"
   en CLAUDE.md).
3. **Datos reales del médico** en la landing (`[corchetes]`, logo/colores,
   `MOSTRAR_AVISO_BOCETO=False`).
4. **Cuenta del médico** (staff scoped) + grupo "Médicos" con permisos (posible
   comando `crear_medico`).
5. Requisitos del piloto real (plan Railway, WhatsApp Business, HABEAS DATA).

---

## 18/07/2026 — Loop 1: integridad clínica, permisos y depuración conservadora

Se ejecutó el primer loop posterior a la auditoría profunda, sin cambiar
umbrales ni decisiones clínicas pendientes de validación médica:

- **POD histórico corregido:** `RegistroDiario.fecha_registro` usa ahora
  `default=timezone.now`, acepta fechas explícitas para importación/seed y
  `dia_postoperatorio` se calcula solo al crear. La migración 0019 reparó
  **16 registros locales** afectados por el cálculo anterior con "hoy".
- **Cierre de alertas íntegro:** formulario de alerta completamente de solo
  lectura; el cierre solo ocurre mediante la acción con motivo. Restricciones
  de BD exigen fecha+motivo, `veces >= 1`, motivo válido y detalle para `OTRO`.
  Cierres antiguos sin motivo se conservan como `LEGACY`, sin inventar una
  actuación clínica.
- **Admin con privilegio mínimo:** médicos no pueden modificar ni borrar
  registros, check-ins o alertas, ni borrar pacientes; sí pueden actualizar
  sus pacientes, resolver alertas por la acción y marcar mensajes de contacto
  como revisados. El superusuario conserva mantenimiento excepcional.
- **Rol reproducible:** nuevo comando idempotente `crear_medico`, integrado al
  arranque Docker/Nixpacks. Configura el grupo `Médicos`; opcionalmente crea la
  cuenta desde `DJANGO_MEDICO_*` y rechaza reutilizar un superusuario.
- **Depuración:** `seed_demo` reutiliza el rol real en vez de mantener permisos
  paralelos; ambos seeds crean fechas/POD correctos. Se corrigió la guía de
  Railway (Dockerfile es el despliegue activo) y se eliminó documentación
  duplicada. No se borraron seeds, fallback Nixpacks ni archivos no rastreados.

**Verificación:** 217 tests OK; `check --deploy` sin issues; migraciones al día;
`git diff --check` limpio. La migración 0019 quedó aplicada en la base local.

**Pendiente inmediato:** desplegar/revisar el Loop 1 en Railway, provisionar la
cuenta real del médico y continuar con el Loop 2 de confiabilidad del webhook y
motor de alertas.

---

## 18/07/2026 — Loop 2: webhook durable y entrega recuperable de alertas

Se cerró el segundo loop sin modificar reglas, umbrales ni mensajes clínicos:

- **Idempotencia durable de Twilio:** `MessageSid` deja de depender de una
  cache de 5 minutos y se registra en PostgreSQL. La fila técnica no guarda
  teléfono ni `Body`; solo SID, token idempotente, estado, intentos y fechas.
  SID ausente/malformado devuelve 400; duplicado completado devuelve TwiML
  vacío; un request que ya está en proceso devuelve 503 para permitir retry.
- **Atomicidad extremo a extremo:** el avance de la conversación y el estado
  COMPLETADO del recibo se confirman en la misma transacción. Una caída antes
  del commit revierte el avance del bot y deja el SID reintentable, evitando
  interpretar la misma respuesta en dos preguntas distintas.
- **Motor recuperable:** cada `RegistroDiario` conserva estado de evaluación,
  intentos, fecha y solo la clase del último error. El nuevo comando
  `reintentar_evaluaciones_alertas` procesa PENDIENTE/ERROR con locks y sigue
  con los demás si uno vuelve a fallar. Se integró al cron matutino y se
  documentó un cron frecuente cada 5 minutos.
- **Concurrencia de alertas:** restricción parcial de BD para una sola alerta
  abierta por `(paciente, tipo)`. El engine captura la colisión de dos workers
  y actualiza la alerta ganadora. La migración 0020 consolida posibles
  duplicados abiertos conservando contador, severidad máxima y trazabilidad.
- **Bot y scheduler coordinados:** `ConversacionWhatsApp.checkin_actual` fija
  el evento desde que inicia el cuestionario. El cron bloquea cada check-in y
  omite conversaciones con actividad reciente; una conversación abandonada
  fuera de las mismas 10 horas de gracia sí puede cerrarse. Las alertas SILENCIO
  repetidas también se agrupan sin violar la nueva unicidad.
- **Operación/Admin:** el estado de evaluación es visible en registros. Los
  recibos Twilio son solo lectura y visibles exclusivamente a superusuarios.
  Seeds y guías de Railway quedaron sincronizados; Redis sigue siendo
  obligatorio para rate limiting, no para idempotencia.

**Problema encontrado y resuelto:** la primera suite completa encontró una
prueba antigua que fabricaba una conversación a mitad de flujo sin check-in.
El bot la rechazó correctamente con `MSG_SIN_CHECKIN`; se corrigió el fixture
para representar un estado posible del sistema y la suite volvió a verde.

**Verificación:** 234 tests OK en PostgreSQL, incluidas carreras reales de dos
workers para alertas y bot-vs-cron; `manage.py check`, `check --deploy`,
`makemigrations --check` y `git diff --check` limpios.

**Punto de restauración remoto (18/07/2026):** los commits del Loop 1
(`49596e8`) y Loop 2 (`442ccc2`) se publicaron en `sprint-5-produccion`. La
rama local y `origin/sprint-5-produccion` quedaron sincronizadas exactamente en
`442ccc2`; el formato de consentimiento local sin seguimiento no se incluyó.
No se modificó código ni se repitió la suite en este cierre documental: se
conserva como evidencia la verificación de **234 tests OK** del Loop 2.

**Pendiente inmediato al retomar:** iniciar el **Loop 3 de experiencia
médica** con una auditoría visual y funcional usando una cuenta médica de
privilegio mínimo. Primero se validará el comportamiento actual del tablero,
las alertas pendientes, el historial y los mensajes de contacto; solo después
se implementarán cambios aprobados. El despliegue de las migraciones 0019-0021,
el cron frecuente y el smoke test real quedan agrupados en el Loop 4 de
producción.

---

## 19/07/2026 — Loop 3: experiencia médica y trazabilidad de detecciones

Se cerró el tercer loop con auditoría funcional usando la cuenta médica demo,
sin modificar reglas ni umbrales clínicos:

- **Tablero de triage:** contraste de marca corregido, ancho ampliado y diseño
  responsivo. Muestra todas las alertas sin resolver, aunque sean de días
  anteriores, y las ordena por severidad, recurrencia y última detección.
  Incluye fecha/hora exacta, tiempo relativo y acceso a la alerta/paciente.
- **Ventana coherente de seguimiento:** historial y gráficas usan 3/7/10 días
  con inclusión exacta. El historial del Admin diferencia "Seguimiento
  activado" y "Seguimiento desactivado". Se corrigió también el filtro oculto
  de fecha de mensajes de "Cualquier fecha" a "Todas las fechas".
- **Resolución y demos:** se verificó que resolver una alerta exige motivo y
  detalle para "Otro". Se quitó el encabezado duplicado; ambos seeds crean
  cédula y consentimiento válidos sin relajar integridad.
- **Mensajes de contacto aislados:** `MensajeContacto.medico_destinatario`
  asigna los nuevos mensajes a la cuenta staff indicada por
  `MEDICO_CONTACTO_USERNAME`. Cada médico solo ve/modifica los propios; los
  mensajes existentes o mal configurados quedan sin asignar y son visibles
  exclusivamente para superusuario. El tablero muestra nombre, teléfono y
  fecha de los pendientes propios, pero no el cuerpo del mensaje.
- **Detalle real de ×N:** el nuevo modelo `DeteccionAlerta` conserva para cada
  detección futura su registro o check-in, fecha, severidad y mensaje. Las
  restricciones de BD exigen exactamente una fuente e impiden duplicarla por
  alerta. El motor usa esa evidencia para hacer idempotentes tanto las alertas
  clínicas como SILENCIO y mantiene la severidad máxima.
- **Histórico conservador:** no se fabricó ningún evento anterior. En alertas
  existentes, `veces` sigue siendo la fuente del contador y el Admin explica
  cuántas detecciones previas no tienen desglose. Solo lo ocurrido desde esta
  versión crea filas hijas.

**Migraciones locales aplicadas:** `home.0002` y `signos_sintomas.0022`, ambas
aditivas y sin backfill sensible.

**Verificación:** **252 tests OK** en PostgreSQL; `manage.py check`,
`check --deploy --settings=Registro_Post_Quirurgico.settings_production`,
`makemigrations --check --dry-run` y `git diff --check` limpios. Revisión visual
en escritorio y 390 px sin desbordamiento, con consola del navegador limpia.

**Commit de código:** `5ad1b71` (`feat: cerrar experiencia medica del loop 3`).
El archivo local `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` permaneció fuera de
Git y no fue modificado.

**Pendiente inmediato:** iniciar el **Loop 4 de producción**. Primero cerrar
actualización/fijación de dependencias, IP real tras proxy, correo ALTA
desacoplado con timeout o API HTTP, CSP y Chart.js local. Luego configurar la
cuenta real y `MEDICO_CONTACTO_USERNAME`, desplegar migraciones 0019-0022 y
`home.0002`, crear el cron de reintento cada 5 minutos y ejecutar smoke tests
reales en Railway.

---

## 19/07/2026 — Seguimiento Loop 3: lenguaje y datos demo verificables

Se atendieron las dudas surgidas durante la revisión del Admin sin cambiar
reglas, umbrales ni decisiones clínicas:

- **Lenguaje de producto:** se eliminó la referencia interna "desde Loop 3".
  El inline ahora se llama "Detecciones de la alerta" y cada objeto muestra un
  identificador compacto con su registro o check-in de origen.
- **Ordenamiento comprobado:** las columnas del Admin ordenan en el servidor,
  por eso recargan la página. Los números pequeños son la prioridad de cada
  criterio. La verificación visual confirmó el cambio de fechas ascendentes a
  descendentes y el filtro quedó como "Todas las fechas".
- **Demos reproducibles:** `seed_demo --borrar` ya respeta las relaciones
  clínicas protegidas y `seed_demo --limpiar` permite retirar el demo local sin
  recrearlo. La limpieza del seed de producción ahora es atómica y reporta
  conteos por modelo sin sumar en cascada las detecciones hijas.
- **Prueba funcional local:** se retiraron los demos previos y se crearon dos
  pacientes ficticios nuevos para `demo_medico`. El panel mostró 10 alertas
  abiertas y el detalle de una alerta ×7 mostró sus siete detecciones. No se
  ejecutó ningún comando contra Railway.

**Migración local aplicada:** `signos_sintomas.0023`, exclusivamente para el
nombre plural de `DeteccionAlerta`.

**Verificación:** **256 tests OK**; `manage.py check`, `check --deploy`,
`makemigrations --check --dry-run` y `git diff --check` limpios. Revisión visual
del filtro, ordenamiento y detalle de detecciones sin errores de consola.

**Pendiente inmediato:** conservar Railway sin cambios hasta el Loop 4. En ese
loop se desplegarán juntos los cambios acumulados, se configurará la cuenta
médica real y se decidirá conscientemente si se cargan o limpian demos remotos.

---

## 19/07/2026 — Despliegue Loops 1-3 y renovación de demos en Railway

Con autorización explícita para borrar los demos remotos se sincronizó el
entorno `production` del proyecto Railway `zooming-trust`:

- **Despliegue confirmado:** GitHub había activado automáticamente el commit
  `de06ff8` en el servicio web y los dos cron. Los tres quedaron en `SUCCESS`;
  el web usa Dockerfile, responde HTTPS 200 y tiene aplicadas las migraciones
  `signos_sintomas.0019-0023` y `home.0002`.
- **Demos renovados:** se eliminaron únicamente `DEMO-0001` y `DEMO-0002` con
  18 registros, 14 alertas y 22 check-ins anteriores. Se recrearon dentro del
  contenedor Railway: 2 pacientes activos asignados temporalmente a `SeñorAL`,
  18 registros, 10 alertas abiertas agrupadas, 18 check-ins y 36 detecciones.
  El contador máximo verificado es ×8.
- **Hallazgo de configuración resuelto:** el `check --deploy` dentro de Railway
  detectó `security.W009` porque `SECRET_KEY` era débil. Se generó un valor
  criptográficamente aleatorio, se transmitió solo por stdin y se aplicó igual
  al web y ambos cron. Tras los tres redespliegues, `check --deploy` quedó en
  cero issues. La rotación invalida sesiones anteriores del Admin.
- **Acceso operativo:** se instaló temporalmente Railway CLI 5.27 vía `npx`, se
  autenticó la cuenta y se enlazó exclusivamente el servicio web de production.
  Se creó y registró una clave SSH dedicada local para ejecutar dentro de la
  red privada de Railway; la primera huella se fijó con `accept-new`, no se
  desactivó la verificación de host.

**Problemas encontrados y resueltos:** Railway CLI no estaba instalado. Luego,
`railway run` intentó usar `postgres.railway.internal` desde Windows y falló por
DNS. El proxy público permitió limpiar, pero cortó dos intentos de recreación;
ambos quedaron completamente revertidos por las transacciones (0 demos antes
del intento final). El SSH oficial se bloqueaba por la confirmación invisible
de la primera huella; tras fijarla, el seed interno terminó en 4 segundos.

**Verificación final:** 2/2 demos activos, 10 alertas abiertas, 36 detecciones;
web + cron en `SUCCESS`; HTTPS 200; sin errores de aplicación recientes y
`manage.py check --deploy` remoto sin issues.

**Pendiente inmediato:** crear la cuenta staff real de privilegio mínimo y
configurar `MEDICO_CONTACTO_USERNAME`; crear el cron de reintentos cada 5
minutos y continuar el Loop 4 (dependencias, IP real, correo ALTA, CSP y
Chart.js local). Los demos siguen asignados a `SeñorAL` hasta entonces.

---

## 19/07/2026 — Loop 4 desplegado y decisión temporal de cron Railway

Se cerró el bloque de hardening de producción con tres commits de código:

- `fc21e43`: Django 6.0.7 y dependencias directas fijadas; CSP; Chart.js 4.5.1
  local; scripts del Admin extraídos del HTML; outbox transaccional
  `NotificacionAlerta` (migración 0024), correo genérico sin PHI/PII, timeout y
  reintentos con espera creciente fuera del webhook.
- `b48d603`: `cron_operativo` para cierre de check-ins y procesamiento de la
  bandeja; `cron_matutino` conserva un respaldo diario.
- `7cb4380`: se agregó al cron operativo el reintento del motor de alertas, que
  no debe esperar hasta la mañana siguiente.

**Verificación local:** suite final completa, **267 tests OK**, incluidas las
pruebas de `cron_operativo` y `cron_matutino`. `check --deploy`,
`makemigrations --check --dry-run` y `git diff --check` limpios.

**Despliegue Railway:** web, `cron-manana` y `cron-tarde` quedaron en `SUCCESS`
sobre `7cb4380`. `check --deploy` remoto sin issues, Django 6.0.7, HTTPS 200,
CSP activo, Chart.js local 200, `/admin/` 404 y la ruta privada del Admin 302 al
login. El cron frecuente ejecutó en vivo a las 02:00 UTC las tres tareas en
orden: cierre, reintento del motor y notificaciones. La outbox estaba vacía y
los 2 pacientes demo seguían activos; el seed demo no genera correo.

**Decisión temporal por límite del plan:** crear un servicio adicional
`cron-notificaciones` falló con `Free plan resource provision limit exceeded`.
Con autorización del Arquitecto, `cron-tarde` se reutilizó temporalmente para
ejecutar `cron_operativo` cada 5 minutos. **Deuda documentada:** cuando se
mejore el plan Railway, crear un servicio `cron-operativo` independiente y
restaurar `cron-tarde` a `cerrar_checkins_vencidos` a las 23:00 UTC como
respaldo idempotente. Esta reutilización no debe quedar como arquitectura final.

**Pendientes que bloquean un piloto real, no las pruebas con demos:**

1. La conexión acotada a `smtp.gmail.com:587` desde Railway volvió a fallar.
   La outbox evita perder alertas y ya no bloquea WhatsApp, pero falta una API
   HTTPS de correo (o salida SMTP compatible) y una entrega real verificada.
2. `medico_piloto` existe como staff no-superuser con privilegio mínimo, pero
   no tiene email configurado. Debe completarse y comprobarse antes de asignar
   pacientes reales.
3. Se conserva `REMOTE_ADDR` para no confiar en un `X-Forwarded-For`
   spoofeable. Falta definir una fuente de IP verificable en Railway; el rate
   limit actual puede agrupar clientes detrás del proxy.

---

## 21/07/2026 — Loop 4: IP real y canal HTTPS preparados

**Estado:** código y despliegue validados; pendiente una credencial externa y
la recepción de un correo real para declarar cerrado el Loop 4.

- El Arquitecto ingresó con `medico_piloto`. En producción se verificó que la
  cuenta está activa, es staff no-superuser y solo tiene los dos demos
  asignados. Se configuró `seguimientolionalejo@gmail.com` como destinatario.
- Railway documenta `X-Real-IP` como IP remota y agrega `X-Railway-Edge` a cada
  solicitud. El formulario de contacto usa esa IP solo con
  `TRUST_RAILWAY_PROXY=True`, edge de formato válido e IP parseable; conserva
  `REMOTE_ADDR` como fallback y nunca usa `X-Forwarded-For`.
- Se integró Resend por HTTPS al outbox. Cada alerta usa una clave idempotente,
  exige ID de respuesta para confirmar entrega y conserva pendiente/reintento
  ante timeout, error, proveedor inválido o credencial ausente. El payload
  continúa sin nombre, teléfono, cédula, síntomas ni mensaje clínico.
- `requests==2.32.5` quedó como dependencia directa de runtime. La configuración
  de producción solo exige secretos SMTP cuando el proveedor es `django`.

**Verificación:** 273 pruebas completas pasaron y, tras el último caso de
header malformado, las 17 pruebas enfocadas también pasaron (**274 casos
vigentes**). `check --deploy` en modo Resend: 0 issues. El entorno de desarrollo
mantiene un conflicto no-runtime entre el `httpx` antiguo de `googletrans` y
Jupyter/Hugging Face; Railway instala el archivo runtime separado y no está
afectado. Commit `5d6b379` desplegado con web y ambos cron en `SUCCESS`.
Smoke interno: inicio 200, `/admin/` 404, Admin privado 302 al login, CSP/HSTS/
nosniff presentes y confianza Railway activa.

**Cierre funcional del Loop 4:** se cargaron en Railway
`EMAIL_DELIVERY_PROVIDER=resend`, la API key sellada y el remitente de prueba.
El contenedor confirmó proveedor activo, destinatario correcto, cero pendientes
y cero pacientes no-demo. Se creó exactamente una notificación sobre la alerta
ALTA demo #90: Resend devolvió confirmación, la outbox quedó `ENVIADA` en un
intento y sin error. El Arquitecto encontró el correo en spam y verificó que el
cuerpo solo contiene severidad general, referencia opaca y enlace al panel.

El formato SMTP antiguo con nombre del paciente, tipo y detalle clínico no se
restaura: fue sustituido deliberadamente durante el hardening para mantener PHI/
PII dentro del panel autenticado. La llegada a spam se atribuye al remitente de
pruebas `onboarding@resend.dev`; se registra como requisito del piloto verificar
un dominio propio con SPF/DKIM/DMARC. **Loop 4 cerrado. Siguiente: Loop 5 de
validación (concurrencia, permisos, fallo del motor, carga y WhatsApp completo).**

---

## 21/07/2026 — Loop 5 de validación cerrado

**Estado:** validación automatizada, carga y flujo real por WhatsApp completados.

- Se auditó la cobertura existente antes de agregar pruebas. Permisos ya cubría
  aislamiento entre médicos, inmutabilidad y restricciones de borrado; no se
  duplicaron esos casos.
- Se agregaron seis validaciones: firma Twilio válida; flujo completo por el
  endpoint; dos requests concurrentes con el mismo `MessageSid`; rollback de
  alerta/outbox parcial al fallar el motor; dos workers sobre una notificación;
  y carga concurrente de 50 pacientes.
- La prueba de carga recorrió las 10 preguntas para cada paciente: 550 webhooks,
  50 registros, 50 conversaciones y 50 check-ins completados en 5,03 segundos.
  Todas las respuestas fueron 200, ninguna superó 15 segundos y no quedaron
  recepciones incompletas.
- Suite completa: **280 tests OK** en 215,6 segundos. Commit de pruebas
  `3c86487` publicado en `sprint-5-produccion`.

**Prueba real Sandbox:** el Arquitecto creó `PRUEBA-WA-L5-001` desde la cuenta
`medico_piloto`, activó el Sandbox y completó el cuestionario con valores
normales. Railway confirmó un registro, evaluación `COMPLETADA`, conversación
cerrada y turno TARDE vinculado, sin alerta clínica ni correo. Como los
check-ins se crearon manualmente a las 18:00, el cron alcanzó a cerrar el turno
MAÑANA con una alerta operativa `SILENCIO/BAJA`; el bot eligió correctamente el
turno TARDE pendiente. Las 20 recepciones técnicas recientes estaban completas
y con un solo intento.

**Limpieza:** transacción confirmada sobre la cédula ficticia exacta: 1 paciente,
1 registro, 2 check-ins, 1 conversación, 1 alerta de silencio, 1 detección y 2
logs Admin eliminados. Cero pacientes `PRUEBA-WA-*` restantes; demos y demás
datos intactos.

**Siguiente paso:** Loop 6 de cierre: prueba manual MEDIA/ALTA, depuración final
del roadmap, smoke de la cuenta médica, PR hacia `Desarrollo`, revisión y merge.

---

## 21/07/2026 — Loop 6: cierre técnico y compuerta de auditoría

**Estado:** validación técnica completada. El PR y el merge permanecen detenidos
hasta recibir una auditoría independiente favorable.

### Pruebas manuales en Railway y Sandbox

- Se creó desde `medico_piloto` el paciente ficticio exacto
  `PRUEBA LOOP 6 TONOS` (`9900000006`) y se generaron check-ins controlados.
- Flujo MEDIA: respuestas normales salvo drenaje turbio. El bot entregó el tono
  MEDIA esperado y Railway confirmó check-in 76, registro 67, evaluación
  completada y alerta `FUGA_ANASTOMOTICA/MEDIA`.
- Al responder `si` en la última pregunta de un segundo flujo, Twilio recibió
  200 pero el bot quedó en `ESPERANDO_TOLERANCIA_LIQUIDOS`. El parser sí aceptaba
  `si`: el contador Redis había llegado a 22 frente al límite de 20 mensajes por
  hora por ejecutar dos cuestionarios completos. El recibo SID se cerraba y la
  respuesta TwiML quedaba vacía.
- Se corrigió el comportamiento en `c12bfe5`: una solicitud Twilio válida que
  supera el límite recibe ahora un mensaje neutro, sin datos clínicos, en vez de
  silencio. Pasaron 15 pruebas enfocadas y luego la suite completa.
- Tras limpiar únicamente la clave Redis del paciente ficticio, se completó el
  flujo MEDIA. Para ALTA se creó el check-in 77 y se respondió temperatura
  38,5 °C; el bot mostró el cierre ALTA esperado sin revelar alerta ni valor.
  Railway confirmó registro 68, evaluación completada y `SEPSIS/ALTA`.
- `medico_piloto` visualizó el resultado con aislamiento correcto en el panel.

### Entrega de correo

- La notificación ALTA quedó primero PENDIENTE tras almacenar solamente la clase
  de error `OSError`, política deliberada para no persistir contenido sensible.
- El cron de las 19:25 se ejecutó antes de la elegibilidad del reintento
  (19:25:31); por ello el siguiente intento automático habría ocurrido a las
  19:30. Se ejecutó una vez el mismo comando desplegado
  `procesar_notificaciones_email`: tomó una candidata y la envió, sin pendientes
  ni duplicados. El Arquitecto confirmó recepción en spam.
- El correo mantuvo el formato genérico: referencia opaca y enlace autenticado,
  sin nombre, teléfono, cédula, signos, síntomas ni detalle clínico.

### Auditoría técnica final

- Suite completa con Requests 2.33.0: **280/280 OK** en 126,46 segundos.
- `makemigrations --check --dry-run`, `manage.py check` y `check --deploy` con
  configuración de producción temporal: sin issues.
- `pip-audit` detectó inicialmente PYSEC-2026-2275 en Requests 2.32.5. El
  proyecto no invoca `requests.utils.extract_zipped_paths`, pero se actualizaron
  `requirements-runtime.txt` y `requirements.txt` a 2.33.0. La auditoría quedó
  sin vulnerabilidades conocidas (`0d12d88`).
- El escaneo del árbol y del historial no encontró claves Resend/Twilio,
  credenciales ni llaves privadas reales. `.env` no está rastreado. Las
  migraciones `RunPython` 0019 y 0020 no contienen pacientes ni secretos.
- Smoke de `0d12d88`: `/` 200 con CSP, `/admin/` 404, ruta privada 302 al login
  y Chart.js local 200 (208.522 bytes). Web de Railway en `SUCCESS`.
- `pip check` del Python global conserva conflictos ajenos entre herramientas de
  notebooks y `googletrans`/`httpx`; no corresponden al runtime reproducible de
  Railway, cuyo Dockerfile instala solo `requirements-runtime.txt`.

### Limpieza y estado

- Se eliminaron transaccionalmente solo los datos del paciente ficticio: 1
  notificación, 3 detecciones, 2 alertas, 1 conversación, 2 check-ins, 2
  registros y 1 log Admin; quedaron cero pacientes de esta prueba. También se
  limpió exclusivamente su clave de rate limit.
- Rama `sprint-5-produccion` sincronizada con origin en `0d12d88` antes de esta
  actualización documental. El único archivo raíz no rastreado es el formato de
  consentimiento recibido externamente y permanece intacto.
- Sigue pendiente para un piloto real: WhatsApp Business y envío saliente real
  (`enviar_recordatorios` continúa stub), dominio propio de Resend, plan Railway
  con cron separado, Habeas Data firmado y datos definitivos del médico.

**Compuerta de cierre:** se creó `docs/proceso/auditorias/2026-07-22_instruccion_loops_1_6.md` para que
Claude Code contraste todo el árbol, los seis loops, las 280 pruebas y los
controles de producción. No se abrirá PR ni se hará merge hasta clasificar sus
hallazgos, resolver los bloqueantes y repetir las pruebas afectadas.

---

## 21/07/2026 — Barrido documental integral y pausa segura

**Objetivo:** detener el proyecto temporalmente sin perder contexto ni dejar
instrucciones activas contradictorias antes de la auditoría con Claude Code.

### Alcance revisado

- Memoria y planificación: `CLAUDE.md`, roadmap, bitácora e instrucción de
  auditoría pre-merge.
- Operación: despliegue Railway, cron, transferencia de cuentas y
  `.env.example`, contrastados contra Dockerfile, settings, URLs y management
  commands actuales.
- Clínica/referencia: `knowledge_base.md`, consentimiento rastreado, auditoría de
  Sprint 3 y toda la carpeta `docs/auditoria_literatura/`.
- Licencia de Chart.js identificada como archivo de proveedor, sin edición.

### Correcciones documentales

- Se creó `docs/README.md` como índice canónico: distingue fuentes vigentes,
  bitácora acumulativa, auditorías históricas, placeholder RAG y documento legal.
- El roadmap y `CLAUDE.md` ahora reflejan dos check-ins diarios ligados al turno,
  cuestionario de hasta 10 preguntas, 280 tests, migraciones hasta 0024, seis
  tareas matutinas, ruta Admin privada, RAG en Sprint 6 y tonos MEDIA/ALTA ya
  probados.
- `docs/transferencia_cuentas.md` dejó de describir Railway/Redis como pendientes,
  cambió las gráficas de 7/14/30 a 3/7/10 y registró Resend, WhatsApp Business y
  los requisitos reales de transferencia.
- `docs/railway_deploy.md` quedó alineado con el Dockerfile: dependencias en el
  build; `collectstatic`, migraciones, bootstrap y Gunicorn al arrancar. Se
  completaron variables faltantes y se retiró la prueba MEDIA/ALTA del backlog.
- `docs/cron_setup.md` distingue reintentos internos de monitoreo externo. En
  Railway no existe el `MAILTO` del ejemplo de crontab: sigue pendiente una
  alarma independiente si el scheduler deja de ejecutar. También queda explícito
  que `cron_matutino` corre hoy a las 6:00 AM e incluye el recordatorio stub; al
  implementar Twilio saliente se debe decidir el horario antes de activarlo.
- `.env.example` agregó `CSRF_TRUSTED_ORIGINS`, `ADMIN_URL`, `REDIS_URL` y
  `RESET_AXES`, todos con valores de ejemplo no secretos y advertencia de no
  copiar la plantilla completa a producción.
- La auditoría de Sprint 3 y los análisis de literatura recibieron un aviso de
  documento histórico. Sus observaciones originales se conservaron intactas.
- Se corrigieron únicamente dos comentarios de código: `collectstatic` corre al
  arrancar el contenedor y la variable real del Admin es `ADMIN_URL`. No cambió
  comportamiento ejecutable.

### Integridad y estado de pausa

- La copia raíz no rastreada de `FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` y la
  versión canónica en `docs/` tienen el mismo SHA-256. La copia raíz permaneció
  intacta y fuera del commit.
- No se reejecutó la suite porque este barrido solo modifica documentación y dos
  comentarios. `manage.py check` se repitió y quedó sin incidencias; también se
  validaron 26 archivos Markdown sin enlaces locales rotos. La última evidencia
  funcional sigue siendo **280/280 tests OK**, `check --deploy` limpio y
  `pip-audit` sin vulnerabilidades conocidas.
- No se abrió PR ni se hizo merge. El siguiente paso obligatorio es entregar a
  Claude Code `docs/proceso/auditorias/2026-07-22_instruccion_loops_1_6.md`, recibir su informe completo y
  volver a Codex para resolver conjuntamente cualquier hallazgo bloqueante.

---

## 22/07/2026 — Auditoría independiente pre-merge y Loop A de corrección

**Estado:** auditoría entregada, 14 hallazgos. El único bloqueante del PR quedó
corregido y verificado. Loops B y C pendientes.

### Auditoría independiente (Claude Code)

Se ejecutó `docs/proceso/auditorias/2026-07-22_instruccion_loops_1_6.md` sobre `fbf62a8`, sin editar
código. **Veredicto: BLOQUEADO PARA PR A DESARROLLO.**

Las cuatro cifras que reportaba Codex se confirmaron reproduciéndolas: 280 tests
OK, `check --deploy` sin issues, `pip-audit` sin vulnerabilidades y migraciones
al día. El **aislamiento por médico resistió** un intento activo de romperlo con
15 comprobaciones (acceso por URL a paciente, registro, alerta, check-in e
historial de otro médico; listados; búsqueda; tablero; acción de resolver).
Todos los accesos redirigen sin exponer dato alguno. La única fuga es menor: el
filtro lateral de pacientes expone los nombres de usuario de los demás médicos.

**El hallazgo bloqueante (ALTO):** la escalera de severidad de las alertas
SILENCIO **nunca escalaba en producción**. `_calcular_racha` recorría todos los
check-ins del paciente sin excluir los posteriores al que cerraba, y trataba un
`PENDIENTE` igual que un `COMPLETADO`: rompía la racha. Como el scheduler
siempre deja turnos pendientes, la racha valía 1 en cada cierre. Un paciente con
tres días completos sin responder (6 turnos) producía `SILENCIO / BAJA —
Monitorear`, y en el tablero de triage las BAJA se ordenan de últimas.

Se reprodujo contra base de datos de prueba simulando la secuencia exacta de
`cron_matutino`, con un control que aisló la causa: mismo historial sin turno
posterior pendiente daba racha 5 y severidad ALTA.

**Por qué sobrevivió a 280 pruebas en verde:** los tests de racha prefijaban los
turnos previos a mano y dejaban un único check-in pendiente — un estado que el
scheduler real nunca produce. La prueba estaba escrita mirando el código, no el
requisito.

### Decisiones tomadas antes de escribir código (D1-D7)

Se documentaron en `docs/decisiones_correccion_auditoria.md`, una ficha por
decisión con su razonamiento, antes de tocar una línea. Las clínicas:

- **D1 — escalera de SILENCIO.** Cuenta check-ins, no días calendario: la
  agrupación por día existe para de-duplicar mediciones y aquí no hay
  mediciones que de-duplicar. Escalera 1 → BAJA, 2-3 → MEDIA, 4+ → ALTA; el
  umbral ALTA de 4 equivale a dos días calendario completos sin señal. Un
  `PENDIENTE` anterior se ignora sin romper la racha, para que una caída del
  cron no degrade una alerta clínica. Base del modelo: SILENCIO es ausencia de
  datos, no un síntoma — no genera mensaje al paciente, así que el costo de un
  falso positivo es una llamada telefónica y conviene errar hacia la
  sensibilidad.
- **D4 — umbral de fiebre.** `RESP_FIEBRE` decía "si supera 38 °C" mientras el
  motor alerta desde 37.9: un paciente con 37.9 recibía el mensaje de que estaba
  bien mientras el sistema mandaba un correo urgente al médico. De fondo violaba
  la regla no negociable del bot (el paciente nunca ve umbrales). Se retiró el
  número en vez de corregirlo. **Redacción final pendiente de validación
  médica.**
- **D5 — signos concurrentes.** El detalle de una alerta conservaba solo el
  signo más grave. Solo afecta a `ILEO_PARALITICO`, único tipo con reglas que
  pueden coincidir. Ahora acumula todos: distensión sola puede ser muchas cosas,
  distensión + ausencia de tránsito + vómito es el cuadro de íleo.

Las operativas (D2 rate limit y caída de Redis, D3 quién resuelve cada alerta,
D6 límite de reintentos, D7 registros de la migración 0020) quedaron decididas y
documentadas; se implementan en los Loops B y C.

### Loop A — cinco commits

- `a6afb30` **test en rojo**: cuatro casos que fallan contra el código anterior,
  ejecutando `crear_checkins_diarios` + `cerrar_checkins_vencidos` en el orden
  real de `cron_matutino`.
- `20ee837` corrección de la racha (D1).
- `0ac7021` retiro del umbral de fiebre (D4) + test que vigila que ninguna de
  las cuatro respuestas exponga una cifra clínica, sea cual sea la redacción
  que apruebe el médico.
- `f4892fc` acumulación de signos concurrentes (D5), idempotente ante los
  reintentos del motor.
- `5a5b477` sincronización de CLAUDE.md, ROADMAP y `knowledge_base.md`.

### Problemas encontrados durante el propio Loop A

Dos defectos **en las pruebas recién escritas**, no en el código, detectados
gracias a ejecutarlas en rojo antes del arreglo:

1. Un test dependía de la **hora del día** en que corriera la suite: a las 18:56
   el turno de las 7:00 de hoy ya estaba vencido y el cierre se lo llevaba,
   dando `5 != 4`. En producción `cron_matutino` corre a las 6:00 AM, cuando
   ambos turnos del día siguen en el futuro. Se normalizó la hora de los turnos
   del día en el helper y se dejó el porqué en su docstring.
2. Un test **pasaba en verde contra el código roto**: el escenario tenía dos
   turnos vencidos, el primero calculaba mal la racha pero el segundo la
   calculaba bien y, como la severidad es la máxima, el resultado final era el
   correcto por el camino equivocado. Se reescribió para llamar a
   `_calcular_racha` directamente.

Es el mismo patrón que dejó vivo el hallazgo 1 durante seis loops. La lección no
es que alguien se equivocara: **un test en verde no prueba nada si no se
verifica por qué está verde.**

### Verificación

- Suite completa: **286 tests OK** (280 originales + 6 nuevos). El commit `5a5b477`
  solo tocó archivos `.md`, así que no se repitió la suite tras él.
- `manage.py check`, `makemigrations --check --dry-run` y `check --deploy` con
  configuración de producción temporal: los tres sin issues.
- `git diff --check` limpio.
- **Verificación del Arquitecto:** León ejecutó él mismo un script contra base de
  datos desechable que muestra la escalera subiendo BAJA → MEDIA → MEDIA → ALTA
  con la racha 1 → 2 → 3 → 4, el reinicio al responder, el detalle de íleo con
  ambos signos sin duplicarse tras tres reevaluaciones, y el mensaje de fiebre
  sin cifras.

### Aclaración registrada durante la verificación

La racha se reinicia porque **el paciente responde** (un `COMPLETADO` corta el
conteo), no porque el médico resuelva la alerta. Resolver solo permite que nazca
una alerta nueva, ya que la base admite una sola abierta por (paciente, tipo).
Consecuencia visible en el panel: si el médico resuelve y el paciente **sigue**
sin responder, la siguiente alerta aparece como **×1 pero con severidad ALTA**,
porque la racha real venía alta. Es correcto y deliberado — si resolver
reiniciara la racha, bastaría con cerrar alertas para que el sistema dejara de
escalar.

### Estado de la documentación

- `docs/decisiones_correccion_auditoria.md`: nuevo. Fichas D1-D7 con su
  razonamiento, método de trabajo, estado de avance por commit y **prompt de
  reanudación** para retomar en otra sesión sin depender de la conversación.
- `knowledge_base.md`: nueva sección "Consulta pendiente al médico" con tres
  preguntas concretas (~10 minutos) listas para llevarle al médico.
- CLAUDE.md: la escalera de SILENCIO quedó documentada en tabla por primera vez
  (antes solo vivía en el docstring del command).

**Pendiente inmediato:** **Loop B** — degradación del rate limit sin bloquear al
paciente y límite de 20 → 60 mensajes/hora (D2), endpoint `/salud/` para
monitoreo externo, `resuelta_por` (D3, migración 0025), límite de reintentos y
estado `FALLIDA` (D6), y acotar el bloqueo de filas durante el envío de correo
(hallazgo 2). Se arranca en sesión nueva con el prompt de reanudación del
documento de decisiones.

---

## Sprint 5 — Corrección post-auditoría, Loop B (trazabilidad y operación)
**Fecha:** 23/07/2026
**Responsable:** León (Arquitecto IA) + Claude Code (Opus)
**Estado:** LOOP B CERRADO ✅ (pendiente de verificación de León y push)

### Verificación de estado al arrancar (manda Git)

Antes de tocar nada se contrastó el documento de decisiones contra Git y la
suite. Coincidían (Loop A cerrado, D1-D10 documentadas), con **un matiz que se
rectificó con evidencia**: la primera corrida de la suite falló 1 test a las
00:08. En vez de etiquetarlo como "flake" y seguir, se **probó** la hipótesis:
un reloj falso monótono, desplazado para que la medianoche de Bogotá caiga a
mitad de corrida, hace caer **17 tests** de forma reproducible; sin el cruce,
los 299 pasan. Se rastreó el mecanismo (p.ej. `test_dos_dias_consecutivos_sin_gases`
ancla "ayer" y "hoy" con dos llamadas a `now()` que pueden quedar a lados
distintos de la medianoche, abriendo un hueco fantasma). **El motor está bien**
(`alert_engine.py:700` usa `timezone.localdate()`; los filtros usan
`fecha_registro__date`, consciente de zona horaria). Es fragilidad de las
pruebas, no del sistema → queda para el Loop C (C7).

### Qué se hizo

Método: un test en rojo por comportamiento **antes** del arreglo, verificando
que cada rojo fuera por su defecto y no por otro. 6 commits (`1207d70` →
`f8fa437`), commits de código y de docs separados.

- **B1 — tests en rojo (D2 y D6).** 6 pruebas: webhook falla abierto ante caída
  del cache, formulario falla cerrado, verificación antes de reclamar el SID,
  límite 60, tope de evaluación, y correo → `FALLIDA`. Cada una falló por su
  defecto (4 asserts + 2 propagaciones de `ConnectionError`). El test previo del
  rate limit se **actualizó** (cambió el requisito, con el porqué en su docstring:
  antes esperaba fila `COMPLETADO`, ahora que no quede fila).
- **B2 — rate limit (D2).** `_rate_limit_excedido` capturaba solo `ValueError`;
  con Redis inalcanzable el webhook devolvía 500 a todos. Ahora el webhook
  **falla abierto** (la firma de Twilio protege la puerta) y registra la
  degradación; el formulario de contacto **falla cerrado** (única puerta sin
  firma). La verificación se movió **antes** de reclamar el SID (un mensaje
  limitado ya no deja fila). Límite 20 → **60** (atrapa un bucle igual; un
  cuestionario son ~11 mensajes).
- **B3 — `resuelta_por` (D3).** La acción del Admin usaba `queryset.update()`,
  que no guardaba **quién** resolvió ni escribía historial. Campo
  `Alerta.resuelta_por` (migración 0025) poblado en el mismo `.update()` +
  `log_change` por alerta. Visible en listado y detalle. Sin backfill.
- **B4 — tope de reintentos y `FALLIDA` (D6).** Correo y evaluación se toparon
  en **10 intentos**. Estado terminal `FALLIDA` para el correo agotado
  (migración 0026, que amplía las restricciones `estado_valido` y
  `envio_coherente`); la evaluación agotada deja de recogerse. El **tablero de
  triage** avisa de correos `FALLIDA`, también al médico (con scoping), porque
  un aviso de alerta ALTA que no llegó es información clínica que no debe quedar
  enterrada.
- **B5 — `/salud/` (D2).** Endpoint que verifica BD y cache y devuelve 200/503
  sin detalle. Es la pareja del "fallar abierto": sin monitor externo, una caída
  silenciosa se volvería pérdida de datos; con la alarma apuntando aquí, se
  vuelve una alerta al Arquitecto.
- **B6 — bloqueo de filas (hallazgo 2).** `procesar_notificaciones_pendientes`
  tomaba el `FOR UPDATE` sobre todo el JOIN, así que la llamada de red del envío
  bloqueaba la fila del paciente que el webhook necesita.
  `select_for_update(of=('self',))` limita el lock a la notificación. Test
  **determinista** (sin depender de tiempos): con el envío en curso, otra
  transacción bloquea la fila del paciente con `nowait`.

### Decisiones tomadas (ya documentadas en el doc de decisiones)

Ninguna decisión clínica ni de producto se tomó dentro del código: D2, D3 y D6
estaban aprobadas y razonadas de antemano en
`docs/decisiones_correccion_auditoria.md`. Ningún umbral clínico cambió.

### Problemas encontrados y resueltos

- **El "flake de medianoche" no era un flake casual.** Se rectificó una
  afirmación apresurada probándola: es sensibilidad real de las pruebas a la
  fecha, reproducible a voluntad, y ajena al motor. Documentada, no barrida.
- **Separar B2-B4 en commits.** `models.py` y `tests.py` mezclaban cambios de
  B3 y B4; se separaron con `git add -p` (respuestas dirigidas por hunk),
  verificando después que cada commit tuviera solo lo suyo.
- **Nueva restricción con `FALLIDA`.** Añadir el estado obligó a ampliar dos
  `CheckConstraint` (no solo la de estados válidos, también `envio_coherente`,
  que exige `fecha_envio` NULL para `FALLIDA`). Migración 0026 probada reversible
  ida y vuelta.

### Cierre

**299 tests OK**, `makemigrations --check` limpio, migraciones 0025 y 0026
reversibles. Las 5 advertencias de `check --deploy` local son de los settings de
desarrollo (DEBUG=True, CSRF_COOKIE_SECURE) y ninguna la introdujo el Loop B.

**Pendiente inmediato:** **Loop C** (coherencia e higiene, el último antes del
PR): hallazgos 6, 7, 8, 11; D7 (consulta de solo lectura en Railway sobre 0020);
D8-D10; recorte de CLAUDE.md; y el blindaje de los tests de medianoche (C7). Solo
al cerrarlo se prepara el PR hacia `Desarrollo`.

---

## Sprint 5 — Corrección post-auditoría, Loop C (coherencia e higiene)
**Fecha:** 24-25/07/2026
**Responsable:** León (Arquitecto IA) + Claude Code (Opus)
**Estado:** LOOP C IMPLEMENTADO ✅ — pendiente de la verificación de León y de
la consulta D7 en Railway. Es el último loop antes del PR.

### Qué se hizo

El tercer y último loop de la corrección post-auditoría. Cierra los hallazgos
técnicos que quedaban (6, 7, 8, 11), las tres decisiones que salieron del
ejercicio de documentación (D8, D9, D10), el hallazgo 9, el hallazgo 14, el
blindaje de las pruebas frágiles a la medianoche, y una reestructuración de toda
la documentación del proyecto.

**Las pruebas en rojo primero (`ad7a93d`).** Un solo commit con 15 casos
nuevos; **9 fallaron** contra el código de entonces y 6 nacieron verdes como
guardas declaradas en su docstring. Cada rojo, con su evidencia:

- **Hallazgo 6:** `USE_X_FORWARDED_HOST` y `SECURE_PROXY_SSL_HEADER` estaban
  activos en la configuración **base**, o sea en todo despliegue incluido el
  local. Django creía lo que dijeran `X-Forwarded-Host` y `X-Forwarded-Proto`
  viniera de donde viniera, mientras la IP del cliente sí exigía declarar la
  confianza. Tres cabeceras del mismo proxy, dos criterios distintos.
- **Hallazgo 7:** `'PENDIENTE' != 'ERROR'`. El motor guardaba con cuidado el
  estado de error antes de relanzar, pero el savepoint defensivo del bot lo
  revertía al salir la excepción. El registro quedaba idéntico a uno que nunca
  pasó por el motor.
- **Hallazgo 8:** `dr_filtro_b` y `super_filtro` aparecían en el HTML del
  listado de otro médico. Se confirmó leyendo el HTML renderizado, no
  deduciéndolo: el filtro lateral se arma con todos los usuarios de la base.
- **Hallazgo 11:** `SECRET_KEY` vacía, `SECRET_KEY=<placeholder>`, `DB_NAME` en
  blanco, `RESEND_API_KEY` y `CSRF_TRUSTED_ORIGINS` vacías — las cinco
  arrancaban sin decir nada.

**Las correcciones,** un commit por hallazgo: `5ad976f` (7), `b2eaa17` (8),
`ec02ef4` (6), `7b7454d` (11).

**D10 en dos pasos, en ese orden.** Primero `21b8d79`, cinco pruebas de
caracterización que **nacen verdes a propósito**: retratan cuándo dispara hoy la
condición MEDIA de hinchazón, incluido el caso sin dato de ayer. Después
`922e13c`, la reescritura legible. La equivalencia se verificó por dos vías
independientes: las cinco pruebas siguen pasando, y una comparación exhaustiva
de la expresión vieja contra la nueva sobre las **64 combinaciones** de
(antier, ayer, hoy) dio **cero diferencias**.

**El blindaje de medianoche (`cc84037`).** Se reprodujo el rojo de forma
determinista con un arnés temporal que corrió las clases **reales** bajo un
reloj falso que adelanta 50 ms por lectura y arranca a distintas distancias de
la medianoche, de modo que el cruce cayera en la 2.ª, 4.ª o 10.ª lectura del
escenario. Cayeron **14 pruebas de cinco clases**. El blindaje congela el reloj
de esas clases en el peor instante del día —un segundo antes de la medianoche—
y ninguna prueba cambió de contenido: solo se les agregó el decorador. El arnés
no se commiteó; era instrumento de medición.

**La documentación.** `c5174c1` (hallazgo 9 y D9), `e7155cb` (D8), `f82a973`
(hallazgo 14 y despliegue) y `27b1960` (la reestructuración completa).

### Decisiones tomadas

**Reestructurar la documentación con un archivo dueño por tema.** Es la única
decisión nueva del loop, y quedó documentada con su razonamiento en
`docs/arquitectura_documentacion.md`. El motivo: `CLAUDE.md` había llegado a
54.742 caracteres mezclando referencia clínica (44%), cronología duplicada de
esta bitácora (38%), instrucciones y contexto. Y las tablas de reglas estaban
copiadas en `CLAUDE.md` **y** en el ROADMAP, así que cada cambio de umbral había
que hacerlo dos veces.

Ahora `CLAUDE.md` es la puerta de entrada (17.700 caracteres) y cada tema tiene
un archivo dueño: `docs/reglas_clinicas.md`, `docs/modelos_datos.md`,
`docs/bot_whatsapp.md`, `docs/trampas_conocidas.md`, `docs/resumen_sprints.md`.
Las reglas clínicas se cargan solas con `CLAUDE.md`, porque el riesgo de que un
agente no las lea es que invente un umbral; el resto se lee bajo demanda y el
mapa dice cuándo.

El requisito que ordenó la decisión fue de León: **que el proyecto siga adelante
sin importar qué agente lo desarrolle.** De ahí que el conocimiento viva en
markdown neutral dentro de `docs/` y no en `.claude/`, que Codex no lee.

**D9 se implementó apartándose de la letra de su ficha.** La ficha pedía marcar
el campo obsoleto en su `help_text` y explícitamente "sin migración". Pero
cambiar un `help_text` genera una migración `AlterField`. Se conservó la
intención (no arrastrar una migración) usando un comentario en el código: el
modelo no está registrado en el Admin, así que el único lector posible de ese
texto es quien lee el archivo. Queda anotado por si León prefiere lo contrario.

**Ningún umbral clínico cambió en todo el loop.** D8 y D10 son precisamente lo
contrario: D8 corrige la documentación para que diga lo que el código hace
("días con datos", no "días calendario"), y D10 reescribe una expresión sin
tocar cuándo dispara.

### Problemas encontrados y resueltos

- **La validación del hallazgo 11 rompió una prueba existente.** `settings_production`
  pasó a exigir `CSRF_TRUSTED_ORIGINS` y `REDIS_URL` al cargarse, y el `.env` de
  desarrollo no las tiene: `test_produccion_aplica_csp_sin_scripts_inline` empezó
  a fallar al importar el módulo. Se ajustó para cargarlo con un entorno de
  producción mínimo y válido, y el porqué quedó escrito en su docstring. Fue la
  primera señal útil de la validación nueva: el fallo aparece al cargar y no
  mucho después.
- **El recorte del ROADMAP abortó a propósito la primera vez.** El script de
  de-duplicación verifica, antes de borrar, que cada línea exista en el destino.
  Se detuvo con tres divergencias. Al revisarlas una por una resultó que **las
  copias del ROADMAP estaban desactualizadas**: no nombraban las cinco variables
  del núcleo clínico, omitían el porqué del criterio de FC y la atribución de la
  decisión sobre FR. El destino conservaba más información en los tres casos. La
  excepción quedó escrita y justificada en el script, no silenciada.
- **Verificar que la reestructuración no perdiera nada.** Además del movimiento
  textual por script, se comprobó automáticamente que los datos duros del
  `CLAUDE.md` anterior siguieran teniendo documento: 15 hashes de commit, 6
  migraciones, 9 cifras de tests, 108 identificadores de código y 12
  identificadores de decisión. Cero sin hogar. Las 96 líneas que la comprobación
  literal marcó como "huérfanas" eran prosa reescrita del estado del proyecto,
  no hechos perdidos.
- **Dos corridas de la suite murieron y dejaron la base de pruebas a medias.**
  Las siguientes se quedaban esperando el prompt de borrado y devolvían un
  críptico `exit code 2` sin salida. Se resolvió corriendo con `--noinput`, que
  quedó documentado en los comandos esenciales de `CLAUDE.md`.
- **El barrido del hallazgo 14 encontró más de lo buscado.** Su texto no estaba
  transcrito en ningún documento, así que se revisó la documentación de
  despliegue contra el código: aparecieron **seis** discrepancias. La peor, el
  crontab de ejemplo invocaba `manage.py` desde la raíz del contenedor cuando en
  este repo vive un nivel debajo — copiado tal cual, cada corrida habría fallado.

### Cierre

**319 tests OK** (299 de línea base + 20 nuevas). `makemigrations --check` sin
cambios, `manage.py check` sin issues, `check --deploy` con configuración de
producción **sin issues**, y `pip-audit` sobre `requirements-runtime.txt` sin
vulnerabilidades conocidas.

`freezegun` se agregó **solo** a `requirements.txt` (desarrollo). No está en
`requirements-runtime.txt`, que es el que instala el Dockerfile: Railway no la
ve y producción no cambia.

### Acciones requeridas en Railway antes de desplegar

Ninguna la detecta `check --deploy`:

1. **`TRUST_RAILWAY_PROXY=True`** en el servicio web. Sin él, Django ve HTTP
   detrás del edge y `SECURE_SSL_REDIRECT` entra en bucle de redirecciones.
2. **`CSRF_TRUSTED_ORIGINS` y `REDIS_URL`** presentes y no vacías, o el
   contenedor no arranca. Fallar rápido nombrando la variable es el objetivo del
   hallazgo 11, pero conviene verificarlo antes del deploy.

En desarrollo con ngrok hay que agregar `TRUST_RAILWAY_PROXY=True` al `.env`
local, o la firma de Twilio deja de validar.

### Pendiente inmediato

1. **Verificación de León** sobre el Loop C, como en los dos anteriores.
2. **D7:** la consulta de solo lectura en Railway sobre la migración 0020
   (contar registros `COMPLETADA` con `intentos = 0`; se espera cero). Es lo
   único del Loop C que no se ejecuta desde el repositorio.
3. Solo después: **revisión del diff completo contra `Desarrollo` y PR.**

Queda decidido pero **no ejecutado**, para después del merge y en rama propia:
`AGENTS.md` para que Codex lea lo mismo sin depender de `CLAUDE.md`, y separar
`.claude/settings.json` compartido de `settings.local.json` personal.

### Incidente en producción durante el cierre del Loop C (25/07/2026)

**Los dos servicios cron dejaron de arrancar tras el deploy.** El push del Loop C
disparó el auto-deploy de Railway y, en su siguiente arranque, ambos cron
murieron con `ImproperlyConfigured: La variable de entorno CSRF_TRUSTED_ORIGINS
es obligatoria y está vacía o sin definir.`

**Causa.** La validación del hallazgo 11 volvió obligatorias
`CSRF_TRUSTED_ORIGINS` y `REDIS_URL`. El servicio web siempre las tuvo —las
necesita para el login del médico y para el cache compartido— pero los cron no,
porque hasta entonces ambas tenían valor por defecto y su ausencia era
invisible. Cada servicio de Railway tiene su propio entorno, y los tres cargan
el mismo módulo de configuración de producción.

**Error de anticipación.** Al cerrar el Loop C se advirtió "verificar estas
variables en Railway antes de desplegar", pensando únicamente en el servicio
web. No se consideró que los cron tienen entorno propio ni que uno de ellos
jamás atiende HTTP, de modo que exigirle orígenes CSRF es pedirle configuración
que no usa.

**Detección.** Railway envió la notificación de fallo al correo. El servicio web
siguió verde todo el tiempo (endpoint de salud en 200), que es justo lo engañoso
del caso: **un cron caído no avisa a nadie por sí mismo.** Es exactamente el
escenario que el monitoreo externo pendiente debe cubrir antes del piloto real.

**Decisión del Arquitecto — entorno único para todo el proyecto.** Los tres
servicios llevan la misma configuración completa, aunque un cron no use orígenes
CSRF. Se descartó la alternativa de que el código detectara si el proceso
atiende HTTP: esa detección es implícita y sorprende a quien la lea meses
después. Se prefiere una regla explícita, documentada y sostenida por las Shared
Variables del proyecto, en vez de por la memoria de alguien.

**Resolución.** Se agregaron las dos variables en `cron-manana` y `cron-tarde`,
copiando los valores del servicio web, y se redesplegaron ambos. La corrida de
`cron-tarde` de las 00:35 completó las tres tareas sin traceback y con todo en
cero: ningún check-in vencido sin cerrar, ninguna evaluación atascada, ninguna
notificación represada. **La caída no dejó trabajo pendiente**, que era la
promesa del diseño idempotente del Loop 2 y del outbox del Loop 4.

**Lo que el incidente confirma del propio hallazgo 11.** El error nombró la
variable exacta y detuvo el arranque en el acto, en vez de dejar el servicio
corriendo roto para fallar mucho después y lejos de la causa. Costó un susto y
media hora; la alternativa habría sido un cron aparentemente sano que dejara de
cerrar check-ins sin que nadie se enterara.

Trampa registrada en `docs/trampas_conocidas.md` y regla en
`docs/railway_deploy.md`.

---

## Sprint 5 — Auditoría de cierre pre-merge y decisiones del Loop D
**Fecha:** 27/07/2026
**Responsable:** León (Arquitecto IA) con Claude Code
**Estado:** DECISIONES ESCRITAS — Loop D sin empezar

### Qué se hizo

La sesión anterior se cortó (pestaña cerrada) justo cuando iba a llegar el
informe de la auditoría de cierre. Se reconstruyó el estado desde el
repositorio, no desde la memoria de nadie: `git log`, el "Estado de avance" de
`docs/decisiones_correccion_auditoria.md`, y una **medición propia de la línea
base** antes de leer nada del auditor — 319 tests OK, `check` limpio,
migraciones al día, `pip-audit` sin vulnerabilidades. Sirvió para contrastar las
cifras del informe en vez de creerlas.

**El informe de Codex volvió a bloquear el PR**, con dos hallazgos ALTOS. Los
cuatro se reprodujeron contra el código antes de aceptar ninguno, con un arnés
desechable fuera del repositorio. El resultado completo quedó escrito en
`docs/proceso/auditorias/2026-07-27_informe_cierre_codex.md`.

**Hallazgo 1 — identidad del paciente en la salida operativa.** Confirmado,
pero **por un canal distinto al que reportaba el informe**. El logger
`signos_sintomas` está en nivel WARNING, así que todos los `logger.info` con
datos del paciente se descartan antes de emitirse; lo que sí llega a Railway es
`self.stdout.write` de `desactivar_pacientes_vencidos`, con el nombre completo y
el día postoperatorio. Corregir la línea que señalaba Codex no habría cerrado
nada. La reproducción encontró además una ocurrencia que el informe no vio:
`enviar_recordatorios` arma nombre completo **y teléfono** de cada check-in
pendiente — hoy mudo por el nivel del logger, y a un cambio de configuración de
volcarse entero. Y el comentario de `settings.py` promete un filtro PHI que no
existe.

**Hallazgo 2 — paciente activo sin médico responsable.** Confirmado y peor de lo
reportado. El formulario del Admin no exige el campo y el desplegable nace
vacío, con una sola opción posible. El paciente resultante sigue activo y
generando alertas, pero desaparece del listado del médico **y de los KPI del
tablero**: el médico ve ceros, no un hueco. Su alerta ALTA queda sin
destinatario y deja `procesar_notificaciones_email` en `CommandError`. Se
verificó que no hay efecto dominó —esa tarea es la última de ambos cron—, lo que
resultó ser una conclusión demasiado amplia (ver más abajo).

**Hallazgo 3 — la firma de Twilio depende del entorno.** `settings_production`
no vuelve a fijar `TWILIO_VALIDATE_SIGNATURE`. Verificado en el panel de
Railway: la variable **no existe**, así que hoy la validación está activa por el
default del código.

**Hallazgo 4 — cinco documentos que contradicen el código.** Los cinco
confirmados. El del ROADMAP no era polvo documental: enunciaba la escalera
SILENCIO como 1/2/3+ cuando el código y `reglas_clinicas.md` dicen 1/2/4. Se
corrigió en esta misma sesión, junto con el estado de CLAUDE.md.

### Decisiones tomadas

**D11 — la salida operativa no contiene identidad del paciente.** Se identifica
por `pk`, como ya hace el resto del código. Con una prueba guardián que captura
stdout, stderr y logs **forzando nivel INFO**: bajo el nivel WARNING de
producción, un guardián normal pasaría en verde con el defecto puesto — el mismo
fallo de julio reproducido dentro de la prueba que debe impedirlo.

**D12 — todo paciente ACTIVO tiene un médico que puede verlo y recibir sus
alertas.** Cuatro capas: formulario obligatorio con autoasignación,
`on_delete=PROTECT` para que borrar una cuenta médica no fabrique huérfanos en
silencio, un `CheckConstraint` que la base rechaza venga de donde venga, y un
aviso en el tablero para el paciente cuyo médico existe pero no puede atenderlo.
Más la regla operativa: **las cuentas de médico no se borran, se desactivan** —
quién atendió a un paciente es parte de la historia clínica, no un dato de
configuración.

**D13 — la autenticidad del webhook no depende del entorno.**
`TWILIO_VALIDATE_SIGNATURE = True` fijo en `settings_production`, y **no crear
la variable en Railway**: `python-decouple` convierte cadena vacía en `False`, y
Railway vacía toda referencia que no resuelve. Crear la casilla introduciría el
mismo modo de fallo del incidente del 25/07, con la diferencia de que este
fallaría **abriendo la cerradura en silencio**.

**D14 — aislamiento entre las tareas de un mismo cron.** Escrita, sin
implementar, para el Loop E.

### Problemas encontrados y resueltos

**Dos fichas prometían más de lo que garantizaban.** Codex revisó las
decisiones antes de programar —ese fue el punto de pedirle una segunda vuelta— y
encontró que D11 declaraba un invariante absoluto sobre "la salida operativa"
mientras excluía los tracebacks tres párrafos después, y que D12 prometía en el
título *"todo paciente activo tiene médico responsable"* mientras su propio
razonamiento admitía que la garantía real era sobre el silencio, no sobre la
existencia del huérfano. Enumeró cuatro vías por las que un huérfano seguía
naciendo, y las cuatro se verificaron ciertas — incluidas dos en
`seed_demo_produccion` que nadie había mirado: crea pacientes sin médico cuando
no hay superusuario, y acepta cualquier `username` en `--medico` sin comprobar
que sea un médico usable.

La respuesta no fue rebajar la promesa sino **hacerla verdadera**, con la cuarta
capa. Una decisión que promete de más es peor que una que promete poco: la
siguiente persona confía en ella. La lección de método queda registrada — **el
mismo rigor que se le exige a un test en verde hay que exigírselo a una ficha de
decisión**: hay que verificar por qué es cierta.

**Una conclusión propia demasiado amplia.** Al verificar el hallazgo 2 se
comprobó que el fallo del envío de correo no arrastra a ninguna otra tarea del
cron, y se concluyó "no hay efecto dominó". Codex señaló que eso demuestra que
la *última* tarea está aislada, no que las tareas lo estén entre sí: un fallo
persistente de `cerrar_checkins_vencidos` sí impide que salgan los correos de
alerta ALTA de ese ciclo. Tenía razón. De ahí salió D14 — y con ella la
constatación de que la corrección obvia (continuar tras el fallo) habría sido
**incorrecta**, porque `cron_matutino` tiene una dependencia clínica declarada:
desactivar antes de crear check-ins, o se generan alertas SILENCIO espurias.

**Una compuerta que no se había visto.** El `Dockerfile` encadena
`migrate --noinput && gunicorn`. Una migración que falle no produce un error en
el log: deja el contenedor sin arrancar. Como la capa 4 de D12 añade una
restricción que las filas existentes deben cumplir, el Loop D empieza por dos
consultas de **solo lectura** contra producción. Es la disciplina de D7: contar
antes de actuar.

### Decisiones de operación

**Rama de despliegue.** Se confirmó en el panel que Railway sigue
`sprint-5-produccion`: cada push sale a producción, y mergear a `Desarrollo` no
despliega nada. Se decidió que el destino tampoco es `Desarrollo` —es la rama de
integración, donde aterriza trabajo a medio terminar— sino una rama `produccion`
creada después del merge. Pasos y advertencias en `docs/railway_deploy.md`,
sección 4.1, incluida la más importante: **nunca apuntar Railway a `Desarrollo`
antes del merge**, porque va 101 commits atrás y revertiría producción a código
anterior a los cuatro loops, con la escalera de SILENCIO rota.

### Qué queda pendiente

**Loop D, paso D-0:** las dos consultas de solo lectura en Railway — pacientes
activos sin responsable, y pacientes activos cuyo médico está inactivo, sin
`is_staff` o sin correo. Las ejecuta el Arquitecto y son la compuerta de la
migración del paso D-6. Si alguna devuelve filas, se arreglan los datos antes de
escribir la migración.

Después, en orden: D-1 (prueba en rojo), D-2 (firma), D-3 (PHI), D-4/5/6/7 (las
cuatro capas de D12), D-8 (seed) y D-9 (documentación). Un solo push al final,
con todo verde, mirando el log del deploy y `/salud/` después. Detalle en el
"Estado de avance" de `docs/decisiones_correccion_auditoria.md`.

---

## Sprint 5 — Loop D completo: privacidad operativa, responsable clínico y firma
**Fecha:** 27/07/2026
**Responsable:** León (Arquitecto) con Claude Code
**Estado:** LOOP D CERRADO Y VERIFICADO ✅ — sin desplegar todavía

### Qué se hizo

Los nueve pasos del Loop D, en 15 commits locales. **Nada se pusheó:** Railway
despliega desde esta rama, así que el push es único y va al final, con la
verificación hecha y mirando el log del deploy.

**D-0 — la compuerta.** Ejecuté contra producción las consultas de solo lectura
que autorizan la migración del paso D-6: **2 pacientes, 0 activos, cero activos
sin responsable, cero sin atención efectiva.** Base `railway`, migración
`0026_notificacion_estado_fallida`. Sin ese cero no se podía escribir la
restricción.

**D-1 — las pruebas en rojo.** Once pruebas, nueve rojas, cada una fallando por
su propio defecto; las dos verdes lo declaran en su docstring. El guardián de
PHI captura stdout, stderr **y los logs forzando nivel INFO**.

**D-2 — la firma (D13).** `TWILIO_VALIDATE_SIGNATURE = True` fijo en
`settings_production.py`. Deja de heredarse del entorno. La variable **no debe
crearse en Railway ni con valor `True`**: decouple convierte la cadena vacía en
`False` y Railway vacía toda referencia que no puede resolver, así que la
casilla fallaría **abriendo la cerradura del webhook en silencio**.

**D-3 — la identidad del paciente (D11).** `desactivar_pacientes_vencidos`
escribía el nombre completo en stdout —que Railway conserva igual que los logs—
y `enviar_recordatorios` armaba nombre **y teléfono** de cada check-in
pendiente. Ambos identifican ahora por `pk`. El comentario de `settings.py` que
afirmaba filtrar PHI/PII ahora dice la verdad: el único filtro declarado era
`RequireDebugFalse`.

**D-4 a D-8 — las cuatro capas de D12 y el seed.** Formulario del Admin con el
médico preseleccionado y validación de paciente activo; `on_delete` de
`SET_NULL` a **`PROTECT`** (migración 0027); **`CheckConstraint`** `activo ⇒
medico_responsable no nulo` (migración 0028); aviso en el tablero del
superusuario de pacientes activos **sin atención efectiva**; y
`seed_demo_produccion` que se niega a crear pacientes sin un médico usable en
vez de advertirlo.

**D-9 — los cinco desfases documentales.** El grave era el ROADMAP: decía que la
escalera de SILENCIO era `1/2/3+` cuando es `1/2/4` desde el Loop A. **Un umbral
clínico mal escrito en un documento vivo**, no polvo documental.

**Cierre.** Suite en **337 tests OK** (18 más que la línea base de 319), `check`
sin issues, `makemigrations --check` limpio. Corrí yo mismo la verificación
independiente `docs/proceso/verificaciones/2026-07-27_verificacion_loop_d.py`:
**8 bloques, OK.**

### Decisiones tomadas y su justificación

**Asignar en vez de rechazar (capa 1).** El invariante "ningún paciente activo
sin médico" se cumplía igual rechazando el formulario. Se eligió **asignar** al
médico que guarda: siendo no-superusuario, su única opción posible es él mismo,
así que un error de validación sería un obstáculo por un campo con una sola
respuesta. Como el invariante no distingue entre los dos caminos, se agregó una
prueba que fija cuál se eligió — si no, alguien puede derivar hacia el rechazo
dentro de seis meses creyendo que da lo mismo.

**La restricción es condicional, no `NOT NULL`.** `activo ⇒ responsable` deja en
paz a las fichas históricas. Un `NOT NULL` obligaría a inventarles un médico, que
es fabricar una atribución clínica — lo mismo que D3 se negó a hacer con
`resuelta_por`.

**Un solo aviso para cuatro condiciones.** Sin médico, médico desactivado, sin
`is_staff` o sin correo producen el mismo daño clínico: nadie mira a ese
paciente. Separarlos multiplicaría avisos sin cambiar la acción del médico.

### Problemas encontrados y resueltos

**1. Corrí la compuerta D-0 contra la base equivocada.** La primera ejecución
fue en PowerShell local y devolvió "0 pacientes" — de `registro_postquirurgico_db
@ localhost`, mi base de desarrollo vacía. Si nos quedábamos ahí, habríamos
escrito la migración creyendo que producción estaba vacía. Lo atrapó el paso de
confirmar **cuál** base estábamos mirando, no el resultado en sí.

**2. Dos pruebas de D-1 nacieron en verde mintiendo.** La del Admin no mandaba
el checkbox `activo`, así que el paciente nacía inactivo y el filtro no lo veía.
Las tres de la firma parcheaban el entorno, pero `settings_production` hereda ese
valor con `from .settings import *` y ese import resuelve contra el módulo ya
cargado al arrancar la suite: el parche no tocaba nada y las tres pasaban con el
defecto intacto. Se corrigieron **antes** de commitear; la segunda dejó el helper
`cargar_produccion_sobre_base_fresca` con el porqué escrito.

**3. Un `save_model` duplicado que habría roto dos cosas ajenas.** Al implementar
la capa 1 se escribió un `save_model` nuevo sin ver que `PacienteAdmin` ya tenía
uno. En Python el segundo gana en silencio: habría anulado la advertencia de
ingreso tardío (A-1) y el registro de `fecha_consentimiento` del HABEAS DATA, sin
que ninguna prueba nueva lo notara. Se integró en el método existente y se
corrieron las 39 pruebas de todas las clases del Admin, no solo las nuevas.

**4. La restricción dejó 164 pruebas en rojo de golpe.** No era un bug: esas
pruebas creaban pacientes activos sin médico, un estado que dejó de existir. Se
agregó el helper `medico_de_pruebas()` y un script mecánico insertó el
responsable en 88 llamadas, saltando las 17 que ya lo pasaban. Tres casos se
corrigieron a mano por tener significado propio — y uno de ellos importa:
**`test_set_null_al_borrar_usuario` afirmaba el comportamiento viejo.**
Verificaba que borrar la cuenta del médico dejara al paciente huérfano. Había una
prueba en verde documentando el hallazgo como si fuera el contrato.

**5. Una prueba escrita después del arreglo, y el intento fallido de
verificarla.** La del `--medico` inservible se escribió después de la corrección.
Para verificar que habría nacido en rojo se corrió contra la versión anterior con
`git stash` — pero el primer intento puso `--quiet` después de `--`, git lo tomó
como ruta, no stasheó nada y la prueba pasó en verde. Repetido bien, falló como
debía. Un "verifiqué" sin mirar la salida no verifica nada.

**6. La verificación archivada del Loop C dejó de correr.** Sus fixtures creaban
pacientes activos sin médico y la restricción 0028 los rechaza. Se les pasó un
responsable sin tocar sus aserciones. De paso, la regex que lo hizo insertó el
argumento en una llamada que ya lo tenía y dejó el módulo con `SyntaxError`;
apareció al ejecutarlo, no al escribirlo. **D-6 tiene alcance más allá del código
de la app:** cualquier script o carga de datos que cree pacientes activos sin
médico ahora falla.

**7. Por qué los demos de producción estaban inactivos, y por qué el correo de
silencio nunca llegó.** Dos cosas que parecían fallos y no lo eran. El seed les
pone `fecha_cirugia` 8-10 días hacia atrás para fabricarles historia, así que
**nacen en POD 8-10**, al borde de los `DIAS_SEGUIMIENTO = 10`; los sostuvo el
guard de gracia de 2 días y `desactivar_pacientes_vencidos` los cerró. Y
`signals.py:23` corta la notificación cuando la cédula empieza por `DEMO-`, antes
de mirar la severidad: **un paciente demo nunca encola correo, por diseño.**
Consecuencia práctica: el correo de alerta **no se puede probar de punta a punta
con los demos** — hace falta un paciente con cédula real asignado a un médico con
correo. Queda para el piloto.

De paso quedó a la vista que la escalera del Loop A vive en producción: 4
check-ins `NO_RESPONDIDO` y 2 alertas `SILENCIO / MEDIA`, que es la severidad que
fija D1 para una racha de 2 turnos.

### Qué queda pendiente

**Hecho al cierre de la sesión:**

1. **Consulta D-0 repetida** con dato fresco justo antes del push:
   `a_sin_medico = 0` otra vez, sobre 2 pacientes y 0 activos. La restricción de
   la 0028 no podía fallar por datos existentes.
2. **Push publicado:** `2fe6815 → 0f51ec0`, 18 commits. Las tres tarjetas de
   Railway (web y los dos cron) quedaron en **SUCCESS**, y `/salud/` respondió
   **HTTP 200 en diez sondeos consecutivos** durante los cinco minutos
   posteriores al deploy — el endpoint verifica base de datos y cache, así que
   descarta tanto un fallo de migración como un Postgres o Redis inalcanzable.

**Lo que queda, ya sin riesgo de producción** (guion completo en
`docs/proceso/2026-07-28_instruccion_cierre_rama_sprint5.md`):

1. Revisión del diff completo contra `origin/Desarrollo` (~117 commits).
2. PR y merge a `Desarrollo`. **No despliega nada.**
3. **Crear la rama `produccion` desde `Desarrollo` y reapuntar Railway allí.**
   Este es el paso que libera `sprint-5-produccion`: mergear no basta, porque
   Railway la sigue mirando y cualquier push por costumbre saldría al aire.
4. Abrir la rama siguiente desde `Desarrollo`.

**Después del push:** revisión del diff completo contra `origin/Desarrollo`, PR y
merge. Solo entonces se crea la rama `produccion` desde `Desarrollo` y se apunta
Railway allí (`docs/railway_deploy.md`, sección 4.1).

**Loop E (D14), no bloquea el merge:** aislar las tareas del cron conservando la
dependencia clínica declarada de `cron_matutino`. Va antes del piloto con
pacientes reales.

**Encabezado corregido:** este archivo nombraba una institución en su título, y
CLAUDE.md prohíbe usar nombres de instituciones y la marca "Sugarbaker" como
nombre del sistema. Ahora dice "Sistema de Monitoreo Posquirúrgico Remoto". Las
entradas históricas no se reescribieron: describen lo que se hizo en su momento.
`sugarbaker_hipec` sigue siendo un valor legítimo de `tipo_cirugia`.

---

## Sprint 5 — Cierre de la rama: PR, merge y rama de despliegue propia
**Fecha:** 29/07/2026
**Responsable:** León (Arquitecto) con Claude Code
**Estado:** SPRINT 5 CERRADO Y MERGEADO ✅ — producción desplegando desde `produccion`

### Qué se hizo

Los cuatro pasos del guion `docs/proceso/2026-07-28_instruccion_cierre_rama_sprint5.md`.
No se escribió código nuevo: la sesión fue de revisión, documentación y cambio de
topología de despliegue.

**Paso 1 — la revisión del diff.** Verifiqué primero que los documentos no
mintieran: `git status` limpio, local igual a remoto, y la suite en **337 tests
OK** (dos corridas, 303 s y 292 s). El diff contra `origin/Desarrollo` eran 124
commits al empezar, no los ~117 que decía el guion — se escribió el 27/07, antes
de los últimos commits de documentación. Revisé las seis áreas de la tabla del
guion y las seis salieron coherentes con las decisiones D1-D13.

**Limpieza de espacios en blanco.** `git diff --check` **no estaba limpio**: 87
líneas en `tests.py` y 3 en la verificación del Loop C, residuo del script
mecánico que insertó el `medico_responsable` en las 88 llamadas afectadas por la
migración 0028. Los cierres de los Loops A, B y C sí registraron
"`git diff --check` limpio" como criterio; el del Loop D no lo listó y por eso se
coló. Se limpió en dos commits, preservando los finales de línea originales y
verificando con `git diff -w` vacío que **solo cambiaron espacios**.

**Integridad documental, antes de limpiar.** `docs/modelos_datos.md` se declara
"Fuente única" de `models.py` pero cubría **4 de los 8 modelos**. Faltaban
`CheckInProgramado` (el modelo sobre el que D1 cuenta la racha de SILENCIO, con la
restricción `unique_checkin_paciente_dia_orden` sin describir en ninguna parte),
`RecepcionWebhookTwilio`, y el campo `ConversacionWhatsApp.checkin_actual`. Los
tres quedaron documentados. Lo demás sí estaba coherente: comparé por script las
18 constantes de `alert_engine.py` contra `reglas_clinicas.md`, los 12 estados del
bot contra `bot_whatsapp.md`, y los comandos programados contra `cron_setup.md`.

**Paso 2 — PR #3 y merge.** Se abrió con una evaluación de ingeniería, no un
resumen. Mergeado con **merge commit** (`3a5c573`), nunca squash: la
documentación cita **42 SHAs de commits individuales** y un squash los habría
dejado huérfanos. Verificado después del merge: los 42 siguen alcanzables desde
`Desarrollo`.

**Paso 3 — la rama `produccion`.** Creada desde `Desarrollo` en `3a5c573` y los
tres servicios de Railway reapuntados de `sprint-5-produccion` a `produccion`.
Los tres deploys en SUCCESS y `/salud/` en 200. **Desplegar dejó de ser una
consecuencia de integrar y pasó a ser un merge explícito de `Desarrollo` a
`produccion`.**

**Paso 4 — rama siguiente.** `sprint-6-ci` abierta desde `Desarrollo`. El primer
trabajo es montar CI, que es el punto 1 de la deuda registrada.

### Decisiones tomadas y su justificación

**El Loop E no absorbe la deuda técnica.** La revisión del PR dejó 8 puntos.
Solo el punto 2 (aislar el cron, D14) es el Loop E — y ya lo era. Meterle CI,
partir `tests.py` y renombrar un comando rompe lo que hace verificable al método:
si un loop toca cinco cosas, la verificación no puede afirmar nada concreto sobre
ninguna. **Un loop, un tema, una sesión.**

**Orden de la deuda: CI → Loop E → partir `tests.py` → `crear_medico`.** La CI va
primero porque hace que el PR del Loop E se verifique solo. Partir `tests.py` va
*después* del Loop E porque el Loop E añade pruebas a ese archivo: hacerlo antes
garantiza el conflicto que se busca evitar.

**Se conserva `sprint-5-produccion`.** Decisión mía: no se borra. En su lugar
queda la etiqueta **`sprint-5-cierre`** sobre `a13038e`, el último commit de la
rama antes del merge, para que ese punto de la historia tenga nombre legible.

**Dos líneas de llegada, no una.** El MVP demostrable (landing con datos reales,
demo que no caduque, correo mostrable) depende solo de nosotros y sin costo. El
piloto con pacientes reales depende de terceros y de dinero (aprobación de Meta,
plan de Railway, dominio en Resend, HABEAS DATA firmado, validación clínica de
las cuatro frases del bot). Los trámites del segundo son **colas, no tareas**, y
conviene arrancarlos en paralelo al primero.

### Problemas encontrados y resueltos

**1. Se sobredimensionó un hallazgo y hubo que retirarlo.** En la primera lectura
del PR se afirmó que "el radio de daño de un `--limpiar` mal apuntado es alto" en
los comandos de seed. **Es falso.** Pedí una segunda verificación exhaustiva y se
comprobó que `seed_demo` **aborta si `DEBUG=False`** —no puede correr en
producción— y que el `--limpiar` de `seed_demo_produccion` exige `--confirmar` y
solo alcanza los teléfonos de la lista fija `TELEFONOS_DEMO`, en transacción y
respetando el orden de las FK `PROTECT`. El punto quedó **tachado, no borrado**,
para que se vea que se revisó y por qué se cayó.

**2. La segunda pasada agravó dos puntos y encontró uno nuevo.** No fue cosmética:

- **El acoplamiento del cron es peor de lo escrito.** `cron_operativo` corre cada
  5 minutos, y `cron_matutino` también ejecuta `procesar_notificaciones_email`
  pero en la posición 6, con `cerrar_checkins_vencidos` en la 3. Un fallo
  persistente de esa tarea aborta **las dos rutas**: los correos de alerta ALTA no
  salen por ninguna. Y en la posición 4 está `enviar_recordatorios`, que es un
  **stub que no envía nada** — un no-op en la ruta crítica de la entrega de
  alertas.
- **Punto 8, nuevo:** `crear_medico` corre en cada arranque del servicio web
  **sin `|| true`** (a diferencia de `crear_admin`) y, sobre un usuario que ya
  existe, ejecuta igual `set_password`, `is_staff = True`, `groups.set([...])` y
  `user_permissions.clear()`. **Si el médico cambia su contraseña en el Admin, el
  siguiente despliegue la revierte en silencio.** Eso condiciona la decisión
  abierta de entregarle `medico_piloto`: hoy esa cuenta no puede tener contraseña
  propia que sobreviva a un deploy. Apareció al verificar otro punto, no por
  buscarlo.

Es el mismo patrón que dejó vivo el hallazgo bloqueante durante seis loops:
**revisar una vez no es revisar.**

**3. Se atribuyó a un campo un motivo que ningún documento respaldaba.** Al
documentar `ConversacionWhatsApp.checkin_actual` se escribió que existía por un
bug de cruce de medianoche. Se verificó contra BITÁCORA y ROADMAP antes de
commitear: el motivo real es coordinar el bot con el cron para que un paciente que
está contestando dentro de las 10 horas de gracia no reciba una alerta SILENCIO.
Corregido antes de que entrara al repositorio.

**4. El check rojo del PR no era nuestro.** El PR mostraba "1 falla, 3 exitosas".
Las tres verdes eran los servicios de `zooming-trust`. La roja era
**`aware-nourishment`, un segundo proyecto de Railway en la cuenta de Alejandro**,
de cuando arrancaba el proyecto, nunca continuado y con configuración incompleta —
fallando en todos los commits desde al menos el 10/07. No estaba documentado en
ninguna parte. Se apagó solo al reapuntar Railway (seguía a `sprint-5-produccion`,
no a `produccion`) y Alejandro lo borró después. Antes de recomendar borrarlo se
planteó verificar si tenía Postgres conectado: si hubiera tenido credenciales
válidas, habría existido una segunda copia de la app clínica en una URL no
documentada ni monitoreada — relevante con HABEAS DATA de por medio.

**5. GitHub dijo que la rama se podía borrar y era falso en ese momento.** Al
mergear, GitHub ofreció borrar `sprint-5-produccion` con el mensaje "can be
safely deleted". En ese instante los tres servicios de Railway todavía la
miraban: borrarla los habría dejado sin fuente. El mensaje es genérico y no sabe
nada de la topología de despliegue.

### Qué queda pendiente

**Instrucción de la próxima sesión:**
`docs/proceso/2026-07-30_instruccion_sprint6_ci.md`.

En una línea: **montar CI en `sprint-6-ci`**, que es el punto 1 de los 8 de
`docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`. Después, el Loop E
(D14) en su propia sesión.

**Decisión al cierre: los trámites del piloto quedan diferidos.** Se planteó
arrancar en paralelo las tres colas de la línea B (WhatsApp Business, dominio en
Resend, los 10 minutos con el médico) porque no se aceleran trabajando más. El
Arquitecto decidió lo contrario: **primero llevar el sistema al mejor punto
posible en desarrollo**, y los trámites después. Queda registrada la consecuencia
—diferirlos no atrasa el piloto por el tiempo diferido, sino por lo que tarden una
vez iniciados— para que conste que se decidió con eso a la vista.

**Cabo verificado al cierre:** el Postgres y el Redis en verde son los de
`zooming-trust`, o sea producción, y deben seguir online. Los de Alejandro también
aparecen en verde **aunque su proyecto figure offline**: borró el servicio de la
app, pero **las dos bases siguen corriendo**. En Railway borrar un servicio no
borra el proyecto. Pendiente suyo, no bloqueante: confirmar que están vacías y
eliminarlas — consumen recursos de su cuenta y, si alguna vez tuvieron datos,
siguen ahí.
