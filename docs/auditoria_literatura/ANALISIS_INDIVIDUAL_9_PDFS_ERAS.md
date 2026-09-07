# Análisis Documento por Documento — 9 PDFs ERAS/Alta Temprana Colorrectal
## Monitoreo posquirúrgico remoto — Auditoría de literatura científica

> **Documento histórico (junio de 2026).** Las frases sobre pasos o decisiones
> pendientes reflejan la sesión original. Para el estado vigente consulta
> `CLAUDE.md` y `ROADMAP_MONITOREO_POSQUIRURGICO.md`.

> Complementa la síntesis cruzada de umbrales ya generada en la sesión anterior
> (ver `CONTEXTO_TRANSFERENCIA_AUDITORIA_PDFS.md`). Aquí cada uno de los 9 PDFs
> se analiza individualmente en el formato acordado: resumen clínico, datos
> accionables, conexión con el proyecto, y pros/contras de incorporar sus
> hallazgos al diseño actual.

---

## 1. Lawrence et al. 2013 — *J Am Coll Surg*
**"Discharge within 24 to 72 Hours of Colorectal Surgery Is Associated with Low Readmission Rates when Using Enhanced Recovery Pathways"**

**Resumen clínico:** Revisión retrospectiva de un cirujano único, 806 colectomías electivas (609 laparoscópicas, 197 abiertas) durante 64 meses, todas bajo un Enhanced Recovery Pathway (ERP) estandarizado. El DoD (día de alta) medio fue 3.9 días en laparoscopía vs 8.4 en abierta. La readmisión global fue 8.9%, pero la acumulada en los subgrupos de alta más temprana (laparoscópicos en DoD 1, 2 y 3) fue de apenas 0.2%, 1.6% y 3.4% respectivamente — es decir, a menor estancia, menor readmisión, no mayor.

**Datos accionables:** Criterios de alta usados: flatos o heces, orina libremente, ambula independiente, tolera dieta, dolor manejado con analgesia oral. Causas principales de readmisión: deshidratación (25%) y obstrucción de intestino delgado (16%) — no sepsis ni fuga como causa dominante. Seguimiento post-alta limitado a una llamada telefónica dentro de 48h, sin app ni monitoreo estructurado.

**Conexión con el proyecto:** Es el estudio más antiguo y menos "tecnológico" del set. No aporta umbrales numéricos de temperatura, dolor o náusea aprovechables para el `alert_engine`. Su valor es de respaldo conceptual: confirma que el alta temprana no es intrínsecamente riesgosa cuando hay criterios claros — relevante para la filosofía general del programa, no para sus reglas concretas.

**Pros/contras de incorporar:** Pro — sirve como cita de respaldo si el médico necesita justificar el modelo de alta temprana con la clínica del proyecto. Contra — no hay nada operacionalizable; incorporarlo no cambiaría ni una línea de `alert_engine.py`.

---

## 2. Turrentine et al. 2022 — *Ann Surg* (NSQIP)
**"Early Patient Discharge in Selected Patients is Not Associated With Higher Readmission After Major Abdominal Operations"**

**Resumen clínico:** Estudio de registro masivo (NSQIP 2011-2017), 364,609 pacientes en 6 grupos quirúrgicos abdominales mayores (colectomía lap/abierta, proctectomía lap/abierta, hepatectomía mayor, pancreatoduodenectomía). En cada uno de los 6 grupos, el alta antes de la fecha mediana se asoció a MENOR readmisión, no mayor: por ejemplo, colectomía laparoscópica 6% vs 8% (p≤0.02). La morbilidad seria compuesta también fue significativamente menor en los dados de alta temprano en todos los grupos (p<0.001).

**Datos accionables:** El estudio no captura variables de seguimiento remoto (no hay app ni cuestionario); es puramente registro hospitalario de readmisión y complicaciones a 30 días. No ofrece umbrales clínicos de fiebre, dolor o drenaje.

**Conexión con el proyecto:** Es el estudio con mayor poder estadístico de todo el set (n=364,609) y el más citable frente a una junta médica escéptica del alta temprana. Pero, igual que Lawrence, no aporta nada operacionalizable para las reglas del bot — es evidencia "de macro nivel" (¿es seguro el alta temprana, en general?), no "de micro nivel" (¿qué umbral debe disparar una alerta en casa?).

**Pros/contras de incorporar:** Pro — el dato más fuerte para tranquilizar a un comité de ética o a la propia clínica del proyecto sobre la seguridad general del enfoque. Contra — cero impacto directo en el código; es argumento institucional, no técnico.

---

## 3. Lee et al. 2022 — *Ann Surg* (McGill)
**"Enhanced Recovery 2.0 – Same Day Discharge With Mobile App Follow-up After Minimally Invasive Colorectal Surgery"**

**Resumen clínico:** El estudio arquitectónicamente más parecido al bot de Somer. 48 pacientes en protocolo de alta el mismo día de cirugía (SDD), con seguimiento por app móvil (CareSense). Cuestionario diario de salud (recuperación GI, fiebre, dolor) hasta POD7; cualquier respuesta positiva dispara notificación automática por correo al cirujano. App también permite chat directo y subida de foto de herida si hay hallazgo positivo. 77% de éxito en SDD (criterio: alta el mismo día sin ED/readmisión en 72h). Complicaciones a 30 días similares entre SDD (17%) y ERP estándar (15%, p=0.813).

**Datos accionables:** Criterios de alta: dieta líquida sin náusea/vómito, dolor ≤3 en reposo / ≤5 con movimiento (escala 0-10), ambula y orina independiente. Tabla de causas reales de visita a Urgencias dentro de 30 días: neumonía (POD18), colitis (POD7, readmisión 1 día), *C. difficile* (POD10, readmisión 1 día), infección profunda de sitio quirúrgico (POD5, readmisión 2 días), preocupación de herida (normal, sin readmisión). 76% de los pacientes usó el chat al menos una vez; 57% completó al menos un "Daily Health Check". Notificación = **cualquier respuesta positiva**, sin esperar acumulación.

**Conexión con el proyecto:** Es la comparación más directa disponible. El diseño de "el paciente nunca ve alertas, lenguaje conversacional" coincide con este estudio. La diferencia estructural clave: Lee notifica ante CUALQUIER hallazgo positivo (alta sensibilidad, bajo umbral), mientras que `alert_engine` espera acumulación (3 días sin gases, >3 episodios de náusea) — un diseño de menor sensibilidad. La tabla de causas reales de ED muestra que ninguna fue capturada por "fiebre aislada" sino por combinaciones (diarrea+fiebre, dolor+cambio de hábito intestinal) — esto valida que el sistema de Somer ya captura las variables correctas (temperatura, drenaje, gases, náuseas), pero la pregunta de fondo es si el umbral de disparo es demasiado conservador frente al estándar más reciente.

**Pros/contras de incorporar:** Pro — el ejemplo más fuerte para proponerle al médico evolucionar de "1 reporte diario con alerta acumulada" a "alerta ante cualquier hallazgo positivo aislado" (sin necesariamente aumentar la frecuencia de los check-ins, solo bajar el umbral de disparo). Contra — implementarlo tal cual generaría muchas más alertas de severidad BAJA que hoy no existen en el modelo de Alerta (`ALTA/MEDIA/BAJA`), lo que podría saturar al oncólogo si no se diseña una capa de triage adicional.

---

## 4. Delaney 2008 — *Dis Colon Rectum*
**"Outcome of Discharge Within 24 to 72 Hours After Laparoscopic Colorectal Surgery"**

**Resumen clínico:** 118 pacientes consecutivos, mismo grupo de Cleveland que el estudio de Lawrence (de hecho es el antecedente directo). 70% dados de alta dentro de 72h. El subgrupo de alta en POD1-2 tuvo complicaciones significativamente menores que el grupo general (7.1% vs 20.3% global), y los pacientes que se quedaron 4+ días tuvieron 44.4% de complicaciones — reforzando que la selección clínica para alta temprana funciona como filtro natural de pacientes que ya van bien.

**Datos accionables:** Es el único de los 9 PDFs con un **número exacto de dolor** como criterio de alta: **EVA < 4**. Otros criterios: flatos o heces, afebril SIN taquicardia (no solo afebril), tolera 3 comidas sin náusea/vómito, ambula independiente. Íleo/obstrucción de intestino delgado ocurrió en 11% del total y 27.8% del grupo que se quedó 4+ días — el íleo es la complicación dominante que retrasa el alta, no la sepsis ni la fuga.

**Conexión con el proyecto:** El umbral EVA<4 es directamente comparable con la variable `dolor_eva` que el sistema ya captura pero sin regla de alerta asociada (como ya se señaló en la síntesis cruzada anterior). Este documento confirma que ese número (4) no es arbitrario — aparece también como criterio de alta en Lee et al. (≤3 reposo / ≤5 movimiento) y es consistente entre estudios de grupos distintos, lo que le da más peso como candidato a umbral real, no solo como dato de alta hospitalaria sino como posible alerta post-alta (dolor que SUBE por encima de 4 en casa podría ser señal, no solo dolor alto al momento del alta).

**Pros/contras de incorporar:** Pro — es el dato más concreto y replicado entre los 9 PDFs para justificar agregar una **Regla 5 al alert_engine: dolor_eva >= 4 (o un incremento sostenido) → alerta DOLOR_AGUDO**, tipo de alerta que ya existe en el modelo `Alerta` (`DOLOR_AGUDO` está en los choices pero no tiene regla implementada). Contra — el dolor es más subjetivo y variable día a día que la temperatura; una regla mal calibrada podría generar muchos falsos positivos si no se diferencia dolor basal post-quirúrgico esperado vs dolor nuevo/creciente.

---

## 5. Yuen et al. 2016 — *Surg Endosc*
**"Is expedited early discharge following elective surgery for colorectal cancer safe?"**

**Resumen clínico:** NSQIP 2012, comparación rigurosa entre alta "expedita" (POD1-2, n=305) y alta "estándar temprana" (POD3-4, n=2277) en cáncer colorrectal electivo. Sin diferencia significativa en eventos adversos a 30 días (1.97% vs 2.59%) ni en readmisión (5.56% vs 6.24%) tras ajuste multivariable.

**Datos accionables:** Predictores independientes de eventos adversos: sexo masculino, tabaquismo, cirugía abierta. Predictores independientes de readmisión: tiempo operatorio prolongado, hipertensión, cirugía abierta. No hay datos de seguimiento remoto ni umbrales de síntomas — es puramente registro perioperatorio.

**Conexión con el proyecto:** Aporta poco al diseño de alertas en sí, pero sí abre una idea distinta: **estratificación de riesgo por perfil del paciente** (fumador, hipertenso, cirugía abierta vs laparoscópica) como input para decidir qué tan estrecho debe ser el seguimiento de un paciente particular — algo que el sistema actual no hace (todos los pacientes activos reciben el mismo flujo de preguntas, sin ajuste por riesgo basal).

**Pros/contras de incorporar:** Pro — si el médico quisiera priorizar a qué pacientes vigilar más de cerca dentro del dashboard de Sprint 4, estos factores de riesgo (tabaquismo, hipertensión, cirugía abierta) podrían alimentar un score simple. Contra — el modelo `Paciente` actual no captura ninguno de estos campos (comorbilidades, tipo de cirugía abierta/lap), así que incorporarlo implicaría una migración de modelo, no solo un ajuste de `alert_engine.py`. Es una mejora de alcance mayor, no inmediata.

---

## 6. Saadat et al. 2019 — *World J Surg* (NSQIP)
**"Twenty-Three-Hour-Stay Colectomy Without Increased Readmissions"**

**Resumen clínico:** Analiza 115,858 colectomías NSQIP 2012-2017; solo 1.6% (1905) fueron alta en ≤23h. Sin aumento de readmisión en ese grupo (6.3% vs 9.3%, de hecho menor). Predictores multivariables de alta ultratemprana: tiempo quirúrgico corto, técnica mínimamente invasiva (OR 2.97), **ausencia de ostomía** (OR 0.614 — es decir, tener ostomía reduce más de un tercio la probabilidad de alta temprana) y **ausencia de stent ureteral** (OR 0.641).

**Datos accionables:** Complicaciones (ISQ, íleo, fuga anastomótica) consistentemente más bajas en el grupo de alta ultratemprana que en el resto — pero esto refleja selección de pacientes sanos, no causalidad del alta en sí. Indicaciones quirúrgicas asociadas a alta temprana: pólipos, apendicitis. Asociadas a NO alta temprana: cáncer de colon, diverticulitis, enfermedad inflamatoria intestinal.

**Conexión con el proyecto:** Este es el hallazgo más importante para la **decisión de alcance** del proyecto. La población que estos protocolos de alta ultratemprana/ambulatoria seleccionan EXCLUYE sistemáticamente a pacientes con ostomía y con stents — y los pacientes de Sugarbaker/HIPEC frecuentemente tienen ostomías derivativas y procedimientos más extensos (múltiples anastomosis, peritonectomía). Esto refuerza, con un número concreto (OR 0.614 y 0.641), la alerta ya señalada en la síntesis cruzada anterior: la variable `aspecto_drenaje` del sistema puede no aplicar bien al perfil real de paciente Sugarbaker, que es precisamente el tipo de paciente que estos estudios excluyen de su población de "alta fácil".

**Pros/contras de incorporar:** Pro — dato cuantitativo fuerte para la conversación de alcance con el médico: "la evidencia de alta temprana que tenemos aplica mejor a colectomía simple sin ostomía, no al perfil HIPEC típico." Contra — no es un dato que cambie el código; es un dato que cambia la conversación sobre a quién está realmente diseñado a servir el bot.

---

## 7. Gignoux et al. 2018/2019 — *Ann Surg*
**"Short-term Outcomes of Ambulatory Colectomy for 157 Consecutive Patients"**

**Resumen clínico:** Primera serie grande de colectomía verdaderamente ambulatoria (alta el mismo día, sin pernoctar), 157 pacientes en 2 centros franceses. Estancia hospitalaria media de solo 10.4 horas. Tasa de "fracaso" (admisión no planeada) 7.0%. Consulta no programada en 20.5% de los pacientes, readmisión 6.1%, reoperación 3.8%, sin mortalidad.

**Datos accionables:** Protocolo de seguimiento intensivo: enfermera a domicilio dos veces al día durante 5 días, luego una vez al día 5 días más (10 días totales) + llamada telefónica diaria. Análisis de sangre (PCR, hemograma, electrolitos) en POD1, 3 y 7. **PCR > 135 mg/L tiene 97% de valor predictivo positivo para fuga anastomótica** (citando a Singh et al.) y dispara automáticamente un TAC abdominopélvico. Criterios de exclusión explícitos: laparotomía media previa, tumores T4 grandes, lesiones colónicas múltiples, **resección rectal baja, diverticulitis perforada previa, ostomía planeada**, desnutrición severa, diabetes insulinodependiente, anticoagulación.

**Conexión con el proyecto:** Confirma con más detalle el mismo punto que Saadat: los criterios de exclusión de este protocolo (sin ostomía planeada, sin resección rectal baja, sin tumores grandes) describen casi el opuesto del paciente Sugarbaker/HIPEC típico. Es el estudio con el dato de laboratorio más citado de toda la síntesis (PCR>135), pero ese dato requiere infraestructura de laboratorio que el bot de WhatsApp no tiene — ya señalado como "fuera de alcance actual" en la síntesis previa.

**Pros/contras de incorporar:** Pro — si en el futuro el sistema se integra con resultados de laboratorio (Sprint 5+), el umbral PCR>135 mg/L en POD3 es el dato más sólido y replicado (también aparece en Coeckelberghs 2025) para automatizar una alerta de fuga anastomótica basada en laboratorio, complementando o incluso superando en sensibilidad a la regla actual basada en aspecto de drenaje. Contra — totalmente fuera de alcance para el MVP actual; requeriría integración con LIS/HIS de la clínica, no solo cambios en `alert_engine.py`.

---

## 8. van Outersterp et al. 2025 — *Surg Endosc*
**"Monitoring early discharge after laparoscopic colon surgery: an interventional study"**

**Resumen clínico:** Estudio holandés con sensores Masimo (signos vitales continuos) + cuestionario 3 veces al día, 51 pacientes, 30 dados de alta temprano (día 1 o 2). Éxito de alta temprana 80% (24/30). Readmisión 20% (6/30), pero **66.7% de esas readmisiones fueron por fallas del sistema de monitoreo, no por el estado real del paciente**. Ninguna readmisión se debió a una desviación real de signos vitales.

**Datos accionables:** Umbrales usados para notificación: temperatura > 37.9 °C sostenida >5 min, frecuencia cardiaca > 100 lpm sostenida >5 min, SpO2 < 88% sostenida >5 min, dolor EVA ≥ 4, o **cualquier respuesta positiva del cuestionario** (excepto la pregunta sobre gases/deposición). De 942 notificaciones de signos vitales generadas, el 77.6% fueron por frecuencia respiratoria — y el equipo concluyó que ese sensor específico no era confiable para monitoreo continuo y decidió **no readmitir a nadie basándose solo en esa alerta**. El hallazgo central del estudio: el monitoreo continuo de signos vitales no predijo ninguna readmisión real; las alertas útiles vinieron del cuestionario + llamada telefónica.

**Conexión con el proyecto:** Es la validación más directa y reciente (2025) del enfoque de bajo costo tecnológico que ya usa Somer: preguntas conversacionales en vez de sensores de hardware. También aporta el número más preciso de toda la síntesis para temperatura (37.9°C, no 38.0°C) — confirmando lo ya anotado en la tabla anterior: el umbral actual del `alert_engine` (≥38.0) es ligeramente más conservador (deja pasar más fiebre antes de alertar) que el estudio más reciente con número exacto.

**Pros/contras de incorporar:** Pro — refuerza con evidencia de 2025 que NO hay necesidad de invertir en wearables o sensores de hardware para este programa; el bot conversacional por WhatsApp está alineado con el estado del arte, no es una versión "pobre" de lo que hacen centros más grandes. También da argumento sólido para bajar el umbral de temperatura de 38.0 a algo más cercano a 37.9-38.0 si el médico lo aprueba. Contra — bajar el umbral de temperatura aumentaría la frecuencia de alertas SEPSIS; debe decidirlo el médico, no es un cambio que deba hacerse unilateralmente en el código.

---

## 9. Coeckelberghs et al. 2025 — *Ann Surg* (Leuven)
**"Road Towards Ambulatory Colectomy — Patient Outcomes and Experience During a Feasibility Study"**

**Resumen clínico:** Protocolo "One-Night-Stay" (ONS) en Lovaina: app + wearable + dashboard + PCR en sangre en POD1, 3 y 5. 26 pacientes en ONS comparados 1:1 con 23 pacientes de ERP tradicional. Estancia mediana: 1 día (ONS) vs 4 días (ERP tradicional). Sin readmisiones ni complicaciones severas en el grupo ONS. Satisfacción 8.5/10. Dolor EVA en POD1 significativamente menor en ONS (mediana 3) que en ERP tradicional (mediana 5).

**Datos accionables:** PCR mediana bajó de 33.1 (POD1) a 13.0 (POD5) en la trayectoria normal de recuperación — útil como referencia de "qué tan rápido debería bajar la PCR si todo va bien", en contraste con el umbral de alarma de Gignoux/Singh (>135 mg/L). La sección de discusión con los panelistas (al final del PDF) plantea preguntas relevantes de gobernanza: ¿quién es responsable médico-legal de las alertas?, ¿el dispositivo de monitoreo requiere certificación regulatoria (MDR)?, y se repite la duda ya planteada por Outersterp: ¿el monitoreo continuo de signos vitales realmente agrega valor sobre el cuestionario + llamada?

**Conexión con el proyecto:** Es el estudio más reciente (2025) y el que más se parece en ambición a hacia dónde podría evolucionar el sistema de Somer si crece (dashboard centralizado, FASE 4-5 del roadmap). La discusión de panelistas sobre responsabilidad legal de las alertas es directamente relevante para Sprint 4: cuando el dashboard del oncólogo esté listo y las alertas lleguen por email/SMS, hay que definir explícitamente quién atiende cada alerta y en qué ventana de tiempo — algo que el modelo `Alerta` ya soporta (campo `resuelta` y `fecha_resolucion`) pero que no está respaldado todavía por un protocolo operativo escrito.

**Pros/contras de incorporar:** Pro — el dato de PCR como trayectoria normal (33→13 en 5 días) es útil si se integra laboratorio a futuro, y el debate de gobernanza es una checklist gratuita de preguntas que el Arquitecto debería resolver antes de activar notificaciones automáticas al médico en FASE 4. Contra — el modelo ONS completo (wearable + PCR seriada + dashboard clínico) excede por mucho el alcance de un MVP de WhatsApp; replicarlo tal cual no es realista para Sprint 4-5 de este proyecto.

---

## Notas que refinan la síntesis cruzada anterior

Esta lectura documento-por-documento no contradice la tabla de umbrales ya construida, pero agrega tres matices que vale la pena que el Arquitecto tenga presentes:

1. **El umbral de dolor EVA≥4 aparece replicado en 3 estudios independientes** (Delaney 2008, Lee 2022, Outersterp 2025) con el mismo número o uno muy cercano — es el candidato más sólido de toda la síntesis para una posible **Regla 5 nueva** en `alert_engine.py` (tipo `DOLOR_AGUDO`, que ya existe en los choices del modelo `Alerta` pero no tiene regla implementada).
2. **El hallazgo de Saadat (OR 0.614 sin ostomía, OR 0.641 sin stent) cuantifica** lo que la síntesis anterior señalaba cualitativamente: los protocolos de alta temprana/ambulatoria de esta literatura seleccionan activamente en contra del perfil de paciente que probablemente más atiende el médico en HIPEC/Sugarbaker (con ostomías y procedimientos extensos). Esto no invalida usar la literatura como respaldo general de ERAS, pero sí refuerza que la decisión de alcance (Sugarbaker vs ERAS colorrectal general) no es un detalle, es estructural.
3. **Dos estudios de 2025 (Outersterp y Coeckelberghs) coinciden en una conclusión negativa importante**: el monitoreo continuo de signos vitales por hardware no demostró agregar valor predictivo sobre cuestionarios conversacionales + llamada telefónica. Esto es evidencia reciente y específica de que el bot de WhatsApp de Somer no es una versión "limitada" del estado del arte — es, de hecho, el enfoque que la evidencia más nueva valida.

---

Quedan pendientes los otros 3 pasos identificados en la sesión anterior: la decisión de alcance con el médico, el análisis de los 5 archivos restantes, y la auditoría final de `alert_engine.py` con recomendación concreta de cambio urgente vs. mejora a futuro. Decime cuál sigue.
