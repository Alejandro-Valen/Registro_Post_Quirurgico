# Revisión de cierre del PR del Sprint 5 — deuda técnica y dónde se atiende

> **Qué es este documento.** La lectura de ingeniería del PR #3 (Sprint 5 →
> `Desarrollo`): los puntos de deuda técnica que quedan **después** de que las dos
> auditorías se cerraran, y **en qué punto del flujo de trabajo se atiende cada
> uno**. Ninguno bloquea el merge.
>
> **Qué NO es.** No es una tercera auditoría. Las dos auditorías (22/07 y 27/07)
> ya se ejecutaron y sus hallazgos están corregidos en los Loops A-D. Esto es lo
> que se ve al mirar el conjunto una vez que los defectos ya no tapan la vista.
>
> **Cómo leerlo.** La tabla de secuencia es lo operativo. El detalle de cada punto
> está abajo para cuando se vaya a atender.

**Fecha:** 29/07/2026 · **Rama:** `sprint-5-produccion` · **HEAD:** `c73f527`
**PR:** [#3](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/pull/3)
· **Revisión:** Claude Code, a pedido de León (Arquitecto)
**Estado del PR:** OPEN · MERGEABLE · aprobado para `Desarrollo`

---

## Nota de método: la lista se revisó dos veces

La primera lectura produjo 7 puntos. **A pedido del Arquitecto se hizo una
segunda pasada, verificando cada uno contra el código.** El resultado no fue
cosmético:

| Cambio | Cuál |
|---|---|
| **1 retirado** | El punto 6 (comandos de seed en producción) estaba mal fundado |
| **2 agravados** | El 2 (acoplamiento del cron) y el 5, que se refuerzan entre sí |
| **1 nuevo** | El punto 8 (`crear_medico` reescribiendo la cuenta del médico), que la primera lectura no vio |

Queda registrado porque es el mismo patrón que dejó vivo el hallazgo bloqueante
durante seis loops: **revisar una vez no es revisar.** El punto retirado se deja
tachado en vez de borrado, para que se vea que se revisó y por qué se cayó.

---

## Dónde se atiende cada uno

**El Loop E no es el lugar para esta lista.** El Loop E tiene una decisión escrita
(**D14**), un tema —aislar las tareas del cron— y dos commits planeados (E-1 test
en rojo, E-2 corrección). Meterle CI, partir `tests.py` y renombrar un comando
rompe exactamente lo que hace verificable al método: si un loop toca cinco cosas,
la verificación del Arquitecto ya no puede decir "esto quedó bien" sobre nada en
concreto. **Un loop, un tema, una sesión.**

De los ocho puntos, **solo el 2 es el Loop E** — y ya lo era antes de esta
revisión.

| # | Punto | Cuándo | Por qué ahí |
|---|---|---|---|
| **1** | ~~Montar CI~~ | ✅ **Hecho el 31/07/2026** — PR #5, `5b40c01` | Entró antes del Loop E, como estaba decidido: su PR ya se verifica solo. Verificación en rojo de las cinco comprobaciones en `proceso/verificaciones/2026-07-31_verificacion_ci.md` |
| **8** | `crear_medico` reescribe la cuenta | **Antes de entregar la cuenta al médico** | Hay una decisión abierta sobre `medico_piloto`. Tal como está, esa cuenta no puede tener contraseña propia |
| **2** | Aislar las tareas del cron | **Loop E**, como está decidido (D14) | Ya decidido. Sin agregados |
| **3** | Partir `tests.py` | **Después del Loop E, antes de que Sprint 6 acumule** | Ventana estrecha y es esa: el Loop E añade pruebas a `tests.py`, así que partirlo antes garantiza el conflicto que se busca evitar; y después de que Sprint 6 avance, el conflicto ya ocurrió |
| **4** | La 0028 y el arranque | **Ahora, documentando** | No es un arreglo: es una trampa operativa. Va a `docs/trampas_conocidas.md` |
| **5** | Renombrar `enviar_recordatorios` | **Sprint 6, con el envío Twilio saliente** | Renombrarlo ahora es churn con riesgo: el nombre lo invoca un servicio cron de Railway. Se renombra cuando el comando haga lo que promete |
| **7** | Correo de alerta de punta a punta | **Prerrequisito del piloto** | No es deuda de código, es una prueba que falta. Ya está en CLAUDE.md |
| ~~6~~ | ~~Seeds en producción~~ | **Retirado** | Mal fundado. Ver abajo |

---

## Los puntos, en detalle

### 1 · No hay CI — ✅ RESUELTO el 31/07/2026

**Resuelto en el PR #5** (`5b40c01`): `.github/workflows/ci.yml` corre las cinco
comprobaciones en cada PR hacia `Desarrollo` y hacia `produccion`, y en cada push
a esas dos ramas. Las cinco se verificaron en rojo antes de mergear —
`proceso/verificaciones/2026-07-31_verificacion_ci.md`. Falta una sola cosa,
que no depende de nosotros: **`Desarrollo` no tiene protección de rama**, así que
los checks se ven pero no bloquean el merge. Configurarla pide permisos de admin
del repositorio.

Se conserva el diagnóstico original, que sigue explicando por qué era el punto 1:

**Lo más importante de la lista.** 127 commits y 337 pruebas que solo han corrido
en la máquina del Arquitecto, en Windows.

Verificado: no hay `.github/workflows`, ni `.gitlab-ci.yml`, ni `.circleci`, ni
`Jenkinsfile`, ni `pre-commit`. Tampoco el `Dockerfile` ni `nixpacks.toml`
ejecutan pruebas en el build — el despliegue no verifica nada.

El repo recibe trabajo desde dos herramientas distintas (Claude Code y Codex
CLI) en sesiones que no comparten memoria. Sin un workflow que corra la suite,
`check --deploy` y `makemigrations --check` en cada PR, la disciplina depende de
que nadie se olvide. Un GitHub Actions de ~30 líneas con un servicio Postgres
cubre esto.

### 2 · El acoplamiento del cron entra sin arreglar (D14 / Loop E)

*Agravado en la segunda pasada.*

`cron_operativo` encadena tres tareas en un bucle **sin manejo de errores** y
corre **cada 5 minutos**:

```
cerrar_checkins_vencidos → reintentar_evaluaciones_alertas → procesar_notificaciones_email
```

La primera lectura decía "los correos de ese ciclo". Es peor: **no hay ruta de
respaldo.** `cron_matutino` también ejecuta `procesar_notificaciones_email`, pero
en la posición 6 de 6, con `cerrar_checkins_vencidos` en la 3. Un fallo
persistente de esa tarea **aborta las dos rutas**, y los correos de alerta ALTA
no salen por ninguna.

Y hay un detalle que la primera lectura no vio: en `cron_matutino` la posición 4
la ocupa `enviar_recordatorios`, que hoy **es un stub que no envía nada** (punto
5). Un comando sin efecto clínico está en la ruta crítica, por delante de la
entrega de alertas: si falla, retiene correos.

Decisión y plan de ejecución: ficha **D14** en
`docs/decisiones_correccion_auditoria.md`.

### 3 · `tests.py` son 6.122 líneas y 45 clases en un solo archivo

Funciona, y no justifica tocarlo hoy. Pero es el mayor pasivo de mantenimiento
del repo: los conflictos de merge en ese archivo van a ser constantes en cuanto
dos ramas avancen en paralelo. No existe todavía un paquete `tests/`, así que
partirlo es trabajo mecánico y de bajo riesgo — **si se hace en la ventana
correcta** (ver la tabla de secuencia).

### 4 · La 0028 es una restricción dependiente de los datos

Postgres valida **todas** las filas al crear un `CheckConstraint`, y el `CMD` del
Dockerfile encadena con `&&`:

```
collectstatic && migrate --noinput && ... && crear_medico && gunicorn
```

Si `migrate` falla, no hay un error en el log: hay **contenedor que no arranca**.

Aquí es seguro —la compuerta D-0 se ejecutó dos veces contra producción, cero
pacientes activos sin responsable— y la propia migración 0028 lleva escrita la
consulta para repetir el recuento en otro entorno. Pero cualquier entorno
restaurado de un dump viejo puede quedarse sin arrancar. Relevante al montar
staging.

### 5 · `enviar_recordatorios` no recuerda nada

Es un stub declarado: el envío Twilio saliente está diferido y el sistema es
reactivo — el paciente debe escribir primero. Está documentado en
`docs/cron_setup.md`, pero el nombre promete lo contrario y confunde a quien lo
lea sin contexto.

Sube de prioridad por su posición en `cron_matutino` (ver punto 2): no es solo un
nombre engañoso, es un no-op en la ruta crítica de la entrega de alertas.

### ~~6 · Los comandos de seed en la imagen de producción~~ — RETIRADO

**La primera lectura afirmaba que "el radio de daño de un `--limpiar` mal
apuntado es alto". Es falso.** Verificado:

- **`seed_demo` aborta si `DEBUG=False`.** No puede ejecutarse en producción,
  punto. Es inerte en esa imagen por diseño.
- **`seed_demo_produccion` exige `--confirmar`**, y su `--limpiar` borra **solo**
  los pacientes cuyo teléfono está en `TELEFONOS_DEMO`, una lista fija derivada
  de las constantes del propio archivo — en transacción y respetando el orden de
  las FK `PROTECT`.

El único borde real es un paciente registrado con uno de esos teléfonos demo. Se
cubre con una línea en `docs/trampas_conocidas.md`, no con código.

### 7 · El correo de alerta nunca se ha probado de punta a punta

`signos_sintomas/signals.py` comprueba si la cédula empieza por `DEMO-`
**antes** que la severidad, así que un paciente de ejemplo **nunca encola
correo, por diseño**. Hace falta un paciente con cédula real asignado a un médico
con correo. Ya está en CLAUDE.md, "Por resolver antes del piloto real".

### 8 · `crear_medico` corre en cada arranque y reescribe la cuenta del médico

*Nuevo: no estaba en la primera lectura. Apareció al verificar el punto 4.*

El `CMD` del Dockerfile invoca `crear_medico` en cada arranque del servicio web
y —a diferencia de `crear_admin`, que va con `|| true`— **sin guarda**. Dos
consecuencias distintas:

**Reescribe la cuenta en cada arranque.** Sobre un usuario que ya existe se
ejecutan igual `set_password(...)`, `is_staff = True`, `groups.set([...])` y
`user_permissions.clear()`. Si el médico cambia su propia contraseña en el
Admin, el siguiente despliegue o reinicio **la revierte en silencio** al valor de
la variable de entorno, y borra cualquier permiso concedido a mano.

**Puede dejar el sitio sin arrancar.** Lanza `CommandError` si solo una de
`DJANGO_MEDICO_USERNAME` / `DJANGO_MEDICO_PASSWORD` está definida, o si el
usuario resulta ser superusuario. Encadenado con `&&`, eso es gunicorn que no
llega a levantar.

**Por qué importa ahora:** hay una decisión abierta sobre si `medico_piloto` se
transfiere al médico definitivo o se crea una cuenta nueva (CLAUDE.md, "Por
resolver antes del piloto real", punto 2). Tal como está el arranque, **esa
cuenta no puede tener una contraseña propia que sobreviva a un despliegue** — lo
que hace que la decisión no sea solo administrativa.

Esto **no se decide aquí.** Provisionar una cuenta de forma declarativa es una
postura legítima; hacerlo sobre la cuenta de una persona que espera gobernar su
propia contraseña es otra cosa. Es decisión del Arquitecto, y toca una cuenta con
acceso a datos clínicos.

---

## Lo que esta revisión confirmó que está bien resuelto

Para que la lista de deuda no se lea como un veredicto sobre el conjunto:

- **El bloqueante se arregló por la causa, no por el síntoma.** La escalera de
  SILENCIO no fallaba por el umbral sino porque `_calcular_racha` miraba turnos
  posteriores que el scheduler siempre deja en `PENDIENTE`.
- **Defensa en profundidad real** en el invariante "ningún paciente activo sin
  médico": cuatro capas que cubren caminos que las otras no.
- **Fail-fast en el arranque** (`config_obligatoria`) en vez de degradación
  silenciosa, sin imprimir nunca el valor de un secreto.
- **La firma del webhook deja de leerse del entorno**, con la variable
  explícitamente prohibida en Railway.
- **El outbox de correo tiene estado terminal** (`FALLIDA`) y ese estado es
  visible en el tablero del médico.
- **Las pruebas miden el requisito**, con mensajes de aserción que nombran la
  decisión que fijan.

---

## Veredicto

**Aprobado para `Desarrollo`.** Los ocho puntos son deuda conocida y anotada, no
defectos ocultos. El orden de atención está en la tabla de secuencia; los dos que
no admiten postergarse mucho son la **CI** (protege todo lo demás) y
**`crear_medico`** (bloquea la entrega de la cuenta al médico).
