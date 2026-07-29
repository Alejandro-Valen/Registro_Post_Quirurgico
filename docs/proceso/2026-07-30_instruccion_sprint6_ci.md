# Instrucción para la próxima sesión — montar CI

> **Qué es esto.** El guion de la sesión que sigue al cierre del Sprint 5. Se
> escribió el 29/07/2026 para que quien retome no tenga que reconstruir el plan
> de una conversación.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**El Sprint 5 está cerrado y mergeado.** PR #3, merge commit `3a5c573`, etiqueta
`sprint-5-cierre` sobre `a13038e`. Los cuatro pasos del guion anterior se
ejecutaron el 29/07/2026.

**La topología de despliegue cambió, y esto es lo primero que hay que entender:**

```
rama de trabajo → PR → Desarrollo → (cuando se decide) → merge a produccion → al aire
```

- **`Desarrollo`** es integración. **No despliega.**
- **`produccion`** es la rama que miran los tres servicios de Railway
  (`zooming-trust`: web, `cron-manana`, `cron-tarde`). **Nadie trabaja ahí**; solo
  recibe merges desde `Desarrollo`. Cada push a `produccion` sale al aire de
  inmediato.
- **`sprint-5-produccion` se conserva** por decisión del Arquitecto, pero ya no la
  mira ningún servicio. No commitear ahí.

**Rama activa de trabajo:** `sprint-6-ci`, ya creada desde `Desarrollo`.

**Estado verificado al cerrar:** suite **337 tests OK**, `check` sin issues,
`makemigrations --check` limpio, `git diff --check` limpio, `/salud/` en 200.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos en la rama sprint-6-ci. Soy León (Arquitecto).

Antes de proponer nada:
1. Lee docs/proceso/2026-07-30_instruccion_sprint6_ci.md — es el guion de esta
   sesión.
2. Lee docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md — los 8 puntos
   de deuda y su orden. Hoy es el punto 1.
3. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

El objetivo de hoy es UNO: montar CI. No es un loop de corrección y no toca
lógica clínica. No metas nada más en esta rama.
```

---

## El objetivo de hoy: CI

**Es el punto 1 de los 8 de la revisión del PR**, y va primero por una razón de
orden: si la CI existe antes del Loop E, el PR del Loop E se verifica solo. Si
entra después, hay que verificar el Loop E a mano una vez más.

**El problema que resuelve.** 127 commits y 337 pruebas que solo han corrido en
la máquina del Arquitecto, en Windows. Nada en el despliegue ejecuta pruebas: ni
el `Dockerfile` ni `nixpacks.toml`. El repo recibe trabajo desde dos herramientas
distintas (Claude Code y Codex CLI) en sesiones que no comparten memoria, así que
hoy la disciplina depende de que nadie se olvide.

### Qué debe correr

En cada PR hacia `Desarrollo` y en cada push a `Desarrollo` y `produccion`:

| Comprobación | Por qué |
|---|---|
| `python manage.py test --noinput` | Las 337. Es el criterio de siempre |
| `python manage.py check` | Errores de configuración |
| `python manage.py makemigrations --check --dry-run` | Detecta un `models.py` cambiado sin migración |
| `python manage.py check --deploy` | Con `settings_production` |
| `git diff --check` | El criterio de higiene que los Loops A-C sí registraban y el D no llegó a listar |

### Lo que hay que tener en cuenta al escribirlo

- **La suite necesita PostgreSQL.** Un `services: postgres` en el job, y las
  variables `DB_*` apuntando a él.
- **`settings_production` aborta si falta una variable obligatoria.** Es
  deliberado (`config_obligatoria`, hallazgo 11 del Loop C). Para
  `check --deploy` hay que darle valores de relleno a `SECRET_KEY`,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `REDIS_URL`, `DB_*` y las de correo
  según `EMAIL_DELIVERY_PROVIDER`. **Sin `<corchetes>`**: el propio guard los
  rechaza.
- **`manage.py` no está en la raíz.** Vive en
  `Registro_Post_Quirurgico/Registro_Post_Quirurgico/`.
- **Dependencias:** `requirements-runtime.txt` es el de producción;
  `requirements.txt` es un `pip freeze` de Windows y **no sirve en Linux**. Para
  la suite hacen falta además las de desarrollo (p. ej. `freezegun`, que entró en
  C7). Revisar cuál instala qué antes de elegir.
- **La suite tarda ~5 minutos.** Es aceptable; no partirla en shards todavía.
- **Python 3.13**, según `.python-version`.

### Cómo cerrarlo

1. El workflow en `.github/workflows/`, en un commit `feat:` o `ci:`.
2. **Verificar que la CI falla cuando debe.** Un workflow que nunca vio un rojo
   no está probado: romper algo a propósito en un commit temporal, ver el rojo, y
   revertirlo. Es el mismo principio del "test en rojo" del método de loops —
   aplicado a la propia CI.
3. PR a `Desarrollo` y merge.
4. **Ojo:** el primer PR con CI mostrará checks nuevos. Que pasen antes de
   mergear.

---

## Después de esto

En este orden, y **cada uno en su propia sesión**:

| Siguiente | Qué es |
|---|---|
| **Loop E** | D14 — aislar las tareas del cron conservando la dependencia clínica declarada de `cron_matutino`. Dos commits: E-1 test en rojo, E-2 corrección. **Solo eso.** El razonamiento completo está en la ficha D14 de `docs/decisiones_correccion_auditoria.md` y en el guion anterior, `2026-07-28_instruccion_cierre_rama_sprint5.md` |
| **Partir `tests.py`** | 6.122 líneas y 45 clases → paquete `tests/`. Va **después** del Loop E, que añade pruebas a ese archivo, y **antes** de que otra rama avance en paralelo |
| **`crear_medico`** | Decidir qué hacer antes de entregarle la cuenta al médico. Ver abajo |

---

## Las dos decisiones que esperan al Arquitecto

Ninguna es de código: son decisiones que hay que tomar antes de programar.

**1 · `crear_medico` reescribe la cuenta del médico en cada arranque.** Ejecuta
`set_password`, `is_staff = True`, `groups.set([...])` y
`user_permissions.clear()` sobre un usuario que ya existe. Si el médico cambia su
contraseña en el Admin, el siguiente despliegue **la revierte en silencio**. Hoy
`medico_piloto` no puede tener una contraseña propia que sobreviva a un deploy.
Provisionar de forma declarativa es una postura legítima; hacerlo sobre la cuenta
de una persona que espera gobernar su propia contraseña es otra cosa. Detalle en
la revisión del PR, punto 8.

**2 · Cómo mostrar el correo de alerta funcionando.** `signals.py` corta la
notificación cuando la cédula empieza por `DEMO-`, **antes** de mirar la
severidad. Es un guard deliberado —evita mandar correos por datos ficticios— pero
implica que el correo de alerta **nunca se ha probado de punta a punta**. Mostrarlo
requiere decidir cómo: ¿un paciente de demostración con cédula real y un correo
del equipo? ¿Otro mecanismo? Toca la frontera que protege de correos espurios, así
que es diseño, no implementación.

---

## Las dos líneas de llegada (contexto de por qué importa el orden)

Conviene no confundirlas, porque necesitan trabajo distinto:

**A · MVP demostrable** — mostrarlo de punta a punta y que convenza. Todo depende
de nosotros y **sin costo**: la landing todavía tiene `[corchetes]` y
`MOSTRAR_AVISO_BOCETO = True` (P-12), los demos se caducan solos porque nacen en
POD 8-10, y el correo no se puede mostrar (ver decisión 2 arriba).

**B · Piloto con pacientes reales** — depende de **terceros y de dinero**:
WhatsApp Business aprobado por Meta, plan de pago de Railway, dominio con
SPF/DKIM/DMARC en Resend, monitoreo externo apuntando a `/salud/`, HABEAS DATA
firmado, y la validación clínica de las cuatro frases del bot. Lista completa en
el ROADMAP, "Requisitos para un PILOTO REAL con pacientes".

**Decisión del Arquitecto (29/07/2026): B queda diferido a propósito.** Primero se
lleva el sistema al mejor punto posible en desarrollo; los trámites del piloto se
arrancan después. **No proponer iniciarlos** hasta que él lo indique.

La consecuencia, para que esté escrita y no se descubra tarde: los pendientes de B
son **colas, no tareas** — la aprobación de Meta para WhatsApp Business y la
agenda del médico no se aceleran trabajando más. Diferirlos no atrasa el piloto
por el tiempo que se difieran, sino por el tiempo que tarden **una vez
iniciados**. Es una decisión tomada con eso a la vista, no un olvido.

---

## Lo que NO se hace en esta sesión

- **No se toca lógica clínica.** Montar CI no cambia un umbral ni una regla.
- **No se repiten las auditorías.** Las dos (22/07 y 27/07) ya se ejecutaron y
  sus hallazgos están corregidos en los Loops A-D.
- **No se reabren las decisiones D1-D14.** Están tomadas.
- **No se mete nada más en `sprint-6-ci`.** Un tema por rama.
