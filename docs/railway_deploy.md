# Despliegue en Railway — referencia

> Este documento es el **guion de referencia** para el despliegue en Railway.
> Los pasos clic-por-clic se hacen en sesión guiada con Claude Code; aquí quedan
> fijas las decisiones, las variables de entorno exactas y el orden correcto,
> para no depender de la memoria de nadie.
>
> Estado al 21/07/2026: **desplegado en Railway**. Web, PostgreSQL, Redis y
> dos servicios cron operativos. Flujos NORMAL/MEDIA/ALTA y correo real
> verificados; punto funcional `0d12d88`.

---

## 1. Cómo está preparado el repo (parte código, ya hecha)

- **`Dockerfile`** (raíz del repo) controla el build y el arranque:
  - Instala desde **`requirements-runtime.txt`** (limpio), NO desde
    `requirements.txt` (que es el `pip freeze` completo de desarrollo e incluye
    paquetes solo-Windows —`pywin32`, `winrt-*`— que romperían el build en Linux).
  - Arranque: `collectstatic` + `migrate` + configuración idempotente de roles
    + `gunicorn`, con `--chdir Registro_Post_Quirurgico`
    porque `manage.py` vive un nivel debajo de la raíz del repo.
- **`nixpacks.toml`** queda como fallback; el despliegue actual no lo usa.
- **`.python-version`** = `3.13` (fija la versión de Python del build).
- **WhiteNoise** sirve los estáticos del Admin en producción (Railway no tiene
  Nginx delante). Configurado en `settings_production.py`.
- **`gunicorn` + `whitenoise`** añadidos a `requirements-runtime.txt`.

**No hay que cambiar nada de esto en Railway** — es automático al conectar el repo.

---

## 2. Servicios a provisionar en Railway

1. **Servicio web** (el repo, vía GitHub).
2. **PostgreSQL** (plugin de Railway).
3. **Redis** (plugin de Railway) — obligatorio: el cache compartido sostiene el
   rate limiting entre workers. La idempotencia del webhook vive en PostgreSQL.
4. **`cron-manana`** — ejecuta `cron_matutino` una vez al día.
5. **`cron-tarde`** — reutilizado temporalmente como `cron_operativo` cada
   5 minutos por el límite de recursos del plan actual.

**Mejora de infraestructura pendiente:** al ampliar el plan de Railway, crear
un servicio `cron-operativo` independiente y devolver `cron-tarde` a su horario
de las 6:00 PM Bogotá. Esta separación está documentada en
`docs/cron_setup.md` y no debe olvidarse al habilitar más recursos.

---

## 3. Variables de entorno (configurar ANTES del primer deploy)

> El Dockerfile actual instala dependencias durante el build y ejecuta
> `collectstatic`, `migrate`, bootstrap y Gunicorn durante el arranque. Ese
> arranque importa `settings_production`, por lo que las variables deben existir
> antes del primer deploy: **primero variables, luego deploy.**

| Variable | Valor / de dónde sale |
|----------|----------------------|
| `DJANGO_SETTINGS_MODULE` | `Registro_Post_Quirurgico.settings_production` |
| `SECRET_KEY` | Clave nueva y larga, **distinta** a la de desarrollo. Generar con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `ALLOWED_HOSTS` | El dominio de Railway, ej. `mi-app.up.railway.app` (sin `https://`). **Ojo:** la variable se llama `ALLOWED_HOSTS`, no `DJANGO_ALLOWED_HOSTS`. |
| `CSRF_TRUSTED_ORIGINS` | El mismo dominio **con** esquema: `https://mi-app.up.railway.app`. **Obligatoria: si falta o queda vacía, el contenedor no arranca.** Vacía, el POST del login del médico devolvía 403 sin explicación. |
| `DB_NAME` | Referencia al Postgres de Railway: `${{Postgres.PGDATABASE}}` |
| `DB_USER` | `${{Postgres.PGUSER}}` |
| `DB_PASSWORD` | `${{Postgres.PGPASSWORD}}` |
| `DB_HOST` | `${{Postgres.PGHOST}}` |
| `DB_PORT` | `${{Postgres.PGPORT}}` |
| `REDIS_URL` | Referencia al Redis de Railway: `${{Redis.REDIS_URL}}`. **Obligatoria: si falta o queda vacía, el contenedor no arranca.** Antes caía a un default `localhost` y degradaba en silencio los rate limits compartidos entre workers. |
| `TRUST_RAILWAY_PROXY` | **`True` en el servicio web** — es un solo interruptor para las tres cabeceras del edge: `X-Real-IP` (IP del cliente), `X-Forwarded-Host` (host con el que se reconstruye la URL) y `X-Forwarded-Proto` (esquema). **Sin él, Django ve HTTP detrás del edge y `SECURE_SSL_REDIRECT` entra en un bucle de redirecciones.** Los servicios cron no atienden tráfico HTTP y no lo necesitan. |
| `ADMIN_URL` | Slug privado no trivial terminado en `/`, ej. `gestion-clinica-x7k2/`. Cambia la URL del Admin para reducir ataques automáticos. Si se omite queda `admin/`, que en producción no debe usarse. No publicar el valor real. |
| `MEDICO_CONTACTO_USERNAME` | Usuario médico que recibe los mensajes del formulario público. |
| `EMAIL_DELIVERY_PROVIDER` | `resend` para entregar alertas por HTTPS. |
| `RESEND_API_KEY` | Clave secreta `re_...` creada en Resend; nunca copiarla en documentación o chat. |
| `RESEND_FROM_EMAIL` | Remitente verificado. Para la prueba restringida: `Seguimiento posquirúrgico <onboarding@resend.dev>`. |
| `EMAIL_TIMEOUT` | `10` segundos. Limita cada llamada al proveedor. |
| `PANEL_MEDICO_URL` | URL HTTPS completa de la ruta privada del Admin; se usa en el correo sin incluir datos del paciente. |
| `TWILIO_AUTH_TOKEN` | Auth Token **primario** de Twilio (no el de Test) |
| `TWILIO_VALIDATE_SIGNATURE` | `True` (o omitir — el default ya es `True`) |
| `DEFAULT_FROM_EMAIL` | *(opcional)* si se omite, usa `EMAIL_HOST_USER` |
| `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` / `DJANGO_SUPERUSER_EMAIL` | Bootstrap temporal de la cuenta técnica. Retirar usuario y contraseña tras verificar el primer arranque. |
| `DJANGO_MEDICO_USERNAME` / `DJANGO_MEDICO_PASSWORD` / `DJANGO_MEDICO_EMAIL` | Bootstrap temporal de la cuenta `staff` del médico. `crear_medico` la asigna al grupo de privilegio mínimo. Retirar usuario y contraseña tras verificar el acceso. |
| `RESET_AXES` | Interruptor temporal. Usar `1` solo para desbloquear Axes y volver a `0` o retirarlo inmediatamente. |

> **Nota sobre `DB_*` con `${{Postgres.*}}`:** Railway permite "referenciar"
> variables de otro servicio. Al escribir `${{Postgres.PGHOST}}` en el servicio
> web, Railway sustituye el valor real del Postgres. Así no se copian secretos
> a mano. (Si la UI de Railway cambió los nombres `PGHOST/PGDATABASE/...`, usar
> los que muestre el panel del Postgres.)

---

## 4. Orden de ejecución (resumen)

1. Crear proyecto en Railway y provisionar **PostgreSQL** y **Redis**.
2. Añadir el **servicio web** desde el repo de GitHub (rama a decidir: se puede
   desplegar `sprint-5-produccion` o mergear antes a `Desarrollo`).
3. Cargar **todas** las variables de la tabla de arriba.
4. Disparar el primer **deploy**. El arranque aplica migraciones, configura el
   grupo `Médicos`, crea las cuentas cuyas variables existan y levanta Gunicorn.
5. Verificar el acceso de ambas cuentas y retirar de Railway las variables
   `*_USERNAME` y `*_PASSWORD` de bootstrap para que no se restablezcan.
6. Configurar los **cron jobs** (ver `docs/cron_setup.md`). En el plan actual,
   `cron-manana` ejecuta el orden clínico diario y `cron-tarde` ejecuta
   temporalmente `cron_operativo` cada 5 minutos: cierre idempotente, reintento
   del motor y entrega de la bandeja de correo.
7. Actualizar el **webhook de Twilio** para que apunte a
   `https://<dominio-railway>/<ruta-del-webhook>` (recordar: Auth Token primario).

---

## 5. Gotchas conocidos

- **Primer deploy sin variables → falla al arrancar, a propósito.**
  `collectstatic` y los demás comandos del `CMD` importan `settings_production`,
  que exige `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
  `CSRF_TRUSTED_ORIGINS`, `REDIS_URL` y las credenciales del proveedor de email
  seleccionado. Desde el Loop C **una variable definida pero vacía cuenta como
  ausente** y el arranque se detiene nombrándola: antes devolvía cadena vacía y
  el sistema arrancaba roto, para fallar mucho después y lejos de la causa.
  También se rechaza el placeholder `<...>` pegado literalmente — fue la causa
  raíz del 403 de Twilio y de los login fallidos al Admin (06/07/2026). Cargar
  las variables **antes** de desplegar, con el valor crudo: sin comillas y sin
  corchetes.
- **Estáticos del Admin sin estilo** → revisar que `collectstatic` corrió en el
  arranque y que WhiteNoise está en el middleware (ya configurado). Si el deploy
  falla al ejecutar `collectstatic` por una referencia estática inexistente, degradar en
  `settings_production.py` a `whitenoise.storage.CompressedStaticFilesStorage`
  (sin manifest).
- **`ALLOWED_HOSTS` mal escrito** → Django responde `400 Bad Request` a todo.
  El valor es el host sin esquema; la variable se llama `ALLOWED_HOSTS`.
- **Rate limit / IP real** → resuelto con `X-Real-IP` documentado por Railway,
  confianza explícita y validación conjunta de `X-Railway-Edge`. No usar
  `X-Forwarded-For`. Desde el Loop C, `TRUST_RAILWAY_PROXY` gobierna también
  `USE_X_FORWARDED_HOST` y `SECURE_PROXY_SSL_HEADER`: sin declararlo, Django ya
  no cree ninguna de las tres cabeceras. **Si el sitio entra en un bucle de
  redirecciones tras desplegar, la causa es esa variable en `False` o ausente.**
- **Gmail SMTP inaccesible desde Railway** → Resend por HTTPS quedó activo y
  entregó la prueba del 21/07/2026. El dominio de onboarding llegó a spam;
  antes del piloto real verificar un dominio propio con SPF/DKIM/DMARC.
- **Límite de recursos del plan** → crear un tercer cron fue rechazado por
  Railway. `cron-tarde` está reutilizado cada 5 minutos solo hasta mejorar el
  plan y separar `cron-operativo`.
- **Antes del primer paciente real:** completar los `[corchetes]` de
  `docs/FORMATO_CONSENTIMIENTO_HABEAS_DATA.md`; verificar WhatsApp Business,
  plantillas y envío saliente; autenticar un dominio de correo; y completar los
  datos definitivos del médico. Los tonos NORMAL/MEDIA/ALTA ya se probaron en
  el Sandbox el 21/07/2026.
