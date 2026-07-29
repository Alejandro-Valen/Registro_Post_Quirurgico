# Instrucción para la próxima sesión — cerrar la rama del Sprint 5

> **Qué es esto.** El guion exacto de lo que falta para dejar `sprint-5-produccion`
> atrás y poder abrir la rama del trabajo siguiente. Se escribió al terminar el
> Loop D (27/07/2026) para que la sesión que retome no tenga que reconstruir el
> plan de una conversación.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md` y del "Estado de avance" de
> `docs/decisiones_correccion_auditoria.md`.

---

## Dónde quedamos

Los cuatro loops de corrección (A, B, C y D) están **cerrados, verificados y
publicados**. El push del Loop D salió el 27/07/2026 y con él fueron a producción
las migraciones **0027** (`PROTECT` en `medico_responsable`) y **0028**
(`CheckConstraint`: paciente activo ⇒ médico responsable).

Estado al cerrar esa sesión: **337 tests OK**, `check` sin issues,
`makemigrations --check` limpio, y la verificación independiente
`docs/proceso/verificaciones/2026-07-27_verificacion_loop_d.py` en verde (8 bloques).

**Lo que falta no es corrección de código.** Es cerrar la rama.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos el cierre de la rama sprint-5-produccion. Soy León (Arquitecto).

Antes de proponer nada:
1. Lee docs/proceso/2026-07-28_instruccion_cierre_rama_sprint5.md — es el guion
   de esta sesión.
2. Lee el "Estado de avance" de docs/decisiones_correccion_auditoria.md y la
   última entrada de BITACORA.md.
3. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

Los cuatro loops están cerrados y pusheados. Las decisiones D1-D14 están tomadas
y no se reabren. Hoy NO se escribe código nuevo salvo que el paso 4 lo exija.

Empezamos por el paso 1 del guion: la revisión del diff contra origin/Desarrollo.
```

---

## Paso 1 — Revisar el diff completo contra `Desarrollo`

Son ~117 commits y ~95 archivos. No es trámite: es la última mirada antes de que
todo esto entre a la rama de integración.

```bash
git fetch origin
git diff --stat origin/Desarrollo...HEAD
git log --oneline origin/Desarrollo..HEAD
```

**Cómo revisarlo sin ahogarse.** Por área, no archivo por archivo, y prestando
atención a lo que **cambia comportamiento clínico**:

| Área | Qué mirar |
|---|---|
| `alert_engine.py` | La escalera de SILENCIO (1/2/4) y la condición MEDIA de hinchazón |
| `models.py` + migraciones 0025-0028 | Los cuatro campos y las dos restricciones nuevas |
| `bot.py` | El mensaje de fiebre sin cifras (D4) |
| `admin.py`, `panel_admin.py` | Asignación de responsable y los dos avisos del tablero |
| `settings*.py` | Firma de Twilio fija, variables obligatorias, cabeceras de proxy |
| `tests.py` | Que las pruebas nuevas midan el requisito, no el código |

**Lo que NO hay que volver a hacer:** las dos auditorías (22/07 y 27/07) ya se
ejecutaron y sus hallazgos ya se corrigieron. Esto es una lectura de cierre, no
una auditoría nueva.

---

## Paso 2 — PR y merge a `Desarrollo`

```bash
gh pr create --base Desarrollo --head sprint-5-produccion
```

En la descripción del PR: qué entregó el Sprint 5, los cuatro loops, y el enlace
a `docs/decisiones_correccion_auditoria.md`. El PR es la última compuerta.

**Mergear a `Desarrollo` NO despliega nada.** Es un cambio de registro del
proyecto, no un evento de producción. Railway sigue mirando
`sprint-5-produccion` hasta el paso 3.

---

## Paso 3 — Crear `produccion` y reapuntar Railway

**Este es el paso que libera la rama.** Sin él, `sprint-5-produccion` sigue
siendo la rama viva de producción y cualquier push a ella —por costumbre— sale al
aire.

```bash
git checkout Desarrollo
git pull origin Desarrollo
git checkout -b produccion
git push -u origin produccion
```

Después, en el panel de Railway → servicio **web** → *Settings* → *Source*:
cambiar la rama de `sprint-5-produccion` a `produccion`. Lo mismo en los
servicios cron (`cron-manana` y `cron-tarde`), que también siguen la rama.

**Por qué `produccion` y no `Desarrollo`.** `Desarrollo` es la rama de
integración: ahí aterriza el trabajo de cada sprint, incluido lo que está a medio
hacer. Apuntar producción ahí significa que todo lo que se integra queda delante
de un paciente sin que nadie lo decida. Con una rama aparte, **desplegar vuelve a
ser un acto explícito** —un merge de `Desarrollo` a `produccion`— en vez de una
consecuencia de integrar.

**Verificar después del reapuntado:** que el deploy de `produccion` termine en
SUCCESS, que `/salud/` responda 200 y que el Admin cargue. Recién ahí
`sprint-5-produccion` queda muerta y se puede borrar.

---

## Paso 4 — Abrir la rama siguiente

Desde `Desarrollo`, nunca desde `produccion`:

```bash
git checkout Desarrollo
git checkout -b sprint-6-<tema>
```

---

## El Loop E, explicado

**No bloquea nada de lo anterior.** Va después del PR y **antes del piloto con
pacientes reales**. Decisión completa: ficha **D14** en
`docs/decisiones_correccion_auditoria.md`.

### El problema

`cron_matutino` y `cron_operativo` ejecutan sus tareas con `call_command` en un
bucle **sin manejo de errores**. Si una tarea falla, las siguientes no corren.

El caso que importa está en `cron_operativo`:

```
cerrar_checkins_vencidos → reintentar_evaluaciones_alertas → procesar_notificaciones_email
```

Un fallo persistente de la **primera** impide que salgan los correos de alerta
ALTA de ese ciclo. La tarea que genera las alertas de silencio y la que entrega
los avisos al médico están encadenadas por una razón que no es clínica: que el
plan de Railway no daba para más servicios cron.

### La decisión

**Un fallo operativo no puede impedir que se entregue una alerta clínica ya
generada.** Las tareas se aíslan entre sí, **salvo cuando hay una dependencia
clínica declarada**.

1. El runner ejecuta **todas** las tareas, captura el fallo de cada una y
   **termina con estado de error** informando cuáles fallaron. No se rinde en la
   primera ni finge que todo salió bien.
2. **Excepción declarada:** en `cron_matutino`, si `desactivar_pacientes_vencidos`
   falla, `crear_checkins_diarios` **no debe ejecutarse**. Si se ejecutara, un
   paciente que vence ese día recibiría un check-in que quedaría `PENDIENTE` para
   siempre y generaría una **alerta SILENCIO espuria**. Las dependencias se
   escriben en el propio comando, con su motivo clínico al lado.

**Por qué no basta con "continuar ante el fallo"**, que es la corrección obvia:
`cron_matutino` tiene un orden clínicamente obligatorio. Continuar ciegamente
produce exactamente el daño de arriba. El aislamiento tiene que ser **selectivo y
declarado**, no automático.

### Cómo se ejecuta

Con el mismo método de siempre, en dos commits:

- **E-1** `test: reproducir que un fallo temprano del cron impide entregar alertas`
  — en rojo, y con un segundo caso que verifique que la dependencia clínica de
  `cron_matutino` **sí** se respeta.
- **E-2** `fix: aislar las tareas del cron conservando las dependencias clinicas`

### Deuda de infraestructura asociada

El agrupamiento existe porque el plan actual de Railway limita los servicios
cron. Al mejorar el plan, `cron-operativo` pasa a servicio propio y `cron-tarde`
vuelve a su horario original — y buena parte del acoplamiento desaparece sola.
**D14 es lo que hace que el sistema sea correcto mientras tanto.**

---

## Lo que sigue pendiente del piloto real (no es de esta sesión)

Está en `CLAUDE.md`, "Por resolver antes del piloto real". Lo que más se cruza
con lo hecho en el Loop D:

- **El correo de alerta no se puede probar de punta a punta con los demos.**
  `signals.py` corta la notificación cuando la cédula empieza por `DEMO-`, así
  que un paciente de ejemplo **nunca encola correo**. Hace falta un paciente con
  cédula real asignado a un médico con correo.
- Los demos vencen solos: el seed les pone la fecha de cirugía 8-10 días atrás,
  así que nacen en POD 8-10 y `desactivar_pacientes_vencidos` los cierra a los
  10. Para ver la escalera de SILENCIO en vivo hace falta un paciente con cirugía
  reciente.
- Salir del Sandbox de Twilio, dominio autenticado en Resend, monitoreo externo
  apuntando a `/salud/`, y el consentimiento HABEAS DATA firmado.
