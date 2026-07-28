# Modelos de datos

> **Fuente única.** Describe los modelos de `signos_sintomas/models.py`: qué
> guarda cada campo y **por qué**, que es lo que el código no puede contar
> solo. Al cambiar un modelo, este archivo se actualiza en el mismo lote de
> commits.
>
> Las reglas que consumen estos datos viven en `docs/reglas_clinicas.md`.

---

## Modelos de Base de Datos

### Paciente (Sprint 1, ampliado en fase de generalización, Sprint 5)
```python
nombre_completo       CharField(200)
cedula                CharField(20) unique=True null=True blank=True
                      # identificador principal (P-4). Obligatorio para pacientes
                      # nuevos vía Paciente.clean() (A-2); null solo permitido en
                      # registros previos a esta versión. blank=True a nivel de
                      # campo a propósito — la exigencia vive en clean(), no en el
                      # campo, para no romper full_clean() de pacientes legado.
telefono_whatsapp     CharField(20) unique  # identificador para el bot
fecha_cirugia         DateField
tipo_cirugia          CharField choices=[sugarbaker_hipec,colectomia_electiva,otra] null=True blank=True
medico_responsable    ForeignKey(User, PROTECT, null=True, blank=True)
                      # related_name='pacientes' — médico accede a sus pacientes con
                      # medico.pacientes.all()
                      # D12 (capa 2, migración 0027): era SET_NULL. Borrar una
                      # cuenta de médico dejaba a sus pacientes huérfanos e
                      # invisibles en silencio. Django ahora se niega a borrar
                      # la cuenta mientras tenga pacientes: hay que reasignarlos.
                      # Regla operativa: las cuentas de médico NO se borran, se
                      # desactivan (is_active=False), y antes de desactivar una
                      # se reasignan sus pacientes activos.
                      # null=True sigue: las fichas históricas e inactivas
                      # conservan lo que tengan, incluido NULL. Exigirles un
                      # médico obligaría a inventarles uno.
activo                BooleanField default=True
                      # Gobierna la restricción de abajo: mientras esté en True,
                      # la base exige medico_responsable.
consentimiento_informado  BooleanField default=False
                      # HABEAS DATA (Bloque 7, P-15). El bot no inicia el flujo con
                      # el paciente hasta que el médico marque este campo en el Admin.
fecha_consentimiento  DateTimeField null=True blank=True
                      # auto-registrada/limpiada en PacienteAdmin.save_model — el
                      # médico no la edita directamente (readonly en el Admin).
fecha_registro        DateTimeField auto_now_add=True
```

**Restricciones de base (`Meta.constraints`)**

| Nombre | Qué garantiza | Migración |
|---|---|---|
| `paciente_tipo_cirugia_valido` | `tipo_cirugia` nulo o uno de los tres valores válidos | 0021 |
| `paciente_activo_con_medico_responsable` | **`activo=True` ⇒ `medico_responsable` no nulo** | **0028** |

La segunda es la capa 4 de D12 y su SQL es
`CHECK (NOT activo OR medico_responsable_id IS NOT NULL)`. Vive en la base
porque el formulario del Admin cubre el camino de todos los días y `PROTECT`
cubre el borrado, pero ninguno de los dos ve un script, el shell o una carga de
datos. Es **condicional y no `NOT NULL`** a propósito: las fichas históricas e
inactivas conservan lo que tengan.

**Consecuencia para las pruebas y para cualquier script:** crear un `Paciente`
sin `medico_responsable` explícito ahora falla, porque `activo` es `True` por
defecto. Las pruebas usan el helper `medico_de_pruebas()` de `tests.py`; un
paciente sin responsable debe crearse con `activo=False`.

**Decisión de diseño (fase de generalización):** `tipo_cirugia` es un dato
puramente descriptivo — no alimenta el `alert_engine` ni cambia el flujo
del bot. Existe para estadística e investigación futura; el sistema trata
a todos los pacientes igual sin importar su valor.

**Guard de ingreso tardío (A-1, Sprint 5):** `desactivar_pacientes_vencidos`
solo desactiva un paciente si además de tener `dia_postoperatorio >=
DIAS_SEGUIMIENTO` (10) lleva al menos `DIAS_GRACIA_INGRESO` (2) días
registrado en el sistema (`fecha_registro`) — evita desactivar a un
paciente de ingreso tardío antes de que reciba un solo check-in.
`PacienteAdmin.save_model` además advierte al médico (sin bloquear) si crea
un paciente con `dia_postoperatorio >= 8`.

### RegistroDiario (Sprint 1, ampliado en Sprint 3)
```python
paciente              ForeignKey(Paciente, PROTECT)
temperatura           DecimalField(4,1)
dolor_eva             PositiveSmallIntegerField  # 1-10
tiene_drenaje         BooleanField null=True  # null=legado, False=sin drenaje, True=con drenaje
aspecto_drenaje       CharField choices=[seroso,hematico,turbio,purulento,fecaloide,sin_drenaje]
cantidad_drenaje      CharField choices=[poco,normal,mucho,sin_drenaje] null=True blank=True
volumen_drenaje_ml    PositiveIntegerField nullable  # opcional, complemento de cantidad_drenaje
presencia_gases       BooleanField
episodios_nauseas     PositiveSmallIntegerField
tolero_liquidos       BooleanField null=True  # null=no capturado, False=no toleró, True=toleró
hinchazon_abdominal   CharField choices=[nada,algo,mucho] null=True  # se evalúa por empeoramiento entre días
frecuencia_cardiaca   PositiveSmallIntegerField null=True  # lpm — alerta TAQUICARDIA por valor absoluto
frecuencia_respiratoria PositiveSmallIntegerField null=True  # rpm — SOLO dashboard, sin alerta (Outersterp 2025)
fecha_registro        DateTimeField default=timezone.now, editable=False
dia_postoperatorio    PositiveSmallIntegerField  # calculado al crear y luego inmutable
```

**Decisión de diseño (Sprint 3):** `cantidad_drenaje` es el dato principal que
captura el bot (escala cualitativa, accesible para cualquier paciente).
`volumen_drenaje_ml` queda como complemento opcional — el bot lo extrae solo si
el paciente lo menciona espontáneamente (ej. "poco, 30ml"). El alert_engine usa
`aspecto_drenaje`, no `cantidad_drenaje` ni `volumen_drenaje_ml`, para las alertas.

### Alerta (Sprint 1, ampliado en Sprint 4, Bloque A y agrupación 10/07/2026)
```python
paciente              ForeignKey(Paciente, PROTECT)
registro_origen       ForeignKey(RegistroDiario, PROTECT, null=True, blank=True)
                      # null solo para alertas SILENCIO (check-in sin respuesta)
tipo                  CharField choices=[SEPSIS,FUGA_ANASTOMOTICA,ILEO_PARALITICO,DOLOR_AGUDO,INTOLERANCIA_ORAL,TAQUICARDIA,SILENCIO]
severidad             CharField choices=[ALTA,MEDIA,BAJA]  # = MÁXIMA alcanzada mientras la alerta está abierta
mensaje               TextField
resuelta              BooleanField default=False
fecha_alerta          DateTimeField auto_now_add=True  # PRIMERA detección
veces                 PositiveSmallIntegerField default=1  # nº de check-ins que la detectaron (contador de recurrencia)
fecha_ultima_deteccion DateTimeField null=True blank=True  # detección más reciente
fecha_resolucion      DateTimeField null=True blank=True
motivo_resolucion     CharField choices=[CONTACTO,URGENCIAS,MEDICACION,FP_MEDICION,FP_RANGO,ESPONTANEO,OTRO,LEGACY] null=True blank=True
                      # Bloque A — obligatorio al resolver (vía formulario intermedio del Admin)
motivo_resolucion_detalle CharField(500) null=True blank=True  # requerido solo si motivo=OTRO
resuelta_por          ForeignKey(User, SET_NULL, null=True, related_name='alertas_resueltas')
                      # D3 (Loop B) — QUIÉN resolvió. Lo puebla la acción del Admin
                      # (mismo .update() + log_change). Sin backfill: cierres
                      # previos quedan NULL. Migración 0025.
```

**Agrupación de alertas por problema (decisión Arquitecto, 10/07/2026):** el
`alert_engine` ya NO crea una alerta por check-in. Hay a lo sumo **UNA alerta
abierta (`resuelta=False`) por `(paciente, tipo)`**: si el mismo problema se
detecta de nuevo mientras sigue abierta, se **actualiza** (helper
`_registrar_alerta`, reemplaza la vieja `_deduplicar` por día) — sube `veces`,
`fecha_ultima_deteccion`, y la `severidad` si la nueva es mayor (la severidad =
la máxima; nunca baja sola). Dentro de un mismo check-in, dos reglas del mismo
tipo cuentan como **una** detección. Si el médico **resuelve** la alerta y el
problema **reaparece** después, se abre una **nueva** (evento nuevo). **Ninguna
regla ni umbral clínico cambió** — solo cómo se almacenan las detecciones. El
Admin muestra un badge de recurrencia "×N"; el tablero de triage también. Desde
el Loop 3, `DeteccionAlerta` conserva la fuente, fecha, severidad y mensaje de
cada detección nueva. No se fabrican filas para el contador histórico previo.

**Signos concurrentes en un mismo check-in (decisión D5, 22/07/2026):** cuando
dos reglas del mismo tipo se disparan en el mismo check-in,
`DeteccionAlerta.mensaje_detectado` **acumula todos los signos**, encabezados
por el más grave (separador `\n· `). Antes conservaba solo el más grave y
descartaba el resto. Solo afecta a `ILEO_PARALITICO`, el único tipo producido
por reglas que pueden coincidir — Reglas 3 (gases), 4 (náuseas) y 7 (hinchazón);
las demás son mutuamente excluyentes. `Alerta.mensaje` **sigue conservando solo
el signo más grave**: es el titular del listado y del tablero, y debe caber en
una línea. La acumulación es idempotente porque
`reintentar_evaluaciones_alertas` vuelve a correr las ocho reglas.

**Correo de alerta ALTA (actualizado 10/07/2026):** `signals.py` envía el email
al médico solo cuando la alerta **alcanza ALTA por primera vez** (creación ALTA
o **escalada** a ALTA, marcada por `_escalo_a_alta` desde el engine), **no** en
cada recurrencia diaria del mismo problema.

**Tope de reintentos y estado FALLIDA (decisión D6, Loop B):** el correo
(`NotificacionAlerta`) y la evaluación de un registro se reintentan **como
máximo 10 veces** (≈39 h con el backoff actual). Un correo agotado pasa al
estado terminal **`FALLIDA`** (nuevo choice de `NotificacionAlerta`, migración
0026 que amplía las restricciones `estado_valido` y `envio_coherente`); una
evaluación agotada deja de recogerse (filtro `intentos < 10` en
`reintentar_evaluaciones_alertas`). El **tablero de triage** avisa cuando hay
correos `FALLIDA` —también al médico, con scoping por médico— porque un aviso de
alerta ALTA que no llegó es información clínica que no debe quedar enterrada. El
envío usa `select_for_update(of=('self',))` para no bloquear las filas de
paciente/alerta durante la llamada de red (hallazgo 2).

**Motivo de resolución (Bloque A, 02/07/2026):** el médico debe elegir un
motivo al marcar una alerta como resuelta — la acción "Marcar como resuelta"
del Admin muestra un formulario intermedio (default "Atendido — contacté al
paciente"; "Otro" exige detalle libre). Sirve para ajustar umbrales clínicos
con datos reales en el futuro. El scoping por médico se aplica en cada paso
(un médico no-superuser solo resuelve alertas de sus propios pacientes).
Desde el Loop 1 de hardening, la alerta completa es de solo lectura en el
formulario y la base exige fecha + motivo para todo cierre. `LEGACY` identifica
exclusivamente cierres históricos previos donde ese motivo no se capturó.

### ConversacionWhatsApp (Sprint 3, ampliado en Sprint 3.5)
```python
paciente                  OneToOneField(Paciente, PROTECT)
estado                     CharField choices=[INICIO, ESPERANDO_TEMPERATURA,
                           ESPERANDO_DOLOR, ESPERANDO_TIENE_DRENAJE,
                           ESPERANDO_ASPECTO_DRENAJE,
                           ESPERANDO_CANTIDAD_DRENAJE, ESPERANDO_GASES_NAUSEAS,
                           ESPERANDO_HINCHAZON, ESPERANDO_FRECUENCIA_CARDIACA,
                           ESPERANDO_FRECUENCIA_RESPIRATORIA,
                           ESPERANDO_TOLERANCIA_LIQUIDOS, COMPLETADO]
temp_temperatura           DecimalField nullable  # respuesta parcial del día
temp_dolor_eva              PositiveSmallIntegerField nullable
temp_tiene_drenaje          BooleanField nullable
temp_aspecto_drenaje        CharField nullable
temp_cantidad_drenaje       CharField nullable
temp_volumen_drenaje_ml     PositiveIntegerField nullable
temp_presencia_gases        BooleanField nullable
temp_episodios_nauseas      PositiveSmallIntegerField nullable
temp_hinchazon_abdominal    CharField nullable
temp_frecuencia_cardiaca    PositiveSmallIntegerField nullable
temp_frecuencia_respiratoria PositiveSmallIntegerField nullable
temp_tolero_liquidos        BooleanField nullable
fecha_ultimo_registro       DateField nullable  # controla "un registro por día"
fecha_actualizacion         DateTimeField auto_now=True
```

**Por qué existe:** cada mensaje de WhatsApp vía Twilio llega como una petición
HTTP independiente — Django no "recuerda" en qué pregunta iba el paciente entre
un mensaje y otro. Este modelo persiste el estado de la máquina de estados en
la base de datos en lugar de en memoria.

---
