# Para la reunión

> **Qué es esto.** Una página para que quien llega —el médico, un profesional de
> desarrollo— **decida en veinte minutos** en vez de gastarlos descubriendo en
> qué estado está el sistema.
>
> **Fecha del corte:** 09/09/2026. Todo lo que aquí se afirma está comprobado
> con un comando; lo que no, se dice.
>
> **Cómo leerla.** La primera mitad es contexto: qué hace el sistema y qué está
> verificado. La segunda es la única que pide algo: **once decisiones que
> necesitan una persona**, agrupadas por quién puede tomarlas.

---

## 1 · Qué es el sistema, en un párrafo

Seguimiento remoto de pacientes que se recuperan en casa de una cirugía
colorrectal. El paciente responde por WhatsApp un cuestionario dos veces al día
—temperatura, dolor, drenaje, gases, náuseas, líquidos, hinchazón, pulso,
respiración—. Un motor de reglas fijas clasifica esos datos y genera alertas de
tres niveles para el médico, que las ve en un panel.

**La IA no diagnostica.** Son reglas escritas, con base en evidencia de
recuperación postoperatoria (protocolos ERAS), y ninguna se cambia sin decisión
del médico. Al paciente nunca se le muestra la clasificación clínica: recibe una
recomendación de acción, no un diagnóstico.

---

## 2 · Qué está verificado, y con qué

| | |
|---|---|
| **Suite de pruebas** | **420**, todas en verde |
| **Comprobaciones automáticas por cada cambio** | **10**, y todas bloquean |
| **Reglas clínicas documentadas** | 24, y una guardia comprueba que el documento y el código digan lo mismo |
| **Decisiones registradas** | 24 fichas, cada una con su porqué y la alternativa descartada |
| **Arneses de verificación** | 12 scripts que **rompen el sistema a propósito** para comprobar que las pruebas lo detectan |

**Lo que hace distinto a este proyecto** es el último punto. Aquí no basta con
que una prueba esté en verde: hay que haberla visto ponerse en rojo. Nació de un
hallazgo concreto —un sabotaje de una línea sobre el motor clínico dejó **344
pruebas en verde con el sistema roto**— y hoy es la norma escrita.

**Auditorías realizadas:** tres, independientes entre sí (22/07, 27/07 y una de
seis frentes el 07/09). La última encontró 101 hallazgos. **Su estado está
verificado uno a uno**, y el informe distingue tres cosas que suelen confundirse:
cerrado, confirmado abierto, y **sin comprobar todavía**.

---

## 3 · Qué NO hay, dicho claro

- **No hay producción.** El periodo de prueba del proveedor venció el
  07/08/2026. Comprobado hoy: el endpoint de salud responde **404**. Nada de lo
  que se decida aquí se puede desplegar sin un plan de pago.
- **No hay pacientes reales.** Nunca los ha habido.
- **El canal de WhatsApp está en entredicho** por la Resolución 1644 de 2026 —
  ver la decisión 1 más abajo.
- **El envío saliente al paciente es un simulacro.** El sistema es reactivo: el
  paciente tiene que escribir primero. Los mensajes que prometen «te escribiré
  cuando sea la hora» **no los cumple nadie hoy**.

---

## 4 · Las decisiones · para el grupo

Estas tres no las puede tomar una sesión técnica y bloquean lo demás.

### 4.1 · El canal del paciente
**La Resolución 1644 de 2026 deja a WhatsApp fuera** para datos clínicos. Las
opciones vivas son tres: reposicionar el proyecto como piloto de investigación
—lo que exige comité de ética—, migrar a una plataforma propia, o un híbrido.
**Decide casi todo lo demás**, incluido si tiene sentido invertir en el bot
actual.

### 4.2 · Repositorio público o privado
Hoy es privado, y eso tiene una consecuencia que sorprende: **GitHub no ofrece
protección de rama en repositorios privados de cuentas sin plan de pago**, ni
siquiera al dueño. Por eso las comprobaciones automáticas se ven pero no
bloquean el merge: hay una compuerta humana en su lugar. Las salidas son plan de
pago (~4 USD/mes), hacerlo público, o seguir mirando a mano.

### 4.3 · Avisarle al médico de sus datos en la historia del repositorio
Su nombre y su cédula estuvieron en el repositorio y **siguen en la historia de
git**, recuperables. Ya no están en el árbol de trabajo. Es un tercero
identificable que no consintió eso. La decisión es si se le informa y si se
reescribe la historia.

---

## 5 · Las decisiones · para el médico

Cinco preguntas clínicas. **Ninguna requiere leer código.**

### 5.1 a 5.3 · Las tres respuestas que el bot le da al paciente
Cuando el paciente pregunta algo fuera del cuestionario, el bot responde con un
texto fijo. Hoy hay tres —fiebre, dolor, alimentación— **redactados por el
equipo técnico y sin validar clínicamente** (ficha **D4**). Están en
`signos_sintomas/knowledge_base.md`, con la pregunta concreta al lado de cada
uno; se responden sobre ese mismo documento en unos diez minutos.

**Una regla que conviene conservar:** ninguna respuesta contiene un umbral
numérico. Si el paciente se auto-evalúa con un número propio, puede quedarse
tranquilo justo cuando el sistema ya escaló.

### 5.4 · BE-08 — una subida brusca de dolor con valor absoluto bajo

Un paciente en el **día 2** con dolor **3 sobre 10** —por debajo del umbral de
esa fase— pero que venía de **0** hace dos días.

- **Hoy el sistema avisa MEDIA:** «llamar al médico».
- **La regla escrita, leída literal, daría BAJA:** «monitorear».

**Pregunta:** ¿una subida de tres puntos merece que le llamen, aunque el dolor
absoluto sea bajo?

*(Hay una segunda mitad, técnica y sin efecto hoy: el promedio se calcula por
reporte y no por día. Empieza a importar cuando entren los dos reportes diarios.)*

### 5.5 · BE-09 — un día en que no se capturó el dato de líquidos

El paciente **sí reportó** ayer, pero la pregunta de si toleró líquidos quedó sin
respuesta. Hoy dice que no tolera.

- **Hoy el sistema cuenta dos días y avisa ALTA:** «ir a urgencias».
- **Si ese día no contara, sería MEDIA:** «vigilar hidratación».

**Pregunta, en una línea:** *¿es lo mismo «no dijo nada» que «no le preguntamos
esto»?*

A favor de que cuente: la deshidratación es la causa número uno de reingreso, y
ahí conviene pasarse de sensible. A favor de que no cuente: el propio sistema ya
decidió que un día sin datos no debe contar, porque hacerlo inventa un hecho
clínico.

> **Las dos, BE-08 y BE-09, avisan de MÁS y nunca de menos.** Ningún paciente
> deja de generar alerta por ellas. Por eso se han dejado quietas y solo se han
> escrito: no corría prisa, y cambiarlas sin el médico habría sido peor.

---

## 6 · Las decisiones · administrativas

### 6.1 · Los datos del médico en la web pública
La página muestra `[Nombre y apellido]`, `[Institución donde ejerce]`,
`[correo@del-consultorio.com]` y seis marcadores más. Hace falta el texto real,
logo y colores. Hasta entonces la web lleva un aviso de borrador.

### 6.2 · La política de tratamiento de datos
Existe la página y la casilla obligatoria de autorización —eso ya está
funcionando y probado— pero **la política está publicada como BORRADOR** porque
le faltan cuatro datos que solo puede dar el responsable: quién responde del
tratamiento, su dirección, el canal para ejercer los derechos, y cuánto tiempo se
conservan los mensajes. **No se ha inventado ninguno.**

### 6.3 · El formato de consentimiento
`docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md` tiene **11 marcadores** sin
rellenar. Es el documento que firma el paciente antes de entrar.

### 6.4 · La cuenta del médico
Existe `medico_piloto`, probada y con permisos correctos. Hay que decidir si se
le transfiere o se crea la definitiva.

---

## 7 · Si se decide seguir: qué haría falta para un piloto real

En orden, y ninguno es opcional:

1. **El canal**, según la decisión 4.1.
2. **Plan de pago del proveedor** — sin él no hay dónde desplegar.
3. **Salir del entorno de pruebas de la mensajería** al canal definitivo.
4. **Dominio verificado** para el correo de alertas.
5. **Monitoreo externo** que avise si el sistema deja de responder. Hoy, si se
   cae de madrugada, nadie se entera.
6. **Los formatos legales completos** — 6.2 y 6.3.
7. **Repetir la prueba de punta a punta** sobre el canal definitivo.

---

## 8 · Dónde mirar cada cosa

| Pregunta | Documento |
|---|---|
| ¿Qué reglas clínicas hay y por qué esos umbrales? | `docs/reglas_clinicas.md` |
| ¿Qué se decidió, cuándo y descartando qué? | `docs/decisiones_correccion_auditoria.md` (24 fichas) |
| ¿Qué encontraron las auditorías y qué queda abierto? | `proceso/auditorias/2026-09-07_auditoria_seis_frentes.md` |
| ¿Qué evidencia científica respalda cada umbral? | `docs/auditoria_literatura/` |
| ¿Qué falta de seguridad, dicho por el propio equipo? | `SECURITY.md` |
| ¿Cómo se instala y se trabaja aquí? | `README.md` y `CONTRIBUTING.md` |

---

## 9 · Lo que este documento no dice

- **No opina sobre si el proyecto debe continuar.** Reúne lo necesario para
  decidirlo.
- **No estima plazos ni costes.** No hay base para hacerlo con honestidad.
- **No cubre los hallazgos técnicos abiertos** que no necesitan a nadie de
  fuera: están en el informe de la auditoría, con su estado verificado, y se
  cierran en sesión técnica.
