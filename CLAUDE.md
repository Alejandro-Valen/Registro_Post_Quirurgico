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
- **Rama activa:** `sprint-5-produccion` (León)

---

## Estructura de Apps Django

```
Registro_Post_Quirurgico/Registro_Post_Quirurgico/
├── Registro_Post_Quirurgico/  → settings.py, settings_local.py (dev), settings_production.py (prod)
├── home/                      → portal web, páginas informativas, formulario de contacto
└── signos_sintomas/           → núcleo clínico
    ├── models.py, admin.py, alert_engine.py, bot.py, signals.py, views.py
    └── management/commands/   → crear_checkins_diarios, enviar_recordatorios,
                                  cerrar_checkins_vencidos, seed_demo
```

Árbol completo (archivo por archivo) en `ROADMAP_MONITOREO_POSQUIRURGICO.md`,
sección "Estructura del Proyecto Django".

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

### Paciente (Sprint 1, ampliado en fase de generalización, Sprint 5)
```python
nombre_completo       CharField(200)
cedula                CharField(20) unique=True null=True blank=True
                      # identificador principal (P-4). Obligatorio para pacientes
                      # nuevos vía Paciente.clean() (A-2); null solo permitido en
                      # registros previos a esta versión. blank=True a nivel de
                      # campo a propósito — la exigencia vive en clean(), no en el
                      # campo, para no romper full_clean() de pacientes legado.
telefono_whatsapp     CharField(20) unique  # identificador para el bot
fecha_cirugia         DateField
tipo_cirugia          CharField choices=[sugarbaker_hipec,colectomia_electiva,otra] null=True blank=True
medico_responsable    ForeignKey(User, SET_NULL, null=True)
                      # related_name='pacientes' — médico accede a sus pacientes con
                      # medico.pacientes.all()
activo                BooleanField default=True
consentimiento_informado  BooleanField default=False
                      # HABEAS DATA (Bloque 7, P-15). El bot no inicia el flujo con
                      # el paciente hasta que el médico marque este campo en el Admin.
fecha_consentimiento  DateTimeField null=True blank=True
                      # auto-registrada/limpiada en PacienteAdmin.save_model — el
                      # médico no la edita directamente (readonly en el Admin).
fecha_registro        DateTimeField auto_now_add=True
```

**Decisión de diseño (fase de generalización):** `tipo_cirugia` es un dato
puramente descriptivo — no alimenta el `alert_engine` ni cambia el flujo
del bot. Existe para estadística e investigación futura; el sistema trata
a todos los pacientes igual sin importar su valor.

**Guard de ingreso tardío (A-1, Sprint 5):** `desactivar_pacientes_vencidos`
solo desactiva un paciente si además de tener `dia_postoperatorio >=
DIAS_SEGUIMIENTO` (10) lleva al menos `DIAS_GRACIA_INGRESO` (2) días
registrado en el sistema (`fecha_registro`) — evita desactivar a un
paciente de ingreso tardío antes de que reciba un solo check-in.
`PacienteAdmin.save_model` además advierte al médico (sin bloquear) si crea
un paciente con `dia_postoperatorio >= 8`.

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
fecha_registro        DateTimeField default=timezone.now, editable=False
dia_postoperatorio    PositiveSmallIntegerField  # calculado al crear y luego inmutable
```

**Decisión de diseño (Sprint 3):** `cantidad_drenaje` es el dato principal que
captura el bot (escala cualitativa, accesible para cualquier paciente).
`volumen_drenaje_ml` queda como complemento opcional — el bot lo extrae solo si
el paciente lo menciona espontáneamente (ej. "poco, 30ml"). El alert_engine usa
`aspecto_drenaje`, no `cantidad_drenaje` ni `volumen_drenaje_ml`, para las alertas.

### Alerta (Sprint 1, ampliado en Sprint 4, Bloque A y agrupación 10/07/2026)
```python
paciente              ForeignKey(Paciente, PROTECT)
registro_origen       ForeignKey(RegistroDiario, PROTECT, null=True, blank=True)
                      # null solo para alertas SILENCIO (check-in sin respuesta)
tipo                  CharField choices=[SEPSIS,FUGA_ANASTOMOTICA,ILEO_PARALITICO,DOLOR_AGUDO,INTOLERANCIA_ORAL,TAQUICARDIA,SILENCIO]
severidad             CharField choices=[ALTA,MEDIA,BAJA]  # = MÁXIMA alcanzada mientras la alerta está abierta
mensaje               TextField
resuelta              BooleanField default=False
fecha_alerta          DateTimeField auto_now_add=True  # PRIMERA detección
veces                 PositiveSmallIntegerField default=1  # nº de check-ins que la detectaron (contador de recurrencia)
fecha_ultima_deteccion DateTimeField null=True blank=True  # detección más reciente
fecha_resolucion      DateTimeField null=True blank=True
motivo_resolucion     CharField choices=[CONTACTO,URGENCIAS,MEDICACION,FP_MEDICION,FP_RANGO,ESPONTANEO,OTRO,LEGACY] null=True blank=True
                      # Bloque A — obligatorio al resolver (vía formulario intermedio del Admin)
motivo_resolucion_detalle CharField(500) null=True blank=True  # requerido solo si motivo=OTRO
```

**Agrupación de alertas por problema (decisión Arquitecto, 10/07/2026):** el
`alert_engine` ya NO crea una alerta por check-in. Hay a lo sumo **UNA alerta
abierta (`resuelta=False`) por `(paciente, tipo)`**: si el mismo problema se
detecta de nuevo mientras sigue abierta, se **actualiza** (helper
`_registrar_alerta`, reemplaza la vieja `_deduplicar` por día) — sube `veces`,
`fecha_ultima_deteccion`, y la `severidad` si la nueva es mayor (la severidad =
la máxima; nunca baja sola). Dentro de un mismo check-in, dos reglas del mismo
tipo cuentan como **una** detección. Si el médico **resuelve** la alerta y el
problema **reaparece** después, se abre una **nueva** (evento nuevo). **Ninguna
regla ni umbral clínico cambió** — solo cómo se almacenan las detecciones. El
Admin muestra un badge de recurrencia "×N"; el tablero de triage también.

**Correo de alerta ALTA (actualizado 10/07/2026):** `signals.py` envía el email
al médico solo cuando la alerta **alcanza ALTA por primera vez** (creación ALTA
o **escalada** a ALTA, marcada por `_escalo_a_alta` desde el engine), **no** en
cada recurrencia diaria del mismo problema.

**Motivo de resolución (Bloque A, 02/07/2026):** el médico debe elegir un
motivo al marcar una alerta como resuelta — la acción "Marcar como resuelta"
del Admin muestra un formulario intermedio (default "Atendido — contacté al
paciente"; "Otro" exige detalle libre). Sirve para ajustar umbrales clínicos
con datos reales en el futuro. El scoping por médico se aplica en cada paso
(un médico no-superuser solo resuelve alertas de sus propios pacientes).
Desde el Loop 1 de hardening, la alerta completa es de solo lectura en el
formulario y la base exige fecha + motivo para todo cierre. `LEGACY` identifica
exclusivamente cierres históricos previos donde ese motivo no se capturó.

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
[Guard de consentimiento informado — Bloque 7]
  Si paciente.consentimiento_informado es False: mensaje neutro, no entra a INICIO.
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
  → COMPLETADO                  crea RegistroDiario, evalúa alertas (síncrono),
                                cierra con mensaje según severidad (neutro / MEDIA / ALTA)
```

**Reglas de diseño no negociables:**
1. **El paciente nunca ve el tipo de alerta ni los valores que la
   dispararon.** El detalle clínico (SEPSIS, FUGA, taquicardia, umbrales,
   etc.) es exclusivo del oncólogo en el admin. Desde el Bloque B
   (02/07/2026) el mensaje de cierre SÍ varía según la severidad máxima de
   las alertas del check-in, pero solo como recomendación de acción
   tranquilizadora: BAJA/sin alertas → `MSG_CONFIRMACION` (neutro); MEDIA
   → `MSG_CIERRE_ALERTA_MEDIA` ("contacta a tu médico en las próximas
   horas"); ALTA → `MSG_CIERRE_ALERTA_ALTA` ("comunícate con tu médico o
   ve a urgencias"). Ninguno menciona el tipo de alerta ni valores.
   Implementación: `evaluar_registro` corre de forma síncrona dentro de
   `_crear_registro` (en un savepoint defensivo) para conocer la severidad
   antes de responder; ver `_mensaje_cierre`.
2. **Identificación por `telefono_whatsapp` + `activo=True`.** Si el número no
   está registrado, el bot responde amablemente sin crear nada — nunca crea
   pacientes desde el chat.
2b. **Consentimiento informado obligatorio (Bloque 7, P-15).** Si
    `paciente.consentimiento_informado` es `False`, el bot devuelve un
    mensaje neutro (`MSG_SIN_CONSENTIMIENTO`, sin mencionar "consentimiento"
    ni "datos") y no entra a la máquina de estados. El médico marca el
    campo en el Admin tras obtener la firma física de
    `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`.
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
| Sprint 3-Hardening | Seguridad y robustez pre-producción | ✅ Completado — 24 hallazgos (A1–A6, B1–B7, C1–C7, D1–D5), 103 tests OK, mergeado a Desarrollo |
| Sprint 4 | Dashboard médico y notificaciones | ✅ Completado y mergeado a Desarrollo — 6 bloques, 135 tests OK |
| Sprint 5 | Producción, despliegue y RAG con contenido real | ⏳ En curso — Bloques 1-7 + A/B, **app en Railway + cron** (bot end-to-end), **landing del médico (P-12)**, **panel/branding**, **alertas agrupadas**, **Loop 1 de integridad/permisos** y **Loop 2 de entrega confiable** (**234 tests OK**). Railway sigue desplegado hasta el estado del 10/07; falta desplegar Loops 1-2, crear el cron frecuente de reintentos, resolver correo ALTA, datos/cuenta real del médico y requisitos de piloto. Rama `sprint-5-produccion` |

**Punto actual (18/07/2026):** Sprint 5 con los 7 Bloques + mejoras A/B, la app
desplegada en Railway y el cron base funcionando. Localmente quedaron cerrados
el **Loop 1 de integridad clínica/permisos** y el **Loop 2 de confiabilidad del
webhook y entrega de alertas** (**234 tests OK**). Railway aún no contiene estos
dos loops. URL:
`registropostquirurgico-production-1f96.up.railway.app`.
- **Panel del médico (Admin):** `/admin/` con branding "calma clínica"
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
- **Landing (P-12):** la página `/` (app `home`) se convirtió en la presentación
  del médico + sistema, con un **sistema de diseño compartido**
  (`home/static/home/css/site.css` + `home/static/home/js/pulse.js` +
  `home/templates/home/base.html`) que reusan `index.html` y `contacto.html`.
  Nav conectado a `/contacto/` y al Admin (enlace "Acceso médico" →
  `{% url 'admin:index' %}`). Contenido del médico en marcadores `[entre
  corchetes]` + flag `MOSTRAR_AVISO_BOCETO` en `home/views.py` (aviso de boceto
  que se apaga con los datos reales). 6 smoke tests en `home/tests.py`.
- **Demo del dashboard:** comando
  `signos_sintomas/management/commands/seed_demo_produccion.py` — idempotente y
  **seguro para producción** (a diferencia de `seed_demo`, bloqueado por A-3):
  `--confirmar` obligatorio, NO crea usuarios (asigna a un médico existente con
  `--medico` o al primer superusuario), pacientes marcados `DEMO — ` /
  cédula `DEMO-000X` / teléfono ficticio, y **reversible** con
  `--limpiar --confirmar`. Crea 2 pacientes de ejemplo con registros y alertas.
**Próximo paso exacto (al retomar):** los Loops 1-2 ya están pusheados hasta
`442ccc2`. Iniciar el **Loop 3 de experiencia médica** con una auditoría visual
y funcional del Admin usando una cuenta médica de privilegio mínimo; revisar
primero tablero de atención, semántica de pendientes, historial, recurrencias y
mensajes de contacto antes de implementar cambios. En el Loop 4 de producción,
desplegar Loops 1-3 a Railway; el arranque aplicará las migraciones 0019-0021,
crear el servicio cron `reintentar_evaluaciones_alertas` cada 5 minutos y
ejecutar un smoke test real de SID duplicado + check-in completo. Después:
**datos reales del médico** (reemplazar
`[corchetes]`, subir logo/colores, `MOSTRAR_AVISO_BOCETO=False`) y los
requisitos del piloto real en `ROADMAP_MONITOREO_POSQUIRURGICO.md`, sección
"Requisitos para un PILOTO REAL con pacientes" (plan Railway, WhatsApp Business,
HABEAS DATA).

**Nota cron (08/07/2026):** en Railway, encadenar comandos con `&&` en el
Custom Start Command **solo corre el primero** → se creó el comando único
`cron_matutino` (corre las 4 tareas matutinas en orden con `call_command`).
Los horarios cron van en **UTC** (Bogotá −5: 6 AM = 11:00 UTC, 6 PM = 23:00
UTC); mínimo de intervalo 5 min. Cambiar el Custom Start Command exige
**redesplegar** el servicio cron para que tome efecto.

**Notas de despliegue (06/07/2026):**
- El build usa **Dockerfile** (`python:3.13-slim`), NO Nixpacks/Railpack.
  Railpack ignora `nixpacks.toml` ("No start command detected"); Nixpacks
  falló con `pip: command not found` (peculiaridad de Nix). El Dockerfile es
  determinista; `nixpacks.toml` queda como fallback inerte.
- `requirements.txt` (raíz) es el pip freeze de desarrollo Windows y **NO** se
  usa para deploy — el Dockerfile instala `requirements-runtime.txt`.
- **Variables de Railway: valor crudo, nunca entre `< >` ni comillas.** Los
  placeholders `<...>` pegados literalmente fueron la causa raíz del 403 de
  Twilio y de los login fallidos al Admin (detalle en BITACORA 06/07/2026).
- El superusuario en producción se gestiona con el comando **`crear_admin`**
  (idempotente, desde `DJANGO_SUPERUSER_*`), no con `createsuperuser` (que no
  actualiza usuarios existentes). El interruptor `RESET_AXES=1` corre
  `axes_reset` al arranque para desbloquear axes; se quita tras usarlo.

Decisiones de producto P-1 a P-15 confirmadas en sesión (01/07/2026) —
ver tabla completa en `ROADMAP_MONITOREO_POSQUIRURGICO.md`, FASE 5.

Resumen de lo resuelto en `sprint-5-produccion` (Bloques 1-6):
- Bloque 1: campo `Paciente.cedula` (único, obligatorio para nuevos,
  migración 0014) + command `desactivar_pacientes_vencidos` (10 días
  postop, `--dry-run`, idempotente). 9 tests.
- Bloque 2: emojis eliminados de todos los mensajes de `bot.py` (P-11).
- Bloque 3: `TieneAlertaActivaFilter` en `PacienteAdmin` (usa
  `alertas__resuelta`, el `related_name` real) + historial configurable
  por días (`_historial_paciente`, selector `?dias=7/14/30`). 6 tests.
- Bloque 4: gráficas Chart.js (temperatura/dolor/FC) en la ficha del
  paciente, con selector 7/14/30 días sin recarga de página, turno M/T
  por `CheckInProgramado.etiqueta` real (no por hora — decisión D2), y
  puntos rojos para alertas ALTA sin resolver. 9 tests.
- Bloque 5: SMTP real (`EMAIL_*` en `settings_production.py` existente)
  — probado end-to-end con una alerta ALTA real, correo recibido y
  confirmado. Formato del correo mejorado en A-4 (02/07/2026): incluye
  teléfono y cédula del paciente y hora en zona Bogotá.
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

Ambas preguntas de arquitectura que quedaban abiertas ya se resolvieron:
cron en **Linux** (Railway/Render, no Windows Task Scheduler) y SMTP con
**Gmail + contraseña de aplicación**.

**Lección clave de la conexión Twilio:** el Sandbox de WhatsApp firma sus webhooks
con el **Auth Token PRIMARIO** (Twilio Console → Account Dashboard), NO con el de
Test Credentials; usar el de Test causa `403`. Para ngrok free, `ALLOWED_HOSTS`
usa el comodín `.ngrok-free.dev` (el subdominio cambia en cada reinicio). Detalle
completo en BITACORA.md.

**Pendiente de producción:** el proxy/balanceador Nginx debe configurarse con
`proxy_set_header REMOTE_ADDR $remote_addr;` (o equivalente) para que
`REMOTE_ADDR` refleje la IP real del cliente. El rate limit del formulario
de contacto (`home/views.py`) y del webhook (`views.py`) dependen de que esto esté
correcto en producción. Se resuelve al desplegar, no en el código Django.

**Por resolver (al 10/07/2026) — lista consolidada de lo pendiente:**
1. **[CRÍTICO] El correo de alerta ALTA no sale desde Railway.** Al poblar la
   demo se detectó que `send_mail` (SMTP síncrono, `fail_silently=False`) en
   `signos_sintomas/signals.py` **se cuelga en `socket.connect` a
   `smtp.gmail.com`** desde el contenedor de Railway — el plan de Railway
   probablemente **bloquea el puerto SMTP saliente**. Impacto: la notificación
   por email al médico (feature clave) NO funciona en producción. A decidir:
   migrar de Gmail SMTP a una **API HTTP de correo** (Resend / SendGrid /
   Mailgun) que no dependa del puerto SMTP, o habilitar SMTP en Railway. Además
   `send_mail` no tiene timeout ni es no-bloqueante: conviene enviarlo con
   timeout o en segundo plano para que un fallo de correo no bloquee el flujo.
   (El comando `seed_demo_produccion` ya silencia el correo durante el seed, así
   que esto NO afecta a la demo, solo a las alertas reales.)
2. **Datos reales del médico en la landing (P-12):** reemplazar los
   `[corchetes]`, subir logo/colores propios, y poner
   `MOSTRAR_AVISO_BOCETO = False` en `home/views.py`.
3. **Cuenta real del médico:** el comando idempotente `crear_medico` y el grupo
   de privilegio mínimo ya están implementados. Falta cargar temporalmente
   `DJANGO_MEDICO_*` en Railway, verificar el acceso y asignarle sus pacientes
   (`medico_responsable`). Registros/check-ins son de solo lectura; alertas se
   resuelven únicamente mediante la acción con motivo.
4. **Requisitos del piloto real** (ver ROADMAP, "Requisitos para un PILOTO REAL
   con pacientes"): plan de pago Railway, salir del Sandbox de Twilio a
   **WhatsApp Business API**, completar los corchetes de
   `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`, y prueba real por WhatsApp.
5. **`enviar_recordatorios` sigue stub** (Twilio saliente real): hoy el sistema
   es reactivo (responde cuando el paciente escribe); el envío matutino
   automático real está pendiente.

**Diferido explícitamente:**
- Desplegar en Railway o Render con PostgreSQL en la nube.
- Integración Twilio saliente real en `enviar_recordatorios` (stub hoy).
- Completar los campos entre corchetes de
  `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` (datos reales del médico/
  institución) antes de imprimirlo para el primer paciente real.
- Vista separada historial paciente (URL y template propios).
- RAG/MCP en el bot — Sprint 6, con corpus de `knowledge_base.md`
  validado por el médico (decisión P-13); pendiente de que se decidan
  primero los umbrales del `alert_engine`.
- OpenMed (anonimización PII) — Sprint 6, solo referencia (P-14).

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
