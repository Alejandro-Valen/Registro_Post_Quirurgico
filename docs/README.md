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
| `docs/decisiones_correccion_auditoria.md` | Fichas **D1-D17** con el razonamiento de cada corrección post-auditoría, más el estado de avance por commit. Se consulta por tema, no por fecha |
| `README.md` (raíz) | La portada del proyecto: qué hace, cómo se instala, qué falta para pacientes reales |
| `CONTRIBUTING.md` | Cómo se trabaja aquí: el ciclo decidir → documentar → prueba en rojo → verificar en las dos direcciones |
| `SECURITY.md` | Cómo reportar una vulnerabilidad, qué cuenta como una en este proyecto, y lo que sabemos que falta |
| `LICENSE` | Todos los derechos reservados, con el porqué y el aviso clínico |
| `docs/trampas_conocidas.md` | Errores que ya costaron horas: cron, despliegue, Twilio, correo. Léelo antes de tocar esas áreas |
| `docs/resumen_sprints.md` | Qué entregó cada sprint, bloque y loop — el mapa compacto de la BITÁCORA |

## Material histórico o de referencia

- La auditoría independiente previa al PR **ya se ejecutó** (22/07); la
  corrección de sus 14 hallazgos está en `docs/decisiones_correccion_auditoria.md`.
  No debe volver a ejecutarse.
- La tercera auditoría (07/09/2026) produjo **101 hallazgos itemizados, con el
  estado de cada uno**. A diferencia de las dos anteriores, ese informe se
  mantiene vivo — cuando se corrige un hallazgo, su fila se actualiza en el
  mismo commit. Trae
  además la advertencia que hay que leer antes de usarlo: **97 de los 101 están
  trazados contra el código pero NO reproducidos ejecutando**, así que cada uno
  es una hipótesis hasta que se compruebe.
- El diagnóstico previo al Sprint 3-Hardening se conserva aparte. Sus
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

## Estado (07/09/2026)

- **Tres auditorías ejecutadas y cerradas**: 22/07, 27/07 y la de seis frentes
  del 07/09. **No se repiten.** Sus correcciones son las fichas D1-D17.
- **Cada PR se verifica solo** con **diez comprobaciones**: suite, `check`,
  `makemigrations --check`, `check --deploy` con `--fail-level WARNING`, higiene
  del diff, guardia de secretos, control de archivos de entorno, linter y
  auditoría de dependencias.
- **Los checks se ven pero no bloquean.** `Desarrollo` no tiene protección de
  rama, y no es cuestión de permisos: en un repositorio privado sin GitHub Pro
  no existe para nadie. La compuerta es humana.
- **No hay producción viva desde el 07/08/2026** — venció la prueba de Railway.
  Mergear a `produccion` no despliega nada.
- **Todavía no apto para pacientes reales.** Además de lo técnico, hay un
  cambio normativo que el proyecto no había registrado: la **Resolución 1644 de
  2026** derogó la 2654 de 2019 y excluye la mensajería instantánea para el
  intercambio de datos clínicos. Ver el README de la raíz.

## Cómo retomar

1. Abrir en `Desarrollo` y traer cambios de origin.
2. Leer `CLAUDE.md` completo.
3. **Verificar el estado real contra `git log` y la suite antes de proponer
   nada.** Si el documento contradice a Git, manda Git — y corrige el documento
   en el mismo commit.
4. Un loop, un tema.
