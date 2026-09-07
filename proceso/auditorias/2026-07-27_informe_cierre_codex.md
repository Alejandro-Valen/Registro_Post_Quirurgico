# Informe de la auditoría de cierre y su verificación

> **Qué es este documento.** Lo que reportó el agente auditor (Codex) el
> 27/07/2026 sobre `sprint-5-produccion`, y **el resultado de reproducir cada
> hallazgo contra el código**. No es el informe de Codex copiado: es el informe
> más lo que sobrevivió a la verificación.
>
> **Por qué la separación importa.** La instrucción de auditoría
> (`2026-07-25_instruccion_cierre_loops_a_b_c.md`, sección 11) exige reproducir
> cada hallazgo antes de tocar nada: *un informe de otro agente es una hipótesis,
> no un hecho*. En esta ronda esa regla cambió dos correcciones de sitio y
> encontró una ocurrencia que el informe no vio.

**Fecha:** 27/07/2026 · **Rama:** `sprint-5-produccion` · **HEAD:** `2eb7801`
**Auditor:** Codex · **Verificación:** Claude Code, con León (Arquitecto)
**Instrucción de origen:** `2026-07-25_instruccion_cierre_loops_a_b_c.md`

---

## Veredicto

**Codex: BLOQUEADO.** Dos hallazgos ALTOS verificados.

**Tras la verificación: se sostiene el bloqueo**, con dos matices que no cambian
la conclusión pero sí cambian dónde va la corrección:

1. **Ninguno de los dos rojos es una fuga hoy.** No ha habido nunca un paciente
   real en el sistema; los nombres que hoy están en los logs de Railway son de
   los pacientes demo. No es una emergencia: es un loop de una sesión.
2. **La mecánica del hallazgo 1 no es la que dice el informe.** Corregir lo que
   Codex señala no habría cerrado la fuga.

---

## Línea base — confirmada de forma independiente

Medida en la máquina del Arquitecto antes de leer el informe, para poder
contrastar las cifras que reportaba el auditor en vez de creerlas:

| Comprobación | Resultado |
|---|---|
| `python manage.py test --noinput` | **319 tests OK** (112 s) |
| `python manage.py check` | sin issues |
| `makemigrations --check --dry-run` | No changes detected |
| `pip-audit -r requirements-runtime.txt` | sin vulnerabilidades conocidas |
| Árbol de trabajo | limpio, sincronizado con `origin` (0/0) |
| Distancia a `Desarrollo` | 101 commits · 95 archivos · +15.719 / −1.955 |

Coinciden con las de Codex. (Codex reportó la suite en 270 s contra 112 s: es
diferencia de máquina, no de resultado.)

---

## Hallazgo 1 — Identidad del paciente en la salida operativa

**Codex: 🔴 ALTO, verificado. Tras reproducirlo: real, pero por otro canal.**

### Lo que dice el informe

Que `settings.py:189` afirma filtrar PHI/PII sin hacerlo, y que la identidad del
paciente llega a los logs por `logger.info` y por `stdout` en
`desactivar_pacientes_vencidos`, más el traceback de `bot.py:536`.

### Lo que se reprodujo

**El canal real es `stdout`, no el logger.** El logger `signos_sintomas` está
configurado en nivel `WARNING` (`settings.py:229`), así que **todo `logger.info`
con datos del paciente se descarta antes de emitirse**:

```
signos_sintomas.management.commands.desactivar_pacientes_vencidos
  isEnabledFor(INFO)  = False
  isEnabledFor(ERROR) = True
```

Lo que sí sale, literal, capturado de la salida del comando:

```
| desactivar_pacientes_vencidos: Maria Fernanda Quintero desactivado (POD 12)
```

Es `self.stdout.write` (línea 66). Railway captura la salida estándar del
proceso igual que los logs. **La corrección apunta a la línea 66, no a la 65.**

### Lo que el informe no vio

- **`enviar_recordatorios.py:48` arma nombre completo _y teléfono_** de cada
  check-in pendiente. Hoy está mudo por el nivel del logger, pero es una bomba
  con temporizador: basta bajar el nivel a INFO para volcar la lista completa de
  pacientes con su celular. Capturado forzando el nivel:

  ```
  enviar_recordatorios: check-in 2 — paciente Maria Fernanda Quintero
  (+573001234567) — programado 2026-07-27T… — [envío Twilio pendiente FASE 4]
  ```

- **El comentario de `settings.py:189` promete una garantía de privacidad que no
  existe.** El único filtro configurado es `RequireDebugFalse`; no hay redacción
  de ningún tipo. Un comentario que miente sobre una garantía de privacidad es
  peor que no tener comentario: hace que nadie vuelva a mirar.

### Lo que quedó en "supuesto", no en "verificado"

El traceback de `bot.py:536` (`logger.exception`) **sí se emite** — ERROR pasa el
umbral, confirmado — y arrastra el mensaje de la excepción. Pero Codex lo
"verificó" inyectando su propio `RuntimeError: detalle sensible`. Que una
excepción **real** del motor de alertas cargue datos clínicos es posible y no
está demostrado. El encabezado que escribe el propio código usa solo `pk`s.

Se registra como **exposición condicional**: real como vía, sin caso conocido.

→ Decisión **[D11](../../docs/decisiones_correccion_auditoria.md#d11)**

---

## Hallazgo 2 — Paciente activo sin médico responsable

**Codex: 🔴 ALTO, verificado. Tras reproducirlo: confirmado, y peor.**

### Lo que se reprodujo

Con el formulario **real** que genera `PacienteAdmin` para un médico
no-superusuario:

```
required           = False
opciones ofrecidas = ['dra_triage']
form.is_valid()    = True
guardado -> medico_responsable = None
pacientes visibles para la dra = []
KPI del tablero: {'alta': 0, 'silencios': 0, 'pendientes': 0, 'activos': 0}
```

El desplegable sale **vacío por defecto** y con una sola opción posible. Dejarlo
así es el camino de menor resistencia, no un descuido rebuscado.

### Lo que el informe no vio

- El paciente huérfano **no solo desaparece del listado: desaparece de los KPI
  del tablero de triage.** El médico ve ceros, no un hueco. El fallo es
  silencioso, que es lo que lo hace peligroso.
- La alerta ALTA de ese paciente queda con `destinatario=''`, y
  `procesar_notificaciones_email` **lanza `CommandError`**. La corrida del cron
  queda en rojo de forma permanente, enmascarando cualquier otro fallo real.

### Lo que se revisó y está bien

`procesar_notificaciones_email` es la **última** tarea tanto de `cron_matutino`
como de `cron_operativo`, así que ese `CommandError` **no salta ninguna tarea
posterior**. No hay efecto dominó. Se deja anotado para que la próxima revisión
no lo investigue otra vez.

→ Decisión **[D12](../../docs/decisiones_correccion_auditoria.md#d12)**

---

## Hallazgo 3 — La firma de Twilio depende del entorno en producción

**Codex: 🟡 ALTO condicional. Tras verificar: correcto, y el estado real es
seguro — pero por accidente, no por diseño.**

`settings_production.py` no vuelve a fijar `TWILIO_VALIDATE_SIGNATURE`: hereda
lo que diga el entorno. Con la variable en `False`, el webhook acepta cualquier
POST sin firma, en silencio, y `check --deploy` no lo reporta.

**Estado real en Railway (verificado por el Arquitecto en el panel el
27/07/2026):** la variable **no existe** en el servicio web. `TWILIO_AUTH_TOKEN`
sí está. Como el default del código es `True`, hoy la validación está **activa**.

**Y por eso mismo no se debe crear la variable.** `python-decouple` convierte
una cadena vacía en `False`:

```
variable AUSENTE     -> True     ← el estado actual
variable VACIA ('')  -> False    ← la firma queda desactivada
variable = True      -> True
```

Railway **reemplaza por cadena vacía toda referencia que no puede resolver**
(`docs/trampas_conocidas.md`, incidente del 25/07). Crear la casilla introduce
exactamente el modo de fallo que ya costó una madrugada: el día que alguien la
mueva a *Shared Variables* o la apunte mal, la cerradura del webhook se abre sin
decir nada.

→ Decisión **[D13](../../docs/decisiones_correccion_auditoria.md#d13)**

---

## Hallazgo 4 — Documentos que contradicen el código

**Codex: 🟢 BAJO. Verificado: los cinco.**

| Documento | Qué afirma | Qué dice el código |
|---|---|---|
| `ROADMAP:374` | escalera SILENCIO `1/2/3+` | `1/2/4` (D1, y `reglas_clinicas.md`) |
| `CLAUDE.md:180` | "Loop C en curso" | los tres loops están cerrados |
| `bot_whatsapp.md:17` | "`views.py`, pendiente" · 69 tests | `views.py` existe desde el Sprint 3 · 319 tests |
| `modelos_datos.md:173` | `fecha_ultimo_registro` "controla un registro por día" | nunca se lee (D9) |
| `proceso/README.md:68` | el verificador fechado no es importable | el comando documentado funciona |

**El primero no es polvo documental: es un umbral clínico mal escrito en un
documento vivo.** Los otros cuatro sí lo son.

---

## Verificación de las correcciones de los Loops A, B y C

Codex las revisó una por una y las dio por buenas, con dos salvedades honestas:
no repitió la consulta remota de D7 contra Railway (no tenía acceso), y señaló
que el hallazgo 14 dejó las contradicciones documentales de arriba. Ambas cosas
son correctas.

**Ninguna corrección de los Loops A, B o C resultó ser falsa.** El trabajo de
esos tres loops se sostiene.

---

## Objeciones a las decisiones D1-D10

Codex no objetó ninguna. Registró una condición sobre D2 con la que este informe
coincide: *el fallo abierto del webhook es aceptable **siempre que la firma de
Twilio siga siendo obligatoria*** — que es precisamente lo que D13 convierte en
garantía en vez de en configuración.

---

## Lo que se revisó y está bien

Del informe de Codex, confirmado o no contradicho: aislamiento entre médicos,
permisos inmutables de registros y alertas, constraints, idempotencia y
concurrencia del webhook, outbox transaccional, rate limiting, dependencias,
migraciones, ausencia de secretos versionados, CSP/HTTPS, y respuestas de error
sin stacktrace hacia el cliente.

Añadido por esta verificación: el orden de tareas de los dos cron resiste que
`procesar_notificaciones_email` falle.

---

## Qué pasa después

Loop D, con el método de `proceso/metodo_de_trabajo.md`: fichas
**D11, D12 y D13** escritas antes de programar, prueba en rojo, implementación,
verificación del Arquitecto. Estado de avance en
`docs/decisiones_correccion_auditoria.md`.

**Advertencia de orden.** Railway despliega el servicio web desde
`sprint-5-produccion`: **cada push del Loop D sale a producción de inmediato.**
Mergear a `Desarrollo`, en cambio, no despliega nada.
