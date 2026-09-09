"""Verificación de SEC-02 — 09/09/2026.

QUÉ COMPRUEBA
=============

Que las pruebas del bloqueo de acceso **pueden ponerse en rojo**. Revierte la
corrección de cuatro maneras distintas y exige que caiga la prueba que la
protege.

POR QUÉ HIZO FALTA, Y NO ERA UN TRÁMITE
========================================

En su primera corrida **dos de las cuatro reversiones escaparon**, y las dos
por el mismo defecto: pruebas verdes por un motivo distinto del que decían
medir.

  · **R3.** El ayudante hacía `range(settings.AXES_FAILURE_LIMIT)`. Al subir
    el límite a 500, la prueba hacía 500 intentos y seguía bloqueando: **se
    adaptaba sola al sabotaje**. Ahora el número va fijo, y que el límite
    configurado siga siendo pequeño lo comprueba una aserción aparte.

  · **R4.** Comparaba las dos formas de resolver la IP con
    `TRUST_RAILWAY_PROXY=False`, donde **ambas devuelven `REMOTE_ADDR`**.
    Coincidían aunque axes no estuviera usando la función del proyecto. Ahora
    la prueba declara el proxy de confianza, que es el único caso en el que
    las dos implementaciones pueden divergir.

Es exactamente el patrón que persigue la ficha **D16**, encontrado esta vez en
pruebas escritas hoy mismo. De ahí que esto se corra siempre y no solo cuando
algo parece sospechoso.

CÓMO SE USA
===========

    python proceso/verificaciones/2026-09-09_verificacion_sec02.py

Sale 0 si las cuatro reversiones caen; 1 si alguna escapa. Restaura siempre
`settings.py`, incluso si se interrumpe.
"""
import io
import subprocess
import sys
from pathlib import Path

RAIZ = Path(r'C:\Users\león\Documents\ProyectoLeonAlejo\Registro_Post_Quirurgico')
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'
PY = str(RAIZ / '.venv' / 'Scripts' / 'python.exe')
SETTINGS = PROYECTO / 'Registro_Post_Quirurgico' / 'settings.py'
CLASE = 'home.tests.BloqueoDeAccesoTests'

REVERSIONES = [
    ('R1', 'volver al defecto de axes: bloquear SOLO por IP (el hallazgo)',
     "AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]",
     "AXES_LOCKOUT_PARAMETERS = ['ip_address']",
     [f'{CLASE}.test_los_fallos_de_otro_usuario_no_bloquean_al_medico',
      f'{CLASE}.test_la_configuracion_no_vuelve_a_bloquear_solo_por_ip']),
    ('R2', 'bloquear solo por usuario: la cuenta se cierra desde cualquier IP',
     "AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]",
     "AXES_LOCKOUT_PARAMETERS = ['username']",
     [f'{CLASE}.test_el_bloqueo_no_alcanza_a_la_misma_cuenta_desde_otra_ip']),
    ('R3', 'subir el limite: deja de bloquear a quien ataca la cuenta',
     'AXES_FAILURE_LIMIT     = 5',
     'AXES_FAILURE_LIMIT     = 500',
     [f'{CLASE}.test_el_bloqueo_sigue_existiendo_para_quien_lo_provoca']),
    ('R4', 'axes deja de usar la IP del proyecto y vuelve a la suya',
     "AXES_CLIENT_IP_CALLABLE = 'home.ip_cliente._get_client_ip'",
     "AXES_CLIENT_IP_CALLABLE = None",
     [f'{CLASE}.test_axes_usa_la_misma_ip_que_el_rate_limit_del_formulario']),
]


def correr(etiquetas):
    r = subprocess.run([PY, 'manage.py', 'test', *etiquetas, '--noinput'],
                       cwd=PROYECTO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.returncode == 0


print('=' * 74)
print('¿PUEDEN CAER LAS PRUEBAS DE SEC-02?')
print('=' * 74)

original = io.open(SETTINGS, encoding='utf-8', newline='').read()
escaparon = []
try:
    for ident, desc, viejo, nuevo, etiquetas in REVERSIONES:
        if original.count(viejo) != 1:
            print(f'  {ident}  ARNES ROTO: el texto aparece {original.count(viejo)} veces')
            escaparon.append(ident)
            continue
        io.open(SETTINGS, 'w', encoding='utf-8', newline='').write(
            original.replace(viejo, nuevo))
        paso = correr(etiquetas)
        io.open(SETTINGS, 'w', encoding='utf-8', newline='').write(original)
        if paso:
            print(f'  {ident}  ESCAPO   — {desc}')
            escaparon.append(ident)
        else:
            print(f'  {ident}  atrapada — {desc}')
finally:
    io.open(SETTINGS, 'w', encoding='utf-8', newline='').write(original)

print()
print('LA OTRA DIRECCIÓN — con la corrección puesta, deben pasar')
print('  ' + ('en verde' if correr([CLASE]) else 'EN ROJO'))
print('=' * 74)
print(f'{len(REVERSIONES) - len(escaparon)} de {len(REVERSIONES)} atrapadas.')
if escaparon:
    print(f'  ESCAPARON: {escaparon}')
print('=' * 74)
sys.exit(1 if escaparon else 0)
