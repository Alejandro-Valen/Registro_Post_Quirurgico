# Instrucción de auditoría de cierre — antes del PR a `Desarrollo`

> **Para el agente auditor (Codex u otro).** Este documento es autocontenido: no
> necesitas ninguna conversación previa. Léelo completo antes de tocar nada.
>
> **Fecha:** 25/07/2026 · **Rama:** `sprint-5-produccion`
> **Encargada por:** León (Arquitecto) · **Entregable:** un informe escrito

---

## 1. Qué se te pide

El proyecto está a un paso de mergear a `Desarrollo` y de convertirse en el MVP
que empezará a usarse. Antes de ese merge se quiere **una revisión
independiente, profunda y honesta** del estado real del sistema.

No es un repaso de estilo ni una búsqueda de perfección: es responder con
evidencia a tres preguntas, en este orden de importancia:

1. **¿Hay algo que no debería entrar a `Desarrollo`?**
2. **¿Hay algo que haría daño —o dejaría a alguien sin atención— si mañana
   entrara un paciente real?**
3. **¿Qué haría a este sistema mejor de lo que es hoy**, sin retrasar lo
   anterior?

El Arquitecto quiere un equilibrio explícito: **ni una auditoría superficial de
"lo mínimo para mergear", ni una lista de cincuenta observaciones de estilo que
entierre lo importante.** La clasificación de la sección 8 es lo que sostiene
ese equilibrio: revisa todo, pero separa lo que bloquea de lo que no.

---

## 2. Reglas de esta auditoría (no negociables)

1. **No edites nada.** Ni código, ni documentación, ni configuración. No hagas
   commits, no crees ramas, no publiques, no fusiones. Tu entregable es un
   informe. Si mezclas auditar y arreglar, se vuelve imposible saber si un
   hallazgo era real o lo creaste al tocar algo.
2. **Cada hallazgo necesita evidencia reproducible:** archivo, línea, y cómo
   verlo fallar (un comando, una consulta, un escenario concreto). Sin eso no es
   un hallazgo, es una opinión — y como opinión debe ir etiquetada.
3. **Distingue lo que verificaste de lo que supones.** Si no pudiste
   reproducirlo, dilo. Un hallazgo no confirmado sigue siendo valioso, pero
   marcado como tal.
4. **Manda el código.** Si un documento y el código se contradicen, el código es
   lo que corre; repórtalo como incoherencia documental, no como defecto de
   comportamiento.
5. **No reabras las decisiones de la sección 6.** Están tomadas, razonadas y
   documentadas. Si crees que una es incorrecta, dilo en una sección aparte del
   informe titulada "Objeciones a decisiones tomadas", con tu argumento — pero
   no la trates como hallazgo pendiente.
6. **No repitas la auditoría de julio.** Sus 14 hallazgos ya están corregidos
   (sección 5). Lo que sí debes hacer es **verificar que cada corrección hace lo
   que dice** — eso es distinto de volver a buscarlos.

---

## 3. Qué es este sistema, en cuatro líneas

Monitoreo remoto de pacientes en recuperación de cirugía colorrectal. El
paciente responde por WhatsApp dos veces al día; un motor de reglas clínicas
fijas clasifica cada reporte y genera alertas de tres severidades; el médico las
atiende desde un panel en Django Admin y recibe correo cuando algo llega a ALTA.

**La IA no diagnostica.** Todo se decide con reglas explícitas y auditables.

Django 6 + PostgreSQL 18 + Redis, desplegado en Railway. **Nunca ha habido un
paciente real en el sistema**: todo lo que hay son datos de demostración.

### Por dónde empezar a leer

| Documento | Qué contiene |
|---|---|
| `CLAUDE.md` | Puerta de entrada: qué es, cómo se trabaja, estado y mapa de todo lo demás |
| `docs/reglas_clinicas.md` | Las 8 reglas del motor + la regla operativa SILENCIO. **Fuente única** |
| `docs/modelos_datos.md` | Los modelos y por qué cada campo existe |
| `docs/bot_whatsapp.md` | Máquina de estados del bot y sus reglas no negociables |
| `docs/decisiones_correccion_auditoria.md` | Fichas D1-D10 con el razonamiento de cada corrección |
| `docs/trampas_conocidas.md` | Errores de despliegue que ya costaron horas |
| `proceso/metodo_de_trabajo.md` | Cómo se corrige algo en este proyecto |
| `proceso/BITACORA.md` | Cronología completa, incluidos los problemas y cómo se resolvieron |

---

## 4. De dónde viene todo esto

El 22/07/2026 una auditoría independiente sobre el commit `fbf62a8` **bloqueó el
PR**. Confirmó las cuatro cifras que se reportaban (280 tests, `check --deploy`,
`pip-audit`, migraciones al día) y que el aislamiento por médico resistía un
intento activo de romperlo con 15 comprobaciones. Pero encontró **14 hallazgos**,
uno de ellos grave:

> La escalera de severidad de las alertas SILENCIO **nunca escalaba en
> producción**. Un paciente con tres días completos sin responder producía
> `SILENCIO / BAJA`, que en el tablero se ordena de últimas. Sobrevivió a 280
> pruebas en verde porque los tests prefijaban un estado que el scheduler real
> nunca produce.

En paralelo, un **ejercicio de documentación** —pedirle a otra sesión que
*explicara* el sistema explorando el código— encontró **tres cosas más** que la
auditoría no vio (D8, D9, D10). Es un dato relevante para ti: **explicar algo
obliga a entenderlo de otra forma que auditarlo.** Se recomienda que dediques
parte de tu revisión a intentar explicar cómo funciona cada pieza, no solo a
buscar defectos.

La corrección se organizó en tres loops (A: clínico y bloqueante; B:
trazabilidad y operación; C: coherencia e higiene), con las decisiones tomadas y
escritas **antes** de programar.

---

## 5. Los 14 hallazgos y cómo se corrigió cada uno

Verifica que cada corrección hace lo que dice. Los commits están en
`sprint-5-produccion`.

| # | Hallazgo | Corrección | Commit |
|---|----------|-----------|--------|
| 1 | **ALTO** — la escalera de SILENCIO nunca escalaba | Racha corregida (solo check-ins estrictamente anteriores; un `PENDIENTE` no la rompe) y escalera 1/2/4 → D1 | `20ee837` (test rojo: `a6afb30`) |
| 2 | El envío de correo bloqueaba filas de paciente y alerta | `select_for_update(of=('self',))` | `f8fa437` |
| 3 | La migración 0020 dio por evaluados registros sin verificarlo | D7: consulta de solo lectura en producción. Resultado **cero** el 25/07 | Sin cambio de código, por decisión |
| 4 | No se registraba **quién** resuelve cada alerta | Campo `Alerta.resuelta_por` + `log_change`, migración 0025, **sin backfill** → D3 | `e143336` |
| 5 | El rate limit tumbaba el webhook si Redis caía | Webhook **falla abierto**, formulario **falla cerrado**, verificación antes de reclamar el SID, límite 20 → 60 → D2 | `e8acc33` |
| 6 | Se confiaba en cabeceras de proxy en toda configuración | `TRUST_RAILWAY_PROXY` gobierna esquema, host e IP; por defecto no se confía | `ec02ef4` |
| 7 | El fallo del motor no dejaba rastro en la ruta del bot | `registrar_fallo_evaluacion` reescribe el estado fuera del savepoint revertido | `5ad976f` |
| 8 | El filtro del Admin exponía las cuentas de otros médicos | `MedicoResponsableListFilter` sin opciones para no-superusuario | `b2eaa17` |
| 9 | La migración 0019 fabricó una `fecha_resolucion` | Comentario corregido: LEGACY es honesto, la fecha sí es un dato inventado | `c5174c1` |
| 10 | Se perdía el signo menos grave de íleo concurrente | `DeteccionAlerta.mensaje_detectado` acumula, idempotente → D5 | `f4892fc` |
| 11 | Una variable de entorno vacía arrancaba en silencio | `config_obligatoria`: rechaza vacías y placeholders `<...>` | `7b7454d` |
| 12 | El bot le daba un umbral clínico al paciente | Se retiró el número de `RESP_FIEBRE` → D4. **Redacción final pendiente del médico** | `0ac7021` |
| 13 | Nada se rendía nunca: reintentos infinitos | Tope de 10 intentos, estado terminal `FALLIDA` visible en el tablero → D6 | `e75ba83` |
| 14 | La documentación de despliegue no coincidía con el código | Seis discrepancias corregidas, incluido un crontab de ejemplo que habría fallado siempre | `f82a973` |

### Los tres hallazgos del ejercicio de documentación

| # | Hallazgo | Decisión y corrección | Commit |
|---|----------|----------------------|--------|
| D8 | Las reglas de días consecutivos cuentan **días con datos**, no días de calendario: un día sin reportar corta el conteo | **Manda el código**; se corrigió la documentación, que decía otra cosa. Contar a través de un día sin datos inventaría un hecho clínico | `e7155cb` |
| D9 | `ConversacionWhatsApp.fecha_ultimo_registro` se escribe y **nunca se lee** | Marcado obsoleto en comentario (no en `help_text`, para no arrastrar una migración). No se borra la columna | `c5174c1` |
| D10 | La condición MEDIA de hinchazón encadenaba tres comparaciones y dos se volvían triviales sin el dato de ayer | Pruebas de caracterización primero, después reescritura legible **sin cambiar cuándo dispara** | `21b8d79` + `922e13c` |

### Trabajo adicional del Loop C

- **Blindaje de medianoche** (`cc84037`): 14 pruebas de cinco clases fallaban si
  la corrida cruzaba la medianoche de Bogotá. Es fragilidad de las pruebas, no
  del motor (que usa `timezone.localdate()`). Se congela el reloj de esas clases
  en el peor instante del día con `freezegun`, que está **solo** en
  `requirements.txt` y no en `requirements-runtime.txt`.
- **Reestructuración documental** (`27b1960`): `CLAUDE.md` bajó de 54.742 a
  ~18.000 caracteres y cada tema quedó con un archivo dueño. El contenido se
  movió textual con script, verificando que ningún dato duro quedara sin
  destino.
- **Incidente de producción** (`b601e93`, `0999c2a`): la validación del hallazgo
  11 tumbó los dos servicios cron al desplegar, porque tenían un entorno
  distinto al del web. Resuelto y documentado en `docs/trampas_conocidas.md`.

---

## 6. Decisiones tomadas — NO las reabras como hallazgos

Todas están razonadas en `docs/decisiones_correccion_auditoria.md`. Léelas antes
de opinar sobre lo que tocan.

| ID | Decisión | El punto que suele malinterpretarse |
|----|----------|-------------------------------------|
| D1 | Escalera de SILENCIO 1/2/4, contando check-ins | No cuenta días calendario **a propósito**: SILENCIO es ausencia de datos, no un síntoma. Resolver una alerta no reinicia la racha, y eso es deliberado |
| D2 | Webhook falla abierto, formulario falla cerrado | Asimetría intencional: la firma de Twilio protege el webhook; el formulario no tiene otra cerradura |
| D3 | `resuelta_por` sin backfill | Rellenar sería **fabricar una atribución clínica** |
| D4 | Sin umbrales clínicos en los mensajes al paciente | La redacción final la valida el médico, no el equipo técnico |
| D5 | Los signos concurrentes se acumulan en el detalle, no en el titular | `Alerta.mensaje` es el titular del tablero y debe caber en una línea |
| D6 | Tope de 10 reintentos y estado `FALLIDA` visible | Rendirse en silencio sería peor que reintentar para siempre |
| D7 | Contar antes de actuar; **jamás reevaluar en masa** | Reevaluar historia mandaría correos ALTA de episodios viejos |
| D8 | Un día sin datos corta el conteo | Contar a través del hueco inventaría un hecho clínico. **La pregunta clínica sigue abierta** y es del médico |
| D9 | Campo obsoleto marcado, no borrado | Borrar una columna en producción no se justifica en medio de un merge bloqueado |
| D10 | La condición MEDIA se reescribió **sin cambiar comportamiento** | Cambiar cuándo dispara es mover un umbral clínico: requiere al Arquitecto y al médico |

**Umbrales clínicos:** ninguno se cambia sin decisión explícita del Arquitecto y
validación del médico. Si encuentras uno que te parece incorrecto, va en
"Objeciones", con tu argumento clínico y su fuente.

---

## 7. Lo que YA se sabe pendiente (no lo reportes como hallazgo)

Está todo en `CLAUDE.md`, sección "Por resolver antes del piloto real". Resumen:

1. **`enviar_recordatorios` es un stub**: el sistema es reactivo, el paciente
   debe escribir primero. La integración de Twilio saliente está diferida.
2. **Sandbox de Twilio**, no WhatsApp Business API.
3. **Dominio de Resend sin autenticar**: los correos llegan a spam.
4. **Sin monitoreo externo** apuntando al endpoint de salud.
5. **Datos del médico en la landing** entre `[corchetes]`, con aviso de boceto.
6. **HABEAS DATA sin completar** (campos entre corchetes del formato legal).
7. **Validación médica pendiente** de las cuatro respuestas del bot (D4).
8. **Deuda menor:** los dos servicios cron usan la URL literal de Redis en vez
   de la referencia al servicio.
9. **RAG/MCP** en el bot está diferido a Sprint 6.

Si crees que alguno de estos **debería bloquear el merge** (y no solo el piloto),
dilo — pero como argumento, no como descubrimiento.

---

## 8. Alcance de la revisión y cómo clasificar

Revisa **todo lo que consideres relevante**, incluyendo como mínimo:

- **Lógica clínica:** las 8 reglas del motor y SILENCIO. ¿Hacen lo que la
  documentación dice? ¿Hay casos límite sin cubrir? ¿Alguna combinación produce
  una severidad que no corresponde?
- **Integridad de datos:** transacciones, constraints, migraciones, condiciones
  de carrera, idempotencia del webhook y del outbox de correo.
- **Seguridad y privacidad:** aislamiento por médico, PHI/PII en logs y correos,
  el webhook, el Admin, el rate limit, las cabeceras de proxy.
- **Arquitectura:** acoplamientos, responsabilidades mal repartidas, cosas que
  serán difíciles de cambiar cuando haya pacientes.
- **Pruebas:** ¿alguna pasa en verde por el motivo equivocado? ¿Qué no está
  cubierto? Las 319 pruebas no son garantía: el hallazgo grave de julio
  sobrevivió a 280.
- **Documentación:** ¿alguna afirmación contradice el código?
- **Operación:** cron, despliegue, variables, qué pasa si un componente cae.
- **Planeación:** ¿el alcance del MVP es coherente? ¿Falta algo indispensable
  para atender a un paciente de forma segura?

**Clasifica cada hallazgo en una sola caja:**

| Caja | Criterio |
|------|----------|
| 🔴 **BLOQUEA EL MERGE** | Es incorrecto y entraría así a `Desarrollo` |
| 🟡 **BLOQUEA EL PILOTO** | Puede mergearse, pero no puede estar delante de un paciente real |
| 🟢 **POST-MVP** | Mejora legítima que no debe retrasar nada |

Sé estricto con la caja roja: úsala solo para lo que de verdad no debería
entrar. Un hallazgo importante mal clasificado hace que se ignoren todos.

---

## 9. Cómo verificar el estado real antes de opinar

```bash
cd Registro_Post_Quirurgico
python manage.py test --noinput          # línea base: 319 tests OK
python manage.py check
python manage.py makemigrations --check --dry-run
pip-audit -r ../requirements-runtime.txt
```

`--noinput` evita quedarse esperando el prompt de borrado si una corrida
anterior dejó la base de pruebas a medias.

También hay una verificación que imprime evidencia en pantalla de las
correcciones del Loop C, en
`proceso/verificaciones/2026-07-25_verificacion_loop_c.py`.

**Si algo de este documento no coincide con `git log` o con la suite, manda
Git** y anótalo como hallazgo: significa que la documentación quedó desfasada.

---

## 10. Qué entregar

Un informe escrito con:

1. **Veredicto en una línea:** ¿se puede mergear a `Desarrollo`, sí o no?
2. **Confirmación de cifras:** tests, `check`, migraciones, `pip-audit`.
3. **Hallazgos**, agrupados por caja (🔴/🟡/🟢) y ordenados por gravedad dentro
   de cada una. Cada uno con: qué está mal, dónde (archivo:línea), **cómo
   reproducirlo**, qué impacto tiene, y si lo verificaste o lo supones.
4. **Verificación de las correcciones** de la sección 5: ¿alguna no hace lo que
   dice?
5. **Objeciones a decisiones tomadas**, si tienes alguna (sección aparte).
6. **Lo que revisaste y encontraste bien.** Es tan útil como lo que está mal:
   evita que la próxima auditoría lo repita.

No propongas parches en el informe: describe el problema con precisión. Las
correcciones se deciden después, y se implementan con el método de
`proceso/metodo_de_trabajo.md` — decidir, documentar, prueba en rojo,
implementar, verificar.

---

## 11. Qué pasa después

El informe vuelve al Arquitecto. **Cada hallazgo se reproduce contra el código
antes de tocar nada**: un informe de otro agente es una hipótesis, no un hecho —
la auditoría de julio empezó confirmando las cifras de la sesión anterior antes
de contradecirla en lo demás. Lo que sobreviva a esa verificación se organiza en
un loop de corrección con el método de siempre, y solo entonces se prepara el PR.
