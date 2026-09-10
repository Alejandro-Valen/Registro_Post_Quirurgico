# Demostración en vivo — la terminal como WhatsApp

> **Esta carpeta no es parte del sistema.** Existe para la reunión y se puede
> borrar entera sin tocar nada: no la importa ningún módulo del proyecto, no
> aparece en la suite, y no escribe en la base de datos de desarrollo.

## Cómo se corre

Desde la raíz del repositorio:

```
demo\demo.bat
```

O, si ya tienes el entorno virtual activo:

```
python demo/demo.py
```

Sale un menú de seis opciones. `q` para salir.

## Qué se ve

Una conversación de WhatsApp dibujada en la terminal —el paciente a la derecha
en verde, el bot a la izquierda— y, en el momento en que se dispara algo, **el
panel del médico** con las alertas que se acaban de generar.

| | Escenario | Qué enseña |
|---|---|---|
| 1 | Un día que va bien | El cuestionario completo sin ninguna alerta |
| 2 | La peor señal que capta el sistema | Contenido intestinal por el drenaje: seis alertas a la vez, y el paciente sin ver una sola palabra médica |
| 3 | El paciente que deja de responder | La escalera de SILENCIO subiendo sola, turno a turno: BAJA → MEDIA → MEDIA → ALTA |
| 4 | Cuando el paciente pide ayuda | La palabra de auxilio corta el cuestionario y avisa |
| 5 | Cómo sabemos que las pruebas sirven | El sabotaje del 07/09/2026 y los arneses que salieron de él |
| 6 | Modo libre | Escribes tú, en vivo |

## Lo que hay detrás — y por qué importa

**No hay guion.** Cada mensaje pasa por `bot.procesar_mensaje()` y cada registro
por `alert_engine.evaluar_registro()`: las mismas funciones que atenderían a un
paciente real. El escenario 3 llama al *management command* real del cron,
`cerrar_checkins_vencidos`. Si el sistema se equivoca durante la demo, se ve.

**Que enchufar una terminal salga gratis no es mérito de esta carpeta.** El bot
se escribió desde el principio como lógica pura respecto al transporte —recibe
texto plano, devuelve texto plano, no conoce HTTP ni Twilio—. Cambiar WhatsApp
por una terminal es cambiarle la puerta de entrada.

**La base de datos se crea al arrancar y se destruye al salir.** Es la maquinaria
de bases de prueba de Django. Ningún paciente de la demo sobrevive a cerrar la
ventana.

**Si PostgreSQL no está levantado**, la demo sigue sobre SQLite en memoria y lo
dice en pantalla. Se comprobó en las dos direcciones —con el motor arriba y con
el motor caído— y el caso grave produce las mismas alertas en los dos. Lo único
que se pierde es un índice de rendimiento que ninguna regla clínica usa.

## Modo libre: qué probar delante de alguien

- `AYUDA` en cualquier momento del cuestionario.
- Una temperatura mal escrita: `379`, `treinta y siete`, `37,5`.
- `saltar` cuando no hay termómetro.
- `no tengo termómetro` — frase completa, no solo la palabra.
- Un dolor fuera de rango: `15`.
