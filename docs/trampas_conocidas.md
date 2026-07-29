# Trampas conocidas

> **Qué es esto.** Cosas que ya costaron horas y volverán a morder si nadie las
> escribe. No es historia —para eso está `BITACORA.md`— sino advertencias
> vigentes: cada una describe un comportamiento que sigue siendo cierto hoy.
>
> Si vas a tocar despliegue, cron, Twilio o correo, **lee esto primero**.

---

## Cron y despliegue en Railway

**Cada servicio de Railway tiene su PROPIO entorno, y pueden divergir sin que
nadie lo note (incidente 25/07/2026).** El servicio web, `cron-manana` y
`cron-tarde` cargan el mismo `settings_production`, pero sus variables se
configuran por separado. Mientras una variable tuvo valor por defecto, la
diferencia fue invisible; el día que se volvió obligatoria (hallazgo 11), el
web siguió arrancando —siempre tuvo `CSRF_TRUSTED_ORIGINS`, la necesita para el
login— y **los cron dejaron de arrancar**, con este error:

```
ImproperlyConfigured: La variable de entorno CSRF_TRUSTED_ORIGINS es
obligatoria y está vacía o sin definir.
```

**Regla del proyecto: entorno único.** Los tres servicios llevan la misma
configuración completa, aunque un cron no atienda HTTP y no use orígenes CSRF.
Se prefiere una regla explícita y aburrida antes que código que adivine en qué
proceso está corriendo. Al agregar una variable obligatoria, **se agrega en
TODOS los servicios**, y la forma segura de hacerlo es copiar el valor desde el
servicio web en vez de escribirlo a mano.

**Cómo se detecta:** el servicio web puede seguir verde mientras los cron están
caídos. `/salud/` solo mide el web. Un cron que no arranca no avisa a nadie —
es exactamente el caso que el monitoreo externo pendiente debe cubrir antes del
piloto real.

**Un `succeeded` en la tarjeta de un cron diario no prueba el deploy actual.**
`cron-manana` corre una vez al día: tras un deploy, su último estado puede ser
de la corrida anterior, con el código anterior. Verificar el log posterior al
deploy, o revisar directamente que tenga las variables.

**Un cron no toma las variables nuevas hasta su siguiente ejecución
programada.** Guardar la variable no reinicia nada. Con `cron-tarde` (cada 5
min) se ve enseguida; con `cron-manana` hay que esperar a las 6:00 AM o forzar
un redeploy. Más de una vez se dio por roto algo que solo estaba esperando su
turno: **compara siempre la hora del log con la hora en que guardaste el
cambio.**

### Variables compartidas vs. referencias entre servicios (25/07/2026)

Railway ofrece dos mecanismos que el selector presenta juntos, y **no son
intercambiables**:

| Tipo de valor | Dónde va | Ejemplo |
|---|---|---|
| Texto plano que escribes tú | Variable **compartida** del proyecto | `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`, `ADMIN_URL` |
| Valor que **produce otro servicio** | Referencia **al servicio** | `REDIS_URL` → `${{Redis.REDIS_URL}}`, `DB_*` → `${{Postgres.*}}` |

Poner `REDIS_URL = ${{shared.REDIS_URL}}` dejó el cache inutilizable: la
compartida guardaba a su vez una referencia que no se resolvía. El sistema no
avisó de forma obvia —la web seguía sirviendo la landing— y solo el endpoint de
salud lo delató con un **503**.

**Railway reemplaza por CADENA VACÍA toda referencia que no puede resolver.**
Ese es el detalle que hace difícil el diagnóstico: no falla ni deja el texto
`${{...}}` a la vista, simplemente queda vacío. Combinado con una variable
obligatoria (hallazgo 11), el resultado es un contenedor que no arranca. Es
preferible a arrancar roto, pero hay que saber leerlo: **"la variable está
vacía" casi siempre significa "la referencia no resolvió"**, no que alguien la
haya borrado.

**Orden obligatorio al reorganizar variables:** primero apuntar las referencias
al destino nuevo, verificar que los servicios arrancan, y **solo entonces**
borrar la variable vieja. Al revés, todos los servicios que la referenciaban
quedan sin valor y dejan de arrancar a la vez. Pasó esa noche: se borró la
compartida antes de corregir las referencias y cayeron el web y los dos cron.

**La línea entre tarjetas del diagrama solo refleja referencias declaradas.** Si
un servicio usa el valor literal de otro, la línea no aparece aunque la conexión
funcione perfectamente. Sirve para detectar que una referencia se perdió, no
para saber si dos servicios se hablan.

**Nunca usar `REDIS_PUBLIC_URL`.** Es el endpoint público: sale del proyecto y
vuelve a entrar por internet, con cargos de egress, más latencia y menos
seguridad. La correcta es `REDIS_URL`, que viaja por la red privada de Railway.

**Pendiente (deuda menor, para hacer con calma):** los dos servicios cron
quedaron con la **URL literal** de Redis en vez de la referencia
`${{Redis.REDIS_URL}}`, para cerrar el incidente de madrugada. Si algún día
rotan las credenciales de Redis, esos dos servicios dejarán de conectarse en
silencio. Conviene devolverlos a la referencia y confirmar que la línea del
diagrama reaparece.

**Nota cron (08/07/2026):** en Railway, encadenar comandos con `&&` en el
Custom Start Command **solo corre el primero** → se creó el comando único
`cron_matutino` (corre **6 tareas** en orden con `call_command`, incluidas la
recuperación del motor y la bandeja de correo).
Los horarios cron van en **UTC** (Bogotá −5: 6 AM = 11:00 UTC, 6 PM = 23:00
UTC); mínimo de intervalo 5 min. Cambiar el Custom Start Command exige
**redesplegar** el servicio cron para que tome efecto.

**Notas de despliegue (06/07/2026):**
- El build usa **Dockerfile** (`python:3.13-slim`), NO Nixpacks/Railpack.
  Railpack ignora `nixpacks.toml` ("No start command detected"); Nixpacks
  falló con `pip: command not found` (peculiaridad de Nix). El Dockerfile es
  determinista; `nixpacks.toml` queda como fallback inerte.
- `requirements.txt` (raíz) es el pip freeze de desarrollo Windows y **NO** se
  usa para deploy — el Dockerfile instala `requirements-runtime.txt`.
- **Variables de Railway: valor crudo, nunca entre `< >` ni comillas.** Los
  placeholders `<...>` pegados literalmente fueron la causa raíz del 403 de
  Twilio y de los login fallidos al Admin (detalle en BITACORA 06/07/2026).
- El superusuario en producción se gestiona con el comando **`crear_admin`**
  (idempotente, desde `DJANGO_SUPERUSER_*`), no con `createsuperuser` (que no
  actualiza usuarios existentes). El interruptor `RESET_AXES=1` corre
  `axes_reset` al arranque para desbloquear axes; se quita tras usarlo.

**Todo el arranque va encadenado con `&&`: si un eslabón falla, no hay error en
el log — hay contenedor que no arranca.** El `CMD` del Dockerfile es
`collectstatic && migrate && (axes_reset) && (crear_admin) && crear_medico &&
gunicorn`. Solo `axes_reset` y `crear_admin` están protegidos con `|| true`. Dos
consecuencias que hay que tener presentes:

- **`migrate` puede fallar por los datos, no por el código.** La migración
  **0028** añade un `CheckConstraint` (`paciente activo ⇒ médico responsable`) y
  Postgres valida **todas** las filas al crearlo. En producción es seguro —la
  compuerta D-0 se corrió dos veces y dio cero activos sin responsable— pero un
  entorno restaurado de un dump viejo puede quedarse sin arrancar. **Antes de
  migrar en un entorno nuevo, contar primero:** la consulta está escrita en el
  docstring de la propia migración 0028.
- **`crear_medico` no tiene `|| true`.** Aborta el arranque si solo una de
  `DJANGO_MEDICO_USERNAME` / `DJANGO_MEDICO_PASSWORD` está definida, o si ese
  usuario resulta ser superusuario.

**`crear_medico` reescribe la cuenta del médico en CADA arranque.** No es solo
"crear si no existe": sobre un usuario que ya existe ejecuta igual
`set_password(...)`, `is_staff = True`, `groups.set([...])` y
`user_permissions.clear()`. Si el médico cambia su contraseña en el Admin, **el
siguiente despliegue o reinicio la revierte en silencio** al valor de la variable
de entorno, y borra los permisos que se le hubieran concedido a mano. Tenerlo en
cuenta antes de entregarle la cuenta a una persona que espera gobernar su propia
contraseña — ver `docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`,
punto 8.

**Los comandos de datos de ejemplo están acotados, pero conviene saber cómo.**
`seed_demo` **se niega a correr con `DEBUG=False`**, así que es inerte en
producción. `seed_demo_produccion` exige `--confirmar`, y su `--limpiar` borra
**solo** los pacientes cuyo teléfono está en la lista fija `TELEFONOS_DEMO` del
propio archivo. El borde que queda: un paciente **real** registrado con uno de
esos teléfonos demo sí sería alcanzado por `--limpiar`. Al dar de alta pacientes
reales, no reutilizar esos números.

---

## Conexión con Twilio

**Lección clave de la conexión Twilio:** el Sandbox de WhatsApp firma sus webhooks
con el **Auth Token PRIMARIO** (Twilio Console → Account Dashboard), NO con el de
Test Credentials; usar el de Test causa `403`. Para ngrok free, `ALLOWED_HOSTS`
usa el comodín `.ngrok-free.dev` (el subdominio cambia en cada reinicio). Detalle
completo en BITACORA.md.

---

## IP del cliente y correo

**IP de producción resuelta (21/07/2026):** Railway documenta `X-Real-IP` como
la IP remota y `X-Railway-Edge` como marca agregada por su edge. El código solo
las usa con confianza explícita, formato de edge válido e IP validada; de lo
contrario vuelve a `REMOTE_ADDR`. `X-Forwarded-For` continúa descartado.

**Canal de correo resuelto (21/07/2026):** Resend aceptó y entregó un aviso
real sin PHI/PII. Llegó a spam por usar el dominio de prueba
`onboarding@resend.dev`; antes del piloto se requiere dominio propio autenticado.
