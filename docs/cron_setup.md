# Configuración del Cron — Sistema de Monitoreo Posquirúrgico

> Sprint 5, Bloque 6. Decisión de arquitectura (confirmada en sesión,
> 01/07/2026): el cron corre en **Linux**, no en Windows Task Scheduler —
> el destino de despliegue es Railway o Render (ambos Linux), no la
> máquina de Alejandro. Ver ROADMAP_MONITOREO_POSQUIRURGICO.md, FASE 5.

## Los 4 management commands que deben programarse

| Command | Qué hace | Hora local (Bogotá) |
|---------|----------|----------------------|
| `desactivar_pacientes_vencidos` | Desactiva pacientes con ≥10 días postoperatorios (P-5) | 5:55 AM |
| `crear_checkins_diarios` | Crea los 2 check-ins del día (mañana/tarde) para pacientes activos | 6:00 AM |
| `enviar_recordatorios` | Envía el recordatorio matutino de WhatsApp (stub hasta integrar Twilio saliente) | 7:00 AM |
| `cerrar_checkins_vencidos` | Cierra check-ins PENDIENTE vencidos (10h de gracia) → NO_RESPONDIDO + alerta SILENCIO | 6:00 AM y 6:00 PM |

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
```

**`MAILTO`:** con esta línea al inicio del crontab, cualquier error en la
salida estándar/error de un command llega por email automáticamente al
desarrollador — es el mecanismo de "cron falla → email → resolución en
~30 min" de la decisión P-3 (mantenimiento con intervención mínima).

**Nota sobre `desactivar_pacientes_vencidos` a las 5:55 y `crear_checkins_diarios`/`cerrar_checkins_vencidos` a las 6:00 en el mismo minuto UTC (11:00):**
cron ejecuta cada línea como un proceso independiente; el orden entre
tareas programadas para el mismo minuto no está garantizado por cron.
Por eso `desactivar_pacientes_vencidos` va 5 minutos antes (10:55 UTC),
no en el mismo minuto — así se garantiza que termina antes de que
empiece `crear_checkins_diarios`.

## Si se migra a Railway con su servicio nativo de Cron Jobs

Railway permite declarar cron jobs como su propio tipo de servicio (sin
necesidad de un crontab de sistema operativo dentro del contenedor). La
lógica es la misma: un servicio de Cron Job por cada línea de la tabla de
arriba, con el mismo comando (`python manage.py <command>`) y la misma
expresión cron (en UTC). Ventaja: Railway reintenta automáticamente si el
comando falla, sin depender de `MAILTO`/crontab tradicional — evaluar si
esto reemplaza o complementa el `MAILTO` de arriba al momento del deploy.

## Verificación post-despliegue (primer día en producción)

- [ ] `desactivar_pacientes_vencidos` corrió y su log es legible (aunque
  no desactive a nadie el primer día, confirma que el command no falla)
- [ ] `crear_checkins_diarios` creó 2 check-ins por paciente activo
- [ ] `enviar_recordatorios` corrió sin error (aunque el envío real de
  WhatsApp saliente siga en stub — ver Sprint 5, tareas diferidas)
- [ ] `cerrar_checkins_vencidos` corrió en sus dos horarios sin error
- [ ] Un fallo forzado (ej. detener la BD un momento) efectivamente
  genera un email a `MAILTO`

## Diferido explícitamente (no bloquea Sprint 5)

- Migración a Celery beat si los fallos de cron son frecuentes o se
  necesita retry automático — la lógica ya está encapsulada en los
  management commands, migrarla es decorar con `@shared_task`.
- Integración real de Twilio saliente en `enviar_recordatorios` (hoy es
  un stub que solo loguea).
