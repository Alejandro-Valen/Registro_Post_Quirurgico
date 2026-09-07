# Análisis de los 4 Archivos Restantes — Documentos Institucionales y Académicos
## Monitoreo posquirúrgico remoto — Fuentes primarias del proponente (parte 2)

> **Documento histórico (junio de 2026).** Las frases sobre pasos o decisiones
> pendientes reflejan la sesión original. Para el estado vigente consulta
> `CLAUDE.md` y `ROADMAP_MONITOREO_POSQUIRURGICO.md`.

> Estos 4 documentos son distintos en naturaleza a todo lo analizado antes: no
> son literatura científica ni presentaciones informales, son **los documentos
> formales que el médico proponente presentó a la universidad**
> para registrar su proyecto de maestría (Maestría en TICs) ante la Dirección
> de Investigación e Innovación y el comité de ética. Dos de los cuatro
> archivos (`.doc`) se convirtieron a `.docx` para extraer el texto, y el
> `.pptx` se procesó directamente. Esto cambia su peso como evidencia: ya no es
> "lo que el médico dijo en un video", es **lo que quedó firmado y registrado**.

---

## 1. FR-IN-018 — Ficha Técnica General

**Resumen:** Formulario institucional de la universidad (Dirección de Investigación e Innovación) que registra los datos generales del proyecto. Título oficial registrado: **"Programa de cirugías colorrectales con seguimiento ambulatorio remoto."** Investigador: el médico proponente, cédula ********, estudiante de posgrado en la Maestría en TICs, rol "Investigador". Cubrimiento: institucional. Lugar de ejecución: la clínica donde ejerce. El proyecto involucra seres humanos (marcado con X), lo que obliga a diligenciar el formato FR-IN-024 (el siguiente documento de este análisis).

**Datos accionables:**
- Título oficial del proyecto ante la universidad: **colorrectal en general**, sin ninguna mención a Sugarbaker, HIPEC o citorreducción.
- Programa académico: Maestría en TICs — confirma que este es, formalmente, un proyecto de tecnología aplicada a la salud, no un proyecto clínico-quirúrgico puro.
- Institución de ejecución registrada: **la clínica donde ejerce** (no la clínica del proyecto).
- Cubrimiento declarado: institucional (no multicéntrico), lo cual contrasta con la lista de "instituciones candidatas" (Centro Oncológico de Antioquia, Clínica Las Vegas, etc.) que el médico menciona en sus presentaciones informales como expansión futura.

**Conexión con el proyecto:** Es la primera pieza de evidencia *formal* (no solo conversacional) de que el alcance académico registrado es "cirugía colorrectal" en sentido amplio. También introduce una pregunta nueva que no había aparecido antes: **el proyecto académico está registrado bajo la clínica donde ejerce, mientras que el MVP que se está construyendo (CLAUDE.md, ROADMAP) está enmarcado bajo la clínica del proyecto.** Puede ser que el médico trabaje en ambas instituciones (es coherente con que en sus presentaciones mencione varias clínicas de Medellín), pero vale la pena que el Arquitecto confirme si son la misma iniciativa con dos nombres, o si hay dos proyectos paralelos del médico que conviene no mezclar.

**Pros/contras de incorporar:** Pro — resuelve la pregunta de alcance con el peso de un documento institucional firmado, no solo de una opinión verbal; es la evidencia más fuerte para llevarle al médico si hace falta justificar un cambio de nombre/alcance del proyecto. Contra — abre una pregunta administrativa (la clínica donde ejerce vs. la clínica del proyecto) que no se puede resolver solo leyendo PDFs; requiere preguntarle directamente al médico.

---

## 2. FR-IN-024 — Ficha Técnica Comité de Ética en Humanos

**Resumen:** Formulario más extenso (6 páginas) para el comité de ética en investigación con humanos, también de la universidad, mismo título de proyecto. Define el objetivo general ("Desarrollar un programa de manejo ambulatorio o de corta estancia de procedimientos quirúrgicos de cirugía colorrectal"), tres objetivos específicos, tipo de estudio (cohorte prospectiva, datos primarios, sin aleatorización), clasificación de riesgo (mínimo, según Resolución 8430 de 1993), y de forma crítica, **los criterios de inclusión y exclusión formales**.

**Datos accionables:**
- **Criterios de inclusión:** "Paciente con Dx de Cáncer colorrectal programados para cirugía. ECOG 0 o 1, sin comorbilidades significativas."
- **Criterio de exclusión:** "Ausencia de apoyo social."
- Procedimiento descrito para el comité: "Monitorización de signos vitales de manera remota para pacientes en postoperatorio de cirugía colorrectal."
- Beneficios declarados al participante: mayor comunicación con el equipo tratante, más vigilancia de signos vitales postoperatorios, mayor seguimiento, más datos generados por el paciente.
- Pregunta 54 ("¿Se utilizarán equipos y/o dispositivos con registro INVIMA?") está marcada **No** — es decir, a la fecha de este formulario, el proyecto NO declara ante el comité de ética el uso de ningún dispositivo médico de monitoreo.
- Consentimiento informado: sí, por escrito, obtenido por el investigador.

**Conexión con el proyecto:** Este es, sin lugar a dudas, el hallazgo más fuerte de toda la auditoría para la decisión de alcance. El criterio de inclusión formal — **ECOG 0-1, sin comorbilidades significativas, cáncer colorrectal programado para cirugía** — describe a un paciente sustancialmente más sano y con una cirugía mucho menos extensa que el perfil típico de Sugarbaker/HIPEC (citorreducción + quimioterapia intraperitoneal, frecuentemente en pacientes con carcinomatosis peritoneal, cirugías de 6-10+ horas, mayor comorbilidad asociada a la enfermedad de base). **El proyecto, tal como está aprobado ante el comité de ética, no fue diseñado pensando en el paciente Sugarbaker** — fue diseñado para el paciente de colectomía electiva "sano" que protagoniza los 9 PDFs ya auditados. Adicionalmente, la respuesta "No" a la pregunta de dispositivos INVIMA confirma, con respaldo regulatorio, que el camino formalmente aprobado es el de monitoreo SIN hardware — coherente con que el bot de WhatsApp no requiera una enmienda regulatoria por ese lado.

**Pros/contras de incorporar:** Pro — si el Arquitecto necesita un argumento definitivo para resolver la pregunta de alcance, este es: el comité de ética no aprobó un proyecto Sugarbaker, aprobó un proyecto de colectomía electiva general. Seguir usando el nombre "MVP Sugarbaker" internamente está bien como apodo de equipo, pero diseñar el `alert_engine` asumiendo el perfil de riesgo de un paciente HIPEC contradice el criterio de inclusión que el propio médico registró. Contra — si en algún momento se quiere ampliar formalmente el estudio a pacientes Sugarbaker/HIPEC, eso requeriría una enmienda al protocolo ante el comité de ética (criterios de inclusión, clasificación de riesgo, posiblemente hasta la clasificación de "riesgo mínimo" podría no aplicar igual a un postoperatorio de citorreducción) — no es un cambio trivial de alcance, tiene una capa regulatoria detrás.

---

## 3. Preproyecto_Julio_5_2023 — Documento formal de preproyecto (la universidad)

**Resumen:** El documento más extenso y estructurado de toda la auditoría (21 páginas, formato de propuesta de investigación completa: planteamiento del problema, justificación, marco teórico, árbol de problemas/objetivos, metodología con marco lógico, consideraciones éticas, resultados esperados, impacto, ODS, presupuesto y cronograma). Cita 27 referencias, varias de las cuales **coinciden exactamente con los 9 PDFs ya auditados** (Lee et al., Gignoux et al. están en la bibliografía), confirmando una vez más que el corpus de literatura que se revisó es el que el propio médico construyó para su tesis.

**Datos accionables — hallazgos del marco lógico (la parte más importante del documento):**
- **Indicador de éxito del proyecto:** "Realización de 60% o más de las cirugías colorrectales de manera ambulatoria para el segundo año de realización del proyecto." Esta es la primera meta numérica explícita y medible de todo el proyecto: 60% de cirugías colorrectales en modalidad ambulatoria.
- El proyecto está dividido en **tres componentes formales**, no solo en el bot:
  - **Componente 1 — "Creación de solución de comunicación directa entre pacientes y equipo médico."** Meta: solución funcionando para abril 2024, piloto con ≥20 pacientes para enero 2024. **La actividad 2 especifica explícitamente "Diseño de solución vía web"** — el canal originalmente planeado era una aplicación web, no WhatsApp.
  - **Componente 2 — "Capacitar el personal para la realización de cirugía."** Protocolos escritos de anestesia y enfermería para colectomías ambulatorias, con reuniones informativas y protocolos formales — un workstream completamente humano/clínico que no tiene ningún equivalente en el código del proyecto (ni debería tenerlo).
  - **Componente 3 — "Definir el dispositivo para monitoreo remoto."** Meta: tener un dispositivo definido para marzo 2024, con una lista de proveedores en Colombia, y explícitamente buscando medir **presión arterial, frecuencia cardíaca, temperatura y saturación de O2**. Piloto planeado con 20 pacientes entre abril y julio de 2024.
- El árbol de objetivos (imagen del documento) muestra el objetivo central como **"Disminución de Estancia POP con el uso de Monitorización Remota en pacientes de Cirugía Gastrointestinal"** — un alcance todavía más amplio que "colorrectal": **cirugía gastrointestinal en general**. Los 6 medios listados para lograrlo incluyen tanto "Uso de Dispositivos de Monitorización Remota" como **"Encuestas a través de Apps"** — es decir, el camino que terminó tomando el bot de WhatsApp (encuestas conversacionales) era uno de los 6 medios planeados desde el inicio, no una desviación.
- Presupuesto total: $35,006,481.41 COP, financiado enteramente por la Dirección de Investigación e Innovación de la universidad, cubriendo únicamente horas de personal científico (el investigador y un asesor de maestría) — no hay partida presupuestal ejecutada para "Equipos y Software" (la fila existe en la tabla, pero está vacía).

**Conexión con el proyecto:** Este documento resuelve formalmente la pregunta de alcance (colorrectal/gastrointestinal en general, no Sugarbaker) y además expone algo que ningún documento anterior había mostrado: **el plan original tenía tres frentes paralelos, y el MVP de WhatsApp solo cubre una fracción del Componente 1.** El Componente 3 (el dispositivo de monitoreo con presión arterial, frecuencia cardíaca y saturación de O2) tenía fecha de definición para marzo de 2024 — hoy, junio de 2026, esa fecha lleva más de dos años vencida sin que el proyecto actual (Django + WhatsApp) la haya retomado. Esto no es necesariamente un problema, pero es una pregunta abierta que vale la pena resolver explícitamente con el médico: ¿el Componente 3 se abandonó deliberadamente a favor del enfoque conversacional (decisión razonable y respaldada por Outersterp 2025 y Coeckelberghs 2025, ya analizados), o sigue siendo una expectativa pendiente que el médico no ha vuelto a mencionar pero todavía espera?

**Pros/contras de incorporar:** Pro — la meta del 60% de cirugías ambulatorias es el primer KPI numérico y medible de todo el proyecto; podría usarse como criterio de éxito del MVP completo, no solo de la auditoría de PDFs. También, el hecho de que "Encuestas a través de Apps" estuviera en el plan original desde el árbol de objetivos significa que no hay que defender el enfoque del bot como una desviación — es ejecutar uno de los 6 medios planeados. Contra — el Componente 2 (protocolos de anestesia/enfermería) y el Componente 3 (dispositivo) representan trabajo pendiente que no es responsabilidad del equipo de software (León/Alejandro) y que probablemente el médico debe estar gestionando por su cuenta o ha dejado pausado; si el Arquitecto reporta avance del proyecto sin aclarar que estos dos componentes existen y no se han tocado, se puede dar una imagen de progreso más completa de la que realmente hay frente al proyecto académico total.

---

## 4. SDD_CRC (Autosaved).pptx — Diapositivas de la presentación "Preproyecto"

**Resumen:** Es el deck de 19 diapositivas que acompaña la transcripción de video ya analizada ("Preproyecto", documento previo de esta auditoría) — mismo contenido, mismo orden, mismas citas. No introduce un argumento nuevo, pero sí aporta el detalle bibliográfico exacto que la transcripción no tenía (la transcripción es audio, no incluye las referencias en pantalla) y dos datos biográficos y de cifras que no estaban en el video.

**Datos accionables (lo que el deck agrega sobre la transcripción ya analizada):**
- Formación del médico: Cirugía Oncológica, una universidad canadiense (2016); Cirugía General, una universidad pública colombiana (2013); Medicina, una universidad pública colombiana (2008).
- Comparación de costos por enfoque quirúrgico (cita: Am J Surg. 2012;204:952-957): cirugía convertida a abierta USD 59,709 vs. abierta USD 56,977 vs. laparoscópica USD 46,624; laparoscópica asociada a 1.87 días menos de estancia en promedio.
- Su experiencia personal en la clínica donde ejerce está descrita como **"En Proceso de Publicación"** — es decir, sus propios datos de mediana de estancia de 3 días no son todavía literatura publicada, son su propia base de datos no revisada por pares.
- Lista de instituciones candidatas en esta versión: otra clínica de la ciudad, Clínica Vida, Hospital Pablo Tobón Uribe, Clínica AUNA, Hospital Manuel Uribe Ángel, Centro Oncológico de Antioquia — una lista distinta (y más amplia) a la mencionada en el video de vigilancia tecnológica, lo cual sugiere que la lista de "dónde expandir esto" sigue siendo una idea en evolución, no una decisión cerrada.
- Pequeño detalle de control de calidad: la diapositiva sobre Gignoux describe la toma de PCR/hemoleucograma en "día 1, 3, 5 y 7", pero el PDF original de Gignoux que ya se auditó especifica día 1, 3 y 7 (sin día 5) — una discrepancia menor de memoria/cita del médico, sin mayor impacto, pero vale la pena no propagarla si se vuelve a citar este dato.

**Conexión con el proyecto:** Confirma, desde una tercera fuente, que Gignoux et al. es la referencia ancla y que el marco mental del médico desde el principio fue "cirugía colorrectal general", reforzando lo ya encontrado en la transcripción de video y en los formularios institucionales — es la pieza con menos información nueva, pero la que más triangula lo que ya sabíamos.

**Pros/contras de incorporar:** Pro — el dato de costos por enfoque quirúrgico (USD 46,624-59,709 según técnica) es útil como argumento económico complementario si se necesita justificar el proyecto ante un comité administrativo o financiero de la clínica. Contra — al ser esencialmente el mismo contenido que el video "Preproyecto" ya analizado, no cambia ninguna decisión técnica o de alcance por sí solo; su valor es de respaldo/triangulación, no de hallazgo nuevo.

---

## Síntesis — lo que estos 4 documentos resuelven (y lo que abren)

- **La decisión de alcance queda formalmente resuelta, no solo sugerida.** El título registrado ante la universidad y ante el comité de ética es "Programa de cirugías colorrectales con seguimiento ambulatorio remoto." El criterio de inclusión formal (ECOG 0-1, sin comorbilidades significativas) describe explícitamente un paciente que **no** es el paciente Sugarbaker/HIPEC típico. Esto ya no es una hipótesis de la auditoría de literatura — es lo que el médico firmó ante su comité de ética.
- **Aparece una pregunta institucional nueva:** los formularios de la universidad registran "la clínica donde ejerce" como sede, mientras que el MVP que se está construyendo se documenta bajo "la clínica del proyecto." Vale la pena que el Arquitecto confirme si son la misma cosa con dos nombres o dos proyectos relacionados pero distintos.
- **El plan original tenía 3 componentes; el MVP de WhatsApp cubre fracciones de uno solo.** El Componente 3 (dispositivo de presión arterial/frecuencia cardíaca/temperatura/SpO2, con fecha de definición marzo 2024) sigue sin resolverse dos años después de su fecha límite — la misma brecha que ya habíamos visto en el video, pero ahora con fechas formales vencidas, lo que le sube la prioridad a resolver esa conversación con el médico.
- **El enfoque de encuestas conversacionales (el bot) no es una desviación del plan — estaba en el árbol de objetivos original** como uno de 6 medios planeados, junto al uso de dispositivos. Es un argumento limpio para defender la arquitectura actual sin tener que presentarla como un cambio de rumbo.

---

Con esto quedan analizados los 5 archivos pendientes de la sesión anterior. Sigue pendiente la decisión de alcance (ahora con mucho más respaldo documental) y la auditoría final de `alert_engine.py`. ¿Cuál de las dos seguimos?
