# Seguridad

Este sistema maneja **datos de salud de personas identificables**. En Colombia
eso los convierte en datos sensibles bajo la **Ley 1581 de 2012**, con un
régimen más estricto que el de cualquier otro dato personal.

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Los issues de este repositorio son visibles para
todo el que tenga acceso, y un reporte de vulnerabilidad detallado es un mapa
para explotarla.

Escribe directamente a los responsables del repositorio, o usa el aviso privado
de seguridad de GitHub (*Security → Report a vulnerability*).

Incluye, si puedes: qué falla, cómo reproducirlo, y qué se puede alcanzar con
ello. Si encontraste datos personales expuestos, **describe dónde están sin
copiar el dato en el reporte**.

## Qué consideramos vulnerabilidad aquí

Más allá de lo habitual, en este proyecto cuentan como fallo de seguridad:

- **Cualquier fuga de identidad de un paciente** — nombre, cédula o teléfono en
  logs, correos, mensajes de error o salida de comandos operativos. El sistema
  identifica por `pk` a propósito.
- **Romper el aislamiento entre médicos.** Un médico solo debe ver a sus
  pacientes. Si encuentras una ruta que lo salte —un filtro, un autocompletado,
  una acción masiva, una exportación—, es un fallo grave aunque parezca menor.
- **Suplantar a un paciente** en el webhook, o inyectar telemetría a su nombre.
- **Impedir que una alerta ALTA llegue al médico.** Una alerta que no llega es
  un fallo de seguridad clínica, no solo de disponibilidad.
- **Una guardia automática que no puede fallar.** Un check que siempre sale en
  verde se ve exactamente igual que uno que funciona, y es peor que no tenerlo:
  da una confianza que no está respaldada. Ya ocurrió aquí (ficha D16).

## Lo que ya está en su sitio

Para que un reporte no repita lo conocido:

- **Webhook de Twilio** con validación de firma que falla de forma explícita si
  falta el token, idempotencia por `MessageSid` con reclamación condicional, y
  bloqueo de fila para el mismo paciente.
- **Aislamiento por médico** en los cinco `ModelAdmin`, en el tablero, en el
  desplegable de responsable y en las acciones masivas, que re-filtran por
  permisos en vez de confiar en los identificadores que manda el cliente.
- **Correos de alerta sin PHI**: solo el número de alerta y un enlace al panel.
- **Configuración de producción sin palancas por entorno**: `DEBUG` y la
  validación de firma están fijados en el código, no leídos de una variable.
- **Guardia de secretos** con `gitleaks` sobre la historia completa en cada PR,
  con una regla propia para la `SECRET_KEY` de Django y otra para números de
  cédula.
- **Auditoría de dependencias** con `pip-audit` en cada PR.

## Lo que sabemos que falta

Se dice aquí en vez de esperar a que alguien lo "descubra":

- **El formulario público recoge datos de salud sin autorización de tratamiento**
  (hallazgo SEC-03 de la auditoría del 07/09/2026, **severidad ALTA**, todavía
  sin corregir). `home/views.py` guarda en `MensajeContacto` el nombre, el
  teléfono y un campo libre que dice *"Cuéntanos brevemente qué necesitas…"* —
  donde un paciente va a escribir su estado de salud— y los conserva
  indefinidamente. Los tres campos son obligatorios.

  **No hay casilla de autorización, ni finalidad declarada, ni responsable
  identificado, ni enlace a una política de tratamiento.** La única frase es
  *"La información enviada quedará registrada para revisión del equipo médico"*,
  que no es autorización previa, expresa e informada; y para datos sensibles el
  artículo 6 de la Ley 1581 de 2012 exige autorización **explícita**.

  Contrasta con el rigor del formato de consentimiento
  (`docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`), que cubre al paciente ya
  inscrito pero **no a quien escribe por la web**. Lo que falta: casilla
  obligatoria, página de política de tratamiento, y una retención definida para
  `MensajeContacto`.

- **No hay registro de accesos de lectura.** Django registra las escrituras del
  Admin, no las consultas. Hoy no se puede saber qué médico consultó qué ficha.
  Con un solo médico el impacto es teórico; con dos deja de serlo.
- **Sin cifrado a nivel de aplicación.** Nombre, cédula y teléfono están en
  claro en la base; la protección depende del cifrado de disco del proveedor.
- **Sin política de retención ni procedimiento de supresión.** El formato de
  consentimiento fija una conservación mínima de cinco años, pero no hay máximo
  ni una herramienta para ejercer el derecho de supresión.
- **Datos personales en la historia de git.** El nombre y la cédula de un
  tercero entraron al repositorio en junio de 2026 y siguen siendo recuperables
  con `git show`, aunque estén fuera del árbol de trabajo. Registrado con su
  razón en `.gitleaksignore` y en la ficha D17.

## Secretos

- El `.env` **nunca** se versiona. La CI lo comprueba en cada PR.
- Si un secreto llega a entrar: **se rota primero y se limpia después.** Un
  secreto en la historia sigue siendo válido aunque el archivo desaparezca.
- Las excepciones históricas viven en `.gitleaksignore`, **cada una con la
  comprobación de por qué ya no abre nada**. Solo entra ahí lo que se verificó
  inofensivo; lo que sigue sirviendo se rota.

## Aviso

Este software **no es un dispositivo médico certificado** y no ha sido evaluado
por ninguna autoridad sanitaria. No debe usarse para tomar decisiones clínicas
sobre pacientes reales sin cumplir la normatividad aplicable. Ver [LICENSE](LICENSE).
