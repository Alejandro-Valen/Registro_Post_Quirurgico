"""Piezas de presentación del demo: color, cajas y ritmo.

Aislado a propósito en `demo/`: esta carpeta existe para la reunión y se puede
borrar entera sin tocar el sistema.

**No hay ninguna lógica del proyecto aquí.** Todo lo que se ve en pantalla sale
de llamar al bot y al motor reales; este módulo solo lo pinta.
"""

import contextlib
import os
import re
import shutil
import sys
import time

# En Windows la consola no interpreta las secuencias ANSI hasta que alguien
# habilita el modo terminal virtual. `os.system('')` lo hace de rebote y es el
# truco estándar; sin esto, la demo se ve llena de basura tipo `[38;5;...`.
if os.name == 'nt':
    os.system('')

# La consola de Windows sigue abriendo la salida en cp1252 en muchos equipos, y
# con eso «¿Cuál es tu temperatura?» se imprime como basura o revienta con
# UnicodeEncodeError. Todo el texto del bot lleva tildes y signos de apertura,
# así que esto no es cosmética: sin ello la demo no se puede enseñar.
for _flujo in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):
        _flujo.reconfigure(encoding='utf-8')

# --- Paleta -----------------------------------------------------------------
#
# Se eligen colores de 256 en vez de los 8 básicos porque los básicos los
# reasigna cada tema de terminal: el verde "WhatsApp" acabaría siendo el verde
# que tenga configurado quien proyecte. Con 256 el resultado es el mismo en
# cualquier máquina, que en una demo delante de gente es lo único que importa.
RESET = '\033[0m'
NEGRITA = '\033[1m'
TENUE = '\033[2m'

VERDE = '\033[38;5;42m'          # el paciente
VERDE_F = '\033[48;5;22m'
GRIS = '\033[38;5;245m'
GRIS_OSC = '\033[38;5;238m'
BLANCO = '\033[38;5;255m'
AZUL = '\033[38;5;39m'           # el bot
AMBAR = '\033[38;5;214m'         # severidad MEDIA
ROJO = '\033[38;5;203m'          # severidad ALTA
ROJO_F = '\033[48;5;52m'
CIAN = '\033[38;5;80m'
MORADO = '\033[38;5;141m'

SEVERIDAD_COLOR = {'ALTA': ROJO, 'MEDIA': AMBAR, 'BAJA': CIAN, None: GRIS}


def ancho():
    return max(80, min(shutil.get_terminal_size((100, 30)).columns, 120))


def limpiar():
    print('\033[2J\033[H', end='')


def escribir(texto='', fin='\n'):
    sys.stdout.write(texto + fin)
    sys.stdout.flush()


def pausa(segundos=0.9):
    """Ritmo de la demo.

    Existe porque una conversación que aparece de golpe no se lee: el ojo no
    distingue quién dijo qué. Con pausa se sigue como un chat de verdad.
    """
    time.sleep(segundos)


def esperar_tecla(mensaje='Enter para seguir'):
    escribir(f'{GRIS_OSC}   {mensaje}…{RESET}', fin='')
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        escribir()
    # Borra la línea del aviso para que no ensucie la transcripción.
    escribir('\033[1A\033[2K', fin='')


_RE_ANSI = re.compile(r'\033\[[0-9;]*m')


def visible(texto):
    """Longitud del texto sin contar las secuencias de color."""
    return len(_RE_ANSI.sub('', texto))


def recuadro(titulo, color=BLANCO, w=None):
    w = w or ancho()
    izq = f'{color}┌─ {NEGRITA}{titulo}{RESET}{color} '
    escribir(izq + '─' * max(0, w - visible(izq) - 1) + f'┐{RESET}')


def cierre_recuadro(color=BLANCO, w=None):
    w = w or ancho()
    escribir(f'{color}└' + '─' * (w - 2) + f'┘{RESET}')


def linea_recuadro(contenido='', color=BLANCO, w=None):
    w = w or ancho()
    relleno = max(0, w - visible(contenido) - 4)
    escribir(f'{color}│{RESET} {contenido}{" " * relleno} {color}│{RESET}')


def titulo_grande(texto, subtitulo=''):
    w = ancho()
    escribir()
    escribir(f'{VERDE}{"═" * w}{RESET}')
    escribir(f'{NEGRITA}{BLANCO}  {texto}{RESET}')
    if subtitulo:
        escribir(f'{GRIS}  {subtitulo}{RESET}')
    escribir(f'{VERDE}{"═" * w}{RESET}')
    escribir()


def burbuja(texto, quien='paciente', w_col=None):
    """Una burbuja de chat, alineada según quién habla.

    El paciente a la derecha y en verde, el bot a la izquierda y en gris: es la
    convención que todo el mundo reconoce sin que nadie se la explique.
    """
    w_col = w_col or (ancho() - 4)
    maximo = min(w_col - 14, 58)
    lineas = _envolver(texto, maximo)

    # La burbuja se encoge hasta el texto más largo que contiene, como en
    # WhatsApp. Con ancho fijo, un «hola» salía como un bloque verde de sesenta
    # caracteres y la pantalla dejaba de parecer una conversación.
    interior = max(len(ln) for ln in lineas)

    if quien == 'paciente':
        color, etiqueta = VERDE_F + BLANCO, f'{VERDE}paciente{RESET}'
        for i, ln in enumerate(lineas):
            cuerpo = f'{color} {ln.ljust(interior)} {RESET}'
            escribir(' ' * max(0, w_col - interior - 11) + cuerpo
                     + (f'  {etiqueta}' if i == 0 else ''))
    else:
        color = f'\033[48;5;236m{BLANCO}'
        etiqueta = f'{AZUL}bot{RESET}'
        for i, ln in enumerate(lineas):
            cuerpo = f'{color} {ln.ljust(interior)} {RESET}'
            escribir('  ' + cuerpo + (f'  {etiqueta}' if i == 0 else ''))
    escribir()


def _envolver(texto, ancho_max):
    salida = []
    for parrafo in texto.split('\n'):
        if not parrafo.strip():
            salida.append('')
            continue
        linea = ''
        for palabra in parrafo.split(' '):
            if len(linea) + len(palabra) + 1 > ancho_max:
                salida.append(linea)
                linea = palabra
            else:
                linea = f'{linea} {palabra}'.strip()
        salida.append(linea)
    return salida or ['']


def escribiendo(segundos=0.7):
    """El «escribiendo…» de WhatsApp. Puro teatro, y funciona."""
    marcos = ['·  ', '·· ', '···']
    fin = time.time() + segundos
    while time.time() < fin:
        for m in marcos:
            escribir(f'\r  {GRIS_OSC}escribiendo {m}{RESET}', fin='')
            time.sleep(0.12)
            if time.time() >= fin:
                break
    escribir('\r' + ' ' * 30 + '\r', fin='')
