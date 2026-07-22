# ROADMAP MVP — Sistema de Monitoreo Posquirúrgico Remoto

> **Para agentes IA:** Lee este archivo completo antes de sugerir cualquier acción.
> Contiene el contexto clínico, el estado actual del proyecto, y los pasos pendientes.
> El repositorio es: https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
> Rama principal: `Desarrollo` | Rama activa: `sprint-5-produccion` (Sprint 4 mergeado a Desarrollo 01/07/2026, 135 tests OK)

---

## Contexto del Proyecto

Sistema de monitoreo remoto posquirúrgico para pacientes en recuperación de
cirugía colorrectal — incluyendo casos Sugarbaker/HIPEC como uno de los tipos
de procedimiento soportados, sin ser exclusivo de ellos. El paciente interactúa
exclusivamente por WhatsApp. Un bot le hace preguntas diarias de telemetría. El
sistema clasifica los datos, detecta alertas rojas automáticas y notifica al
médico a través de un dashboard en Django Admin.

**Stack:** Django 6.0.7 + PostgreSQL 18 + WhatsApp Bot (Twilio) + Python 3.13
**OS de desarrollo:** Windows 11
**Ruta del proyecto en máquina de León:**
`C:\Users\león\Documents\ProyectoLeonAlejo\Registro_Post_Quirurgico`

**Equipo:**
- León (Arquitecto IA) — define lógica clínica, trabaja con Claude Code
- Alejandro (Dev Full-Stack) — implementa código, trabaja con Codex CLI

**Ramas Git:**
- `Desarrollo` — rama principal estable ✅ actualizada (incluye Sprint 2 + fix 01b8a47)
- `sprint-1-modelos` — rama de León ✅ completada
- `sprint-2-alertas` — rama de Sprint 2 ✅ completada y mergeada a Desarrollo (PR #1)
- `sprint-1-frontend` — rama de Alejandro ✅ activa

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
nivel de alerta. **Las 5 variables están reescritas bajo este
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
valor de cada registro, sin lógica de días calendario ni persistencia.
Solo se vigila FC alta, no bradicardia.

**Frecuencia respiratoria (FR): SOLO DASHBOARD, sin regla.** Se captura y
almacena pero el `alert_engine` NO la evalúa — Outersterp 2025 halló que
el 77% de las falsas alertas venían del sensor de FR. Por eso FR no tiene
fila de reglas; solo aparece como variable y campo del modelo.

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

## Estructura del Proyecto Django

> Actualizada 01/07/2026 contra el árbol real del repositorio (post-merge Sprint 4).

```
Registro_Post_Quirurgico/                    ← raíz del repositorio
├── CLAUDE.md                                ← contexto para agentes IA
├── BITACORA.md                              ← historial del equipo
├── ROADMAP_MONITOREO_POSQUIRURGICO.md       ← este archivo
├── AUDITORIA_SPRINT3_CIERRE.md              ← detalle de hallazgos A/B/C/D del hardening
├── .gitignore
├── inicio_entornoR.bat
├── requirements.txt                         ← pip freeze completo (reproducir entorno dev)
├── requirements-runtime.txt                 ← dependencias directas de runtime (producción)
├── docs/
│   └── auditoria_literatura/                ← auditoría de evidencia ERAS (9 PDFs + transcripciones)
│       ├── README.md
│       ├── ANALISIS_INDIVIDUAL_9_PDFS_ERAS.md
│       ├── ANALISIS_4_ARCHIVOS_RESTANTES.md
│       ├── ANALISIS_TRANSCRIPCIONES_MEDICO.md
│       └── SINTESIS_CRUZADA_UMBRALES.md
└── Registro_Post_Quirurgico/                ← proyecto Django (manage.py aquí)
    ├── .env                                 ← secretos locales (NUNCA a GitHub)
    ├── .env.example                         ← plantilla de variables
    ├── manage.py
    ├── Registro_Post_Quirurgico/            ← configuración Django
    │   ├── settings.py                      ← base: PostgreSQL + decouple + Bogotá
    │   ├── settings_local.py                ← dev: EMAIL_BACKEND=console (Sprint 4)
    │   ├── settings_production.py           ← prod: DEBUG=False, HSTS, cookies seguras, cache Redis (Sprint 3-Hardening)
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── home/                                ← app portal web
    │   ├── models.py                        ← MensajeContacto
    │   ├── views.py                         ← index y contacto (rate limit)
    │   ├── admin.py
    │   ├── urls.py
    │   ├── migrations/0001_initial.py
    │   └── templates/home/
    │       ├── index.html
    │       └── contacto.html
    └── signos_sintomas/                     ← app núcleo clínico
        ├── models.py                        ← modelos clínicos + recibo técnico de Twilio
        ├── admin.py                         ← panel del médico: scoping, badges severidad, historial, filtros
        ├── alert_engine.py                  ← motor clínico + unicidad concurrente de alertas
        ├── evaluacion_alertas.py            ← estado auditable y reintentos del motor
        ├── bot.py                           ← máquina de estados WhatsApp (10 preguntas, 2×/día)
        ├── signals.py                       ← email al médico por alerta ALTA (on_commit)
        ├── views.py                         ← webhook Twilio (firma + SID durable en PostgreSQL)
        ├── urls.py
        ├── knowledge_base.md                ← placeholder (RAG diferido a FASE 5/6)
        ├── management/commands/
        │   ├── crear_checkins_diarios.py
        │   ├── enviar_recordatorios.py
        │   ├── cerrar_checkins_vencidos.py
        │   ├── reintentar_evaluaciones_alertas.py
        │   └── seed_demo.py                 ← datos demo (Camilo Rueda, demo_medico/demo1234)
        ├── migrations/                      ← 0001 a 0021
        └── tests.py                         ← 234 tests
```

---

## Modelos de Base de Datos

### Paciente
| Campo | Tipo | Descripción |
|-------|------|-------------|
| nombre_completo | CharField(200) | Nombre del paciente |
| telefono_whatsapp | CharField(20) unique | Formato: +573001234567 |
| fecha_cirugia | DateField | Fecha de la cirugía a la que se le da seguimiento postoperatorio |
| tipo_cirugia | CharField choices null=True | Dato descriptivo (sugarbaker_hipec/colectomia_electiva/otra) — no afecta alert_engine ni bot |
| medico_responsable | ForeignKey(User, SET_NULL, null=True) | Médico a cargo — related_name='pacientes' |
| activo | BooleanField | Desactivar al terminar seguimiento |
| fecha_registro | DateTimeField auto | Timestamp automático |

### RegistroDiario
| Campo | Tipo | Descripción |
|-------|------|-------------|
| paciente | ForeignKey(Paciente) PROTECT | No borrar paciente con registros |
| temperatura | DecimalField(4,1) | °C — alerta ALTA si >= 37.9 |
| dolor_eva | PositiveSmallIntegerField | Escala 1-10 |
| volumen_drenaje_ml | PositiveIntegerField nullable | ml |
| tiene_drenaje | BooleanField nullable | null=no capturado, False=sin drenaje, True=con drenaje |
| aspecto_drenaje | CharField choices | seroso/hemático/turbio/purulento/fecaloide/sin_drenaje |
| presencia_gases | BooleanField | Tránsito intestinal |
| episodios_nauseas | PositiveSmallIntegerField | Episodios en 24h |
| tolero_liquidos | BooleanField nullable | null=no capturado, False=no toleró, True=toleró |
| hinchazon_abdominal | CharField choices nullable | nada/algo/mucho — evaluado por empeoramiento entre días |
| frecuencia_cardiaca | PositiveSmallIntegerField nullable | lpm — alerta TAQUICARDIA por valor absoluto |
| frecuencia_respiratoria | PositiveSmallIntegerField nullable | rpm — SOLO dashboard, sin alerta (Outersterp 2025) |
| fecha_registro | DateTimeField auto | Timestamp automático |
| dia_postoperatorio | PositiveSmallIntegerField | Calculado con la fecha del registro al crear y luego congelado |
| estado_evaluacion_alertas | CharField choices | PENDIENTE/PROCESANDO/COMPLETADA/ERROR; indexado |
| intentos_evaluacion_alertas | PositiveSmallIntegerField | Número de intentos del motor |
| fecha_ultima_evaluacion_alertas | DateTimeField nullable | Auditoría técnica del último intento |
| ultimo_error_evaluacion_alertas | CharField(100) | Solo clase del error; nunca respuestas del paciente |

### Alerta
| Campo | Tipo | Descripción |
|-------|------|-------------|
| paciente | ForeignKey(Paciente) PROTECT | — |
| registro_origen | ForeignKey(RegistroDiario) PROTECT | Registro que disparó la alerta |
| tipo | CharField choices | SEPSIS/FUGA_ANASTOMOTICA/ILEO_PARALITICO/DOLOR_AGUDO/INTOLERANCIA_ORAL/TAQUICARDIA/SILENCIO |
| severidad | CharField choices | ALTA/MEDIA/BAJA |
| mensaje | TextField | Descripción generada por alert_engine |
| resuelta | BooleanField | El oncólogo marca cuando atiende |
| fecha_alerta | DateTimeField auto | Timestamp automático |
| fecha_resolucion | DateTimeField nullable | Cuándo fue atendida |
| veces | PositiveSmallIntegerField | Cantidad de detecciones mientras permanece abierta |

Restricción: como máximo una alerta abierta por `(paciente, tipo)`.

### DeteccionAlerta
- Modelo hijo de solo lectura creado en el Loop 3 (migración 0022).
- Cada fila conserva exactamente una fuente: `RegistroDiario` para una
  detección clínica o `CheckInProgramado` para SILENCIO.
- Guarda fecha, severidad y mensaje de esa detección; las restricciones de BD
  impiden duplicar la misma fuente dentro de una alerta.
- Empieza a registrar desde esta versión. El contador histórico `veces` se
  conserva, pero no se reconstruyen eventos que nunca fueron almacenados.

### ConversacionWhatsApp / RecepcionWebhookTwilio
- `ConversacionWhatsApp.checkin_actual` fija el evento exacto que el paciente
  está respondiendo y permite coordinar el bot con el cron.
- `RecepcionWebhookTwilio` conserva solo `MessageSid`, token idempotente,
  estado, intentos y timestamps. No guarda teléfono ni cuerpo del mensaje.

---

## CHECKLIST GENERAL DEL PROYECTO

### ✅ FASE 0 — Configuración Base y Seguridad — COMPLETADA
- [x] Instalar python-decouple y psycopg2-binary
- [x] Crear archivo .env con SECRET_KEY nueva (nunca a GitHub)
- [x] Agregar .env al .gitignore
- [x] Modificar settings.py → PostgreSQL + decouple + America/Bogota + es-co
- [x] Crear requirements.txt con pip freeze
- [x] Crear .env.example como plantilla del equipo
- [x] Crear CLAUDE.md con contexto clínico del proyecto
- [x] Crear BITACORA.md con historial del equipo
- [x] python manage.py check → 0 errores
- [x] Push a GitHub rama Desarrollo

---

### ✅ FASE 1 — Modelos Clínicos — COMPLETADA
- [x] Crear rama git sprint-1-modelos
- [x] Definir modelo Paciente en signos_sintomas/models.py
- [x] Definir modelo RegistroDiario con todas las variables clínicas
- [x] Definir modelo Alerta con tipos red flags Sugarbaker
- [x] Registrar los 3 modelos en admin.py con list_display y filtros
- [x] python manage.py check → 0 errores
- [x] Push models.py y admin.py a sprint-1-modelos
- [x] Merge sprint-1-modelos → Desarrollo (carpeta renombrada correctamente)
- [x] Instalar PostgreSQL 18 en máquina local
- [x] Crear base de datos sugarbaker_db en pgAdmin
- [x] Actualizar .env con contraseña real de PostgreSQL
- [x] Ejecutar python manage.py makemigrations → 0001_initial.py generado
- [x] Ejecutar python manage.py migrate → tablas creadas en PostgreSQL
- [x] Crear superusuario admin
- [x] Verificar modelos visibles en http://127.0.0.1:8000/admin/
- [x] Push migraciones a sprint-1-modelos
- [x] Merge final sprint-1-modelos → Desarrollo
- [x] Actualizar BITACORA.md con Sprint 1 completado

---

### ✅ FASE 2 — Motor de Alertas — COMPLETADA
> Mergeada a `Desarrollo` vía PR #1

- [x] Crear archivo signos_sintomas/alert_engine.py
- [x] Implementar función evaluar_registro(registro)
- [x] Regla 1: temperatura >= 38.0°C → crear Alerta tipo SEPSIS
- [x] Regla 2: drenaje purulento o fecaloide → crear Alerta FUGA_ANASTOMOTICA
- [x] Regla 3: sin gases 3 días consecutivos → crear Alerta ILEO_PARALITICO
- [x] Regla 4: vómito > 3 episodios → crear Alerta ILEO_PARALITICO
- [x] Escribir tests unitarios para las 4 reglas clínicas
- [x] Agregar pruebas de caso sano, valores límite y alertas combinadas
- [x] python manage.py test signos_sintomas → 7 pruebas OK
- [x] python manage.py check → 0 errores
- [x] Push seguro de sprint-2-alertas a GitHub
- [x] Revisión/aprobación del Arquitecto IA (post-merge — ver nota de proceso en BITACORA.md)
- [x] Merge sprint-2-alertas → Desarrollo (PR #1)
- [x] Resolver duplicación de modelos clínicos en home/models.py
- [x] Fix post-merge Regla 3 (dia_postoperatorio) — commit 01b8a47

---

### ✅ FASE 3 — Bot WhatsApp — COMPLETADA (mergeada a Desarrollo)
> Rama: `sprint-3-whatsapp` (mergeada a `Desarrollo` antes de `sprint-3-hardening`; confirmado por historial git)

**Paso 1 — Modelos (commit `68950ef`):**
- [x] Modelo ConversacionWhatsApp (persiste estado de la máquina de estados)
- [x] Campo cantidad_drenaje en RegistroDiario (cualitativo) + volumen_drenaje_ml opcional
- [x] Migración 0002 generada y aplicada

**Paso 2 — Bot (commit `109afc7`):**
- [x] Crear signos_sintomas/bot.py con máquina de estados (5 preguntas, lógica pura)
- [x] Pregunta 1: temperatura
- [x] Pregunta 2: dolor EVA
- [x] Pregunta 3A: aspecto drenaje / Pregunta 3B: cantidad drenaje
- [x] Pregunta 4 (estado gases+náuseas): presencia de gases y náuseas
- [x] Respuestas a dudas con predefinidos + knowledge_base.md placeholder
- [x] 18 pruebas unitarias OK + manage.py check sin errores

**Paso 3 — Webhook (commit `832873d`):**
- [x] Crear vista webhook en views.py (POST Twilio + validación firma + csrf_exempt)
- [x] Validación de firma fail-safe (default validar) / fail-clear (ImproperlyConfigured si falta token)
- [x] Configurar URL del webhook en signos_sintomas/urls.py (include del proyecto ya existía)
- [x] Config Twilio en settings.py (toggle + token + headers proxy ngrok) / .env.example / requirements.txt
- [x] Instalar twilio==9.10.9
- [x] Conectar: webhook → bot.procesar_mensaje → RegistroDiario → alert_engine
- [x] 22 pruebas unitarias OK (18 previas + 4 del webhook) + manage.py check sin errores

**Paso 4 — Conexión real Twilio (commit `de48db9` + prueba real):**
- [x] Activar sandbox WhatsApp de Twilio
- [x] Poner TWILIO_AUTH_TOKEN (primario, no Test) / TWILIO_ACCOUNT_SID reales en .env local
- [x] Exponer webhook con ngrok y configurar la URL en la consola de Twilio
- [x] Resolver 400 DisallowedHost → ALLOWED_HOSTS configurable por .env (.ngrok-free.dev)
- [x] Resolver 403 firma → usar Auth Token PRIMARIO (no Test Credentials)
- [x] Prueba end-to-end con WhatsApp real → RegistroDiario + Alerta verificados en BD
- [x] **Merge sprint-3-whatsapp → Desarrollo (con aprobación del Arquitecto)** — confirmado presente en `Desarrollo` (commits 68950ef, 109afc7, 832873d, de48db9), previo a la rama `sprint-3-hardening`

> **Resuelto:** la validación de firma detrás de ngrok funciona; el 403 NO era por
> la URL (build_absolute_uri() era correcta) sino por usar el Test Auth Token en
> vez del primario. Detalle completo en BITACORA.md (sesión Twilio+ngrok).
>
> **Diferido:** envío automático matutino 7-10 AM Bogotá → FASE 4 (Celery).
> Capa RAG sobre knowledge_base.md real → FASE 5 (pendiente acceso Drive médico).

---

### ✅ FASE 3.5 — Generalización de Alcance, Marca y Documentación — COMPLETADA

**Completado:**
- [x] Agregar campo `tipo_cirugia` a `Paciente` (descriptivo, sin lógica clínica)
- [x] Generalizar título y descripción del proyecto en CLAUDE.md (sin afiliación institucional)
- [x] Generalizar callout de agentes IA y base clínica de Regla 1 (corregir afirmación de evidencia HIPEC específica)
- [x] Generalizar menciones de marca Sugarbaker/Clínica Somer en código y templates de producción (models.py, bot.py, knowledge_base.md, index.html, contacto.html)
- [x] Renombrar base de datos local a `registro_postquirurgico_db`
- [x] Sincronizar bloque de `Paciente` en CLAUDE.md con el campo `tipo_cirugia`
- [x] Organizar auditoría de literatura en `docs/auditoria_literatura/` (4 documentos + README)
- [x] Reescribir sección "Auditoría de Literatura Clínica" en CLAUDE.md
- [x] Generalizar ROADMAP_MVP_SUGARBAKER.md (este archivo)
- [x] Actualizar tabla "Estado Actual del Proyecto" / "Punto actual" en CLAUDE.md

---

### ⏳ FASE 3.6 — Decisiones de Arquitectura Clínica del alert_engine — 5/5 VARIABLES COMPLETAS
> Basado en `docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md`.
> Workflow: decidir → implementar → verificar → documentar → repetir,
> una variable a la vez. Principio de diseño general: modelo de alta
> sensibilidad (Lee 2022, Outersterp 2025) — escalera BAJA/MEDIA/ALTA
> en vez de un solo nivel de alerta.

- [x] Drenaje — campo `tiene_drenaje` + escalera por aspecto (commits
  `3d98637`, `40ecbf8`, `552e419`, `38774c9`)
- [x] Temperatura — escalera ALTA/MEDIA por días calendario (commits
  `7c6817f`, `62aacbc`)
- [x] Gases — escalera BAJA/MEDIA/ALTA por días calendario consecutivos
  (commits `98c2bc6`, `c1b9ef3`)
- [x] Náuseas — suma diaria + persistencia en dos escalones (commits
  `edc2baa`, `9ee8e33`)
- [x] Dolor / gap `DOLOR_AGUDO` — escalera por `dia_postoperatorio` +
  tendencia alcista delta≥3 (commits `acd0d64`, `f0ba511`)
- [x] **Frecuencia de check-ins 2×/día — ARQUITECTURA CERRADA (Sprint 3).
  IMPLEMENTACIÓN → SPRINT 4.**
  La idea original ("un campo en ConversacionWhatsApp para mañana/tarde")
  se DESCARTÓ por insuficiente tras análisis de robustez (respuestas
  tardías, cruce de medianoche, mezcla AM/PM, escalar a N chequeos).

  DECISIONES CERRADAS — no se re-discuten en Sprint 4, se implementan:
  D1. El check-in es un EVENTO de primera clase → modelo nuevo
      `CheckInProgramado`, NO un campo en ConversacionWhatsApp.
  D2. El turno se etiqueta POR EVENTO (lo fija el prompt que el sistema
      envía), nunca por la hora en que el paciente responde. Chequeo 1 =
      mañana, chequeo 2 = tarde. El paciente responde cuando sea; la
      etiqueta no cambia.
  D3. Solo se persiste DATO CRUDO: `hora_programada` y `fecha_respuesta`.
      NO se hornea 'a tiempo/tarde'. Latencia, % tardío y promedios se
      DERIVAN en el dashboard (FASE 4) con umbrales parametrizables.
  D4. `estado` SÍ se persiste (PENDIENTE/COMPLETADO/NO_RESPONDIDO): el
      silencio es un hecho cualitativo, no una franja de latencia.
  D5. Escalable a N chequeos vía campo `orden` (1, 2, 3…). La etiqueta
      legible es para el humano; `orden` es la clave robusta del sistema.

  ESQUEMA ACORDADO de `CheckInProgramado` (especificación para Sprint 4):
      paciente         FK
      fecha_dia        DateField   (día calendario del evento; congelado
                                    al crear, NO recalculado en save —
                                    evita el bug de cruce de medianoche)
      orden            PositiveSmallInteger  (1, 2, …)
      etiqueta         CharField   ('MAÑANA' / 'TARDE')
      hora_programada  DateTimeField  (cuándo el sistema disparó el prompt)
      fecha_respuesta  DateTimeField null  (cuándo respondió el paciente)
      estado           CharField   ('PENDIENTE'/'COMPLETADO'/'NO_RESPONDIDO')
      registro         OneToOne→RegistroDiario, null
      Constraint: UniqueConstraint(paciente, fecha_dia, orden)
  Todo cálculo de fecha usa timezone.localdate() (regla del proyecto).

  DEPENDE DE SCHEDULER (Celery beat / cron): quien crea los eventos del
  día y cierra los vencidos (PENDIENTE→NO_RESPONDIDO) es una tarea
  programada, no el bot (el bot solo reacciona a mensajes entrantes).
  Por eso modelo + scheduler se construyen como UNA unidad en Sprint 4.
  → Handoff de implementación detallado en FASE 4.

- [x] **NUEVA alerta clínica: silencio del paciente.** RESUELTO en Sprint 4
  (Bloque 4, 26/06/2026, ver FASE 4 abajo): tipo `SILENCIO`, racha check a
  check (1→BAJA, 2 consecutivos→MEDIA, 3+→ALTA), implementado en
  `cerrar_checkins_vencidos`.

- [x] **Gating del alert_engine — 2 políticas.** RESUELTO en Sprint 4
  (Bloque 2B, 26/06/2026, ver FASE 4 abajo):
  - Deduplicación: Opción A+ — una alerta por tipo/día, escalamiento
    intra-día permitido (`_deduplicar()`).
  - Gating pre-operatorio: `VENTANAS_DOLOR[0]` ya cubre POD 0-2, sin
    cambio de lógica adicional.

**Camino de cierre del Sprint 3 (REVISADO — entregable del Paso 1 = la
DECISIÓN de arquitectura documentada, no el código de frecuencia):**
- [x] **Paso 1 (REDEFINIDO) — Arquitectura 2×/día cerrada y documentada.**
  Decisiones D1–D5 + esquema `CheckInProgramado` congelados arriba e
  trasladados a FASE 4 como ítems ejecutables. Implementación (modelo +
  scheduler + alerta de silencio + 2 gatings) → Sprint 4 por dependencia
  con Celery.
- [x] **Paso 1b — Mini-revisión de seguridad webhook/secretos Twilio.**
  SÍ va en Sprint 3: es el endpoint que ya existe, no depende del
  scheduler. Revisar validación de firma del webhook y manejo de
  secretos en views.py / settings.
  Resuelto en commit 22fb629: DEBUG default→False (fail-safe en prod) y
  Body truncado a 500 chars (defensa en profundidad). Auditoría confirmó:
  validación de firma Twilio ya existente y correcta, secretos vía .env
  fuera de git, 49/49 tests en verde. Sin deuda.
- [x] **Paso 2 — Variables nuevas de la literatura** (4/4, una por una,
  ciclo decidir→implementar→verificar→documentar):
  - [x] Tolerancia a líquidos — booleano, escalera MEDIA/ALTA,
    tipo INTOLERANCIA_ORAL (Regla 6)
  - [x] Hinchazón abdominal — escala nada/algo/mucho, alerta por
    empeoramiento entre días (Regla 7), tipo ILEO_PARALITICO
  - [x] Frecuencia cardíaca (FC) — entero, escalera por valor absoluto
    (101/110/150), tipo TAQUICARDIA (Regla 8)
  - [x] Frecuencia respiratoria (FR) — entero, SOLO dashboard, sin
    alerta (Outersterp 2025: 77% de falsas alertas venían del sensor de FR)
  - Nota: estado de herida (fotos) y antecedentes quedan FUERA de
    Sprint 3 (mejora futura / Sprint 4 respectivamente).
- [x] **Paso 3 — Revisión de cierre en dos frentes.** Claude Code audita
  coherencia interna y deuda técnica (alert_engine/modelos); Codex hace
  pasada adversarial de seguridad + escalabilidad; Claude (chat)
  sintetiza ambos en lista priorizada.
- [x] **Paso 4 — Resolver lo bloqueante, luego merge** sprint-3-whatsapp
  → Desarrollo con aprobación del Arquitecto.

---

### 🔒 FASE 3-HARDENING — Seguridad y Robustez pre-producción

> Rama: `sprint-3-hardening` (desde `Desarrollo` post-merge)
> Prerequisito: merge de `sprint-3-whatsapp` → `Desarrollo`.
> Detalle completo de cada hallazgo en `AUDITORIA_SPRINT3_CIERRE.md`.

**Grupo A — Obligatorio antes de pacientes reales:**
- [x] A1 — Conversación abandonada no reinicia al día siguiente
- [x] A2 — FC/FR obligatorias bloquean paciente sin dispositivo
- [x] A3 — Webhook sin idempotencia (MessageSid)
- [x] A4 — Sin `select_for_update()` en estado conversacional
- [x] A5 — Sin rate limiting en el webhook
- [x] A6 — `DEBUG=True` con Twilio/ngrok real activo

**Grupo B — Hardening de producción:**
- [x] B1 — settings.py sin configuración de producción
- [x] B2 — Sin LOGGING configurado (datos médicos en logs)
- [x] B3 — Path síncrono del webhook (timeout de Twilio)
- [x] B4 — `fecha_registro` sin índice eficiente para filtros
- [x] B5 — Admin en `/admin/` sin controles adicionales
- [x] B6 — Admin sin scoping por médico (Sprint 4)
- [x] B7 — Tests del webhook incompletos

**Grupo C — Backlog:**
- [x] C1 — Refactor `evaluar_registro()` monolítica
- [x] C2 — Choices sin `CheckConstraint` en BD
- [x] C3 — Django 6.0.5 → 6.0.6
- [x] C4 — Decimales truncados en parsers FC/FR
- [x] C5 — Mensaje de alerta no visible en list_display
- [x] C6 — 403 del webhook revela detalles internos
- [x] C7 — Endpoint de contacto sin rate limit

**Grupo D — Hallazgos auditoría post-hardening (Codex):**
- [x] D1 — Cache local-memory no comparte estado entre workers (A3/A5/C7 rompen en multi-worker)
- [x] D2 — Admin scoping sin `formfield_for_foreignkey` ni `has_*_permission` por objeto
- [x] D3 — `X-Forwarded-For` spoofeable en rate limit del formulario de contacto
  > ⚠️ **Pendiente de producción (FASE 5):** Nginx debe configurar
  > `proxy_set_header REMOTE_ADDR $remote_addr;` para que el rate limit funcione
  > correctamente con la IP real del cliente. El código Django usa `REMOTE_ADDR`
  > de forma segura — el ajuste requerido es exclusivamente de infraestructura.
- [x] D4 — `requirements.txt` interno con Django 6.0.5 / duplicado con el de raíz
- [x] D5 — Sin tests de acceso admin para médico no-superuser (changelist + URL directa)

---

### ✅ FASE 4 — Dashboard Oncólogo y Notificaciones — COMPLETADA (mergeada a Desarrollo 01/07/2026)
> Rama: `sprint-4-dashboard` — 6 bloques, 135 tests OK, mergeada (fast-forward) a `Desarrollo`

**Bloque 0 — Decisiones arquitectónicas (cerradas 26/06/2026):**
- [x] **0-① Fecha autoritativa:** Opción B — parámetro opcional
  `fecha_referencia: date` en `evaluar_registro()`. Default:
  `timezone.localdate(registro.fecha_registro)`. El bot pasa
  `fecha_referencia=checkin.fecha_dia` al completar el flujo. Corrige el
  bug de cruce de medianoche en reglas de persistencia (temperatura,
  gases, náuseas, líquidos, hinchazón).
- [x] **0-② Deduplicación de alertas:** Opción A+ — una alerta por
  tipo/día; si la nueva severidad supera la existente ese día, se crea
  igual (escalamiento intra-día permitido). Comparación con
  `_ORDEN_SEVERIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3}`.
- [x] **0-③ Alerta de silencio:** tipo `SILENCIO` (choice nuevo en
  `Alerta.tipo`). Racha contada check a check (mañana→tarde→mañana…):
  1 silencio → BAJA, 2 consecutivos → MEDIA, 3+ → ALTA. La racha se
  rompe con cualquier check-in COMPLETADO entre medias.
- [x] **0-④ Scheduler:** Opción A — management commands + cron del SO.
  Tres commands: `crear_checkins_diarios`, `cerrar_checkins_vencidos`,
  `enviar_recordatorios`. Monitoreo y evaluación de migración a Celery
  diferidos a Sprint 5.
- [x] **0-⑤ Gating POD 0:** Opción A — extender ventana de dolor POD
  1-2 a `dia_postoperatorio <= 2`. Justificación: en el flujo real del
  sistema dia_postoperatorio=0 es clínicamente imposible (cirugías de
  9+ horas — el alta ocurre como mínimo el día siguiente). El cambio es
  defensivo: la condición `<= 2` ya lo cubría; solo se actualizó el
  comentario en `VENTANAS_DOLOR`. Implementado en Bloque 2A (26/06/2026).

- [x] Personalizar Django Admin con colores según severidad de alertas
  (Bloque 5A — 26/06/2026: badge HTML inline, acción marcar_resuelta)
- [x] Crear vista detalle_paciente con historial y gráfica temperatura/dolor
  (Bloque 5B — 26/06/2026: historial_ultimos_7_dias como readonly_field en PacienteAdmin.
  **Nota de precisión (01/07/2026):** lo implementado es una tabla/lista de texto,
  NO una gráfica. La gráfica real queda pendiente — ver propuesta Chart.js en
  discusión de Sprint 5, sección de seguridad más abajo antes de implementarla.)
- [x] Implementar notificación al médico por email/SMS cuando hay alerta roja
  (Bloque 5C — 26/06/2026: signals.py post_save + on_commit; backend consola en dev)
- [x] **Implementación 2×/día (arquitectura CERRADA en FASE 3.6 — leer D1–D5
  y el esquema de `CheckInProgramado` ahí; aquí NO se re-decide, se ejecuta):**
  - [x] Crear modelo `CheckInProgramado` según el esquema acordado + migración.
    (Bloque 1 — 26/06/2026; migración 0012, 7 tests, admin con scoping)
  - [x] Scheduler — **DECISIÓN TOMADA (0-④):** management commands +
    cron del SO. Tres commands: `crear_checkins_diarios` (6:00 AM),
    `enviar_recordatorios` (7:00 AM), `cerrar_checkins_vencidos` (18:00
    y 06:00 AM). Cada command loguea resumen de ejecución. Horas de
    gracia antes de declarar vencido: 10 horas.
    (Bloque 4 — 26/06/2026: 3 management commands, 8 tests, migración 0013)
  - [x] Refactor de bot.py: la conversación se vincula al CheckInProgramado
    PENDIENTE del día (la conversación deja de decidir el turno).
    (Bloque 3 — 26/06/2026: _procesar_con_conv + _crear_registro reemplazados;
    guard por CheckInProgramado PENDIENTE; 3 tests nuevos; 122 tests OK)
  - [x] Alerta de silencio (NO_RESPONDIDO) — **DECISIÓN TOMADA (0-③):**
    tipo `SILENCIO` (choice nuevo). Racha check a check:
    1 → BAJA, 2 consecutivos → MEDIA, 3+ → ALTA.
    (Bloque 4 — 26/06/2026: cerrar_checkins_vencidos + modelo Alerta actualizado)
  - [x] Resolver los 2 gatings (Bloque 2B — 26/06/2026):
    - Deduplicación — **IMPLEMENTADA (0-②):** `_deduplicar()` en cada
      `Alerta.objects.create()` del engine. 6 tests `AlertDeduplicacionTests`.
    - Gating pre-operatorio — **CERRADO (0-⑤):** `VENTANAS_DOLOR[0]` ya
      cubre POD 0 con `dia_postoperatorio <= 2`. Solo comentario actualizado.
  - [x] **Deuda de diseño detectada en el cruce contra el código
    (detalle y razonamiento en BITACORA.md, entrada del 22/06/2026):**
    - [x] **Fecha autoritativa — IMPLEMENTADA (0-①, Bloque 2A, 26/06/2026):**
      `evaluar_registro(registro, fecha_referencia=None)`. Los 6 usos de
      `fecha_registro__date` en funciones privadas reemplazados por el
      parámetro. 3 tests `AlertFechaReferenciaTests`. Tests existentes: OK.
    - [x] **Reescribir el guard "un registro por día" → "por check-in".**
      Implementado en Bloque 3 (26/06/2026): `_procesar_con_conv` guarda
      por CheckInProgramado PENDIENTE/COMPLETADO, no por `fecha_ultimo_registro`.
    - [x] **Vínculo OneToOne transaccional.** Implementado en Bloque 3
      (26/06/2026): `_crear_registro` vincula RegistroDiario al CheckInProgramado
      PENDIENTE dentro de la misma transacción; lo marca COMPLETADO.
- [x] Demo funcional con 1 paciente ficticio para el equipo médico
  (Bloque 6 — 26/06/2026: seed_demo management command, demo_medico/demo1234)

**Decisiones de diseño pendientes (anotadas durante la implementación
del alert_engine, jun 2026):**
- [ ] Mecanismo de escalamiento automático: si una alerta MEDIA lleva
  mucho tiempo sin marcarse `resuelta`, ¿debería escalar sola a ALTA?
  Depende de los campos `resuelta`/`fecha_resolucion` que ya existen en
  el modelo `Alerta` pero no se usan activamente todavía.
  **(02/07/2026: diferido explícitamente a Sprint 6.)**
- [x] **Campo de "motivo de resolución" en `Alerta` (Bloque A, 02/07/2026).**
  Implementado: `motivo_resolucion` (7 opciones + "Otro") +
  `motivo_resolucion_detalle` (migración 0017). La acción "Marcar como
  resuelta" del Admin exige elegir el motivo en un formulario intermedio
  antes de resolver ("Otro" pide detalle); scoping por médico en cada paso.
  Útil para ajustar umbrales del alert_engine con datos reales. 6 tests.
- [x] **Duración del seguimiento del bot por paciente — RESUELTO (Sprint 5
  Bloque 1 + A-1, P-5).** `Paciente.activo` se desactiva automáticamente a
  los `DIAS_SEGUIMIENTO = 10` días postoperatorios vía el command
  `desactivar_pacientes_vencidos` (con guard `DIAS_GRACIA_INGRESO = 2` para
  ingresos tardíos), o manualmente por el médico desde el Admin. Corre por
  cron antes de `crear_checkins_diarios`.
- [x] **Interfaz del médico para gestionar alertas — RESUELTO (Sprint 4
  Bloque 5A + Sprint 5 Bloque A).** Marcar `resuelta`: acción "Marcar como
  resuelta" del Admin con formulario intermedio de motivo obligatorio.
  Distinguir falso positivo vs. caso real: opciones `FP_MEDICION` /
  `FP_RANGO` del `motivo_resolucion`. Visualización de la escalera
  BAJA/MEDIA/ALTA: badge de color por severidad (`severidad_badge`) en la
  lista de alertas + puntos rojos de alerta ALTA en las gráficas Chart.js
  (Bloque 4).

**Mejoras futuras (decisiones diferidas explícitamente, no bloqueantes):**
- [ ] **Vista de historial del paciente — versión completa (Sprint 5+):**
  Sprint 4 implementa el historial como sección dentro del admin
  (`change_view` de `PacienteAdmin`, Opción A). La versión completa sería
  una URL y template propios (`/signos_sintomas/paciente/<id>/historial/`)
  con gráfica de temperatura, EVA y alertas a lo largo del tiempo. Requiere
  decisión de si el dashboard médico permanece en Django Admin o evoluciona
  a una app independiente.
- [ ] **Integración IA/RAG en el chat del paciente (Sprint 5+):**
  Cuando el paciente escribe fuera de un check-in programado, hoy recibe
  un mensaje neutro + FAQ predefinidos. La mejora es conectar ese flujo a
  un agente IA con acceso a un sistema RAG (NotebookLM u otro) que responda
  dudas clínicas sobre el procedimiento con límites conservadores. El bot
  ya abre la puerta con "Si tienes alguna duda, puedes preguntarme aquí."
  — el mensaje no necesita cambiar cuando se implemente la capa IA.
  Prerrequisito: decisión de umbrales/contenido de `knowledge_base.md`
  (pendiente desde Sprint 3.5).

---

### ⏳ FASE 5 — Producción — EN CURSO
> Rama: `sprint-5-produccion` (creada desde `Desarrollo` post-merge Sprint 4)

**Decisiones de producto — confirmadas explícitamente por el Arquitecto en
sesión el 01/07/2026 (no re-discutir, ejecutar):**

| # | Decisión | Resolución |
|---|----------|-----------|
| P-1 | ¿Un médico o varios? | Un solo médico cliente. El equipo son admins; el médico llama si hay un problema. |
| P-2 | Titularidad de cuentas | Cuentas del proyecto (Railway, Twilio, Gmail) a nombre del equipo; se transfieren al médico cuando se venda. |
| P-3 | Mantenimiento en producción | El equipo mantiene con intervención mínima: si el cron falla → email automático → resolución en ~30 min. |
| P-4 | Identificador del paciente | Cédula obligatoria y única, además del teléfono. |
| P-5 | Desactivación de paciente | Automática a los 10 días postoperatorios, O manual por el médico — lo que ocurra primero. El scheduler no crea check-ins para pacientes inactivos. |
| P-6 | Email de notificación | Solo alertas ALTA disparan email; MEDIA y BAJA solo se ven en el dashboard. |
| P-7 | Check-ins por día | 2 check-ins/día fijos; el médico no los modifica desde el panel. |
| P-8 | Historial del paciente | Configurable por el médico desde el Admin; default 7 días. |
| P-9 | Visual del dashboard | Gráficas dentro del Admin (Chart.js), sin panel separado. |
| P-10 | Bot fuera de horario | Mantener las respuestas predefinidas actuales (`MSG_SIN_CHECKIN`) sin ampliar. RAG diferido a Sprint 6. |
| P-11 | Emojis en el bot | Eliminar todos los emojis de los mensajes del bot. |
| P-12 | Landing page | Página de presentación personal del médico (estática, contenido lo define él) — Sprint 5. |
| P-13 | RAG/MCP | Sprint 6, con corpus de `knowledge_base.md` validado por el médico — no antes. |
| P-14 | OpenMed | No se integra ahora; referencia futura para anonimización PII (exportación, HABEAS DATA) en Sprint 6. |
| P-15 | HABEAS DATA | Sprint 5 — consentimiento informado mínimo antes de que cualquier paciente real use el sistema. |

**Notas de implementación de las decisiones anteriores:**
- P-4/P-5 requieren migración en `models.py` (campo `cedula`, lógica de
  desactivación) — ver bloque de tareas abajo.
- P-9 requiere revisar primero la nota de seguridad de esta sesión: los
  datos que alimentan las gráficas deben ir con `json.dumps()`, nunca
  interpolados directo en un f-string dentro de `<script>`.
- P-15 (HABEAS DATA) bloquea el uso con pacientes reales, no el desarrollo
  del resto de Sprint 5. Requiere texto de consentimiento redactado o
  validado por el médico — no inventar contenido clínico/legal.

**Preguntas de arquitectura — resueltas en sesión (01/07/2026):**
- [x] Ubicación del cron: **Linux** (Railway/Render, ya decidido como destino
  de deploy — cron del contenedor o el servicio nativo de "Cron Jobs" de la
  plataforma). Windows Task Scheduler queda descartado: el plan es cuentas
  del proyecto en la nube (P-1/P-2), no correr desde la máquina de Alejandro.
- [x] Proveedor SMTP real: **Gmail con contraseña de aplicación** —
  coherente con P-2/P-3 (cuentas del equipo, mantenimiento mínimo) y con
  volumen bajo de correo (solo alertas ALTA, un médico).

**Tareas de código (orden sugerido):**
- [x] **Bloque 1 (01/07/2026):** Campo `cedula` en `Paciente` — `unique=True`,
  `null=True` (no rompe pacientes/tests previos), `blank=False` (obligatorio
  en formularios nuevos). Migración `0014_paciente_cedula`. Agregado a
  `list_display`/`search_fields` en `PacienteAdmin` (P-4).
- [x] **Bloque 1 (01/07/2026):** Management command
  `desactivar_pacientes_vencidos` — `DIAS_SEGUIMIENTO=10`, usa
  `timezone.localdate()`, soporta `--dry-run`, idempotente (solo actúa
  sobre `activo=True`). La desactivación manual desde el Admin sigue
  disponible sin cambios (P-5). 9 tests nuevos (`PacienteCedulaTests`,
  `DesactivarPacientesVencidosTests`). **144 tests OK.**
- [x] **Bloque 2 (01/07/2026):** Emojis eliminados de todos los mensajes
  del bot (`MSG_*` en `bot.py`). Las preguntas numeradas (`1️⃣`…`🔟`) pasan
  a `"1. "`…`"10. "`; el resto de emojis decorativos (🌿✅👋) se quitan sin
  reemplazo. Sin cambios de contenido clínico ni de la máquina de estados.
  Tests existentes usan `assertIn` con substrings — no requirieron cambios,
  **144 tests OK** (P-11).
- [x] **Bloque 3A (01/07/2026):** Filtros en `PacienteAdmin` — `activo`,
  `tipo_cirugia`, `medico_responsable` (ya existía) y `TieneAlertaActivaFilter`
  (`SimpleListFilter` nuevo: "Con alertas sin resolver" / "Sin alertas
  pendientes", vía `alertas__resuelta` — corregido el `related_name` real
  del modelo, que es `alertas`, no `alerta` como en el borrador original).
- [x] **Bloque 3B (01/07/2026):** Historial configurable por días (P-8).
  `_historial_7_dias` renombrada a `_historial_paciente(paciente, dias=7)`.
  Selector de rango (3/7/10 días desde Loop 3, 19/07/2026) como enlaces
  `?dias=N` en el propio
  HTML del campo — el médico cambia el rango recargando la misma página
  de detalle. `PacienteAdmin.get_readonly_fields()` captura `?dias=` de la
  URL y acepta solo 3/7/10 porque los `readonly_fields` solo reciben `obj`, no
  `request`. 8 tests (filtro de alertas + selector e inclusión exacta).
  **150 tests OK.**
- [x] **Bloque 4 (01/07/2026, con rediseño post-revisión visual):** Gráficas
  Chart.js en la ficha del paciente (P-9) — 3 gráficas separadas
  (temperatura con línea punteada de umbral 37.9°C, dolor EVA 0-10, FC con
  líneas punteadas de umbral 101/110 lpm), cada una con su propio
  `new Chart()`, no una sola gráfica multi-eje.
  - **Selector de período independiente del historial:** los 3 rangos
    (3/7/10 días desde Loop 3, 19/07/2026) se precalculan en el servidor y
    se embeben una sola
    vez como JSON; el médico cambia de rango en el navegador sin recargar
    la página. El selector del historial en tabla (Bloque 3B, `?dias=`)
    sigue siendo aparte, con recarga de página.
  - **Puntos rojos = alerta ALTA sin resolver** en ese registro exacto,
    vía `registro_origen` (no por coincidencia de fecha).
  - **Turno (M/T) por `CheckInProgramado.etiqueta` real**, no por la hora
    de respuesta del paciente — corrige un enfoque propuesto que violaba
    la decisión D2 ya cerrada (Sprint 3.6: "el turno lo fija el evento,
    nunca la hora en que el paciente responde"). Fallback por hora solo
    para registros legado sin check-in vinculado.
  - **Bug de zona horaria corregido:** el fallback por hora y las fechas
    del historial en tabla usaban `fecha_registro.hour`/`.strftime()`
    crudo — con `USE_TZ=True` eso está en UTC, no en hora de Bogotá. Un
    registro de las 8am Bogotá se habría clasificado como tarde. Ahora
    usa `timezone.localtime()`.
  - **FC nula viaja como `null` (hueco en la línea), nunca como `0`** —
    ya estaba bien desde la primera versión (el "bug" reportado en la
    instrucción externa no existía en el código real).
  - Todos los datos van por `json.dumps()` en un único objeto `DATOS`,
    nunca interpolados directo en el HTML/JS.
  - Simplificación consciente: las "bandas de color" de FC quedaron como
    líneas de umbral punteadas, no zonas de fondo — evita depender de un
    plugin adicional de Chart.js solo por estética. Versión de Chart.js
    fijada (`4.4.0`, no "latest") para evitar romperse con actualizaciones
    del CDN.
  - **9 tests nuevos** (`GraficaSignosVitalesTests`, reemplazan los 3 de
    la primera versión): sin registros no carga Chart.js; FC nula
    serializa `null`; los 3 períodos llegan precalculados; turno por
    check-in vinculado (no por hora); respaldo por hora en zona horaria
    correcta para datos legado; punto de alerta ALTA marcado/no marcado;
    versión fija del CDN; selector de gráfica independiente del
    historial. **159 tests OK.** `manage.py check` limpio.
  - **Evidencia histórica de la versión 01/07/2026:** con la ventana de 7
    días solo se ven 3 de los 10 registros del paciente demo — no es un
    bug, es correcto: `seed_demo` fija fechas del 17-26 de junio de 2026,
    y con la fecha real del sistema (01/07/2026) esos registros quedan
    entre 5 y 14 días atrás. Con "14 días" o "30 días" se ven los 10.
  - **No verificado:** la renderización real de Chart.js en un navegador
    (fuera de las herramientas disponibles en esta sesión) — sí se
    verificó con el test client de Django que el HTML/JSON generado es
    válido y con los valores esperados.
  - **Hallazgo colateral — resuelto en A-3 (02/07/2026):** `demo_medico`
    (creado por `seed_demo`) era superusuario — veía *todo* `/admin/`
    (Usuarios, Grupos, pacientes de cualquiera), a diferencia de una
    cuenta de médico real (staff, no-superuser). `seed_demo` ahora crea
    `demo_medico` con `is_staff=True, is_superuser=False`, representando
    la experiencia real del médico.
- [x] **Desplegado en Railway con PostgreSQL + Redis en la nube (06/07/2026).**
  App viva en `registropostquirurgico-production-1f96.up.railway.app`. Build
  con **Dockerfile** (`python:3.13-slim`) tras descartar Railpack (ignora
  `nixpacks.toml`) y Nixpacks (`pip: command not found` por Nix). Migraciones
  aplicadas, estáticos con WhiteNoise, **bot de WhatsApp respondiendo
  end-to-end** (Sandbox de Twilio), acceso al Admin resuelto con el comando
  `crear_admin`, y limpieza de seguridad hecha. Detalle completo (incluida la
  causa raíz: placeholders `< >` pegados literalmente en las variables) en
  BITACORA.md, sesión 06/07/2026. **194 tests OK.** **Pendiente del despliegue:
  cron jobs** (ver `docs/cron_setup.md` + Bloque 6, abajo).
- [x] **Bloque 5 (01/07/2026):** SMTP real. Variables `EMAIL_*` agregadas
  al `settings_production.py` **existente** (append, no reemplazo —
  conserva DEBUG=False, HSTS, cookies seguras y cache Redis del Sprint
  3-Hardening). `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` sin default en
  `config()` → falla fuerte (fail-clear) si faltan en el `.env` de
  producción, en vez de arrancar sin poder enviar correo.
  `DEFAULT_FROM_EMAIL` con default = `EMAIL_HOST_USER`. Plantilla agregada
  a `.env.example` (sin secretos reales).
  **Prueba real end-to-end:** alerta ALTA real disparada con
  `DJANGO_SETTINGS_MODULE=...settings_production` → correo recibido en
  `seguimientolionalejo@gmail.com`. Confirmado por el Arquitecto.
  Datos de prueba (paciente, registro, alertas, usuario de prueba)
  eliminados después de confirmar. **159 tests OK** (sin tests nuevos —
  el envío real de SMTP no se puede probar con `manage.py test`, que
  usa el backend de consola; la lógica del signal ya tenía cobertura
  desde Sprint 4, `AlertaEmailNotificacionTests`).
  **Mejora implementada en A-4 (02/07/2026):** el cuerpo ahora incluye
  teléfono y cédula del paciente y la hora en zona Bogotá
  (`timezone.localtime`, no el datetime crudo en UTC).
- [x] **Bloque 6 (01/07/2026):** `docs/cron_setup.md` — creado. Cubre los
  **4** management commands (los 3 originales + `desactivar_pacientes_vencidos`
  del Bloque 1), horarios en UTC, `MAILTO` para fallos, y el orden
  obligatorio `desactivar_pacientes_vencidos` **antes** de
  `crear_checkins_diarios` (nunca al revés). **Bug de documentación
  corregido de paso:** el docstring de `desactivar_pacientes_vencidos.py`
  decía que debía correr *después* de `crear_checkins_diarios`, lo cual
  contradice su propio propósito (evitar que un paciente reciba un
  check-in el día que vence) y el orden que ya prueba
  `test_scheduler_no_crea_checkins_tras_desactivacion`. Corregido el
  comentario para que diga "antes", no "después".
- [x] **Bloque 6 (01/07/2026):** `docs/transferencia_cuentas.md` —
  creado. Protocolo de transferencia (P-1/P-2/P-13), tabla de cuentas del
  proyecto, manual mínimo de operación para el médico, y nota de que
  HABEAS DATA (Bloque 7) bloquea el uso con pacientes reales, no el resto
  del despliegue técnico. **159 tests OK**, `manage.py check` limpio.
- [x] **Correcciones pre-Bloque 7, A-1 a A-4 (02/07/2026):**
  - **A-1:** guard `DIAS_GRACIA_INGRESO=2` en `desactivar_pacientes_vencidos`
    (no desactiva hasta que el paciente lleve ≥2 días registrado en el
    sistema) + advertencia (no bloqueante) en `PacienteAdmin.save_model`
    al crear un paciente con `dia_postoperatorio >= 8`. Decisión del
    Arquitecto: implementar ambas opciones, no son excluyentes.
  - **A-2:** `Paciente.clean()` exige cédula solo para pacientes nuevos
    (`pk is None`). **Bug real corregido durante la implementación:** el
    diseño original dejaba `cedula` con `blank=False` a nivel de campo,
    lo que rompía `full_clean()` para *cualquier* paciente sin cédula,
    incluidos los migrados — no solo los nuevos. Corregido con
    `blank=True` a nivel de campo (migración `0015`) + la exigencia real
    viviendo en `clean()`.
  - **A-3:** `seed_demo` aborta si `DEBUG=False` (evita crear una cuenta
    con contraseña conocida en producción por error). Su usuario demo
    pasó de `create_superuser` a `create_user(is_staff=True,
    is_superuser=False)` — resuelve también el hallazgo pendiente del
    Bloque 4 sobre que `demo_medico` no representaba la experiencia real.
  - **A-4:** email de alerta ALTA mejorado (ver nota en Bloque 5 arriba).
  - **12 tests nuevos. 171 tests OK** tras esta corrección. `manage.py check`
    limpio.
- [x] **Bloque 7 — HABEAS DATA (02/07/2026):** `consentimiento_informado`
  (default `False`) y `fecha_consentimiento` en `Paciente` (migración
  `0016`), auto-registrada/limpiada en `PacienteAdmin.save_model` en
  sincronía con el checkbox; `fecha_consentimiento` es readonly en el
  Admin. Guard en `bot.procesar_mensaje`: paciente sin consentimiento
  recibe mensaje neutro y no entra a la máquina de estados. Texto de
  `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` confirmado como ya
  aprobado por el Arquitecto en sesión — copiado sin modificar (P-15).
  **6 tests nuevos.** El guard rompió 22 tests preexistentes del bot/webhook
  (fixtures de paciente que no marcaban el consentimiento) — corregidos
  agregando `consentimiento_informado=True` en los fixtures afectados, sin
  tocar la lógica del guard. **177 tests OK**, `manage.py check` limpio.
  **Pendiente antes de pacientes reales:** completar los campos entre
  corchetes del formato (datos del médico/institución) antes de
  imprimirlo.
- [x] **Bloque A — Motivo de resolución en Alerta (02/07/2026):** ver
  detalle en "Decisiones de diseño pendientes" arriba (checkbox marcado).
  `motivo_resolucion` + `motivo_resolucion_detalle` (migración 0017),
  formulario intermedio obligatorio en el Admin. **183 tests OK.**
  - [x] **Hardening Loop 1:** formulario de alerta completamente de solo lectura,
    cierre obligatorio con fecha/motivo a nivel de base de datos y migración
    conservadora de cierres históricos como `LEGACY` (migración 0019).
- [x] **Bloque B — Tono de cierre del bot según severidad (02/07/2026):**
  el check-in con alerta MEDIA/ALTA cierra con recomendación de acción al
  paciente (MEDIA: contactar médico; ALTA: urgencias), sin revelar tipo de
  alerta ni valores. `evaluar_registro` pasó de `on_commit` a síncrono
  dentro de `_crear_registro` (savepoint defensivo — un fallo del engine
  nunca pierde el reporte del paciente). **191 tests OK.** **Pendiente:**
  prueba manual real por WhatsApp de los mensajes MEDIA/ALTA (canal Twilio,
  fuera de `manage.py test`).
- [x] **Bloque C — Limpieza de Sugarbaker en index.html (02/07/2026):
  no-op verificado.** No existe ninguna mención de "Sugarbaker"/"HIPEC" en
  `index.html` ni en `home`; el único uso es la opción legítima
  `sugarbaker_hipec` de `tipo_cirugia` (no se toca) y migraciones
  (inmutables). Nada que limpiar; sin cambios de código.
- [ ] Configurar monitoreo externo básico (ping al servidor cada 5 min)
  para detectar caídas totales independientemente del cron
- [x] IP real para rate limit en Railway: `X-Real-IP` solo se acepta con
  `TRUST_RAILWAY_PROXY=True`, una marca `X-Railway-Edge` válida y una IP bien
  formada; `X-Forwarded-For` se descarta por ser spoofeable.
- [x] Landing page de presentación del médico (P-12) — hecha en la app `home`
  (Django, no estática): `/` como landing del médico + sistema de diseño
  compartido (`base.html` + `static/home/css/site.css`); contenido en
  marcadores `[corchetes]` + flag `MOSTRAR_AVISO_BOCETO`. **Pendiente:** datos
  reales del médico y deploy a Railway.
- [x] Demo del dashboard — comando `seed_demo_produccion` (seguro para prod,
  2 pacientes de ejemplo, reversible con `--limpiar`)
- [x] Panel del médico (Admin): branding "calma clínica" + tablero de triage
  como índice (sin forkear el admin; se conservan listas/filtros/gráficas)
- [x] Agrupación de alertas por problema: una alerta abierta por (paciente,tipo)
  con contador `veces` (badge ×N); correo ALTA solo al escalar (migración 0018)
- [x] **Loop 4 — entrega durable de alertas ALTA:** outbox
  `NotificacionAlerta`, timeout, reintentos crecientes y procesamiento fuera
  del webhook. Correo genérico sin datos del paciente (migración 0024).
- [x] **Canal real de correo en Railway:** Resend por API HTTPS activo con
  idempotencia. El aviso controlado de la alerta demo #90 fue aceptado y
  recibido en `seguimientolionalejo@gmail.com` el 21/07/2026.
- [x] **Loop 4 — hardening web/dependencias:** Django 6.0.7, dependencias
  directas fijadas y auditadas, CSP activo y Chart.js 4.5.1 servido localmente.
- [x] **Loop 5 — validación:** firma Twilio positiva, SID concurrente,
  concurrencia de outbox, rollback parcial del motor y flujo completo por
  webhook cubiertos. Carga local: 50 pacientes concurrentes, 550 webhooks y
  50 registros en 5,03 s, sin superar 15 s por solicitud. Suite: **280 OK**.
- [x] **Loop 6 — cierre técnico:** flujos reales MEDIA y ALTA verificados con
  `medico_piloto`; panel y correo ALTA confirmados; respuesta silenciosa del
  rate limit corregida; reintento durable de Resend comprobado; Requests 2.33.0
  y `pip-audit` limpio; smoke de producción correcto. Los datos ficticios se
  eliminaron. **280 tests OK.** Auditoría independiente pre-merge pendiente.
- [x] Comando idempotente `crear_medico` + grupo "Médicos" de privilegio mínimo
- [x] **Hardening Loop 2 — confiabilidad del webhook y alertas:** recibo
  persistente por `MessageSid` en PostgreSQL (sin teléfono ni Body), reintento
  después de error, estado PENDIENTE/COMPLETADA/ERROR por `RegistroDiario`,
  comando `reintentar_evaluaciones_alertas`, unicidad de alerta abierta bajo
  concurrencia y vínculo de la conversación al check-in exacto. Punto de
  restauración publicado en `sprint-5-produccion` hasta `442ccc2` (18/07/2026).
- [x] **Loop 3 — experiencia médica (cerrado 19/07/2026):** auditoría real con cuenta
  médica, navegación y revisión responsiva del Admin.
  - [x] Primera iteración segura: contraste y ancho del tablero, pendientes
    acumulados, prioridad por gravedad/recurrencia/última detección, periodos
    exactos 3/7/10, historial activado/desactivado, seed demo íntegro y flujo
    de resolución sin encabezado duplicado.
  - [x] Propiedad por médico de `MensajeContacto`: destinatario configurable
    por `MEDICO_CONTACTO_USERNAME`, scoping en Admin/tablero y mensajes
    anteriores sin asignar visibles solo para superusuario (`home.0002`).
  - [x] Trazabilidad de cada detección nueva que compone ×N mediante
    `DeteccionAlerta`; fuente única e idempotente por registro/check-in,
    inline de solo lectura y resumen explícito del contador histórico sin
    backfill ficticio (`signos_sintomas.0022`).
  - [x] Panel de mensajes de contacto debajo de Silencios y filtro de fecha
    renombrado a "Todas las fechas". Revisión visual escritorio/móvil sin
    desbordamientos.
  - [x] Cierre UX posterior: el detalle dice "Detecciones de la alerta" sin
    lenguaje interno de loops; se verificó el ordenamiento real de las tablas
    y se robusteció la limpieza/recreación de datos demo con FKs protegidas
    (`signos_sintomas.0023`). **256 tests OK.**
    Commit base del Loop 3: `5ad1b71`.
- [x] Desplegar Loops 1-3 en Railway: commit `de06ff8`, migraciones hasta
  `signos_sintomas.0023` + `home.0002`, web y dos cron en `SUCCESS`, HTTPS 200
  y `check --deploy` limpio. Demos remotos renovados (2 activos, 10 alertas
  abiertas, 36 detecciones). `SECRET_KEY` remoto rotado (19/07/2026).
- [x] Cron frecuente verificado en Railway (`*/5 * * * *`):
  `cron_operativo` ejecuta cierre idempotente, reintento del motor y bandeja de
  notificaciones. Temporalmente reutiliza `cron-tarde` por el límite del plan.
- [ ] Al mejorar el plan de Railway, crear un servicio `cron-operativo`
  independiente y restaurar `cron-tarde` a su horario original de las 6 PM.
- [x] Provisionar y verificar en Railway la cuenta `medico_piloto` con
  privilegio mínimo y correo configurado. Los demos y pacientes ficticios de
  las validaciones ya fueron eliminados.
- [ ] Entrega final al equipo médico

**Diferido explícitamente a Sprint 6:**
- [ ] Integrar capa RAG/MCP para respuestas del bot (P-13) — prerrequisito:
  corpus de `knowledge_base.md` validado por el médico
- [ ] OpenMed para anonimización PII de exportación (P-14)

---

## Requisitos para un PILOTO REAL con pacientes

> Estado a 06/07/2026: la app **ya está desplegada y probada** en Railway con
> el Sandbox de Twilio. Esto es lo que falta para pasar de "pruebas" a
> "pacientes reales". Ninguno bloquea seguir probando el sistema con el Sandbox.

**Infraestructura / operación (con costo):**
- [ ] **Dominio propio para correo:** verificarlo en Resend y configurar
  SPF/DKIM/DMARC antes del piloto. La entrega con `onboarding@resend.dev`
  funciona, pero la prueba del 21/07/2026 llegó a spam.
- [ ] **Plan de pago en Railway.** Además de sostener web + Postgres + Redis,
  debe permitir separar el cron operativo frecuente. El plan actual rechazó
  un tercer cron por límite de recursos.
- [x] **Cron jobs en Railway:** `cron-manana` (`0 11 * * *` UTC) ejecuta
  `cron_matutino`; `cron-tarde` está reutilizado temporalmente cada 5 minutos
  para `cron_operativo` (cierre + reintento + notificaciones). Verificado en
  vivo el 19/07/2026.
- [ ] **Después del upgrade del plan:** crear `cron-operativo` como servicio
  dedicado cada 5 minutos y devolver `cron-tarde` a `0 23 * * *` UTC como
  respaldo de cierre.

**Canal de WhatsApp (con costo y aprobación):**
- [ ] **Pasar del Sandbox de Twilio a la API de WhatsApp Business.** El Sandbox
  es solo para pruebas (regla de 72 h por teléfono, número compartido). Para
  pacientes reales se requiere: número propio aprobado por Meta/WhatsApp,
  **facturación de Twilio** (costo por conversación), y **plantillas
  pre-aprobadas** para mensajes iniciados por el sistema.
- [ ] **Implementar el envío saliente real de Twilio** en `enviar_recordatorios`
  (hoy es un stub). Solo necesario si se quieren recordatorios proactivos; hoy
  el sistema es reactivo (responde cuando el paciente escribe primero).

**Legal / clínico:**
- [ ] **HABEAS DATA:** completar los `[corchetes]` de
  `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` con los datos reales del
  médico/institución, imprimirlo y firmarlo con cada paciente antes de marcar
  `consentimiento_informado=True`.

**Validación end-to-end (con el Sandbox alcanza):**
- [x] Crear un **paciente de prueba** en el Admin (con `consentimiento_informado`),
  correr `crear_checkins_diarios`, y hacer una **prueba real de WhatsApp
  completa**. Ejecutada el 21/07/2026 con valores normales: registro y turno
  tarde completados, motor en `COMPLETADA`, sin alerta clínica. El turno mañana
  creado a las 18:00 fue cerrado por cron con `SILENCIO/BAJA`, comportamiento
  operativo esperado. Todos los datos ficticios se eliminaron al terminar.
- [x] Prueba manual del **tono del bot** (Bloque B): alerta MEDIA provocada por
  drenaje turbio y alerta ALTA por temperatura de 38,5 °C. Ambos mensajes de
  cierre `MSG_CIERRE_ALERTA_*` se recibieron sin exponer tipo ni valor clínico.
  Registro, check-in, motor y alertas quedaron coherentes y luego se limpiaron.

**Limpieza técnica menor (no bloqueante):**
- [ ] Revisar/limpiar el dominio duplicado en Railway (si quedaron dos).
- [ ] `inicio_entornoR.bat` apunta a un venv (`entorno_registro`) que ya no
  existe; recrear el venv o borrar el `.bat` (hoy todo corre en el Python
  global).

---

## Convenciones del Equipo

- **Idioma del código:** español (variables, comentarios, commits)
- **Rama principal:** `Desarrollo` — nadie trabaja directo aquí
- **Una rama por sprint:** sprint-1-modelos, sprint-2-alertas, etc.
- **Commits:** formato `feat:`, `fix:`, `docs:` + descripción en español
- **El .env nunca se sube a GitHub**
- **Ningún código clínico entra a Desarrollo sin aprobación del Arquitecto**
- **DEFAULT_AUTO_FIELD:** BigAutoField (configurado en settings.py)
- **Zona horaria:** America/Bogota (crítico para timestamps clínicos)

---

## Comandos Frecuentes

```bash
# Navegar al proyecto (manage.py siempre aquí)
cd C:\Users\león\Documents\ProyectoLeonAlejo\Registro_Post_Quirurgico\Registro_Post_Quirurgico

# Activar entorno virtual (si está configurado)
..\entorno_registro\Scripts\activate

# Verificar que Django no tiene errores
python manage.py check

# Crear migraciones después de cambiar models.py
python manage.py makemigrations

# Aplicar migraciones a la base de datos
python manage.py migrate

# Crear superusuario para el panel admin
python manage.py createsuperuser

# Correr el servidor de desarrollo
python manage.py runserver
# Luego abrir: http://127.0.0.1:8000/admin/

# Generar nueva SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Ver estado de ramas
git branch -a

# Cambiar de rama
git checkout nombre-de-rama

# Subir cambios
git add .
git commit -m "tipo: descripción"
git push origin nombre-de-rama
```

---

## Estado del .env requerido (cada desarrollador tiene el suyo)

```env
SECRET_KEY=clave-generada-con-get_random_secret_key
DEBUG=True
DB_NAME=registro_postquirurgico_db
DB_USER=postgres
DB_PASSWORD=contraseña-real-de-postgresql-local
DB_HOST=localhost
DB_PORT=5432
```

---

## Glosario Técnico (para el Arquitecto)

| Término | Qué es en términos clínicos |
|---------|----------------------------|
| Modelo Django | Plano de una tabla — define qué campos tendrá |
| Migración | Construcción real de la tabla en PostgreSQL |
| makemigrations | Genera el archivo de instrucciones de construcción |
| migrate | Ejecuta la construcción en la base de datos |
| ForeignKey | Relación entre tablas (como vincular un registro a su paciente) |
| PROTECT | No permite borrar un paciente que tenga registros asociados |
| admin.py | Configura qué ve el oncólogo en el panel /admin/ |
| list_display | Columnas visibles en la tabla del panel admin |
| list_filter | Filtros laterales en el panel admin |
| runserver | Arranca el servidor local para probar el sistema |
| webhook | URL que Twilio llama cuando el paciente manda un WhatsApp |
| Branch/Rama | Versión paralela del código para trabajar sin afectar lo estable |
| Merge | Fusionar los cambios de una rama a otra |

---

*Última actualización: 21/07/2026. Sprint 5 en cierre sobre
`sprint-5-produccion`: Loops 1-6 completados técnicamente, 280 tests OK y
producción validada con flujos NORMAL/MEDIA/ALTA. Siguiente paso: ejecutar la
auditoría independiente descrita en `AUDITORIA_PRE_MERGE_LOOPS_1_6.md`, resolver
hallazgos bloqueantes y solo entonces preparar el PR hacia `Desarrollo`. Los
requisitos externos de WhatsApp Business, correo con dominio propio, plan
Railway, Habeas Data y datos definitivos del médico siguen siendo compuertas
separadas para el piloto real.*
