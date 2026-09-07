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

**`crear_medico` corre en CADA arranque, y desde el 12/08/2026 sabe distinguir
qué debe reescribir.** Hasta esa fecha reescribía todo: sobre un usuario que ya
existía ejecutaba igual `set_password(...)`, `user.email = ...`,
`groups.set([...])` y `user_permissions.clear()`, así que un médico que cambiaba
su contraseña en el Admin **se la veía revertida en silencio** en el siguiente
despliegue. La decisión **D15** lo separó en tres comportamientos distintos, y
conviene conocerlos antes de tocar la cuenta:

- **La contraseña ya no se toca** si la cuenta existe. La elige el médico y le
  sobrevive a los despliegues.
- **Para rotarla hay que pedirlo:** `DJANGO_MEDICO_RESET=1` en el servicio, un
  reinicio, y **quitar la variable después** — si se queda puesta, vuelve el
  comportamiento viejo en cada arranque. Mismo convenio que `RESET_AXES`: el
  valor tiene que ser exactamente `1`.
- **Los grupos y permisos individuales SÍ se reescriben**, a propósito: el
  privilegio mínimo es declarativo. Un permiso concedido a mano desde el Admin
  **desaparece en el siguiente arranque**. Para ampliar lo que puede hacer el
  médico se edita `PERMISOS_MEDICO` en el propio comando, no la cuenta.

**Cómo saber cuál de los tres casos ocurrió:** el comando lo dice en el log del
despliegue — `creada con privilegio mínimo`, `permisos al día; contraseña sin
tocar`, o `credenciales reescritas por DJANGO_MEDICO_RESET=1`. Es lo primero que
hay que mirar cuando el médico reporte que no puede entrar.

Razonamiento completo en `docs/decisiones_correccion_auditoria.md`, ficha D15;
el hallazgo que lo originó, en
`docs/proceso/auditorias/2026-07-29_revision_pr_sprint5.md`, punto 8.

**Trampa asociada, esta sigue viva:** `DJANGO_MEDICO_EMAIL` alimenta el campo que
`notificaciones.py` usa como **destinatario de las alertas**. Hasta el
12/08/2026, si esa variable faltaba, cada arranque vaciaba el correo del médico y
las alertas ALTA morían en `DestinatarioNoConfigurado`. Ya no se vacía solo —
pero si nunca se definió, el campo sigue vacío y el resultado es el mismo. **Al
crear la cuenta, comprobar que el médico tiene correo.**

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

---

## Pruebas y comprobaciones locales

**`check --deploy` falla en tu máquina y no es tu código (10/08/2026).**
Ejecutado en local contra `settings_production`, aborta con
`ImproperlyConfigured: La variable de entorno CSRF_TRUSTED_ORIGINS es
obligatoria`. No hay nada roto: el `.env` de desarrollo no define las variables
que esa configuración exige. La CI sí las define, y ahí pasa en verde. Si
quieres reproducir la comprobación de la CI en local, define las mismas
variables que `ci.yml` antes de correrlo. **No "arregles" el código por esto.**

**`tests/__init__.py` no se puede borrar, y su ausencia no da error
(10/08/2026).** Desde que `tests.py` es un paquete, Django descubre las pruebas
solo si el paquete tiene `__init__.py`. Sin él, el directorio **no se recorre**:
no hay excepción, no hay aviso, la suite simplemente reporta menos pruebas y
sigue en verde. El conteo baja en silencio. Por la misma razón el archivo de
piezas compartidas se llama `soporte.py` y **no** `test_soporte.py`: si casara
con el patrón `test*.py`, el descubridor lo recorrería.

**Un conteo de pruebas igual no prueba que no se perdió nada (10/08/2026).** Al
partir `tests.py` se comprobó que seguían siendo 340, pero eso lo cumpliría
también un paquete al que se le perdió una prueba y se le duplicó otra. La
comprobación que sirve es comparar los nombres `Clase.metodo` uno a uno contra
el archivo original. Vale para cualquier refactor futuro que mueva pruebas.

**`pip-audit` revienta en local por la tilde de la ruta, no por una
vulnerabilidad (07/09/2026).** En esta máquina el usuario de Windows se llama
`león`, así que la ruta del entorno virtual lleva una `ó`. `pip_api` —una
dependencia de `pip-audit`— ejecuta `pip --version` y decodifica su salida como
UTF-8; Windows la devuelve en cp1252 y el comando muere con
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf3` **antes de mirar
ninguna dependencia**.

Lo importante: **eso no dice absolutamente nada sobre la seguridad de las
dependencias.** En la CI (Linux, rutas ASCII) corre sin problema, y es ahí donde
la comprobación cuenta. `docs/proceso/verificaciones/2026-09-07_verificacion_arnes.py`
distingue este caso a propósito y lo reporta como "no verificable en esta
máquina" en vez de como fallo — dar por vulnerable lo que solo es un problema
de codificación sería justo el tipo de conclusión falsa que las verificaciones
existen para evitar.

**Un linter recién añadido puede dejar espacios al final de línea y romper otra
comprobación (07/09/2026).** Al convertir `'...'.format(x)` en f-strings, `ruff`
dejó líneas en blanco **con espacios** donde estaba el `.format(...)`. Es válido
para Python y para el propio linter, pero hace fallar el paso «Higiene del diff»
de la CI, que corre `git diff --check`. Tras cualquier corrida de `ruff --fix`,
comprobar `git diff --check` antes de commitear.

**`ruff` mueve los import-estrella de los settings, y ahí el orden importa
(07/09/2026).** El ordenador de imports movió `from .settings import *` detrás
de los demás imports en `settings_production.py`. Funcionalmente no rompió nada,
pero ese archivo gobierna la seguridad de producción y su orden de carga no debe
reordenarse solo. Lleva `# isort: skip` por eso. No se lo quites.

## Secretos

**`gitleaks` no detecta una `SECRET_KEY` de Django escrita a mano
(10/08/2026).** Se comprobó: ninguna de sus ~170 reglas de fábrica cubre ese
caso, que es justo el error que este proyecto cometió en el Sprint 0. Por eso
`.gitleaks.toml` lleva una regla propia, `django-secret-key-literal`. **Si
alguien simplifica esa configuración a `useDefault = true` y borra la regla, se
pierde la única protección contra el error que ya ocurrió aquí.**

**Un secreto de prueba escrito entero se convierte en un hallazgo real
(10/08/2026).** El script de verificación de la guardia lleva cebos —claves
falsas— y, escritos literalmente, `gitleaks` los encuentra **en el propio
script** en cuanto entra en un commit: la guardia se dispara contra sí misma y
todo escaneo da rojo. Se arman por concatenación (`"SK" + "0123..."`). La salida
fácil sería meter esa ruta en la allowlist, y sería peor: dejaría un archivo del
repositorio donde un secreto de verdad podría esconderse para siempre.

**Cuidado con `git stash` antes de verificar (10/08/2026).** Si `.gitleaksignore`
se va en el stash, reaparece el hallazgo histórico del Sprint 0 y **todo** da
rojo, por un motivo que no tiene nada que ver con lo que estabas probando. Costó
dos rondas de diagnóstico. El script de verificación ahora aborta si el árbol
está sucio.
