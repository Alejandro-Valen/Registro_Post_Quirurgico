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

Capturadas 2 veces al día por WhatsApp (decisión jun 2026 — Gignoux 2018
como referencia parcial; **pendiente de implementar en bot.py**, hoy el
bot sigue capturando 1 vez/día):

| # | Variable | Tipo | Unidad |
|---|----------|------|--------|
| 1 | Temperatura corporal | Decimal | °C |
| 2 | Dolor EVA | Entero | Escala 1-10 |
| 3 | ¿Tiene drenaje activo? | Booleano nullable | sí/no/no capturado |
| 4 | Aspecto del drenaje | Choices | seroso/hemático/turbio/purulento/fecaloide/sin_drenaje |
| 5 | Cantidad del drenaje | Choices | poco/normal/mucho/sin_drenaje (cualitativo) |
| 6 | Volumen del drenaje | Entero opcional | ml — solo si el paciente lo mide |
| 7 | Presencia de gases | Booleano | sí/no |
| 8 | Episodios de náuseas/vómito | Entero | cantidad por check-in |
| 9 | ¿Toleró líquidos sin vomitar? | Booleano nullable | sí/no/no capturado |
| 10 | Hinchazón/distensión abdominal | Choices nullable | nada/algo/mucho |
| 11 | Frecuencia cardíaca | Entero nullable | lpm — alerta TAQUICARDIA si >= 101 |
| 12 | Frecuencia respiratoria | Entero nullable | rpm — SOLO dashboard, sin alerta |

---

## Reglas del Motor de Alertas (alert_engine.py)

**Archivo:** `signos_sintomas/alert_engine.py`
**Función principal:** `evaluar_registro(registro: RegistroDiario) -> list[Alerta]`
**Principio de diseño (decisión jun 2026):** modelo de alta sensibilidad
(Lee 2022, Outersterp 2025) — escalera BAJA/MEDIA/ALTA en vez de un solo
nivel de alerta. **Las 5 variables del núcleo clínico (drenaje,
temperatura, gases, náuseas, dolor) están reescritas bajo este
modelo — fase de decisiones de arquitectura clínica completa.**

| Regla | Condición exacta | Tipo Alerta | Severidad | Base clínica |
|-------|-----------------|-------------|-----------|--------------|
| 1a | temperatura >= 37.9°C (cualquier registro del día) | SEPSIS | ALTA | Outersterp 2025 — umbral de notificación domiciliaria |
| 1b | temperatura 37.5–37.8°C en 2 días calendario consecutivos | SEPSIS | MEDIA | Subfebrícula persistente — construcción propia |
| 2a | tiene_drenaje is True AND aspecto in ['purulento','fecaloide'] | FUGA_ANASTOMOTICA | ALTA | Fuga anastomótica confirmada |
| 2b | tiene_drenaje is True AND aspecto in ['turbio','hematico'] | FUGA_ANASTOMOTICA | MEDIA | Drenaje sospechoso — seguimiento |
| 2c | tiene_drenaje is True AND aspecto == 'seroso' | FUGA_ANASTOMOTICA | BAJA | Drenaje dentro de lo esperado |
| 3a | sin gases 1 día calendario | ILEO_PARALITICO | BAJA | Gases = criterio de alta ERAS; ausencia = regresión |
| 3b | sin gases 2 días calendario consecutivos | ILEO_PARALITICO | MEDIA | ídem |
| 3c | sin gases 3 días calendario consecutivos | ILEO_PARALITICO | ALTA | ídem — umbral histórico del proyecto |
| 4a | suma episodios_nauseas del día: 1-2 | ILEO_PARALITICO | BAJA | Lee 2022, Outersterp 2025 — cualquier episodio es señal |
| 4b | suma episodios_nauseas del día: 3-4 | ILEO_PARALITICO | MEDIA | ídem |
| 4c | suma episodios_nauseas del día: 5+ | ILEO_PARALITICO | ALTA | ídem |
| 4d | náuseas (≥1 episodio/día) en 2 días calendario consecutivos | ILEO_PARALITICO | MEDIA (mínimo) | Persistencia — solo sube severidad, nunca la baja |
| 4e | náuseas (≥1 episodio/día) en 4 días calendario consecutivos | ILEO_PARALITICO | ALTA | Delaney 2008 — íleo en 27.8% con estancia 4+ días vs 11% general |
| 5a | dolor_eva >= umbral según ventana de dia_postoperatorio (ver nota) | DOLOR_AGUDO | BAJA/MEDIA/ALTA según ventana | Delaney 2008, Lee 2022, Outersterp 2025, Coeckelberghs 2025 |
| 5b | promedio dolor_eva últimos 2 días - promedio 2 días anteriores >= 3 | DOLOR_AGUDO | sube un nivel sobre 5a (techo ALTA) | Tendencia alcista — construcción propia |
| 6a | tolero_liquidos=False en 1 día calendario | INTOLERANCIA_ORAL | MEDIA | Deshidratación = causa #1 de readmisión (Lawrence 2013); tolerancia oral es criterio de alta ERAS |
| 6b | tolero_liquidos=False en 2 días calendario consecutivos | INTOLERANCIA_ORAL | ALTA | Riesgo de deshidratación establecida |
| 7a | hinchazón: nivel de hoy > nivel de ayer (empeoramiento puntual) | ILEO_PARALITICO | BAJA | Distensión = signo de íleo; empeoramiento leve |
| 7b | hinchazón: hoy > antier sostenido sin bajar >2 días | ILEO_PARALITICO | MEDIA | Empeoramiento sostenido — posible íleo en progreso |
| 7c | hinchazón "mucho" sostenido 4 días calendario consecutivos | ILEO_PARALITICO | ALTA | Distensión severa persistente — posible íleo paralítico |
| 8a | frecuencia_cardiaca 101-109 lpm | TAQUICARDIA | BAJA | Taquicardia leve, probablemente fisiológica |
| 8b | frecuencia_cardiaca 110-149 lpm | TAQUICARDIA | MEDIA | CREWS 2022 (110 lpm, 75% sens. fuga/sangrado); Cleveland NCT04574908 (>110 intervención) |
| 8c | frecuencia_cardiaca >= 150 lpm | TAQUICARDIA | ALTA | Escalamiento inmediato (protocolos hospitalarios) |

**Nota Regla 8 (FC — valor absoluto):** la taquicardia se evalúa por el
valor de cada registro, sin lógica de días calendario ni persistencia
(el valor por sí solo ya es clínicamente significativo). Solo se vigila
FC alta, no bradicardia.

**Frecuencia respiratoria (FR): SOLO DASHBOARD, sin regla.** Se captura y
almacena pero el `alert_engine` NO la evalúa — decisión del Arquitecto:
Outersterp 2025 halló que el 77% de las falsas alertas venían del sensor
de FR. Por eso FR no tiene fila de reglas; solo aparece como variable y
campo del modelo.

**Nota sobre lógica de días calendario (Reglas 1, 3, 4, 6, 7):** agrupan
registros por `fecha_registro__date`, no por número de registro — el
sistema captura 2 check-ins/día, así que 2 registros del mismo día
cuentan como 1 día, no como 2.

**Nota Regla 5 (Dolor/DOLOR_AGUDO — implementado):** escalera por
`dia_postoperatorio`: POD 1-2 → BAJA 5-6/MEDIA 7-8/ALTA 9-10; POD 3-5
→ BAJA 4-5/MEDIA 6-7/ALTA 8-10; POD 6+ → BAJA 3-4/MEDIA 5-6/ALTA
7-10. Capa de tendencia: si el promedio de los últimos 2 días
calendario sube >=3 puntos vs. el promedio de los 2 días anteriores,
escala un nivel de severidad sobre el valor de la tabla (nunca baja
una severidad ya alcanzada). Base: Delaney 2008, Lee 2022, Outersterp
2025, Coeckelberghs 2025.

---

## Modelos de Base de Datos

### Paciente (Sprint 1, ampliado en fase de generalización)
```python
nombre_completo       CharField(200)
telefono_whatsapp     CharField(20) unique  # identificador para el bot
fecha_cirugia         DateField
tipo_cirugia          CharField choices=[sugarbaker_hipec,colectomia_electiva,otra] null=True blank=True
medico_responsable    ForeignKey(User, SET_NULL, null=True)
                      # related_name='pacientes' — médico accede a sus pacientes con
                      # medico.pacientes.all()
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
tiene_drenaje         BooleanField null=True  # null=legado, False=sin drenaje, True=con drenaje
aspecto_drenaje       CharField choices=[seroso,hematico,turbio,purulento,fecaloide,sin_drenaje]
cantidad_drenaje      CharField choices=[poco,normal,mucho,sin_drenaje] null=True blank=True
volumen_drenaje_ml    PositiveIntegerField nullable  # opcional, complemento de cantidad_drenaje
presencia_gases       BooleanField
episodios_nauseas     PositiveSmallIntegerField
tolero_liquidos       BooleanField null=True  # null=no capturado, False=no toleró, True=toleró
hinchazon_abdominal   CharField choices=[nada,algo,mucho] null=True  # se evalúa por empeoramiento entre días
frecuencia_cardiaca   PositiveSmallIntegerField null=True  # lpm — alerta TAQUICARDIA por valor absoluto
frecuencia_respiratoria PositiveSmallIntegerField null=True  # rpm — SOLO dashboard, sin alerta (Outersterp 2025)
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
tipo                  CharField choices=[SEPSIS,FUGA_ANASTOMOTICA,ILEO_PARALITICO,DOLOR_AGUDO,INTOLERANCIA_ORAL,TAQUICARDIA]
severidad             CharField choices=[ALTA,MEDIA,BAJA]
mensaje               TextField
resuelta              BooleanField default=False
fecha_alerta          DateTimeField auto_now_add=True
fecha_resolucion      DateTimeField null=True blank=True
```

### ConversacionWhatsApp (Sprint 3, ampliado en Sprint 3.5)
```python
paciente                  OneToOneField(Paciente, PROTECT)
estado                     CharField choices=[INICIO, ESPERANDO_TEMPERATURA,
                           ESPERANDO_DOLOR, ESPERANDO_TIENE_DRENAJE,
                           ESPERANDO_ASPECTO_DRENAJE,
                           ESPERANDO_CANTIDAD_DRENAJE, ESPERANDO_GASES_NAUSEAS,
                           ESPERANDO_HINCHAZON, ESPERANDO_FRECUENCIA_CARDIACA,
                           ESPERANDO_FRECUENCIA_RESPIRATORIA,
                           ESPERANDO_TOLERANCIA_LIQUIDOS, COMPLETADO]
temp_temperatura           DecimalField nullable  # respuesta parcial del día
temp_dolor_eva              PositiveSmallIntegerField nullable
temp_tiene_drenaje          BooleanField nullable
temp_aspecto_drenaje        CharField nullable
temp_cantidad_drenaje       CharField nullable
temp_volumen_drenaje_ml     PositiveIntegerField nullable
temp_presencia_gases        BooleanField nullable
temp_episodios_nauseas      PositiveSmallIntegerField nullable
temp_hinchazon_abdominal    CharField nullable
temp_frecuencia_cardiaca    PositiveSmallIntegerField nullable
temp_frecuencia_respiratoria PositiveSmallIntegerField nullable
temp_tolero_liquidos        BooleanField nullable
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
bot completo sin mockear peticiones web — actualmente **69 tests unitarios OK**.

**Máquina de estados (10 preguntas):**
```
INICIO
  → ESPERANDO_TEMPERATURA       "¿Cuál es tu temperatura? ej: 37.5"
  → ESPERANDO_DOLOR             "Del 1 al 10, ¿cuánto dolor sientes?"
  → ESPERANDO_TIENE_DRENAJE     "¿Tienes drenaje activo? sí/no"
  → ESPERANDO_ASPECTO_DRENAJE   menú 1-5 en lenguaje no médico — se OMITE si tiene_drenaje=False
  → ESPERANDO_CANTIDAD_DRENAJE  poco/normal/mucho (+ ml opcional) — se OMITE si tiene_drenaje=False
  → ESPERANDO_GASES_NAUSEAS     "¿pasaste gases? (sí/no), ¿náuseas? (número)" en un solo mensaje
  → ESPERANDO_HINCHAZON         "¿cómo siente la hinchazón del abdomen? nada/algo/mucho"
  → ESPERANDO_FRECUENCIA_CARDIACA "¿cuál es tu frecuencia cardíaca? (lpm)"
  → ESPERANDO_FRECUENCIA_RESPIRATORIA "¿cuál es tu frecuencia respiratoria? (rpm)"
  → ESPERANDO_TOLERANCIA_LIQUIDOS "¿Ha podido tomar líquidos sin vomitar? sí/no"
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
| Sprint 3.6 | Decisiones de arquitectura clínica del alert_engine | ✅ 5/5 variables del núcleo + 4/4 variables nuevas del Paso 2 |
| Sprint 3-Hardening | Seguridad y robustez pre-producción | ✅ Completado — 20 hallazgos (A1–A6, B1–B7, C1–C7), 88 tests OK, rama sprint-3-hardening |
| Sprint 4 | Dashboard médico y notificaciones | ⏳ Pendiente |
| Sprint 5 | Producción, despliegue y RAG con contenido real | ⏳ Pendiente |

**Punto actual:** Sprint 3-Hardening completo en rama `sprint-3-hardening`
(20 hallazgos resueltos: A1–A6, B1–B7, C1–C7; 88 tests OK). **Próximo
paso inmediato: merge `sprint-3-hardening` → `Desarrollo`, luego Sprint 4
(dashboard médico).**

Resumen de lo resuelto en `sprint-3-hardening`:
- A: conversación abandonada, FC/FR saltables, idempotencia, lock transaccional,
  rate limit webhook, settings por entorno.
- B: headers HTTPS producción, logging, on_commit para alert_engine, índice
  fecha_registro, URL admin + django-axes, scoping por médico en admin, tests
  del webhook.
- C: refactor alert_engine en funciones _evaluar_X, CheckConstraint en BD,
  Django 6.0.6, rechazo de decimales en FC/FR, mensaje en list_display admin,
  403 genérico webhook, rate limit formulario de contacto.

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

  **Regla de sincronización inmediata (no diferible):** si la sesión
  modificó cualquier regla, umbral, constante, campo de modelo, o
  estructura de datos que tenga su reflejo en una tabla de referencia
  técnica de CLAUDE.md o ROADMAP_MONITOREO_POSQUIRURGICO.md (ej. "Reglas
  del Motor de Alertas", "Variables Clínicas", "Modelos de Base de
  Datos", la máquina de estados del bot), esas tablas se actualizan en el
  mismo lote de commits que el cambio de código — esto NUNCA se difiere,
  ni siquiera si el Arquitecto pidió esperar para escribir en
  BITACORA.md. La narrativa de BITACORA (qué se hizo, por qué, qué
  queda pendiente) sí puede acumularse en una sola entrada al cierre de
  una fase completa; las tablas de referencia técnica no — deben reflejar
  el código real en todo momento, porque son lo primero que cualquier
  agente IA lee para entender el estado actual del proyecto.

  **Norma de zona horaria:** todo cálculo de 'fecha de hoy' usa
  `timezone.localdate()`, nunca `.date()` sobre un datetime aware ni
  `timezone.now().date()` — con USE_TZ=True y TIME_ZONE=America/Bogota,
  esos dos devuelven la fecha en UTC, no en la zona del proyecto, y
  rompen las reglas de días calendario en horario nocturno.

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