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
├── auditorias/            Instrucciones e informes de revisión independiente
└── verificaciones/        Scripts que el Arquitecto ejecuta él mismo para comprobar
```

**Convención de nombres:** los archivos van con fecha al inicio
(`2026-07-22_...`), porque son documentos de un momento y no fuentes vivas. La
fecha permite ordenarlos y podarlos por antigüedad.

## Auditorías

| Archivo | Qué es | Estado |
|---------|--------|--------|
| `auditorias/2026-06_informe_sprint3_cierre.md` | Diagnóstico previo al Sprint 3-Hardening | Histórico. Sus hallazgos no son actuales |
| `auditorias/2026-07-22_instruccion_loops_1_6.md` | Instrucción de la auditoría independiente pre-merge | **Ya ejecutada.** Sus 14 hallazgos están corregidos en los Loops A, B y C |

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

> El nombre de módulo con fecha no es importable directamente en Python; para
> ejecutarlo, cópialo con un nombre sin guiones ni cifras iniciales (por
> ejemplo `verificacion_loop_c.py`) o ábrelo y adapta el comando. Se conserva
> con fecha porque su valor es de archivo histórico, no de uso frecuente.

## Cuándo se puede borrar todo esto

Cuando el proyecto tenga un equipo estable que no dependa de agentes para
retomar contexto. Mientras el trabajo siga siendo "una sesión nueva cada vez",
esta carpeta es lo que evita repetir errores ya cometidos.
