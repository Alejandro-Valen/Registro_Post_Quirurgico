"""Demostración interactiva del sistema, para la reunión.

    python demo/demo.py

QUÉ ES
======

Una terminal que hace de WhatsApp. Se escribe como escribiría un paciente y
responde **el bot de verdad**: cada mensaje pasa por `bot.procesar_mensaje()` y
por `alert_engine.evaluar_registro()`, las mismas funciones que atenderían a una
persona real. A la derecha se ve, en el mismo instante, **lo que le aparece al
médico**.

No hay guion escondido ni respuestas grabadas. Si el bot se equivoca durante la
demo, se ve.

QUÉ NO ES
=========

No es el producto. El paciente real usaría WhatsApp; esto es la misma lógica con
otra puerta. Que eso salga gratis no es mérito de la demo: el bot se escribió
como *lógica pura respecto al transporte* desde el primer día.

DÓNDE VIVE
==========

En `demo/`, aparte del sistema. Se puede borrar la carpeta entera sin tocar
nada. Corre sobre una base de datos temporal que se destruye al salir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import entorno
from estilo import (
    AMBAR,
    AZUL,
    BLANCO,
    CIAN,
    GRIS,
    GRIS_OSC,
    MORADO,
    NEGRITA,
    RESET,
    ROJO,
    SEVERIDAD_COLOR,
    TENUE,
    VERDE,
    ancho,
    burbuja,
    cierre_recuadro,
    escribiendo,
    escribir,
    esperar_tecla,
    limpiar,
    linea_recuadro,
    pausa,
    recuadro,
    titulo_grande,
)

DIAG = {
    'SEPSIS': 'Fiebre — posible sepsis',
    'FUGA_ANASTOMOTICA': 'Fuga anastomótica',
    'ILEO_PARALITICO': 'Íleo paralítico',
    'DOLOR_AGUDO': 'Dolor agudo',
    'INTOLERANCIA_ORAL': 'Intolerancia oral',
    'TAQUICARDIA': 'Taquicardia',
    'SILENCIO': 'Sin respuesta',
    'AUXILIO': 'PIDIÓ AYUDA',
}

ACCION = {'ALTA': 'ir a urgencias', 'MEDIA': 'llamar al médico',
          'BAJA': 'monitorear'}


# ---------------------------------------------------------------------------
# El panel del médico
# ---------------------------------------------------------------------------
def panel(paciente, destacar=None):
    """Lo que el médico tiene delante ahora mismo."""
    w = ancho()
    alertas = entorno.alertas_de(paciente)
    altas = sum(1 for a in alertas if a.severidad == 'ALTA')

    color = ROJO if altas else (AMBAR if alertas else VERDE)
    recuadro(f'PANEL DEL MÉDICO · {paciente.nombre_completo}', color, w)

    from django.utils import timezone
    pod = (timezone.localdate() - paciente.fecha_cirugia).days
    linea_recuadro(f'{GRIS}Día postoperatorio {pod}{RESET}', color, w)
    linea_recuadro('', color, w)

    if not alertas:
        linea_recuadro(f'{VERDE}✓ Sin alertas pendientes.{RESET}', color, w)
    for a in alertas:
        c = SEVERIDAD_COLOR[a.severidad]
        nuevo = f'  {NEGRITA}{c}◀ NUEVA{RESET}' if destacar and a.pk in destacar else ''
        veces = f' {TENUE}×{a.veces}{RESET}' if a.veces > 1 else ''
        linea_recuadro(
            f'{c}{NEGRITA}{a.severidad:<5}{RESET} {BLANCO}'
            f'{DIAG.get(a.tipo, a.tipo)}{RESET}{veces}'
            f'  {GRIS_OSC}→ {ACCION[a.severidad]}{RESET}{nuevo}', color, w)
    cierre_recuadro(color, w)


def turno_del_paciente(paciente, texto, mostrar_panel=True):
    """Un mensaje del paciente, de principio a fin, con lo que provoca."""
    antes = {a.pk for a in entorno.alertas_de(paciente)}

    burbuja(texto, 'paciente')
    pausa(0.35)
    escribiendo(0.6)
    respuesta = entorno.hablar(paciente, texto)
    burbuja(respuesta, 'bot')

    despues = entorno.alertas_de(paciente)
    nuevas = {a.pk for a in despues} - antes
    if mostrar_panel and despues:
        panel(paciente, destacar=nuevas)
        escribir()
    return respuesta


# ---------------------------------------------------------------------------
# Escenarios
# ---------------------------------------------------------------------------
def _cabecera(n, titulo, explicacion):
    limpiar()
    titulo_grande(f'ESCENARIO {n} · {titulo}', explicacion)
    esperar_tecla('Enter para empezar')


def escenario_normal():
    _cabecera(1, 'Un día que va bien',
              'Paciente en el día 5. Todo dentro de lo esperado.')
    p = entorno.crear_paciente('Ana Restrepo', '+573001110001', 5)
    entorno.abrir_turno(p)
    for m in ['hola', '36.8', '2', 'no', 'si, 0', 'nada', '76', '16', 'si']:
        turno_del_paciente(p, m, mostrar_panel=False)
    panel(p)
    escribir()
    escribir(f'{GRIS}  Nueve preguntas, ninguna alerta. El médico no tiene que'
             f' hacer nada,{RESET}')
    escribir(f'{GRIS}  y eso también es información: el paciente va bien.{RESET}')
    escribir()
    esperar_tecla()


def escenario_fuga():
    _cabecera(2, 'La peor señal que capta el sistema',
              'El mismo cuestionario. Cambia una respuesta.')
    p = entorno.crear_paciente('Jorge Villa', '+573001110002', 4)
    entorno.abrir_turno(p)
    turno_del_paciente(p, 'hola', mostrar_panel=False)
    turno_del_paciente(p, '38.4', mostrar_panel=False)
    turno_del_paciente(p, '7', mostrar_panel=False)
    turno_del_paciente(p, 'si', mostrar_panel=False)

    escribir(f'{GRIS_OSC}  ── El paciente ve un menú de cinco opciones, escrito'
             f' sin una sola palabra médica.{RESET}')
    escribir(f'{GRIS_OSC}     La 5 es «café oscuro o con olor muy fuerte»:'
             f' contenido intestinal.{RESET}')
    escribir()
    pausa(1.2)

    turno_del_paciente(p, '5', mostrar_panel=False)
    turno_del_paciente(p, 'mucho', mostrar_panel=False)
    turno_del_paciente(p, 'no, 3', mostrar_panel=False)
    turno_del_paciente(p, 'mucho', mostrar_panel=False)
    turno_del_paciente(p, '118', mostrar_panel=False)
    turno_del_paciente(p, '20', mostrar_panel=False)
    turno_del_paciente(p, 'no')

    escribir(f'{BLANCO}  Lo que acaba de pasar:{RESET}')
    escribir(f'{GRIS}   · El paciente nunca vio la palabra «sepsis» ni «fuga».'
             f' Solo se le dijo{RESET}')
    escribir(f'{GRIS}     qué hacer. Es una regla del proyecto, no un descuido.{RESET}')
    escribir(f'{GRIS}   · El médico ve el cuadro completo, agrupado por problema.{RESET}')
    escribir()
    esperar_tecla()


def escenario_silencio():
    _cabecera(3, 'El paciente que deja de responder',
              'La ausencia de datos también es una señal, y escala sola.')
    p = entorno.crear_paciente('Marta Ochoa', '+573001110003', 6)
    escribir(f'{GRIS}  Se le abren cuatro turnos —dos días— y no responde a'
             f' ninguno.{RESET}')
    escribir(f'{GRIS}  Cada vez que uno vence, el cron lo cierra y vuelve a'
             f' contar la racha.{RESET}')
    escribir()
    pausa(1.2)

    turnos = [(2, 1, 'anteayer, mañana'), (2, 2, 'anteayer, tarde'),
              (1, 1, 'ayer, mañana'), (1, 2, 'ayer, tarde')]
    for dias, orden, etiqueta in turnos:
        entorno.abrir_turno(p, dias_atras=dias, orden=orden, horas_atras=11)
        entorno.vencer_turnos()
        a = entorno.alertas_de(p)
        sev = a[0].severidad if a else '—'
        c = SEVERIDAD_COLOR.get(sev, GRIS)
        escribir(f'   {GRIS}{etiqueta:<18}{RESET} sin respuesta   →   '
                 f'{c}{NEGRITA}SILENCIO / {sev}{RESET}')
        pausa(0.9)
    escribir()
    panel(p)
    escribir()
    escribir(f'{GRIS}  Cuatro turnos son dos días completos sin una sola'
             f' señal.{RESET}')
    escribir(f'{GRIS}  Nadie tuvo que revisar una lista: la alerta subió'
             f' sola.{RESET}')
    escribir()
    escribir(f'{GRIS_OSC}  Y si el paciente hubiera respondido una sola vez, la'
             f' racha se rompe y{RESET}')
    escribir(f'{GRIS_OSC}  vuelve a empezar. Un turno que el sistema no llegó a'
             f' enviar no cuenta:{RESET}')
    escribir(f'{GRIS_OSC}  una caída del cron no debe parecer un paciente'
             f' callado.{RESET}')
    escribir()
    esperar_tecla()


def escenario_auxilio():
    _cabecera(4, 'Cuando el paciente pide ayuda',
              'A mitad del cuestionario, algo va mal.')
    p = entorno.crear_paciente('Luis Cárdenas', '+573001110004', 3)
    entorno.abrir_turno(p)
    for m in ['hola', '37.2', '4', 'no']:
        turno_del_paciente(p, m, mostrar_panel=False)
    escribir(f'{GRIS_OSC}  ── Toca la pregunta de gases y náuseas. Pero el'
             f' paciente escribe otra cosa.{RESET}')
    escribir()
    pausa(1.2)
    turno_del_paciente(p, 'estoy sangrando mucho, necesito ayuda')
    escribir(f'{BLANCO}  Hasta el 08/09/2026 esto se guardaba como un dato más'
             f' y el bot{RESET}')
    escribir(f'{BLANCO}  seguía preguntando.{RESET} {GRIS}Hoy corta el'
             f' cuestionario y avisa.{RESET}')
    escribir()
    esperar_tecla()


# ---------------------------------------------------------------------------
# El arnés: romper el sistema a propósito
# ---------------------------------------------------------------------------
def escenario_arnes():
    limpiar()
    titulo_grande('CÓMO SABEMOS QUE LAS PRUEBAS SIRVEN',
                  'Una prueba en verde no prueba nada si no se ha visto en rojo.')
    escribir(f'{GRIS}  El 07/09/2026 se quitó una palabra de una lista del motor'
             f' clínico:{RESET}')
    escribir()
    escribir(f"      {ROJO}- DRENAJES_ALTA = ('purulento', 'fecaloide'){RESET}")
    escribir(f"      {VERDE}+ DRENAJES_ALTA = ('purulento',){RESET}")
    escribir()
    escribir(f'{GRIS}  Con esa línea así, un paciente puede reportar contenido'
             f' intestinal{RESET}')
    escribir(f'{GRIS}  por el drenaje y no generarse ninguna alerta.{RESET}')
    escribir()
    escribir(f'  {NEGRITA}Las 344 pruebas de entonces siguieron en verde.{RESET}')
    escribir()
    esperar_tecla()

    escribir(f'{GRIS}  Ese día cambió cómo trabajamos. Hoy cada corrección lleva'
             f' un arnés{RESET}')
    escribir(f'{GRIS}  que rompe el sistema a propósito y exige que la prueba'
             f' caiga:{RESET}')
    escribir()
    for nombre, n in [('umbrales clínicos', '21 de 21'),
                      ('bugs del paciente', '17 de 17'),
                      ('bloqueo de acceso', '4 de 4'),
                      ('veracidad de la documentación', '7 de 7')]:
        escribir(f'   {MORADO}▸{RESET} {BLANCO}{nombre:<32}{RESET}'
                 f' {VERDE}{n} atrapados{RESET}')
        pausa(0.45)
    escribir()
    escribir(f'{GRIS}  Son scripts en el repositorio. Se pueden correr ahora'
             f' mismo.{RESET}')
    escribir()
    esperar_tecla()


# ---------------------------------------------------------------------------
# Modo libre
# ---------------------------------------------------------------------------
def modo_libre():
    limpiar()
    titulo_grande('MODO LIBRE',
                  'Escribe como escribiría el paciente. Responde el bot real.')
    p = entorno.crear_paciente('Paciente en vivo', '+573001119999', 5)
    entorno.abrir_turno(p)
    escribir(f'{GRIS}  Empieza con «hola». Escribe «salir» para volver al'
             f' menú.{RESET}')
    escribir(f'{GRIS}  Prueba también: «AYUDA», «saltar», o una temperatura mal'
             f' escrita como «379».{RESET}')
    escribir()
    while True:
        try:
            texto = input(f'  {VERDE}tú ▸ {RESET}')
        except (EOFError, KeyboardInterrupt):
            return
        if texto.strip().lower() in ('salir', 'exit', 'q'):
            return
        if not texto.strip():
            continue
        escribir('\033[1A\033[2K', fin='')
        turno_del_paciente(p, texto)


# ---------------------------------------------------------------------------
# Menú
# ---------------------------------------------------------------------------
OPCIONES = [
    ('1', 'Un día que va bien', escenario_normal),
    ('2', 'La peor señal que capta el sistema', escenario_fuga),
    ('3', 'El paciente que deja de responder', escenario_silencio),
    ('4', 'Cuando el paciente pide ayuda', escenario_auxilio),
    ('5', 'Cómo sabemos que las pruebas sirven', escenario_arnes),
    ('6', 'Modo libre — escribe tú', modo_libre),
]


def menu():
    while True:
        limpiar()
        w = ancho()
        escribir()
        escribir(f'{VERDE}{"═" * w}{RESET}')
        escribir(f'{NEGRITA}{BLANCO}  SEGUIMIENTO POSTQUIRÚRGICO REMOTO{RESET}')
        escribir(f'{GRIS}  Demostración en vivo · el bot y el motor de alertas'
                 f' reales{RESET}')
        escribir(f'{VERDE}{"═" * w}{RESET}')
        escribir()
        for tecla, nombre, _ in OPCIONES:
            escribir(f'   {CIAN}{NEGRITA}{tecla}{RESET}  {BLANCO}{nombre}{RESET}')
        escribir()
        escribir(f'   {GRIS_OSC}q  salir{RESET}')
        escribir()
        try:
            eleccion = input(f'  {AZUL}▸ {RESET}').strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if eleccion in ('q', 'salir', ''):
            return
        for tecla, _, funcion in OPCIONES:
            if eleccion == tecla:
                funcion()
                break


def main():
    limpiar()
    escribir()
    escribir(f'{GRIS}  Levantando el sistema sobre una base de datos temporal…'
             f'{RESET}')
    motor = entorno.arrancar()
    if motor != 'PostgreSQL':
        escribir(f'{AMBAR}  PostgreSQL no respondió: la demo corre sobre'
                 f' {motor}.{RESET}')
        escribir(f'{GRIS_OSC}  El bot y el motor de alertas son los mismos; solo'
                 f' cambia dónde se guarda.{RESET}')
        pausa(2.0)
    try:
        menu()
    finally:
        escribir()
        escribir(f'{GRIS}  Borrando la base temporal…{RESET}')
        entorno.apagar()
        escribir(f'{VERDE}  Listo. No queda rastro.{RESET}')
        escribir()


if __name__ == '__main__':
    main()
