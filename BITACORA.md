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

## Sprint 4 — Dashboard y Notificaciones
**Fecha:** pendiente
**Estado:** EN COLA ⏳

---

## Sprint 5 — Producción
**Fecha:** pendiente
**Estado:** EN COLA ⏳
