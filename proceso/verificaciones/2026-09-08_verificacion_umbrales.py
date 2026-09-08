"""Verificacion del loop de umbrales — 08/09/2026.

QUE COMPRUEBA
=============

Que cada prueba de frontera anadida en este loop **puede ponerse en rojo**. No
repite la suite: rompe el motor clinico a proposito, una constante a la vez, y
exige que la prueba correspondiente CAIGA. Una prueba que no cae con su sabotaje
aplicado no esta protegiendo el umbral que dice proteger.

POR QUE EXISTE
==============

El 07/09/2026 se ejecuto este sabotaje sobre `alert_engine.py`:

    - DRENAJES_ALTA  = ('purulento', 'fecaloide')
    + DRENAJES_ALTA  = ('purulento',)

y las 344 pruebas de entonces quedaron **en verde** con el motor roto: un
paciente podia reportar contenido intestinal saliendo por el drenaje —una fuga
anastomotica franca— sin que se generara ninguna alerta. La auditoria de calidad
de pruebas propuso 18 sabotajes de una linea y predijo que **14 pasarian**. De
esos 18 solo se conservaron por escrito los cinco de mas peso: la lista completa
se perdio con la sesion que la produjo (el guion y el informe se citaban el uno
al otro sin que estuviera en ninguno; detectado el 08/09/2026).

Por eso este script no "comprueba la prediccion" de la auditoria: la SUSTITUYE.
Los 21 sabotajes de abajo son de diseno propio, cubren las ocho familias de
reglas, e --a diferencia de aquella lista-- quedan escritos y se pueden volver a
correr.

COMO SE USA
===========

    python proceso/verificaciones/2026-09-08_verificacion_umbrales.py

Sale 0 si TODOS los sabotajes fueron atrapados; 1 si alguno paso desapercibido.
Restaura siempre el codigo, incluso si se interrumpe: el original se guarda en
memoria antes de tocar nada y se reescribe en un `finally`.

LAS DOS DIRECCIONES
===================

Un sabotaje que la prueba atrapa solo demuestra la mitad. La otra mitad —que la
prueba pasa con el codigo intacto— la comprueba el paso final, que corre las dos
clases enteras sin ningun sabotaje aplicado.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'
MOTOR = PROYECTO / 'signos_sintomas' / 'alert_engine.py'
BOT = PROYECTO / 'signos_sintomas' / 'bot.py'

FRONTERAS = 'signos_sintomas.tests.test_alert_engine.FronterasDeUmbralTests'
BOT_TESTS = 'signos_sintomas.tests.test_bot.BotWhatsAppTests'


def prueba(clase, metodo):
    return f'{clase}.{metodo}'


# Cada entrada: (id, que rompe, archivo, texto viejo, texto nuevo, pruebas que
# DEBEN caer). Los textos multilinea se escriben con '\n' y el script los
# traduce al separador real del archivo.
SABOTAJES = [
    (
        'S01',
        "quitar 'fecaloide' de DRENAJES_ALTA (el sabotaje del 07/09)",
        MOTOR,
        "DRENAJES_ALTA  = ('purulento', 'fecaloide')",
        "DRENAJES_ALTA  = ('purulento',)",
        [prueba(FRONTERAS, 'test_drenaje_fecaloide_crea_fuga_alta')],
    ),
    (
        'S02',
        'bajar el umbral de fiebre ALTA de 37.9 a 37.8',
        MOTOR,
        "TEMPERATURA_ALTA = Decimal('37.9')",
        "TEMPERATURA_ALTA = Decimal('37.8')",
        [prueba(FRONTERAS, 'test_temperatura_378_un_dia_no_crea_alerta')],
    ),
    (
        'S03',
        'subir el piso de la subfebricula de 37.5 a 37.6',
        MOTOR,
        "TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.5')",
        "TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.6')",
        [prueba(FRONTERAS, 'test_temperatura_375_dos_dias_crea_sepsis_media')],
    ),
    (
        'S04',
        'bajar el piso de la subfebricula de 37.5 a 37.4',
        MOTOR,
        "TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.5')",
        "TEMPERATURA_SUBFEBRICULA_MIN = Decimal('37.4')",
        [prueba(FRONTERAS, 'test_temperatura_374_dos_dias_no_crea_alerta')],
    ),
    (
        'S05',
        'que la Regla 1b mire tres dias hacia atras en vez de dos '
        '(contaria a traves de un dia sin reporte)',
        MOTOR,
        'for offset in range(DIAS_SUBFEBRICULA_PERSISTENTE):',
        'for offset in range(DIAS_SUBFEBRICULA_PERSISTENTE + 1):',
        [prueba(FRONTERAS, 'test_subfebricula_con_hueco_de_un_dia_no_crea_alerta')],
    ),
    (
        'S06',
        'borrar la guarda D8 de la Regla 3: un dia sin reporte deja de cortar '
        'el conteo de dias sin gases',
        MOTOR,
        'if not existe_registro:\n            break\n        if hubo_gases:',
        'if hubo_gases:',
        [prueba(FRONTERAS, 'test_gases_hueco_de_un_dia_corta_el_conteo')],
    ),
    (
        'S07',
        'bajar NAUSEAS_MEDIA_MIN de 3 a 2',
        MOTOR,
        'NAUSEAS_MEDIA_MIN = 3',
        'NAUSEAS_MEDIA_MIN = 2',
        [prueba(FRONTERAS, 'test_nauseas_dos_episodios_crea_baja')],
    ),
    (
        'S08',
        'subir NAUSEAS_MEDIA_MIN de 3 a 4',
        MOTOR,
        'NAUSEAS_MEDIA_MIN = 3',
        'NAUSEAS_MEDIA_MIN = 4',
        [prueba(FRONTERAS, 'test_nauseas_tres_episodios_crea_media')],
    ),
    (
        'S09',
        'bajar DIAS_NAUSEAS_ALTA de 4 a 3 (Regla 4e)',
        MOTOR,
        'DIAS_NAUSEAS_ALTA  = 4',
        'DIAS_NAUSEAS_ALTA  = 3',
        [prueba(FRONTERAS, 'test_nauseas_persistencia_tres_dias_no_escala_a_alta')],
    ),
    (
        'S10',
        'que la persistencia de nauseas (Regla 4d) salte los dias sin reporte '
        'en vez de cortar en ellos',
        MOTOR,
        'if not hubo_nauseas:\n            break',
        'hay_datos = RegistroDiario.objects.filter(\n'
        '            paciente=registro.paciente,\n'
        '            fecha_registro__date=dia_revisado,\n'
        '        ).exists()\n'
        '        if hay_datos and not hubo_nauseas:\n            break',
        [prueba(FRONTERAS, 'test_nauseas_hueco_de_un_dia_corta_la_persistencia')],
    ),
    (
        'S11',
        'subir el piso de MEDIA en la ventana POD 0-2 de EVA 7 a EVA 8',
        MOTOR,
        '(2,    5, 7, 9),',
        '(2,    5, 8, 9),',
        [
            prueba(FRONTERAS, 'test_dolor_pod2_eva7_crea_media'),
            prueba(FRONTERAS, 'test_matriz_de_ventanas_de_dolor'),
        ],
    ),
    (
        'S12',
        'bajar el piso de BAJA en la ventana POD 0-2 de EVA 5 a EVA 4',
        MOTOR,
        '(2,    5, 7, 9),',
        '(2,    4, 7, 9),',
        [
            prueba(FRONTERAS, 'test_dolor_pod2_eva4_no_crea_alerta'),
            prueba(FRONTERAS, 'test_matriz_de_ventanas_de_dolor'),
        ],
    ),
    (
        'S13',
        'bajar el piso de ALTA en la ventana POD 3-5 de EVA 8 a EVA 7',
        MOTOR,
        '(5,    4, 6, 8),',
        '(5,    4, 6, 7),',
        [prueba(FRONTERAS, 'test_matriz_de_ventanas_de_dolor')],
    ),
    (
        'S14',
        'bajar el piso de BAJA en la ventana POD 6+ de EVA 3 a EVA 2',
        MOTOR,
        '(None, 3, 5, 7),',
        '(None, 2, 5, 7),',
        [prueba(FRONTERAS, 'test_matriz_de_ventanas_de_dolor')],
    ),
    (
        'S15',
        'bajar DOLOR_DELTA_TENDENCIA de 3 a 2 (Regla 5b)',
        MOTOR,
        'DOLOR_DELTA_TENDENCIA = 3',
        'DOLOR_DELTA_TENDENCIA = 2',
        [prueba(FRONTERAS, 'test_dolor_tendencia_delta_dos_no_escala')],
    ),
    (
        'S16',
        'borrar la guarda D8 de la Regla 6: un dia sin reporte deja de cortar '
        'el conteo de dias sin tolerar liquidos',
        MOTOR,
        'if not existe_registro:\n            break\n        if toleraba:',
        'if toleraba:',
        [prueba(FRONTERAS, 'test_liquidos_hueco_de_un_dia_corta_el_conteo')],
    ),
    (
        'S17',
        'bajar DIAS_HINCHAZON_MUCHO_ALTA de 4 a 3 (Regla 7c)',
        MOTOR,
        'DIAS_HINCHAZON_MUCHO_ALTA = 4',
        'DIAS_HINCHAZON_MUCHO_ALTA = 3',
        [prueba(FRONTERAS, 'test_hinchazon_mucho_tres_dias_no_escala_a_alta')],
    ),
    (
        'S18',
        "menu del bot: la opcion 4 (purulento) pasa a registrar 'seroso'",
        BOT,
        "'4': 'purulento',",
        "'4': 'seroso',",
        [prueba(BOT_TESTS, 'test_menu_drenaje_opcion_4_registra_purulento')],
    ),
    (
        'S19',
        "menu del bot: la opcion 5 (fecaloide) pasa a registrar 'seroso'",
        BOT,
        "'5': 'fecaloide',",
        "'5': 'seroso',",
        [
            prueba(BOT_TESTS, 'test_menu_drenaje_opcion_5_registra_fecaloide'),
            prueba(BOT_TESTS, 'test_menu_drenaje_fecaloide_llega_hasta_la_alerta_alta'),
        ],
    ),
    (
        'S20',
        "menu del bot: la opcion 2 (hematico) pasa a registrar 'seroso'",
        BOT,
        "'2': 'hematico',",
        "'2': 'seroso',",
        [prueba(BOT_TESTS, 'test_menu_drenaje_opcion_2_registra_hematico')],
    ),
    (
        'S21',
        'menu del bot: las opciones 1 y 3 se intercambian',
        BOT,
        "'1': 'seroso',\n        '2': 'hematico',\n        '3': 'turbio',",
        "'1': 'turbio',\n        '2': 'hematico',\n        '3': 'seroso',",
        [
            prueba(BOT_TESTS, 'test_menu_drenaje_opcion_1_registra_seroso'),
            prueba(BOT_TESTS, 'test_menu_drenaje_opcion_3_registra_turbio'),
        ],
    ),
]


def separador_de(texto):
    return '\r\n' if '\r\n' in texto else '\n'


def correr_pruebas(etiquetas):
    """Corre las pruebas indicadas. Devuelve True si TODAS pasaron."""
    resultado = subprocess.run(
        [sys.executable, 'manage.py', 'test', *etiquetas, '--noinput'],
        cwd=PROYECTO,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    return resultado.returncode == 0, resultado.stderr


def main():
    originales = {MOTOR: MOTOR.read_text(encoding='utf-8'),
                  BOT: BOT.read_text(encoding='utf-8')}

    atrapados = []
    escapados = []

    print('=' * 78)
    print('SABOTAJES — cada uno debe hacer CAER su prueba')
    print('=' * 78)

    try:
        for ident, descripcion, archivo, viejo, nuevo, etiquetas in SABOTAJES:
            texto = originales[archivo]
            sep = separador_de(texto)
            viejo_real = sep.join(viejo.split('\n'))
            nuevo_real = sep.join(nuevo.split('\n'))

            ocurrencias = texto.count(viejo_real)
            if ocurrencias != 1:
                print(f'{ident}  ERROR DE ARNES: el texto a sabotear aparece '
                      f'{ocurrencias} veces, no 1. Sabotaje no aplicado.')
                escapados.append((ident, descripcion, 'arnes roto'))
                continue

            archivo.write_text(texto.replace(viejo_real, nuevo_real),
                               encoding='utf-8')
            paso, _ = correr_pruebas(etiquetas)
            archivo.write_text(texto, encoding='utf-8')

            if paso:
                print(f'{ident}  ESCAPO   — {descripcion}')
                print(f'      la prueba siguio en verde con el motor roto: '
                      f'{", ".join(e.split(".")[-1] for e in etiquetas)}')
                escapados.append((ident, descripcion, 'la prueba no cayo'))
            else:
                print(f'{ident}  atrapado — {descripcion}')
                atrapados.append(ident)
    finally:
        for archivo, texto in originales.items():
            archivo.write_text(texto, encoding='utf-8')

    print()
    print('=' * 78)
    print('LA OTRA DIRECCION — con el codigo intacto, las pruebas deben pasar')
    print('=' * 78)
    paso_limpio, salida = correr_pruebas([FRONTERAS, BOT_TESTS])
    print('en verde' if paso_limpio else 'EN ROJO — revisar:\n' + salida[-3000:])

    print()
    print('=' * 78)
    print(f'{len(atrapados)} de {len(SABOTAJES)} sabotajes atrapados.')
    for ident, descripcion, motivo in escapados:
        print(f'  ESCAPO {ident} ({motivo}): {descripcion}')
    print('=' * 78)

    return 0 if (not escapados and paso_limpio) else 1


if __name__ == '__main__':
    sys.exit(main())
