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
**Estado:** COMPLETADO ✅ — ver `AUDITORIA_SPRINT3_CIERRE.md`

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
  reflejan el estado real del código. `AUDITORIA_SPRINT3_CIERRE.md`
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

## Sprint 4 — Dashboard y Notificaciones
**Fecha:** pendiente
**Estado:** EN COLA ⏳

---

## Sprint 5 — Producción
**Fecha:** pendiente
**Estado:** EN COLA ⏳
