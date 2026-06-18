# Contexto del Proyecto — Sistema de Monitoreo Posquirúrgico Remoto

> **Para agentes IA:** Lee este archivo COMPLETO antes de sugerir cualquier
> cambio al proyecto. Toda decisión técnica debe ser compatible con el contexto
> clínico descrito aquí. Las reglas del alert_engine no son negociables —
> tienen base en evidencia clínica de recuperación postoperatoria colorrectal
> (protocolos ERAS). La auditoría de literatura confirmó que ningún estudio
> revisado trata HIPEC/Sugarbaker de forma específica; los umbrales se derivan
> de cirugía colorrectal electiva en general, no de ensayos HIPEC.

---

## ¿Qué es este proyecto?

Sistema de monitoreo remoto posquirúrgico para pacientes en recuperación de
cirugía colorrectal — incluyendo casos Sugarbaker/HIPEC como uno de los
tipos de procedimiento soportados, sin ser exclusivo de ellos (ver campo
`tipo_cirugia` en el modelo `Paciente`). El paciente interactúa
exclusivamente por WhatsApp. Un bot le hace preguntas diarias de telemetría.
El sistema clasifica los datos, detecta alertas rojas y notifica al médico
a través de un dashboard en Django Admin.

**La IA NO diagnostica.** Funciona bajo un sistema de reglas clínicas fijas
(alert_engine) para clasificar, resumir telemetría y generar alertas
tempranas.

**Nota sobre alcance y afiliación:** este proyecto no tiene afiliación
institucional formal a la fecha — es trabajo directo con el médico que
originó la idea, sin vínculo formalizado a una clínica o universidad. No
usar nombres de instituciones ni el nombre "Sugarbaker" como marca del
sistema en código, documentación o el nombre del repositorio, hasta que
exista una decisión formal sobre afiliación.

---

## Stack Tecnológico

- **Backend:** Django 6.0.5 + Python 3.13
- **Base de datos:** PostgreSQL 18 (local: registro_postquirurgico_db)
- **Interfaz paciente:** WhatsApp Bot vía Twilio API (en construcción, Sprint 3)
- **Panel médico:** Django Admin personalizado
- **Dependencias clave:** python-decouple, psycopg2-binary, twilio (próximo)
- **OS desarrollo:** Windows 11

---

## Repositorio

- **URL:** https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
- **Rama principal:** `Desarrollo`
- **Rama activa:** `sprint-3-whatsapp` (León)

---

## Estructura de Apps Django

```
Registro_Post_Quirurgico/Registro_Post_Quirurgico/
├── home/             → portal web, páginas informativas, formulario de contacto
└── signos_sintomas/  → núcleo clínico: modelos, bot, alertas, webhook
```

**Importante:** La carpeta del proyecto se llama `Registro_Post_Quirurgico`
(sin typo). Hubo una versión anterior llamada `Resgistro_Post_Quirurgico`
que fue eliminada en el Sprint 1.

---

## Variables Clínicas que Registra el Sistema

Capturadas una vez al día por WhatsApp:

| # | Variable | Tipo | Unidad |
|---|----------|------|--------|
| 1 | Temperatura corporal | Decimal | °C |
| 2 | Dolor EVA | Entero | Escala 1-10 |
| 3 | Aspecto del drenaje | Choices | seroso/hemático/purulento/fecaloide/sin_drenaje |
| 4 | Cantidad del drenaje | Choices | poco/normal/mucho/sin_drenaje (cualitativo, lo captura el bot) |
| 5 | Volumen del drenaje | Entero opcional | ml — solo si el paciente lo mide y lo reporta |
| 6 | Presencia de gases | Booleano | sí/no |
| 7 | Episodios de náuseas/vómito | Entero | cantidad en 24h |

---

## Reglas del Motor de Alertas (alert_engine.py)

**Archivo:** `signos_sintomas/alert_engine.py` — implementado en Sprint 2, mergeado a
`Desarrollo` (PR #1), con fix post-merge en commit `01b8a47`
**Función principal:** `evaluar_registro(registro: RegistroDiario) -> list[Alerta]`

| Regla | Condición exacta | Tipo Alerta | Severidad | Base clínica |
|-------|-----------------|-------------|-----------|--------------|
| 1 | temperatura >= 38.0 | SEPSIS | ALTA | Riesgo de sepsis postoperatoria |
| 2 | aspecto_drenaje in ['purulento','fecaloide'] | FUGA_ANASTOMOTICA | ALTA | Fuga anastomótica |
| 3 | sin gases 3 días consecutivos (por dia_postoperatorio) | ILEO_PARALITICO | ALTA | Íleo paralítico severo |
| 4 | episodios_nauseas > 3 | ILEO_PARALITICO | MEDIA | Íleo paralítico moderado |

**Nota:** la Regla 3 usa `dia_postoperatorio` (no timestamp) para determinar
"3 días consecutivos" — corregido en el fix post-merge `01b8a47` tras auditoría
de Claude Code, que detectó que usar `fecha_registro` no garantizaba el orden
correcto en casos de timestamps coincidentes.

---

## Modelos de Base de Datos

### Paciente (Sprint 1, ampliado en fase de generalización)
```python
nombre_completo       CharField(200)
telefono_whatsapp     CharField(20) unique  # identificador para el bot
fecha_cirugia         DateField
tipo_cirugia          CharField choices=[sugarbaker_hipec,colectomia_electiva,otra] null=True blank=True
medico_responsable    CharField(200)
activo                BooleanField default=True
fecha_registro        DateTimeField auto_now_add=True
```

**Decisión de diseño (fase de generalización):** `tipo_cirugia` es un dato
puramente descriptivo — no alimenta el `alert_engine` ni cambia el flujo
del bot. Existe para estadística e investigación futura; el sistema trata
a todos los pacientes igual sin importar su valor.

### RegistroDiario (Sprint 1, ampliado en Sprint 3)
```python
paciente              ForeignKey(Paciente, PROTECT)
temperatura           DecimalField(4,1)
dolor_eva             PositiveSmallIntegerField  # 1-10
aspecto_drenaje       CharField choices=[seroso,hematico,purulento,fecaloide,sin_drenaje]
cantidad_drenaje      CharField choices=[poco,normal,mucho,sin_drenaje] null=True blank=True
volumen_drenaje_ml    PositiveIntegerField nullable  # opcional, complemento de cantidad_drenaje
presencia_gases       BooleanField
episodios_nauseas     PositiveSmallIntegerField
fecha_registro        DateTimeField auto_now_add=True
dia_postoperatorio    PositiveSmallIntegerField  # calculado automáticamente en save()
```

**Decisión de diseño (Sprint 3):** `cantidad_drenaje` es el dato principal que
captura el bot (escala cualitativa, accesible para cualquier paciente).
`volumen_drenaje_ml` queda como complemento opcional — el bot lo extrae solo si
el paciente lo menciona espontáneamente (ej. "poco, 30ml"). El alert_engine usa
`aspecto_drenaje`, no `cantidad_drenaje` ni `volumen_drenaje_ml`, para las alertas.

### Alerta (Sprint 1)
```python
paciente              ForeignKey(Paciente, PROTECT)
registro_origen       ForeignKey(RegistroDiario, PROTECT)
tipo                  CharField choices=[SEPSIS,FUGA_ANASTOMOTICA,ILEO_PARALITICO,DOLOR_AGUDO]
severidad             CharField choices=[ALTA,MEDIA,BAJA]
mensaje               TextField
resuelta              BooleanField default=False
fecha_alerta          DateTimeField auto_now_add=True
fecha_resolucion      DateTimeField null=True blank=True
```

### ConversacionWhatsApp (Sprint 3)
```python
paciente                  OneToOneField(Paciente, PROTECT)
estado                     CharField choices=[INICIO, ESPERANDO_TEMPERATURA,
                           ESPERANDO_DOLOR, ESPERANDO_ASPECTO_DRENAJE,
                           ESPERANDO_CANTIDAD_DRENAJE, ESPERANDO_GASES_NAUSEAS,
                           COMPLETADO]
temp_temperatura           DecimalField nullable  # respuesta parcial del día
temp_dolor_eva              PositiveSmallIntegerField nullable
temp_aspecto_drenaje        CharField nullable
temp_cantidad_drenaje       CharField nullable
temp_volumen_drenaje_ml     PositiveIntegerField nullable
temp_presencia_gases        BooleanField nullable
temp_episodios_nauseas      PositiveSmallIntegerField nullable
fecha_ultimo_registro       DateField nullable  # controla "un registro por día"
fecha_actualizacion         DateTimeField auto_now=True
```

**Por qué existe:** cada mensaje de WhatsApp vía Twilio llega como una petición
HTTP independiente — Django no "recuerda" en qué pregunta iba el paciente entre
un mensaje y otro. Este modelo persiste el estado de la máquina de estados en
la base de datos en lugar de en memoria.

---

## El Bot de WhatsApp (signos_sintomas/bot.py — Sprint 3)

**Función principal:** `procesar_mensaje(telefono, texto) -> texto_respuesta`

Diseño: lógica **pura**, sin conocimiento de HTTP ni Twilio. La vista
(`views.py`, pendiente) traduce HTTP ↔ esta función. Esto permite testear el
bot completo sin mockear peticiones web — actualmente **18 tests unitarios OK**.

**Máquina de estados (5 preguntas):**
```
INICIO
  → ESPERANDO_TEMPERATURA       "¿Cuál es tu temperatura? ej: 37.5"
  → ESPERANDO_DOLOR             "Del 1 al 10, ¿cuánto dolor sientes?"
  → ESPERANDO_ASPECTO_DRENAJE   menú 1-5 en lenguaje no médico
  → ESPERANDO_CANTIDAD_DRENAJE  poco/normal/mucho (+ ml opcional) — se OMITE si aspecto=sin_drenaje
  → ESPERANDO_GASES_NAUSEAS     "¿pasaste gases? (sí/no), ¿náuseas? (número)" en un solo mensaje
  → COMPLETADO                  crea RegistroDiario, llama evaluar_registro(), confirmación neutra
```

**Reglas de diseño no negociables:**
1. **El paciente nunca ve alertas.** Solo recibe confirmación neutra
   ("¡Listo! Hemos registrado tu reporte de hoy 🌿"). Las alertas son
   exclusivamente para el oncólogo en el admin.
2. **Identificación por `telefono_whatsapp` + `activo=True`.** Si el número no
   está registrado, el bot responde amablemente sin crear nada — nunca crea
   pacientes desde el chat.
3. **Un registro por día.** Si ya completó hoy, responde "Ya registramos tus
   datos de hoy" y se reinicia automáticamente al día siguiente.
4. **Lenguaje:** español coloquial, tuteo, tono cálido — nunca jerga médica en
   las preguntas al paciente (ej. no decir "hemático", se muestra "rojo con
   sangre").
5. **Validación con reintento por pregunta:** cada respuesta mal formada pide
   reintento con un mensaje específico de esa pregunta, nunca un error genérico.
6. **Sin bloqueo horario en la lógica del bot.** El horario 7-10 AM Bogotá es
   para el envío automático matutino (diferido a FASE 4 con Celery); el bot
   responde a cualquier hora si el paciente escribe primero.
7. **Dudas (FAQ) fuera del flujo de registro:** respuestas predefinidas
   conservadoras (fiebre / alimentación / dolor / fallback a "contacta a tu
   médico"). Esto es un espejo temporal de `knowledge_base.md` mientras no
   exista la capa RAG (FASE 5).

**`knowledge_base.md`:** placeholder con la estructura final pendiente y las
respuestas predefinidas actuales. **No completar con información clínica real
ni cambiar las reglas del alert_engine sin que el Arquitecto lo decida
explícitamente en sesión** — la auditoría de literatura ya está disponible
(ver sección 'Auditoría de Literatura Clínica' abajo), pero las decisiones
que se derivan de ella todavía no se han tomado.

---

## Auditoría de Literatura Clínica

La auditoría de la evidencia científica del proyecto (9 PDFs sobre
ERAS/alta temprana en cirugía colorrectal, transcripciones de
presentaciones del médico, y documentos institucionales/académicos
complementarios) ya se realizó — ver `docs/auditoria_literatura/` para
el análisis completo, documento por documento, y la síntesis cruzada de
umbrales.

**Resultado relevante para el alcance del proyecto:** la evidencia
confirma que el sistema corresponde a ERAS/alta temprana en cirugía
colorrectal en general, no a un protocolo exclusivo de Sugarbaker/HIPEC
— ver el campo `tipo_cirugia` en `Paciente` y la sección "¿Qué es este
proyecto?" arriba.

**Pendiente:** la decisión de qué cambia en los umbrales y reglas del
`alert_engine` a partir de esta evidencia (fiebre, gases, náuseas,
drenaje, dolor, frecuencia de check-ins) — fase de decisiones de
arquitectura clínica, todavía sin resolver. El detalle completo de los
puntos abiertos está en
`docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md`.

**Mientras tanto:** nunca inventar ni suponer contenido clínico para
`knowledge_base.md`, ni cambiar ninguna regla del `alert_engine`, sin que
el Arquitecto lo decida explícitamente en sesión. La auditoría es
evidencia disponible, no decisiones ya tomadas.

---

## Estado Actual del Proyecto

| Sprint | Descripción | Estado |
|--------|-------------|--------|
| Sprint 0 | Configuración base y seguridad | ✅ Completado |
| Sprint 1 | Modelos clínicos y base de datos | ✅ Completado |
| Sprint 1 Frontend | Formulario de contacto, templates, admin home | ✅ Completado |
| Sprint 2 | Motor de alertas (alert_engine) | ✅ Completado (fix post-merge 01b8a47) |
| Sprint 3 | Bot WhatsApp (Twilio) | ⏳ Funcional end-to-end — merge a Desarrollo POSPUESTO a propósito (ver nota) |
| Sprint 3.5 | Auditoría de literatura, generalización de alcance/marca y documentación | ✅ Completado |
| Sprint 4 | Dashboard médico y notificaciones | ⏳ Pendiente |
| Sprint 5 | Producción, despliegue y RAG con contenido real | ⏳ Pendiente |

**Punto actual:** Sprint 3 funcional end-to-end (sin cambios desde la
prueba real con WhatsApp — ver pasos 1-4 abajo). Sprint 3.5
(generalización + auditoría de literatura) ya cerrado — ver
`docs/auditoria_literatura/` y la sección "Auditoría de Literatura
Clínica" arriba. **Próximo paso: fase de decisiones de arquitectura
clínica del `alert_engine`** (umbrales de fiebre, gases, náuseas,
drenaje; gap de `DOLOR_AGUDO`; frecuencia de check-ins) — ver
`docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md` para el punto
de partida. El merge `sprint-3-whatsapp` → `Desarrollo` sigue pospuesto
hasta cerrar esa fase.

- ✅ **Paso 1:** modelo `ConversacionWhatsApp` + campo `cantidad_drenaje` en
  `RegistroDiario` + migración `0002` aplicada.
- ✅ **Paso 2:** `bot.py` completo (lógica pura) + `knowledge_base.md`
  placeholder.
- ✅ **Paso 3:** `views.py` (webhook Twilio con `webhook_whatsapp` +
  `_firma_twilio_valida` fail-safe/fail-clear), `urls.py` de la app, bloque
  Twilio en `settings.py` (`TWILIO_VALIDATE_SIGNATURE` default True,
  `TWILIO_AUTH_TOKEN`, headers de proxy ngrok), `twilio==9.10.9` +
  `requirements.txt`, `.env.example`. **22 tests OK** (18 bot/alertas + 4 webhook).
- ✅ **Paso 4 (conexión real):** sandbox WhatsApp + ngrok + `.env` con credenciales
  reales. Prueba end-to-end exitosa: mensaje real → webhook → bot →
  `RegistroDiario` → `alert_engine` → `Alerta`, verificado en BD. Se resolvió un
  `400` (ALLOWED_HOSTS) y un `403` (firma) — ver BITACORA, sesión Twilio+ngrok.
- ⏳ **Único pendiente Sprint 3:** merge `sprint-3-whatsapp` → `Desarrollo`.

> **Merge sigue POSPUESTO (decisión del Arquitecto, actualizada tras
> cierre de Sprint 3.5):** la auditoría de literatura del médico ya se
> realizó (9 PDFs, transcripciones, documentos institucionales — ver
> `docs/auditoria_literatura/`) y confirmó que el alcance real es
> ERAS/cirugía colorrectal en general, no exclusivo de Sugarbaker/HIPEC.
> Lo que falta antes de mergear es la decisión de qué cambia en los
> **umbrales del `alert_engine`** a partir de esa evidencia. Mergear
> ahora obligaría a hacerlo dos veces. Se mergeará una sola vez, después
> de tomar esas decisiones.

**Lección clave de la conexión Twilio:** el Sandbox de WhatsApp firma sus webhooks
con el **Auth Token PRIMARIO** (Twilio Console → Account Dashboard), NO con el de
Test Credentials; usar el de Test causa `403`. Para ngrok free, `ALLOWED_HOSTS`
usa el comodín `.ngrok-free.dev` (el subdominio cambia en cada reinicio). Detalle
completo en BITACORA.md.

**Diferido explícitamente (no es parte del Sprint 3):**
- FASE 4 — envío automático matutino 7:00-10:00 AM Bogotá vía Celery/cron, y
  notificación al médico por email/SMS ante alerta roja.
- FASE 5 — capa RAG real leyendo `knowledge_base.md` con contenido
  derivado de la auditoría de literatura ya realizada (ver
  `docs/auditoria_literatura/`); pendiente de que se decidan primero los
  umbrales del `alert_engine`.

---

## Roles del Equipo

- **León (Arquitecto IA):** define lógica clínica, valida reglas médicas,
  aprueba cada decisión de diseño antes de que se escriba código, trabaja con
  Claude Code. NO es el programador principal.
- **Alejandro (Dev Full-Stack):** implementa modelos y vistas, configura
  infraestructura, trabaja con Codex CLI.

---

## Protocolo Obligatorio de Cierre de Sesión

**Esto no es opcional. Al final de CADA sesión de trabajo, sin que el Arquitecto
tenga que pedirlo, Claude Code debe ejecutar estos 3 procesos en orden:**

### 1. Documentar en BITACORA.md
Agregar una nueva entrada de sesión siguiendo el formato ya usado en el archivo
(Sprint, Fecha, Responsable, Estado, Qué se hizo, Decisiones tomadas, Problemas
encontrados y resueltos). Debe incluir:
- Qué se construyó, en lenguaje claro — el Arquitecto define la lógica clínica
  pero no es el programador principal.
- Decisiones clínicas tomadas y su justificación médica.
- Errores, bugs o conflictos de merge que aparecieron y cómo se resolvieron —
  esto es lo más valioso, nunca omitir un problema solo porque ya se arregló.
- Qué queda pendiente para la próxima sesión, indicando el paso exacto (no
  solo "Sprint 3 pendiente", sino "paso 3: views.py + urls.py + Twilio").

### 2. Actualizar CLAUDE.md y ROADMAP_MONITOREO_POSQUIRURGICO.md
- En **CLAUDE.md**: actualizar la tabla "Estado Actual del Proyecto" y la
  sección "Punto actual" con el sprint y paso exacto donde quedó el trabajo.
- En **ROADMAP_MONITOREO_POSQUIRURGICO.md**: marcar con `[x]` los
  checkboxes de las tareas completadas en la sesión.

### 3. Git add, commit y push
- Seguir la convención de commits ya definida (`feat:`, `fix:`, `docs:` +
  descripción en español).
- Nunca dejar trabajo funcional sin commitear al cerrar sesión.
- Hacer push siempre a la rama activa — no dejar commits solo locales.
- Si hay cambios de código Y de documentación, son commits separados (uno de
  código, otro de `docs:`).

**Regla de oro:** si el Arquitecto dice "vamos a cerrar", "dejemos hasta aquí",
"eso es todo por hoy" o cualquier frase equivalente, estos 3 pasos se ejecutan
automáticamente sin que tenga que pedir cada uno por separado. Al finalizar,
mostrar un resumen breve de qué se documentó y qué se commiteó/pusheó.

**Excepción:** si el Arquitecto dice explícitamente "no hagas commit todavía"
o "espera para documentar", respetar eso y ejecutar el paso correspondiente
solo cuando lo confirme.

**Nota sobre la evidencia clínica:** la auditoría de literatura ya se
realizó (ver `docs/auditoria_literatura/`), pero `knowledge_base.md`
permanece como placeholder hasta que el Arquitecto tome las decisiones de
umbrales/reglas del `alert_engine` que se derivan de ella. No completar
con información clínica real, inventada o supuesta, ni cambiar reglas del
`alert_engine`, sin esa decisión explícita.

---

## Convenciones del Equipo

- Idioma del código: **español** (nombres de variables, comentarios, commits).
- Rama principal: `Desarrollo` — **nadie trabaja directo aquí**.
- Una rama por sprint: `sprint-1-modelos`, `sprint-2-alertas`, `sprint-3-whatsapp`, etc.
- El `.env` **nunca** se sube a GitHub.
- Ningún código clínico entra a `Desarrollo` sin aprobación explícita del
  Arquitecto — incluyendo el visto bueno de cada decisión de diseño antes de
  escribir en disco, no solo antes del merge final.
- Commits: formato `feat:`, `fix:`, `docs:` + descripción en español.
- Modelo de Claude recomendado: **Opus** para diseño de arquitectura y
  decisiones clínicas complejas (máquina de estados, alert_engine); **Sonnet**
  para tareas rutinarias (tests, configuración, documentación).

---

## Comandos Esenciales

```bash
# Posición correcta para todos los comandos manage.py
cd Registro_Post_Quirurgico/Registro_Post_Quirurgico

python manage.py check           # verificar sin errores
python manage.py makemigrations  # después de cambiar models.py
python manage.py migrate         # aplicar cambios a PostgreSQL
python manage.py test signos_sintomas  # correr los 18 tests del bot + alert_engine
python manage.py runserver       # iniciar servidor → http://127.0.0.1:8000/admin/
```