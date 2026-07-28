# El bot de WhatsApp

> **Fuente única.** Máquina de estados, reglas de diseño no negociables y
> respuestas predefinidas de `signos_sintomas/bot.py`. Al cambiar el flujo del
> bot, este archivo se actualiza en el mismo lote de commits.
>
> Las reglas que evalúan lo que el bot captura viven en
> `docs/reglas_clinicas.md`.

---

## El Bot de WhatsApp (signos_sintomas/bot.py — Sprint 3)

**Función principal:** `procesar_mensaje(telefono, texto) -> texto_respuesta`

Diseño: lógica **pura**, sin conocimiento de HTTP ni Twilio. La vista
(`views.py`, en funcionamiento desde el Sprint 3) traduce HTTP ↔ esta función.
Esto permite testear el bot completo sin mockear peticiones web.

> El número total de pruebas del proyecto no se anota aquí: se desactualiza en
> cada sesión y ya lo hizo una vez (decía 69 con la suite en 319). La cifra
> vigente sale de `python manage.py test --noinput`.

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
3. **Un registro por check-in pendiente.** Se programan dos turnos diarios
   (mañana/tarde) y la conversación se liga al check-in exacto. Si no queda un
   turno pendiente, el bot informa que no hay reporte por completar.
4. **Lenguaje:** español coloquial, tuteo, tono cálido — nunca jerga médica en
   las preguntas al paciente (ej. no decir "hemático", se muestra "rojo con
   sangre").
5. **Validación con reintento por pregunta:** cada respuesta mal formada pide
   reintento con un mensaje específico de esa pregunta, nunca un error genérico.
6. **Sin bloqueo horario artificial en la lógica del bot.** El bot puede
   completar un check-in pendiente cuando el paciente escribe. El inicio
   proactivo por WhatsApp sigue pendiente en `enviar_recordatorios`; hoy el
   sistema es reactivo.
7. **Dudas (FAQ) fuera del flujo de registro:** respuestas predefinidas
   conservadoras (fiebre / alimentación / dolor / fallback a "contacta a tu
   médico"). Esto es un espejo temporal de `knowledge_base.md` mientras no
   exista la capa RAG (Sprint 6). **Ninguna de ellas puede contener un umbral
   clínico** (decisión D4): el paciente no se auto-evalúa, el sistema le
   pregunta la temperatura dos veces al día y el motor la evalúa. `RESP_FIEBRE`
   decía "si supera 38°C" mientras el motor alerta desde 37.9 — se retiró el
   número. Lo vigila
   `test_respuestas_predefinidas_no_revelan_umbrales_clinicos`. La redacción
   final de las cuatro respuestas está **pendiente de validación médica**: ver
   `knowledge_base.md`, sección "Consulta pendiente al médico".

**`knowledge_base.md`:** placeholder con la estructura final pendiente y las
respuestas predefinidas actuales. **No completar con información clínica real
ni cambiar las reglas del alert_engine sin que el Arquitecto y el médico lo
validen explícitamente**. La auditoría de literatura ya está disponible; las
reglas vigentes están documentadas y cualquier ampliación clínica futura debe
volver a pasar por esa validación.

---
