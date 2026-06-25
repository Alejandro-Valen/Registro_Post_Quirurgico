# Síntesis Cruzada de Umbrales Clínicos — alert_engine.py vs. 9 PDFs

> **Qué es esto:** la tabla comparativa construida en la sesión original de
> auditoría de literatura, antes del análisis documento-por-documento que vive
> en `ANALISIS_INDIVIDUAL_9_PDFS_ERAS.md` (este archivo es anterior a ese, y
> los dos se complementan — donde hay diferencia de matiz entre ambos, el
> análisis documento-por-documento es la versión más reciente y detallada).
> Es el insumo de partida para la fase de decisiones del `alert_engine` que
> viene después de cerrar la generalización de alcance/afiliación.
>
> **Nota de contexto:** este documento se escribió cuando la pregunta de
> alcance (ERAS general vs. Sugarbaker exclusivo) todavía estaba abierta. Esa
> pregunta ya se resolvió — ver `CLAUDE.md` y el campo `tipo_cirugia` en
> `Paciente`. Lo que sigue vigente y sin resolver de este documento es
> específicamente la comparación de umbrales, no la discusión de alcance.

---

## Tabla comparativa: regla actual vs. literatura

| Variable | `alert_engine` actual | Lo que dice la literatura | Nota / conflicto |
|---|---|---|---|
| **Temperatura** | `>= 38.0°C` → SEPSIS / ALTA | Outersterp 2025 usa `>37.9°C` sostenido >5 min; el resto de estudios usa "afebril" como criterio binario, sin número exacto. | El umbral actual es razonable, ligeramente más conservador (deja pasar un poco más de fiebre antes de alertar) que el único estudio con número exacto y reciente. |
| **Gases — 3 días consecutivos** | Sin gases en 3 registros consecutivos (`dia_postoperatorio`) → ÍLEO / ALTA | Ningún estudio de los 9 usa "3 días consecutivos sin gases" como regla explícita — es una construcción propia del proyecto, no un estándar replicado en la literatura. Los estudios tratan el íleo como complicación binaria reportada, no como conteo de días. | La regla funciona y es razonable, pero no tiene respaldo textual directo en ningún PDF. Vale la pena saberlo al decidir si se ajusta o se mantiene. |
| **Náuseas — >3 episodios** | `episodios_nauseas > 3` → ÍLEO / MEDIA | Lee et al. 2022 y Outersterp 2025 tratan **cualquier** episodio de náusea/vómito reportado como señal de seguimiento — no esperan acumular 3 o más. | El umbral actual es más permisivo (deja pasar más casos sin alertar) que el estándar de los dos estudios más recientes y más parecidos arquitectónicamente al bot. |
| **Drenaje — aspecto** | `purulento`/`fecaloide` → FUGA_ANASTOMOTICA / ALTA | Varios protocolos ERAS modernos (Lee 2022, Gignoux 2018, Coeckelberghs 2025) **no usan drenajes en absoluto** — la fuga anastomótica se vigila por dolor nuevo + fiebre + taquicardia + PCR en sangre, no por aspecto de drenaje. | Riesgo real: la variable principal del sistema (drenaje) puede no aplicar al perfil de paciente de los protocolos ERAS más nuevos, que ya no colocan drenaje de rutina. |
| **Dolor (EVA)** | Capturado (`dolor_eva`), sin regla de alerta asociada | Usado como **criterio de alta hospitalaria** (no como alarma aislada post-alta) en todos los estudios que lo mencionan. | Coherente con el diseño actual de no alertar por dolor aislado. Nota cruzada: el análisis documento-por-documento posterior encontró que **EVA ≥ 4** se repite como el mismo número en 3 estudios independientes (Delaney 2008, Lee 2022, Outersterp 2025) — candidato fuerte si se decide agregar una regla de `DOLOR_AGUDO`. Ver `ANALISIS_INDIVIDUAL_9_PDFS_ERAS.md`, sección 4 y "Notas que refinan la síntesis cruzada". |
| **PCR/CRP en sangre** | No existe en el sistema | 3 de 9 estudios (Gignoux 2018, Coeckelberghs 2025, y por extensión Singh et al. citado en ambos) la usan como predictor fuerte de fuga anastomótica — `PCR > 135 mg/L` con 97% de valor predictivo positivo. | Fuera de alcance de un bot de WhatsApp sin integración de laboratorio. Anotado como posible mejora futura si el sistema llega a integrarse con resultados de laboratorio (no es parte de esta fase). |

---

## Decisión pendiente — arquitectura de check-ins (no resuelta todavía)

Los 3 estudios más recientes y sofisticados (Lee 2022, Outersterp 2025,
Coeckelberghs 2025) usan una arquitectura de seguimiento **2-3 veces al día**
con preguntas binarias/escala simple y notificación automática ante
**cualquier respuesta positiva** — estructuralmente distinta al diseño actual
del bot (1 reporte diario con 5 preguntas, alertas por umbral acumulado).

Esto no invalida el diseño actual, pero es un patrón concreto a decidir en la
fase de `alert_engine`: ¿el sistema debería evolucionar hacia check-ins más
frecuentes y de menor umbral de alerta, o se mantiene 1×/día con el umbral
acumulado que ya existe? Sigue sin resolverse — es, junto con la tabla de
arriba, el otro insumo principal para esa conversación.

---

## Lo que la evidencia confirma que NO hay que cambiar

El diseño de "el paciente nunca ve alertas, solo confirmación neutra" y
"lenguaje no médico, bot conversacional" está alineado con el estudio más
exitoso de todos (Lee et al., el más parecido arquitectónicamente al bot) y
con Outersterp 2025. No es una apuesta arriesgada del proyecto, es el
estándar de la literatura más reciente revisada. Esto no necesita decisión —
ya está validado.

---

*Cuarto documento de la carpeta `docs/auditoria_literatura/`. Los otros tres
— análisis documento por documento de los 9 PDFs, transcripciones del médico,
y documentos institucionales/académicos — están en esta misma carpeta.*
