# Análisis de Transcripciones — Presentaciones del médico proponente
## Monitoreo posquirúrgico remoto — Fuentes primarias del proponente

> **Documento histórico (junio de 2026).** Las frases sobre pasos o decisiones
> pendientes reflejan la sesión original. Para el estado vigente consulta
> `CLAUDE.md` y `ROADMAP_MONITOREO_POSQUIRURGICO.md`.

> A diferencia de los 9 PDFs científicos, estos dos documentos no son literatura
> revisada por pares — son transcripciones de presentaciones del propio médico
> que originó la idea del proyecto. Su valor no es evidencia clínica, es
> contexto fundacional: por qué quiere esto, qué modelo tenía en mente, y con
> qué literatura llegó a esa idea.

---

## 1. "Preproyecto" — Presentación general (sin fecha visible)

**Resumen:** El médico proponente (cirujano oncólogo, con fellowship internacional en cirugía oncológica) presenta el caso de negocio para monitoreo remoto postquirúrgico, partiendo de epidemiología colombiana: 3,222 casos nuevos de cáncer colorrectal en 2020, 57.59% requieren cirugía. Recorre la evolución histórica de la estancia hospitalaria (Reino Unido 1998-2010: mediana 11-17 días), la diferencia abierta vs laparoscópica, y el programa ERAS. Cita un estudio multicéntrico colombiano (Revista Colombiana de Cirugía, con la Clínica Reina Sofía) con mediana de 4 días, y su propia experiencia en la clínica donde ejerce con mediana de 3 días tras implementar ERAS. Cierra proponiendo ir más allá citando explícitamente el estudio de **Gignoux et al.** (157 colectomías ambulatorias, vigilancia telefónica + enfermeras a domicilio días impares, tasa de reingreso 6%) como su referencia ancla, y plantea el monitoreo remoto como el siguiente paso lógico.

**Datos accionables:**
- Colombia 2020: 3,222 casos nuevos de cáncer colorrectal/año, edad mediana 64 años, 57.59% requieren cirugía.
- Comparativo de estancia: Reino Unido histórico 11-17 días; cirugía abierta ~8 días; laparoscópica menor estancia y menos complicaciones.
- Benchmark nacional: Reina Sofía/multicéntrico colombiano, mediana 4 días con ERAS.
- Benchmark personal del médico: mediana 3 días en la clínica donde ejerce tras ERAS.
- Referencia ancla explícita: Gignoux et al. (157 pacientes, reingreso 6%) — el mismo PDF #7 ya analizado en la síntesis de literatura.
- Beneficios que el médico espera del monitoreo remoto (en sus palabras): menor tiempo de espera quirúrgica, más proyectos de investigación, menos complicaciones, detección más temprana, mayor costo-efectividad para las EPS, más PROMs, mayor disponibilidad de camas, mayor satisfacción del paciente.

**Conexión con el proyecto:** Este documento es el "por qué" detrás de todo el proyecto. Confirma dos cosas importantes para la decisión de alcance pendiente: primero, que **Gignoux es la referencia intelectual original** del médico — no llegó a los 9 PDFs por azar, el set de literatura que se auditó está alineado con su propio punto de partida. Segundo, y más relevante para la pregunta de alcance: en ningún momento de esta presentación se menciona Sugarbaker, HIPEC, ni citorreducción — el marco es "cirugía colorrectal" en sentido amplio, igual que en los 9 PDFs. El proyecto nació pensando en colectomía/cirugía colorrectal en general, y Sugarbaker apareció después (probablemente porque es lo que el médico hace con más frecuencia en su práctica), no porque la idea original fuera exclusiva de HIPEC.

**Pros/contras de incorporar:** Pro — es el argumento más fuerte hasta ahora para resolver la decisión de alcance: si el propio fundador de la idea la concibió como "ERAS colorrectal general", renombrar/replantear el proyecto en esos términos no es una desviación, es volver a la intención original. También da munición de negocio (datos de epidemiología y benchmarks de estancia) útiles si hay que justificar el proyecto ante la clínica o una EPS. Contra — no aporta ningún dato clínico nuevo o umbral aprovechable para `alert_engine.py`; es contexto y narrativa, no especificación técnica.

---

## 2. "video1756390509" — Ejercicio académico de vigilancia tecnológica (PESTEL + mercado)

**Resumen:** Grabación de un ejercicio de clase (probablemente de una maestría/especialización en innovación o gestión, dado el lenguaje de PESTEL y TAM/SAM/SOM). El médico proponente se identifica como cirujano oncólogo de la clínica donde ejerce y profesor universitario, y menciona de paso que **el mismo día hizo un procedimiento de Sugarbaker** (citorreducción + quimioterapia intraperitoneal) — la única mención explícita a Sugarbaker en cualquiera de los dos documentos, y aparece como anécdota de agenda, no como el foco de la investigación. Su idea de investigación, en sus palabras, es usar dispositivos de monitoreo remoto para reducir estancia hospitalaria, aumentar satisfacción, y reducir ingresos a urgencias y costos — sin acotar a un tipo de cirugía específico. Desarrolla un análisis PESTEL completo (tendencias en Google Trends, políticas de reembolso en EE. UU., el mercado de mHealth proyectado en USD 12.1 mil millones para 2030, dispositivos comerciales de Medtronic/Surgical Company/Philips, e influencers como Eric Topol) y termina con un ejercicio de tamaño de mercado *bottom-up* basado en su propia casuística.

**Datos accionables:**
- **Variables que el médico quiere medir con dispositivos:** temperatura, frecuencia cardíaca, presión arterial — y menciona dispositivos comerciales que además miden frecuencia respiratoria, marcha, simetría de pasos, caídas, posición corporal y "síntomas similares a infección" (PaiVal de Medtronic).
- **Meta personal explícita:** bajar de su mediana actual (~48h) a colectomía de 23 horas o menos; identifica el monitoreo remoto como "el engranaje que falta".
- **Casuística propia:** 324 procedimientos en 2.5 años en la clínica donde ejerce que podrían beneficiarse de esto (~10.8/mes).
- **Modelo de costos que él mismo cotizó** con un proveedor de Medellín ("Smart Monitor"): activación ~3,000,000 COP por 15 dispositivos + 20,000 COP/dispositivo/mes, diluido a ~250,000 COP/mes + personal de enfermería para vigilar resultados (~1,120,000 + 1,700,000 COP/mes) → costo estimado por paciente desde ~850,000 COP dentro de un paquete quirúrgico.
- **Mercado objetivo identificado:** Centro Oncológico de Antioquia, la clínica donde ejerce, Clínica Las Vegas, Clínica UNA (todas en Medellín/Grupo Quirón).
- **Frase clave del propio médico:** *"lo importante aquí no es la tecnología, sino el servicio, el monitoreo y el contacto con el paciente"*.

**Conexión con el proyecto:** Este documento revela una brecha importante entre la visión original del médico y lo que el MVP construyó. Su modelo mental era **hardware-céntrico**: wearables/parches que miden signos vitales objetivos (temperatura, frecuencia cardíaca, presión arterial) de forma continua, con un proveedor externo y un costo por paciente de ~850,000+ COP. Lo que Somer construyó es exactamente lo opuesto en términos de infraestructura: un bot conversacional de WhatsApp sin ningún dispositivo, costo marginal de hardware cero, que captura variables distintas (dolor EVA, aspecto y cantidad de drenaje, gases, náuseas) — ninguna de las cuales es frecuencia cardíaca o presión arterial. Aquí hay dos lecturas posibles: (a) el sistema actual no cumple la visión original del médico porque no mide signos vitales objetivos, o (b) el sistema actual cumple mejor el principio que el propio médico articuló — "el valor es el servicio y el contacto, no la tecnología" — y lo hace con un costo y una complejidad de implementación muchísimo menor que el modelo de wearables que él mismo cotizó. La síntesis cruzada de la literatura (Outersterp 2025, Coeckelberghs 2025) respalda fuertemente la lectura (b): el monitoreo continuo de signos vitales por hardware no demostró valor predictivo adicional sobre cuestionarios + llamada.

**Pros/contras de incorporar:** Pro — el contraste de costos es un argumento de venta inmejorable para presentarle al médico: su propio modelo cotizado costaba ≥850,000 COP/paciente en hardware y monitoreo de terceros; el bot de WhatsApp logra el mismo objetivo declarado (reducir estancia, satisfacción, menos urgencias) a costo de infraestructura cercano a cero, y además está alineado con su propia frase ancla sobre el valor del servicio sobre la tecnología — vale la pena citársela textualmente en la próxima conversación. También reconfirma, con una fuente distinta a la de la presentación anterior, que el marco mental original es "cirugía abdominal/colorrectal en general" y que Sugarbaker es una mención incidental, no el foco. Contra — si el médico todavía espera medir frecuencia cardíaca y presión arterial (lo dijo explícitamente como las variables centrales de su idea original), hay una expectativa no resuelta: el WhatsApp bot no puede capturar esas dos variables de forma objetiva sin un dispositivo, y eso puede salir a la superficie como un "¿por qué no hicimos lo que yo propuse originalmente?" si no se aborda la conversación de forma proactiva.

---

## Lectura conjunta — lo que estos 2 documentos cambian (o no) de la auditoría anterior

- **La pregunta de alcance queda prácticamente resuelta del lado de la evidencia, no solo de la literatura.** Tanto los 9 PDFs como las dos presentaciones originales del propio médico enmarcan el problema como "cirugía colorrectal/abdominal en general", y Sugarbaker aparece en los documentos del médico exactamente una vez, de forma incidental. Esto no es ya solo un hallazgo de la literatura — es la intención original documentada del proponente.
- **Aparece una brecha nueva que no estaba en la síntesis de los 9 PDFs:** la ausencia de frecuencia cardíaca y presión arterial en `RegistroDiario`, frente a la expectativa original del médico de medir signos vitales objetivos con dispositivos. Vale la pena que el Arquitecto decida si esto se aborda explícitamente en la próxima conversación con el médico (mostrando por qué se optó por no usar hardware) en vez de dejarlo como un vacío implícito.
- **El costo del modelo de hardware que el médico mismo cotizó (~850,000+ COP/paciente) es el dato más persuasivo de toda la auditoría hasta ahora** para defender la arquitectura actual del MVP frente a cualquier sugerencia futura de "deberíamos comprar sensores".

---

Quedan 4 archivos sin analizar (`FR-IN-018`, `FR-IN-024`, `Preproyecto_Julio_5_2023.doc`, `SDD_CRC.pptx`) — estos son `.doc`/`.pptx`, no se leen directamente del chat, así que si quieres que siga con ellos los abro desde el sistema de archivos. También sigue pendiente la decisión de alcance y la auditoría final del alert_engine. ¿Cuál seguimos?
