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

**Máquina de estados (11 preguntas; 9 si el paciente no tiene drenaje):**
```
[Palabra de auxilio — D21, se mira ANTES que el estado]
  Si el mensaje contiene ayuda / auxilio / socorro / emergencia (palabra suelta,
  en cualquier estado, incluido a mitad del cuestionario):
    → se descarta el flujo en curso, se responde MSG_AUXILIO y se crea una
      alerta AUXILIO / ALTA para el médico.
[Guard de consentimiento informado — Bloque 7]
  Si paciente.consentimiento_informado es False: mensaje neutro, no entra a INICIO.
[Duda de la FAQ fuera del cuestionario — BE-04 / UX-B08]
  Con un turno pendiente: respuesta de la FAQ + MSG_ARRANQUE_TRAS_DUDA, y la
  conversación pasa a ESPERANDO_TEMPERATURA. Sin turno pendiente: solo la FAQ.
INICIO
  → ESPERANDO_TEMPERATURA       "¿Cuál es tu temperatura? ej: 37.5"
                                admite "saltar" (D20) → temperatura = null
                                responde con el ECO: "Anoté: 37.5 °C." (D19)
  → ESPERANDO_DOLOR             "Del 0 al 10, ¿cuánto dolor sientes?"  (0 = sin dolor, D20)
  → ESPERANDO_TIENE_DRENAJE     "¿Tienes drenaje activo? sí/no"
  → ESPERANDO_ASPECTO_DRENAJE   menú 1-5 en lenguaje no médico — se OMITE si tiene_drenaje=False
  → ESPERANDO_CANTIDAD_DRENAJE  poco/normal/mucho (+ ml opcional) — se OMITE si tiene_drenaje=False
  → ESPERANDO_GASES             "¿Has podido pasar gases o ir al baño? sí/no" (pregunta 6)
                                un mensaje con «sí» Y «no» se repregunta (UX-B03)
  → ESPERANDO_NAUSEAS           "¿Cuántas veces náuseas o vómito?" número, 0-20 (pregunta 7)
                                acepta «ninguna», «nada», «no», «cero» como 0
  → ESPERANDO_HINCHAZON         "¿cómo siente la hinchazón del abdomen? nada/algo/mucho"
  → ESPERANDO_FRECUENCIA_CARDIACA "¿cuál es tu frecuencia cardíaca? (lpm)"
  → ESPERANDO_FRECUENCIA_RESPIRATORIA "¿cuál es tu frecuencia respiratoria? (rpm)"
  → ESPERANDO_TOLERANCIA_LIQUIDOS "¿Ha podido tomar líquidos sin vomitar? sí/no"
  → COMPLETADO                  crea RegistroDiario, evalúa alertas (síncrono),
                                cierra con mensaje según severidad (neutro / MEDIA / ALTA)
```

**El bot devuelve lo que entendió (D19, 08/09/2026).** Tras la pregunta 1
responde «Anoté: 37.5 °C.» —o «Anoté: sin medir (la saltaste).»— antes de la
pregunta 2. No es cosmético: el parser rechaza lo ambiguo (`379`, `37 9`,
`375`), pero **no puede detectar un dedazo válido**. Quien quiso escribir 37.5
y escribió 38.5 pasa todos los filtros, porque es una temperatura posible. El
eco es lo único que se lo enseña.

**Una pregunta, un dato (UX-B03, 02/10/2026).** Hasta esa fecha la pregunta 6
pedía gases y náuseas en el mismo mensaje, y el parser buscaba un «no» en
cualquier parte: *«sí, no tuve náuseas: 0»* —el paciente SÍ pasó gases— se
guardaba como **sin gases** y alimentaba la Regla 3 (íleo) con un hecho falso.
Ahora son las preguntas 6 y 7. Y como el paciente puede seguir contestando las
dos cosas por costumbre, un mensaje a la pregunta de gases que trae un «sí» y un
«no» **se repregunta: el bot nunca elige uno de los dos.** La migración 0031 lleva
a la pregunta de gases cualquier conversación que estuviera en el estado viejo.

**La duda no deja el reporte sin empezar (BE-04 / UX-B08, 02/10/2026).** La FAQ
se consultaba antes que el turno pendiente y devolvía su respuesta sola: el
paciente que escribía *«tengo fiebre»* recibía la respuesta enlatada, el
cuestionario no arrancaba y, si no volvía a escribir, su turno acababa en
SILENCIO en vez de pasar por la Regla 1. Ahora, con un turno pendiente, la
respuesta de la FAQ va seguida de *«Aprovechemos para hacer tu reporte de
hoy»*, el aviso de AYUDA y la pregunta 1. El texto de las respuestas no cambia
(sigue pendiente de validación médica), y **una palabra de la FAQ no crea
ninguna alerta**: sería clasificar síntomas desde el chat, el mismo criterio
que dejó `urgencias` fuera de la palabra de auxilio (D21).

**Reglas de diseño no negociables:**
1. **El paciente nunca ve el tipo de alerta ni los valores que la
   dispararon.** El detalle clínico (SEPSIS, FUGA, taquicardia, umbrales,
   etc.) es exclusivo del oncólogo en el admin. Desde el Bloque B
   (02/07/2026) el mensaje de cierre SÍ varía según la severidad máxima de
   las alertas del check-in, pero solo como recomendación de acción
   tranquilizadora: BAJA/sin alertas → `MSG_CONFIRMACION` (neutro); MEDIA
   → `MSG_CIERRE_ALERTA_MEDIA` ("contacta a tu médico en las próximas
   horas"); ALTA → `MSG_CIERRE_ALERTA_ALTA` ("comunícate con tu médico o
   ve a urgencias"). Ninguno menciona el tipo de alerta ni valores. Su
   recomendación clínica la fija `test_los_cierres_conservan_su_indicacion_clinica`:
   el 02/10/2026 (D26) solo cambiaron su última línea y sus tildes.
   Implementación: `evaluar_registro` corre de forma síncrona dentro de
   `_crear_registro` (en un savepoint defensivo) para conocer la severidad
   antes de responder; ver `_mensaje_cierre`.

   **El eco de la temperatura (D19) NO va en el mensaje de cierre, y esta
   regla es la razón.** Se probó ahí primero y
   `test_alerta_no_se_muestra_al_paciente` lo puso en rojo: mostrar «38.5 °C»
   junto a «ve a urgencias» es exactamente revelar el valor que disparó la
   alerta. El eco vive en el paso de la temperatura, donde todavía no se ha
   evaluado nada y por tanto no hay ninguna clasificación que filtrar.

   **La única excepción a esta regla es `MSG_AUXILIO`** (D21), que sí da una
   indicación explícita —llamar al 123 o ir a urgencias—. Es deliberado: ahí
   el paciente ya dijo que está en peligro, y el silencio es peor que la
   indicación. No es una clasificación del sistema: es la respuesta a lo que
   él pidió.
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
6b. **El bot no promete lo que el sistema no hace (D26, 02/10/2026).** Como
    nadie le escribe al paciente, ningún mensaje puede decirle «te escribiré»,
    «te escribiremos», «te avisaremos» ni nada de esa familia: lo vigila
    `test_ningun_mensaje_promete_que_se_le_escribira`, que recorre todos los
    `MSG_*` y `RESP_*`. Lo que se le dice es la verdad: `MSG_SIN_CHECKIN` le pide
    que escriba él, el reporte de la mañana desde las 7:00 y el de la tarde
    desde las 2:00 (las horas salen de `crear_checkins_diarios`). Los cierres
    MEDIA y ALTA terminan en «Escríbeme en tu próximo turno para seguir con tu
    reporte». Cuando se implemente el envío saliente, esta regla se revisa en
    el mismo PR.

    De la misma familia: el aviso de un reporte abandonado dice «la última
    vez», y no «ayer», porque puede ser de cualquier día anterior. Y si hoy no
    hay turno, va seguido de `MSG_SIN_CHECKIN` en lugar de una pregunta que
    después se ignoraría (DB-12).
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
