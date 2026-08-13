# Instrucción para la próxima sesión — sin objetivo impuesto

> **Qué es esto.** El guion de la sesión que sigue a D15. Se escribió el
> 12/08/2026.
>
> **En qué se diferencia de los anteriores:** los otros traían un objetivo ya
> decidido. **Este no**, y es deliberado. La lista de trabajo heredada de la
> revisión del PR del Sprint 5 (`2026-07-29_revision_pr_sprint5.md`) **se terminó**
> con D15. Lo que siga se decide en sesión, no se hereda de una lista vieja.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**12/08/2026 — PR #17 mergeado** (`1396744`): la decisión **D15** y su
implementación en la misma sesión.

`crear_medico` ya no reescribe la contraseña ni el correo del médico en cada
arranque. Los grupos y permisos **sí** siguen reescribiéndose, y eso pasó de
efecto colateral a decisión declarada. Rotación explícita con
`DJANGO_MEDICO_RESET=1`.

**Con D15 quedan implementadas las quince decisiones D1-D15.**

**Suite: 344 tests OK** (340 + las 4 de D15), verificada el 12/08 sobre
`1396744`. **Rama activa de trabajo: ninguna.**

**Sigue sin haber producción** (venció Railway el 07/08/2026). No proponer nada
que dependa de desplegar.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo. Soy León (Arquitecto).

Antes de proponer nada:
1. Lee docs/proceso/2026-08-12_instruccion_siguiente_sesion.md — es el guion de
   esta sesión.
2. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

Este guion NO trae objetivo decidido: trae candidatos. Preséntamelos con sus
consecuencias y elijo yo antes de que escribas nada.

Ten en cuenta que ya no hay produccion en Railway (vencio la prueba). No
propongas nada que dependa de desplegar.
```

---

## Los candidatos, con sus consecuencias

Ninguno es obligatorio y no están en orden de prioridad.

### 1 · Auditar la calidad de las pruebas

**Es el que más peso ganó el 12/08**, y no por intuición: la verificación de D15
lo demostró con un caso. Al retirar `user.user_permissions.clear()` del comando,
la prueba que **ya existía** —`test_crea_staff_no_superusuario_sin_permisos_extra`—
**siguió en verde**. Comprueba `user_permissions.count() == 0` sobre una cuenta
recién creada, que no tiene permisos individuales de todas formas. Es decir:
medía el código, no el requisito, y nada protegía esa línea.

Es el mismo patrón que dejó vivo el hallazgo bloqueante del 22/07 durante seis
loops. **Ahora hay un ejemplo concreto y reproducible**, no una sospecha.

**Qué implicaría:** revisar las 344 pruebas —o un subconjunto por temas— buscando
las que pasarían igual con el comportamiento roto. La técnica ya está probada en
este proyecto: sabotear el código y ver **qué no cae**.

**Lo que cuesta:** es trabajo lento y sin entregable visible. Al partir `tests.py`
no se revisó ninguna prueba, a propósito, así que el terreno está sin explorar.

### 2 · Protección de rama

**No es un trámite de permisos** — eso lo decía `CLAUDE.md` y era falso. En un
repositorio privado de una cuenta personal sin GitHub Pro, GitHub **no ofrece
protección de rama a nadie, ni al dueño**.

Tres salidas, y las tres son decisión del Arquitecto: **GitHub Pro** (~4 USD/mes,
en la cuenta del dueño), **hacer público el repositorio**, o **seguir con la
compuerta humana** de mirar los siete checks antes de mergear.

**Lo que está en juego:** hoy los checks se ven pero no bloquean. Con Railway
caído, la CI es la única red de seguridad automática del proyecto, y depende de
que una persona la mire.

### 3 · `medico_piloto`

**D15 desbloqueó esta decisión.** Antes no era resoluble: la cuenta no podía
tener una contraseña propia que sobreviviera a un despliegue. Ahora sí, así que
lo que queda es administrativo: **transferir `medico_piloto` al médico
definitivo**, o **crear la cuenta definitiva y reasignar los pacientes**.

**Ojo:** no se puede cerrar del todo sin producción, porque la cuenta vive en el
servicio. Se puede **decidir** ahora y ejecutar cuando haya despliegue.

### 4 · El entorno virtual que no existe

`inicio_entornoR.bat` llama a `entorno_registro\Scripts\activate.bat`, y esa
carpeta **no está en disco**. La suite corre con el Python global (3.13.0,
Django 6.0.7) y pasa, así que no bloquea nada — pero el script de arranque miente
sobre lo que hay. Decidir si se recrea el entorno o si el `.bat` se retira.

**Es el más pequeño de los cuatro**, y sirve como sesión corta.

---

## Lo que NO se hace en esta sesión

- **No se reabren D1-D15.** Están implementadas y verificadas.
- **No se repiten las auditorías.** Las dos (22/07 y 27/07) ya se ejecutaron.
- **No se propone nada que dependa de desplegar.** No hay dónde.
- **No se toca el `alert_engine` ni ningún umbral** sin decisión explícita del
  Arquitecto y validación del médico.
- **No se inicia ningún trámite del piloto real** (WhatsApp Business, plan de
  Railway, dominio en Resend, HABEAS DATA firmado): siguen **diferidos por
  decisión del Arquitecto** hasta que él lo indique.

---

## Un recordatorio de método, por si el candidato elegido es el 1

Si la sesión audita pruebas, la regla que la hace útil está escrita en
`docs/proceso/metodo_de_trabajo.md` y se confirmó otra vez el 12/08: **un test en
verde no prueba nada si no se sabe por qué está verde.** La forma de saberlo es
romper el código a propósito y comprobar **qué cae y qué no** — el sabotaje que
no hace caer nada es el que encuentra la prueba floja.
