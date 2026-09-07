# Instrucción para la próxima sesión — la decisión sobre `crear_medico`

> **Qué es esto.** El guion de la sesión que sigue al reparto de `tests.py` y a
> la guardia de secretos. Se escribió el 10/08/2026 para que quien retome no
> tenga que reconstruir el plan de una conversación.
>
> **Para quién.** Para el Arquitecto y para el agente que lo acompañe. El agente
> lee esto **después** de `CLAUDE.md`.

---

## Dónde quedamos

**Dos ramas cerradas y mergeadas el 10/08/2026:**

| PR | Qué | Merge |
|---|---|---|
| #12 | `signos_sintomas/tests.py` (6.288 líneas) partido en un paquete `tests/` de nueve archivos | `427153b` |
| #13 | Guardia de secretos y control de archivos de entorno en la CI | `301c743` |

**Suite: 340 tests OK.** **La CI ahora corre siete comprobaciones**, no cinco.
**Rama activa de trabajo: ninguna.** La de esta sesión se abre desde `Desarrollo`.

**Sigue sin haber producción** (venció Railway el 07/08/2026). No proponer nada
que dependa de desplegar. Esto importa especialmente hoy: el problema que se va a
decidir **solo se manifiesta al desplegar**, así que hoy no muerde — pero la
decisión es barata de tomar ahora y cara de improvisar cuando haya un médico real
esperando su cuenta.

---

## Prompt para arrancar la sesión

Copiar y pegar tal cual:

```text
Retomamos desde Desarrollo. Soy __ (Arquitecto).

Antes de proponer nada:
1. Lee proceso/instrucciones/2026-08-10_instruccion_crear_medico.md — es el guion de esta
   sesión.
2. Verifica el estado real con git log, git status y la suite. Si algo no
   coincide con los documentos, manda Git y avísame.

El objetivo de hoy es UNA DECISIÓN, no código: qué hacer con crear_medico, que
reescribe la cuenta del médico en cada arranque del servicio web. Primero
decidimos y documentamos; solo después se programa, y solo si la decisión lo
pide.

Ten en cuenta que ya no hay produccion en Railway (vencio la prueba). No
propongas nada que dependa de desplegar.
```

---

## El problema, con el código delante

`signos_sintomas/management/commands/crear_medico.py` corre **en cada arranque
del servicio web**. Está en los dos sitios que arrancan la app:

- `Dockerfile`, línea 37, encadenado con `&&` antes de gunicorn.
- `nixpacks.toml`, `[start]`, igual.

Lo que hace, resumido: garantiza que exista el grupo `Médicos` con sus permisos
y, **si están definidas** `DJANGO_MEDICO_USERNAME` y `DJANGO_MEDICO_PASSWORD`,
crea **o actualiza** esa cuenta:

```python
user, creado = User.objects.get_or_create(username=username, defaults={'email': email})
...
user.email = email
user.is_staff = True
user.is_superuser = False
user.set_password(password)     # ← reescribe la contraseña SIEMPRE
user.save()
user.groups.set([grupo])        # ← reemplaza los grupos
user.user_permissions.clear()   # ← borra permisos individuales
```

**La consecuencia:** si el médico entra al Admin y cambia su contraseña, **el
siguiente despliegue se la revierte en silencio** a la que esté en la variable de
entorno. No hay aviso, no hay error: la cuenta simplemente vuelve a la contraseña
del operador. Lo mismo con cualquier permiso que se le haya dado a mano.

**Un matiz que cambia el análisis y conviene no pasar por alto:** si las
variables `DJANGO_MEDICO_*` **no están definidas**, el comando no toca ninguna
cuenta — solo configura el grupo y sale. Es decir, parte del problema es de
**operación** (qué variables quedan puestas en el servicio) y no solo de código.

---

## Las opciones, con sus consecuencias

Ninguna es obviamente correcta. Por eso es decisión del Arquitecto y no de quien
programe.

| | Opción | Qué implica | Coste |
|---|---|---|---|
| **A** | **Quitar las variables del servicio** una vez creada la cuenta | Cero código. El comando pasa a configurar solo el grupo | Frágil: nada impide volver a ponerlas, y el porqué no queda escrito en ningún lado |
| **B** | **No tocar la contraseña si la cuenta ya existe** (`set_password` solo cuando `creado` es `True`) | Cambio pequeño y honesto con el nombre del comando: *crear*, no *reescribir* | Deja sin vía para rotar la contraseña si se filtra |
| **C** | **B + una vía explícita para forzar**, p. ej. `--forzar-credenciales` o `DJANGO_MEDICO_RESET=1` | Por defecto no toca nada; reescribir exige pedirlo a propósito | Un poco más de código y de documentación |
| **D** | **Separar los dos trabajos**: el arranque solo garantiza el grupo; crear o actualizar cuentas es un comando manual | El más limpio conceptualmente | El más invasivo: cambia el arranque y la operación |

**Recomendación de quien escribe este guion: C.** Es la única que responde bien a
las dos preguntas que se van a hacer de verdad —*"¿por qué me cambió la
contraseña?"* y *"¿cómo la roto si se filtró?"*— sin dejar la garantía de
privilegio mínimo a merced de que alguien se acuerde de quitar una variable.

**Y hay una segunda decisión escondida**, que conviene no resolver por inercia:
`groups.set([grupo])` y `user_permissions.clear()` también se ejecutan en cada
arranque. Eso **borra cualquier permiso extra** que se le haya dado al médico a
mano desde el Admin. ¿Es un bug o es la garantía de privilegio mínimo
funcionando? Se puede defender de las dos maneras, y la respuesta no tiene por
qué ser la misma que para la contraseña.

---

## Cómo cerrarlo

1. **Decidir primero, y escribirlo** en `docs/decisiones_correccion_auditoria.md`
   como ficha nueva, antes de tocar código. Es el método del proyecto: decidir →
   documentar → test en rojo → implementar → verificar.
2. Si la decisión pide código: rama propia desde `Desarrollo`, **test en rojo
   primero** —una prueba que demuestre que hoy la contraseña se revierte— y
   después la corrección.
3. Actualizar `docs/trampas_conocidas.md`, que hoy lleva la advertencia
   operativa, y `docs/railway_deploy.md` si cambia qué variables van en el
   servicio.
4. PR a `Desarrollo`. **Mirar los siete checks antes de mergear** — se ven pero
   no bloquean.
5. Cierre: BITÁCORA, `CLAUDE.md`, ROADMAP y el guion de la sesión siguiente.

Las pruebas del comando viven ahora en
`signos_sintomas/tests/test_commands.py`, clase `CrearMedicoCommandTests`. Se
corren solas, sin esperar los cuatro minutos y medio de la suite completa:

```bash
python manage.py test signos_sintomas.tests.test_commands.CrearMedicoCommandTests --noinput
```

---

## Lo que NO se hace en esta sesión

- **No se programa antes de decidir.** Si la conversación empieza a escribir
  código sin una decisión escrita, algo se saltó.
- **No se reabren D1-D14.** Están implementadas y verificadas.
- **No se repiten las auditorías.** Las dos (22/07 y 27/07) ya se ejecutaron.
- **No se propone nada que dependa de desplegar.** No hay dónde.
- **No se toca el `alert_engine` ni ningún umbral.** Esto es una cuenta de
  usuario, no una regla clínica.

---

## Después de esto

**No hay guion escrito más allá de este punto**, y es a propósito: lo que siga se
decide en sesión, no se hereda de una lista vieja. Lo único anotado como posible:

| Candidato | Qué sería |
|---|---|
| **Auditar la calidad de las pruebas** | Ahora que están repartidas por tema, revisar si alguna mide el código en vez del requisito. Al partirlas **no se revisó ninguna**, a propósito |
| **Protección de rama** | Decidir entre GitHub Pro (~4 USD/mes), repositorio público, o seguir mirando los checks a mano. **No es un trámite de permisos**: en un repo privado de cuenta Free, GitHub no la ofrece a nadie |

**Recordatorio:** los trámites del piloto real (WhatsApp Business, plan de
Railway, dominio en Resend, HABEAS DATA firmado) siguen **diferidos por decisión
del Arquitecto**. No proponer iniciarlos hasta que él lo indique.
