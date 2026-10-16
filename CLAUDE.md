# Contexto del Proyecto — Sistema de Monitoreo Posquirúrgico Remoto

> **Para agentes IA y para cualquier desarrollador nuevo:** este archivo es la
> **puerta de entrada**, no el manual. Dice qué es el proyecto, cómo se trabaja,
> dónde vamos y **dónde vive cada cosa**. Las reglas clínicas se cargan solas
> junto con él; los demás documentos se leen **cuando vas a tocar esa parte**.
>
> **Regla que no se negocia:** ninguna regla, umbral o mensaje clínico se
> cambia sin decisión explícita del Arquitecto. Los umbrales tienen base en
> evidencia de recuperación postoperatoria colorrectal (protocolos ERAS); la
> auditoría de literatura confirmó que ningún estudio revisado trata
> HIPEC/Sugarbaker de forma específica.

## ¿Qué es este proyecto?

Monitoreo remoto posquirúrgico para pacientes en recuperación de cirugía
colorrectal —incluidos casos Sugarbaker/HIPEC, sin ser exclusivo de ellos (campo
`tipo_cirugia` de `Paciente`)—. El paciente interactúa **solo por WhatsApp**: un
bot le pregunta su telemetría, el sistema la clasifica con reglas fijas
(`alert_engine`) y avisa al médico en un panel sobre Django Admin.

**La IA NO diagnostica.** Clasifica, resume y alerta con reglas fijas.

**Sin afiliación institucional formal.** No usar nombres de instituciones ni
"Sugarbaker" como marca del sistema en código, documentación o nombre del
repositorio hasta que exista una decisión formal.

---

## Mapa de la documentación

> Por qué existe esta separación: `docs/arquitectura_documentacion.md`. En una
> línea: **cada hecho vive en un solo archivo**, y ese archivo se actualiza en
> el mismo commit que el código que describe.

### Se carga solo, junto con este archivo

Las reglas clínicas viajan siempre en el contexto: el riesgo de que un agente no
las lea es que invente un umbral.

@docs/reglas_clinicas.md

### Léelo ANTES de tocar esa parte

| Documento | Cuándo es obligatorio leerlo |
|-----------|------------------------------|
| `docs/modelos_datos.md` | Antes de tocar `models.py`, escribir una migración o agregar un campo |
| `docs/bot_whatsapp.md` | Antes de tocar `bot.py`, la máquina de estados o cualquier texto que lea el paciente |
| `docs/trampas_conocidas.md` | Antes de tocar despliegue, cron, Twilio o correo. Son errores que ya costaron horas |
| `docs/railway_deploy.md` | Antes de cambiar variables de entorno o desplegar |
| `docs/cron_setup.md` | Antes de tocar los management commands programados |
| `docs/decisiones_correccion_auditoria.md` | Antes de tocar lo que corrigieron los loops de auditoría (fichas **D1-D27**) |
| `ROADMAP_MONITOREO_POSQUIRURGICO.md` | Antes de proponer alcance nuevo o discutir prioridades |

### Consúltalo cuando necesites contexto

| Documento | Qué responde |
|-----------|--------------|
| `README.md` (raíz) | La portada: qué hace, cómo se instala, qué falta para pacientes reales |
| `CONTRIBUTING.md` | Ramas, commits, qué correr antes del PR y las reglas del código |
| `SECURITY.md` | Qué cuenta como fallo de seguridad, qué está resuelto y **qué falta** |
| `docs/README.md` | Índice general y **orden de autoridad** si dos documentos se contradicen |
| `docs/resumen_sprints.md` | **La historia:** qué entregó cada sprint, bloque y loop, con su PR y su merge |
| `docs/auditoria_literatura/` | La evidencia clínica que respalda (o no) cada umbral |
| `docs/transferencia_cuentas.md` | Propiedad de servicios y credenciales |
| `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` | Documento legal canónico (Ley 1581/2012) |

`docs/` es **solo producto**. `proceso/verificaciones/` guarda los scripts que
se ejecutan a mano para comprobar el trabajo. La narrativa de cada sesión, los
guiones de reunión y la bitácora **no viven en el repositorio** (salieron el
20/09/2026) y aquí no se recrean.

### Si algo se contradice

Manda **el código**; después el documento dueño del tema; después este archivo.
Al encontrar una contradicción, **corrígela en el mismo commit**.

---

## Stack

- **Backend:** Django 6.1.1 + Python 3.13 (lo fija `pyproject.toml`)
- **Base de datos:** PostgreSQL 18 (local: `registro_postquirurgico_db`)
- **Paciente:** bot de WhatsApp vía Twilio · **Médico:** Django Admin personalizado
- **Desarrollo:** Windows 11, con el entorno virtual `.venv/` (ver "Comandos")

## Estructura

```
Registro_Post_Quirurgico/Registro_Post_Quirurgico/
├── Registro_Post_Quirurgico/  → settings.py, settings_local.py (dev), settings_production.py (prod)
├── home/                      → portal web, páginas informativas, formulario de contacto
└── signos_sintomas/           → núcleo clínico
    ├── models.py, admin.py, alert_engine.py, bot.py, signals.py, views.py
    ├── management/commands/   → crear_checkins_diarios, enviar_recordatorios,
    │                             cerrar_checkins_vencidos, seed_demo, …
    └── tests/                 → un archivo por tema + soporte.py
```

**En `tests/`, dos cosas que no se tocan:** `__init__.py` debe existir —sin él
Django no recorre el paquete y el conteo baja **en silencio**— y `soporte.py` se
llama así, y no `test_soporte.py`, para que el descubridor no lo recorra.

La carpeta se llama `Registro_Post_Quirurgico` (sin typo). Árbol completo en el
ROADMAP, sección "Estructura del Proyecto Django".

---

## Repositorio

- **URL:** https://github.com/Alejandro-Valen/Registro_Post_Quirurgico
- **`Desarrollo`:** rama de integración. Nadie trabaja directo aquí.
- **`produccion`:** la que miran los servicios de Railway. Solo recibe merges
  desde `Desarrollo` (`docs/railway_deploy.md` §4.1).
- **Borrar la rama al mergear:** `gh pr merge <n> --merge --delete-branch`. El
  borrado automático de GitHub solo lo puede activar el dueño de la cuenta.
- **Cada PR se verifica solo:** `.github/workflows/ci.yml` corre **diez
  comprobaciones** en cada PR y cada push a `Desarrollo` y `produccion`: la
  suite, `check`, `makemigrations --check`, `check --deploy --fail-level
  WARNING`, la higiene del diff, `gitleaks` sobre la historia completa, que no
  haya un `.env` rastreado, `ruff`, `pip-audit` y el **barrido de veracidad**
  (`proceso/verificaciones/2026-09-09_barrido_veracidad.py`), que comprueba que
  lo que la documentación afirma sea cierto —rutas, conteo de pruebas, commits
  citados y **que los umbrales de `docs/reglas_clinicas.md` sean las constantes
  de `alert_engine.py`**—.
- **Ficha D16:** ninguna guardia entra ni permanece en la CI sin haberse visto
  fallar al menos una vez. Sin `--fail-level WARNING`, `check --deploy` nunca
  pudo fallar.
- **Los checks se ven pero no bloquean.** En un repositorio privado de cuenta
  personal sin GitHub Pro, la protección de rama no existe **para nadie**. Las
  salidas son GitHub Pro, hacer el repositorio público o la compuerta humana; hoy
  rige la última: **mirar las diez antes de mergear**.

---

## Cómo se trabaja

**Método de los loops:** decidir → documentar → **prueba en rojo** →
implementar → **verificar en las dos direcciones** (revertir el arreglo y ver
caer la prueba) → verificación del Arquitecto. Nació de una lección cara: *una
prueba en verde no prueba nada si no se verifica por qué está verde.*

**Ningún umbral clínico entra ni se mueve sin su par de pruebas de frontera**
—el valor que dispara y el inmediatamente inferior—, y el par no vale hasta que
se ha visto caer (`proceso/verificaciones/2026-09-08_verificacion_umbrales.py`).

**Carriles en paralelo**, solo si ningún par toca los mismos archivos y como
máximo tres. Cada carril en su worktree, con su rama, su PR y su base de pruebas
(`$env:DB_NAME='registro_carril_x'`: con un nombre compartido, una corrida con
`--noinput` borra la base de la otra). Solo un carril crea migraciones a la vez.
Commit por hallazgo, no al final. **Lo clínico, el bot y lo legal no van en
carriles.**

**Producción: NO HAY desde el 07/08/2026** (venció la prueba de Railway). Mergear
a `produccion` no despliega nada y nada se verifica contra producción: la red de
seguridad es la suite local más la CI. `docs/railway_deploy.md` es el guion para
reconstruir el despliegue. **No proponer trabajo que hoy no se puede terminar**
(despliegue, Twilio saliente, piloto).

**Norma de zona horaria:** toda "fecha de hoy" usa `timezone.localdate()`, nunca
`.date()` sobre un datetime aware ni `timezone.now().date()`: con `USE_TZ=True`
esos dos devuelven la fecha en UTC y rompen las reglas de días calendario de
noche.

---

## Estado actual

> **Esta sección se REEMPLAZA en cada cierre, no se le añade.** Lo que deja de
> ser presente pasa a `docs/resumen_sprints.md` (qué se entregó) o al cuaderno de
> trabajo (cómo fue). Es lo que la tenía en 700 líneas.

**Sprints 0 a 6 completos y mergeados**, con los loops A-E, D1-D27 implementadas
y la auditoría de seis frentes del 07/09/2026 en curso de cierre. Historia
completa, con PR y merge de cada etapa: `docs/resumen_sprints.md`.

**Auditoría del 07/09/2026 (101 hallazgos):** se cierran por PR; el estado de
cada uno lo lleva el cuaderno de trabajo. **Lo clínico abierto no lo decide una
sesión técnica** (ver abajo).

**Pendiente técnico, en orden:**

1. **REPO-20** (la CI cancela la corrida que sigue a un merge): listo en la rama
   local `ci-no-cancela-tras-merge`. GitHub rechaza el push porque el token de
   `gh` no tiene el permiso `workflow`: `gh auth refresh -h github.com -s
   workflow`, después push y PR.
2. **Auditoría de la calidad de las pruebas** y la decisión de **protección de
   rama** (ver "Repositorio").

**Lo que necesita a alguien, no a una sesión técnica:**

- **El médico:** BE-08 y BE-09 (dos ramas de sobre-alerta, fijadas por pruebas de
  caracterización; ficha D10, y `docs/reglas_clinicas.md`) y la redacción de las
  respuestas de la FAQ (D4).
- **León:** BE-03 (cron tardío crea y cierra el turno de la mañana en la misma
  corrida: cambia qué cuenta como turno no respondido, D1); caducidad de sesión
  por inactividad (hoy 8 h desde el ingreso); SEC-13 (requiere Docker Desktop);
  rotar las credenciales del `.env` de desarrollo (SEC-09); lo legal (SEC-07,
  SEC-08, DB-11).
- **Alejandro:** borrado automático de ramas en GitHub; datos de un tercero en la
  historia de git (REPO-01, D17).
- **Los datos de P-12** para la política de datos y la landing (SEC-03, REPO-21):
  `/politica-datos/` está publicada como **BORRADOR** con `[corchetes]`; no se
  inventó ninguno.
- **A la reunión** con Alejandro, el médico y el profesional de desarrollo: el
  canal del paciente, si el repositorio se hace público, y avisarle al médico de
  sus datos en la historia.

**Antes de un piloto real** (detalle en el ROADMAP, "Requisitos para un PILOTO
REAL"): datos del médico en la landing (P-12) y `MOSTRAR_AVISO_BOCETO = False`;
decidir la cuenta del médico definitivo (D15 ya permite contraseña propia;
grupos y permisos se siguen reescribiendo a propósito, ver
`docs/trampas_conocidas.md`); Railway de pago; WhatsApp Business API; dominio de
Resend; monitoreo externo; los `[corchetes]` del consentimiento; validación
médica de las respuestas del bot (D4); `cron-operativo` como servicio separado;
y documentar la versión de PostgreSQL de Railway (la CI usa `postgres:18`).

**Diferido a propósito** (Twilio saliente, monitoreo externo de los cron, RAG,
OpenMed): ROADMAP, con las decisiones de producto P-1 a P-15.

**Evidencia clínica:** la auditoría de literatura está hecha
(`docs/auditoria_literatura/`), pero `knowledge_base.md` sigue como placeholder.
**Nunca inventar contenido clínico** ni cambiar una regla del `alert_engine` sin
decisión explícita del Arquitecto en sesión.

---

## Roles del equipo

- **León (`@arboledaLeon`):** **programador y desarrollador principal.** Escribe
  el código, define la lógica clínica, valida las reglas médicas y aprueba cada
  decisión de diseño. Trabaja con Claude Code. Cuando la documentación dice "el
  Arquitecto", es él.
- **Alejandro (`@Alejandro-Valen`):** se consulta para las decisiones de
  **funcionamiento, arquitectura, infraestructura y la gestión con el médico**.
  Trabaja con Codex CLI.

En el README los dos aparecen con el mismo rol, y es deliberado: de cara afuera
no se reparten méritos. Esta sección describe el reparto real del trabajo.

---

## Cierre de sesión

Sin que el Arquitecto lo pida, al terminar cada sesión:

1. **La narrativa va al cuaderno de trabajo**, fuera del repositorio. Aquí no se
   escribe bitácora ni se recrea `BITACORA.md`.
2. **El estado se reemplaza** en "Estado actual" de este archivo, y se marcan con
   `[x]` en el ROADMAP las tareas completadas.
3. **El documento dueño de lo que se tocó, en el mismo lote de commits que el
   código.** Esto **nunca** se difiere:

   | Si tocaste... | Actualiza en el mismo commit |
   |---|---|
   | `alert_engine.py` — reglas, umbrales, severidades | `docs/reglas_clinicas.md` |
   | `models.py` — campos, choices, constraints, migraciones | `docs/modelos_datos.md` |
   | `bot.py` — máquina de estados, preguntas, respuestas | `docs/bot_whatsapp.md` |
   | Despliegue, cron, variables de entorno | `docs/railway_deploy.md` · `docs/cron_setup.md` |

   Y no se copia a otro documento: cada hecho tiene un solo dueño.
4. **Commit y push** a la rama activa, con commits de código y de `docs:`
   separados. Nunca dejar trabajo funcional sin commitear.

Si el Arquitecto dice "no hagas commit todavía" o "espera para documentar", se
respeta.

---

## Convenciones

- Idioma del código: **español** (variables, comentarios, commits).
- Commits: `feat:`, `fix:`, `docs:` + descripción en español.
- Una rama por loop o PR; `Desarrollo` solo recibe merges.
- El `.env` **nunca** se sube.
- Ningún código clínico entra a `Desarrollo` sin aprobación explícita del
  Arquitecto, incluido el visto bueno de cada decisión de diseño **antes** de
  escribir en disco.

---

## Comandos esenciales

```bash
# Los comandos manage.py se corren desde la carpeta que contiene manage.py,
# un nivel por debajo de la raíz del repositorio (REPO-14):
cd Registro_Post_Quirurgico          # desde la raíz del repositorio

python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test --noinput        # suite completa (~7 min en Windows)
python manage.py runserver             # http://127.0.0.1:8000/admin/

# Un solo tema, en segundos:
python manage.py test signos_sintomas.tests.test_alert_engine --noinput
```

`--noinput` evita quedarse esperando el prompt de borrado si una corrida anterior
murió y dejó la base de pruebas a medio crear.

**El intérprete es el de `.venv/`, no el `python` del PATH.** En la máquina del
Arquitecto el global es un 3.10 sin Django ni `ruff`, y un comando lanzado sin
activar el entorno falla con `No module named ...` y parece un problema del
proyecto. Activarlo, o invocar `.venv/Scripts/python.exe` por ruta.

**Antes de abrir un PR, la suite completa.** Correr un solo tema es para iterar.
