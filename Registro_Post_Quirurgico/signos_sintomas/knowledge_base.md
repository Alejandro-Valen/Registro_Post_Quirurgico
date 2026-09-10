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

## Consulta pendiente al médico

> **Para el médico.** Son **tres preguntas concretas, ~10 minutos**, más una
> cuarta frase que se incluye solo para que vea **todo** lo que el bot le dice a
> su paciente. Estas cuatro son las únicas respuestas del bot cuando el paciente
> pregunta algo fuera del cuestionario diario. Hoy están redactadas de forma
> conservadora por el equipo técnico y **ninguna ha sido validada
> clínicamente**. Puede responder sobre este mismo documento.
>
> **Corrección del 09/09/2026.** Hasta hoy esta consulta sometía tres respuestas
> y el bot tenía **cuatro**: faltaba la de «no entendí tu pregunta»
> (`RESP_FALLBACK`). No lleva contenido clínico —solo remite al médico— y por eso
> se había quedado fuera, pero someter tres de cuatro dejaba al médico opinando
> sobre un conjunto incompleto sin saberlo.
>
> **Regla que no debe romperse:** la respuesta no puede contener un umbral
> numérico (grados, pulsaciones, escala de dolor). El paciente no necesita
> auto-evaluarse — el sistema le pregunta la temperatura, el dolor y el pulso
> dos veces al día y el motor de alertas los evalúa. Si el paciente usa un
> umbral propio, puede quedarse tranquilo justo cuando el sistema ya escaló.

### 1. Fiebre

- **Texto actual:** "Registramos tu temperatura en cada reporte y tu equipo
  médico la está revisando. Si te sientes peor, con escalofríos o mucho
  malestar, comunícate con tu médico. Si es urgente, ve al servicio de
  urgencias."
- **Qué hace el sistema:** alerta ALTA desde 37.9 °C en cualquier registro;
  alerta MEDIA con 37.5–37.8 °C sostenido dos días calendario seguidos.
- **Antes decía:** "Si supera 38 °C comunícate con tu médico de inmediato" —
  se retiró porque contradecía al motor (un paciente con 37.9 recibía el
  mensaje de que estaba bien) y porque daba un umbral al paciente.
- **Pregunta:** ¿basta con remitir al médico según cómo se siente, o el
  paciente necesita algún criterio propio? Si necesita uno, ¿cuál, expresado
  sin número?

### 2. Dolor

- **Texto actual:** "Algo de molestia es esperado. Si el dolor es muy intenso o
  repentino, contacta a tu médico urgente."
- **Qué hace el sistema:** escalera por día postoperatorio. El mismo 7/10 es
  MEDIA ("llamar al médico") en el día 2 y ALTA ("ir a urgencias") en el día 8,
  porque se espera que el dolor baje con los días.
- **Pregunta:** ¿conviene decirle al paciente que el dolor debería ir
  disminuyendo, para que note un estancamiento o un repunte? El texto actual no
  le da ninguna referencia temporal.

### 3. Alimentación

- **Texto actual:** "La alimentación se recupera gradualmente. Sigue las
  indicaciones de tu médico."
- **Qué hace el sistema:** evalúa tolerancia a líquidos — alerta MEDIA el
  primer día que el paciente no los tolera, ALTA al segundo.
- **Pregunta:** ¿debería mencionar la hidratación? La deshidratación es la
  causa #1 de readmisión (Lawrence 2013) y el sistema la vigila, pero la
  respuesta actual no la nombra.

### Cómo se aplica la respuesta

Al recibir la redacción del médico: actualizarla arriba en "Respuestas
predefinidas actuales del bot" y reflejarla en las constantes de `bot.py`. El
test `test_respuestas_predefinidas_no_revelan_umbrales_clinicos` verifica que la
nueva redacción siga sin exponer cifras clínicas.

---

> **Nota para desarrolladores:** las respuestas predefinidas viven también como
> constantes en `bot.py` (`RESP_FIEBRE`, `RESP_COMER`, `RESP_DOLOR`,
> `RESP_FALLBACK`). Este archivo es la fuente humana de verdad; al actualizar una
> respuesta aquí, reflejarla en `bot.py` (hasta que exista la capa RAG que lea
> este documento directamente).
>
> No agregar umbrales, diagnósticos ni recomendaciones nuevas sin validación
> explícita del médico y pruebas del comportamiento resultante.

### 4. Cuando el bot no entiende la pregunta

- **Texto actual:** "Para esa pregunta específica, te recomiendo contactar
  directamente a tu médico. Estamos aquí para tu seguimiento diario."
- **Cuándo aparece:** cuando el paciente escribe una pregunta que no encaja
  en ninguna de las tres anteriores.
- **Por qué se incluye aquí aunque no tenga contenido clínico:** es la cuarta
  y última cosa que el bot le puede decir a un paciente fuera del
  cuestionario. El médico debería ver el conjunto completo, no tres de
  cuatro.
- **Pregunta:** ¿le parece bien remitir sin más, o prefiere que el bot añada
  alguna indicación de seguridad —por ejemplo, cuándo no esperar respuesta y
  acudir a urgencias?
