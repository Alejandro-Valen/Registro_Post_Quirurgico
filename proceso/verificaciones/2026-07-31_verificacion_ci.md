# Verificación de la CI — se la vio fallar, comprobación por comprobación

> **Por qué esta verificación es un documento y no un script.** Las otras de
> esta carpeta son `.py` porque comprueban el comportamiento del código y se
> pueden volver a ejecutar. Lo que hay que verificar de una CI es que **se ponga
> en rojo cuando debe**, y eso no se reproduce localmente: la evidencia son las
> corridas de GitHub Actions, con su SHA y su mensaje de error. Esto las
> registra.
>
> **Regla que aplica:** `proceso/metodo_de_trabajo.md`, regla 2 — *un test
> en verde no prueba nada si no se verifica por qué está verde.* Aplicada a la
> propia CI: un workflow que nunca vio un rojo no está probado.

**Fecha:** 31/07/2026 · **Rama:** `sprint-6-ci` · **PR:** [#5](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/pull/5)
**Workflow:** `.github/workflows/ci.yml` · **Commit verificado:** `e1d73af`

---

## Resumen

Cinco comprobaciones, cinco vistas en rojo, cada una con su mensaje propio, y
después las cinco en verde sobre el commit final. Las roturas se hicieron en dos
commits temporales que **ya no existen en la rama**: se borraron con
`git reset --hard e1d73af` y `push --force-with-lease`, así que la evidencia vive
aquí y en las corridas, no en la historia de `Desarrollo`.

| # | Comprobación | Rota a propósito con | Vista en rojo |
|---|---|---|---|
| 1 | Higiene del diff | Una línea terminada en tres espacios | [run 30674617834](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674617834) |
| 2 | Comprobaciones del sistema | Columna inexistente en `list_display` | [run 30674851992](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674851992) |
| 3 | Migraciones al día | `help_text` cambiado sin migración | [run 30674617834](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674617834) |
| 4 | Configuración de producción | `RESEND_API_KEY` retirada del entorno | [run 30674617834](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674617834) |
| 5 | Suite completa | Una prueba con una aserción que falla | [run 30674617834](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674617834) |

---

## Las corridas, en orden

| Run | Commit | Resultado | Qué demostró |
|---|---|---|---|
| [30674174843](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674174843) | `c187d57` | 4 verdes, suite roja | **Rojo no buscado.** Ver abajo |
| [30674440539](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674440539) | `e1d73af` | Las 5 en verde | 337 tests en Linux, 1m45s |
| [30674617834](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674617834) | `36dc751` | 4 rojas, `check` verde | Rotura deliberada 1 de 2 |
| [30674851992](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674851992) | `e5630b8` | Las 5 rojas | Rotura deliberada 2 de 2 |
| [30674921355](https://github.com/Alejandro-Valen/Registro_Post_Quirurgico/actions/runs/30674921355) | `e1d73af` | Las 5 en verde | Estado final, tras borrar las roturas |

> **Nota del 09/09/2026.** Los commits `36dc751` y `e5630b8` **ya no existen**
> en el repositorio: eran las roturas deliberadas, y se borraron de la rama al
> terminar la verificación, así que no son alcanzables desde ninguna
> referencia. `git show` sobre ellos falla en cualquier clon.
>
> **La evidencia de aquel día no es el commit: son los enlaces a las corridas**,
> que sí son permanentes y públicos. Los SHA se conservan como etiqueta de qué
> se probó en cada una.
>
> Lo detectó el barrido de veracidad en su primera corrida en la CI — en local
> pasaba, porque la copia del Arquitecto todavía guarda esos objetos.

---

## Mensajes de error, textuales

Se transcriben porque un paso "en rojo" no dice nada por sí solo: lo que
demuestra que el paso mide lo que dice medir es **qué** denunció.

**1 · Higiene del diff**

```
Registro_Post_Quirurgico/signos_sintomas/tests_ci_rojo.py:24: trailing whitespace.
```

Es la comprobación que más importaba ver en rojo, porque es la que se apartó del
guion: `git diff --check` sin argumentos —tal como estaba escrito— compara el
árbol de trabajo contra el índice, y en un checkout limpio de CI eso está siempre
vacío. **Habría dado verde siempre.** Aquí corre contra `base.sha...HEAD`.

**2 · Comprobaciones del sistema**

```
SystemCheckError: System check identified some issues:
<class 'home.admin.MensajeContactoAdmin'>: (admin.E108) The value of
'list_display[0]' refers to 'columna_que_no_existe', which is not a callable or
attribute of 'MensajeContactoAdmin', or an attribute, method, or field on
'home.MensajeContacto'.
```

**3 · Migraciones al día**

```
Migrations for 'home':
    ~ Alter field medico_destinatario on mensajecontacto
```

La rotura fue un `help_text` distinto, elegido a propósito porque **no toca el
esquema**: así el paso de migraciones cae solo, sin arrastrar a la suite, y su
rojo es atribuible.

**4 · Configuración de producción**

```
django.core.exceptions.ImproperlyConfigured: La variable de entorno
RESEND_API_KEY es obligatoria y está vacía o sin definir.
```

Este es el mensaje de `config_obligatoria` (hallazgo 11 del Loop C). Vale doble:
prueba que el paso carga de verdad `settings_production` —y no la configuración
base— y de paso vuelve a ejercitar el fail-fast del arranque.

**5 · Suite completa**

```
FAIL: test_esta_prueba_debe_fallar
AssertionError: 'la CI detecta el fallo' != 'la CI no detecta nada'
Ran 338 tests in 89.887s
FAILED (failures=1)
```

338 y no 337: la prueba temporal es la de más.

---

## Los pasos son independientes, y está demostrado

No es una suposición del diseño: se vio dos veces.

- En la **rotura 1**, `Comprobaciones del sistema` quedó **en verde** mientras
  las otras cuatro caían.
- En la **primera corrida** (`c187d57`), la suite cayó sola y las otras cuatro
  pasaron.

Es la consecuencia buscada del `if: !cancelled()` de cada paso: una corrida en
rojo muestra **todo** lo que está mal de una vez, en vez de obligar a arreglar de
a uno y esperar cinco minutos entre cada intento.

---

## El rojo que no se buscó, y es el hallazgo de la sesión

La **primera** corrida (`c187d57`) no estaba planeada como verificación de nada:
era la corrida normal del PR. Dejó cuatro comprobaciones en verde y la suite en
rojo, con una sola falla:

```
FAIL: home.tests.ClientIpTests.test_por_defecto_ignora_headers_spoofeables
AssertionError: '198.51.100.20' != '10.0.0.4'
```

**La causa fue el entorno de la CI, no un defecto del sistema:** el workflow
traía `TRUST_RAILWAY_PROXY=True`. Corregido a `False` en `e1d73af`, que es el
valor que documenta `.env.example`.

**Pero deja algo que sí importa.** Esa prueba comprueba que **sin confianza
declarada no se cree la cabecera `X-Real-IP`** — es decir, el default seguro de
`home.views._get_client_ip`. Sus tres hermanas de la misma clase fijan el valor
con `@override_settings(TRUST_RAILWAY_PROXY=True)`; ella no fija nada: **lee el
del entorno de quien corra la suite.**

Las dos consecuencias:

1. Pasa en verde en Windows porque el `.env` local trae `False`. En una máquina
   con `True` cae sin que nada esté mal — que es exactamente lo que pasó aquí.
2. Y al revés, que es lo grave: **si alguna vez se rompiera el default seguro**,
   esa prueba solo lo denunciaría si quien la corre tiene la variable en `False`.
   La guarda de una decisión de seguridad depende de un archivo que no está en el
   repositorio.

Es el mismo patrón del hallazgo bloqueante del 22/07 —una prueba que parece medir
un requisito y en realidad mide otra cosa—, en versión pequeña y sin consecuencia
clínica.

**No se arregló en la rama de la CI, a propósito** —arreglarlo era tocar la
suite—, pero **sí en la misma sesión, en su propia rama:** PR #7, merge
`dc32530`.

La corrección es un `@override_settings(TRUST_RAILWAY_PROXY=False)` sobre esa
prueba, y se verificó en las tres direcciones, porque fijar un valor puede
convertir una prueba en una que pasa siempre:

| Comprobación | Antes | Después |
|---|---|---|
| La clase con `TRUST_RAILWAY_PROXY=True` en el entorno | `AssertionError: '198.51.100.20' != '10.0.0.4'` | OK (5 tests) |
| La clase con `TRUST_RAILWAY_PROXY=False` en el entorno | OK | OK (5 tests) |
| **Con la guarda de `_get_client_ip` anulada a propósito** | — | **FAILED** — la prueba sigue sirviendo |

La tercera fila es la que cierra el asunto: la prueba dejó de depender del
entorno **sin** dejar de denunciar la regresión que le toca vigilar. `views.py`
quedó intacto; solo cambió `home/tests.py`.

---

## Lo que esta verificación NO cubre

- **La CI no es obligatoria para mergear.** `Desarrollo` no tiene protección de
  rama configurada, así que hoy los checks se ven pero no bloquean: alguien puede
  mergear en rojo. Configurarlo requiere permisos de administrador del
  repositorio, que la cuenta del Arquitecto no tiene (el repo es de Alejandro).
- **La versión de PostgreSQL de Railway no está documentada.** La CI usa
  `postgres:18`, la misma mayor que la base local. Si producción corre otra, esta
  CI no lo detectaría.
- **La CI no prueba el despliegue.** Verifica que `settings_production` carga y
  que `check --deploy` pasa; no construye la imagen del `Dockerfile` ni ejecuta
  el `CMD`.
