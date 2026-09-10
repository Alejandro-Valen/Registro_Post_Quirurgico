# Instrucción para la próxima sesión — antes de la reunión del domingo

> **Qué es esto.** El guion de la sesión que sigue al día de los cuatro ítems.
> Se escribió el **09/09/2026**, al cerrar, sabiendo que la próxima sesión puede
> ser el sábado y que **la reunión es el domingo a las 18:00**.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**09/09/2026 — cuatro PR mergeados el mismo día:**

| PR | Qué | Merge |
|---|---|---|
| #30 | SEC-02: el bloqueo de acceso deja de castigar al médico (ficha **D24**) | `35e2c9d` |
| #31 | Dependabot agrupa también las menores | — |
| #33 | BE-02 y la verificación de los hallazgos de la auditoría | `ad9f6ed` |
| #34 | La página para la reunión | `ffcc966` |

**Suite: 420 tests OK.** La CI corre **diez comprobaciones**. **Cero PR abiertos.**

De los 101 hallazgos de la auditoría del 07/09, **78 tienen estado comprobado**
(32 cerrados, 3 a medias, 44 abiertos confirmados) y **23 siguen sin verificar**.

**Sigue sin haber producción** (venció Railway el 07/08/2026). Comprobado el
09/09: el endpoint de salud responde 404.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo. Soy León (Arquitecto y desarrollador principal).

Antes de tocar nada:
1. Lee proceso/instrucciones/2026-09-09_instruccion_antes_de_la_reunion.md — es
   el guion de esta sesión.
2. Verifica el estado real con git log, git status, ruff, la suite y el barrido
   de veracidad. Si algo no coincide con los documentos, manda Git y avísame.

La reunión con el médico, el ingeniero y Alejo es el DOMINGO a las 18:00. El
objetivo de esta sesión es que no quede nada que un profesional externo mire y
piense que no sabemos lo que hacemos.

Empieza por los tres bugs visibles (UX-B03, UX-P05, UX-L01). Son los únicos que
se ven sin abrir el código.

Un loop, un tema. Las decisiones que necesiten mi criterio, todas juntas al
principio, con qué implica cada una y tu recomendación.

Contexto: no hay producción en Railway; la política de datos está en BORRADOR a
propósito porque le faltan datos míos; y el canal del paciente, el repo
público/privado y avisar al médico van a la reunión, no se deciden aquí.
```

---

## El orden, y por qué este y no el de completitud

`CLAUDE.md` dice que el próximo paso son los 23 hallazgos sin verificar. **Para
esta sesión concreta, no.** Falta una semana de trabajo para dejar los 101
cerrados y **queda un día antes de la reunión**, así que lo que se haga tiene que
elegirse por lo que se ve, no por lo que falta.

### 1 · Los tres bugs visibles (prioridad máxima)

Los únicos hallazgos abiertos que alguien puede encontrar **sin leer una línea de
código**:

| | Qué pasa | Por qué pesa |
|---|---|---|
| **UX-B03** | *"si, no tuve nauseas: 0"* se registra como **sin gases** | **Corrompe datos clínicos.** El paciente dice que sí pasó gases y el sistema anota lo contrario, alimentando la regla de íleo con un dato falso. Es el único de UX que no es cosmético |
| **UX-P05** | La gráfica va de 35 a 40 °C; el bot acepta hasta 45 | **El valor más grave es el único que no se dibuja.** Un paciente con 41 °C aparece como si no hubiera dato |
| **UX-L01** | En móvil desaparecen los cuatro enlaces del menú | **El único visible lleva al login del Admin.** Un paciente que entre desde el móvil ve una web cuyo único botón es para el personal |

Los tres están reproducidos y localizados. **UX-B03 es el que hay que hacer sí o
sí**: los otros dos son de presentación; ese produce un dato clínico falso.

**Cuidado con UX-B03.** Arreglarlo toca `_parse_gases_nauseas`, que es código
clínico: cambia qué se guarda. Sigue el método —decidir, documentar, prueba en
rojo, implementar, verificar en las dos direcciones— y **pregunta antes** si la
corrección puede cambiar cuándo dispara una regla.

### 2 · SEC-05, el gemelo de la ficha D15

`crear_medico` dejó de reescribir la contraseña en cada arranque el 12/08/2026.
**`crear_admin` sigue haciendo exactamente eso**, y además promueve a
superusuario sin condición. Se arregló uno y se dejó vivo el otro.

No es clínico, la decisión ya está tomada en D15, y hay un precedente exacto que
copiar. **Es la corrección más barata que queda con más valor por hora.**

### 3 · Las 22 ramas muertas

Todas fusionadas en `Desarrollo`; no se pierde nada al borrarlas. Es cosmético
del repositorio, pero es de lo primero que ve alguien que llega. **Falta el visto
bueno explícito del Arquitecto.**

### 4 · Los 23 hallazgos sin verificar

Después de la reunión. Necesitan leer código con calma —ramas de la máquina de
estados, semántica de pruebas, reversibilidad de migraciones, cuatro de seguridad
que dependen de infraestructura— y **ninguno es visible al abrir la aplicación**.

---

## Si solo hay tiempo para una cosa

**UX-B03.** Es el único de la lista que hace que el sistema guarde un dato clínico
falso. Todo lo demás se puede explicar en la reunión; eso no.

---

## Lo que NO se hace en esta sesión

- **No se toca ningún umbral clínico.** BE-08 y BE-09 están fijados con pruebas
  de caracterización y **esperan al médico**. Cambiarlos antes de la reunión
  sería exactamente lo contrario de lo que se decidió.
- **No se rellenan los corchetes** de la landing, la política de datos ni el
  formato de consentimiento. Esos datos los da el Arquitecto o el médico; **no
  se inventan**.
- **No se decide el canal, ni público/privado, ni avisar al médico.** Van a la
  reunión.
- **No se propone nada que dependa de desplegar.** No hay dónde.

---

## Para la reunión

**`docs/PARA_LA_REUNION.md`** está listo y se sostiene solo. Nueve secciones: qué
es el sistema, qué está verificado, **qué no hay**, y once decisiones agrupadas
por quién puede tomarlas —tres del grupo, cinco del médico, tres administrativas—.

Si la sesión anterior a la reunión no llega a ocurrir, **esa página ya sirve tal
como está**. Las cifras que da estaban comprobadas con un comando el 09/09/2026.

**Lo único que conviene revisar antes de enseñarla:** si se arregla alguno de los
tres bugs visibles, la página no lo sabe. El recuento de hallazgos vive en
`proceso/auditorias/2026-09-07_auditoria_seis_frentes.md`, y la página lo copia.

---

## Un recordatorio de método

Lo que dejó esta sesión, en una línea:

> **Tres pruebas escritas la misma tarde no medían lo que decían, y las tres las
> destaparon sus arneses.**

Una se adaptaba al sabotaje (`range(settings.AXES_FAILURE_LIMIT)`), otra comparaba
dos implementaciones en el único escenario donde coinciden por casualidad, y la
tercera usaba números con los que las dos lecturas daban el mismo resultado.

Ninguna se habría detectado leyendo el código. **Por eso el arnés no es opcional,
y por eso restaura siempre en un `finally`:** improvisar uno sin él dejó el motor
clínico saboteado en disco durante un minuto.
