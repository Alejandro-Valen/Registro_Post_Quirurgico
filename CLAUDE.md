# Contexto del Proyecto — Sistema de Monitoreo Posquirúrgico Remoto

> **Para agentes IA y para cualquier desarrollador nuevo:** este archivo es la
> **puerta de entrada**, no el manual completo. Contiene qué es el proyecto,
> cómo se trabaja en él, dónde vamos, y **un mapa de dónde vive cada cosa**.
>
> Las reglas clínicas se cargan automáticamente junto con este archivo (ver
> "Mapa de la documentación"). Los demás documentos se leen **cuando vas a
> tocar esa parte** — cada uno dice explícitamente cuándo.
>
> **Regla que no se negocia:** ninguna regla, umbral o mensaje clínico se
> cambia sin decisión explícita del Arquitecto. Los umbrales tienen base en
> evidencia de recuperación postoperatoria colorrectal (protocolos ERAS), y la
> auditoría de literatura confirmó que ningún estudio revisado trata
> HIPEC/Sugarbaker de forma específica: se derivan de cirugía colorrectal
> electiva en general, no de ensayos HIPEC.

## ¿Qué es este proyecto?

Sistema de monitoreo remoto posquirúrgico para pacientes en recuperación de
cirugía colorrectal — incluyendo casos Sugarbaker/HIPEC como uno de los
tipos de procedimiento soportados, sin ser exclusivo de ellos (ver campo
`tipo_cirugia` en el modelo `Paciente`). El paciente interactúa
exclusivamente por WhatsApp. Un bot le hace preguntas diarias de telemetría.
El sistema clasifica los datos, detecta alertas rojas y notifica al médico
a través de un dashboard en Django Admin.

**La IA NO diagnostica.** Funciona bajo un sistema de reglas clínicas fijas
(alert_engine) para clasificar, resumir telemetría y generar alertas
tempranas.

**Nota sobre alcance y afiliación:** este proyecto no tiene afiliación
institucional formal a la fecha — es trabajo directo con el médico que
originó la idea, sin vínculo formalizado a una clínica o universidad. No
usar nombres de instituciones ni el nombre "Sugarbaker" como marca del
sistema en código, documentación o el nombre del repositorio, hasta que
exista una decisión formal sobre afiliación.

---

---

## Mapa de la documentación

> Por qué existe esta separación, con su razonamiento completo:
> `docs/arquitectura_documentacion.md`. En una línea: **cada hecho vive en un
> solo archivo**, y ese archivo se actualiza en el mismo commit que el código
> que describe.

### Se carga solo, junto con este archivo

Las reglas clínicas viajan siempre en el contexto. El riesgo de que un agente
no las lea es que invente un umbral, y eso no es aceptable en un sistema que
clasifica señales de alarma médicas.

@docs/reglas_clinicas.md

### Léelo ANTES de tocar esa parte

| Documento | Cuándo es obligatorio leerlo |
|-----------|------------------------------|
| `docs/modelos_datos.md` | Antes de tocar `models.py`, escribir una migración o agregar un campo |
| `docs/bot_whatsapp.md` | Antes de tocar `bot.py`, la máquina de estados o cualquier texto que lea el paciente |
| `docs/trampas_conocidas.md` | Antes de tocar despliegue, cron, Twilio o correo. Son errores que ya costaron horas |
| `docs/railway_deploy.md` | Antes de cambiar variables de entorno o desplegar |
| `docs/cron_setup.md` | Antes de tocar los management commands programados |
| `docs/decisiones_correccion_auditoria.md` | Antes de tocar lo que corrigieron los loops de auditoría (fichas **D1-D17**) |
| `ROADMAP_MONITOREO_POSQUIRURGICO.md` | Antes de proponer alcance nuevo o discutir prioridades |

### Dónde está cada cosa (desde el 07/09/2026)

`docs/` es **solo producto**: reglas clínicas, modelo de datos, bot, operación,
legal. `proceso/verificaciones/` guarda los scripts que se ejecutan a mano para
comprobar el trabajo. Un desarrollador nuevo no necesita abrirlos para usar ni
extender el sistema.

### Consúltalo cuando necesites contexto

| Documento | Qué responde |
|-----------|--------------|
| `README.md` (raíz) | La portada: qué hace el sistema, cómo se instala, y qué falta —técnico y normativo— para pacientes reales |
| `CONTRIBUTING.md` | Las convenciones en forma corta: ramas, commits, qué correr antes del PR, y las reglas del código |
| `SECURITY.md` | Qué cuenta como fallo de seguridad aquí, qué ya está resuelto y **qué sabemos que falta** |
| `docs/README.md` | Índice general y **orden de autoridad** si dos documentos se contradicen |
| `docs/resumen_sprints.md` | Qué entregó cada sprint, bloque y loop — el mapa de la BITÁCORA |
| `docs/auditoria_literatura/` | La evidencia clínica que respalda (o no) cada umbral |
| `docs/transferencia_cuentas.md` | Propiedad de servicios y credenciales |
| `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` | Documento legal canónico (Ley 1581/2012) |

**Los documentos de la reunión salieron del repositorio el 20/09/2026** — la
página de decisiones y el guion para explicar el sistema. Viven fuera del árbol,
en el cuaderno de trabajo, porque son material de una conversación concreta y no
documentación del producto: quedan en la voz de quien la dirige y con lo que esa
persona elige contar. **Aquí no se recrean**, que es justo lo que esa mudanza
deshizo.

### Si algo se contradice

Manda **el código**; después el documento dueño de ese tema (los de la tabla
"antes de tocar"); después este archivo. Al encontrar una contradicción,
**corrígela en el mismo commit** en vez de dejarla
anotada para después.

---

## Stack Tecnológico

- **Backend:** Django 6.1.1 + Python 3.13 — hasta el 12/09/2026 esta línea
  decía **6.0.7**, que era falso desde el bump de Dependabot; lo fija
  `pyproject.toml` y lo confirma `django.get_version()`
- **Base de datos:** PostgreSQL 18 (local: registro_postquirurgico_db)
- **Interfaz paciente:** WhatsApp Bot vía Twilio API (en construcción, Sprint 3)
- **Panel médico:** Django Admin personalizado
- **Dependencias clave:** python-decouple, psycopg2-binary, twilio (próximo)
- **OS desarrollo:** Windows 11

---

---

## Repositorio

- **URL:** https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
- **Rama principal (integración):** `Desarrollo`
- **Rama de despliegue:** `produccion` — la miran los tres servicios de Railway.
  Nadie trabaja aquí; solo recibe merges desde `Desarrollo`. Ver
  `docs/railway_deploy.md` §4.1.
- **Ramas, al cerrar la sesión del 02 al 04/10/2026.** En el remoto solo quedan
  `Desarrollo` y `produccion`: el 02/10 se borraron 20 ramas ya mergeadas.
  Mergeados en esa sesión: el PR #36 (Dependabot), el #37 (`8961036`), el #38
  (`7383b00`), el #39 (`b89c1d1`), el #40 (`82fe8ef`), el #41 (`55e1369`) y el
  #42 (`3974b2c`). **Quedan dos cosas sin mergear:**
  - **`carril-a-panel`:** el panel del médico, con un PR abierto o en camino.
    Ver «Próximo paso exacto».
  - **`ci-no-cancela-tras-merge`:** solo existe **en local**, en la máquina de
    León (REPO-20). GitHub rechaza cualquier push que cambie `.github/workflows/` si el
    token de `gh` no tiene el permiso `workflow`. Hay que darlo con
    `gh auth refresh -h github.com -s workflow`, y después push y PR.
- **Borrar la rama al mergear:** se hace con `gh pr merge <n> --merge
  --delete-branch`. El ajuste automático del repositorio («Automatically delete
  head branches») solo lo puede activar el dueño de la cuenta: la API le
  responde 404 a un colaborador.
- **Cada PR se verifica solo:** `.github/workflows/ci.yml` corre **diez
  comprobaciones** en cada PR hacia `Desarrollo` y hacia `produccion`, y en cada
  push a esas dos ramas: la suite, `check`, `makemigrations --check`,
  `check --deploy` **con `--fail-level WARNING`**, la higiene del diff, la
  **guardia de secretos** (`gitleaks` sobre la historia completa), que no haya
  ningún `.env` rastreado, el **linter** (`ruff`), **`pip-audit`** sobre las
  dependencias instaladas, y el **barrido de veracidad de la documentación**
  (desde el 09/09/2026).

  **Qué vigila el barrido, y por qué se añadió.** Comprueba que lo que la
  documentación *afirma* sea cierto: que las rutas citadas existan, que el
  conteo de pruebas publicado sea el real, que los commits citados estén en la
  historia, y —lo que más importa— **que los umbrales de
  `docs/reglas_clinicas.md` sigan siendo las constantes de `alert_engine.py`**.
  En dos días se habían encontrado cinco afirmaciones falsas, todas por
  casualidad. Un documento que miente no rompe ninguna prueba, y en un sistema
  clínico el documento de reglas es la referencia con la que alguien decide si
  un umbral está bien.

  **La bandera `--fail-level WARNING` no es un detalle.** Sin ella, el paso de
  configuración de producción **nunca pudo fallar**: todos los checks de
  despliegue de Django son de nivel WARNING y el umbral por defecto es ERROR,
  así que reportaba los problemas y salía con código 0. Fue el hallazgo SEC-01
  de la auditoría del 07/09/2026, y de él salió la ficha **D16**: ninguna
  guardia entra ni permanece aquí sin haberse visto fallar al menos una vez.
- **Los checks se ven pero no bloquean.** `Desarrollo` no tiene protección de
  rama. **Y no es cuestión de permisos**, como decía este archivo hasta el
  10/08/2026: en un repositorio **privado** de una cuenta personal sin GitHub
  Pro, GitHub no ofrece protección de rama **a nadie, ni al dueño** — la API de
  rulesets responde *"Upgrade to GitHub Pro or make this repository public"*.
  Las tres salidas son: GitHub Pro (~4 USD/mes, en la cuenta del dueño), hacer
  el repositorio público, o seguir con la compuerta humana de mirar las diez
  comprobaciones antes de mergear. Hoy rige la tercera: **mirar antes de
  mergear**. (Hasta el 04/10/2026 esta línea decía «los siete checks»: eran
  diez desde el 09/09.)

---

---

## Estructura de Apps Django

```
Registro_Post_Quirurgico/Registro_Post_Quirurgico/
├── Registro_Post_Quirurgico/  → settings.py, settings_local.py (dev), settings_production.py (prod)
├── home/                      → portal web, páginas informativas, formulario de contacto
└── signos_sintomas/           → núcleo clínico
    ├── models.py, admin.py, alert_engine.py, bot.py, signals.py, views.py
    ├── management/commands/   → crear_checkins_diarios, enviar_recordatorios,
    │                             cerrar_checkins_vencidos, seed_demo
    └── tests/                 → un archivo por tema (test_alert_engine.py,
                                  test_bot.py, test_admin.py, test_commands.py,
                                  test_webhook.py, test_models.py,
                                  test_alertas_persistencia.py,
                                  test_notificaciones.py, test_configuracion.py)
                                  + soporte.py con lo compartido
```

**Sobre `tests/`, dos cosas que no se pueden tocar sin romper el conteo de la
suite:** `__init__.py` debe existir —Django no recorre un paquete de pruebas sin
él, y el conteo baja **en silencio**, sin error ni aviso— y `soporte.py` se llama
así, y no `test_soporte.py`, precisamente para que el descubridor **no** lo
recorra: contiene el ancla de reloj, el helper `medico_de_pruebas` y el mixin
`EspiaDeTareasCronMixin`, no pruebas.

Árbol completo (archivo por archivo) en `ROADMAP_MONITOREO_POSQUIRURGICO.md`,
sección "Estructura del Proyecto Django".

**Importante:** La carpeta del proyecto se llama `Registro_Post_Quirurgico`
(sin typo). Hubo una versión anterior llamada `Resgistro_Post_Quirurgico`
que fue eliminada en el Sprint 1.

---

---

## Auditoría de Literatura Clínica

La auditoría de la evidencia científica del proyecto (9 PDFs sobre
ERAS/alta temprana en cirugía colorrectal, transcripciones de
presentaciones del médico, y documentos institucionales/académicos
complementarios) ya se realizó — ver `docs/auditoria_literatura/` para
el análisis completo, documento por documento, y la síntesis cruzada de
umbrales.

**Resultado relevante para el alcance del proyecto:** la evidencia
confirma que el sistema corresponde a ERAS/alta temprana en cirugía
colorrectal en general, no a un protocolo exclusivo de Sugarbaker/HIPEC
— ver el campo `tipo_cirugia` en `Paciente` y la sección "¿Qué es este
proyecto?" arriba.

**Pendiente:** la decisión de qué cambia en los umbrales y reglas del
`alert_engine` a partir de esta evidencia (fiebre, gases, náuseas,
drenaje, dolor, frecuencia de check-ins) — fase de decisiones de
arquitectura clínica, todavía sin resolver. El detalle completo de los
puntos abiertos está en
`docs/auditoria_literatura/SINTESIS_CRUZADA_UMBRALES.md`.

**Mientras tanto:** nunca inventar ni suponer contenido clínico para
`knowledge_base.md`, ni cambiar ninguna regla del `alert_engine`, sin que
el Arquitecto lo decida explícitamente en sesión. La auditoría es
evidencia disponible, no decisiones ya tomadas.

---

## Estado Actual del Proyecto

| Sprint | Descripción | Estado |
|--------|-------------|--------|
| Sprint 0 | Configuración base y seguridad | ✅ Completado |
| Sprint 1 | Modelos clínicos y base de datos | ✅ Completado |
| Sprint 1 Frontend | Formulario de contacto, templates, admin home | ✅ Completado |
| Sprint 2 | Motor de alertas (alert_engine) | ✅ Completado |
| Sprint 3 | Bot WhatsApp (Twilio) | ✅ Completado y endurecido en Sprint 3-Hardening |
| Sprint 3.5 | Auditoría de literatura, generalización de alcance y documentación | ✅ Completado |
| Sprint 3.6 | Decisiones de arquitectura clínica del alert_engine | ✅ 5/5 variables del núcleo + 4/4 del Paso 2 |
| Sprint 3-Hardening | Seguridad y robustez pre-producción | ✅ Completado — 24 hallazgos, mergeado a Desarrollo |
| Sprint 4 | Dashboard médico y notificaciones | ✅ Completado y mergeado a Desarrollo |
| Sprint 5 | Producción, despliegue y cierre pre-merge (RAG diferido a Sprint 6) | ✅ **Completado y mergeado** (29/07/2026, PR #3, merge commit `3a5c573`). Loops A-D cerrados y verificados; rama `produccion` creada y Railway reapuntado |
| Sprint 6 · CI | Integración continua en GitHub Actions | ✅ **Completado y mergeado** (31/07/2026, PR #5, merge commit `5b40c01`). Cinco comprobaciones, las cinco verificadas en rojo |
| Loop E · D14 | Aislar las tareas del cron sin perder la dependencia clínica | ✅ **Completado y mergeado** (07/08/2026, PR #10, merge commit `4fc690d`). **340 tests OK**; cierra D1-D14 |
| Partir `tests.py` | Convertir el archivo de 6.288 líneas en un paquete `tests/` por tema | ✅ **Completado y mergeado** (10/08/2026, PR #12, merge commit `427153b`). Nueve archivos + `soporte.py`; **340 tests OK** y los 305 métodos comparados uno a uno |
| Guardia de secretos | `gitleaks` y control de archivos de entorno en la CI | ✅ **Completado y mergeado** (10/08/2026, PR #13, merge commit `301c743`). La CI pasa de cinco a **siete comprobaciones** |
| D15 · `crear_medico` | Que el arranque deje de reescribir la cuenta del médico | ✅ **Completado y mergeado** (12/08/2026, PR #17, merge commit `1396744`). **344 tests OK**; cierra D1-D15 |
| Auditoría de seis frentes | Seguridad, datos, backend clínico, frontend, calidad de pruebas y repositorio, en paralelo y ciegas entre sí | ✅ **Ejecutada** (07/09/2026). **101 hallazgos, 15 de severidad ALTA.** Cuatro reproducidos ejecutando código, incluido un sabotaje que dejó las 344 pruebas en verde con el motor clínico roto |
| Loop del arnés · D16-D17 | Que las guardias automáticas puedan fallar, y retirar la identidad de terceros | ✅ **Completado y mergeado** (07/09/2026, PR #18, merge commit `5f51831`). CI de **siete a nueve** comprobaciones; `check --deploy` recupera la capacidad de fallar; identidad del médico fuera del árbol. **344 tests OK** |
| Loop del repositorio · D18 | Separar producto de cuaderno de trabajo, y que el repositorio se pueda instalar | ✅ **Completado y mergeado** (07/09/2026, PR #19, merge commit `591cd7c`). `README`, `LICENSE`, `CONTRIBUTING`, `SECURITY`, `pyproject.toml` en vez de tres `requirements`, plantillas de `.github/`, `CODEOWNERS`, `.mailmap`, y el proceso movido a `proceso/`. **344 tests OK** |
| Loop de bugs del paciente | Los ocho fallos que llegan a la persona: parser de temperatura, rangos, salto, palabra de auxilio, turno de la tarde, tablero que miente, consentimiento revocado y habeas data del formulario | ✅ **Completado y mergeado** (PR #29, merge commit `6580996`, 09/09/2026). Fichas **D19-D23**, 3 migraciones, **43 pruebas nuevas** y un arnés de **17 reversiones, las 17 atrapadas**. **409 tests OK** |
| Loop de umbrales | Anclar los umbrales clínicos con pruebas de frontera | ✅ **Completado y mergeado** (08/09/2026, PR #28, merge commit `21105a2`). **22 pruebas nuevas** —el valor que dispara y el inmediatamente inferior— y un arnés re-ejecutable de **21 sabotajes, los 21 atrapados**. Cierra TEST-01 a TEST-05. **366 tests OK** |
| Reverificación y siete PR (02-04/10/2026) | Volver a comprobar los hallazgos contra el código, y corregir lo que se puede corregir sin el médico | ✅ **PR #36 a #42 mergeados.** Fichas **D25-D27**, primera ola de carriles en paralelo. **475 tests OK**. Detalle y próximo paso, abajo |

**Qué pasó (22/07/2026).** Una auditoría independiente sobre `fbf62a8` confirmó
las cuatro cifras que se reportaban (280 tests, `check --deploy`, `pip-audit`,
migraciones) y que **el aislamiento por médico resiste** un intento activo de
romperlo con 15 comprobaciones. Pero encontró **14 hallazgos** y dejó el PR
**BLOQUEADO**. El bloqueante: la escalera de severidad de las alertas SILENCIO
**nunca escalaba en producción** — un paciente con 3 días sin responder producía
`SILENCIO / BAJA`, y las 280 pruebas lo dejaban pasar porque estaban escritas
mirando el código en vez del requisito.

La corrección se organizó en loops, con las decisiones tomadas y documentadas
**antes** de escribir código en `docs/decisiones_correccion_auditoria.md`. Ese
archivo es la fuente de verdad del trabajo de corrección e incluye el estado de
avance por commit.

- **Loop A** (clínico, bloqueante): cerrado y verificado por el Arquitecto.
- **Loop B** (trazabilidad y operación): cerrado y verificado.
- **Loop C** (coherencia e higiene): cerrado y verificado.

**Qué pasó (27/07/2026).** La auditoría de cierre pre-merge (Codex) **volvió a
bloquear el PR** con dos hallazgos ALTOS: identidad del paciente en la salida
operativa, y un paciente activo que puede quedarse sin médico responsable —
invisible para todos. Los cuatro hallazgos se reprodujeron contra el código
antes de aceptarlos; la verificación cambió de sitio una corrección y encontró
una ocurrencia que el informe no vio.

- **Loop D** (privacidad operativa, responsable clínico, firma del webhook):
  **cerrado y verificado (27/07).** Los nueve pasos, 15 commits, suite en **337
  tests OK**, migraciones **0027** (`PROTECT`) y **0028** (`CheckConstraint`
  `activo ⇒ médico`).
- **Loop E** (aislamiento de las tareas del cron, D14): **cerrado, verificado y
  mergeado (07/08/2026, PR #10, merge commit `4fc690d`).** Con él quedan
  **implementadas las catorce decisiones D1-D14.**

**Método de trabajo de los loops:** decidir → documentar → **test en rojo** →
implementar → verificación del Arquitecto → un loop por sesión. Nació de la
lección que dejó el hallazgo bloqueante: *un test en verde no prueba nada si no
se verifica por qué está verde.*

**Desde el 02/10/2026, también en carriles paralelos:** varios loops a la vez,
solo si ningún par toca los mismos archivos, y como máximo tres. Cada carril
trabaja en su propia copia (worktree), con su rama, su PR y su propia base de
pruebas (`$env:DB_NAME='registro_carril_x'` en cada corrida, porque con un
nombre compartido una corrida con `--noinput` borra la base de la otra). Solo
un carril crea migraciones a la vez. El conteo de pruebas del README y del
ROADMAP choca en todos los PR y se recalcula al mergear en orden. **Lo clínico,
el bot y lo legal no van en carriles.** Y cada carril hace commit por hallazgo,
no al final: un corte por límite de uso dejó dos veces trabajo de un carril
varado sin commit.

**Producción: NO HAY, desde el 07/08/2026.** Venció el periodo de prueba de
Railway. El endpoint de salud responde **404** y los dos servicios cron **no
están corriendo**. Consecuencias para cualquier plan que se proponga:

- **Mergear a `produccion` no despliega nada** — no hay servicio al otro lado.
- **Nada se puede verificar contra producción.** La verificación de un cambio hoy
  es la suite local **más la CI de GitHub Actions**, que sigue corriendo y es
  gratuita. Esa CI es ahora la única red de seguridad automática del proyecto.
- **El trabajo local no está bloqueado.** El motor clínico, el bot, el Admin y
  las pruebas se desarrollan y verifican igual que siempre.

La topología, las variables y los gotchas siguen en `docs/railway_deploy.md`, que
pasó de describir el presente a ser el **guion para reconstruir el despliegue**
cuando haya plan de pago. No se borró nada de ahí a propósito.

**Los umbrales clínicos ya están anclados** (08/09/2026, rama
`umbrales-frontera`). El loop añadió **22 pruebas de frontera** —por cada umbral,
el valor que dispara y el inmediatamente inferior que no— y un arnés
re-ejecutable, `proceso/verificaciones/2026-09-08_verificacion_umbrales.py`, que
rompe el motor a propósito una constante a la vez: **21 sabotajes, los 21
atrapados**, incluido el del drenaje fecaloide que el día anterior había dejado
las 344 pruebas en verde con el motor roto. Suite en **366 tests OK**. Cierra los
hallazgos **TEST-01 a TEST-05**.

De ahí sale una regla que hereda `CONTRIBUTING.md` y que conviene no olvidar:
**ningún umbral clínico entra ni se mueve sin su par de pruebas de frontera**, y
el par no vale hasta que se ha visto caer.

**Los ocho bugs que tocan al paciente están corregidos** (08/09/2026, fichas
**D19-D23**). Los ocho se **reprodujeron ejecutando código** antes de tocar
nada —`proceso/verificaciones/2026-09-08_reproduccion_bugs_paciente.py`— y cada
corrección tiene su prueba de regresión, verificada revirtiendo el arreglo y
viéndola caer: **17 reversiones, las 17 atrapadas**.

Lo que cambió para el paciente: una temperatura ambigua ya no se guarda
truncada y el bot le dice lo que anotó; sin termómetro puede responder
*saltar* en vez de perder el turno entero; `0` es un dolor válido; **AYUDA**
detiene el cuestionario y avisa al médico desde cualquier punto; y el turno de
la tarde ya no se le niega. Para el médico: el tablero dejó de decir «todo bajo
control» con una ALTA sin resolver, y ve a quien tiene el seguimiento detenido.

> **Los «34 hallazgos de criterio del linter» NO EXISTEN.** Hasta el 09/09/2026
> este mismo párrafo los daba como el próximo paso, y era falso: `ruff` con la
> configuración que bloquea la CI pasa limpio desde el 07/09/2026. La cifra venía
> de un conteo exploratorio con un conjunto de reglas más amplio que el que se
> acabó seleccionando (ficha D16). Quien se fiara del documento habría gastado
> media sesión en trabajo inexistente — y eso es lo que motivó el **barrido de
> veracidad**, que hoy es la décima comprobación de la CI.
>
> Lo que sí aparece con un conjunto de reglas más amplio son ~447 avisos,
> dominados por `import-outside-top-level` y `relative-imports`, que son idioma
> de Django y no defectos. **No hay cola de linter pendiente.**

**Estado de la auditoría del 07/09/2026, al 04/10/2026.** El 02/10 se volvieron
a comprobar contra el código los 69 hallazgos que no estaban cerrados, y todos
recibieron severidad (antes solo 3 la tenían). De los 101:
**54 cerrados**, **45 abiertos confirmados**, **1 descartado** (BE-13: se
comprobó y no era un defecto) y **1 sin verificar** (TEST-11: hace falta correr
la suite con el reloj en las 23:59 de Bogotá). Cinco afirmaciones del informe
original resultaron falsas; la más seria, que **BE-02 estaba cerrado a medias**:
la gráfica del panel dibuja los umbrales con números escritos a mano en el JS.

**Lo que se hizo del 02 al 04/10/2026**, siete PR mergeados y **475 tests OK**:

| PR | Qué cambió | Decisión |
|---|---|---|
| #37 | Gases y náuseas en dos preguntas (UX-B03); una duda con turno pendiente arranca el reporte (BE-04, UX-B08). Migración 0031 con reverso real | D25 |
| #38 | El bot deja de prometer que le escribirá al paciente (UX-B02, BE-05); tildes de los cierres ALTA y MEDIA; «la última vez» en vez de «ayer»; abandono sin turno (DB-12, UX-B07) | D26 |
| #39 | Página pública: menú en el móvil, errores visibles, lo escrito se conserva, nada se recorta en silencio, accesibilidad, animación (UX-L01 a L06) | — |
| #40 | Pruebas que caen cuando se rompe lo que cuidan (TEST-06, 08, 10, 12 y la mitad del cron de TEST-07) | — |
| #41 | `wsgi`/`asgi` sin la variable arrancan con producción (SEC-04); la sesión del panel caduca a las 8 h y al cerrar el navegador (SEC-15) | — |
| #42 | `crear_admin` ya no reescribe ni promueve (SEC-05); `cron_runner` no vuelca el mensaje de la excepción (SEC-10) | D27 |

Cada uno con sus pruebas en rojo primero y sus reversiones atrapadas. Los
carriles B y C los hicieron agentes en paralelo, cada uno en su copia del
repositorio y con su propia base de pruebas (`DB_NAME` distinto); los revisó y
mergeó el agente principal.

**Próximo paso exacto (al retomar):**

1. **El carril A, el panel del médico.** Su PR (`carril-a-panel`) lleva la
   primera parte: orden de alertas por severidad, fecha de la última detección
   y consultas de más (UX-P02, UX-P03, DB-05) según lo que alcanzó. Revisarlo,
   repetir sus reversiones y mergearlo. Lo que dejó fuera lo dice su PR en «Lo
   que NO resuelve»: probablemente UX-P04 a P11, la mitad JS de BE-02 (con su
   extensión del barrido) y la frontera del aviso del Admin (TEST-07).
2. **REPO-20**, que está listo pero solo en local: darle al token el permiso
   `workflow` y subir `ci-no-cancela-tras-merge`.
3. **La documentación que miente** (REPO-05 a 09, DB-06): el ROADMAP duplica
   las tablas de modelos y su árbol de archivos está desfasado.
   `docs/modelos_datos.md` no tiene sección para `NotificacionAlerta`,
   `DeteccionAlerta` ni `MensajeContacto`, le faltan los cuatro campos de
   evaluación de `RegistroDiario`, y no menciona el tipo `AUXILIO` ni el
   estado `SIN_CONSENTIMIENTO`.
4. **El barrido de veracidad lee `.claude/worktrees/`**: recorre el sistema de
   archivos en vez de lo que git rastrea, y con carriles abiertos da falsos rojos
   en local (en la CI no). Esperar a que mergee el carril A, que también toca el
   barrido.

**Lo que necesita a alguien, no a una sesión técnica:**

- **El médico:** BE-08 y BE-09 (dos ramas de sobre-alerta, fijadas por pruebas
  de caracterización; ficha D10) y la redacción de las respuestas de la FAQ (D4).
- **León:**
  - **BE-03:** si el cron arranca tarde, crea el turno de la mañana y lo cierra
    en la misma corrida, lo que da SILENCIO a todos. Arreglarlo cambia qué
    cuenta como turno no respondido (D1).
  - **La caducidad de la sesión por inactividad:** hoy son 8 h desde que se
    entra, no desde el último clic.
  - **Arrancar Docker Desktop** para verificar SEC-13 (el contenedor como root).
  - **Rotar las credenciales del `.env` de desarrollo** (SEC-09).
  - **Lo legal:** SEC-07, SEC-08 y DB-11.
- **Alejandro:** activar el borrado automático de ramas en GitHub; la historia
  de git con datos de un tercero (REPO-01, D17).
- **Los datos de P-12** para la política de datos y la landing (SEC-03, REPO-21).

**Lo que este loop dejó abierto a propósito, y necesita datos tuyos:** la
página `/politica-datos/` está publicada como **BORRADOR**. Le faltan
responsable del tratamiento, dirección, canal para ejercer los derechos y plazo
de retención — los mismos `[corchetes]` de P-12. No se inventó ninguno.

**Lo que NO se decide en sesión técnica:** el canal del paciente, si el
repositorio se hace público, y avisarle al médico de sus datos en la historia.
Esas tres van a la reunión con Alejandro, el médico y el profesional de
desarrollo.

Los cinco cierres anteriores están **completos**: la rama del Sprint 5 (29/07),
la CI (31/07), el Loop E (07/08), el reparto de `tests.py` (10/08) y
`crear_medico` (12/08).

Lo que sigue, en este orden:

1. ~~**Montar CI**~~ — ✅ hecho el 31/07/2026 (PR #5, `5b40c01`). Las cinco
   comprobaciones se verificaron en rojo.
2. ~~**Loop E**~~ — ✅ hecho el 07/08/2026 (PR #10, `4fc690d`). D14 implementada;
   verificación independiente en
   `proceso/verificaciones/2026-08-06_verificacion_loop_e.py`.
3. ~~**Partir `tests.py`**~~ — ✅ hecho el 10/08/2026 (PR #12, `427153b`). Nueve
   archivos por tema más `soporte.py`; 340 tests y los 305 métodos comparados
   uno a uno contra el archivo original.
4. ~~**`crear_medico`**~~ — ✅ hecho el 12/08/2026 (PR #17, `1396744`). Decisión
   **D15** y su implementación; verificado en las dos direcciones con dos
   sabotajes documentados en la ficha.

**Esta lista está terminada.** Con Railway caído, todo lo que toca despliegue,
Twilio o el piloto sigue fuera de alcance hasta que haya plan de pago — conviene
no proponer trabajo que hoy no se puede terminar.

**No hay guion escrito para lo que sigue, y es deliberado:** se decide en sesión,
no se hereda de una lista vieja. Lo anotado como posible es **auditar la calidad
de las pruebas** —al partir `tests.py` no se revisó ninguna, a propósito— y la
decisión de **protección de rama**.

**Pendientes menores que dejó el montaje de la CI**, ninguno bloqueante:

- ~~El `override_settings` que le faltaba a
  `home.tests.ClientIpTests.test_por_defecto_ignora_headers_spoofeables`~~ — ✅
  cerrado el 31/07/2026 (PR #7, `dc32530`), la misma sesión que lo encontró.
  Verificado en las dos direcciones, incluida la que importa: anulando la guarda
  de `_get_client_ip`, la prueba vuelve a caer.
- **Protección de rama en `Desarrollo`** para que los checks bloqueen el merge.
  **No es un trámite de permisos** —eso decía este archivo y era incorrecto—
  sino una decisión con coste: GitHub Pro, repositorio público, o seguir
  mirando los checks a mano. Ver la sección "Repositorio", arriba.
- La versión de PostgreSQL de Railway no está documentada; la CI usa
  `postgres:18` por ser la mayor de la base local.

Las dos auditorías de julio **ya se ejecutaron — no repetirlas.** A ellas se
sumó la **auditoría de seis frentes del 07/09/2026** (seguridad, datos,
backend clínico, frontend, calidad de pruebas y repositorio), de la que salieron
las fichas **D16**, **D17** y **D18**. **Sus 101 hallazgos están itemizados
con su estado actual**, y hay que consultarlos antes de tocar cualquiera de
ellos: dicen cuáles siguen abiertos y cuáles solo están *trazados* y no
reproducidos. Las decisiones D1-D18 están tomadas; no se reabren salvo que el
Arquitecto lo pida.

**Deuda técnica y su orden de atención (29/07/2026).** La revisión de cierre del
PR dejó **8 puntos** de deuda que no bloquean el merge, con la secuencia decidida
de dónde se atiende cada uno. Lo esencial: **el Loop E es solo el punto 2** (D14, aislar el cron) y no se le agrega nada más —
un loop, un tema. El punto 1 (CI) **ya está hecho**; **partir `tests.py` va
después del Loop E**, en la ventana en que ninguna rama esté avanzando en
paralelo.

**Railway despliega desde `produccion`** (desde el 29/07/2026, los tres
servicios). Cada push a `produccion` sale a producción de inmediato; **mergear a
`Desarrollo` no despliega nada**. Desplegar es un merge explícito de
`Desarrollo` → `produccion`. Detalle en `docs/railway_deploy.md` §4.1.

### Por resolver antes del piloto real

1. **Datos reales del médico en la landing (P-12):** reemplazar los
   `[corchetes]`, subir logo/colores propios, y poner
   `MOSTRAR_AVISO_BOCETO = False` en `home/views.py`.
2. **Cuenta del médico definitivo:** `medico_piloto` ya fue creada, probada y
   limitada correctamente. Antes de pacientes reales hay que decidir si esa
   cuenta se transfiere al médico o se crea la definitiva con el mismo comando
   y se reasignan los pacientes.
   **La restricción que condicionaba esta decisión ya no existe** (D15,
   12/08/2026): `crear_medico` deja de reescribir la contraseña, así que la
   cuenta **sí puede tener una contraseña propia que sobreviva a un despliegue**.
   Lo que queda es administrativo: transferirla o crear la definitiva. Ojo con lo
   que **sigue** reescribiéndose a propósito —grupos y permisos— y con
   `DJANGO_MEDICO_RESET`: ver `docs/trampas_conocidas.md` y la ficha D15 en
   `docs/decisiones_correccion_auditoria.md`.
3. **Requisitos del piloto real** (ver ROADMAP, "Requisitos para un PILOTO REAL
   con pacientes"): plan de pago de Railway, salir del Sandbox de Twilio a
   **WhatsApp Business API**, dominio autenticado de Resend, monitoreo externo
   apuntando al endpoint de salud, completar los corchetes de
   `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` y repetir el end-to-end sobre
   el canal definitivo.
4. **Validación médica de las cuatro respuestas del bot** (ficha D4 y
   `knowledge_base.md`, sección "Consulta pendiente al médico").
5. **Infraestructura:** al mejorar el plan de Railway, crear `cron-operativo`
   como servicio separado y restaurar `cron-tarde` a su horario original.

### Diferido explícitamente

- Integración real de Twilio saliente en `enviar_recordatorios` (hoy es un
  stub: el sistema es reactivo y el paciente debe escribir primero).
- Monitoreo externo de disponibilidad y de ejecuciones omitidas de los cron; los
  reintentos internos no sustituyen esa alarma operativa.
- Vista separada de historial del paciente (URL y template propios).
- RAG/MCP en el bot — Sprint 6, con corpus de `knowledge_base.md` validado por
  el médico (decisión P-13).
- OpenMed (anonimización PII) — Sprint 6, solo referencia (P-14).

Decisiones de producto P-1 a P-15 confirmadas en sesión (01/07/2026) — tabla
completa en `ROADMAP_MONITOREO_POSQUIRURGICO.md`, FASE 5.

---

## Roles del Equipo

> **Corregido el 07/09/2026.** Hasta esta fecha esta sección decía que León
> *"NO es el programador principal"* y que Alejandro *"implementa modelos y
> vistas"*. **Era falso**, y no es un detalle: es lo primero que lee un agente
> antes de decidir cómo trabajar, y lo estuvo llevando a tratar a quien escribe
> el código como si no lo escribiera. La historia de git ya lo contradecía —316
> commits contra 14— sin que nadie sacara la conclusión.

- **León (`@arboledaLeon`):** **programador y desarrollador principal.** Escribe
  el código, define la lógica clínica, valida las reglas médicas y aprueba cada
  decisión de diseño. Trabaja con Claude Code. Es quien firma lo clínico: cuando
  el resto de esta documentación dice "el Arquitecto", se refiere a él.
- **Alejandro (`@Alejandro-Valen`):** se consulta para las decisiones de
  **funcionamiento, arquitectura, infraestructura y la gestión con el médico**.
  Trabaja con Codex CLI.

**Nota sobre el README.** Ahí los dos aparecen con el mismo rol —"lógica
clínica, arquitectura, desarrollo e infraestructura"— y es **deliberado**: de
cara afuera no se reparten méritos, porque cada aporte es necesario. Esta
sección describe el reparto real del trabajo, que es lo que un agente necesita
saber; aquella describe al equipo, que es lo que un visitante necesita saber. No
se contradicen: responden preguntas distintas.

---

---

## Protocolo Obligatorio de Cierre de Sesión

**Esto no es opcional. Al final de CADA sesión de trabajo, sin que el Arquitecto
tenga que pedirlo, Claude Code debe ejecutar estos 3 procesos en orden:**

### 1. Documentar la sesión en el cuaderno de trabajo
**La bitácora salió del repositorio el 20/09/2026.** La narrativa de sesión vive
desde entonces en el cuaderno de trabajo, fuera del árbol; aquí ya no se escribe
—y no se recrea `BITACORA.md`, que es justo lo que esa mudanza deshizo—. Agregar
una entrada de sesión con el formato de siempre (Sprint, Fecha, Responsable,
Estado, Qué se hizo, Decisiones tomadas, Problemas encontrados y resueltos).
Debe incluir:
- Qué se construyó, en lenguaje claro. La bitácora la lee quien retoma meses
  después y quien nunca vio esta sesión: tiene que entenderse sin abrir el diff.
- Decisiones clínicas tomadas y su justificación médica.
- Errores, bugs o conflictos de merge que aparecieron y cómo se resolvieron —
  esto es lo más valioso, nunca omitir un problema solo porque ya se arregló.
- Qué queda pendiente para la próxima sesión, indicando el paso exacto (no
  solo "Sprint 3 pendiente", sino "paso 3: views.py + urls.py + Twilio").

### 2. Actualizar el estado y el documento dueño de lo que se tocó
- En **CLAUDE.md**: actualizar la tabla "Estado Actual del Proyecto" y el
  "Próximo paso exacto" con el sprint y paso donde quedó el trabajo.
- En **ROADMAP_MONITOREO_POSQUIRURGICO.md**: marcar con `[x]` los
  checkboxes de las tareas completadas en la sesión.

  **Regla de sincronización inmediata (no diferible):** si la sesión
  modificó una regla, umbral, constante, campo de modelo o estructura de
  datos, **el documento dueño de ese tema se actualiza en el mismo lote de
  commits que el código**:

  | Si tocaste... | Actualiza en el mismo commit |
  |---|---|
  | `alert_engine.py` — reglas, umbrales, severidades | `docs/reglas_clinicas.md` |
  | `models.py` — campos, choices, constraints, migraciones | `docs/modelos_datos.md` |
  | `bot.py` — máquina de estados, preguntas, respuestas | `docs/bot_whatsapp.md` |
  | Despliegue, cron, variables de entorno | `docs/railway_deploy.md` · `docs/cron_setup.md` |

  Esto **NUNCA se difiere**, ni siquiera si el Arquitecto pidió esperar
  para escribir la bitácora. La narrativa del cuaderno (qué se hizo,
  por qué, qué queda pendiente) sí puede acumularse en una sola entrada al
  cierre de una fase; las referencias técnicas no — deben reflejar el
  código real en todo momento, porque son lo primero que cualquier agente
  lee antes de decidir qué hacer.

  **Y no se copian a otro documento.** Cada hecho tiene un solo archivo
  dueño; los demás apuntan. Ver `docs/arquitectura_documentacion.md`.

  **Norma de zona horaria:** todo cálculo de 'fecha de hoy' usa
  `timezone.localdate()`, nunca `.date()` sobre un datetime aware ni
  `timezone.now().date()` — con USE_TZ=True y TIME_ZONE=America/Bogota,
  esos dos devuelven la fecha en UTC, no en la zona del proyecto, y
  rompen las reglas de días calendario en horario nocturno.

### 3. Git add, commit y push
- Seguir la convención de commits ya definida (`feat:`, `fix:`, `docs:` +
  descripción en español).
- Nunca dejar trabajo funcional sin commitear al cerrar sesión.
- Hacer push siempre a la rama activa — no dejar commits solo locales.
- Si hay cambios de código Y de documentación, son commits separados (uno de
  código, otro de `docs:`).

**Regla de oro:** si el Arquitecto dice "vamos a cerrar", "dejemos hasta aquí",
"eso es todo por hoy" o cualquier frase equivalente, estos 3 pasos se ejecutan
automáticamente sin que tenga que pedir cada uno por separado. Al finalizar,
mostrar un resumen breve de qué se documentó y qué se commiteó/pusheó.

**Excepción:** si el Arquitecto dice explícitamente "no hagas commit todavía"
o "espera para documentar", respetar eso y ejecutar el paso correspondiente
solo cuando lo confirme.

**Nota sobre la evidencia clínica:** la auditoría de literatura ya se
realizó (ver `docs/auditoria_literatura/`), pero `knowledge_base.md`
permanece como placeholder hasta que el Arquitecto tome las decisiones de
umbrales/reglas del `alert_engine` que se derivan de ella. No completar
con información clínica real, inventada o supuesta, ni cambiar reglas del
`alert_engine`, sin esa decisión explícita.

---

## Convenciones del Equipo

- Idioma del código: **español** (nombres de variables, comentarios, commits).
- Rama principal: `Desarrollo` — **nadie trabaja directo aquí**.
- Una rama por sprint: `sprint-1-modelos`, `sprint-2-alertas`, `sprint-3-whatsapp`, etc.
- El `.env` **nunca** se sube a GitHub.
- Ningún código clínico entra a `Desarrollo` sin aprobación explícita del
  Arquitecto — incluyendo el visto bueno de cada decisión de diseño antes de
  escribir en disco, no solo antes del merge final.
- Commits: formato `feat:`, `fix:`, `docs:` + descripción en español.
- Modelo de Claude recomendado: **Opus** para diseño de arquitectura y
  decisiones clínicas complejas (máquina de estados, alert_engine); **Sonnet**
  para tareas rutinarias (tests, configuración, documentación).

---

## Comandos Esenciales

```bash
# Posición correcta para todos los comandos manage.py: la carpeta que
# contiene manage.py, un nivel por debajo de la raíz del repositorio.
# La ruta se escribe DESDE LA RAÍZ del repositorio — hasta el 08/09/2026
# esta línea decía `Registro_Post_Quirurgico/Registro_Post_Quirurgico`,
# que solo funciona si se ejecuta desde la carpeta padre del repositorio y
# falla desde la raíz. Era el hallazgo REPO-14 de la auditoría del 07/09.
cd Registro_Post_Quirurgico          # desde la raíz del repositorio

python manage.py check                 # verificar sin errores
python manage.py makemigrations        # después de cambiar models.py
python manage.py migrate               # aplicar cambios a PostgreSQL
python manage.py test --noinput        # suite completa
python manage.py runserver             # http://127.0.0.1:8000/admin/

# Desde que tests.py es un paquete, se puede correr un solo tema (segundos en
# vez de los ~4,5 min de la suite completa en Windows):
python manage.py test signos_sintomas.tests.test_alert_engine --noinput
python manage.py test signos_sintomas.tests.test_bot.BotWhatsAppTests --noinput
```

`--noinput` evita quedarse esperando el prompt de borrado si una corrida
anterior murió y dejó la base de pruebas a medio crear.

**El intérprete es el del entorno virtual, `.venv/`, no el `python` del
PATH.** En la máquina del Arquitecto el `python` global es un 3.10 sin
Django ni `ruff` instalados, así que un comando lanzado sin activar el
entorno falla con `No module named ...` o `can't open file manage.py` y
parece un problema del proyecto cuando no lo es. Activarlo, o invocar
`.venv/Scripts/python.exe` por ruta.

**Antes de abrir un PR, la suite completa igual** — correr solo un tema es para
iterar rápido, no para dar algo por bueno. La CI corre la completa de todos
modos.
