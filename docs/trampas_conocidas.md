# Trampas conocidas

> **Qué es esto.** Cosas que ya costaron horas y volverán a morder si nadie las
> escribe. No es historia —para eso está `BITACORA.md`— sino advertencias
> vigentes: cada una describe un comportamiento que sigue siendo cierto hoy.
>
> Si vas a tocar despliegue, cron, Twilio o correo, **lee esto primero**.

---

## Cron y despliegue en Railway

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
