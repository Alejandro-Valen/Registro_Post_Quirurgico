# Reglas clínicas del sistema

> **Fuente única.** Este archivo es el original de las reglas del
> `alert_engine` y de las variables clínicas que captura el sistema. Ni
> CLAUDE.md, ni el ROADMAP, ni ningún otro documento conservan una copia: si
> alguno las repite, está desactualizado por definición.
>
> **Estas reglas no son negociables.** Tienen base en evidencia clínica de
> recuperación postoperatoria colorrectal (protocolos ERAS) y ningún umbral se
> cambia sin decisión explícita del Arquitecto y validación del médico. Ver
> `docs/arquitectura_documentacion.md` para el porqué de esta separación.
>
> Al cambiar una regla en `signos_sintomas/alert_engine.py` **este archivo se
> actualiza en el mismo lote de commits** — nunca después.

---

## Variables Clínicas que Registra el Sistema

Capturadas 2 veces al día por WhatsApp (decisión jun 2026 — Gignoux 2018
como referencia parcial; **pendiente de implementar en bot.py**, hoy el
bot sigue capturando 1 vez/día):

| # | Variable | Tipo | Unidad |
|---|----------|------|--------|
| 1 | Temperatura corporal | Decimal | °C |
| 2 | Dolor EVA | Entero | Escala 1-10 |
| 3 | ¿Tiene drenaje activo? | Booleano nullable | sí/no/no capturado |
| 4 | Aspecto del drenaje | Choices | seroso/hemático/turbio/purulento/fecaloide/sin_drenaje |
| 5 | Cantidad del drenaje | Choices | poco/normal/mucho/sin_drenaje (cualitativo) |
| 6 | Volumen del drenaje | Entero opcional | ml — solo si el paciente lo mide |
| 7 | Presencia de gases | Booleano | sí/no |
| 8 | Episodios de náuseas/vómito | Entero | cantidad por check-in |
| 9 | ¿Toleró líquidos sin vomitar? | Booleano nullable | sí/no/no capturado |
| 10 | Hinchazón/distensión abdominal | Choices nullable | nada/algo/mucho |
| 11 | Frecuencia cardíaca | Entero nullable | lpm — alerta TAQUICARDIA si >= 101 |
| 12 | Frecuencia respiratoria | Entero nullable | rpm — SOLO dashboard, sin alerta |

---

## Reglas del Motor de Alertas (alert_engine.py)

**Archivo:** `signos_sintomas/alert_engine.py`
**Función principal:** `evaluar_registro(registro: RegistroDiario) -> list[Alerta]`
**Principio de diseño (decisión jun 2026):** modelo de alta sensibilidad
(Lee 2022, Outersterp 2025) — escalera BAJA/MEDIA/ALTA en vez de un solo
nivel de alerta. **Las 5 variables del núcleo clínico (drenaje,
temperatura, gases, náuseas, dolor) están reescritas bajo este
modelo — fase de decisiones de arquitectura clínica completa.**

| Regla | Condición exacta | Tipo Alerta | Severidad | Base clínica |
|-------|-----------------|-------------|-----------|--------------|
| 1a | temperatura >= 37.9°C (cualquier registro del día) | SEPSIS | ALTA | Outersterp 2025 — umbral de notificación domiciliaria |
| 1b | temperatura 37.5–37.8°C en 2 días con datos consecutivos | SEPSIS | MEDIA | Subfebrícula persistente — construcción propia |
| 2a | tiene_drenaje is True AND aspecto in ['purulento','fecaloide'] | FUGA_ANASTOMOTICA | ALTA | Fuga anastomótica confirmada |
| 2b | tiene_drenaje is True AND aspecto in ['turbio','hematico'] | FUGA_ANASTOMOTICA | MEDIA | Drenaje sospechoso — seguimiento |
| 2c | tiene_drenaje is True AND aspecto == 'seroso' | FUGA_ANASTOMOTICA | BAJA | Drenaje dentro de lo esperado |
| 3a | sin gases 1 día con datos | ILEO_PARALITICO | BAJA | Gases = criterio de alta ERAS; ausencia = regresión |
| 3b | sin gases 2 días con datos consecutivos | ILEO_PARALITICO | MEDIA | ídem |
| 3c | sin gases 3 días con datos consecutivos | ILEO_PARALITICO | ALTA | ídem — umbral histórico del proyecto |
| 4a | suma episodios_nauseas del día: 1-2 | ILEO_PARALITICO | BAJA | Lee 2022, Outersterp 2025 — cualquier episodio es señal |
| 4b | suma episodios_nauseas del día: 3-4 | ILEO_PARALITICO | MEDIA | ídem |
| 4c | suma episodios_nauseas del día: 5+ | ILEO_PARALITICO | ALTA | ídem |
| 4d | náuseas (≥1 episodio/día) en 2 días con datos consecutivos | ILEO_PARALITICO | MEDIA (mínimo) | Persistencia — solo sube severidad, nunca la baja |
| 4e | náuseas (≥1 episodio/día) en 4 días con datos consecutivos | ILEO_PARALITICO | ALTA | Delaney 2008 — íleo en 27.8% con estancia 4+ días vs 11% general |
| 5a | dolor_eva >= umbral según ventana de dia_postoperatorio (ver nota) | DOLOR_AGUDO | BAJA/MEDIA/ALTA según ventana | Delaney 2008, Lee 2022, Outersterp 2025, Coeckelberghs 2025 |
| 5b | promedio dolor_eva últimos 2 días - promedio 2 días anteriores >= 3 | DOLOR_AGUDO | sube un nivel sobre 5a (techo ALTA) | Tendencia alcista — construcción propia |
| 6a | tolero_liquidos=False en 1 día con datos | INTOLERANCIA_ORAL | MEDIA | Deshidratación = causa #1 de readmisión (Lawrence 2013); tolerancia oral es criterio de alta ERAS |
| 6b | tolero_liquidos=False en 2 días con datos consecutivos | INTOLERANCIA_ORAL | ALTA | Riesgo de deshidratación establecida |
| 7a | hinchazón: nivel de hoy > nivel de ayer (empeoramiento puntual) | ILEO_PARALITICO | BAJA | Distensión = signo de íleo; empeoramiento leve |
| 7b | hinchazón: hoy > antier sostenido sin bajar >2 días | ILEO_PARALITICO | MEDIA | Empeoramiento sostenido — posible íleo en progreso |
| 7c | hinchazón "mucho" sostenido 4 días con datos consecutivos | ILEO_PARALITICO | ALTA | Distensión severa persistente — posible íleo paralítico |
| 8a | frecuencia_cardiaca 101-109 lpm | TAQUICARDIA | BAJA | Taquicardia leve, probablemente fisiológica |
| 8b | frecuencia_cardiaca 110-149 lpm | TAQUICARDIA | MEDIA | CREWS 2022 (110 lpm, 75% sens. fuga/sangrado); Cleveland NCT04574908 (>110 intervención) |
| 8c | frecuencia_cardiaca >= 150 lpm | TAQUICARDIA | ALTA | Escalamiento inmediato (protocolos hospitalarios) |

**Nota Regla 8 (FC — valor absoluto):** la taquicardia se evalúa por el
valor de cada registro, sin lógica de días calendario ni persistencia
(el valor por sí solo ya es clínicamente significativo). Solo se vigila
FC alta, no bradicardia.

**Frecuencia respiratoria (FR): SOLO DASHBOARD, sin regla.** Se captura y
almacena pero el `alert_engine` NO la evalúa — decisión del Arquitecto:
Outersterp 2025 halló que el 77% de las falsas alertas venían del sensor
de FR. Por eso FR no tiene fila de reglas; solo aparece como variable y
campo del modelo.

**Nota sobre la lógica de días (Reglas 1, 3, 4, 6, 7) — corregida en el
Loop C (D8):** se cuentan **días con datos**, no días de calendario. Dos
cosas distintas:

1. **Agrupación:** los registros se agrupan por `fecha_registro__date`, no
   por número de registro — el sistema captura 2 check-ins/día, así que 2
   registros del mismo día cuentan como 1 día, no como 2.
2. **Días sin ningún reporte:** un día en el que el paciente no reportó
   nada **corta el conteo** (Reglas 3, 4, 6 y 7) o impide alcanzar el
   umbral (Regla 1b). Tres días sin tránsito intestinal con un hueco en
   medio se cuentan como uno, no como tres.

Es deliberado: un día sin datos es un desconocido genuino —el paciente pudo
haber tenido gases y no reportarlo— y contar a través de él **inventaría un
hecho clínico**. El hueco además ya tiene su propia alerta: la ausencia de
respuesta genera SILENCIO, que sí escala. Limitación aceptada y conocida: un
paciente que reporta de forma intermitente puede acumular signos sin que
ninguna regla escale, mientras recibe alertas SILENCIO por separado — las dos
señales no se suman.

**Esto no cierra la pregunta clínica.** Si el médico considera que un hueco de
un solo día no debería reiniciar el conteo, eso es un cambio de umbral y
requiere su validación explícita. Razonamiento completo en
`docs/decisiones_correccion_auditoria.md`, ficha D8.

**Nota Regla 5 (Dolor/DOLOR_AGUDO — implementado):** escalera por
`dia_postoperatorio`: POD 1-2 → BAJA 5-6/MEDIA 7-8/ALTA 9-10; POD 3-5
→ BAJA 4-5/MEDIA 6-7/ALTA 8-10; POD 6+ → BAJA 3-4/MEDIA 5-6/ALTA
7-10. Capa de tendencia: si el promedio de los últimos 2 días
calendario sube >=3 puntos vs. el promedio de los 2 días anteriores,
escala un nivel de severidad sobre el valor de la tabla (nunca baja
una severidad ya alcanzada). Base: Delaney 2008, Lee 2022, Outersterp
2025, Coeckelberghs 2025.

**Regla operativa: SILENCIO (paciente sin responder).** No la produce
`alert_engine.evaluar_registro` sino el command `cerrar_checkins_vencidos`,
que cierra los check-in `PENDIENTE` pasadas 10 horas de su
`hora_programada` y cuenta la racha de turnos consecutivos sin responder.

| Racha | Tipo | Severidad |
|-------|------|-----------|
| 1 turno | SILENCIO | BAJA |
| 2-3 turnos | SILENCIO | MEDIA |
| 4+ turnos | SILENCIO | ALTA |

**Decisión D1 (22/07/2026):** la racha cuenta **check-ins, no días
calendario** — la agrupación por día existe para de-duplicar mediciones y
aquí no hay mediciones que de-duplicar; cada turno perdido es un intento
de contacto distinto que falló. Con dos turnos diarios, el umbral ALTA de
4 equivale a **dos días calendario completos sin una sola señal**. Solo se
miran turnos **estrictamente anteriores** al que se cierra: un
`COMPLETADO` rompe la racha (el paciente respondió), un `PENDIENTE` se
ignora sin romperla (una caída del cron no debe degradar una alerta
clínica). Base del modelo: SILENCIO es ausencia de datos, no un síntoma —
no genera mensaje al paciente, así que el costo de un falso positivo es
una llamada telefónica y conviene errar hacia la sensibilidad. Razonamiento
completo en `docs/decisiones_correccion_auditoria.md`, ficha D1.

---
