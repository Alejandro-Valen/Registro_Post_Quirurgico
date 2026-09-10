"""Verificación de las pruebas de caracterización de BE-08 y BE-09 — 09/09/2026.

QUÉ COMPRUEBA, Y POR QUÉ ES DISTINTO DE LOS OTROS ARNESES
==========================================================

Las pruebas de `CaracterizacionBE08yBE09Tests` **no pueden nacer en rojo**:
congelan un comportamiento que ya existe en vez de denunciar un defecto. Es el
caso que `CONTRIBUTING.md` contempla — *«cuando una prueba no pueda nacer en
rojo, se dice en su docstring»*— y así está dicho allí.

Pero eso no las libra de justificarse. Una prueba de caracterización que pasara
igual con el comportamiento cambiado no estaría fijando nada, y sería peor que
no tenerla: daría la impresión de que hay una decisión protegida donde no la
hay. Así que se comprueba lo que sí se puede comprobar: **que cambiar el
comportamiento las hace caer**.

Los dos cambios de abajo son, además, las dos lecturas alternativas que van a la
reunión con el médico. Verlas caer demuestra que las pruebas distinguen una
lectura de la otra, que es exactamente su función.

POR QUÉ ESTO ES UN ARCHIVO Y NO UN COMANDO SUELTO
==================================================

Porque el 09/09/2026, al improvisar esta misma comprobación en línea, el proceso
murió entre el sabotaje y la restauración y **dejó `alert_engine.py` con una
constante clínica cambiada**. No llegó a git, pero pudo. Todos los arneses de
`proceso/verificaciones/` restauran en un `finally`; el de usar y tirar no lo
tenía.

CÓMO SE USA
===========

    python proceso/verificaciones/2026-09-09_verificacion_caracterizacion_d10.py

Sale 0 si los dos cambios hacen caer las pruebas; 1 si alguno pasa desapercibido.
Restaura `alert_engine.py` siempre.
"""

import io
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'
MOTOR = PROYECTO / 'signos_sintomas' / 'alert_engine.py'
CLASE = 'signos_sintomas.tests.test_alert_engine.CaracterizacionBE08yBE09Tests'

CAMBIOS = [
    (
        'BE-08',
        'aplicar la otra lectura: que la tendencia NO escale desde «ninguna '
        'alerta» (lo que dice la regla escrita leída al pie de la letra)',
        "            severidad_base = severidad_por_tabla or 'BAJA'\n"
        "            siguiente_nivel = {'BAJA': 'MEDIA', 'MEDIA': 'ALTA', 'ALTA': 'ALTA'}\n"
        "            severidad_por_tendencia = siguiente_nivel[severidad_base]",
        "            siguiente_nivel = {None: 'BAJA', 'BAJA': 'MEDIA',\n"
        "                               'MEDIA': 'ALTA', 'ALTA': 'ALTA'}\n"
        "            severidad_por_tendencia = siguiente_nivel[severidad_por_tabla]",
    ),
    (
        'BE-09',
        'aplicar la otra lectura: que un día con reporte pero SIN el dato de '
        'líquidos corte el conteo, por coherencia con la ficha D8',
        "        existe_registro = RegistroDiario.objects.filter(\n"
        "            paciente=registro.paciente,\n"
        "            fecha_registro__date=dia_revisado,\n"
        "        ).exists()\n"
        "        if not existe_registro:\n"
        "            break\n"
        "        if toleraba:",
        "        existe_registro = RegistroDiario.objects.filter(\n"
        "            paciente=registro.paciente,\n"
        "            fecha_registro__date=dia_revisado,\n"
        "            tolero_liquidos__isnull=False,\n"
        "        ).exists()\n"
        "        if not existe_registro:\n"
        "            break\n"
        "        if toleraba:",
    ),
]


def separador_de(texto):
    return '\r\n' if '\r\n' in texto else '\n'


def correr():
    return subprocess.run(
        [sys.executable, 'manage.py', 'test', CLASE, '--noinput'],
        cwd=PROYECTO, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    ).returncode == 0


def main():
    original = io.open(MOTOR, encoding='utf-8', newline='').read()
    sep = separador_de(original)
    escaparon = []

    print('=' * 78)
    print('¿FIJAN ALGO LAS PRUEBAS DE CARACTERIZACIÓN?')
    print('=' * 78)

    if not correr():
        print('  !! las pruebas ya están en rojo sin tocar nada; abortando')
        return 1

    try:
        for ident, descripcion, viejo, nuevo in CAMBIOS:
            viejo_real = sep.join(viejo.split('\n'))
            nuevo_real = sep.join(nuevo.split('\n'))
            if original.count(viejo_real) != 1:
                print(f'  {ident}  ARNÉS ROTO: el texto aparece '
                      f'{original.count(viejo_real)} veces, no 1')
                escaparon.append(ident)
                continue
            io.open(MOTOR, 'w', encoding='utf-8', newline='').write(
                original.replace(viejo_real, nuevo_real))
            paso = correr()
            io.open(MOTOR, 'w', encoding='utf-8', newline='').write(original)
            if paso:
                print(f'  {ident}  ESCAPÓ   — {descripcion}')
                escaparon.append(ident)
            else:
                print(f'  {ident}  atrapado — {descripcion}')
    finally:
        # Pase lo que pase, el motor clínico queda como estaba.
        io.open(MOTOR, 'w', encoding='utf-8', newline='').write(original)

    print()
    print('  restaurado -> ' + ('verde' if correr() else 'ROJO'))
    print('=' * 78)
    print(f'{len(CAMBIOS) - len(escaparon)} de {len(CAMBIOS)} cambios atrapados.')
    if escaparon:
        print(f'  ESCAPARON: {escaparon}')
    print('=' * 78)
    return 1 if escaparon else 0


if __name__ == '__main__':
    sys.exit(main())
