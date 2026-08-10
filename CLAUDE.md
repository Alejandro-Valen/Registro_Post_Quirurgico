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
| `docs/decisiones_correccion_auditoria.md` | Antes de tocar lo que corrigieron los Loops A, B y C (fichas D1-D10) |
| `ROADMAP_MONITOREO_POSQUIRURGICO.md` | Antes de proponer alcance nuevo o discutir prioridades |

### Consúltalo cuando necesites contexto

| Documento | Qué responde |
|-----------|--------------|
| `docs/README.md` | Índice general y **orden de autoridad** si dos documentos se contradicen |
| `docs/proceso/metodo_de_trabajo.md` | **Cómo se corrige algo aquí:** decidir → documentar → test en rojo → implementar → verificar. Léelo antes de tu primer cambio |
| `BITACORA.md` | Qué pasó en cada sesión, con los problemas encontrados y cómo se resolvieron |
| `docs/resumen_sprints.md` | Qué entregó cada sprint, bloque y loop — el mapa de la BITÁCORA |
| `docs/auditoria_literatura/` | La evidencia clínica que respalda (o no) cada umbral |
| `docs/transferencia_cuentas.md` | Propiedad de servicios y credenciales |
| `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` | Documento legal canónico (Ley 1581/2012) |

### Si algo se contradice

Manda **el código**; después el documento dueño de ese tema (los de la tabla
"antes de tocar"); después este archivo. `BITACORA.md` describe el momento en
que se escribió y nunca es fuente de verdad sobre el estado actual. Al
encontrar una contradicción, **corrígela en el mismo commit** en vez de dejarla
anotada para después.

---

## Stack Tecnológico

- **Backend:** Django 6.0.7 + Python 3.13
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
- **Rama activa de trabajo:** ninguna. `guardia-secretos` se mergeó el
  10/08/2026 (PR #13); la siguiente se abre desde `Desarrollo`.
- **Cada PR se verifica solo:** `.github/workflows/ci.yml` corre **siete
  comprobaciones** en cada PR hacia `Desarrollo` y hacia `produccion`, y en cada
  push a esas dos ramas: la suite, `check`, `makemigrations --check`,
  `check --deploy`, la higiene del diff, la **guardia de secretos** (`gitleaks`
  sobre la historia completa) y que no haya ningún `.env` rastreado.
- **Los checks se ven pero no bloquean.** `Desarrollo` no tiene protección de
  rama. **Y no es cuestión de permisos**, como decía este archivo hasta el
  10/08/2026: en un repositorio **privado** de una cuenta personal sin GitHub
  Pro, GitHub no ofrece protección de rama **a nadie, ni al dueño** — la API de
  rulesets responde *"Upgrade to GitHub Pro or make this repository public"*.
  Las tres salidas son: GitHub Pro (~4 USD/mes, en la cuenta del dueño), hacer
  el repositorio público, o seguir con la compuerta humana de mirar los siete
  checks antes de mergear. Hoy rige la tercera: **mirar antes de mergear**.

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
una ocurrencia que el informe no vio. Informe completo en
`docs/proceso/auditorias/2026-07-27_informe_cierre_codex.md`.

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

**Próximo paso exacto (al retomar):** verificar el estado real contra `git log` y
la suite antes de proponer nada, y seguir el guion de
**`docs/proceso/2026-08-10_instruccion_crear_medico.md`** — el objetivo de esa
sesión es **una decisión, no código**: qué hacer con `crear_medico`, que reescribe
la cuenta del médico —contraseña, grupos y permisos— en **cada arranque** del
servicio web. Se decide primero, se documenta, y solo después se programa.

Los cuatro cierres anteriores están **completos**: la rama del Sprint 5
(`docs/proceso/2026-07-28_instruccion_cierre_rama_sprint5.md`, 29/07), la CI
(`docs/proceso/2026-07-30_instruccion_sprint6_ci.md`, 31/07), el Loop E
(`docs/proceso/2026-08-01_instruccion_loop_e.md`, 07/08) y el reparto de
`tests.py` (`docs/proceso/2026-08-07_instruccion_partir_tests.md`, 10/08).

Lo que sigue, en este orden (razonamiento y detalle en
`docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`):

1. ~~**Montar CI**~~ — ✅ hecho el 31/07/2026 (PR #5, `5b40c01`). Las cinco
   comprobaciones se verificaron en rojo:
   `docs/proceso/verificaciones/2026-07-31_verificacion_ci.md`.
2. ~~**Loop E**~~ — ✅ hecho el 07/08/2026 (PR #10, `4fc690d`). D14 implementada;
   verificación independiente en
   `docs/proceso/verificaciones/2026-08-06_verificacion_loop_e.py`.
3. ~~**Partir `tests.py`**~~ — ✅ hecho el 10/08/2026 (PR #12, `427153b`). Nueve
   archivos por tema más `soporte.py`; 340 tests y los 305 métodos comparados
   uno a uno contra el archivo original.
4. **`crear_medico`** — **es el siguiente.** Decidir qué hacer antes de
   entregarle la cuenta al médico (ver "Por resolver antes del piloto real",
   punto 2). Guion en `docs/proceso/2026-08-10_instruccion_crear_medico.md`.

**Ojo con el orden de aquí en adelante.** Con Railway caído, el punto 4
es el único que depende solo de nosotros; todo lo que toca despliegue,
Twilio o el piloto quedó fuera de alcance hasta que haya plan de pago. Eso no
cambia las prioridades — 3 y 4 ya eran los siguientes — pero sí conviene no
proponer trabajo que hoy no se puede terminar.

**No hay guion escrito más allá de `crear_medico`.** Cuando ese punto se cierre,
lo que siga se decide en sesión: no hay una cola de trabajo esperando. Lo único
anotado como posible es auditar la calidad de las pruebas ahora que están
repartidas por tema — al partirlas **no se revisó ninguna**, a propósito.

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

Las dos auditorías **ya se ejecutaron — no repetirlas.** Las decisiones D1-D14
están tomadas; no se reabren salvo que el Arquitecto lo pida.

**Deuda técnica y su orden de atención (29/07/2026).** La revisión de cierre del
PR dejó **8 puntos** de deuda que no bloquean el merge, con la secuencia decidida
de dónde se atiende cada uno:
`docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`. Lo esencial: **el
Loop E es solo el punto 2** (D14, aislar el cron) y no se le agrega nada más —
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
   **Restricción que condiciona esa decisión:** `crear_medico` corre en **cada
   arranque** del servicio web y reescribe la cuenta —contraseña, grupos y
   permisos—, así que hoy esa cuenta **no puede tener una contraseña propia que
   sobreviva a un despliegue**. Detalle en
   `docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`, punto 8, y la
   advertencia operativa en `docs/trampas_conocidas.md`.
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

- **León (Arquitecto IA):** define lógica clínica, valida reglas médicas,
  aprueba cada decisión de diseño antes de que se escriba código, trabaja con
  Claude Code. NO es el programador principal.
- **Alejandro (Dev Full-Stack):** implementa modelos y vistas, configura
  infraestructura, trabaja con Codex CLI.

---

---

## Protocolo Obligatorio de Cierre de Sesión

**Esto no es opcional. Al final de CADA sesión de trabajo, sin que el Arquitecto
tenga que pedirlo, Claude Code debe ejecutar estos 3 procesos en orden:**

### 1. Documentar en BITACORA.md
Agregar una nueva entrada de sesión siguiendo el formato ya usado en el archivo
(Sprint, Fecha, Responsable, Estado, Qué se hizo, Decisiones tomadas, Problemas
encontrados y resueltos). Debe incluir:
- Qué se construyó, en lenguaje claro — el Arquitecto define la lógica clínica
  pero no es el programador principal.
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
  para escribir en BITACORA.md. La narrativa de la BITÁCORA (qué se hizo,
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
# Posición correcta para todos los comandos manage.py
cd Registro_Post_Quirurgico/Registro_Post_Quirurgico

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

**Antes de abrir un PR, la suite completa igual** — correr solo un tema es para
iterar rápido, no para dar algo por bueno. La CI corre la completa de todos
modos.
