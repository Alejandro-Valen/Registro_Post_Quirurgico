# Configuración del Cron — Sistema de Monitoreo Posquirúrgico

> Sprint 5, Bloque 6. Decisión de arquitectura (confirmada en sesión,
> 01/07/2026): el cron corre en **Linux**, no en Windows Task Scheduler —
> el destino de despliegue es Railway o Render (ambos Linux), no la
> máquina de Alejandro. Ver ROADMAP_MONITOREO_POSQUIRURGICO.md, FASE 5.
>
> Estado al 21/07/2026: `cron-manana` y el `cron_operativo` temporal están
> desplegados. La recuperación de evaluaciones y correo fue verificada; el
> monitoreo externo de ausencia de ejecuciones sigue pendiente.

## Los 6 management commands que deben programarse

| Command | Qué hace | Hora local (Bogotá) |
|---------|----------|----------------------|
| `desactivar_pacientes_vencidos` | Desactiva pacientes con ≥10 días postoperatorios (P-5) | 5:55 AM |
| `crear_checkins_diarios` | Crea los 2 check-ins del día (mañana/tarde) para pacientes activos | 6:00 AM |
| `enviar_recordatorios` | Envía el recordatorio matutino de WhatsApp (stub hasta integrar Twilio saliente) | 7:00 AM |
| `cerrar_checkins_vencidos` | Cierra check-ins PENDIENTE vencidos (10h de gracia) → NO_RESPONDIDO + alerta SILENCIO | 6:00 AM y 6:00 PM |
| `reintentar_evaluaciones_alertas` | Recupera registros cuya evaluación clínica quedó pendiente o falló | Cada 5 minutos |
| `procesar_notificaciones_email` | Procesa la bandeja persistente de alertas ALTA y conserva los fallos para reintento | Cada 5 minutos |

**Orden obligatorio a las 5:55-6:00 AM:** `desactivar_pacientes_vencidos`
**siempre antes** de `crear_checkins_diarios`. Si se invierte el orden, un
paciente que justo cumple el día 10 recibiría un check-in el mismo día en
que se desactiva — ese check-in quedaría PENDIENTE para siempre (el
paciente ya no responde) y terminaría generando una alerta SILENCIO
espuria cuando `cerrar_checkins_vencidos` lo cierre. Este orden está
protegido por el test `test_scheduler_no_crea_checkins_tras_desactivacion`
en `signos_sintomas/tests.py`.

`cerrar_checkins_vencidos` corre dos veces al día porque hay 2 check-ins
(mañana y tarde) con sus propias ventanas de gracia de 10 horas — una
corrida cierra los vencidos de la tarde anterior, la otra los de la
mañana.

`reintentar_evaluaciones_alertas` es una tarea técnica y no envía preguntas
al paciente. Procesa como máximo 100 registros por corrida, bloquea cada fila
y continúa con las demás si una evaluación vuelve a fallar. El cron matutino
también lo ejecuta como respaldo, pero no reemplaza la corrida frecuente.

`procesar_notificaciones_email` tampoco corre dentro del webhook. Consume la
bandeja `NotificacionAlerta`, limita cada corrida a 50 candidatas y aplica
reintentos con espera creciente. El comando `cron_operativo` agrupa, en este
orden, `cerrar_checkins_vencidos`, `reintentar_evaluaciones_alertas` y
`procesar_notificaciones_email` para plataformas con pocos servicios.

## Crontab (producción Linux — Railway/Render con worker o VPS)

Bogotá es **UTC-5** todo el año (no tiene horario de verano). Las horas
de abajo ya están convertidas a UTC para pegar directo en `crontab -e`:

```cron
MAILTO=email-del-desarrollador@ejemplo.com
SHELL=/bin/bash

# 5:55 AM Bogotá = 10:55 UTC — desactivar vencidos ANTES de crear check-ins
55 10 * * * cd /app && python manage.py desactivar_pacientes_vencidos >> /var/log/monitoreo/desactivar.log 2>&1

# 6:00 AM Bogotá = 11:00 UTC — crear check-ins del día
0 11 * * * cd /app && python manage.py crear_checkins_diarios >> /var/log/monitoreo/checkins.log 2>&1

# 6:00 AM Bogotá = 11:00 UTC — cerrar vencidos de la noche/madrugada anterior
5 11 * * * cd /app && python manage.py cerrar_checkins_vencidos >> /var/log/monitoreo/vencidos.log 2>&1

# 7:00 AM Bogotá = 12:00 UTC — recordatorio matutino
0 12 * * * cd /app && python manage.py enviar_recordatorios >> /var/log/monitoreo/recordatorios.log 2>&1

# 6:00 PM Bogotá = 23:00 UTC — cerrar vencidos de la tarde
0 23 * * * cd /app && python manage.py cerrar_checkins_vencidos >> /var/log/monitoreo/vencidos.log 2>&1

# Recuperar evaluaciones de alertas pendientes o fallidas
*/5 * * * * cd /app && python manage.py reintentar_evaluaciones_alertas >> /var/log/monitoreo/reintentos-alertas.log 2>&1

# Entregar correos pendientes sin bloquear el webhook
*/5 * * * * cd /app && python manage.py procesar_notificaciones_email >> /var/log/monitoreo/notificaciones.log 2>&1
```

**`MAILTO`:** con esta línea al inicio del crontab, cualquier error en la
salida estándar/error de un command llega por email automáticamente al
desarrollador — es el mecanismo de "cron falla → email → resolución en
~30 min" de la decisión P-3 (mantenimiento con intervención mínima).

`MAILTO` aplica al ejemplo de `crontab` autogestionado. Los servicios cron de
Railway no heredan este mecanismo: hoy sus fallos quedan en logs. Antes del
piloto real se debe configurar monitoreo externo que avise si una ejecución no
ocurre o si web/cron dejan de responder.

**Nota sobre `desactivar_pacientes_vencidos` a las 5:55 y `crear_checkins_diarios`/`cerrar_checkins_vencidos` a las 6:00 en el mismo minuto UTC (11:00):**
cron ejecuta cada línea como un proceso independiente; el orden entre
tareas programadas para el mismo minuto no está garantizado por cron.
Por eso `desactivar_pacientes_vencidos` va 5 minutos antes (10:55 UTC),
no en el mismo minuto — así se garantiza que termina antes de que
empiece `crear_checkins_diarios`.

## Configuración actual en Railway

Desde el 19/07/2026 hay dos servicios cron:

- `cron-manana`: `cron_matutino`, a las `0 11 * * *` UTC.
- `cron-tarde`: **reutilizado temporalmente** con `cron_operativo`, cada
  `*/5 * * * *`.

`cron_matutino` ejecuta hoy las seis tareas en una sola corrida de las 6:00 AM,
incluido `enviar_recordatorios`. Como ese command sigue siendo un stub, todavía
no envía nada. Al implementar Twilio saliente se debe decidir si el recordatorio
se separa a las 7:00 AM o si se aprueba explícitamente enviarlo a las 6:00 AM;
no se debe activar el envío conservando el horario por accidente.

Esta reutilización fue necesaria porque Railway rechazó un servicio adicional
con `Free plan resource provision limit exceeded`. No es la arquitectura final:
al mejorar el plan de Railway se debe crear un servicio independiente
`cron-operativo` cada 5 minutos y restaurar `cron-tarde` a
`cerrar_checkins_vencidos` a las `0 23 * * *` UTC como respaldo idempotente.
Así el ciclo operativo frecuente no depende de un servicio cuyo nombre y
responsabilidad original eran el cierre de la tarde.

## Verificación post-despliegue (primer día en producción)

- [ ] `desactivar_pacientes_vencidos` corrió y su log es legible (aunque
  no desactive a nadie el primer día, confirma que el command no falla)
- [ ] `crear_checkins_diarios` creó 2 check-ins por paciente activo
- [ ] `enviar_recordatorios` corrió sin error (aunque el envío real de
  WhatsApp saliente siga en stub — ver Sprint 5, tareas diferidas)
- [x] `cerrar_checkins_vencidos` fue ejecutado en vivo por `cron_operativo` y
  cerró check-ins vencidos de forma idempotente
- [x] `cron_operativo` corre cada 5 minutos y ejecuta cierre, reintento del
  motor y bandeja de notificaciones en ese orden
- [x] Una alerta ALTA ficticia crea una notificación y Resend la entrega
  (alerta demo #90, 21/07/2026; recibida en spam por usar dominio de prueba)
- [x] Un fallo transitorio de entrega conservó la notificación PENDIENTE y el
  mismo procesador la envió al reintentar, sin duplicarla (21/07/2026)
- [ ] Un fallo forzado (ej. detener la BD un momento) genera una alerta del
  sistema de monitoreo externo; todavía no está configurado

## Diferido explícitamente (no bloquea Sprint 5)

- Migración a Celery beat si el volumen supera lo razonable para el cron
  frecuente — la lógica ya está encapsulada en los management commands.
- Mejorar el plan de Railway y separar `cron-operativo` de `cron-tarde`, como
  se describe arriba. La reutilización actual es una medida temporal.
- Integración real de Twilio saliente en `enviar_recordatorios` (hoy es
  un stub que solo loguea).
- Monitoreo externo de disponibilidad y ejecuciones omitidas de Railway. Los
  reintentos internos recuperan trabajo fallido, pero no detectan por sí solos
  que un servicio cron haya dejado de arrancar.
