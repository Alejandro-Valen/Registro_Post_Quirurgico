# Instrucción para la próxima sesión — anclar los umbrales clínicos

> **Qué es esto.** El guion de la sesión que sigue a la auditoría de seis frentes
> y a los loops del arnés y del repositorio. Se escribió el 07/09/2026.
>
> **En qué se diferencia del anterior:** el guion del 12/08 no traía objetivo, a
> propósito. **Este sí, y no es una elección entre candidatos.** La auditoría lo
> convirtió en el trabajo obligado, con una demostración ejecutada.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**07/09/2026 — dos PR mergeados el mismo día:**

| PR | Qué | Merge |
|---|---|---|
| #18 | Reparar el arnés de verificación: que las guardias puedan fallar (D16, D17) | `5f51831` |
| #19 | Separar el producto del cuaderno de trabajo (D18) | `591cd7c` |

**Suite: 344 tests OK.** **La CI corre nueve comprobaciones**, no siete.
**Rama activa de trabajo: ninguna.**

**Sigue sin haber producción** (venció Railway el 07/08/2026). No proponer nada
que dependa de desplegar.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo. Soy León (Arquitecto).

Antes de tocar nada:
1. Lee proceso/instrucciones/2026-09-07_instruccion_umbrales.md — es el guion de
   esta sesión.
2. Verifica el estado real con git log, git status, ruff y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

El objetivo está decidido: anclar los umbrales clínicos con pruebas de frontera.
Un loop, un tema. No abras nada más.

Ten en cuenta que no hay produccion en Railway. Y que las decisiones sobre el
canal del paciente, el repositorio publico y avisarle al medico NO son de esta
sesion: van a la reunion con el equipo.
```

---

## El objetivo, y por qué no es negociable

El 07/09/2026 se ejecutó este sabotaje sobre `alert_engine.py:16`:

```diff
- DRENAJES_ALTA  = ('purulento', 'fecaloide')
+ DRENAJES_ALTA  = ('purulento',)
```

Y después la suite completa:

```
Ran 344 tests in 283.581s

OK
```

**Ni una prueba cayó.** Con esa línea así, un paciente puede reportar contenido
intestinal saliendo por el drenaje —una fuga anastomótica franca, el peor signo
que captura el sistema— y no se genera ninguna alerta.

No es un caso aislado. `fecaloide` **no aparece ni una vez** en los once archivos
de prueba; tampoco `dolor_eva=7` ni `episodios_nauseas=3`. De 18 sabotajes de una
línea que propuso la auditoría, **14 pasarían sin que caiga nada**.

## Qué hay que hacer

Aplicar a las siete familias de reglas restantes **el patrón que la Regla 8
(frecuencia cardíaca) ya tiene en casa**: para cada umbral, una prueba con el
valor que dispara **y otra con el valor inmediatamente inferior, que NO debe
disparar**.

La Regla 8 y la escalera SILENCIO son las únicas dos zonas con frontera completa
del proyecto — y no por casualidad: son las dos que pasaron por una auditoría
previa. Ahí está el modelo a copiar: `test_alert_engine.py:951-1022` prueba
100/101/109/110/149/150 y `None`.

**Empezar por los cinco de más peso**, en este orden:

| # | Sabotaje que hoy pasaría | Prueba que falta |
|---|---|---|
| 1 | quitar `fecaloide` de `DRENAJES_ALTA` | drenaje fecaloide → FUGA / ALTA |
| 2 | `bot.py:617`, `'4': 'purulento'` → `'seroso'` | un flujo del bot por cada opción 1-5 del menú de drenaje |
| 3 | `TEMPERATURA_ALTA` 37.9 → 37.8 | 37,8 → **sin** alerta ALTA (la frontera) |
| 4 | `NAUSEAS_MEDIA_MIN` 3 → 4 | 3 episodios → MEDIA |
| 5 | `VENTANAS_DOLOR` (2, 5, 7, 9) → (2, 5, 8, 9) | POD 1-2 con EVA 7 → MEDIA |

Después, el resto de las fronteras: 4e y 7c con 3 días, 5b con Δ=2, la ventana
POD 3-5 completa, y el corte de conteo de D8 (día-1 / hueco / día+1) para las
reglas 1b, 3, 4 y 6.

Son unas **25 pruebas**. La lista completa de los 18 sabotajes está en el informe
de la auditoría de pruebas.

## La regla que hace útil este loop

**Cada prueba nueva se verifica aplicando su sabotaje ANTES de darla por buena.**

Una prueba de frontera escrita sin comprobar que cae es exactamente el error que
esta auditoría acaba de encontrar catorce veces. Si la prueba nace en verde, no
sabe lo que dice saber.

El procedimiento por prueba:

1. Escribir la prueba.
2. Aplicar el sabotaje de su fila. **Ver caer la prueba.**
3. Restaurar el código con `git checkout --`.
4. Ver la prueba pasar.
5. Solo entonces, commit.

Cuando una prueba no pueda nacer en rojo —porque congela un comportamiento
correcto en vez de denunciar un defecto—, **decirlo en su docstring**.

---

## Lo que NO se hace en esta sesión

- **No se cambia ningún umbral.** Este loop **fija** lo que ya está decidido, no
  lo revisa. Si al escribir una prueba aparece la duda de si el umbral es el
  correcto, **se anota y se sigue** — esa es una pregunta para el médico, no para
  esta sesión.
- **No se tocan los bugs del paciente.** Van en el loop siguiente. Un loop, un
  tema.
- **No se abordan los 34 hallazgos de criterio del linter.** Están diferidos a
  propósito hasta que la red aguante, que es lo que este loop construye.
- **No se decide el canal, ni público/privado, ni se avisa al médico.** Esas tres
  van a la reunión con Alejandro, el médico y el profesional de desarrollo.
- **No se propone nada que dependa de desplegar.** No hay dónde.

---

## Lo que quedó pendiente y no es de este loop

- **Siete PR de Dependabot abiertos** (#20 a #26). Se abrieron solos en cuanto el
  `dependabot.yml` entró con el PR #19 — está haciendo su trabajo, pero siete PR
  de golpe son ruido, y **dos no son rutinarios**:

  | PR | Salto | Por qué esperar |
  |---|---|---|
  | **#23** | `django 6.0.8 → 6.1.1` | Versión **menor**: puede traer deprecaciones |
  | **#26** | `django-axes 7.0.1 → 8.3.1` | Versión **MAYOR**, y es el que bloquea los intentos de acceso al panel del médico |
  | #20, #21 | `actions/checkout 5→7`, `setup-python 6→7` | Mayores, pero solo de la CI |
  | #22, #24, #25 | twilio, requests, redis | Menores rutinarias, sin prisa |

  **Los dos primeros pasan las nueve comprobaciones, y ese verde vale menos de
  lo que parece.** `django-axes` es el del hallazgo SEC-02 —bloquea por IP, y
  detrás del edge de Railway esa IP es una sola—; un salto mayor puede cambiar
  ese comportamiento en cualquier dirección y **no hay una prueba que lo fije**.
  Y el salto de Django pasa una suite que este mismo loop viene a arreglar
  precisamente porque no protege siete de las ocho familias de reglas.

  **Recomendación: mergear los tres menores cuando se quiera, y dejar #23 y #26
  para después de este loop**, cuando la red aguante.

  **Y afinar el `dependabot.yml`:** se configuró agrupando solo los parches, por
  eso cada versión menor abrió su propio PR. Agrupando también las menores esto
  sería **un PR mensual en vez de siete**. Fue un error de calibración al
  escribirlo el 07/09.

- **La cédula del médico sigue en la historia de git.** Fuera del árbol, pero
  recuperable con `git show`. Registrada en `.gitleaksignore` con lo que falta
  decidir.

- **Las capturas del panel: hechas** (PR #27, 07/09/2026). Están en `docs/img/`
  con su propio README explicando cómo regenerarlas.

---

## Un recordatorio de método

La lección de esta auditoría, en una línea, y sirve más allá de las pruebas:

> **Una guardia que nunca se ha visto fallar no protege: tranquiliza.**

Se encontró en seis sitios el mismo día —la CI, el escáner de secretos, las
pruebas, las restricciones de base, el auditor de dependencias, los validadores
de rango— y volvió a aparecer dos veces más *durante* la corrección: en los
scripts de verificación que calculaban mal su propia ruta, y en el intento de
quitar `--strict` a `pip-audit` para que un check pasara.

Esa última es la que conviene recordar: **la tentación de debilitar una guardia
para que el semáforo se ponga verde es exactamente el defecto que la guardia
existe para impedir.**
