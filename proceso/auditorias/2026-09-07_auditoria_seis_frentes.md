# Auditoría de seis frentes — informe completo

> **Qué es este documento.** Los **101 hallazgos** que reportaron seis auditorías
> independientes el 07/09/2026, itemizados y con su estado actual. Existe para
> que los hallazgos de severidad MEDIA y BAJA no se pierdan: los 15 ALTA están
> nombrados en `CLAUDE.md`, `SECURITY.md` y el guion de la sesión siguiente, pero
> los otros 86 solo vivían en el informe.
>
> **Lo que este documento NO es.** No es el informe de los agentes copiado. Es la
> síntesis de los seis, con el estado de cada hallazgo comprobado contra el
> código el 07/09/2026.

**Fecha:** 07/09/2026 · **Rama:** `Desarrollo` · **HEAD auditado:** `7d6a834`
**Auditores:** seis agentes en paralelo, ciegos entre sí, **sin permiso de editar**
**Síntesis y verificación:** Claude Code, con León

---

## Advertencia de método, antes de usar este documento

**Ninguno de los seis agentes pudo ejecutar código.** No había entorno virtual y
se les prohibió correr `manage.py`. Sus hallazgos están **trazados línea a
línea** contra el código, con archivo y línea — pero **trazar no es reproducir**.

De los 101, **solo cuatro se reprodujeron ejecutando**, y están marcados como
tales. Los demás son hipótesis fundadas, no hechos comprobados.

> **Un informe de otro agente es una hipótesis, no un hecho.** Es la regla que ya
> rige aquí desde la auditoría del 27/07/2026, y esta ronda volvió a darle la
> razón: al reproducir se encontró que la cédula estaba también en el `tests.py`
> viejo, algo que ningún agente vio porque solo miraron `docs/`.

**Antes de actuar sobre cualquier hallazgo de este documento, reprodúcelo.**

---

## Veredicto

**Cinco de los seis frentes emitieron BLOQUEADO por su cuenta.** Ninguno bloquea
el trabajo en `Desarrollo`: bloquean **el piloto con pacientes reales**, que ya
estaba fuera de alcance por otras razones.

| Frente | ALTA | Total |
|---|---:|---:|
| Seguridad | 3 | 15 |
| Datos y modelos | 2 | 12 |
| Backend clínico | 1 | 13 |
| Frontend y panel | 3 | 28 |
| Calidad de las pruebas | 3 | 12 |
| Repositorio | 3 | 21 |
| **Total** | **15** | **101** |

---

## El patrón que explica los 101

Los hallazgos no estaban repartidos al azar. Casi todos sobrevivieron por la
misma razón, encontrada de forma independiente en **seis** sitios:

> **Las guardias automáticas de este proyecto estaban escritas de forma que no
> podían fallar.**

| Guardia | Por qué no protegía |
|---|---|
| `check --deploy` | Sin `--fail-level WARNING` salía 0 aunque reportara cinco fallos de seguridad |
| `gitleaks` | Excluía `docs/auditoria_literatura/`, la única carpeta con datos personales |
| Las 344 pruebas | `fecaloide` no aparece en ninguna |
| 25 restricciones de BD | 19 nunca se han visto fallar |
| `pip-audit` | Citado como garantía en seis documentos. No estaba en ninguna parte |
| Validadores de rango | Cero en todo el repositorio |

De aquí salieron las fichas **D16**, **D17** y **D18**.

---

## Los cuatro reproducidos ejecutando código

Estos cuatro **no son hipótesis**. Se comprobaron corriendo código el 07/09/2026.

### 1 · `check --deploy` no podía ponerse en rojo (SEC-01)

```
$ python manage.py check --deploy      # configuración con 5 fallos
?: (security.W004) ... SECURE_HSTS_SECONDS ...
?: (security.W008) ... SECURE_SSL_REDIRECT ...
?: (security.W012) ... SESSION_COOKIE_SECURE ...
?: (security.W016) ... CSRF_COOKIE_SECURE ...
?: (security.W018) You should not have DEBUG set to True in deployment.
System check identified 5 issues (0 silenced).
>>> EXIT CODE: 0

$ python manage.py check --deploy --fail-level WARNING
>>> EXIT CODE: 1
```

Todos los checks de despliegue de Django son de nivel WARNING y `--fail-level`
vale ERROR por defecto. **Desde que existe la CI (31/07/2026) esa comprobación
nunca pudo fallar.** ✅ **Corregido** (PR #18).

### 2 · El sabotaje del drenaje fecaloide (TEST-01)

```diff
- DRENAJES_ALTA  = ('purulento', 'fecaloide')
+ DRENAJES_ALTA  = ('purulento',)
```

```
Ran 344 tests in 283.581s
OK
```

**Ni una prueba cayó.** Con esa línea así, un paciente puede reportar contenido
intestinal saliendo por el drenaje —una fuga anastomótica franca— y no se genera
ninguna alerta. Código restaurado y árbol comprobado limpio. ⬜ **Abierto**: es
el objetivo del loop de umbrales.

### 3 · El parser de temperatura trunca en silencio (DB-02)

```
paciente escribe "37.9"  →  guarda 37.9  →  SEPSIS / ALTA
paciente escribe "379"   →  guarda 37.0  →  SIN ALERTA
paciente escribe "37 9"  →  guarda 37.0  →  SIN ALERTA
paciente escribe "375"   →  guarda 37.0  →  SIN ALERTA
```

El regex `\d{2}(?:[.,]\d)?` de `bot.py:585` toma los dos primeros dígitos. Un
paciente con 37,9 °C que teclea sin separador —lo más natural desde un celular—
queda registrado en 37,0, no dispara ninguna regla, y **recibe el mensaje de
cierre normal**. Ni él ni el médico pueden notarlo: 37,0 es un valor válido.
⬜ **Abierto**.

### 4 · Datos personales de un tercero en el repositorio (REPO-01)

Nombre completo, cédula y afiliaciones del médico proponente en
`docs/auditoria_literatura/`, entrados en junio de 2026 al cargar un documento
que él mismo proporcionó. **La carpeta estaba excluida del escaneo de gitleaks**,
así que la guardia nunca la iba a mirar.

Al añadir la regla de cédula aparecieron **15 fugas, no una**: también estaba en
el `signos_sintomas/tests.py` que ya no existe. ✅ **Árbol limpio** (PR #18) ·
⬜ **La historia de git sigue teniéndolo** — ver `.gitleaksignore` y la ficha D17.

---

## Los 15 hallazgos de severidad ALTA

| ID | Hallazgo | Estado |
|---|---|---|
| **SEC-01** | `check --deploy` sin `--fail-level`: la CI no podía fallar | ✅ Corregido, PR #18 |
| **SEC-02** | `django-axes` bloquea por IP; detrás del edge de Railway esa IP es una sola → **5 intentos fallidos anónimos dejan al médico sin panel una hora** | ⬜ Abierto |
| **SEC-03** | El formulario público guarda nombre, teléfono y texto libre de salud **sin autorización de tratamiento** (Ley 1581/2012, art. 6) | ⬜ Abierto · detallado en `SECURITY.md` |
| **DB-01** | **Cero validadores de rango** en todo el proyecto. `episodios_nauseas` no tiene techo ni en el bot: `"si, 99999"` → `DataError` → webhook 500 → el paciente no recibe respuesta | ⬜ Abierto |
| **DB-02** | El parser de temperatura trunca: `379` → 37,0, sin alerta | ⬜ Abierto |
| **BE-01** | El bot le dice "no tienes reporte pendiente" al paciente que empezó por la mañana y vuelve por la tarde, y le pierde el turno | ⬜ Abierto |
| **TEST-01** | `fecaloide` sin ninguna prueba (sabotaje ejecutado) | ⬜ Abierto |
| **TEST-02** | El bot nunca prueba las opciones "4" (purulento) y "5" (fecaloide) del menú de drenaje — las dos que significan urgencia | ⬜ Abierto |
| **TEST-03** | Cuatro umbrales clínicos se pueden mover sin que caiga una prueba | ⬜ Abierto |
| **UX-P01** | El tablero imprime *"Sin alertas pendientes. Todo bajo control"* mientras su propio indicador muestra una alerta ALTA sin resolver (ocurre siempre que la ALTA es de tipo SILENCIO) | ⬜ Abierto |
| **UX-B01** | **No hay palabra de auxilio.** *"estoy sangrando mucho"* en la pregunta 7 se guarda como distensión abdominal y el bot pasa a la siguiente pregunta | ⬜ Abierto |
| **UX-B02** | El bot promete *"Te escribiré cuando sea la hora"*, pero el envío saliente es un stub: nadie le va a escribir nunca | ⬜ Abierto |
| **REPO-01** | Cédula y nombre de un tercero en el repositorio, en la carpeta que gitleaks excluía | ✅ Árbol · ⬜ Historia |
| **REPO-02** | El proyecto no se podía instalar: cero instrucciones en 44 documentos | ✅ Corregido, PR #19 |
| **REPO-03** | Sin `README.md`, `LICENSE`, `CONTRIBUTING`, `SECURITY` | ✅ Corregido, PR #19 |

---

## Seguridad — los 12 restantes

| ID | Hallazgo | Estado |
|---|---|---|
| SEC-04 | Sin `DJANGO_SETTINGS_MODULE` la app **arranca igual** con la configuración base y pierde HSTS, redirect HTTPS, cookies seguras y CSP. El `Dockerfile` la fija; `nixpacks.toml` no | ⬜ |
| SEC-05 | `crear_admin` **reescribe la contraseña del superusuario en cada arranque** y puede promover a superusuario una cuenta existente. Es el defecto que D15 corrigió para el médico y aquí quedó sin corregir. Verificado 07/09: `set_password` sigue sin condición | ⬜ |
| SEC-06 | Sin vigilancia de dependencias; Django 6.0.7 con CVE-2026-15830 (no explotable: `contrib.gis` no está instalado) | ✅ PR #18 |
| SEC-07 | **Sin registro de accesos de lectura.** Django registra escrituras del Admin, no consultas: no se puede saber qué médico consultó qué ficha | ⬜ |
| SEC-08 | Datos sensibles sin cifrado de aplicación, retención indefinida y sin procedimiento de supresión | ⬜ |
| SEC-09 | Secretos de producción en el `.env` de desarrollo; la documentación indica reutilizar el Auth Token **primario** de Twilio, que es la única cerradura del webhook | ⬜ |
| SEC-10 | `cron_runner` vuelca el mensaje completo de la excepción, contra la regla del propio proyecto. Verificado 07/09: sigue así | ⬜ |
| SEC-11 | Un médico puede dejar un paciente **inactivo sin responsable**, borrando la atribución clínica | ⬜ |
| SEC-12 | Oráculo de unicidad: un médico puede averiguar si una cédula está en el sistema aunque el paciente sea de otro | ⬜ |
| SEC-13 | El contenedor corre como **root** y no declara `HEALTHCHECK` | ⬜ |
| SEC-14 | `requirements.txt` era un `pip freeze` de 214 líneas del entorno personal | ✅ PR #19 |
| SEC-15 | Sesión del panel de **14 días**, sin expiración por inactividad | ⬜ |

---

## Datos y modelos — los 10 restantes

| ID | Hallazgo | Estado |
|---|---|---|
| DB-03 | `Alerta.registro_origen` **no contiene lo que su nombre dice**: guarda el último registro que tocó la alerta, no el que la originó. La gráfica marca un punto rojo por alerta abierta en vez de uno por detección | ⬜ |
| DB-04 | **19 de 25 restricciones de base nunca se han visto fallar.** Un `RemoveConstraint` futuro las borra y la suite sigue verde | ⬜ |
| DB-05 | **N+1 en cuatro listados del Admin.** `PacienteAdmin` no aplica ningún `select_related`: ~101 consultas por página; `AlertaAdmin` ~201 | ⬜ |
| DB-06 | `docs/modelos_datos.md` desincronizado: faltan `DeteccionAlerta`, `NotificacionAlerta` y 4 campos de `RegistroDiario` | ⬜ |
| DB-07 | **Revocar el consentimiento no detiene la generación de datos.** Se le siguen creando turnos, no puede responderlos, y a los dos días genera `SILENCIO/ALTA` con correo al médico | ⬜ |
| DB-08 | `.date()` sobre datetime *aware* en los dos seeds — el patrón que la norma del proyecto prohíbe. Hoy da el resultado correcto por casualidad | ⬜ |
| DB-09 | `CheckInProgramado` sin índice por `estado`, `hora_programada` ni `fecha_dia`. La tabla **nunca se purga** y crece linealmente | ⬜ |
| DB-10 | Dos migraciones de datos con `RunPython.noop` como reverse: un `migrate` hacia atrás **reporta éxito sin deshacer nada** | ⬜ |
| DB-11 | **No hay procedimiento de supresión.** El botón "Eliminar" del Admin siempre termina en `ProtectedError` | ⬜ |
| DB-12 | Rama de abandono del bot que hace una pregunta y luego ignora la respuesta | ⬜ |

---

## Backend clínico — los 12 restantes

**Fidelidad de las reglas: 24 de 26 se implementan exactamente como están
escritas.** Las dos desviaciones son de sobre-alerta, no de falso negativo.

| ID | Hallazgo | Estado |
|---|---|---|
| BE-02 | Umbrales clínicos (37,9 °C · 101 · 110 lpm) **duplicados a mano** en el panel del médico, fuera de la fuente única. El día que cambien, el médico verá la línea vieja | ⬜ |
| BE-03 | Un arranque tardío de `cron_matutino` **crea el turno de la mañana y lo cierra en la misma corrida** → SILENCIO espurio. La prueba que cubre esa secuencia **anula la condición** | ⬜ |
| BE-04 | Una palabra clave de la FAQ impide que arranque el check-in: *"hoy tengo mucho dolor"* devuelve la respuesta enlatada y el cuestionario no empieza | ⬜ |
| BE-05 | Los mensajes prometen un contacto que ningún código realiza (amplifica BE-01 y BE-04) | ⬜ |
| BE-06 | La mitad clínica de D8 —que un día sin datos **corta** el conteo— no tiene ninguna prueba | ⬜ |
| BE-07 | Sin salida para el paciente que no puede medir: temperatura, dolor, gases, hinchazón y líquidos no admiten "saltar". Sin termómetro, el turno se pierde | ⬜ |
| BE-08 | Regla 5b escala **dos niveles** cuando la tabla no da alerta; el promedio se calcula por registro, no por día | ⬜ |
| BE-09 | Regla 6 cuenta como "no toleró" un día cuyo dato **no se capturó** | ⬜ |
| BE-10 | `.date()` sobre datetime aware en los seeds (mismo que DB-08) | ⬜ |
| BE-11 | Rama muerta en la máquina de estados del bot | ⬜ |
| BE-12 | La docstring del stub anuncia un sprint ya cerrado | ⬜ |
| BE-13 | Un registro atascado en `PROCESANDO` no lo recoge ningún comando | ⬜ |

---

## Frontend y panel — los 25 restantes

**Panel del médico**

| ID | Hallazgo | Estado |
|---|---|---|
| UX-P02 | El changelist ordena por fecha, no por severidad; ordenar por la columna Severidad da **ALTA, BAJA, MEDIA** (alfabético) | ⬜ |
| UX-P03 | El listado muestra `fecha_alerta` y no `fecha_ultima_deteccion`: una alerta redetectada hoy se hunde al fondo | ⬜ |
| UX-P04 | Si Chart.js no carga, el médico ve **tres lienzos en blanco sin ningún aviso** — idéntico a "no hay datos". El estado *error* no está resuelto en ninguna pantalla | ⬜ |
| UX-P05 | La escala de temperatura está fijada a 35–40 °C, pero el bot acepta hasta 45: **el valor más grave es el único que la gráfica no dibuja** | ⬜ |
| UX-P06 | Contrastes por debajo de WCAG: píldora MEDIA **2,90:1**, texto atenuado 3,57:1, nota de la gráfica 2,54:1 | ⬜ |
| UX-P07 | La tabla de historial tiene 9 columnas sin contenedor desplazable: desborda en móvil | ⬜ |
| UX-P08 | La ficha no define `fieldsets`: para ver la evolución clínica hay que pasar por encima de los campos administrativos | ⬜ |
| UX-P09 | Chart.js (204 KB) se descarga también en el listado de pacientes, donde no hay gráficas | ⬜ |
| UX-P10 | `.pt-alerta-sistema` no existe en ningún CSS; el estilo va en línea y duplicado | ⬜ |
| UX-P11 | El selector de días pisa el query string y pierde el retorno al filtro | ⬜ |

**Bot / paciente**

| ID | Hallazgo | Estado |
|---|---|---|
| UX-B03 | La pregunta 6 mete dos cosas en un mensaje: *"si, no tuve nauseas: 0"* se registra como **sin gases**, que alimenta la regla de íleo | ⬜ |
| UX-B04 | **Sin termómetro no se puede avanzar**, y "saltar" no funciona en esa pregunta. Un paciente sin dolor tampoco puede responder: el rango es 1-10 y "0" se rechaza | ⬜ |
| UX-B05 | El parser de temperatura trunca y **el bot nunca devuelve lo que entendió** (mismo que DB-02) | ⬜ |
| UX-B06 | El paciente sin drenaje ve saltar del 3 al 6 sin explicación, y el cuestionario de "10 preguntas" nunca llega a 10 | ⬜ |
| UX-B07 | Conversación abandonada sin check-in hoy: el bot hace una pregunta y luego ignora la respuesta | ⬜ |
| UX-B08 | La FAQ contesta y **no encadena** el inicio del reporte | ⬜ |
| UX-B09 | Las preguntas 1-6 tutean y las 7-10 tratan de usted, contra la regla del documento dueño | ⬜ |
| UX-B10 | Los dos mensajes que mandan al paciente a urgencias están **sin tildes**; los otros veinte sí las llevan | ⬜ |
| UX-B11 | *"parece que ayer no pudimos terminar"* puede haber sido hace una semana | ⬜ |

**Landing pública** — el estado de boceto es decisión documentada (P-12), no hallazgo.

| ID | Hallazgo | Estado |
|---|---|---|
| UX-L01 | En móvil desaparecen los cuatro enlaces del menú y **el único visible es "Acceso médico"**, que lleva al login del Admin | ⬜ |
| UX-L02 | El formulario con espacios en blanco no crea nada y **no muestra ni éxito ni error** | ⬜ |
| UX-L03 | Si salta el rate limit, el usuario pierde todo lo que escribió | ⬜ |
| UX-L04 | El mensaje se recorta a 2000 caracteres **en silencio** y responde "enviado correctamente" | ⬜ |
| UX-L05 | Los avisos del formulario sin `role="alert"`: un lector de pantalla no anuncia el resultado | ⬜ |
| UX-L06 | El bucle de animación llama a `getComputedStyle` en cada fotograma | ⬜ |

---

## Calidad de las pruebas — los 9 restantes

**Cifras mecánicas, y en esto la suite está sana:** 0 aserciones tautológicas,
0 `skip`, 0 `sleep`, una sola importación de constante de producción usada como
valor esperado.

**El problema es la ausencia sistemática de la frontera inferior.** De las 30
severidades del sistema, 24 están fijadas por alguna prueba; **solo 15 tienen el
caso frontera** — el valor justo por debajo, que es el que ancla el umbral.
Distribución que lo demuestra: `dolor_eva` nunca vale 7 en las 344 pruebas;
`episodios_nauseas` nunca vale 3; `fecaloide` no aparece.

Las dos zonas con frontera completa —la Regla 8 (FC) y la escalera SILENCIO— son
justo las dos que pasaron por una auditoría previa.

| ID | Hallazgo | Estado |
|---|---|---|
| TEST-04 | La decisión D8 (un día sin datos corta el conteo) **no tiene guardián** | ⬜ |
| TEST-05 | La ventana de dolor POD 3-5 y las fronteras entre ventanas no se prueban | ⬜ |
| TEST-06 | El backoff de reintentos del correo ALTA no está probado: cualquier valor positivo satisface la aserción | ⬜ |
| TEST-07 | Umbrales operativos sin frontera: gracia del cron, ingreso tardío, aviso del Admin | ⬜ |
| TEST-08 | Cinco pruebas sin ninguna aserción; dos de ellas no protegen nada | ⬜ |
| TEST-09 | El badge de severidad se verifica por la subcadena `border-radius`: no comprueba color ni severidad | ⬜ |
| TEST-10 | Una prueba de rate limit importa la constante de producción: si el límite cambia, la prueba cambia con él | ⬜ |
| TEST-11 | Escenarios multidía fuera del ancla de reloj (PLAUSIBLE, no confirmado) | ⬜ |
| TEST-12 | La prueba de "no re-notificar en recurrencia" pasa por un motivo colateral | ⬜ |

**Los 18 sabotajes propuestos**, con la predicción de si la suite los atraparía,
están en el guion `proceso/instrucciones/2026-09-07_instruccion_umbrales.md`.
**14 de 18 pasarían.**

---

## Repositorio — los 18 restantes

| ID | Hallazgo | Estado |
|---|---|---|
| REPO-04 | `docs/README.md` con cuatro afirmaciones falsas | ✅ PR #19 |
| REPO-05 | El ROADMAP documenta `medico_responsable` con `SET_NULL`; el código usa `PROTECT` desde julio. **Verificado 07/09: sigue diciendo `SET_NULL` en la línea 168** | ⬜ |
| REPO-06 | `cron_setup.md` y `transferencia_cuentas.md` afirman infraestructura desplegada; no hay producción desde el 07/08 | ⬜ |
| REPO-07 | `trampas_conocidas.md` describe los cron en presente y no menciona la caída | ⬜ |
| REPO-08 | El árbol de archivos del ROADMAP lista un archivo que no existe y omite 13 de los 15 documentos de `docs/` | ⬜ |
| REPO-09 | El ROADMAP duplica las tablas de modelos que `modelos_datos.md` posee (REPO-05 es la divergencia que la regla predecía) | ⬜ |
| REPO-10 | La CI sin linter, sin auditoría de dependencias, sin cobertura | ✅ PR #18 |
| REPO-11 | `.github/` sin plantillas, `CODEOWNERS` ni `dependabot` | ✅ PR #19 |
| REPO-12 | `.gitignore` no cubría `entorno_registro/` sin punto, `.venv/`, `.claude/` ni las cachés | ✅ PR #18 |
| REPO-13 | `requirements-dev.txt` citaba `tests.py`, borrado el 10/08 | ✅ PR #18 |
| REPO-14 | `CLAUDE.md` da una ruta de `cd` ambigua según desde dónde se ejecute | ⬜ |
| REPO-15 | `resumen_sprints.md` decía que el correo se resolvió con SMTP + Gmail; producción usó Resend por HTTPS | ✅ Corregido |
| REPO-16 | Cuatro sitios decían "fichas D1-D10" | ✅ Corregido |
| REPO-17 | `inicio_entornoR.bat` activaba un entorno que no existía | ✅ PR #18 |
| REPO-18 | Sin `docker-compose.yml` y sin una sola captura de pantalla | Capturas ✅ PR #27 · `docker-compose` ⬜ |
| REPO-19 | Ruta absoluta de la máquina del Arquitecto en el ROADMAP | ⬜ |
| REPO-20 | `concurrency: cancel-in-progress` puede cancelar la corrida post-merge, que sin protección de rama es la única señal (NO reproducido) | ⬜ |
| REPO-21 | La landing muestra `[Nombre y apellido]` y `[Institución donde ejerce]` — decisión documentada P-12, no hallazgo nuevo | ⬜ |

---

## Lo que los auditores destacaron como bien hecho

No es cortesía: sirve para no "arreglar" lo que ya está bien.

- **El aislamiento por médico resiste un intento activo de romperlo.** Los seis
  vectores clásicos están cerrados, y no hay `autocomplete_fields`,
  `raw_id_fields` ni `list_editable` — las tres puertas por donde suele
  escaparse.
- **El webhook está bien cerrado**: firma con fallo explícito si falta el token,
  idempotencia por `MessageSid` con reclamación condicional, bloqueo de fila. Y
  sus pruebas calculan una **firma real**.
- **El correo de alerta no lleva PHI**: solo el número de alerta y un enlace.
- **24 de 26 reglas clínicas** se implementan exactamente como están escritas.
- **La concurrencia está probada con hilos reales**, no con mocks.
- **`models.py` sincronizado con las 28 migraciones**, comparado por AST.
- **El índice funcional de la migración 0010** coincide exactamente con la
  expresión que Django genera para `fecha_registro__date` con `USE_TZ=True`.
- **`.env.example`** lleva la trampa que costó horas escrita al lado de cada
  variable que la tiene.
- **Un solo commit mal escrito en 324.**
- **`proceso/verificaciones/*.py`**: scripts que intentan **romper** el
  invariante en vez de repetir la suite.

---

## Lo que esta auditoría NO verificó

- **Nada contra producción.** Railway venció el 07/08/2026.
- **97 de los 101 hallazgos no están ejecutados**, solo trazados.
- **La suite no se corrió** durante las auditorías; las cifras que citan salen de
  leer el código de prueba.
- **No se revisó la calidad de las pruebas una por una**, solo por patrones.
- **Ningún agente leyó `.env`**, por instrucción.

---

## Qué hacer con este documento

1. **Reproducir antes de actuar.** Un hallazgo trazado es una hipótesis.
2. **El orden de trabajo no es la severidad**, es el del plan acordado: primero
   anclar los umbrales (que es lo que da red), después los bugs del paciente.
3. **Actualizar el estado de cada fila** cuando se corrija, en el mismo commit.
   Un informe con estados viejos deja de ser evidencia y pasa a ser ruido.
