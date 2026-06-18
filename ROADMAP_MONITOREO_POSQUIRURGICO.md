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

Capturadas una vez al día por WhatsApp:

1. **Temperatura corporal** (°C) — alerta si >= 38.0°C
2. **Dolor EVA** (escala 1-10) — alerta si dolor agudo repentino
3. **Volumen de drenaje** (ml) — cantidad de líquido en drenajes
4. **Aspecto del drenaje** — seroso / hemático / purulento / fecaloide
5. **Tránsito intestinal** — presencia de gases (sí/no)
6. **Náuseas o vómito** — episodios en las últimas 24 horas

---

## Reglas del Motor de Alertas (alert_engine.py)

| Regla | Condición | Tipo de Alerta | Severidad |
|-------|-----------|----------------|-----------|
| 1 | Temperatura >= 38.0°C | SEPSIS | ALTA |
| 2 | Drenaje purulento o fecaloide | FUGA_ANASTOMOTICA | ALTA |
| 3 | Sin gases por 3 días consecutivos | ILEO_PARALITICO | ALTA |
| 4 | Vómito > 3 episodios en 24h | ILEO_PARALITICO | MEDIA |

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
| aspecto_drenaje | CharField choices | seroso/hemático/purulento/fecaloide/sin_drenaje |
| presencia_gases | BooleanField | Tránsito intestinal |
| episodios_nauseas | PositiveSmallIntegerField | Episodios en 24h |
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

**Pendiente (decidido, sin ejecutar — fuera de esta fase):**
- [x] Decidir nombre del archivo: renombrado a `ROADMAP_MONITOREO_POSQUIRURGICO.md` (nombre del repositorio se mantiene sin cambios, decisión explícita del Arquitecto)
- [ ] Fase de decisiones de arquitectura del `alert_engine` (umbrales de fiebre, gases, náuseas, drenaje; gap de `DOLOR_AGUDO`; frecuencia de check-ins) — ver `docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md`
- [ ] Merge `sprint-3-whatsapp` → `Desarrollo` (pospuesto hasta cerrar la fase anterior)

---

### ⏳ FASE 4 — Dashboard Oncólogo y Notificaciones — PENDIENTE
> Crear rama: `git checkout -b sprint-4-dashboard`

- [ ] Personalizar Django Admin con colores según severidad de alertas
- [ ] Crear vista detalle_paciente con historial y gráfica temperatura/dolor
- [ ] Implementar notificación al médico por email/SMS cuando hay alerta roja
- [ ] Configurar envío automático del bot cada mañana (Celery beat o cron)
- [ ] Demo funcional con 1 paciente ficticio para el equipo médico

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

*Última actualización: Sprint 3 funcional end-to-end (rama `sprint-3-whatsapp`) — pasos 1-4 completados: modelo ConversacionWhatsApp, campo cantidad_drenaje, bot.py con máquina de estados, webhook Twilio (22 tests OK) y prueba real con WhatsApp exitosa (RegistroDiario + Alerta verificados en BD)*
*Siguiente paso: merge `sprint-3-whatsapp` → `Desarrollo` con aprobación del Arquitecto; luego Sprint 4 (dashboard + notificaciones)*
