# Contexto del Proyecto — MVP Sugarbaker / Clínica Somer

## ¿Qué es este proyecto?
Sistema de monitoreo remoto postquirúrgico para pacientes de cirugía
oncológica Sugarbaker (HIPEC) de la Clínica Somer, Medellín, Colombia.
El paciente interactúa exclusivamente por WhatsApp. Un bot le hace
preguntas diarias de telemetría. El sistema clasifica los datos,
detecta alertas rojas y notifica al oncólogo a través de un dashboard
en Django Admin.

## Stack tecnológico
- Backend: Django 5.x + PostgreSQL
- Interfaz paciente: WhatsApp Bot vía Twilio API
- Panel médico: Django Admin personalizado
- Servidor: Python, hosted en Railway o Render (futuro)
- IA: Claude Code (arquitectura/lógica), Codex CLI (implementación)

## Estructura de apps Django
- `home/` — portal web del sistema, páginas informativas
- `signos_sintomas/` — núcleo clínico: modelos, bot, alertas, webhook

## Variables clínicas que registra el sistema
Estas variables se capturan una vez al día por WhatsApp:

1. **Temperatura corporal** (°C) — riesgo de sepsis si >= 38.0°C
2. **Dolor EVA** (escala 1-10) — dolor agudo repentino es red flag
3. **Volumen de drenaje** (ml) — cantidad de líquido en los drenajes
4. **Aspecto del drenaje** — seroso / hemático / purulento / fecaloide
5. **Tránsito intestinal** — presencia de gases (sí/no)
6. **Náuseas o vómito** — episodios en las últimas 24 horas

## Reglas del motor de alertas (alert_engine.py)
Estas reglas generan una Alerta roja automática y notifican al médico:

| Regla | Condición | Tipo de alerta |
|-------|-----------|----------------|
| 1 | Temperatura >= 38.0°C | SEPSIS |
| 2 | Drenaje purulento o fecaloide | FUGA_ANASTOMOTICA |
| 3 | Sin gases por 3 días consecutivos | ILEO_PARALITICO |
| 4 | Vómito incontrolable (>3 episodios) | ILEO_PARALITICO |

## Modelos de base de datos (Sprint 1)
- `Paciente` — nombre, teléfono WhatsApp, fecha cirugía, médico
- `RegistroDiario` — todas las variables clínicas + timestamp
- `Alerta` — tipo, severidad, paciente, resuelta (bool), timestamp

## Convenciones del equipo
- Idioma del código: español (nombres de variables, comentarios)
- Rama principal de desarrollo: `Desarrollo`
- Una rama por sprint: `sprint-1-modelos`, `sprint-2-alertas`, etc.
- Nunca trabajar directo en `Desarrollo`
- El `.env` nunca se sube a GitHub

## Roles del equipo
- **Arquitecto IA**: define lógica clínica, valida reglas médicas,
  trabaja con Claude Code
- **Dev Full-Stack (Alejandro)**: implementa modelos y vistas,
  configura infraestructura, trabaja con Codex CLI

## Cómo usar este archivo si eres un agente IA
Lee este archivo completo antes de sugerir cualquier cambio al
proyecto. Toda decisión técnica debe ser compatible con el contexto
clínico descrito aquí. Las reglas del alert_engine no son
negociables — tienen base en protocolos médicos reales de
postoperatorio HIPEC/Sugarbaker.