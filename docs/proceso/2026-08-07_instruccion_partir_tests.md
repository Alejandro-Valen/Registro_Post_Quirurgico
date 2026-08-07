# Instrucción para la próxima sesión — partir `tests.py`

> **Qué es esto.** El guion de la sesión que sigue al Loop E. Se escribió el
> 07/08/2026 para que quien retome no tenga que reconstruir el plan de una
> conversación.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**El Loop E está cerrado y mergeado** — PR #10, merge commit `4fc690d`. Con él
quedan implementadas **las catorce decisiones D1-D14**. La suite pasó de 337 a
**340 tests OK** y las cinco comprobaciones de la CI quedaron en verde.

**Rama activa de trabajo:** ninguna. La de esta sesión se abre desde
`Desarrollo`.

### Lo primero que hay que entender: no hay producción

**Venció el periodo de prueba de Railway** (07/08/2026). El endpoint de salud
responde **404**, la app no sirve y los dos servicios cron no corren.

| Ya no se puede | Sigue igual |
|---|---|
| Verificar contra producción (`/salud/`, cron real, WhatsApp end-to-end) | La suite local contra PostgreSQL |
| Desplegar — mergear a `produccion` no hace nada | **La CI de GitHub Actions**, gratuita |

**Consecuencia práctica para esta sesión: ninguna.** Partir `tests.py` es trabajo
puramente local y la CI lo verifica igual que siempre. Pero conviene saberlo
antes de proponer nada que toque despliegue.

`docs/railway_deploy.md` **no se vació a propósito**: pasó de describir el
presente a ser el guion para reconstruir el despliegue cuando haya plan de pago.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo. Soy __ (Arquitecto).

Antes de proponer nada:
1. Lee docs/proceso/2026-08-07_instruccion_partir_tests.md — es el guion de esta
   sesión.
2. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

El objetivo de hoy es UNO: partir signos_sintomas/tests.py en un paquete
tests/. Es un refactor SIN cambio de comportamiento. No metas nada más en esta
rama: ni arreglar una prueba floja, ni renombrar, ni "de paso" tocar el código
que prueban.

Ten en cuenta que ya no hay produccion en Railway (vencio la prueba). No
propongas nada que dependa de desplegar.
```

---

## El objetivo de hoy

`Registro_Post_Quirurgico/signos_sintomas/tests.py` tiene **6.288 líneas y 46
clases** — 45 de pruebas más el mixin `EspiaDeTareasCronMixin` que dejó el Loop E.
(Las cifras 6.122/45 que citan los documentos anteriores al 06/08 son de antes
del Loop E.) Hay que convertirlo en un paquete `tests/` con un archivo por tema.

**Por qué ahora.** Es la ventana: ninguna rama avanza en paralelo, y el Loop E
—que era el que seguía añadiendo pruebas a ese archivo— ya cerró. Partirlo con
otra rama viva garantiza un conflicto de merge irresoluble a mano en un archivo
de 6.000 líneas.

**Por qué importa.** Un archivo así es donde las pruebas se esconden. Dos de las
lecciones más caras del proyecto —el hallazgo bloqueante del 22/07 y las dos
pruebas que el Loop E tuvo que reescribir— fueron pruebas que pasaban en verde
sin medir el requisito. Cuesta más verlas en 6.000 líneas que en un archivo de
300 con nombre propio.

### La regla que define esta sesión

**Es un refactor sin cambio de comportamiento.** Se mueve código, no se arregla
nada. Si aparece una prueba floja, mal nombrada o que mide el código en vez del
requisito —y van a aparecer—, **se anota y se deja para otra sesión**. Cambiar
comportamiento y mover archivos en el mismo commit hace que la verificación no
pueda afirmar nada sobre ninguna de las dos cosas.

### Cómo se sabe que salió bien

Tres comprobaciones, y las tres son objetivas:

1. **El conteo no se mueve: 340 tests.** Ni uno más, ni uno menos. Uno menos
   significa que una clase se perdió al mover; uno más, que se duplicó.
2. **Ninguna clase desaparece.** Comparar la lista de clases antes y después.
   Conviene volcarla a un archivo antes de empezar:
   `git show HEAD:Registro_Post_Quirurgico/signos_sintomas/tests.py | grep -E "^class "`
3. **Las cinco comprobaciones de la CI en verde** en el PR.

**Ojo con el punto 1:** Django descubre las pruebas de un paquete solo si tiene
`__init__.py`. Un subpaquete sin él no se recorre y **el conteo baja en
silencio** — sin error, sin aviso. Es el modo de fallo más probable de esta
sesión.

### Sugerencia de reparto, no obligatoria

Lo decide quien lo haga, mirando las 46 clases. Una división que sigue la
estructura del código:

| Archivo | Qué agrupa |
|---|---|
| `tests/test_alert_engine.py` | Las reglas clínicas — es el bloque más grande |
| `tests/test_bot.py` | Máquina de estados y respuestas al paciente |
| `tests/test_models.py` | Modelos, constraints, validaciones |
| `tests/test_commands.py` | Los management commands, incluidos los cron |
| `tests/test_admin.py` | Panel, tablero de triage, aislamiento por médico |
| `tests/test_webhook.py` | Webhook de Twilio, firma, rate limiting |
| `tests/test_notificaciones.py` | Bandeja de correo y reintentos |

Si un archivo queda en 1.500 líneas, se vuelve a partir. Si dos quedan en 80,
se juntan.

---

## Cómo cerrarlo

1. Rama propia desde `Desarrollo`. Nombre sugerido: `partir-tests`.
2. Volcar la lista de clases y el conteo **antes** de tocar nada.
3. Mover. Correr la suite. Comparar conteo y lista de clases.
4. PR a `Desarrollo`. **Mirar los cinco checks antes de mergear** — se ven pero
   no bloquean, falta la protección de rama.
5. Cierre: BITÁCORA, `CLAUDE.md`, ROADMAP y el guion de la sesión siguiente.

**Esta sesión no necesita script de verificación en `docs/proceso/verificaciones/`.**
Las anteriores lo llevaban porque cambiaban comportamiento y había que
demostrar cuál. Aquí la verificación es el conteo y la lista de clases, y va en
el cuerpo del PR.

---

## Después de esto

| Siguiente | Qué es |
|---|---|
| **`crear_medico`** | Decidir qué hacer antes de entregarle la cuenta al médico. Ver abajo |

---

## Las decisiones que esperan al Arquitecto

Ninguna es de código: hay que tomarlas antes de programar.

**1 · `crear_medico` reescribe la cuenta del médico en cada arranque.** Ejecuta
`set_password`, `is_staff = True`, `groups.set([...])` y
`user_permissions.clear()` sobre un usuario que ya existe. Si el médico cambia su
contraseña en el Admin, el siguiente despliegue **la revierte en silencio**.
Detalle en `docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`, punto 8.

*Nota:* con Railway caído esto no muerde hoy —no hay despliegues— pero la
decisión sigue pendiente y es barata de tomar ahora.

**2 · Cómo mostrar el correo de alerta funcionando.** `signals.py` corta la
notificación cuando la cédula empieza por `DEMO-`, **antes** de mirar la
severidad. Es un guard deliberado, pero implica que el correo de alerta **nunca
se ha probado de punta a punta contra el canal real**. Mostrarlo requiere decidir
cómo, y toca la frontera que protege de correos espurios: es diseño, no
implementación.

**Recordatorio, ahora con más razón:** los trámites del piloto real (WhatsApp
Business, plan de Railway, dominio en Resend, HABEAS DATA firmado) quedan
**diferidos por decisión del Arquitecto**. Primero se lleva el sistema al mejor
punto posible en desarrollo. **No proponer iniciarlos** hasta que él lo indique.

---

## Pendientes menores que no son de esta sesión

- **Protección de rama en `Desarrollo`**, para que los checks bloqueen en vez de
  solo avisar. Pendiente de Alejandro: pide permisos de admin del repositorio.
- **La versión de PostgreSQL de Railway** sigue sin documentar. En pausa: sin
  producción no hay contra qué comprobarlo.
- **Los nombres de dos servicios de Railway tienen espacios pegados**:
  `"cron-manana "` (al final) y `" cron-tarde"` (al principio). Se arregla cuando
  se reconstruya el despliegue.

---

## Lo que NO se hace en esta sesión

- **No se arregla ninguna prueba.** Ni una aserción floja, ni un nombre mentiroso
  (`test_llama_las_cinco_tareas_en_orden` listaba seis; el Loop E lo corrigió
  porque tuvo que reescribir esa prueba de todos modos). Se anotan y se dejan.
- **No se toca el código que las pruebas prueban.**
- **No se reabren D1-D14.** Están implementadas y verificadas.
- **No se repiten las auditorías.** Las dos (22/07 y 27/07) ya se ejecutaron.
- **No se propone nada que dependa de desplegar.** No hay dónde.
