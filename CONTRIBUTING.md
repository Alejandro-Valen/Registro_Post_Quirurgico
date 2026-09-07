# Cómo se trabaja en este proyecto

Este es un sistema que clasifica señales de alarma médicas. Eso cambia lo que
significa "un cambio pequeño": una constante movida un punto puede ser la
diferencia entre avisar y no avisar de una fuga anastomótica.

Las reglas de abajo no son ceremonia. Cada una existe porque su ausencia costó
algo concreto, y está anotado cuál.

---

## La regla que no se negocia

**Ninguna regla, umbral o mensaje clínico se cambia sin decisión explícita del
responsable clínico del proyecto.** Ni "de paso", ni "para que quede más
limpio", ni porque un linter lo sugiera.

Los umbrales tienen base en evidencia de recuperación postoperatoria colorrectal
y están trazados uno a uno en [`docs/reglas_clinicas.md`](docs/reglas_clinicas.md),
que es su **fuente única**: si otro documento los repite, ese otro está
desactualizado por definición.

## Antes de escribir código

1. **Lee el documento dueño de lo que vas a tocar.** El mapa está en
   [`CLAUDE.md`](CLAUDE.md); cada documento dice explícitamente cuándo es
   obligatorio leerlo. Si vas a tocar despliegue o cron,
   [`docs/trampas_conocidas.md`](docs/trampas_conocidas.md) no es opcional.
2. **Verifica el estado real con comandos**, no con lo que diga un documento.
   Si el código y el documento se contradicen, **manda el código** — y corrige
   el documento en el mismo commit.
3. **Escribe la decisión antes de programarla.** Las decisiones de diseño,
   clínicas o de producto van a
   [`docs/decisiones_correccion_auditoria.md`](docs/decisiones_correccion_auditoria.md)
   con su razonamiento, antes de tocar un archivo. Una decisión tomada mientras
   se escribe código queda justificada por lo que era cómodo de programar.

## El ciclo

```
decidir → documentar → prueba en rojo → implementar → verificar en las dos direcciones
```

**La prueba en rojo primero, y hay que verla caer.** No es un trámite: durante
la corrección de julio aparecieron dos pruebas recién escritas que pasaban por
la razón equivocada, y se detectaron precisamente porque se exigió ver el rojo
y entenderlo.

> **Un test en verde no prueba nada si no se sabe por qué está verde.**

Cuando una prueba no puede nacer en rojo —porque congela un comportamiento
existente en vez de denunciar un defecto— **se dice en su docstring**.

**Verificar en las dos direcciones** significa comprobar que la prueba atrapa lo
que debe atrapar *y* que deja pasar lo que debe pasar. Comprobar solo la primera
mitad es cómo se da por bueno un arnés roto. Y cuando puedas, añade la tercera:
anula la corrección y comprueba que la prueba vuelve a caer.

El razonamiento completo, con los casos reales que originaron cada regla, está
en [`proceso/metodo_de_trabajo.md`](proceso/metodo_de_trabajo.md).

## Ramas y commits

- Rama principal: **`Desarrollo`**. **Nadie trabaja directo ahí.**
- Una rama por tema, con nombre descriptivo: `arnes-verificable`,
  `crear-medico-no-reescribe`, `guardia-secretos`.
- Rama de despliegue: `produccion`. Solo recibe merges desde `Desarrollo`.
- Commits en **español**, con prefijo: `feat:`, `fix:`, `docs:`, `ci:`, `test:`,
  `chore:`.
- **Código y documentación van en commits separados.**
- El mensaje explica **por qué**, no qué. El *qué* ya está en el diff.

## Antes de abrir el PR

```bash
python manage.py test --noinput        # la suite completa, desde Registro_Post_Quirurgico/
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .                           # desde la raíz
git diff --check                       # espacios al final de línea
```

La CI corre **nueve comprobaciones** y las mira todas aunque una falle, para que
una corrida en rojo muestre de una vez todo lo que está mal.

**`Desarrollo` no tiene protección de rama**, así que los checks se ven pero no
bloquean: la compuerta es humana. Mirarlos antes de mergear es parte del
trabajo, no una formalidad.

## Convenciones del código

- **Idioma: español.** Nombres, comentarios y docstrings. Es la convención del
  equipo y no se mezcla.
- **Fechas:** `timezone.localdate()` siempre. **Nunca** `.date()` sobre un
  datetime *aware* ni `timezone.now().date()` — con `USE_TZ=True` y
  `TIME_ZONE='America/Bogota'` esos dos devuelven la fecha en UTC y rompen las
  reglas de días calendario en horario nocturno.
- **El `.env` nunca se sube.** La CI lo comprueba, y `gitleaks` revisa la
  historia completa en cada PR.
- **Datos de pacientes fuera de los logs.** La salida operativa identifica por
  `pk`, nunca por nombre ni teléfono. Los correos de alerta no llevan dato
  clínico.
- **Excepciones a un linter:** con su razón escrita al lado, en la misma línea,
  no silenciadas desde la configuración. Una lista de excepciones sin razones es
  una lista que crece hasta que no protege nada.

## Si trabajas con un agente de código

Buena parte de este proyecto se escribió así, y funciona — pero con reglas:

- **El agente lee [`CLAUDE.md`](CLAUDE.md) primero.** Las reglas clínicas viajan
  siempre en el contexto, precisamente para que no invente un umbral.
- **Un agente que corrige no puede auditar.** Quien escribió el código es el peor
  juez de si está bien. Las auditorías se piden a un agente que **no edita
  nada** y cuyo único producto es un informe con evidencia reproducible.
- **Un informe de otro agente es una hipótesis, no un hecho.** Se reproduce
  contra el código antes de actuar.
- La instrucción de una auditoría **se escribe en un archivo del repositorio**,
  no en el chat: el auditor no tiene la conversación previa.

## Reportar un problema

Usa las plantillas de issue. Si el problema es de seguridad o toca datos de
pacientes, **no abras un issue público**: ver [`SECURITY.md`](SECURITY.md).
