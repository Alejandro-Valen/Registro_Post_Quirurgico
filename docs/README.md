# Mapa y estado de la documentación

> Última revisión integral: 24/07/2026. Estado actualizado el 31/07/2026.

Este índice distingue la documentación vigente de los registros históricos. Si
dos documentos parecen contradecirse, usa el **orden de autoridad** de abajo y
verifica siempre el código real.

**Cómo está organizada y por qué:** `docs/arquitectura_documentacion.md`. En una
línea: cada hecho vive en un solo archivo, y ese archivo se actualiza en el
mismo commit que el código que describe.

## Orden de autoridad

1. **El código.** Cualquier documento puede quedar desfasado; el código es lo
   que corre.
2. **El documento dueño del tema** (las "fuentes únicas" de abajo).
3. **`CLAUDE.md`**, para el estado del proyecto y cómo se trabaja aquí.
4. **`BITACORA.md`** describe el momento en que se escribió: nunca es fuente de
   verdad sobre el estado actual.

Al encontrar una contradicción, corrígela en el mismo commit en vez de anotarla
para después.

## Fuentes únicas (el documento dueño de cada tema)

| Documento | Es dueño de |
|-----------|-------------|
| `docs/reglas_clinicas.md` | Las 8 reglas del `alert_engine`, la regla operativa SILENCIO y las variables clínicas que captura el sistema |
| `docs/modelos_datos.md` | Los modelos de `models.py`: qué guarda cada campo y por qué |
| `docs/bot_whatsapp.md` | La máquina de estados del bot, sus reglas de diseño no negociables y las respuestas predefinidas |
| `docs/railway_deploy.md` | Topología de producción, variables de entorno y despliegue |
| `docs/cron_setup.md` | Programación de los management commands y límites operativos |
| `docs/transferencia_cuentas.md` | Propiedad y entrega futura de servicios y credenciales |
| `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` | El documento legal (Ley 1581/2012) |
| `Registro_Post_Quirurgico/.env.example` | Nombres de variables y ejemplos no secretos. Nunca es un archivo listo para copiar a producción sin revisar |

## Contexto y decisiones

| Documento | Qué responde |
|-----------|--------------|
| `CLAUDE.md` | Qué es el proyecto, cómo se trabaja, dónde vamos y el mapa de todo lo demás. Es la puerta de entrada |
| `ROADMAP_MONITOREO_POSQUIRURGICO.md` | Decisiones de producto (P-1 a P-15), checklists y requisitos separados para merge y para piloto real |
| `docs/arquitectura_documentacion.md` | Cómo se organiza esta documentación y por qué. Dónde escribir algo nuevo |
| `docs/decisiones_correccion_auditoria.md` | Fichas D1-D10 con el razonamiento de cada corrección post-auditoría, más el estado de avance por commit. Se consulta por tema, no por fecha |
| `docs/trampas_conocidas.md` | Errores que ya costaron horas: cron, despliegue, Twilio, correo. Léelo antes de tocar esas áreas |
| `docs/resumen_sprints.md` | Qué entregó cada sprint, bloque y loop — el mapa compacto de la BITÁCORA |
| `BITACORA.md` | La cronología completa: qué se hizo cada sesión, qué falló y cómo se resolvió |

## Material histórico o de referencia

- `docs/proceso/auditorias/2026-07-22_instruccion_loops_1_6.md` es la **instrucción** que se usó para la
  auditoría independiente previa al PR. La auditoría **ya se ejecutó** (22/07);
  sus 14 hallazgos y su informe están en la entrada de `BITACORA.md` de esa
  fecha y su corrección en `docs/decisiones_correccion_auditoria.md`. No debe
  volver a ejecutarse.
- `docs/proceso/auditorias/2026-06_informe_sprint3_cierre.md` conserva el diagnóstico previo al hardening. Sus
  hallazgos no deben reportarse como actuales sin volver a reproducirlos.
- `docs/auditoria_literatura/` conserva los análisis clínicos de junio de 2026.
  Las frases "pendiente" dentro de esos análisis pertenecen a la sesión
  original; las decisiones vigentes están en `docs/reglas_clinicas.md`.
- `Registro_Post_Quirurgico/signos_sintomas/knowledge_base.md` es un placeholder
  para Sprint 6. No es un corpus RAG activo ni sustituye validación médica.
- `Chart.js-LICENSE.md` es una licencia de proveedor y no se edita como memoria
  del proyecto.

## Documento legal canónico

La versión rastreada y canónica es
`docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`. Sigue requiriendo completar los
campos entre corchetes, revisión final del responsable y firma de cada paciente
antes del uso real.

Existe localmente una copia raíz no rastreada con el mismo nombre. Al cierre del
21/07/2026 ambas copias tenían el mismo SHA-256, pero la copia raíz no forma
parte del repositorio y no debe agregarse automáticamente a commits o PR.

## Estado (31/07/2026)

- **Rama activa: ninguna.** El Sprint 5 se mergeó a `Desarrollo` el 29/07/2026
  (PR #3, `3a5c573`) y `sprint-6-ci` el 31/07/2026 (PR #5, `5b40c01`).
- Las dos auditorías (22/07 y 27/07) están **cerradas**: sus 18 hallazgos se
  corrigieron en los Loops A-D, todos verificados. **No se repiten.**
- **Cada PR se verifica solo** desde el 31/07: `.github/workflows/ci.yml` corre
  la suite, `check`, `makemigrations --check`, `check --deploy` y la higiene del
  diff. Los checks se ven pero **todavía no bloquean** el merge.
- Despliegue: Railway mira `produccion`. Mergear a `Desarrollo` no despliega
  nada — ver `docs/railway_deploy.md` §4.1.
- Todavía no apto para pacientes reales: ver los requisitos del piloto en el
  ROADMAP y en `CLAUDE.md`, sección "Por resolver antes del piloto real".

## Siguiente sesión

1. Abrir el repositorio en `Desarrollo` y traer cambios de origin sin mezclar
   otras ramas.
2. Leer `CLAUDE.md` completo y el "Estado de avance" de
   `docs/decisiones_correccion_auditoria.md`.
3. Verificar el estado real contra `git log` y la suite **antes** de proponer
   nada. Si el documento contradice a Git, manda Git.
4. Abrir el **Loop E** (ficha D14) en su propia rama. Un loop, un tema. Las
   auditorías ya se ejecutaron: no repetirlas.
