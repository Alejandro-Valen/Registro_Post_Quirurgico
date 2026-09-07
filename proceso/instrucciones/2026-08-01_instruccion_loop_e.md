# Instrucción para la próxima sesión — Loop E (D14)

> **Qué es esto.** El guion de la sesión que sigue al montaje de la CI. Se
> escribió el 31/07/2026 para que quien retome no tenga que reconstruir el plan
> de una conversación.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**La CI está montada y mergeada.** PR #5 (`5b40c01`), y sobre ella tres PRs más
el mismo día: #6 documentación, #7 el arreglo de un hallazgo que la propia CI
encontró, #8 su documentación. `Desarrollo` quedó en `82b4d65`.

**Lo que cambió para esta sesión, y es lo primero que hay que entender:** ya no
hace falta verificar a mano que la suite pasa antes de un merge. **Cada PR se
verifica solo.** El workflow (`.github/workflows/ci.yml`) corre en cada PR hacia
`Desarrollo` y hacia `produccion`, y en cada push a esas dos ramas:

| Comprobación | Qué atrapa |
|---|---|
| `manage.py test --noinput` | Las 337 |
| `manage.py check` | Errores de configuración |
| `manage.py makemigrations --check --dry-run` | `models.py` cambiado sin migración |
| `manage.py check --deploy` con `settings_production` | Regresiones de seguridad del despliegue |
| `git diff --check` contra la base del PR | Espacios al final, marcadores de conflicto |

**Ojo con una cosa:** los checks **se ven pero no bloquean**. `Desarrollo` no
tiene protección de rama, así que se puede mergear en rojo. Configurarla pide
permisos de admin del repositorio, que la cuenta del Arquitecto no tiene. **Mirar
el check antes de mergear sigue siendo manual.**

**Rama activa de trabajo:** ninguna. La de esta sesión se abre desde
`Desarrollo`.

**Estado verificado al cerrar (31/07/2026):** suite **337 tests OK** (89 s en la
CI de Linux, 321 s en Windows), `check` sin issues, `makemigrations --check`
limpio, `git diff --check` limpio, `check --deploy` sin issues, `/salud/` en 200,
y los dos servicios cron de Railway completando todas sus tareas.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo para el Loop E. Soy __ (Arquitecto).

Antes de proponer nada:
1. Lee proceso/instrucciones/2026-08-01_instruccion_loop_e.md — es el guion de esta
   sesión.
2. Lee la ficha D14 en docs/decisiones_correccion_auditoria.md — la decisión ya
   está tomada y no se reabre.
3. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

El objetivo de hoy es UNO: el Loop E. Un loop, un tema. Dos commits: E-1 test en
rojo, E-2 corrección. No metas nada más en esta rama.
```

---

## El objetivo de hoy: D14, aislar las tareas del cron

**La decisión ya está tomada y escrita** en la ficha D14 de
`docs/decisiones_correccion_auditoria.md`. Esta sesión **implementa**, no decide.
Si algo de D14 parece discutible, se plantea al Arquitecto y él decide — no se
cambia sobre la marcha.

### El problema, en el código real

`cron_matutino.py` y `cron_operativo.py` recorren su lista con `call_command`
dentro de un `for`, **sin manejo de errores**. Si una tarea lanza, las siguientes
no corren.

```python
for tarea in TAREAS_OPERATIVAS:
    self.stdout.write(f'--- cron_operativo: {tarea} ---')
    call_command(tarea)
```

`TAREAS_OPERATIVAS` es `cerrar_checkins_vencidos` →
`reintentar_evaluaciones_alertas` → `procesar_notificaciones_email`. Un fallo
persistente de **la primera** impide que salgan los correos de alerta ALTA de ese
ciclo. Y `cron_matutino` no es ruta de respaldo: también lleva
`procesar_notificaciones_email` al final, con `cerrar_checkins_vencidos` por
delante. **Un mismo fallo aborta las dos rutas.**

Peor: en `TAREAS_MATUTINAS` la posición 4 la ocupa `enviar_recordatorios`, que
hoy **es un stub que no envía nada**. Un comando sin efecto clínico está por
delante de la entrega de alertas.

### Lo que hay que construir

1. **El runner ejecuta todas las tareas**, captura el fallo de cada una, y
   **termina con estado de error** informando cuáles fallaron. No se rinde en la
   primera ni finge que todo salió bien.
2. **Excepción declarada, y es la parte delicada:** en `cron_matutino`, si
   `desactivar_pacientes_vencidos` falla, `crear_checkins_diarios` **no debe
   ejecutarse**. La dependencia se escribe en el propio comando, con su motivo
   clínico al lado.

**Por qué esa excepción existe** (está en el docstring de `cron_matutino.py` y en
`docs/cron_setup.md`): si se invierte el orden, un paciente que vence ese día
recibe un check-in que quedará `PENDIENTE` para siempre y **generará una alerta
SILENCIO espuria**. Continuar ciegamente tras el fallo de la primera produce
exactamente ese daño. **El aislamiento tiene que ser selectivo y declarado, no
automático** — "continuar ante el fallo" a secas es la corrección obvia y sería
un error.

### Los dos commits, ya nombrados

De `docs/decisiones_correccion_auditoria.md`, sección "Loop E":

- [ ] **E-1** `test: reproducir que un fallo temprano del cron impide entregar alertas`
- [ ] **E-2** `fix: aislar las tareas del cron conservando las dependencias clinicas`

**E-1 tiene que nacer en rojo, y hay que entender por qué está rojo.** No basta
con verla fallar: hay que confirmar que falla por el requisito que dice medir y
no por otra cosa. Es la regla que nació del hallazgo bloqueante del 22/07 — una
escalera de alertas que nunca escalaba en producción sobrevivió a 280 pruebas en
verde porque la prueba se escribió mirando el código en vez del requisito.

Conviene que E-1 cubra **las dos caras**, porque son requisitos distintos:

- Un fallo de `cerrar_checkins_vencidos` **no** impide que corra
  `procesar_notificaciones_email`.
- Un fallo de `desactivar_pacientes_vencidos` **sí** impide que corra
  `crear_checkins_diarios`.

### Sincronización documental, en el mismo lote de commits

`docs/cron_setup.md` es el documento dueño de la programación de los comandos y
sus límites operativos. Si cambia cómo se comporta el runner ante un fallo, **ese
archivo se actualiza en el mismo lote**, no después. Y la ficha D14 pasa de
"Decidida, sin implementar" a implementada, con los SHAs.

---

## Cómo cerrarlo

1. Rama propia desde `Desarrollo`. Nombre sugerido: `loop-e-aislar-cron`.
2. E-1 en rojo, verificado y entendido. E-2. Suite completa en verde.
3. PR a `Desarrollo`. **La CI lo verifica sola** — mirar que los cinco checks
   estén en verde antes de mergear, porque no bloquean.
4. Verificación del Arquitecto: un script propio en
   `proceso/verificaciones/`, que imprima la evidencia en pantalla. El
   agente que escribió el código es el peor juez de si el código está bien.
5. Cierre: BITÁCORA, `CLAUDE.md`, y el guion de la sesión siguiente.

---

## Después de esto

En este orden, y **cada uno en su propia sesión**:

| Siguiente | Qué es |
|---|---|
| **Partir `tests.py`** | 6.122 líneas y 45 clases → paquete `tests/`. Va **después** del Loop E, que añade pruebas a ese archivo, y **antes** de que otra rama avance en paralelo. Es la ventana |
| **`crear_medico`** | Decidir qué hacer antes de entregarle la cuenta al médico. Ver abajo |

---

## Las decisiones que esperan al Arquitecto

Ninguna es de código: hay que tomarlas antes de programar.

**1 · `crear_medico` reescribe la cuenta del médico en cada arranque.** Ejecuta
`set_password`, `is_staff = True`, `groups.set([...])` y
`user_permissions.clear()` sobre un usuario que ya existe. Si el médico cambia su
contraseña en el Admin, el siguiente despliegue **la revierte en silencio**. Hoy
`medico_piloto` no puede tener una contraseña propia que sobreviva a un deploy.
Detalle en `proceso/auditorias/2026-07-29_revision_pr_sprint5.md`, punto 8.

**2 · Cómo mostrar el correo de alerta funcionando.** `signals.py` corta la
notificación cuando la cédula empieza por `DEMO-`, **antes** de mirar la
severidad. Es un guard deliberado, pero implica que el correo de alerta **nunca
se ha probado de punta a punta**. Mostrarlo requiere decidir cómo, y toca la
frontera que protege de correos espurios: es diseño, no implementación.

**Recordatorio del 29/07, todavía vigente:** los trámites del piloto real
(WhatsApp Business, plan de Railway, dominio en Resend, HABEAS DATA firmado)
quedan **diferidos por decisión del Arquitecto**. Primero se lleva el sistema al
mejor punto posible en desarrollo. **No proponer iniciarlos** hasta que él lo
indique.

---

## Pendientes menores que no son de esta sesión

Están listados en `CLAUDE.md`; se repiten aquí para que no se descubran tarde:

- **Protección de rama en `Desarrollo`**, para que los checks bloqueen en vez de
  solo avisar. Pendiente de Alejandro: pide permisos de admin del repositorio.
- **Los nombres de dos servicios de Railway tienen espacios pegados**:
  `"cron-manana "` (al final) y `" cron-tarde"` (al principio). No es cosmético —
  `railway logs -s cron-manana` responde `Service not found`, y cualquier script
  o runbook que los nombre falla por una razón invisible.
- **La versión de PostgreSQL de Railway no está documentada.** La CI usa
  `postgres:18` por ser la mayor de la base local; si producción corre otra, la
  CI no lo detectaría.

---

## Lo que NO se hace en esta sesión

- **No se le agrega nada al Loop E.** Un loop, un tema. Meterle partir
  `tests.py` o renombrar `enviar_recordatorios` rompe justo lo que hace
  verificable al método: si un loop toca cinco cosas, la verificación del
  Arquitecto ya no puede afirmar nada concreto sobre ninguna.
- **No se reabre D14.** Está decidida.
- **No se repiten las auditorías.** Las dos (22/07 y 27/07) ya se ejecutaron y
  sus 18 hallazgos están corregidos en los Loops A-D.
- **No se renombra `enviar_recordatorios`**, aunque el Loop E lo tenga delante.
  Su nombre lo invoca un servicio cron de Railway; se renombra cuando el comando
  haga lo que promete, junto con el envío Twilio saliente.
