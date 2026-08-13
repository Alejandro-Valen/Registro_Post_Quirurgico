# Proceso de trabajo con agentes de código

> **Qué hay aquí.** Los documentos que describen **cómo se trabaja** en este
> proyecto con agentes de código (Claude Code, Codex): instrucciones de
> auditoría, scripts de verificación y el método de corrección por loops.
>
> **Qué NO hay aquí.** Nada sobre cómo funciona el sistema. Las reglas clínicas,
> los modelos, el bot y el despliegue viven en `docs/`. Si buscas cómo se
> comporta el software, esta carpeta no es el lugar.

---

## Por qué existe esta carpeta

Estos archivos son **andamiaje, no producto**. Sirvieron para construir el
sistema y para verificarlo, pero un día podrán archivarse sin que el proyecto
pierda nada. Separarlos permite podarlos con confianza: si estuvieran mezclados
con la documentación del producto, nadie se atrevería a borrar nada.

También responden a una necesidad concreta del proyecto: **el trabajo lo hacen
agentes distintos en sesiones que no comparten memoria.** Lo que aquí se escribe
es lo que permite que una sesión nueva —o un agente distinto, o una persona—
retome sin depender de una conversación que ya no existe.

## Estructura

```
docs/proceso/
├── README.md              Este archivo
├── metodo_de_trabajo.md   Cómo se corrige algo en este proyecto: el método de loops
├── AAAA-MM-DD_instruccion_*.md   El guion de una sesión concreta (ver abajo)
├── auditorias/            Instrucciones e informes de revisión independiente
└── verificaciones/        Scripts que el Arquitecto ejecuta él mismo para comprobar
```

## Instrucciones de sesión

Cada una es el guion que deja una sesión para la siguiente: dónde quedamos, el
prompt de arranque, el objetivo, y lo que NO se hace. Existen porque el trabajo
lo hacen agentes que no comparten memoria.

| Archivo | Objetivo | Estado |
|---|---|---|
| `2026-07-28_instruccion_cierre_rama_sprint5.md` | Cerrar la rama del Sprint 5: diff, PR, merge, rama `produccion` | **Ejecutada** el 29/07/2026. Sus 4 pasos están hechos |
| `2026-07-30_instruccion_sprint6_ci.md` | Montar CI en `sprint-6-ci` — punto 1 de los 8 de la revisión del PR | **Ejecutada** el 31/07/2026. PR #5 (`5b40c01`), verificación en rojo de las 5 comprobaciones |
| `2026-08-01_instruccion_loop_e.md` | Loop E — D14, aislar las tareas del cron conservando la dependencia clínica de `cron_matutino` | **Ejecutada** el 07/08/2026. PR #10 (`4fc690d`), 340 tests OK, cierra D1-D14 |
| `2026-08-07_instruccion_partir_tests.md` | Partir `signos_sintomas/tests.py` (6.288 líneas, 46 clases) en un paquete `tests/` | **Ejecutada** el 10/08/2026. PR #12 (`427153b`), nueve archivos, 340 tests y los 305 métodos comparados uno a uno |
| `2026-08-10_instruccion_crear_medico.md` | La decisión sobre `crear_medico`, que reescribe la cuenta del médico en cada arranque | **Ejecutada** el 12/08/2026. Ficha **D15** decidida e implementada el mismo día: PR #17 (`1396744`), 344 tests OK, cierra D1-D15 |
| `2026-08-12_instruccion_siguiente_sesion.md` | **Sin objetivo impuesto.** Cuatro candidatos con sus consecuencias, para que el Arquitecto elija en sesión | **Vigente.** Es el guion de la próxima sesión |

**Convención de nombres:** los archivos van con fecha al inicio
(`2026-07-22_...`), porque son documentos de un momento y no fuentes vivas. La
fecha permite ordenarlos y podarlos por antigüedad.

## Auditorías

| Archivo | Qué es | Estado |
|---------|--------|--------|
| `auditorias/2026-06_informe_sprint3_cierre.md` | Diagnóstico previo al Sprint 3-Hardening | Histórico. Sus hallazgos no son actuales |
| `auditorias/2026-07-22_instruccion_loops_1_6.md` | Instrucción de la auditoría independiente pre-merge | **Ya ejecutada.** Sus 14 hallazgos están corregidos en los Loops A, B y C |
| `auditorias/2026-07-27_informe_cierre_codex.md` | Informe de la auditoría de cierre (Codex) y el resultado de reproducir cada hallazgo | **Ya ejecutada.** Sus 4 hallazgos están corregidos en el Loop D |
| `auditorias/2026-07-29_revision_pr_sprint5.md` | Revisión de ingeniería del PR #3: los 8 puntos de deuda técnica que quedan y **en qué punto del flujo se atiende cada uno** | **Vigente.** No bloquea el merge. Es la referencia para secuenciar el trabajo posterior al Sprint 5 |

Las auditorías de este proyecto siguen un patrón que funcionó: **una instrucción
escrita y versionada**, ejecutada por un agente distinto del que escribió el
código, con prohibición explícita de editar. La del 22/07/2026 encontró un bug
que había sobrevivido a 280 pruebas en verde.

## Verificaciones

Scripts que **ejecuta el Arquitecto**, no el agente. Existen porque el método
exige que quien aprueba vea la evidencia con sus propios ojos, en vez de confiar
en el informe de quien hizo el trabajo.

Se corren contra una base de datos de prueba desechable y **no tocan datos
reales**. Cada uno imprime en pantalla el antes y el después de lo que
verifica.

```powershell
cd Registro_Post_Quirurgico
$env:PYTHONPATH = "../docs/proceso/verificaciones"
python manage.py test 2026-07-25_verificacion_loop_c -v 2 --noinput
Remove-Item Env:PYTHONPATH
```

> El comando de arriba **funciona tal cual**: el cargador de pruebas de Django
> importa el módulo por nombre y el nombre con fecha no le estorba. La nota
> anterior decía lo contrario y mandaba a copiar el archivo con otro nombre —
> era falso, y se corrigió en el Loop D (hallazgo 4 de la auditoría de cierre).
>
> Verificado el 27/07/2026: 6 pruebas, OK. Sus fixtures se ajustaron ese día
> para pasarle un `medico_responsable`, que la migración 0028 volvió
> obligatorio en todo paciente activo; lo que la verificación comprueba no
> cambió.

**No todos se corren igual.** Los de arriba son pruebas de Django y se lanzan con
`manage.py test`. El de la guardia de secretos **no**: es un script suelto,
porque lo que verifica no es el comportamiento de la aplicación sino el de la
CI. Se corre directo, y **necesita `gitleaks`, que la máquina de desarrollo no
trae de fábrica**:

```powershell
winget install Gitleaks.Gitleaks      # una sola vez; sirve la 8.30.1, la de ci.yml
gitleaks version                       # comprobar que quedó en el PATH
python docs/proceso/verificaciones/2026-08-10_verificacion_guardia_secretos.py
```

Que la versión local coincida con la fijada en `ci.yml` no es cosmético: una
distinta puede dar otro resultado y mandar a buscar un problema que no existe.

Comprueba las **dos** direcciones: que tres secretos distintos detienen la CI, y
que dos formas correctas de escribir una `SECRET_KEY` la dejan pasar. La segunda
mitad no es adorno — y la cabecera del script cuenta los dos tropiezos que hubo
al escribirlo, ambos del tipo que da por bueno un arnés roto.

## Cuándo se puede borrar todo esto

Cuando el proyecto tenga un equipo estable que no dependa de agentes para
retomar contexto. Mientras el trabajo siga siendo "una sesión nueva cada vez",
esta carpeta es lo que evita repetir errores ya cometidos.
