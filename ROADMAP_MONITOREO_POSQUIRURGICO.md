# ROADMAP MVP — Sistema de Monitoreo Posquirúrgico Remoto

> **Para agentes IA:** Lee este archivo completo antes de sugerir cualquier acción.
> Contiene el contexto clínico, el estado actual del proyecto, y los pasos pendientes.
> El repositorio es: https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
> Rama principal: `Desarrollo` | Rama activa: `sprint-3-whatsapp` (funcional end-to-end, merge pendiente — ver Sprint 3.5)

---

## Contexto del Proyecto

Sistema de monitoreo remoto posquirúrgico para pacientes en recuperación de
cirugía colorrectal — incluyendo casos Sugarbaker/HIPEC como uno de los tipos
de procedimiento soportados, sin ser exclusivo de ellos. El paciente interactúa
exclusivamente por WhatsApp. Un bot le hace preguntas diarias de telemetría. El
sistema clasifica los datos, detecta alertas rojas automáticas y notifica al
médico a través de un dashboard en Django Admin.

**Stack:** Django 6.0.5 + PostgreSQL 18 + WhatsApp Bot (Twilio) + Python 3.13
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

```
Registro_Post_Quirurgico/              ← raíz del repositorio
├── CLAUDE.md                          ← contexto para agentes IA
├── BITACORA.md                        ← historial del equipo
├── .gitignore
├── inicio_entornoR.bat
└── Registro_Post_Quirurgico/          ← proyecto Django (manage.py aquí)
    ├── .env                           ← secretos locales (NUNCA a GitHub)
    ├── .env.example                   ← plantilla de variables
    ├── requirements.txt
    ├── manage.py
    ├── Registro_Post_Quirurgico/      ← configuración Django
    │   ├── settings.py                ← PostgreSQL + decouple + Bogotá
    │   ├── urls.py
    │   └── wsgi.py
    ├── home/                          ← app portal web
    │   ├── views.py                   ← index y contacto
    │   ├── urls.py
    │   └── templates/home/
    │       ├── index.html
    │       └── contacto.html
    └── signos_sintomas/               ← app núcleo clínico
        ├── models.py                  ← ✅ Paciente, RegistroDiario, Alerta, ConversacionWhatsApp
        ├── admin.py                   ← ✅ panel del oncólogo configurado
        ├── migrations/
        │   ├── 0001_initial.py        ← ✅ tablas creadas en PostgreSQL
        │   └── 0002_...cantidad...    ← ✅ cantidad_drenaje + ConversacionWhatsApp
        ├── views.py                   ← ⏳ paso 3: webhook WhatsApp
        ├── urls.py                    ← ⏳ paso 3: rutas
        ├── alert_engine.py            ← ✅ creado y mergeado (Sprint 2)
        ├── knowledge_base.md          ← ✅ placeholder (RAG diferido a FASE 5)
        └── bot.py                     ← ✅ máquina de estados, 18 tests OK (Sprint 3)
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
| medico_responsable | CharField(200) | Médico a cargo |
| activo | BooleanField | Desactivar al terminar seguimiento |
| fecha_registro | DateTimeField auto | Timestamp automático |

### RegistroDiario
| Campo | Tipo | Descripción |
|-------|------|-------------|
| paciente | ForeignKey(Paciente) PROTECT | No borrar paciente con registros |
| temperatura | DecimalField(4,1) | °C — alerta si >= 38.0 |
| dolor_eva | PositiveSmallIntegerField | Escala 1-10 |
| volumen_drenaje_ml | PositiveIntegerField nullable | ml |
| tiene_drenaje | BooleanField nullable | null=no capturado, False=sin drenaje, True=con drenaje |
| aspecto_drenaje | CharField choices | seroso/hemático/turbio/purulento/fecaloide/sin_drenaje |
| presencia_gases | BooleanField | Tránsito intestinal |
| episodios_nauseas | PositiveSmallIntegerField | Episodios en 24h |
| tolero_liquidos | BooleanField nullable | null=no capturado, False=no toleró, True=toleró |
| hinchazon_abdominal | CharField choices nullable | nada/algo/mucho — evaluado por empeoramiento entre días |
| fecha_registro | DateTimeField auto | Timestamp automático |
| dia_postoperatorio | PositiveSmallIntegerField | Calculado automáticamente al guardar |

### Alerta
| Campo | Tipo | Descripción |
|-------|------|-------------|
| paciente | ForeignKey(Paciente) PROTECT | — |
| registro_origen | ForeignKey(RegistroDiario) PROTECT | Registro que disparó la alerta |
| tipo | CharField choices | SEPSIS/FUGA_ANASTOMOTICA/ILEO_PARALITICO/DOLOR_AGUDO |
| severidad | CharField choices | ALTA/MEDIA/BAJA |
| mensaje | TextField | Descripción generada por alert_engine |
| resuelta | BooleanField | El oncólogo marca cuando atiende |
| fecha_alerta | DateTimeField auto | Timestamp automático |
| fecha_resolucion | DateTimeField nullable | Cuándo fue atendida |

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

### ⏳ FASE 3 — Bot WhatsApp — FUNCIONAL END-TO-END (pendiente solo merge)
> Rama: `sprint-3-whatsapp` (pusheada a origin)

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
- [ ] **Merge sprint-3-whatsapp → Desarrollo (con aprobación del Arquitecto)** ← único pendiente

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

- [ ] **NUEVA alerta clínica: silencio del paciente.** Si un
  CheckInProgramado pasa a NO_RESPONDIDO, generar alerta para que el
  equipo médico contacte al paciente. DEPENDE del scheduler (solo una
  tarea programada detecta la ausencia de respuesta) → SPRINT 4.
  DECISIÓN ABIERTA (resolver en Sprint 4): severidad, y si dispara con
  un silencio o con dos consecutivos.

- [ ] **Gating del alert_engine — 2 políticas (se deciden CON el código
  del bot en Sprint 4, no antes):**
  - DECISIÓN ABIERTA: alertas duplicadas con 2 check-ins/día — ¿una
    alerta por condición por día, o una por cada check-in que la detecte?
  - DECISIÓN ABIERTA: gating pre-operatorio (dia_postoperatorio=0) —
    ¿filtra el bot antes de llamar al engine, o el engine salta la
    evaluación?

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
- [ ] **Paso 2 — Variables nuevas de la literatura** (una por una,
  ciclo decidir→implementar→verificar→documentar):
  - [x] Tolerancia a líquidos — booleano, escalera MEDIA/ALTA,
    tipo INTOLERANCIA_ORAL (Regla 6)
  - [x] Hinchazón abdominal — escala nada/algo/mucho, alerta por
    empeoramiento entre días (Regla 7), tipo ILEO_PARALITICO
  - [ ] Frecuencia cardíaca (FC) — pendiente (dispositivo provisto por
    el médico, pregunta directa)
  - [ ] Frecuencia respiratoria (FR) — pendiente (solo-dashboard, sin
    alerta — Outersterp 2025: 77% de falsas alertas)
  - Nota: estado de herida (fotos) y antecedentes quedan FUERA de
    Sprint 3 (mejora futura / Sprint 4 respectivamente).
- [ ] **Paso 3 — Revisión de cierre en dos frentes.** Claude Code audita
  coherencia interna y deuda técnica (alert_engine/modelos); Codex hace
  pasada adversarial de seguridad + escalabilidad; Claude (chat)
  sintetiza ambos en lista priorizada.
- [ ] **Paso 4 — Resolver lo bloqueante, luego merge** sprint-3-whatsapp
  → Desarrollo con aprobación del Arquitecto.

---

### ⏳ FASE 4 — Dashboard Oncólogo y Notificaciones — PENDIENTE
> Crear rama: `git checkout -b sprint-4-dashboard`

- [ ] Personalizar Django Admin con colores según severidad de alertas
- [ ] Crear vista detalle_paciente con historial y gráfica temperatura/dolor
- [ ] Implementar notificación al médico por email/SMS cuando hay alerta roja
- [ ] **Implementación 2×/día (arquitectura CERRADA en FASE 3.6 — leer D1–D5
  y el esquema de `CheckInProgramado` ahí; aquí NO se re-decide, se ejecuta):**
  - [ ] Crear modelo `CheckInProgramado` según el esquema acordado + migración.
  - [ ] Scheduler (Celery beat / cron): crea los eventos del día con su
    `orden`/`etiqueta`/`hora_programada` y cierra vencidos PENDIENTE→
    NO_RESPONDIDO. Incluye el envío matutino 7–10 AM Bogotá ya diferido.
  - [ ] Refactor de bot.py: la conversación se vincula al CheckInProgramado
    PENDIENTE del día (la conversación deja de decidir el turno).
  - [ ] Alerta de silencio (NO_RESPONDIDO) — resolver DECISIÓN ABIERTA:
    severidad + ¿uno o dos silencios?
  - [ ] Resolver los 2 gatings (DECISIONES ABIERTAS): deduplicación de
    alertas y gating pre-operatorio (dia_postoperatorio=0).
  - [ ] **Deuda de diseño detectada en el cruce contra el código
    (detalle y razonamiento en BITACORA.md, entrada del 22/06/2026):**
    - [ ] **Fecha autoritativa para reglas de días calendario.** El
      alert_engine agrupa por `fecha_registro__date` (verificado: ~8 usos
      en alert_engine.py). Si `CheckInProgramado.fecha_dia` (congelado) y
      `RegistroDiario.fecha_registro` (auto_now_add) divergen en un cruce
      de medianoche, las reglas cuentan el registro en el día equivocado.
      DECISIÓN CLÍNICA pendiente: ¿cuál fecha manda para las reglas — la
      del evento o la del registro? (Riesgo más serio: toca el engine, no
      solo el bot.)
    - [ ] **Reescribir el guard "un registro por día" → "por check-in".**
      bot.py hoy bloquea con `fecha_ultimo_registro` (líneas ~145-146 y
      161-162 → MSG_YA_REGISTRADO); con 2 check-ins/día eso bloquearía el
      segundo. El refactor debe expresar la guarda en términos del evento
      PENDIENTE, no de la fecha.
    - [ ] **Vínculo OneToOne transaccional.** Al completar el flujo,
      asociar el RegistroDiario al CheckInProgramado PENDIENTE dentro de
      una transacción, para no dejar eventos COMPLETADO sin `registro` ni
      registros huérfanos.
- [ ] Demo funcional con 1 paciente ficticio para el equipo médico

**Decisiones de diseño pendientes (anotadas durante la implementación
del alert_engine, jun 2026):**
- [ ] Mecanismo de escalamiento automático: si una alerta MEDIA lleva
  mucho tiempo sin marcarse `resuelta`, ¿debería escalar sola a ALTA?
  Depende de los campos `resuelta`/`fecha_resolucion` que ya existen en
  el modelo `Alerta` pero no se usan activamente todavía.
- [ ] Campo de "motivo de resolución" en `Alerta` para diferenciar caso
  real vs. falso positivo — útil si se quiere ajustar umbrales del
  alert_engine con datos reales en el futuro, no indispensable para el
  primer dashboard.
- [ ] Duración del seguimiento del bot por paciente: ¿cuándo se
  desactiva automáticamente `Paciente.activo`? Hoy nada lo cambia solo
  — definir si es un número fijo de días postoperatorios, o si el
  médico lo cierra manualmente desde el dashboard.
- [ ] Interfaz del médico para gestionar alertas: cómo marcar
  `resuelta`, cómo distinguir falsos positivos de casos reales, y cómo
  se visualiza la escalera de severidad BAJA/MEDIA/ALTA en pantalla.

---

### ⏳ FASE 5 — Producción — PENDIENTE
> Crear rama: `git checkout -b sprint-5-produccion`

- [ ] Desplegar en Railway o Render con PostgreSQL en la nube
- [ ] Configurar HTTPS y deshabilitar DEBUG
- [ ] Integrar capa RAG para respuestas a preguntas frecuentes del postoperatorio
- [ ] Revisión cumplimiento HABEAS DATA Colombia
- [ ] Entrega final al equipo médico

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

*Última actualización: Fase 3.6 — las 5 reglas del alert_engine
completas (drenaje, temperatura, gases, náuseas, dolor) y van 2 de 4
variables nuevas del Paso 2: tolerancia a líquidos (Regla 6,
INTOLERANCIA_ORAL) y hinchazón abdominal (Regla 7, ILEO_PARALITICO) —
60 tests OK. Antes se corrigió un bug de zona horaria (UTC vs
America/Bogota) que afectaba las reglas de días calendario en horario
nocturno, más un clamp para dia_postoperatorio negativo (commit
ff8bdc4). Pendiente: variables nuevas restantes (FC, FR), implementar
2×/día en bot.py (con los 2 gatings pendientes) y repaso final de
alert_engine.py antes del merge.*
*Siguiente paso: implementar frecuencia de check-ins (2×/día) en
bot.py resolviendo los 2 pendientes de gating, luego repaso final de
alert_engine.py completo, luego merge `sprint-3-whatsapp` →
`Desarrollo` con aprobación del Arquitecto.*
