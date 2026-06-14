# Contexto del Proyecto — MVP Sugarbaker / Clínica Somer

> **Para agentes IA:** Lee este archivo COMPLETO antes de sugerir cualquier
> cambio al proyecto. Toda decisión técnica debe ser compatible con el contexto
> clínico descrito aquí. Las reglas del alert_engine no son negociables —
> tienen base en protocolos médicos reales de postoperatorio HIPEC/Sugarbaker.

---

## ¿Qué es este proyecto?

Sistema de monitoreo remoto postquirúrgico para pacientes de cirugía oncológica
Sugarbaker (HIPEC) de la Clínica Somer, Medellín, Colombia. El paciente interactúa
exclusivamente por WhatsApp. Un bot le hace preguntas diarias de telemetría. El
sistema clasifica los datos, detecta alertas rojas y notifica al oncólogo a través
de un dashboard en Django Admin.

**La IA NO diagnostica.** Funciona bajo un sistema de reglas clínicas fijas
(alert_engine) para clasificar, resumir telemetría y generar alertas tempranas.

---

## Stack Tecnológico

- **Backend:** Django 6.0.5 + Python 3.13
- **Base de datos:** PostgreSQL 18 (local: sugarbaker_db)
- **Interfaz paciente:** WhatsApp Bot vía Twilio API (pendiente Sprint 3)
- **Panel médico:** Django Admin personalizado
- **Dependencias clave:** python-decouple, psycopg2-binary, twilio (futuro)
- **OS desarrollo:** Windows 11

---

## Repositorio

- **URL:** https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
- **Rama principal:** `Desarrollo`
- **Ramas activas:** `sprint-1-modelos` (León), `sprint-1-frontend` (Alejandro)

---

## Estructura de Apps Django

```
Registro_Post_Quirurgico/Registro_Post_Quirurgico/
├── home/             → portal web, páginas informativas
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
| 3 | Volumen de drenaje | Entero | ml (nullable) |
| 4 | Aspecto del drenaje | Choices | seroso/hemático/purulento/fecaloide/sin_drenaje |
| 5 | Presencia de gases | Booleano | sí/no |
| 6 | Episodios de náuseas/vómito | Entero | cantidad en 24h |

---

## Reglas del Motor de Alertas (alert_engine.py)

**Archivo:** `signos_sintomas/alert_engine.py` — implementado en Sprint 2, mergeado a `Desarrollo` (PR #1), con fix post-merge en commit `01b8a47`
**Función principal:** `evaluar_registro(registro: RegistroDiario) -> list[Alerta]`

| Regla | Condición exacta | Tipo Alerta | Severidad | Base clínica |
|-------|-----------------|-------------|-----------|--------------|
| 1 | temperatura >= 38.0 | SEPSIS | ALTA | Riesgo de sepsis post-HIPEC |
| 2 | aspecto_drenaje in ['purulento','fecaloide'] | FUGA_ANASTOMOTICA | ALTA | Fuga anastomótica |
| 3 | sin gases 3 días consecutivos | ILEO_PARALITICO | ALTA | Íleo paralítico severo |
| 4 | episodios_nauseas > 3 | ILEO_PARALITICO | MEDIA | Íleo paralítico moderado |

---

## Modelos de Base de Datos (Sprint 1 — COMPLETADO)

### Paciente
```python
nombre_completo       CharField(200)
telefono_whatsapp     CharField(20) unique  # identificador para el bot
fecha_cirugia         DateField
medico_responsable    CharField(200)
activo                BooleanField default=True
fecha_registro        DateTimeField auto_now_add=True
```

### RegistroDiario
```python
paciente              ForeignKey(Paciente, PROTECT)
temperatura           DecimalField(4,1)
dolor_eva             PositiveSmallIntegerField  # 1-10
volumen_drenaje_ml    PositiveIntegerField nullable
aspecto_drenaje       CharField choices=[seroso,hematico,purulento,fecaloide,sin_drenaje]
presencia_gases       BooleanField
episodios_nauseas     PositiveSmallIntegerField
fecha_registro        DateTimeField auto_now_add=True
dia_postoperatorio    PositiveSmallIntegerField  # calculado automáticamente en save()
```

### Alerta
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

---

## Estado Actual del Proyecto

| Sprint | Descripción | Estado |
|--------|-------------|--------|
| Sprint 0 | Configuración base y seguridad | ✅ Completado |
| Sprint 1 | Modelos clínicos y base de datos | ✅ Completado |
| Sprint 2 | Motor de alertas (alert_engine) | ✅ Completado (con fix post-merge 01b8a47) |
| Sprint 3 | Bot WhatsApp (Twilio) | ⏳ En curso (pasos 1-2 completados) |
| Sprint 4 | Dashboard oncólogo y notificaciones | ⏳ Pendiente |
| Sprint 5 | Producción y despliegue | ⏳ Pendiente |

**Punto actual:** Sprint 3 en curso en la rama `sprint-3-whatsapp` (pasos 1 y 2
completados, pusheados a origin):

- **Paso 1 — Modelos:** modelo `ConversacionWhatsApp` creado (persiste el estado
  de la máquina de estados, ya que cada mensaje de Twilio llega como petición
  HTTP independiente). Campo `cantidad_drenaje` (escala cualitativa
  poco/normal/mucho) agregado a `RegistroDiario`; `volumen_drenaje_ml` pasa a ser
  opcional. Migración `0002` aplicada.
- **Paso 2 — Bot:** `signos_sintomas/bot.py` con máquina de estados de 5 preguntas
  (lógica pura: `procesar_mensaje(telefono, texto) -> texto`, sin HTTP). El bot NO
  diagnostica ni muestra alertas al paciente; solo captura telemetría, delega en
  `alert_engine` y responde confirmación neutra. **18 pruebas unitarias OK.**
  `knowledge_base.md` creado como placeholder con respuestas predefinidas
  conservadoras (RAG diferido).

**Pendiente paso 3:** `views.py` (webhook Twilio + validación de firma +
`csrf_exempt`), `urls.py` de la app y del proyecto, config Twilio en
`settings.py`/`.env`/`requirements.txt`.

**Diferido:**
- FASE 4 — envío automático matutino 7-10 AM Bogotá (Celery/cron) + notificación
  al médico.
- FASE 5 — capa RAG que lea el `knowledge_base.md` real (acceso Drive médico
  pendiente).

---

## Roles del Equipo

- **León (Arquitecto IA):** define lógica clínica, valida reglas médicas,
  trabaja con Claude Code. NO es el programador principal.
- **Alejandro (Dev Full-Stack):** implementa modelos y vistas, configura
  infraestructura, trabaja con Codex CLI.

---

## Convenciones del Equipo

- Idioma del código: **español** (nombres de variables, comentarios, commits)
- Rama principal: `Desarrollo` — **nadie trabaja directo aquí**
- Una rama por sprint: `sprint-1-modelos`, `sprint-2-alertas`, etc.
- El `.env` **nunca** se sube a GitHub
- Ningún código clínico entra a `Desarrollo` sin aprobación del Arquitecto
- Commits: formato `feat:`, `fix:`, `docs:` + descripción en español

---

## Comandos Esenciales

```bash
# Posición correcta para todos los comandos manage.py
cd Registro_Post_Quirurgico/Registro_Post_Quirurgico

python manage.py check           # verificar sin errores
python manage.py makemigrations  # después de cambiar models.py
python manage.py migrate         # aplicar cambios a PostgreSQL
python manage.py runserver       # iniciar servidor → http://127.0.0.1:8000/admin/
```
