# Auditoría de Literatura — Material de Referencia

> **Estado documental al 21/07/2026:** estos archivos son evidencia histórica,
> no una lista de tareas vigente. Las preguntas de alcance y arquitectura se
> resolvieron después en Sprint 3.6 y Sprint 5. Las decisiones actuales viven en
> `CLAUDE.md` y `ROADMAP_MONITOREO_POSQUIRURGICO.md`; RAG/OpenMed quedaron
> diferidos a Sprint 6 y requieren validación médica.

Carpeta generada en sesión de Claude.ai (junio 2026) antes de la fase de
decisiones de arquitectura del sistema de monitoreo posquirúrgico remoto.
Contiene cuatro análisis de las fuentes primarias revisadas:

- **ANALISIS_INDIVIDUAL_9_PDFS_ERAS.md** — Análisis documento por documento
  de los 9 PDFs científicos sobre protocolos ERAS y alta temprana en cirugía
  colorrectal (la evidencia que respalda el modelo de monitoreo remoto).

- **ANALISIS_TRANSCRIPCIONES_MEDICO.md** — Análisis de las transcripciones
  de presentaciones del médico proponente (Dr. Juan Camilo Correa); fuentes
  primarias del origen clínico del proyecto.

- **ANALISIS_4_ARCHIVOS_RESTANTES.md** — Análisis de documentos
  institucionales y académicos complementarios (Word, PowerPoint, PDFs no
  incluidos en el lote principal).

- **SINTESIS_CRUZADA_UMBRALES.md** — Tabla comparativa entre las reglas del
  `alert_engine` de ese momento y los hallazgos de los 9 PDFs (fiebre, gases,
  náuseas, drenaje, dolor, PCR), más la discusión histórica sobre frecuencia
  de check-ins.

> **Nota:** este material es referencia de apoyo para decisiones de
> arquitectura, no un contrato que el proyecto deba cumplir al pie de la
> letra. El alcance real del sistema, los umbrales clínicos vigentes y las
> decisiones de diseño quedan documentados en `CLAUDE.md` y `BITACORA.md`.
