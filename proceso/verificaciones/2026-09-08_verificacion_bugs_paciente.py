"""Verificación del loop de bugs del paciente — 08/09/2026.

QUÉ COMPRUEBA
=============

Que cada prueba de regresión de este loop **puede ponerse en rojo**. No repite
la suite: revierte cada arreglo, uno a uno, y exige que la prueba que lo
protege CAIGA. Una prueba que sigue verde con el bug de vuelta no está
protegiendo nada — es la lección de la ficha D16 aplicada a las correcciones.

Es el hermano de `2026-09-08_verificacion_umbrales.py`, con una diferencia: allí
se saboteaban umbrales que ya existían; aquí se revierten arreglos recién
escritos, que es donde más fácil es engañarse.

POR QUÉ IMPORTA EN ESTE LOOP EN CONCRETO
=========================================

Porque ya falló una vez, el mismo día. La palabra de auxilio se implementó
comparando el mensaje COMPLETO contra la lista (`texto in _PALABRAS_AUXILIO`),
y con eso el caso que originó la decisión —"estoy sangrando mucho, necesito
ayuda"— seguía sin arreglarse. Las pruebas escritas en ese momento pasaban. Lo
destapó volver a ejecutar la reproducción, no leer el código.

CÓMO SE USA
===========

    python proceso/verificaciones/2026-09-08_verificacion_bugs_paciente.py

Sale 0 si TODOS los arreglos están protegidos; 1 si alguno se puede revertir sin
que caiga nada. Restaura siempre el código, incluso si se interrumpe.

LAS DOS DIRECCIONES
===================

La otra mitad —que las pruebas pasan con el código bueno— la comprueba el paso
final, que corre las cinco clases enteras sin ninguna reversión aplicada.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'
BOT = PROYECTO / 'signos_sintomas' / 'bot.py'
MOTOR = PROYECTO / 'signos_sintomas' / 'alert_engine.py'
CREAR = PROYECTO / 'signos_sintomas' / 'management' / 'commands' / 'crear_checkins_diarios.py'
CERRAR = PROYECTO / 'signos_sintomas' / 'management' / 'commands' / 'cerrar_checkins_vencidos.py'
PANEL = PROYECTO / 'signos_sintomas' / 'templatetags' / 'panel_admin.py'
VISTAS = PROYECTO / 'home' / 'views.py'

BOT_TESTS = 'signos_sintomas.tests.test_bot.BugsDelPacienteTests'
CMD_TESTS = 'signos_sintomas.tests.test_commands.ConsentimientoRevocadoTests'
PANEL_TESTS = 'signos_sintomas.tests.test_admin.TableroQueNoSeContradiceTests'
HOME_TESTS = 'home.tests.AutorizacionHabeasDataTests'
PRIVACIDAD = 'signos_sintomas.tests.test_bot.BotWhatsAppTests'

ARCHIVOS = [BOT, MOTOR, CREAR, CERRAR, PANEL, VISTAS]


# (id, qué se revierte, archivo, viejo, nuevo, pruebas que DEBEN caer)
REVERSIONES = [
    (
        'R01',
        'el parser de temperatura vuelve a truncar en silencio (DB-02)',
        BOT,
        "match = re.fullmatch(r'[^\\d]*(\\d{2}(?:\\.\\d{1,2})?)[^\\d]*', limpio)",
        "match = re.search(r'\\d{2}(?:[.,]\\d)?', limpio)",
        [f'{BOT_TESTS}.test_temperatura_sin_separador_se_rechaza',
         f'{BOT_TESTS}.test_temperatura_ambigua_pide_de_nuevo_y_no_crea_registro'],
    ),
    (
        'R02',
        'el bot deja de decir lo que entendió (UX-B05)',
        BOT,
        "return _eco_temperatura(conv.temp_temperatura) + MSG_PREGUNTA_DOLOR",
        "return MSG_PREGUNTA_DOLOR",
        [f'{BOT_TESTS}.test_el_bot_devuelve_la_temperatura_que_anoto',
         f'{BOT_TESTS}.test_el_eco_va_antes_de_que_exista_ninguna_alerta'],
    ),
    (
        'R03',
        'el eco se mueve al cierre, junto al mensaje de severidad — la regla '
        'del Bloque B que dice que el paciente no ve los valores que la '
        'dispararon',
        BOT,
        "    if 'ALTA' in severidades:\n        return MSG_CIERRE_ALERTA_ALTA",
        "    if 'ALTA' in severidades:\n        return MSG_CIERRE_ALERTA_ALTA + ' 38.5'",
        [f'{BOT_TESTS}.test_el_cierre_no_repite_los_valores_que_dispararon_la_alerta',
         f'{PRIVACIDAD}.test_alerta_no_se_muestra_al_paciente'],
    ),
    (
        'R04',
        'la temperatura vuelve a ser obligatoria: sin termómetro se pierde el '
        'turno entero (UX-B04)',
        BOT,
        "        if _es_salto(texto):\n            conv.temp_temperatura = None\n        else:\n            valor = _parse_temperatura(texto)",
        "        if False:\n            conv.temp_temperatura = None\n        else:\n            valor = _parse_temperatura(texto)",
        [f'{BOT_TESTS}.test_saltar_temperatura_deja_reportar_todo_lo_demas'],
    ),
    (
        'R05',
        'la Regla 1 vuelve a evaluar sin dato de temperatura (D20)',
        MOTOR,
        "    if registro.temperatura is None:\n        return []",
        "    if registro.temperatura is None:\n        registro.temperatura = Decimal('40.0')",
        [f'{BOT_TESTS}.test_sin_temperatura_no_se_evalua_la_regla_de_fiebre'],
    ),
    (
        'R06',
        'el dolor vuelve a empezar en 1: el paciente sin dolor no puede '
        'responder (D20)',
        BOT,
        "        valor = _parse_entero_rango(texto, *RANGOS_CLINICOS['dolor_eva'])",
        "        valor = _parse_entero_rango(texto, 1, 10)",
        [f'{BOT_TESTS}.test_dolor_cero_es_valido_y_no_alerta'],
    ),
    (
        'R07',
        'las náuseas pierden el techo: vuelve el 500 del webhook (DB-01)',
        BOT,
        "    minimo, maximo = RANGOS_CLINICOS['episodios_nauseas']\n    if not (minimo <= nauseas <= maximo):\n        return None, None",
        "    pass",
        [f'{BOT_TESTS}.test_nauseas_desmesuradas_se_rechazan_en_el_bot'],
    ),
    (
        'R08',
        'la palabra de auxilio deja de reconocerse (UX-B01)',
        BOT,
        "    if _es_auxilio(texto):",
        "    if False and _es_auxilio(texto):",
        [f'{BOT_TESTS}.test_auxilio_a_mitad_del_cuestionario_corta_y_alerta',
         f'{BOT_TESTS}.test_auxilio_fuera_del_cuestionario_tambien_alerta'],
    ),
    (
        'R09',
        'el auxilio vuelve a compararse contra el mensaje COMPLETO — el error '
        'real que se cometió al implementarlo, y que las pruebas de entonces '
        'no atrapaban',
        BOT,
        "    return bool(_RE_AUXILIO.search(_sin_acentos(texto.lower())))",
        "    return _sin_acentos(texto.strip().lower()) in _PALABRAS_AUXILIO",
        [f'{BOT_TESTS}.test_auxilio_a_mitad_del_cuestionario_corta_y_alerta'],
    ),
    (
        'R10',
        'el auxilio se dispara con cualquier síntoma, no con una palabra '
        'anunciada: el panel se llena de ruido',
        BOT,
        "_PALABRAS_AUXILIO = ('ayuda', 'auxilio', 'socorro', 'emergencia')",
        "_PALABRAS_AUXILIO = ('ayuda', 'auxilio', 'socorro', 'emergencia', 'no', 'mucho')",
        [f'{BOT_TESTS}.test_las_respuestas_normales_no_disparan_auxilio'],
    ),
    (
        'R11',
        'el bot vuelve a negar el turno de la tarde (BE-01)',
        BOT,
        "            otro = CheckInProgramado.objects.select_for_update().filter(",
        "            otro = CheckInProgramado.objects.none().filter(",
        [f'{BOT_TESTS}.test_el_turno_de_la_tarde_no_se_niega'],
    ),
    (
        'R12',
        'el cron vuelve a crear turnos sin mirar el consentimiento (D22)',
        CREAR,
        "pacientes = Paciente.objects.filter(activo=True, consentimiento_informado=True)",
        "pacientes = Paciente.objects.filter(activo=True)",
        [f'{CMD_TESTS}.test_sin_consentimiento_no_se_crean_turnos'],
    ),
    (
        'R13',
        'el cierre de turnos vuelve a generar SILENCIO sin consentimiento (D22)',
        CERRAR,
        "                if not checkin.paciente.consentimiento_informado:",
        "                if False:",
        [f'{CMD_TESTS}.test_revocar_no_genera_alertas_de_silencio'],
    ),
    (
        'R14',
        'el tablero deja de contar las alertas que no muestra (UX-P01)',
        PANEL,
        "    silencios_pendientes = pendientes.filter(tipo='SILENCIO').count()",
        "    silencios_pendientes = 0",
        [f'{PANEL_TESTS}.test_una_alta_de_silencio_se_cuenta_aunque_no_este_en_la_lista'],
    ),
    (
        'R15',
        'el paciente con seguimiento detenido vuelve a desaparecer del panel (D22)',
        PANEL,
        "    detenidos = pacientes.filter(activo=True, consentimiento_informado=False)",
        "    detenidos = pacientes.none()",
        [f'{PANEL_TESTS}.test_el_paciente_con_seguimiento_detenido_no_desaparece'],
    ),
    (
        'R16',
        'el formulario público vuelve a guardar sin autorización (SEC-03)',
        VISTAS,
        "            if not autorizo:\n                error_autorizacion = True\n            elif nombre and telefono and mensaje:",
        "            if nombre and telefono and mensaje:",
        [f'{HOME_TESTS}.test_sin_la_casilla_no_se_guarda_nada'],
    ),
    (
        'R17',
        'la autorización deja de poder demostrarse: se recoge sin fecharla (D23)',
        VISTAS,
        "                    fecha_autorizacion=timezone.now(),",
        "                    fecha_autorizacion=None,",
        [f'{HOME_TESTS}.test_con_la_casilla_se_guarda_y_queda_la_prueba'],
    ),
]


def separador_de(texto):
    return '\r\n' if '\r\n' in texto else '\n'


def correr_pruebas(etiquetas):
    resultado = subprocess.run(
        [sys.executable, 'manage.py', 'test', *etiquetas, '--noinput'],
        cwd=PROYECTO, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )
    return resultado.returncode == 0, resultado.stderr


def main():
    originales = {ruta: ruta.read_text(encoding='utf-8') for ruta in ARCHIVOS}
    atrapadas, escapadas = [], []

    print('=' * 78)
    print('REVERSIONES — revertir cada arreglo debe hacer CAER su prueba')
    print('=' * 78)

    try:
        for ident, descripcion, archivo, viejo, nuevo, etiquetas in REVERSIONES:
            texto = originales[archivo]
            sep = separador_de(texto)
            viejo_real = sep.join(viejo.split('\n'))
            nuevo_real = sep.join(nuevo.split('\n'))

            ocurrencias = texto.count(viejo_real)
            if ocurrencias != 1:
                print(f'{ident}  ERROR DE ARNES: el texto aparece {ocurrencias} '
                      f'veces, no 1. Reversión no aplicada.')
                escapadas.append((ident, descripcion, 'arnés roto'))
                continue

            archivo.write_text(texto.replace(viejo_real, nuevo_real),
                               encoding='utf-8')
            paso, _ = correr_pruebas(etiquetas)
            archivo.write_text(texto, encoding='utf-8')

            if paso:
                print(f'{ident}  ESCAPO   — {descripcion}')
                print(f'      siguieron en verde: '
                      f'{", ".join(e.split(".")[-1] for e in etiquetas)}')
                escapadas.append((ident, descripcion, 'la prueba no cayó'))
            else:
                print(f'{ident}  atrapada — {descripcion}')
                atrapadas.append(ident)
    finally:
        for archivo, texto in originales.items():
            archivo.write_text(texto, encoding='utf-8')

    print()
    print('=' * 78)
    print('LA OTRA DIRECCIÓN — con el código bueno, las pruebas deben pasar')
    print('=' * 78)
    paso_limpio, salida = correr_pruebas(
        [BOT_TESTS, CMD_TESTS, PANEL_TESTS, HOME_TESTS,
         'signos_sintomas.tests.test_models.RangosClinicosEnLaBaseTests'])
    print('en verde' if paso_limpio else 'EN ROJO — revisar:\n' + salida[-3000:])

    print()
    print('=' * 78)
    print(f'{len(atrapadas)} de {len(REVERSIONES)} reversiones atrapadas.')
    for ident, descripcion, motivo in escapadas:
        print(f'  ESCAPO {ident} ({motivo}): {descripcion}')
    print('=' * 78)

    return 0 if (not escapadas and paso_limpio) else 1


if __name__ == '__main__':
    sys.exit(main())
