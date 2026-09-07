# Arquitectura de la documentación

> **Qué es este documento.** La decisión de cómo se organiza la documentación
> de este proyecto y **por qué**. Se consulta cuando alguien va a crear un
> documento nuevo, no sabe dónde escribir algo, o encuentra dos archivos que se
> contradicen.
>
> **Fecha de la decisión:** 24/07/2026 · **Tomada por:** León (Arquitecto) ·
> **Contexto:** Loop C de la corrección post-auditoría del Sprint 5.

---

## El problema que resuelve

`CLAUDE.md` había crecido hasta **54.742 caracteres**. Dentro convivían cuatro
cosas de naturaleza distinta:

| Qué contenía | Peso | Con qué frecuencia cambia |
|---|---|---|
| Reglas clínicas, modelos y bot | 44% | Casi nunca — y cada cambio necesita aprobación |
| Cronología de sprints y loops | 38% | Cada sesión |
| Instrucciones de trabajo | 10% | Rara vez |
| Contexto del proyecto | 8% | Casi nunca |

Eso produjo tres problemas concretos, todos verificados:

1. **Duplicación con contradicción latente.** Las tablas de reglas del
   `alert_engine` estaban copiadas en `CLAUDE.md` **y** en el ROADMAP. Cada
   cambio clínico había que hacerlo en dos lugares; el día que alguien olvide
   uno, el proyecto tiene dos versiones de un umbral médico y ninguna forma de
   saber cuál manda.
2. **Cronología duplicada de la BITÁCORA.** El 38% del archivo era narrativa de
   qué pasó en cada loop — que ya estaba, con más detalle, en `proceso/BITACORA.md`.
3. **Riesgo al actualizar el estado.** El protocolo de cierre obliga a
   actualizar el estado del proyecto en cada sesión, y eso significaba editar el
   mismo archivo que contiene las reglas clínicas. Un descuido al escribir el
   estado podía tocar una tabla clínica.

---

## La decisión

**Un hecho, un archivo dueño.** Cada pieza de conocimiento vive en exactamente
un documento, y ese documento se actualiza **en el mismo lote de commits** que
el código que describe. Los demás documentos no copian: apuntan.

`CLAUDE.md` deja de ser el manual y pasa a ser **la puerta de entrada**: qué es
el proyecto, cómo se trabaja aquí, dónde vamos, y un mapa de dónde vive cada
cosa.

### Estructura resultante

```
CLAUDE.md                    Puerta de entrada + mapa. Carga las reglas clínicas.
BITACORA.md                  Cronología: qué pasó en cada sesión y por qué.
ROADMAP_...md                Producto: decisiones P-x, checklists, alcance.
docs/
├── README.md                Índice general y ORDEN DE AUTORIDAD.
├── arquitectura_documentacion.md   Este archivo.
├── reglas_clinicas.md       FUENTE ÚNICA de las 8 reglas + SILENCIO + variables.
├── modelos_datos.md         FUENTE ÚNICA de los modelos y sus decisiones de diseño.
├── bot_whatsapp.md          FUENTE ÚNICA de la máquina de estados y sus reglas.
├── trampas_conocidas.md     Errores que ya costaron horas y volverán a morder.
├── resumen_sprints.md       Mapa compacto de la BITÁCORA (qué entregó cada etapa).
├── decisiones_correccion_auditoria.md   Fichas D1-D17 con su razonamiento.
├── railway_deploy.md        Topología, variables y despliegue.
├── cron_setup.md            Programación y límites de los cron.
├── transferencia_cuentas.md Propiedad de servicios y credenciales.
├── FORMATO_CONSENTIMIENTO_HABEAS_DATA.md   Documento legal canónico.
└── auditoria_literatura/    La evidencia clínica, documento por documento.
```

### Qué se carga solo y qué se lee bajo demanda

`CLAUDE.md` importa **solo** `docs/reglas_clinicas.md` (con `@docs/...`), así que
esas reglas viajan siempre en el contexto de cualquier agente. El criterio:

- **Se carga siempre** lo que un agente puede romper *sin darse cuenta de que
  entró en territorio clínico*. Si no lee las reglas, puede inventar un umbral.
- **Se lee bajo demanda** lo que un agente solo toca deliberadamente: modelos,
  bot, despliegue. Ahí basta con que el mapa le diga que existe y cuándo es
  obligatorio abrirlo.

Cargar todo siempre tendría el mismo costo que el archivo monolítico anterior y
no resolvería nada.

---

## Los principios que hay detrás

**1. Manda el código.** Cualquier documento puede quedar desfasado; el código
es lo que corre. El orden de autoridad ante una contradicción es: código →
documento dueño del tema → `CLAUDE.md` → BITÁCORA. Y al encontrar una
contradicción se **corrige en el mismo commit**, no se anota para después.

**2. La sincronización de referencias técnicas no es diferible.** Si un cambio
toca una regla, un umbral, un campo de modelo o el flujo del bot, el documento
dueño se actualiza en el mismo lote de commits. La narrativa de la BITÁCORA sí
puede acumularse hasta el cierre de sesión; las tablas de referencia no, porque
son lo primero que lee un agente para decidir qué hacer.

**3. La documentación es neutral respecto de la herramienta.** El conocimiento
del proyecto vive en markdown plano dentro de `docs/`, legible por Claude, por
Codex, por un desarrollador sin agente y por el propio Arquitecto en dos años.
La prueba: *si se borra la carpeta `.claude/` entera, ¿se pierde conocimiento
clínico o de arquitectura?* La respuesta debe ser **no**. En `.claude/` solo va
configuración de una herramienta concreta (permisos, comandos propios), nunca
las reglas del sistema.

**4. No se inventa nada al reorganizar.** El contenido se **mueve textual**, con
script, nunca reescribiendo de memoria. Reformular una regla clínica mientras se
"ordena la documentación" es introducir un cambio clínico sin aprobación. Al
mover, se verifica: en esta reorganización se comprobó que los 15 hashes de
commit, 6 migraciones, 9 cifras de tests, 108 identificadores de código y 12
identificadores de decisión del archivo anterior siguen teniendo documento.

**5. Historia y estado son cosas distintas.** La BITÁCORA es acumulativa y
describe el momento en que se escribió: **nunca** es fuente de verdad sobre el
estado actual. El estado vive en `CLAUDE.md` y se reescribe; la historia se
agrega y no se toca.

---

## Qué queda pendiente (decidido, no ejecutado)

**`AGENTS.md` para Codex.** Alejandro trabaja con Codex CLI, que no lee
`CLAUDE.md`. La intención es un archivo delgado equivalente, apuntando a los
mismos `docs/`, para que el conocimiento no dependa de qué herramienta use cada
quien. **Pendiente de verificar con Alejandro** cuál es el nombre y formato que
su herramienta lee de verdad, antes de crearlo — no se agrega un archivo por
suposición.

**`.claude/` como configuración versionada.** Hoy solo existe
`.claude/settings.local.json` con permisos personales, fuera de Git por
accidente y no por decisión (`.gitignore` no lo menciona). Lo pendiente:
separar lo compartible (`settings.json`) de lo personal
(`settings.local.json`, explícitamente ignorado) y evaluar un comando propio
`/cerrar-sesion` que ejecute el protocolo obligatorio de cierre, que hoy depende
de que el agente se acuerde de leerlo.

**Ambas cosas se hacen después del merge a `Desarrollo`,** en rama propia: son
mejoras de proceso y no deben mezclarse con el PR que cierra los 14 hallazgos de
la auditoría, que tiene que poder revisarse por lo que es.

---

## Cómo decidir dónde escribir algo nuevo

| Si es... | Va en... |
|---|---|
| Una regla, umbral o mensaje clínico | `docs/reglas_clinicas.md` |
| Un campo, modelo o migración | `docs/modelos_datos.md` |
| Una pregunta o texto que ve el paciente | `docs/bot_whatsapp.md` |
| Un error que costó horas y puede repetirse | `docs/trampas_conocidas.md` |
| El porqué de una decisión de diseño | La ficha correspondiente en `docs/decisiones_*.md` |
| Qué pasó hoy y qué problemas aparecieron | `proceso/BITACORA.md` |
| Dónde vamos y cuál es el siguiente paso | `CLAUDE.md`, sección "Estado Actual" |
| Alcance nuevo o una prioridad de producto | `ROADMAP_MONITOREO_POSQUIRURGICO.md` |

Si no encaja en ninguna fila, probablemente sea un documento nuevo — y entonces
hay que agregarlo al mapa de `CLAUDE.md` y al índice de `docs/README.md` en el
mismo commit. Un documento que nadie sabe que existe no está documentando nada.
