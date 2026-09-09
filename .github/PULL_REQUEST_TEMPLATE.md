<!--
El PR se explica solo. Quien lo revise dentro de seis meses no tendrá la
conversación en la que se decidió esto.
-->

## Qué cambia y por qué

<!-- El *qué* ya está en el diff. Aquí va el porqué. -->

## Cómo se verificó

<!--
Números vistos en pantalla en esta sesión, no heredados de la documentación.
Y si el cambio toca comportamiento: cómo se comprobó en LAS DOS direcciones —
que atrapa lo que debe atrapar, y que deja pasar lo que debe pasar.
-->

- [ ] Suite completa (`python manage.py test --noinput`) — nº de pruebas:
- [ ] `ruff check .`
- [ ] `python manage.py makemigrations --check --dry-run`
- [ ] `git diff --check`
- [ ] Las diez comprobaciones de la CI, **miradas una a una** (sin protección
      de rama, la compuerta es humana)

## Si toca comportamiento

- [ ] La prueba **nació en rojo** y se vio caer, o su docstring explica por qué
      no podía nacer en rojo
- [ ] Se anuló la corrección y se comprobó que la prueba vuelve a caer

## Si toca algo clínico

<!-- Umbrales, severidades, reglas del motor, textos que lee el paciente. -->

- [ ] **Decisión escrita ANTES del código**, en `docs/decisiones_correccion_auditoria.md`
- [ ] Aprobada explícitamente por el Arquitecto
- [ ] `docs/reglas_clinicas.md` actualizado **en este mismo lote de commits**

## Documentación

- [ ] El documento dueño de lo que se tocó está actualizado (ver la tabla de
      sincronización en `CLAUDE.md`)
- [ ] No se copió ningún dato a un segundo documento: cada hecho vive en un solo
      archivo

## Lo que este PR NO resuelve

<!--
Lo que quedó fuera a propósito, y por qué. Es la sección más útil del PR: evita
que alguien lo dé por cerrado creyendo que cubría más de lo que cubre.
-->
