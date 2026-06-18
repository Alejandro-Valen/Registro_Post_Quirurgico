# Auditoría de Literatura — Material de Referencia

Carpeta generada en sesión de Claude.ai (junio 2026) antes de la fase de
decisiones de arquitectura del sistema de monitoreo posquirúrgico remoto.
Contiene tres análisis de las fuentes primarias revisadas:

- **ANALISIS_INDIVIDUAL_9_PDFS_ERAS.md** — Análisis documento por documento
  de los 9 PDFs científicos sobre protocolos ERAS y alta temprana en cirugía
  colorrectal (la evidencia que respalda el modelo de monitoreo remoto).

- **ANALISIS_TRANSCRIPCIONES_MEDICO.md** — Análisis de las transcripciones
  de presentaciones del médico proponente (Dr. Juan Camilo Correa); fuentes
  primarias del origen clínico del proyecto.

- **ANALISIS_4_ARCHIVOS_RESTANTES.md** — Análisis de documentos
  institucionales y académicos complementarios (Word, PowerPoint, PDFs no
  incluidos en el lote principal).

- **SINTESIS_CRUZADA_UMBRALES.md** — Tabla comparativa entre las 4 reglas
  actuales del `alert_engine` y los hallazgos de los 9 PDFs (fiebre, gases,
  náuseas, drenaje, dolor, PCR), más la decisión pendiente sobre frecuencia
  de check-ins. Es el insumo de partida para la próxima fase de decisiones
  del alert_engine.

> **Nota:** este material es referencia de apoyo para decisiones de
> arquitectura, no un contrato que el proyecto deba cumplir al pie de la
> letra. El alcance real del sistema, los umbrales clínicos vigentes y las
> decisiones de diseño quedan documentados en `CLAUDE.md` y `BITACORA.md`.
