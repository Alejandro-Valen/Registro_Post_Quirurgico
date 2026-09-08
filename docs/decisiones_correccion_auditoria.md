# Decisiones de corrección — Auditoría pre-merge Sprint 5

> **Qué es este documento.** El registro de las decisiones tomadas por el
> Arquitecto (León) para corregir los hallazgos de la auditoría independiente
> del 22/07/2026, junto con el razonamiento de cada una.
>
> **Para qué sirve.** Para responder "¿por qué se hizo así?" sin depender de
> la memoria de nadie ni de una conversación. Se consulta **por tema**, no por
> fecha — la cronología vive en `proceso/BITACORA.md`.
>
> **A quién le sirve.** Al Arquitecto, al médico (decisión D4), a Codex, y a
> cualquier agente IA que retome el proyecto.

**Fecha de las decisiones:** 22/07/2026
**Rama:** `sprint-5-produccion` · **Punto de partida:** `fbf62a8`
**Auditoría de origen:** ver `proceso/auditorias/2026-07-22_instruccion_loops_1_6.md` (instrucción) y
la entrada de `proceso/BITACORA.md` del 22/07/2026 (informe y hallazgos).

---

## Índice

| ID | Decisión | Hallazgo | Loop | Estado |
|----|----------|----------|------|--------|
| [D1](#d1) | Escalera de severidad de las alertas SILENCIO | 1 | A | Aceptada |
| [D2](#d2) | Comportamiento del rate limit ante caída de Redis | 5 | B | Aceptada |
| [D3](#d3) | Registrar quién resuelve cada alerta | 4 | B | Aceptada |
| [D4](#d4) | Umbral de fiebre comunicado al paciente | 12 | A | Aceptada — **pendiente de validación médica** |
| [D5](#d5) | Signos concurrentes de íleo en un mismo check-in | 10 | A | Aceptada |
| [D6](#d6) | Límite de reintentos y estado terminal | 13 | B | Aceptada |
| [D7](#d7) | Registros dados por evaluados en la migración 0020 | 3 | C | Aceptada |
| [D8](#d8) | Días sin datos en las reglas de días consecutivos | *(nuevo)* | C | Aceptada |
| [D9](#d9) | Campo `fecha_ultimo_registro` sin lectores | *(nuevo)* | C | Aceptada |
| [D10](#d10) | Cláusula MEDIA de la regla de hinchazón | *(nuevo)* | C | Aceptada |
| [D11](#d11) | Identidad del paciente en la salida operativa | cierre 1 | D | Aceptada |
| [D12](#d12) | Todo paciente activo tiene un médico responsable | cierre 2 | D | Aceptada |
| [D13](#d13) | La autenticidad del webhook no depende del entorno | cierre 3 | D | Aceptada |
| [D14](#d14) | Aislamiento entre las tareas de un mismo cron | cierre (d) | E | **Implementada** (06/08/2026) |
| [D15](#d15) | Qué reescribe `crear_medico` en cada arranque | revisión PR 8 | — | **Implementada** (12/08/2026) |

Los hallazgos 2, 6, 7, 8, 9, 11 y 14 son correcciones técnicas sin decisión de
producto; no tienen ficha aquí y se ejecutan en los Loops B y C.

**D15 no viene de ninguna de las dos auditorías.** Salió del punto 8 de la
revisión de cierre del PR del Sprint 5 (`proceso/auditorias/2026-07-29_revision_pr_sprint5.md`),
que la primera lectura de ese mismo PR no había visto. No tiene loop asignado:
se decidió en su propia sesión, siguiendo el guion
`proceso/instrucciones/2026-08-10_instruccion_crear_medico.md`.

**D11, D12 y D13 vienen de una auditoría posterior**, la de cierre pre-merge del
27/07/2026 — informe y verificación en
`proceso/auditorias/2026-07-27_informe_cierre_codex.md`. Los "hallazgos
cierre 1-3" de la tabla son los de **ese** informe, no los de la auditoría del
22/07.

**D8, D9 y D10 no vienen de la auditoría.** Salieron de un ejercicio distinto el
22/07/2026: se le pidió a otra sesión que **documentara** el sistema explorando
el código. Explicar algo obliga a entenderlo de otra forma que auditarlo, y
encontró tres cosas que la auditoría no vio. Las tres se verificaron contra el
código antes de aceptarlas.

---

## Estado de avance

> **Se actualiza en CADA cierre de sesión, aunque quede a mitad de un loop.**
> Es lo primero que debe leer quien retome el trabajo.

**Última actualización:** 07/09/2026
**Punto alcanzado:** **D1-D18 IMPLEMENTADAS Y MERGEADAS.**

**Lo último (07/09/2026):** una auditoría de seis frentes en paralelo encontró
101 hallazgos, 15 de severidad ALTA, y sobre todo el patrón que los explica —
**las guardias automáticas del proyecto estaban escritas de forma que no podían
fallar**. De ahí salieron **D16** (toda guardia debe poder ponerse en rojo),
**D17** (datos personales de un tercero en la historia) y **D18** (separar el
producto del cuaderno de trabajo), implementadas en los PR #18 (`5f51831`) y #19
(`591cd7c`). La CI pasó de siete a **nueve comprobaciones**.

**El siguiente trabajo no es una ficha D: es anclar los umbrales clínicos.** Un
sabotaje ejecutado dejó las 344 pruebas en verde con el motor clínico roto.

**Contexto anterior (12/08/2026):** los cinco loops cerrados, D1-D15
implementadas y mergeadas. El Loop E se verificó con un script propio
(`proceso/verificaciones/2026-08-06_verificacion_loop_e.py`) y entró a
`Desarrollo` el 07/08/2026 (PR #10, `4fc690d`). Los Loops A, B, C y D estaban
cerrados y verificados desde el 27/07; el Sprint 5 se mergeó el 29/07 y la CI el
31/07. Suite comprobada de nuevo el 12/08/2026 sobre `c1ec1ca`: **340 tests OK**
en 264 s.

**D15 quedó implementada el mismo 12/08/2026** en la rama
`crear-medico-no-reescribe` (`84b684c` test en rojo, `2e02384` corrección), con
la suite en **344 tests OK** y los dos sabotajes de verificación documentados en
la propia ficha. Con ella, **las quince decisiones están implementadas.**

**Siguiente paso: el PR a `Desarrollo`.** Ojo: los **siete**
checks de la CI **se ven pero no bloquean** (no hay protección de rama, y no es
un trámite de permisos — ver `CLAUDE.md`, sección "Repositorio"), así que
mirarlos antes de mergear sigue siendo manual.

**Rama:** `loop-e-aislar-cron` · **Restauración segura:** `e103c8e`
(`Desarrollo` antes del loop)
**Línea base de la suite:** 337 tests OK antes del Loop E · **340 OK** al
implementarlo
**Guion de la sesión:** `proceso/instrucciones/2026-08-01_instruccion_loop_e.md`
**Informe de la auditoría de cierre:**
`proceso/auditorias/2026-07-27_informe_cierre_codex.md`

### Loop A — Corrección clínica *(bloquea el merge)*

- [x] **A1** `test: reproducir escalera de silencio con el scheduler real` — `a6afb30`
- [x] **A2** `fix: corregir el conteo de racha en alertas de silencio` → D1 — `20ee837`
- [x] **A3** `fix: retirar el umbral clinico del mensaje de fiebre al paciente` → D4 — `0ac7021`
- [x] **A4** `feat: conservar los signos concurrentes de ileo en el detalle` → D5 — `f4892fc`
- [x] **A5** `docs: sincronizar reglas del motor y consulta pendiente al medico` — `5a5b477`
- [x] Cierre: **286 tests OK** · `manage.py check`, `makemigrations --check` y `check --deploy` sin issues · `git diff --check` limpio
- [x] **Verificación de León:** ejecutó él mismo la comprobación contra base de datos desechable — escalera BAJA → MEDIA → MEDIA → ALTA con racha 1→2→3→4, reinicio al responder, detalle de íleo con ambos signos sin duplicar tras tres reevaluaciones, y mensaje de fiebre sin cifras
- [x] Push a `origin/sprint-5-produccion` + entrada de BITACORA

**Aclaración registrada en la verificación:** la racha se reinicia porque el
paciente **responde** (un `COMPLETADO` corta el conteo), no porque el médico
resuelva la alerta — resolver solo permite que nazca una alerta nueva. Efecto
visible: si el médico resuelve y el paciente sigue sin responder, la siguiente
alerta aparece como **×1 pero ALTA**. Es correcto: si resolver reiniciara la
racha, bastaría con cerrar alertas para que el sistema dejara de escalar.

**Resultado de A1 (evidencia del hallazgo):** los cuatro casos fallaron contra el
código anterior — `'BAJA' != 'ALTA'`, `'BAJA' != 'MEDIA'` ×2, y `1 != 5` en
`_calcular_racha`. Tras A2 pasaron los 16 casos del scheduler. La suite completa
quedó en **286 tests OK** (280 originales + 6 nuevos).

**Nota de método:** durante A1 se detectaron dos defectos en las pruebas recién
escritas, no en el código: una dependía de la hora del día en que corriera la
suite, y otra pasaba en verde por el orden de cierre en vez de por la regla que
decía medir. Ambas se corrigieron antes de tocar el código. Es el mismo patrón
que dejó vivo el hallazgo 1 durante seis loops: **un test en verde no prueba
nada si no se verifica por qué está verde.**

### Loop B — Trazabilidad y operación

- [x] **B1** `test: cubrir degradacion de cache y agotamiento de reintentos` — `1207d70` (6 rojos, cada uno por su defecto)
- [x] **B2** `fix: degradar el rate limit sin bloquear al paciente` → D2 (1-4) — `e8acc33`
- [x] **B3** `feat: registrar quien resuelve cada alerta` → D3 + migración 0025 — `e143336`
- [x] **B4** `feat: limitar reintentos y exponer entregas fallidas` → D6 (+ FALLIDA, migración 0026, aviso en tablero) — `e75ba83`
- [x] **B5** `feat: endpoint de salud para monitoreo externo` → D2 (5) — `74da9ee`
- [x] **B6** `fix: acotar el bloqueo de filas durante el envio de correo` → hallazgo 2 — `f8fa437`
- [x] **B7** `docs: operacion, monitoreo y trazabilidad de resolucion` — `4673853`
- [x] Cierre: **299 tests OK** · `makemigrations --check` limpio · migraciones 0025 y 0026 reversibles (ida y vuelta) · `/salud/` responde 200 y 503
- [x] **Verifiqué el Loop B yo mismo:** corrí el subconjunto (**59 tests OK**) y vi el banner de correos `FALLIDA` en el `/admin/` local
- [x] Push a `origin/sprint-5-produccion` (`4673853`) + entrada de BITACORA

**Hallazgo del Loop B (no bloqueante, para el Loop C):** la suite no es
determinista cerca de la medianoche de Bogotá. Forzando el cruce de día a mitad
de corrida (reloj falso monótono desplazado) caen **17 tests** que arman
fixtures de varios días con dos llamadas a `now()` que pueden quedar a lados
distintos de la medianoche. El **motor está bien** (usa `timezone.localdate()` y
`fecha_registro__date`); es fragilidad de las pruebas. Blindaje en C7 (anclar
los fixtures a un único `now()` de referencia, o `freezegun`).

### Loop C — Coherencia e higiene

- [x] **C1** `test: cubrir cabeceras de proxy, estado del motor, filtros y arranque` — `ad7a93d` (9 rojos de 15 casos, cada uno por su defecto)
- [x] **C2** `fix: conservar el estado de error del motor en la ruta del bot` → hallazgo 7 — `5ad976f`
- [x] **C3** `fix: no exponer otras cuentas medicas en los filtros` → hallazgo 8 — `b2eaa17`
- [x] **C4** `fix: condicionar la confianza en cabeceras de proxy` → hallazgo 6 — `ec02ef4`
- [x] **C5** `fix: validar variables de entorno vacias al arrancar` → hallazgo 11 — `7b7454d` (+ `9483913`, ajuste de la prueba de CSP que cargaba producción)
- [x] **C6** D10 en dos pasos: `21b8d79` (caracterización, verde a propósito) y `922e13c` (expresión legible, comportamiento idéntico)
- [x] **C7** `test: blindar contra la medianoche las pruebas de escenarios de varios dias` — `cc84037` (freezegun, solo en `requirements.txt`)
- [x] **C8** Documentación: `c5174c1` (hallazgo 9 + D9), `e7155cb` (D8), `f82a973` (hallazgo 14 + despliegue), `27b1960` (reestructuración documental)
- [x] **C9** D7 — consulta de solo lectura ejecutada por el Arquitecto en Railway el 25/07/2026: **cero registros** con `COMPLETADA` + `intentos = 0`. Nada que revisar, nada que reevaluar. Ficha D7 cerrada
- [x] Cierre: suite (319 OK) · `check` y `check --deploy` sin issues · `makemigrations --check` limpio · `pip-audit` sin vulnerabilidades · verificación del Arquitecto ejecutada (6 bloques en verde)

**Resultado de D7 (25/07/2026).** La consulta sobre la base de producción
devolvió `d7_marcados_0020 = 0` sobre 18 registros totales. La expectativa de la
ficha se confirmó: los demos se limpiaron, los pacientes de prueba de los Loops
5 y 6 se eliminaron transaccionalmente y **nunca ha habido un paciente real en
el sistema**, así que no hay evaluación clínica congelada por la migración. Se
documenta y se cierra sin tocar dato alguno.

Panorama de la base al momento de la consulta: 18 registros, 2 pacientes activos
(ambos demo, `DEMO-0001` y `DEMO-0002`), 10 alertas abiertas y 4 check-ins
pendientes creados esa madrugada por `cron_matutino`.

**Numeración:** el plan original nombraba C1-C6 por hallazgo. Al aplicar el
método, la primera posición la ocupó el commit de pruebas en rojo (como `A1` y
`B1`) y el resto se corrió una posición. El contenido es el mismo.

**Resultado de C1 (evidencia de los hallazgos).** De 15 casos nuevos, **9
fallaron** contra el código anterior y 6 nacieron verdes como guardas
declaradas:

| Hallazgo | Evidencia del rojo |
|---|---|
| 6 — cabeceras de proxy | `USE_X_FORWARDED_HOST` era `True` en **toda** configuración; `TRUST_RAILWAY_PROXY` ni existía en la base |
| 7 — estado del motor | `'PENDIENTE' != 'ERROR'`: el savepoint del bot revertía la constancia del fallo |
| 8 — filtros | `dr_filtro_b` y `super_filtro` aparecían en el HTML del listado de otro médico |
| 11 — variables vacías | `SECRET_KEY=''`, `SECRET_KEY=<placeholder>`, `DB_NAME='   '`, `RESEND_API_KEY=''` y `CSRF_TRUSTED_ORIGINS=''` arrancaban sin error |

**Nota sobre D10.** Sus pruebas **nacen en verde a propósito**: son de
caracterización, retratan el comportamiento actual para que la reescritura no
pueda cambiarlo. Se verificó por dos vías independientes: las cinco pruebas
siguen pasando, y una comparación exhaustiva de la expresión vieja contra la
nueva sobre las **64 combinaciones** de (antier, ayer, hoy) en {sin dato, nada,
algo, mucho} dio **cero diferencias**.

**Nota sobre C7.** El rojo se reprodujo de forma determinista con un arnés
temporal que corrió las clases **reales** bajo un reloj falso que adelanta 50 ms
por lectura, arrancando a distintas distancias de la medianoche: cayeron **14
pruebas de cinco clases** (el Loop B había contado 17 con otro arnés). Con el
blindaje puesto, el mismo arnés pasa en las cuatro profundidades de cruce
probadas. El arnés no se commiteó: era instrumento de medición.

**Acciones requeridas en Railway antes de desplegar** (no las detecta
`check --deploy`):

1. `TRUST_RAILWAY_PROXY=True` en el servicio web. Sin él, Django ve HTTP detrás
   del edge y `SECURE_SSL_REDIRECT` entra en bucle de redirecciones.
2. `CSRF_TRUSTED_ORIGINS` y `REDIS_URL` presentes y no vacías, o el contenedor
   no arranca. Fallar rápido y nombrando la variable es el objetivo del
   hallazgo 11, pero conviene verificarlo antes del deploy.

En desarrollo con ngrok hay que agregar `TRUST_RAILWAY_PROXY=True` al `.env`
local, o la firma de Twilio deja de validar.

### Loop D — Privacidad operativa, responsable clínico y firma *(bloquea el merge)*

Nace de la auditoría de cierre del 27/07/2026. Decisiones D11-D13 aprobadas
**antes** de escribir código, como en los tres loops anteriores.

- [x] **D-0** *(León, en Railway)* Dos consultas de **solo lectura**: pacientes activos sin responsable, y pacientes activos cuyo médico está inactivo / sin `is_staff` / sin correo. **Compuerta de D-6** — ver D12. Ejecutada el 27/07/2026: **cero y cero**
- [x] **D-1** `test: reproducir PHI en salida operativa, paciente sin medico y firma heredada` — `4cee84c` (11 pruebas: 9 rojas, 2 verdes declaradas). **Dos falsos verdes detectados antes de commitear** — ver abajo
- [x] **D-2** `fix: fijar la validacion de firma de Twilio en produccion` → D13 — `213218e` (+ `ec0aeda`, docs)
- [x] **D-3** `fix: identificar al paciente por pk en la salida operativa` → D11 — `ba1c573`
- [x] **D-4** `feat: exigir medico responsable al registrar un paciente` → D12 (capa 1) — `6de4410`
- [x] **D-5** `feat: proteger la atribucion clinica al eliminar una cuenta medica` → D12 (capa 2, migración **0027**) — `798e7a9` (+ `338b99d`, docs)
- [x] **D-6** `feat: garantizar responsable en todo paciente activo` → D12 (capa 4, `CheckConstraint`, migración **0028**) — `dc16719` (+ `72a3a29`, docs)
- [x] **D-7** `feat: avisar en el tablero de pacientes sin atencion efectiva` → D12 (capa 3) — `f9df890` (+ `f55f4c2`, docs)
- [x] **D-8** `fix: negar la creacion de pacientes de ejemplo sin medico usable` → D12 — `76c4869`
- [x] **D-9** `docs: corregir los cinco desfases entre documentos y codigo` — `e67dab1`
- [x] Cierre: **337 tests OK** · `check` sin issues · `makemigrations --check` limpio · script de verificación `5eff498`
- [x] **Verificación del Arquitecto:** corrí `proceso/verificaciones/2026-07-27_verificacion_loop_d.py` — **8 bloques, OK**. Confirmé las dos líneas que distinguen la verificación del trámite: la ficha histórica inactiva **sí** se sigue creando (la restricción no es `NOT NULL`), y el aviso del tablero da **0** con un médico que sí puede atender (no salta siempre)
- [x] **D-0 repetido antes del push** (27/07, dato fresco): `a_sin_medico = 0` otra vez. La 0028 no puede fallar por datos existentes
- [x] **Un solo push** a `origin/sprint-5-produccion` (`2fe6815 → 0f51ec0`, 18 commits). Las tres tarjetas de Railway en **SUCCESS** y `/salud/` en **HTTP 200 durante diez sondeos consecutivos** tras el deploy. **El Loop D está en producción**

**Los dos falsos verdes de D-1, porque son la lección del loop.** La prueba del
Admin no mandaba el checkbox `activo`: el paciente nacía inactivo y el filtro por
`activo=True` no lo encontraba. Las tres de la firma parcheaban el entorno, pero
`settings_production` hereda ese valor con `from .settings import *` y ese import
resuelve contra el módulo **ya cargado** al arrancar la suite — el parche no
tocaba nada y las tres pasaban con el defecto intacto. Se corrigieron antes de
commitear; la segunda dejó el helper `cargar_produccion_sobre_base_fresca` con el
porqué escrito, para que la próxima prueba de configuración no caiga en lo mismo.

**Alcance de D-6 más allá de la app.** La restricción dejó **164 pruebas en rojo**
—creaban pacientes activos sin médico— y también rompió la verificación archivada
del Loop C. Cualquier script, fixture o carga de datos que cree un paciente
activo sin responsable ahora falla. Es lo que la capa 4 debía lograr; conviene
saberlo antes de encontrarse con el error.

**Resultado de D-0 (27/07/2026).** Ejecutada en la tarjeta de SQL del Postgres de
producción (`base = railway`, última migración `0026_notificacion_estado_fallida`):

```
pacientes_totales  2      pacientes_activos  0
(A) activos sin medico        0      <- compuerta: abre
(B) activos sin atencion util 0
cuentas medicas: pk=1 superusuario, pk=2 staff — ambas activas y con correo
```

**La migración de D-6 puede escribirse.** Con cero pacientes activos, ninguna fila
existente puede violar `activo ⇒ medico_responsable no nulo`, y las dos filas
inactivas quedan fuera del alcance de la restricción — que es exactamente por lo
que D12 la eligió condicional en vez de `NOT NULL`.

**Por qué los dos demos están inactivos, y por qué no es un fallo.** Sus alertas
están fechadas el 24/07 y el seed les pone `fecha_cirugia` 8-10 días hacia atrás
para fabricarles historia: **nacen en POD 8-10**, al borde de los
`DIAS_SEGUIMIENTO = 10` de P-5. Los sostuvo el guard `DIAS_GRACIA_INGRESO = 2` y
`desactivar_pacientes_vencidos` los cerró el 26/07. El sistema hizo lo que debía.

**Hallazgo lateral, verificado y sin acción:** un paciente demo **nunca encola
correo**. `signals.py:23` corta la notificación cuando la cédula empieza por
`DEMO-`, antes de mirar la severidad. Por eso producción tiene alertas ALTA y
cero filas en `NotificacionAlerta`. Consecuencia práctica: **el correo de alerta
no se puede probar de punta a punta con los demos** — hace falta un paciente con
cédula real asignado a un médico con correo. Queda anotado para el piloto, no
para este loop.

**Señal de que el Loop A vive en producción:** 4 check-ins `NO_RESPONDIDO` y 2
alertas `SILENCIO / MEDIA` — racha de 2 turnos perdidos por paciente, que es la
severidad que fija D1. Antes del Loop A habrían quedado en BAJA.

**Por qué D-2 (la firma) va tan arriba.** Es pequeño, independiente de todo lo
demás y protege la única autenticación del webhook. Si el loop se interrumpe a
mitad, conviene que eso ya esté hecho.

**Advertencia de despliegue.** Railway sigue `sprint-5-produccion`: **el push
sale a producción de inmediato**, y el `Dockerfile` encadena
`migrate && gunicorn` — una migración que falla deja el contenedor sin arrancar.
Por eso el push es único, con todo verde, y **mirando el log del deploy y
`/salud/` justo después**, con el revert listo. Nunca de madrugada.

### Loop E — Operación del cron *(no bloquea el merge)*

- [x] **E-1** `test: reproducir que un fallo temprano del cron impide entregar alertas` — `e37e1a4`
- [x] **E-2** `fix: aislar las tareas del cron conservando las dependencias clinicas` → D14 — `d48ba41`
- [x] Cierre: **340 tests OK** · `check`, `makemigrations --check` y `check --deploy` sin issues · `git diff --check` limpio contra `origin/Desarrollo`
- [x] **Verificación del Arquitecto** — `proceso/verificaciones/2026-08-06_verificacion_loop_e.py`
- [x] PR a `Desarrollo` — **PR #10, mergeado el 07/08/2026** (`4fc690d`). Con él quedan implementadas las catorce decisiones D1-D14

> Desde el 10/08/2026 la CI corre **siete** comprobaciones, no cinco: se sumaron
> la guardia de secretos (`gitleaks` sobre la historia completa) y el control de
> que no haya ningún `.env` rastreado. **Se siguen viendo sin bloquear** — ver
> `CLAUDE.md`, sección "Repositorio", para por qué no es un trámite de permisos.

Va **después** del PR del Sprint 5, antes del piloto con pacientes reales. Motivo
en D14: es una condición preexistente que aquella rama no empeoraba, y
`cron_operativo` corre cada 5 minutos, así que un fallo transitorio se cura solo.
Lo que no se cura solo es uno persistente.

**Resultado de E-1 (evidencia del hallazgo):** las tres pruebas fallaron contra
el código anterior, y las tres **en la afirmación de qué tareas corrieron de
verdad** — no en el tipo de la excepción ni en el andamiaje del mock:
`3 != 6` en el resumen de fallos, y dos listas truncadas en la primera tarea que
falló. Es la comprobación que exige el método: ver el rojo no basta, hay que
confirmar que el rojo es el del requisito.

**Nota de método:** el refactor rompió dos pruebas preexistentes que afirmaban el
orden espiando `cron_matutino.call_command` — es decir, medían *dónde vivía el
bucle* en vez del requisito. Se reescribieron sobre el espía de E-1, que observa
qué tareas corrieron de verdad. El requisito que cuidan (el orden clínico de las
5:55-6:00 AM) no cambió.

### Después de los cuatro loops

- [ ] Entrada final de BITACORA cerrando los loops
- [ ] Revisión del diff completo contra `origin/Desarrollo`
- [ ] PR a `Desarrollo`
- [ ] **Rama de despliegue:** crear `produccion` desde `Desarrollo` tras el merge
  y apuntar Railway allí — pasos y advertencias en `docs/railway_deploy.md`,
  sección 4.1

---

## Cómo retomar en otra sesión

Este trabajo está diseñado para poder pausarse **en cualquier punto**, incluso a
mitad de un loop. El estado vive en este archivo y en el historial de Git, nunca
en la memoria de una conversación.

### Al cerrar una sesión

Se ejecuta el protocolo obligatorio de CLAUDE.md (BITACORA → CLAUDE.md/ROADMAP →
commit y push) **más un paso extra**: marcar en "Estado de avance" de arriba las
casillas completadas y actualizar la línea **Punto alcanzado** con la frase
exacta de dónde quedó el trabajo. Si un loop quedó a medias, decirlo así:
*"Loop B, A3 y A4 hechos, B5 sin empezar"*.

### Prompt para la sesión siguiente

Copiar y pegar tal cual:

```text
Retomamos el trabajo de corrección post-auditoría del Sprint 5.

Antes de proponer nada:
1. Lee completo docs/decisiones_correccion_auditoria.md — contiene las
   decisiones D1-D14 con su razonamiento, el método de trabajo acordado y el
   estado de avance.
2. Lee completo CLAUDE.md.
3. Verifica el estado real con git log, git status y la suite de tests. No
   asumas que el "Estado de avance" del documento está al día: contrástalo
   contra el código y el historial, y avísame si no coinciden.

Luego dime en una línea dónde quedamos y cuál es el siguiente commit según el
plan. No implementes nada hasta que yo confirme.

Respeta el método acordado: test en rojo antes del arreglo, muéstrame la salida
del fallo, un loop por sesión, y yo verifico antes de pasar al siguiente loop.
Las decisiones clínicas ya están tomadas en el documento — no las reabras salvo
que yo lo pida.
```

### Regla para quien retome

Si el "Estado de avance" contradice lo que dice Git o la suite de tests,
**manda Git**. El documento se actualiza a mano y puede quedar desfasado si una
sesión terminó de forma abrupta. Verificar siempre antes de continuar.

---

<a id="d1"></a>
## D1 — Escalera de severidad de las alertas SILENCIO

**Hallazgo:** 1 (ALTO, bloqueaba el PR) · **Loop:** A · **Estado:** Aceptada

### Problema

`_calcular_racha` recorría todos los check-ins del paciente sin excluir los
posteriores al que se estaba cerrando, y trataba un check-in `PENDIENTE` igual
que uno respondido: rompía la racha. Como el scheduler siempre deja turnos
pendientes, la racha valía 1 en cada cierre y **toda alerta SILENCIO quedaba en
BAJA**. Un paciente con 3 días completos sin responder (6 turnos) producía
`SILENCIO / BAJA — Monitorear`.

Reproducido contra base de datos de prueba, simulando la secuencia de
`cron_matutino`. Control: con el mismo historial pero sin turno posterior
pendiente, la racha daba 5 y la severidad ALTA.

### Decisión

1. Contar **solo check-ins estrictamente anteriores** al que se está cerrando,
   en el orden `(fecha_dia, orden)`.
2. Un check-in `PENDIENTE` anterior **se ignora y el conteo continúa**.
3. Escalera: **racha 1 → BAJA · racha 2 → MEDIA · racha 4 → ALTA**
   (antes: 1 / 2 / 3).

### Razonamiento

**SILENCIO no es un síntoma, es la ausencia de datos.** Eso invierte la
economía del error respecto de las otras siete reglas:

- Una alerta SILENCIO **no le dice nada al paciente** — no puede, el paciente no
  está respondiendo. Solo genera correo al médico y sube en el tablero.
- Por lo tanto el costo de un falso positivo es **una llamada telefónica**, no
  un viaje innecesario a urgencias.
- El costo de un falso negativo es perder al paciente entero.
- Conclusión: en SILENCIO conviene equivocarse hacia la **sensibilidad**. Es lo
  contrario de la Regla 7 (hinchazón), y por razones opuestas igualmente válidas.

**Por qué se cuentan check-ins y no días calendario.** Las Reglas 1, 3, 4, 6 y 7
agrupan por día porque necesitan **de-duplicar mediciones**: dos reportes de
fiebre en un mismo día son *un* día de fiebre. SILENCIO no tiene mediciones que
de-duplicar — cada check-in perdido es un intento de contacto distinto que
falló. El motivo de la agrupación por día no está presente aquí.

**Por qué 4 y no 3.** Con 4, el umbral ALTA cae exactamente en **dos días
calendario completos sin una sola señal** — una unidad clínica que el médico
puede enunciar y defender. Con 3 caía a mitad del segundo día, que no
corresponde a ninguna unidad nombrable. En un seguimiento de 10 días, 2 días
ciegos son el 20% de la ventana.

**Por qué la BAJA se queda en un solo turno.** Es gratis (no genera correo, solo
aparece en el tablero) y es informativa. En POD 1-2 la causa más común es que el
paciente todavía no se familiariza con el bot; verlo temprano permite una
llamada de acompañamiento en vez de una de emergencia.

**Por qué se ignora un PENDIENTE anterior.** Un check-in de un día pasado que
sigue abierto **ya no puede ser respondido**: `bot.py` solo sirve check-ins con
`fecha_dia = hoy`. Es decir, terminará inevitablemente en `NO_RESPONDIDO`.
Cortar el conteo ahí permitiría que una caída del cron degradara una alerta
clínica real — exactamente el tipo de fallo que se está corrigiendo. Un problema
de infraestructura no debe silenciar un problema del paciente.

### Efecto secundario conocido y aceptado

Resolver una alerta SILENCIO **no reinicia la racha**: la racha se calcula desde
el estado de los check-ins, no desde la alerta. Si el médico llama, el paciente
explica que se le dañó el teléfono, el médico resuelve — y el paciente sigue sin
responder, el siguiente turno perdido abre una alerta **nueva** que arranca
directo en ALTA.

**Se acepta y no se cambia.** Si el paciente sigue sin dar señales, el sistema
sigue sin datos, y eso es cierto. Además es el comportamiento consistente con
los otros seis tipos de alerta.

### Verificación

Prueba escrita **antes** de la corrección, ejecutando `crear_checkins_diarios`
seguido de `cerrar_checkins_vencidos` sobre un paciente con 4 turnos perdidos.
Las pruebas anteriores (`tests.py`) prefijaban los turnos a mano y dejaban un
único check-in pendiente, por lo que nunca modelaban al scheduler real: pasaban
en verde con la escalera rota.

---

<a id="d2"></a>
## D2 — Comportamiento del rate limit ante caída de Redis

**Hallazgo:** 5 (MEDIO) · **Loop:** B · **Estado:** Aceptada

### Problema

`_rate_limit_excedido` solo capturaba `ValueError` (clave inexistente). Con
Redis inalcanzable, `redis.ConnectionError` se propagaba y **el webhook devolvía
500 a todos los pacientes**: nadie podía reportar. Además la verificación ocurría
*después* de reclamar el SID, dejando filas colgadas en `PROCESANDO`.

Descubierto adicionalmente: el límite de **20 mensajes/hora** es peligrosamente
bajo. El cuestionario completo son 11 mensajes y cada respuesta mal entendida
cuesta uno más. Dos cuestionarios en una hora (22) o uno con 9 reintentos (20)
bloquean al paciente. Es la causa de fondo del incidente del Loop 6, del que
solo se había corregido el síntoma (`c12bfe5`).

### Decisión

1. **Webhook de WhatsApp: fallar abierto.** Si el cache no responde, se procesa
   el mensaje y se registra la degradación en el log.
2. **Formulario de contacto: fallar cerrado.** Se muestra el mensaje amable que
   ya existe para el rate limit.
3. Mover la verificación **antes** de reclamar el SID.
4. Subir `_LIMITE_MENSAJES_HORA` de **20 a 60**.
5. Endpoint `/salud/` que verifica base de datos y cache y devuelve **200** o
   **503**, sin detalle en el cuerpo, más un monitor externo gratuito que lo
   consulte cada 5 minutos y avise **al Arquitecto, no al médico**.

### Razonamiento

**Por qué el webhook falla abierto y el formulario no.** El rate limit protege
cosas distintas en cada puerta:

| | Webhook | Formulario de contacto |
|---|---|---|
| Quién puede tocarlo | Solo Twilio (firma HMAC) | Cualquiera en internet |
| Qué protege el límite | Costo por mensaje y bucles | Abuso — es el único control |
| Si Redis cae | La firma sigue protegiendo | Queda completamente abierto |

La firma de Twilio es la cerradura; el rate limit es el torniquete que cuenta.
Si se daña el torniquete del webhook, la cerradura sigue puesta: cerrar el
edificio dejaría afuera a los pacientes para protegerse de nadie. El formulario
no tiene cerradura, así que ahí el torniquete sí es el único control.

**El argumento decisivo es la ausencia de monitoreo.** Sin alarma externa,
fallar cerrado convierte una caída silenciosa en **pérdida de datos clínicos**
(los pacientes escriben, no reciben respuesta, se rinden, y nadie se entera
hasta que el médico abre el panel días después). Fallar abierto la convierte en
**pérdida temporal de un control de costos**, sin nada que recuperar. Un sistema
sin monitoreo no puede permitirse fallar cerrado en la ruta del paciente.

**Por qué 60 y no otro número.** El trabajo real del límite es **atrapar un
bucle**, no vigilar a un humano. Un cliente en bucle genera cientos de mensajes
por minuto; un paciente confundido genera cuarenta en una hora como mucho. Con
60 (≈5 cuestionarios completos) el bucle se corta igual y el paciente nunca toca
el techo. La población objetivo —personas mayores, recién operadas, con dolor—
es exactamente la que más reintentos necesita.

**Por qué la alarma va al Arquitecto.** Una caída de Redis es un problema
técnico. El médico no debe recibir ruido de infraestructura mezclado con
alertas clínicas.

### Nota de infraestructura

Redis es un plugin gestionado de Railway: si el proceso cae, Railway lo
reinicia. Las fallas que Railway **no** resuelve son de configuración o de plan
(`REDIS_URL` mal referenciada tras recrear el servicio, límite de recursos,
expulsión por memoria) — y son más probables que un crash real.

---

<a id="d3"></a>
## D3 — Registrar quién resuelve cada alerta

**Hallazgo:** 4 (MEDIO) · **Loop:** B · **Estado:** Aceptada

### Problema

`Alerta` guarda **cuándo** se resolvió, **por qué** y con qué **detalle**, pero
no **quién**. La acción del Admin usa `queryset.update()`, que salta las señales
y tampoco escribe una entrada en el historial de Django. No es que el dato se
borre: nunca se escribe.

### Decisión

1. Campo `resuelta_por = ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL,
   null=True)`, poblado en el mismo `.update()` de la acción.
2. Además, llamar a `log_change` para que el botón "Historial" de cada alerta
   funcione.
3. Mostrar "Resuelta por" en el detalle y en el listado.
4. **Sin backfill.** Lo anterior queda en `NULL` y el Admin lo muestra como
   *"No registrado — anterior a esta versión"*.

### Razonamiento

**Por qué importa aunque hoy haya un solo médico.** Los datos que no se capturan
no son recuperables. El día que entre un segundo médico —o que el sistema se
transfiera, escenario ya contemplado en `docs/transferencia_cuentas.md`— todo lo
resuelto hasta ese momento queda permanentemente sin atribución.

El caso concreto: si dentro de seis meses el médico revisa por qué un paciente
terminó reoperado y encuentra que doce horas antes hubo una alerta ALTA de
`FUGA_ANASTOMOTICA` marcada como *"Falso positivo — error de medición del
paciente"*, la pregunta inevitable es **quién** decidió eso. Hoy el sistema no
puede responder, y eso es peor que no tener nada porque *parece* un registro
completo.

**Por qué un campo y no solo el historial del Admin.** El historial guarda el
cambio como texto libre. `motivo_resolucion` existe explícitamente "para ajustar
umbrales clínicos con datos reales en el futuro" (CLAUDE.md); ese análisis
requiere consultas como *"¿qué alertas marcó este médico como falso positivo?"*,
imposibles de hacer sobre texto libre.

**Por qué no se hace backfill.** Rellenar con el único usuario existente sería
**fabricar una atribución clínica**: afirmar que una persona concreta tomó una
decisión concreta, sin evidencia. Es el mismo error que la migración 0019
cometió con `fecha_resolucion` (hallazgo 9) y el acierto que tuvo con `veces`,
donde se negó a inventar detecciones históricas. El proyecto ya tiene el patrón
honesto funcionando en `cobertura_detecciones`.

### Fuera de alcance

**No se agrega un flujo para reabrir alertas mal resueltas.** Si el problema
persiste, el motor abre una alerta nueva en el siguiente check-in, así que un
error se autocorrige. Agregar reapertura sería alcance nuevo sin necesidad
demostrada.

---

<a id="d4"></a>
## D4 — Umbral de fiebre comunicado al paciente

**Hallazgo:** 12 (BAJO) · **Loop:** A
**Estado:** Aceptada provisionalmente — **PENDIENTE DE VALIDACIÓN MÉDICA**

### Problema

Dos inconsistencias:

1. `RESP_FIEBRE` decía *"Si supera 38°C comunícate con tu médico"*, mientras el
   motor abre alerta ALTA desde **37.9 °C**. Un paciente con 37.9 recibía el
   mensaje de que estaba bien mientras el sistema le mandaba un correo urgente
   al médico.
2. La frase *"una temperatura leve los primeros días puede ser normal"* sugiere
   que **el tiempo normaliza** la fiebre, mientras la Regla 1b dice que el
   tiempo es exactamente lo que la **escala** (37.5–37.8 dos días seguidos →
   MEDIA).

Y de fondo, una incoherencia mayor con la regla de diseño no negociable del bot
en CLAUDE.md: *"El paciente nunca ve el tipo de alerta ni los valores que la
dispararon... umbrales... es exclusivo del oncólogo"*. `RESP_FIEBRE` **le estaba
dando un umbral clínico al paciente**. Cambiar 38 por 37.9 corregía la
aritmética y dejaba la violación intacta.

### Decisión

**Opción B — retirar el número.** Texto nuevo:

> *"Registramos tu temperatura en cada reporte y tu equipo médico la está
> revisando. Si te sientes peor, con escalofríos o mucho malestar, comunícate
> con tu médico. Si es urgente, ve al servicio de urgencias."*

Reflejado en `bot.py` (`RESP_FIEBRE`) y en `knowledge_base.md`, que obliga a
mantener el espejo.

### Razonamiento

**El paciente no necesita auto-triarse — para eso existe el sistema.** Se le
pregunta la temperatura dos veces al día y el motor la evalúa. Pedirle además
que haga su propio juicio con un umbral duplica la función y abre la puerta a
que se equivoque en la dirección peligrosa.

El texto nuevo además le recuerda que el sistema ya está vigilando por él, y usa
la misma salida de acción que `MSG_CIERRE_ALERTA_ALTA`.

**`RESP_DOLOR` ya está escrito así** (remite al médico sin dar números) y por
eso **no se toca**: es el modelo, no un problema.

### Límite explícito de esta decisión

**Cuál debe ser el mensaje clínico no lo decide el equipo técnico.** CLAUDE.md
prohíbe completar contenido clínico sin validación del médico. Esta decisión
resuelve una **incoherencia interna del producto** (el bot contradecía su propia
regla de diseño y su propio motor); la redacción final es del médico.

### Consulta pendiente al médico

Registrada en `knowledge_base.md`, sección "Consulta pendiente al médico", con
tres preguntas concretas (fiebre, dolor, alimentación) para resolver en una sola
sesión de ~10 minutos. Ítem correspondiente agregado al ROADMAP en los
requisitos del piloto.

**Este texto no debe presentarse como contenido final en las pruebas.**

---

<a id="d5"></a>
## D5 — Signos concurrentes de íleo en un mismo check-in

**Hallazgo:** 10 (BAJO) · **Loop:** A · **Estado:** Aceptada

### Problema

Cuando dos reglas del mismo tipo se disparan en el mismo check-in, se pierde el
mensaje de la menos grave: la restricción `unique_det_alerta_registro` fuerza
una sola `DeteccionAlerta` por check-in, y su `mensaje_detectado` se sobrescribe
con el de mayor severidad.

**Solo afecta a `ILEO_PARALITICO`**, que es el único tipo producido por reglas
que pueden coincidir: Regla 3 (gases), Regla 4 (náuseas) y Regla 7 (hinchazón).
Los demás tipos tienen reglas mutuamente excluyentes.

### Decisión

1. `DeteccionAlerta.mensaje_detectado` **acumula** los signos concurrentes,
   verificando que el mensaje no esté ya presente (idempotente ante reintentos
   del motor sobre registros en `ERROR`).
2. `Alerta.mensaje` conserva el del signo más grave — **sin cambio**.
3. Severidad = la máxima — **sin cambio**.

### Razonamiento

**La evidencia convergente es más fuerte que la suma de sus partes.** Distensión
sola puede ser muchas cosas; distensión + ausencia de tránsito + vómito es el
cuadro clásico de íleo. Hoy el médico ve un solo signo cuando el paciente tenía
tres a la vez.

**Separación titular/detalle:** `Alerta.mensaje` es el titular del listado y del
tablero de triage — debe caber en una línea y ordenar por urgencia.
`DeteccionAlerta.mensaje_detectado` es el detalle donde el médico entra a mirar,
y ahí sí cabe el cuadro completo.

**Por qué no se separa el íleo en tipos distintos** (`ILEO_GASES`,
`ILEO_NAUSEAS`, `ILEO_DISTENSION`): contradiría la decisión de agrupación del
10/07/2026, exigiría migración, multiplicaría alertas y correos, y metería ruido
en el tablero. La solución elegida no toca la agrupación, ni los umbrales, ni la
severidad, ni el número de correos, y **no requiere migración**.

---

<a id="d6"></a>
## D6 — Límite de reintentos y estado terminal

**Hallazgo:** 13 (BAJO) · **Loop:** B · **Estado:** Aceptada

### Problema

Nada se rinde nunca. El correo de alerta reintenta indefinidamente (backoff
tope 6 h) y la evaluación de un registro se reintenta cada 5 minutos sin
límite. Además `intentos` es `PositiveSmallIntegerField` (máx. 32767): a 5
minutos por intento desbordaría en ~113 días.

### Decisión

1. **Máximo 10 intentos** en ambos casos.
2. Estado **`FALLIDA`** para notificaciones agotadas (requiere reemplazar la
   restricción `notificacion_alerta_estado_valido`).
3. Aviso visible en el **tablero de triage** cuando existan notificaciones
   `FALLIDA` — **visible también para el médico**, a diferencia del aviso de
   degradación de cache, que es solo para el superusuario.

### Razonamiento

**Reintentar para siempre esconde el problema.** De las cuatro causas reales de
fallo, tres necesitan intervención humana y ninguna cantidad de reintentos las
resuelve:

| Causa | ¿Se resuelve sola? |
|---|---|
| Resend caído o red intermitente | Sí, en minutos |
| API key vencida o mal copiada | **No** |
| Médico sin email configurado | **No** |
| Correo rebotado | **No** |

**Por qué 10.** Con el backoff actual (5, 15, 45, 135 min, luego cada 6 h), 10
intentos son ≈39 horas. Día y medio de recuperación automática es generoso para
un fallo transitorio; si a las 39 horas sigue fallando, es configuración.

**Por qué `FALLIDA` tiene que ser visible.** Un correo de alerta ALTA que falla
permanentemente **es información clínica que no llegó**. Rendirse en silencio
sería peor que reintentar para siempre. Para un piloto de 1-3 pacientes con el
Arquitecto revisando el panel con regularidad, el aviso en el tablero alcanza;
un canal de alerta propio para anomalías de negocio queda para después del
piloto.

Como efecto colateral, el tope elimina el riesgo de desbordamiento del contador.

---

<a id="d7"></a>
## D7 — Registros dados por evaluados en la migración 0020

**Hallazgo:** 3 (MEDIO) · **Loop:** C · **Estado:** Aceptada

### Problema

La migración 0020 marcó **todos** los `RegistroDiario` existentes como
`COMPLETADA` asumiendo que ya habían pasado por el motor. Antes del Loop 2 no
existía seguimiento de estado, así que es una suposición no verificable. Un
registro cuya evaluación falló antes de 0020 queda congelado como evaluado y
nunca será recuperado por `reintentar_evaluaciones_alertas`.

### Decisión

1. **Contar primero**, con una consulta de solo lectura en Railway:

   ```
   estado_evaluacion_alertas = 'COMPLETADA'  AND  intentos_evaluacion_alertas = 0
   ```

2. Si el resultado es **cero** → documentar y cerrar, sin tocar nada.
3. Si es mayor que cero → revisar de quién son esos datos. Solo si fueran de un
   **paciente real** entra el médico; si son de demos o de las pruebas de los
   Loops 5-6, los revisa el Arquitecto.
4. **En ningún caso reevaluar en masa.**

### Razonamiento

**El marcador es exacto.** La migración puso el estado pero no tocó el contador
de intentos, que quedó en su default de 0. Cualquier registro evaluado de verdad
por el motor instrumentado pasa por `intentos_evaluacion_alertas += 1`. La
combinación `COMPLETADA` + `intentos = 0` identifica sin ambigüedad los
registros marcados por la migración.

**Por qué no se reevalúa en masa.** `evaluar_registro` dispara la señal que
encola correos. Reevaluar historia le mandaría al médico alertas ALTA sobre
episodios de hace semanas, de pacientes cuyo seguimiento ya cerró: convertiría
una duda contable en ruido clínico real.

**Expectativa:** se espera cero. Los demos se limpiaron, los pacientes de prueba
de los Loops 5 y 6 se eliminaron transaccionalmente, y nunca ha habido un
paciente real en el sistema. Pero es una expectativa, y por eso el primer paso
es contar.

---

<a id="d8"></a>
## D8 — Días sin datos en las reglas de días consecutivos

**Origen:** ejercicio de documentación, 22/07/2026 · **Loop:** C · **Estado:** Aceptada

### Problema

Las cuatro reglas que cuentan días consecutivos **dejan de contar cuando
encuentran un día sin ningún registro**. Cuentan *días con datos consecutivos*,
no *días calendario consecutivos*, que es como los describen CLAUDE.md y el
ROADMAP.

| Regla | Cómo se corta |
|-------|---------------|
| 3 — gases | `alert_engine.py:394` — `if not existe_registro: break` |
| 6 — tolerancia a líquidos | `alert_engine.py:576` — `if not existe_registro: break` |
| 4 — náuseas | rompe cuando no hubo náuseas; un día sin datos cuenta como "sin náuseas" |
| 7 — hinchazón | `_nivel_hinchazon_dia` devuelve `None` → `break` |

En la práctica:

```
Lunes      reporta:  sin gases     → cuenta 1
Martes     no reporta              → CORTA el conteo
Miércoles  reporta:  sin gases     → vuelve a contar desde 1
```

Tres días sin tránsito intestinal quedan registrados como "un día".

### Decisión

**Conservar el comportamiento del código. Corregir la documentación**, que es
donde está el error: las tablas de referencia deben decir "días con datos
consecutivos", no "días calendario consecutivos".

### Razonamiento

Al detectarlo pareció una **inconsistencia con D1** — allí se decidió que un
check-in `PENDIENTE` (un desconocido) **no rompe** la racha de SILENCIO, y aquí
un día sin datos (otro desconocido) **sí la rompe**. Al analizarlo, los dos
casos no son equivalentes:

- En D1, el `PENDIENTE` es un desconocido **cuyo desenlace ya está determinado**:
  ese check-in no puede responderse (el bot solo sirve los de hoy), así que
  terminará en `NO_RESPONDIDO`. Ignorarlo recupera un hecho conocido.
- Aquí, un día sin datos es un desconocido **genuino**: el paciente pudo haber
  tenido gases y no reportarlo. Contar a través de él **inventaría un hecho
  clínico**.

No inventar datos que no se observaron es el principio más consistente de este
proyecto: no se hizo backfill de `veces`, ni de `resuelta_por` (D3), y la
migración 0019 fue criticada precisamente por fabricar una `fecha_resolucion`.

Además **el hueco ya tiene su propia alerta**: si el paciente no reporta, se
genera SILENCIO, que tras el Loop A sí escala correctamente.

### Límite explícito

Esta decisión **no cierra la pregunta clínica**. Si el médico considera que un
día sin reportar no debería reiniciar el conteo —por ejemplo, tolerar un hueco
de un solo día sin romper la racha— eso es un **cambio de umbral clínico** y
requiere su validación explícita más evidencia. Queda anotado como pregunta
abierta, no como decisión tomada.

**Limitación conocida que se acepta:** un paciente que reporta de forma
intermitente puede tener 3 días con signos y que ninguna regla escale, mientras
recibe alertas SILENCIO por separado. Las dos señales **no se suman** — el
médico ve `ILEO/BAJA` + `SILENCIO/BAJA` en vez de un cuadro que escale.

---

<a id="d9"></a>
## D9 — Campo `fecha_ultimo_registro` sin lectores

**Origen:** ejercicio de documentación, 22/07/2026 · **Loop:** C · **Estado:** Aceptada

### Problema

`ConversacionWhatsApp.fecha_ultimo_registro` se escribe pero **nunca se lee**.
Verificado: aparece exactamente dos veces en todo el código —
`models.py:726` (definición) y `bot.py:724` (escritura). Cero lecturas.

Es un resto del modelo anterior de "un registro por día", que hoy se controla
por `CheckInProgramado`.

### Decisión

**Marcar el campo como obsoleto en su `help_text`. Sin migración, sin borrar la
columna, sin quitar la escritura.**

### Razonamiento

Borrar una columna en una base de datos de producción exige migración y
despliegue. El beneficio es cosmético; el riesgo, aunque bajo, no es cero. En
medio de una corrección que bloquea un merge, no se justifica.

Dejar la escritura mantiene el campo coherente por si alguien lo consulta
manualmente. La limpieza real —quitar campo y escritura— queda para después del
merge, cuando no haya nada en juego.

---

<a id="d10"></a>
## D10 — Cláusula MEDIA de la regla de hinchazón

**Origen:** ejercicio de documentación, 22/07/2026 · **Loop:** C · **Estado:** Aceptada

### Problema

La condición MEDIA de la Regla 7 (`alert_engine.py:623-626`) encadena tres
comparaciones, y **dos de ellas se vuelven trivialmente verdaderas cuando falta
el dato de ayer**:

```python
if nivel_hoy > nivel_antier and (
    nivel_ayer is None or nivel_ayer >= nivel_antier      # ← True si falta ayer
) and nivel_hoy >= (nivel_ayer if nivel_ayer is not None else nivel_hoy):
                                                          # ← nivel_hoy >= nivel_hoy
```

Sin el dato de ayer, toda la condición se reduce a `nivel_hoy > nivel_antier`:
la verificación de "sostenido" desaparece justo cuando no hay con qué
verificarla. La regla documentada dice "empeoramiento sostenido sin bajar".

### Decisión

**Primero hacerla auditable, después decidir.** En el Loop C:

1. Agregar pruebas dedicadas que **fijen el comportamiento actual**, incluido
   explícitamente el caso sin dato de ayer.
2. Reescribir la expresión para que sea legible, **sin cambiar comportamiento**
   — las pruebas del punto 1 lo garantizan.
3. **No** modificar cuándo dispara la alerta.

### Razonamiento

Cambiar cuándo dispara es mover un umbral clínico, y CLAUDE.md exige validación
explícita del Arquitecto y del médico para eso. Pero la expresión actual no se
puede auditar leyéndola, así que hoy nadie —ni el médico— puede opinar con
fundamento sobre si es correcta.

El orden importa: **hacerla legible y cubierta por pruebas primero** permite que
la decisión clínica se tome después con la información a la vista, y que
cualquier cambio futuro sea verificable en vez de arriesgado.

---

<a id="d11"></a>
## D11 — Identidad del paciente en la salida operativa

**Hallazgo:** auditoría de cierre, 1 (ALTO) · **Loop:** D · **Estado:** Aceptada

### Problema

`desactivar_pacientes_vencidos` escribe el **nombre completo** del paciente y su
día postoperatorio en la salida estándar, que Railway captura y conserva:

```
desactivar_pacientes_vencidos: Maria Fernanda Quintero desactivado (POD 12)
```

`enviar_recordatorios` arma además **nombre completo y teléfono** de cada
check-in pendiente. Hoy no se emite porque el logger `signos_sintomas` está en
nivel `WARNING`, pero un cambio de nivel volcaría la lista completa de pacientes
con su celular.

Y `settings.py:189` afirma que el LOGGING "filtra PHI/PII". **No filtra nada:**
el único filtro configurado es `RequireDebugFalse`.

Reproducido el 27/07/2026 — ver
`proceso/auditorias/2026-07-27_informe_cierre_codex.md`.

### Decisión

**Invariante: ninguna salida que el sistema escribe deliberadamente —logs,
stdout, stderr, salida de un comando— contiene identidad del paciente.**

El invariante habla de la salida **nominal**: la que este código decide
escribir. No alcanza al texto de una excepción ajena que llegue por un
traceback; eso se acota abajo como riesgo residual, y la ficha no promete
cubrirlo.

1. Toda salida operativa identifica al paciente por `pk`, como ya hace el resto
   del código (`cerrar_checkins_vencidos`, `signals`, `bot`).
2. El comentario de `settings.py:189` dice la verdad sobre lo que el LOGGING
   hace y lo que no — y **no afirma que los tracebacks estén saneados**.
3. **Una prueba guardián** recorre la salida de los comandos operativos y falla
   si aparece el nombre o el teléfono de un paciente. Captura **stdout, stderr y
   los logs forzando nivel INFO**, no con la configuración normal.

**Por qué el guardián fuerza el nivel INFO.** Bajo el nivel `WARNING` que rige
en producción, la línea de `enviar_recordatorios` con nombre y teléfono es
invisible: un guardián que corriera con la configuración normal **pasaría en
verde con el defecto puesto**. Sería el fallo de julio —una prueba verde que no
prueba nada— reproducido dentro de la prueba que existe para impedirlo. La
regresión que hay que atrapar no es "se emite PHI", es "se escribió código que
emitiría PHI si alguien cambia un nivel de log".

### Razonamiento

**Por qué `pk` y no una cédula parcial o un seudónimo.** El `pk` ya es el
identificador que usa el resto del sistema para operar, es estable, y no dice
nada de la persona fuera de la base. Cualquier identificador derivado del dato
real (iniciales, cédula truncada) sigue siendo dato personal degradado: reduce
el riesgo sin eliminarlo, y obliga a discutir cuánto es "suficientemente poco".

**Qué se pierde.** Leer un log operativo ya no dice *a quién* le pasó algo sin
consultar la base. Es exactamente la propiedad que se busca: quien tiene derecho
a saberlo entra al panel autenticado, que es donde vive esa información.

**Por qué la prueba guardián y no solo corregir las dos líneas.** Las dos
ocurrencias de hoy se arreglan en diez minutos; lo que hace falta es que la
tercera —la que escriba alguien dentro de seis meses— no llegue a producción.
Sin el guardián esto se repite, porque escribir el nombre en un log es lo
natural cuando estás depurando.

### Riesgo residual aceptado

El traceback de `bot.py:536` (`logger.exception`) sí se emite —ERROR pasa el
umbral— y arrastra el mensaje de la excepción. El encabezado que escribe este
código usa solo `pk`s, pero una excepción de terceros podría cargar un valor
clínico. **No hay ningún caso conocido**; se registra como exposición
condicional, fuera del alcance de D11 y fuera del Loop D.

Redactar tracebacks es una capa de logging propia, no un parche, y merece su
propia decisión cuando exista un caso real que la justifique. Lo que sí exige
esta ficha es que **ningún comentario del código afirme lo contrario**: la
promesa que se escriba en `settings.py` debe describir la salida nominal, no
insinuar que los tracebacks están saneados.

---

<a id="d12"></a>
## D12 — Todo paciente activo tiene un médico responsable

**Hallazgo:** auditoría de cierre, 2 (ALTO) · **Loop:** D · **Estado:** Aceptada

### Problema

El formulario del Admin **no exige** `medico_responsable`, y el desplegable nace
vacío. Un médico no-superusuario puede crear un paciente sin asignarlo — con una
sola opción posible en la lista, que es él mismo.

El paciente resultante sigue activo, responde al bot y genera alertas, pero:

- **desaparece del listado del médico** (`get_queryset` filtra por
  `medico_responsable=request.user`),
- **desaparece de los KPI del tablero de triage** — el médico ve ceros, no un
  hueco,
- su alerta ALTA queda con `destinatario=''` y `procesar_notificaciones_email`
  lanza `CommandError`, dejando la corrida del cron en rojo permanente.

Hay además una segunda vía, por la puerta de atrás: `medico_responsable` es
`on_delete=SET_NULL`, así que **borrar la cuenta de un médico convierte a todos
sus pacientes en huérfanos invisibles, en silencio.**

Reproducido el 27/07/2026 con el formulario real del Admin.

**Y dos vías más, señaladas por Codex al revisar la primera versión de esta
ficha** (verificadas contra el código antes de aceptarlas):

- `seed_demo_produccion.py:190` crea los pacientes de ejemplo **sin médico** si
  no encuentra un superusuario, con solo un `WARNING` en pantalla.
- `seed_demo_produccion.py:183` acepta **cualquier `username`** en `--medico`,
  sin comprobar que sea `is_staff`, que pertenezca al grupo Médicos ni que tenga
  correo. Un paciente asignado a un usuario así no es huérfano —el campo está
  lleno— pero **nadie puede verlo ni recibir su alerta**, y ninguno de los dos
  avisos de la capa 3 lo detectaba.

### Decisión

**Invariante clínico: todo paciente ACTIVO tiene un médico responsable que
puede verlo y recibir sus alertas; y la atribución, una vez hecha, es histórica
e indeleble.**

La palabra *activo* es la que hace que el invariante sea cumplible y no un deseo:
las filas históricas e inactivas conservan lo que tengan, incluido `NULL`.

Se sostiene en cuatro capas, porque ninguna alcanza sola:

1. **La puerta de entrada.** El formulario del Admin exige el campo. Si quien
   guarda es un médico no-superusuario, se le asigna a él automáticamente. El
   superusuario conserva la libertad de dejarlo vacío para mantenimiento.
2. **La puerta de atrás.** `on_delete=SET_NULL` → **`PROTECT`**. Django se niega
   a borrar una cuenta de médico mientras tenga pacientes: obliga a reasignarlos
   explícitamente antes.
3. **La red.** El tablero del superusuario avisa de los pacientes **activos sin
   nadie que pueda atenderlos**: sin médico responsable, o con un médico que
   está inactivo, **o que no tiene acceso al Admin (`is_staff=False`), o que no
   tiene correo**. Las cuatro condiciones producen el mismo daño clínico —nadie
   mira a ese paciente— y por eso comparten un solo aviso.
4. **La garantía.** `CheckConstraint` en `Paciente`: **`activo=True` implica
   `medico_responsable` no nulo**. La base de datos rechaza la fila, venga del
   Admin, de un script, del shell o de un comando.

Y el comando que hoy los fabrica se corrige: `seed_demo_produccion` **se niega a
crear pacientes sin médico** en vez de advertirlo, y valida que el `--medico`
recibido sea un médico usable (activo, `is_staff`, con correo).

**Regla operativa que acompaña a la decisión:** las cuentas de médico **no se
borran, se desactivan** (`is_active=False`); y antes de desactivar una, se
reasignan sus pacientes activos.

### Razonamiento

**Por qué quién atendió a un paciente no se borra.** Es parte de la historia
clínica, no un dato de configuración. Borrarlo no es limpiar datos personales:
es borrar la trazabilidad de un acto médico. El proyecto ya aplica ese principio
en dos sitios — los pacientes se cierran con `activo=False` porque *"el borrado
elimina trazabilidad clínica"* (`PacienteAdmin.has_delete_permission`), y D3 se
negó a rellenar `resuelta_por` hacia atrás porque habría **fabricado una
atribución clínica**. Esta decisión es la misma idea aplicada al otro extremo de
la relación.

**Por qué desactivar y no borrar resuelve el caso real.** Un médico que deja de
usar el sistema no puede entrar, pero su nombre sigue colgando de cada paciente
que atendió y de cada alerta que resolvió. No se pierde nada y no hay que migrar
nada. `PROTECT` no es la regla: es lo que impide saltársela por descuido.

**Por qué cuatro capas y no una.** Cada una tapa lo que las otras no ven. El
formulario cubre el camino de todos los días; `PROTECT` cubre el borrado
administrativo; la restricción cubre todo lo que no pasa por Django —un script,
el shell, una carga de datos—; y el aviso del tablero cubre lo que ninguna
impide: el paciente cuyo médico existe pero **no puede atenderlo**. Porque **el
problema real de este hallazgo no es que el paciente quede huérfano: es que
quede huérfano en silencio.** Un huérfano visible es un pendiente; uno invisible
es un paciente sin atención.

**Por qué el invariante se acotó a los pacientes activos.** La primera versión de
esta ficha prometía *"todo paciente activo tiene un médico responsable"* en el
título y, tres párrafos después, admitía en el razonamiento que la garantía real
era sobre el silencio, no sobre la existencia del huérfano. Codex leyó el título,
enumeró cuatro vías por las que un huérfano seguía naciendo, y tenía razón: la
ficha se contradecía a sí misma. La respuesta no fue rebajar la promesa sino
**hacerla verdadera**, con la capa 4. Una decisión que promete de más es peor que
una que promete poco: la siguiente persona confía en ella.

**Por qué el aviso de "médico inactivo" pesa tanto como el de "sin médico".** Es
el riesgo operativo del día a día una vez aplicada la regla de desactivar en vez
de borrar: se desactiva al médico que se fue, sus pacientes siguen vivos
respondiendo al bot, y sus alertas ALTA viajan al correo de alguien que ya no
entra al sistema. El síntoma es idéntico —nadie mira a ese paciente— pero la
causa no se detecta con la comprobación de huérfanos.

**Por qué una restricción condicional y no `NOT NULL`.** `NOT NULL` obligaría a
inventarle un médico a cada fila histórica e inactiva que hoy no lo tiene —
fabricar una atribución clínica, justo lo que D3 se negó a hacer. La restricción
`activo ⇒ responsable` deja esas filas en paz y protege exactamente el caso que
importa: el paciente que **hoy** está siendo monitoreado. Es más estrecha y más
fuerte a la vez. La sugirió Codex al revisar la primera versión de esta ficha.

**La compuerta antes de la capa 4, que no es opcional.** El `Dockerfile` encadena
`migrate --noinput && gunicorn`: **si la migración falla, el contenedor no
arranca.** Añadir una restricción que alguna fila existente viole no produce un
error en el log — produce el sitio caído. Por eso el Loop D empieza por dos
consultas de **solo lectura** contra producción (paso D-0): cero pacientes
activos sin responsable, y cero pacientes activos con un médico inactivo, sin
`is_staff` o sin correo. Si alguna devuelve filas, **se arreglan los datos antes
de escribir la migración**. Es la misma disciplina de D7: contar antes de actuar.

### Efecto secundario conocido y aceptado

Con `PROTECT`, borrar una cuenta de médico con pacientes **falla con un error de
Django** en vez de hacerlo en silencio. Es el comportamiento buscado, pero
significa que la operación "dar de baja a un médico" pasa a tener un paso
obligatorio previo: reasignar. Se documenta en la regla operativa, y el aviso
del tablero es lo que hace que se cumpla sola.

---

<a id="d13"></a>
## D13 — La autenticidad del webhook no depende del entorno

**Hallazgo:** auditoría de cierre, 3 (ALTO condicional) · **Loop:** D ·
**Estado:** Aceptada

### Problema

La firma `X-Twilio-Signature` es **la única cerradura** del webhook: la URL es
pública y adivinable, no hay login y está exenta de CSRF. Sin validación de
firma, cualquiera que conozca la URL puede inyectar telemetría falsa en la
historia de un paciente real, cerrar su check-in del día como respondido
—**apagando la alerta SILENCIO de alguien que en realidad no respondió**— o
generar alertas ALTA falsas. Ni el rate limit ni la validación del SID lo
impiden: ninguno autentica.

`settings_production.py` **no fija** `TWILIO_VALIDATE_SIGNATURE`: hereda lo que
diga el entorno. Con la variable en `False`, producción acepta cualquier POST sin
firma, en silencio, y `check --deploy` no lo reporta.

**Estado real verificado en Railway el 27/07/2026:** la variable **no existe** en
el servicio web; `TWILIO_AUTH_TOKEN` sí. Como el default del código es `True`, la
validación está activa hoy.

### Decisión

1. **`TWILIO_VALIDATE_SIGNATURE = True` fijo en `settings_production.py`**, junto
   a `DEBUG = False`. Deja de leerse del entorno.
2. **No crear la variable en Railway.** Ni con valor `True`.

### Razonamiento

**Por qué no crear la casilla, aunque sea para ponerla en `True`.**
`python-decouple` convierte una cadena vacía en `False`:

```
variable AUSENTE     -> True     ← el estado actual
variable VACIA ('')  -> False    ← la firma queda desactivada
variable = True      -> True
```

Y Railway **reemplaza por cadena vacía toda referencia que no puede resolver**
(`docs/trampas_conocidas.md`, incidente del 25/07). Crear la variable introduce
exactamente el modo de fallo que ya costó una madrugada, con la diferencia de
que este falla **abriendo la cerradura en silencio** en vez de tumbando el
contenedor. Una variable que no existe no se puede configurar mal.

**Por qué en producción no se negocia.** El valor `False` es legítimo y
necesario en desarrollo local, donde no hay firma que validar. Que la misma
palanca exista en producción significa que una variable copiada entre servicios
—o compartida entre ellos— desactiva la autenticación del canal por el que entra
toda la información clínica del sistema.

**Qué se pierde.** Poder desactivar la validación en producción para depurar. No
hace falta: cuando la firma falla detrás de Railway, la causa real es casi
siempre que Django no reconstruye la URL pública `https`, y eso se arregla con
`TRUST_RAILWAY_PROXY=True` (hallazgo 6), no apagando la cerradura.

**Coherencia con D2.** El rate limit del webhook **falla abierto** ante una caída
de Redis, y esa decisión se justificó precisamente en que *la firma de Twilio
protege el webhook*. D13 convierte ese supuesto en garantía. Codex registró la
misma condición al revisar D2.

---

<a id="d14"></a>
## D14 — Aislamiento entre las tareas de un mismo cron

**Hallazgo:** auditoría de cierre, riesgo residual (d) · **Loop:** E ·
**Estado:** **Implementada** (06/08/2026) — `e37e1a4` (E-1) y `d48ba41` (E-2).
Runner en `signos_sintomas/cron_runner.py`; comportamiento documentado en
`docs/cron_setup.md`, sección "Qué pasa si una tarea del cron falla".

### Problema

`cron_matutino` y `cron_operativo` ejecutan sus tareas con `call_command` en un
bucle sin manejo de errores. **Si una tarea falla, las siguientes no corren.**

La verificación del 27/07 comprobó que el fallo de
`procesar_notificaciones_email` no arrastra a nadie —es la última de ambas
listas— y de ahí se concluyó "no hay efecto dominó". **La conclusión era más
amplia que la evidencia**, y Codex lo señaló: eso demuestra que la *última*
tarea está aislada, no que las tareas estén aisladas entre sí.

El caso que importa es el contrario. En `cron_operativo`:

```
cerrar_checkins_vencidos → reintentar_evaluaciones_alertas → procesar_notificaciones_email
```

Un fallo persistente de la **primera** impide que salgan los correos de alerta
ALTA de ese ciclo. La tarea que genera las alertas de silencio y la que entrega
los avisos al médico están encadenadas por una razón que no es clínica: que el
plan de Railway no daba para más servicios cron.

### Decisión

**Un fallo operativo no puede impedir que se entregue una alerta clínica ya
generada.** Las tareas de un cron se aíslan entre sí, **salvo cuando existe una
dependencia clínica declarada.**

1. El runner ejecuta **todas** las tareas, captura el fallo de cada una, y
   **termina con estado de error** informando cuáles fallaron. No se rinde en la
   primera ni finge que todo salió bien.
2. **Excepción declarada:** en `cron_matutino`, si `desactivar_pacientes_vencidos`
   falla, `crear_checkins_diarios` **no debe ejecutarse**. Las dependencias se
   escriben en el propio comando, con su motivo clínico al lado.

### Razonamiento

**Por qué no basta con "continuar ante el fallo".** Es la corrección obvia y
sería un error. `cron_matutino` tiene un orden clínicamente obligatorio, escrito
en su propio docstring: `desactivar_pacientes_vencidos` va **antes** de
`crear_checkins_diarios` porque, si no, un paciente que vence ese día recibe un
check-in que quedará `PENDIENTE` para siempre y **generará una alerta SILENCIO
espuria**. Continuar ciegamente tras el fallo de la primera produce exactamente
ese daño. El aislamiento tiene que ser **selectivo y declarado**, no automático.

**Por qué termina en error igualmente.** Rendirse en silencio sería peor que
fallar — es el mismo razonamiento de D6. Railway marca la corrida como fallida y
eso es una señal operativa legítima; lo que no es legítimo es que esa señal
cueste los correos del ciclo.

**Por qué no bloquea el merge y va en un loop aparte.** Es una condición
**preexistente**: la rama `sprint-5-produccion` no la introduce ni la empeora, y
`cron_operativo` corre cada 5 minutos, así que un fallo transitorio se cura solo
en el siguiente ciclo. Lo que no se cura solo es un fallo persistente. Se
implementa antes del piloto con pacientes reales, no antes del merge.

### Deuda de infraestructura asociada

El agrupamiento existe porque el plan actual de Railway limita el número de
servicios cron (ver `CLAUDE.md`, "Por resolver antes del piloto real", punto 5).
Al mejorar el plan, `cron-operativo` pasa a servicio propio y `cron-tarde`
vuelve a su horario original — y buena parte de este acoplamiento desaparece por
sí solo. D14 es lo que hace que el sistema sea correcto **mientras tanto**.

---

## D15 — Qué reescribe `crear_medico` en cada arranque

**Hallazgo:** revisión de cierre del PR del Sprint 5, punto 8 · **Loop:** — ·
**Estado:** **Decidida** (12/08/2026), **pendiente de implementar.**
Guion de la sesión: `proceso/instrucciones/2026-08-10_instruccion_crear_medico.md`.

### Problema

`crear_medico` corre en **cada arranque** del servicio web, encadenado con `&&`
en los dos sitios que levantan la app: `Dockerfile:37` y `nixpacks.toml`,
`[start]`. Sobre una cuenta que **ya existe** ejecuta igual, sin preguntar:

```python
user.email = email              # crear_medico.py:84
user.is_staff = True
user.is_superuser = False
user.set_password(password)     # :87  reescribe la contraseña SIEMPRE
user.save()
user.groups.set([grupo])        # :89  reemplaza los grupos
user.user_permissions.clear()   # :90  borra permisos individuales
```

Son **tres** efectos distintos, con consecuencias que no se parecen entre sí:

1. **La contraseña vuelve al valor de la variable de entorno.** Si el médico
   cambia su clave en el Admin, el siguiente despliegue o reinicio se la revierte
   **en silencio**. No hay aviso ni error: la cuenta simplemente vuelve a la
   contraseña del operador.
2. **Los permisos concedidos a mano desaparecen.** `groups.set` + `clear()`
   devuelven la cuenta al perfil del grupo `Médicos`.
3. **El correo se borra si falta la variable.** `email` sale de
   `os.environ.get('DJANGO_MEDICO_EMAIL', '')` y se asigna **siempre**, sin la
   guarda `if email:` que su gemelo `crear_admin.py:47` sí tiene. Con
   `DJANGO_MEDICO_USERNAME`/`PASSWORD` puestas y `EMAIL` ausente, cada arranque
   deja el campo vacío. **Y ese campo es el destinatario de las alertas:**
   `notificaciones.py:105-106` y `signals.py:32` leen `medico.email`; sin él,
   `_enviar` levanta `DestinatarioNoConfigurado` (`notificaciones.py:109`) y la
   alerta ALTA **no llega al médico**. Queda registrada como entrega fallida, no
   se pierde sin rastro, pero no llega.

**Nada de esto está fijado por una prueba.** `CrearMedicoCommandTests`
(`tests/test_commands.py:776`) tiene tres casos —sin credenciales, creación
nueva, y rechazo de superusuario— y **ninguno ejercita la cuenta que ya existe**,
que es justo el caso del problema. Su gemelo `CrearAdminCommandTests:761` sí
tiene `test_actualiza_password_de_usuario_existente`. La diferencia importa: en
`crear_admin` la reescritura es un requisito decidido y probado —su propio
docstring la declara y explica cómo desactivarla—; en `crear_medico` es un efecto
heredado de copiar la forma, que **nadie decidió y nada protege.**

### Decisión

**`crear_medico` hace lo que su nombre dice: crear.** Reescribe solo cuando
alguien lo pide a propósito — con una excepción deliberada, los permisos.

1. **La contraseña no se toca si la cuenta ya existe.** `set_password` se ejecuta
   únicamente cuando el usuario se crea.
2. **Vía explícita para rotarla:** con `DJANGO_MEDICO_RESET=1` en el entorno, el
   comando sí reescribe las credenciales. La guarda vive **dentro del comando**,
   en Python, no en el shell del arranque.
3. **Los grupos y los permisos individuales se siguen reescribiendo en cada
   arranque.** No es un descuido: es la garantía de privilegio mínimo, y a partir
   de esta ficha es comportamiento **declarado**, no efecto colateral.
4. **El correo deja de borrarse.** Se le añade la misma guarda `if email:` que
   tiene `crear_admin`.

### Razonamiento

**Por qué la contraseña sí y los permisos no.** Es la pregunta que decide la
ficha, y las dos mitades tienen respuestas opuestas a propósito. Una persona
espera **gobernar su propia contraseña**: que un despliegue se la revierta sin
avisar es una promesa rota, y encima obliga a que el operador conozca la clave
del médico para siempre. Nadie, en cambio, espera gobernar sus propios permisos.
En una cuenta con acceso a datos clínicos, que el perfil sea reproducible y
vuelva siempre al aprobado vale más que la comodidad de conceder un permiso
suelto desde el Admin: un permiso extra que sobrevive callado a los despliegues
es una cuenta que deriva sin que nadie lo note. Si el médico necesita más
permisos, se cambian los del grupo `Médicos` en `PERMISOS_MEDICO` y quedan
escritos en el repositorio, que es donde deben verse.

**Por qué una variable de entorno y no un flag de línea de comandos.** El
arranque es un comando fijo dentro del `Dockerfile` y de `nixpacks.toml`; añadir
`--forzar-credenciales` ahí lo dejaría permanente, que es exactamente lo que se
quiere evitar. Una variable se pone y se quita desde el panel del servicio sin
tocar código. Además **el proyecto ya usa ese patrón**: `Dockerfile:35` hace
`[ "$RESET_AXES" = "1" ] && ... axes_reset`. No se inventa un mecanismo nuevo.

**Por qué la guarda va en Python y no en el shell, como sí está la de axes.**
Porque los dos archivos de arranque **ya divergen**: el bloque de `RESET_AXES`
está en el `Dockerfile` y **no** en `nixpacks.toml`. Una guarda escrita en el
shell hay que acordarse de replicarla en los dos sitios, y el precedente dice que
eso no ocurre. Dentro del comando protege igual, lo invoque quien lo invoque.

**Por qué el correo entra en esta ficha y no en otra.** Es el mismo comando, el
mismo arranque y el mismo tipo de fallo —reescribir en silencio algo que nadie
pidió—, y son tres líneas del mismo archivo. Separarlo sería ceremonia sin
beneficio, con el agravante de dejar conocido y sin arreglar un fallo que afecta
la **entrega de alertas clínicas**.

**Lo que esta decisión no resuelve.** `crear_medico` sigue **sin `|| true`** en
el arranque, así que aborta el despliegue si solo una de
`DJANGO_MEDICO_USERNAME`/`PASSWORD` está definida, o si el usuario resulta ser
superusuario. Es deliberado —un error de configuración de una cuenta con acceso
clínico debe ser ruidoso— y queda documentado en `docs/trampas_conocidas.md`. No
se toca aquí.

**Qué desbloquea.** La decisión abierta de `medico_piloto` (CLAUDE.md, "Por
resolver antes del piloto real", punto 2): hoy esa cuenta **no puede tener una
contraseña propia que sobreviva a un despliegue**, y por eso la pregunta de si se
transfiere o se crea una nueva no era solo administrativa. Implementada D15, deja
de serlo.

### Implementación — hecha el 12/08/2026

Rama `crear-medico-no-reescribe`, con el método del proyecto.

| Commit | Contenido |
|---|---|
| `84b684c` | `test: reproducir que crear_medico reescribe la cuenta en cada arranque` — cuatro pruebas |
| `2e02384` | `fix: crear_medico deja de reescribir contrasena y correo en cada arranque` |

**El rojo, con su mensaje exacto.** De las cuatro pruebas, dos nacieron en rojo y
son el hallazgo reproducido: la contraseña elegida por la médica no sobrevivía
(`False is not true`) y el correo se vaciaba (`'' != 'doctora@example.com'`). El
borrado del email pasó así de deducción leyendo el código a hecho reproducido.

**Las dos que nacieron en verde, y por qué no es lo mismo.** La de los permisos
declarativos pasa por la **razón correcta**: fija como requisito algo que ya
funcionaba así y que esta ficha decide conservar. La de `DJANGO_MEDICO_RESET=1`
pasaba por la **razón equivocada** —el comando reescribía siempre, mirara o no la
variable—, así que antes del `fix` no demostraba nada.

**Verificación en las dos direcciones (dos sabotajes, restaurados con `git
checkout --`):**

| Sabotaje | Resultado |
|---|---|
| `if creado or forzar_credenciales` → `if creado` (ignorar la variable de reset) | Cae `test_reset_explicito_si_reescribe_la_password`, **y solo esa** |
| Retirar `user.user_permissions.clear()` | Cae `test_los_permisos_si_vuelven_al_perfil_aprobado_en_cada_arranque`, **y solo esa** |

El segundo sabotaje dejó un dato que conviene registrar: la prueba que **ya
existía** (`test_crea_staff_no_superusuario_sin_permisos_extra`) **no cayó**.
Comprueba `user_permissions.count() == 0` sobre una cuenta recién creada, que no
tiene permisos individuales de todas formas — así que hasta hoy **nada protegía
el `clear()`**. Es el mismo patrón del hallazgo bloqueante del 22/07: una prueba
escrita mirando el código, verde por una razón distinta de la que dice medir.

**Cierre:** **344 tests OK** (340 + 4) · `check`, `makemigrations --check` y
`check --deploy` sin issues · `git diff --check` limpio.

**Sin producción no se pudo verificar el arranque real** (Railway venció el
07/08/2026), y no hacía falta: lo que cambia es el comportamiento del comando,
no el encadenado del `CMD`. Queda un tramo que **ninguna prueba local cubre** y
conviene no darlo por probado: que Railway entregue `DJANGO_MEDICO_RESET` al
contenedor. Eso solo se ve desplegando, cuando haya plan de pago.

---

## D16 — Toda guardia automática debe poder ponerse en rojo

**Hallazgo:** auditoría de seis frentes del 07/09/2026, SEC-01 · **Loop:** Arné
· **Estado:** **Decidida** (07/09/2026).
Guion de la sesión: `proceso/instrucciones/2026-09-07_instruccion_loop_arnes.md`.

### Problema

La auditoría encontró el mismo defecto en seis sitios distintos: **las guardias
automáticas del proyecto están escritas de forma que no pueden fallar.** No es
una lista de descuidos sueltos; es un patrón, y explica por qué los otros 100
hallazgos sobrevivieron.

El caso que lo demuestra sin discusión, **reproducido ejecutándolo**:

```
$ python manage.py check --deploy      # sobre una configuración con 5 fallos
?: (security.W004) ... SECURE_HSTS_SECONDS ...
?: (security.W008) ... SECURE_SSL_REDIRECT ...
?: (security.W012) ... SESSION_COOKIE_SECURE ...
?: (security.W016) ... CSRF_COOKIE_SECURE ...
?: (security.W018) You should not have DEBUG set to True in deployment.
System check identified 5 issues (0 silenced).
>>> EXIT CODE: 0            # ← la CI queda VERDE

$ python manage.py check --deploy --fail-level WARNING
>>> EXIT CODE: 1
```

Los checks de despliegue de Django son todos de nivel **WARNING**, y
`--fail-level` vale **ERROR** por defecto. Es decir: desde que existe la CI
(31/07/2026), la comprobación «Configuración de producción» **nunca pudo
fallar**. Hoy se pueden borrar HSTS, el redirect a HTTPS y las cookies seguras y
las siete comprobaciones siguen en verde.

Los otros cinco casos del mismo patrón:

| Guardia | Por qué no protege |
|---|---|
| `gitleaks` | El `allowlist` excluye `docs/auditoria_literatura/.*` — la única carpeta con datos personales. Fue un aplazamiento declarado al «Loop G», que nunca se ejecutó |
| Las 344 pruebas | `fecaloide` no aparece en ninguna. **Sabotaje ejecutado el 07/09:** al quitarlo de `DRENAJES_ALTA`, las 344 siguen OK |
| 25 restricciones de BD | 19 nunca se han visto fallar. Un `RemoveConstraint` futuro las borra y la suite sigue verde |
| `pip-audit` | Se cita como garantía en seis documentos. **No está en la CI ni en ningún `requirements`** |
| Validadores de rango | Cero en todo el repositorio. El único control sobre un dato clínico es un regex del bot |

### Decisión

**Ninguna guardia entra ni permanece en este proyecto sin haberse visto fallar
al menos una vez.** En concreto, para esta sesión:

1. **`check --deploy` lleva `--fail-level WARNING`.** Verificado rompiendo una
   directiva a propósito y viendo la CI caer.
2. **`pip-audit` entra en la CI** y bloquea. (Al migrar a `pyproject.toml` en
   el mismo loop pasó a auditar el entorno instalado en vez de un archivo de
   requisitos, que dejó de existir.)
3. **`ruff` entra en la CI y bloquea**, con el conjunto amplio. Dos familias se
   ignoran **con el porqué escrito en la configuración**, no en silencio:
   - `RUF012` (117 hallazgos): exige anotar `list_display` y `dependencies` como
     `ClassVar`. Es un falso positivo de Django; 60 de ellos están en
     migraciones generadas.
   - `N999`: se queja del nombre `Registro_Post_Quirurgico`. Renombrarlo rompe
     `DJANGO_SETTINGS_MODULE`, el `--chdir` del `Dockerfile`, el
     `working-directory` de la CI y 28 migraciones. **Decidido no renombrar.**
   - Las **migraciones se excluyen enteras**: son código generado.
4. **Django sube a 6.0.8**, que cierra CVE-2026-15830 (`contrib.gis`, no
   explotable aquí porque la app no lo instala — pero `pip-audit` lo reportaría
   en cada corrida).

**Lo que NO se hace en esta decisión, y por qué.** De los 83 hallazgos reales de
`ruff` se aplican los **49 automáticos**; los **34 de criterio se difieren al
loop de umbrales**, no por pereza sino por secuencia: casi todos están en
`tests/`, y ese loop va a reescribir esos mismos archivos para añadir las pruebas
de frontera. Refactorizarlos hoy y reescribirlos en dos sesiones es trabajo
tirado. Además —y pesa más— **la auditoría acaba de demostrar que la suite no
protege siete de las ocho familias de reglas clínicas**: un refactor automático
masivo verificado por una red agujereada es la forma clásica de meter una
regresión silenciosa.

Los seis `BLE001` (captura de excepción a ciegas) **no se ignoran en la
configuración**: llevan `# noqa: BLE001` individual con su razón al lado, porque
los tres que se revisaron son *fail-open* deliberados y ya documentados (rate
limit degradado, health check que devuelve 503, captura del motor de
evaluación). Silenciarlos desde la configuración los volvería invisibles; el
`noqa` con razón los deja a la vista.

### Por qué esta decisión y no otra

**Por qué bloquear y no informar.** Un linter que reporta sin detener es
exactamente la guardia-que-no-puede-fallar que esta ficha viene a eliminar.
Añadirlo en modo informativo habría sido repetir el defecto mientras se lo
corrige.

**Por qué el conjunto amplio y no el estricto.** Decisión del Arquitecto
(07/09/2026): aprovechar que se va a tocar el tema para dejarlo lo mejor posible.
El conjunto estricto (`F`+`E9`) daba solo 4 hallazgos reales y habría dejado
fuera el orden de imports, las f-strings y las capturas a ciegas.

**Por qué se escribe el porqué de cada regla ignorada.** Una lista de excepciones
sin razones es una lista que crece hasta que no protege nada. El precedente está
en `.gitleaksignore`, cuya única entrada lleva cuatro razones comprobables.

---

## D17 — Qué hacer con los datos personales que ya están en la historia

**Hallazgo:** auditoría del 07/09/2026, REPO-01 · **Loop:** Arnés ·
**Estado:** **Decidida** (07/09/2026).

### Problema

`docs/auditoria_literatura/` contenía el nombre completo del médico proponente,
**su número de cédula** y sus afiliaciones institucionales. Llegó al repositorio
en `74f3e04` al cargar un documento que el propio médico proporcionó para
alimentar el contexto del proyecto.

Tres cosas lo agravan:

1. **`.gitleaks.toml` excluye esa carpeta del escaneo.** La guardia de secretos
   montada en agosto justo para esto nunca la iba a mirar. La exclusión fue
   deliberada —el comentario la aplaza al «Loop G» de higiene de identidad— pero
   ese loop nunca se ejecutó, y mientras tanto la carpeta quedó sin vigilancia.
2. **Viola una regla escrita de este mismo repositorio**: `CLAUDE.md` prohíbe
   usar nombres de instituciones.
3. **El Arquitecto redactó el archivo el 07/09/2026, pero el dato sigue en la
   historia.** Comprobado commit por commit: aparece en `74f3e04` (línea 17) y
   en `fbf62a8` (línea 21). `git show fbf62a8:<ruta>` lo sigue devolviendo
   entero, y `fbf62a8` es el commit que `CLAUDE.md` cita como base de la
   auditoría del 22/07.

En un proyecto cuyo documento legal canónico es la Ley 1581/2012, es exactamente
el tipo de dato que el sistema promete proteger.

### Decisión

1. **El árbol de trabajo queda limpio.** La cédula la redactó el Arquitecto; las
   **7 menciones de instituciones** restantes se sustituyen por descripciones
   genéricas («una universidad de Medellín»). El valor clínico no depende de
   ellas: ningún umbral cambia porque el estudio nombre o no la institución.
2. **Se retira la exclusión de `docs/auditoria_literatura/`** del
   `.gitleaks.toml`. La carpeta pasa a escanearse como el resto.
3. **Se añade una regla propia `cedula-colombiana`**, anclada a la palabra
   «cédula» para no producir falsos positivos con cualquier número.
4. **Las dos ocurrencias históricas se registran en `.gitleaksignore` con su
   razón escrita**, para que la CI siga verde y quede constancia de que la
   historia está sucia. Es el mismo patrón que ya se usó con la `SECRET_KEY` del
   Sprint 0.
5. **La reescritura de la historia queda como decisión aparte**, atada a si el
   repositorio va a ser público.

### Por qué no se reescribe la historia ahora

Borrar el dato del pasado exige `git filter-repo`, que **reescribe todos los
SHA**. Eso rompe las referencias de los cinco informes de auditoría, las URLs de
los veinte PR mergeados y las citas de `CLAUDE.md` — incluido `fbf62a8`. El
repositorio es **privado**, así que el dato solo es alcanzable por quien ya tiene
acceso: los dos miembros del equipo.

**Esto no cierra el asunto, lo acota.** Si el repositorio pasa a público, la
reescritura deja de ser opcional. Y aunque siga privado, el titular del dato es
un tercero identificable que no consintió su publicación en un repositorio de
código: **conviene decírselo y preguntarle qué prefiere.** Esa conversación es
del Arquitecto, no del equipo técnico, y queda anotada aquí para que no se
pierda.

---

## D18 — Qué es producto y qué es cuaderno de trabajo

**Hallazgo:** auditoría del 07/09/2026, REPO-01 a REPO-21 · **Loop:** Repositorio
· **Estado:** **Decidida** (07/09/2026).

### Problema

De cada 100 KB de documentación del repositorio, **solo 12 describían el
producto**. El resto —59 % proceso puro, 21 % mixto— era cómo trabajan dos
personas, y estaba en la portada.

Consecuencias concretas, medidas:

- **No había `README.md` en la raíz.** Lo primero que veía quien abría el
  repositorio era `BITACORA.md`, 277 KB.
- **No había licencia.** El estado legal por defecto ya era "todos los derechos
  reservados", pero nadie podía saberlo mirando.
- **No había una sola instrucción de instalación** en los 44 documentos. Lo más
  parecido era una ruta absoluta de la máquina del Arquitecto apuntando a un
  entorno virtual que no existía.
- **`requirements.txt` (214 líneas) era un `pip freeze`** de esa misma máquina,
  con TensorFlow, Jupyter y paquetes solo-Windows. No lo usaba nadie —el
  Dockerfile y la CI instalaban los otros dos— pero era el primero que abría
  cualquiera, y le faltaban `gunicorn` y `whitenoise`.
- **Ni una captura de pantalla.** Para un panel médico que se quiere enseñar a un
  médico y a un desarrollador externo, es la ausencia más cara.

### Decisión

**1 · `docs/` es producto. `proceso/` es cuaderno.** La bitácora, los informes
de auditoría, los guiones de sesión y los scripts de verificación se mueven a
`proceso/`, un nivel por encima de `docs/`. Se **mueven, no se parten**: el
ROADMAP y el archivo de decisiones se quedan enteros por ahora, porque partirlos
rompe las referencias de los cinco informes de auditoría y ese coste no compra
nada hoy.

**2 · Licencia: todos los derechos reservados, explícita.** El médico proponente
puede ser adquiriente, y el núcleo del trabajo —las reglas y su respaldo en
literatura— conserva valor comercial. Una licencia permisiva lo regalaría antes
de que exista esa conversación. Ampliarla después siempre es posible; al revés,
no. El `LICENSE` incluye además el **aviso clínico**: esto no es un dispositivo
médico certificado.

**3 · `pyproject.toml` como fuente única de dependencias.** Se borran los tres
`requirements*.txt`. El `Dockerfile` pasa a `pip install .` y la CI a
`pip install -e ".[dev]"`. Las nueve dependencias de runtime se comprobaron
contra los `import` reales del código: no sobra ninguna.

**4 · Lo que NO se toca: el nombre del repositorio ni la carpeta anidada.** Tres
directorios llamados `Registro_Post_Quirurgico` confunden, y renombrarlos rompe
`DJANGO_SETTINGS_MODULE`, el `--chdir` del `Dockerfile`, el `working-directory`
de la CI, `wsgi.py`, `asgi.py` y las referencias de 28 migraciones. Se resuelve
con tres líneas en el README, no con un `git mv`.

**5 · `CODEOWNERS` le da fuerza mecánica a una regla que ya existía.** `CLAUDE.md`
dice desde el principio que ninguna regla clínica se cambia sin el Arquitecto;
hasta hoy eso dependía de que alguien se acordara. Ahora GitHub pide su revisión
automáticamente cuando un PR toca `alert_engine.py`, `bot.py`, `models.py`, las
reglas clínicas o la evidencia. Sin protección de rama **solicita** la revisión,
no la exige — es un recordatorio automático, como los checks.

**6 · Las capturas del panel** entraron el mismo día en el PR #27 (`ceaba8c`),
con datos ficticios y su propio `docs/img/README.md` de cómo regenerarlas. Una
lección operativa que quedó de hacerlas: **con un solo paciente el tablero parece
vacío** y la imagen no explica nada. Hacen falta tres —uno complicado, uno
intermedio y uno tranquilo— y por eso el README de `docs/img/` manda correr
también `seed_demo_produccion`.

### Lo que este loop dejó a la vista y no resolvió

Mover documentación **rompió dos scripts de verificación** que calculaban la raíz
del repositorio contando carpetas (`parents[3]`). Fallaban en silencio: se ponían
a mirar el directorio equivocado. Se cambiaron por una búsqueda del `.git`, que
sobrevive a cualquier mudanza futura. Es el mismo patrón de D16 —una guardia que
falla sin avisar— apareciendo en las propias verificaciones.

---

## Método de trabajo acordado

Aplica a los tres loops de corrección.

1. **Decidir antes de implementar.** Ninguna decisión clínica o de producto se
   toma dentro del código. Las siete fichas de arriba se aprobaron una por una
   antes de escribir una sola línea.
2. **Test en rojo primero.** Para cada corrección de comportamiento se escribe
   la prueba que modela la realidad, se la ve fallar, y solo entonces se toca el
   código. Motivo: el hallazgo 1 sobrevivió a 280 pruebas en verde porque la
   prueba se escribió mirando el código en vez del requisito. Una prueba que
   nace en verde no demuestra nada.
3. **Verificación del Arquitecto al cerrar cada loop.** No basta con que el
   agente informe que quedó bien; León ejecuta una comprobación propia antes de
   pasar al siguiente loop.
4. **Un loop por sesión.** Cada loop cierra con sus commits, push y entrada de
   BITACORA. La sesión siguiente arranca leyendo este documento, sin depender de
   la memoria de la conversación anterior.
5. **Sincronización documental no diferible.** Todo cambio que se refleje en una
   tabla de referencia de CLAUDE.md o del ROADMAP se actualiza en el mismo lote
   de commits (regla ya vigente en CLAUDE.md).

---

## Plan de ejecución  *(sección temporal — podar al cerrar los loops)*

> Esta sección describe trabajo en curso y **deja de ser útil cuando los tres
> loops cierren**. Las fichas D1-D7 de arriba son permanentes; esto no.

**Punto de restauración:** `fbf62a8`, publicado en `origin/sprint-5-produccion`.

### Loop A — Corrección clínica *(único que bloquea el merge)*

| # | Commit | Contenido |
|---|---|---|
| A1 | `test: reproducir escalera de silencio con el scheduler real` | En rojo |
| A2 | `fix: corregir el conteo de racha en alertas de silencio` | D1 |
| A3 | `fix: retirar el umbral clinico del mensaje de fiebre al paciente` | D4 |
| A4 | `feat: conservar los signos concurrentes de ileo en el detalle` | D5 |
| A5 | `docs: sincronizar reglas del motor y consulta pendiente al medico` | Tablas + consulta |

**Cierre:** suite completa en verde · `makemigrations --check` sin cambios ·
`check --deploy` limpio · A1 pasa de rojo a verde · verificación de León.

### Loop B — Trazabilidad y operación

| # | Commit | Contenido |
|---|---|---|
| B1 | `test: cubrir degradacion de cache y agotamiento de reintentos` | En rojo |
| B2 | `fix: degradar el rate limit sin bloquear al paciente` | D2 (1-4) |
| B3 | `feat: registrar quien resuelve cada alerta` | D3 + migración 0025 |
| B4 | `feat: limitar reintentos y exponer entregas fallidas` | D6 |
| B5 | `feat: endpoint de salud para monitoreo externo` | D2 (5) |
| B6 | `fix: acotar el bloqueo de filas durante el envio de correo` | Hallazgo 2 |
| B7 | `docs: operacion, monitoreo y trazabilidad de resolucion` | Docs |

**Cierre:** suite en verde · migración aplicada y reversible · `/salud/`
responde 200 y 503 según corresponda.

### Loop C — Coherencia e higiene

| # | Commit | Contenido |
|---|---|---|
| C1 | `fix: condicionar la confianza en cabeceras de proxy` | Hallazgo 6 |
| C2 | `fix: conservar el estado de error del motor en la ruta del bot` | Hallazgo 7 |
| C3 | `fix: no exponer otras cuentas medicas en los filtros` | Hallazgo 8 |
| C4 | `fix: validar variables de entorno vacias al arrancar` | Hallazgo 11 |
| C5 | `docs: corregir CLAUDE.md, comentarios de migracion y despliegue` | Hallazgos 9, 14 + discrepancias |
| C6 | *(sin commit de código)* | D7 — consulta y anotación en BITACORA |

**Cierre:** suite en verde · `check --deploy` limpio · `pip-audit` limpio · sin
contradicciones entre CLAUDE.md, ROADMAP y código.

### Después

Entrada final de BITACORA cerrando los tres loops, revisión del diff completo
contra `Desarrollo`, y PR. Los 14 hallazgos de la auditoría quedan cubiertos.

---

## Qué NO resuelven estos loops

Requisitos externos para el piloto real, ninguno resoluble en código:

1. WhatsApp Business API con número aprobado, facturación y plantillas.
2. `enviar_recordatorios` sigue siendo un stub: el bot es reactivo y el paciente
   debe escribir primero.
3. Dominio propio autenticado en Resend con SPF/DKIM/DMARC.
4. Monitor externo configurado apuntando a `/salud/` (el endpoint lo entrega el
   Loop B; darlo de alta es una tarea de operación).
5. Plan de Railway que permita un `cron-operativo` separado.
6. **HABEAS DATA completado y firmado antes del primer paciente real.** Los
   campos entre corchetes de `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` siguen
   vacíos. Probar con el equipo no lo requiere; una persona real como paciente,
   sí — Ley 1581/2012.
7. Datos reales del médico en la landing y `MOSTRAR_AVISO_BOCETO = False`.
8. Validación médica de las respuestas del bot (ver D4).
