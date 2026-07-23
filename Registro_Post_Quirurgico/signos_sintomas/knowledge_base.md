# Base de Conocimiento Clínico — Bot de Seguimiento Posquirúrgico

> **Estado al 21/07/2026:** PLACEHOLDER no conectado al runtime. El contenido
> clínico real se construirá cuando el equipo tenga acceso al material validado
> por el médico. La capa RAG está diferida a Sprint 6. Por ahora el bot responde
> dudas con las respuestas predefinidas conservadoras de la última sección.

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

> **Ninguna de estas respuestas puede contener un umbral clínico** (decisión D4,
> 22/07/2026). El paciente nunca ve los valores que disparan una alerta, y no
> necesita auto-evaluarse: el sistema le pregunta la temperatura dos veces al día
> y el motor la evalúa. Hay un test que lo vigila
> (`test_respuestas_predefinidas_no_revelan_umbrales_clinicos`).

- "¿Es normal tener fiebre?" →
  "Registramos tu temperatura en cada reporte y tu equipo médico la está
  revisando. Si te sientes peor, con escalofríos o mucho malestar, comunícate
  con tu médico. Si es urgente, ve al servicio de urgencias."
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
>
> No agregar umbrales, diagnósticos ni recomendaciones nuevas sin validación
> explícita del médico y pruebas del comportamiento resultante.
