# Formato de Consentimiento Informado — Tratamiento de Datos Personales Sensibles
## Sistema de Monitoreo Posquirúrgico Remoto

> **Estado:** plantilla base — debe ser revisada y aprobada por el médico
> responsable antes de usarse con pacientes reales.
> El texto entre [corchetes] debe ser completado por el médico o la institución.
>
> **Para el equipo de desarrollo:** este formato se entrega impreso al paciente.
> Una vez firmado físicamente, el médico marca `consentimiento_informado = True`
> en el perfil del paciente dentro del sistema (Django Admin). El documento
> físico queda en la historia clínica del paciente.

---

## AUTORIZACIÓN PARA TRATAMIENTO DE DATOS PERSONALES SENSIBLES

---

### RESPONSABLE DEL TRATAMIENTO

| Campo | Valor |
|-------|-------|
| Nombre completo / Razón social | [Nombre del médico o institución] |
| Cargo / Especialidad | [Ej: Cirujano de colon y recto] |
| Dirección | [Dirección de la clínica o consultorio] |
| Correo electrónico | [correo del médico — para ejercer derechos HABEAS DATA] |
| Teléfono | [teléfono de contacto] |

---

### ENCARGADO DEL TRATAMIENTO (operador técnico)

El sistema de monitoreo es operado técnicamente por:

| Campo | Valor |
|-------|-------|
| Nombre / Proyecto | [Nombre del equipo de desarrollo] |
| Contacto técnico | [correo del equipo] |

> El encargado técnico accede a los datos únicamente para operar y mantener
> el sistema. No toma decisiones clínicas ni comparte datos con terceros.

---

### DATOS QUE SE RECOLECTAN

A través de mensajes de WhatsApp durante su período de recuperación, el
sistema recolectará diariamente los siguientes datos de salud:

**Signos vitales y síntomas (2 veces al día):**
- Temperatura corporal (°C)
- Nivel de dolor según escala EVA (1 a 10)
- Presencia y características del drenaje quirúrgico
- Presencia de gases intestinales
- Episodios de náuseas
- Nivel de hinchazón abdominal
- Frecuencia cardíaca (latidos por minuto)
- Frecuencia respiratoria (respiraciones por minuto)
- Tolerancia a líquidos orales

**Datos de identificación:**
- Nombre completo
- Número de cédula de ciudadanía
- Número de teléfono WhatsApp

---

### FINALIDAD DEL TRATAMIENTO

Los datos recolectados se usan exclusivamente para:

1. Monitoreo remoto de su recuperación posquirúrgica por su médico tratante
2. Generación de alertas clínicas automáticas para detección temprana de
   complicaciones posquirúrgicas
3. Seguimiento de la evolución clínica durante el período postoperatorio

**Los datos NO se usan para diagnóstico automático, investigación comercial,
ni se comparten con terceros distintos a su médico tratante.**

---

### TIEMPO DE CONSERVACIÓN

Sus datos se conservarán por un mínimo de **5 años** contados desde la
fecha de su cirugía, conforme a la Resolución 1995 de 1999 del Ministerio
de Salud de Colombia (normas de historia clínica).

---

### SUS DERECHOS — Ley 1581 de 2012, artículo 8

Usted tiene derecho a:

- **Conocer** los datos que el sistema tiene sobre usted
- **Actualizar** o **rectificar** datos inexactos o incompletos
- **Solicitar prueba** de esta autorización
- **Revocar** esta autorización en cualquier momento — lo que implicará
  la suspensión del monitoreo remoto por WhatsApp
- **Presentar quejas** ante la Superintendencia de Industria y Comercio
  (www.sic.gov.co) si considera que sus derechos han sido vulnerados

**Para ejercer cualquiera de estos derechos, contacte a:**

```
[Nombre del médico responsable]
[Correo electrónico]
[Teléfono]
```

---

### AUTORIZACIÓN DEL PACIENTE

Yo, __________________________________________________, identificado/a
con cédula de ciudadanía número _________________ de _________________,
en pleno uso de mis facultades mentales, declaro que:

1. He leído y entendido esta autorización
2. El médico me ha explicado el funcionamiento del sistema de monitoreo
3. Autorizo de forma **libre, previa e informada** el tratamiento de mis
   datos personales sensibles de salud según los términos descritos arriba
4. Entiendo que puedo revocar esta autorización en cualquier momento
   contactando a mi médico responsable

```
Firma del paciente: ___________________________

Fecha: ___ / ___ / ______

Huella dactilar (pulgar derecho):




```

---

### CONFIRMACIÓN DEL MÉDICO RESPONSABLE

Yo, Dr./Dra. _________________________________________, confirmo que:

- Expliqué al paciente el funcionamiento del sistema de monitoreo remoto
- Respondí todas sus preguntas antes de solicitar la firma
- Obtuve su consentimiento de forma libre e informada

```
Firma del médico: ___________________________

Fecha: ___ / ___ / ______

Sello de la institución (si aplica):




```

---

## Notas para el equipo de desarrollo

- Este formato se imprime y firma físicamente. El papel queda en la
  historia clínica del paciente — no se digitaliza ni se sube al sistema.
- Una vez firmado, el médico entra al Admin → perfil del paciente →
  marca `Consentimiento informado = ✓` → guarda. El sistema registra
  automáticamente la fecha y hora de esa confirmación.
- Si el paciente revoca su consentimiento, el médico desmarca el campo.
  El bot dejará de responder al paciente hasta nueva autorización.
- El equipo de desarrollo (encargado técnico) **no firma** este formato
  ni es responsable del tratamiento — esa responsabilidad recae en el
  médico o su institución.

---

*Plantilla generada el 01/07/2026.*
*Referencia legal: Ley 1581 de 2012, Decreto 1377 de 2013, Resolución 1995/1999 MinSalud Colombia.*
*Pendiente: revisión y aprobación del médico responsable antes del primer uso con pacientes reales.*
