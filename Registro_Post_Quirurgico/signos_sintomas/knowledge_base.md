# Base de Conocimiento Clínico — Bot Sugarbaker

> **Estado:** PLACEHOLDER. El contenido clínico real se construirá cuando el
> equipo tenga acceso al Drive del médico (pendiente). La capa RAG está
> pospuesta (ver ROADMAP, FASE 5). Por ahora el bot responde dudas con las
> respuestas predefinidas conservadoras de la última sección.

---

## Umbrales de alarma clínica
(pendiente - acceso Drive médico)

## Señales de urgencia inmediata
(pendiente - acceso Drive médico)

## Evolución normal del postoperatorio
(pendiente - acceso Drive médico)

## Preguntas frecuentes del paciente
(pendiente - acceso Drive médico)

## Respuestas predefinidas actuales del bot
- "¿Es normal tener fiebre?" →
  "Una temperatura leve los primeros días puede ser normal. Si supera 38°C
  comunícate con tu médico de inmediato."
- "¿Cuándo puedo comer normal?" →
  "La alimentación se recupera gradualmente. Sigue las indicaciones de tu médico."
- "¿Es normal el dolor?" →
  "Algo de molestia es esperado. Si el dolor es muy intenso o repentino, contacta
  a tu médico urgente."
- Cualquier otra duda →
  "Para esa pregunta específica, te recomiendo contactar directamente a tu médico.
  Estamos aquí para tu seguimiento diario."

---

> **Nota para desarrolladores:** las respuestas predefinidas viven también como
> constantes en `bot.py` (`RESP_FIEBRE`, `RESP_COMER`, `RESP_DOLOR`,
> `RESP_FALLBACK`). Este archivo es la fuente humana de verdad; al actualizar una
> respuesta aquí, reflejarla en `bot.py` (hasta que exista la capa RAG que lea
> este documento directamente).
