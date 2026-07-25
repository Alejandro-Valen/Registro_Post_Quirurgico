# Método de trabajo con agentes de código

> **Qué es esto.** El método que este proyecto usa para corregir algo sin
> romperlo, destilado de lo que funcionó en los Loops A, B y C de la corrección
> post-auditoría (julio 2026). No es teoría: cada regla existe porque su
> ausencia costó algo concreto.
>
> Aplica a cualquier agente —Claude Code, Codex u otro— y también a una persona
> trabajando sola.

---

## Las seis reglas

### 1. Decidir antes de implementar

Ninguna decisión clínica o de producto se toma dentro del código. Se escribe
primero, con su razonamiento, en un documento de decisiones; recién entonces se
programa.

**Por qué:** una decisión tomada mientras se escribe código queda justificada
por lo que era cómodo de programar, no por lo que era correcto. Y seis meses
después nadie recuerda por qué el umbral es 4 y no 3.

### 2. Test en rojo primero, y verificar POR QUÉ está rojo

Para cada corrección de comportamiento se escribe la prueba que modela el
requisito, **se la ve fallar**, y solo entonces se toca el código.

**Por qué:** el hallazgo más grave de este proyecto —una escalera de alertas que
nunca escalaba en producción— sobrevivió a 280 pruebas en verde, porque la
prueba se había escrito mirando el código en vez del requisito.

> **Un test en verde no prueba nada si no se verifica por qué está verde.**

Durante el Loop A aparecieron dos pruebas defectuosas recién escritas: una
dependía de la hora del día, otra pasaba por el orden de los datos y no por la
regla que decía medir. Ambas se detectaron **porque se exigió ver el rojo y
entenderlo**.

Cuando una prueba no puede nacer en rojo —porque congela un comportamiento
existente en vez de denunciar un defecto— **se dice explícitamente en su
docstring**. Una prueba verde sin explicación es una prueba sospechosa.

### 3. Mover, no reescribir

Al reorganizar documentación o código, el contenido se **mueve textual**, con
script, y se verifica que nada quedó sin destino.

**Por qué:** reformular una regla clínica mientras se "ordena" es introducir un
cambio clínico sin que nadie lo apruebe. En la reorganización del 24/07 se
comprobó automáticamente que los 15 hashes de commit, 6 migraciones, 9 cifras de
tests y 108 identificadores de código del archivo original seguían teniendo
documento.

### 4. Verificación del Arquitecto al cerrar cada loop

No basta con que el agente informe que quedó bien. Quien aprueba **ejecuta una
comprobación propia** que imprime la evidencia en pantalla, antes de pasar a lo
siguiente.

**Por qué:** el agente que escribió el código es el peor juez de si el código
está bien. Las verificaciones viven en `docs/proceso/verificaciones/`.

### 5. Un loop por sesión, y el estado en un archivo

Cada loop cierra con sus commits, su push y su entrada de bitácora. El estado de
avance vive en un **archivo del repositorio**, no en la conversación.

**Por qué:** las sesiones se cortan, la conexión falla, el contexto se agota.
Todo lo que solo existe en un chat está perdido de antemano. La regla práctica:
*si mañana empieza otra persona con otro agente, ¿puede continuar leyendo el
repositorio?* Si la respuesta es no, falta escribir algo.

### 6. Sincronización documental no diferible

Todo cambio que se refleje en un documento de referencia se actualiza **en el
mismo lote de commits**. La narrativa de la bitácora puede acumularse hasta el
cierre; las tablas de referencia no.

**Por qué:** son lo primero que lee un agente antes de decidir qué hacer. Una
tabla desactualizada no es documentación incompleta: es documentación que miente.

---

## Cómo se pide una auditoría independiente

Lo que funcionó, y por qué cada parte importa:

1. **La instrucción se escribe en un archivo del repositorio**, no en el chat.
   El agente auditor no tiene la conversación previa; necesita un documento
   autocontenido que pueda leer del repo.
2. **Prohibición explícita de editar.** El auditor no arregla: reporta. Mezclar
   ambos roles hace imposible saber si un hallazgo era real o si el auditor lo
   creó al tocar algo.
3. **Evidencia reproducible por hallazgo.** Archivo, línea, y cómo verlo fallar.
   Sin eso no es un hallazgo, es una opinión.
4. **Clasificación obligatoria** por impacto: qué bloquea el merge, qué bloquea
   el uso con pacientes, y qué es mejora posterior. Sin esa separación, treinta
   observaciones de estilo entierran las tres que importan.
5. **Lista explícita de lo que NO debe reabrir:** las decisiones ya tomadas, con
   su documento. De lo contrario cada auditoría vuelve a discutir lo mismo.
6. **Los hallazgos se reproducen antes de actuar.** Un informe de otro agente es
   una hipótesis, no un hecho. La auditoría del 22/07 empezó confirmando las
   cuatro cifras que reportaba la sesión anterior; solo después la contradijo en
   lo demás.

---

## Errores que este método ya evitó

| Situación | Qué habría pasado sin la regla |
|---|---|
| Escalera de SILENCIO rota | Seguía en producción: las pruebas la daban por buena (regla 2) |
| Reorganizar 54.000 caracteres de documentación | Perder una regla clínica en el camino sin notarlo (regla 3) |
| Reescribir la condición de hinchazón | Cambiar cuándo se alerta a un paciente sin que nadie lo aprobara (reglas 1 y 2) |
| Variables obligatorias en Railway | Se detectó al desplegar, no tres días después con un cron caído en silencio |
| Sesiones cortadas a mitad de trabajo | Empezar de cero cada vez (regla 5) |
