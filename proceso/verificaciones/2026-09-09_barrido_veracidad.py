"""Barrido de veracidad de la documentación — 09/09/2026.

QUÉ COMPRUEBA
=============

Que lo que la documentación **afirma** coincide con lo que el repositorio **es**.
No revisa estilo ni redacción: solo hechos comprobables con un comando.

POR QUÉ EXISTE
==============

En dos días de trabajo se tropezó con **cinco afirmaciones falsas**, todas por
casualidad, ninguna por haberlas buscado:

1. El `cd` de `CLAUDE.md` no funcionaba desde la raíz del repositorio (REPO-14).
2. El intérprete del proyecto (`.venv/`) no estaba escrito en ningún sitio, y el
   ROADMAP afirmaba lo contrario ("hoy todo corre en el Python global").
3. El índice de `decisiones_correccion_auditoria.md` se quedó en D15 mientras el
   cuerpo ya tenía D16, D17 y D18.
4. "La lista completa de los 18 sabotajes": el guion decía que estaba en el
   informe y el informe decía que estaba en el guion. No estaba en ninguno.
5. El "próximo paso exacto" apuntaba a **34 hallazgos del linter que no
   existen**: `ruff` con la configuración que bloquea la CI pasa limpio desde el
   07/09/2026.

El quinto es el que explica por qué esto merece un script. Un documento que
miente **no lo atrapa ninguna prueba**, y cuesta más que un bug: el bug lo caza
la suite, la mentira se la cree quien retoma el proyecto y gasta media sesión en
trabajo que no existe.

LA COMPROBACIÓN QUE MÁS IMPORTA
================================

La número 4 de abajo: que **los umbrales de `docs/reglas_clinicas.md` y las
constantes de `alert_engine.py` digan lo mismo**. Los dos lados se derivan de su
fuente —no hay una tercera copia dentro de este script—, así que si alguien
mueve un umbral en el código y no lo escribe en el documento, esto se pone rojo.

En un sistema que clasifica señales de alarma médicas, un documento clínico
desactualizado no es un problema de documentación: es la referencia con la que
alguien va a decidir si una regla está bien.

CÓMO SE USA
===========

    python proceso/verificaciones/2026-09-09_barrido_veracidad.py

Sale 0 si todo lo que la documentación afirma es cierto; 1 si algo no lo es.
No corrige nada: reporta.

VERIFICADO EN LAS DOS DIRECCIONES (09/09/2026)
===============================================

Un barrido que solo se ha visto en verde no vale nada — es la ficha **D16**. Se
rompió una afirmación de cada tipo y se comprobó que el barrido cae:

    1 rutas      citar `docs/inventado_no_existe.md`      → atrapado
    2 conteo     insignia del README a 999 pruebas        → atrapado
    3 ci         «cinco comprobaciones» en CONTRIBUTING   → atrapado
    4 umbrales   TEMPERATURA_ALTA de 37.9 a 38.4          → atrapado
    5 fichas     quitar D23 del índice                    → atrapado
    6 commits    citar el commit `abc1234`                → atrapado
    7 comandos   `cd` a una carpeta que no existe         → atrapado

    7 de 7, y verde otra vez al restaurar.

LO QUE ESTE BARRIDO NO PUEDE COMPROBAR
=======================================

Solo mira hechos mecánicos. **No detecta una afirmación que sea falsa por su
contenido y no por sus números** — por ejemplo, «el próximo paso son los 34
hallazgos del linter» cuando esos hallazgos no existen. Ese hueco se cerró a
mano el 09/09/2026, y para el resto no hay sustituto: alguien tiene que leer.

Dicho de otro modo: esto atrapa la documentación que **envejece**, no la que
**nació equivocada**.

CORRER ESTO EN LOCAL ES MÁS DÉBIL QUE EN LA CI
===============================================

La comprobación 6 —que los commits citados existan— pregunta en realidad
**«¿puede verificar esto cualquiera que clone el repositorio?»**. La copia de
quien trabaja a diario conserva objetos que ya no son alcanzables desde ninguna
rama, así que en local pasan citas que en un clon limpio no existirían.

Pasó en la primera corrida: dos commits del 31/07/2026 estaban verdes en local
y rojos en el runner. **La respuesta de la CI es la que vale.**
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# La consola de Windows abre en cp1252 y este informe lleva flechas y comillas
# angulares. Sin esto el barrido muere al imprimir su primer hallazgo, que es la
# peor forma posible de fallar: parece que no encontró nada.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RAIZ = Path(__file__).resolve().parents[2]
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'

fallos = []
avisos = []

# Bases desde las que Django resuelve rutas cortas: cada app y cada carpeta de
# plantillas. Se calculan, no se listan a mano, para que una app nueva entre sola.
RAICES_DE_APP = [PROYECTO] + [
    carpeta for carpeta in PROYECTO.iterdir()
    if carpeta.is_dir() and (carpeta / '__init__.py').exists()
]
RAICES_DE_APP += [p for p in PROYECTO.rglob('templates') if p.is_dir()]


def titulo(n, texto):
    print()
    print('=' * 78)
    print(f'{n} · {texto}')
    print('=' * 78)


def falla(comprobacion, detalle):
    fallos.append((comprobacion, detalle))
    print(f'   FALLA  {detalle}')


def aviso(detalle):
    avisos.append(detalle)
    print(f'   aviso  {detalle}')


def ok(detalle):
    print(f'   ok     {detalle}')


# Una afirmación anclada a una fecha, a un PR o a un commit es un REGISTRO
# HISTÓRICO: «PR #5 (31/07/2026): cinco comprobaciones» sigue siendo verdad hoy
# y debe seguir diciéndolo. Una cifra sin ancla temporal —«la CI corre nueve
# comprobaciones»— es una afirmación sobre el presente y tiene que ser cierta
# ahora.
#
# Este discriminador es lo que separa un barrido que se usa de uno que se ignora:
# sin él, 26 de los 27 hallazgos de la primera corrida eran historia correcta.
ANCLA_TEMPORAL = re.compile(
    r'\d{2}/\d{2}/\d{4}'      # 31/07/2026
    r'|PR #\d+'                # PR #5
    r'|`[0-9a-f]{7}`'          # `5b40c01`
    r'|Sprint \d',             # Sprint 6
    re.I,
)

# Commits citados que YA NO ESTÁN en la historia alcanzable, con su razón.
#
# Este hueco lo destapó la primera corrida en la CI, y no se veía en local: mi
# copia conservaba los objetos, así que el barrido pasaba en mi máquina y caía
# en el runner. La comprobación de la CI es la que vale — «¿puede verificar esto
# cualquiera que clone el repositorio?»— y en local es más débil por definición.
COMMITS_HISTORICOS = {
    '36dc751': 'rotura deliberada 1 de 2 del 31/07/2026, para comprobar que la '
               'CI podía ponerse en rojo. Se borró de la rama al terminar, así '
               'que no es alcanzable desde ninguna referencia. La evidencia de '
               'aquel día NO es el commit: son los enlaces a las corridas de '
               'GitHub Actions, que sí son permanentes.',
    'e5630b8': 'rotura deliberada 2 de 2 del mismo día y por la misma razón.',
}

# Rutas que la documentación cita a propósito aunque ya no existan, con su razón
# —mismo criterio que `.gitleaksignore`: una lista de excepciones sin razones es
# una lista que crece hasta que no protege nada.
RUTAS_HISTORICAS = {
    'signos_sintomas/tests.py':
        'existió hasta el 10/08/2026; se partió en el paquete tests/ (PR #12). '
        'Los documentos que lo nombran describen ese cambio.',
    'Registro_Post_Quirurgico/signos_sintomas/tests.py':
        'la misma, citada con el prefijo del paquete.',
}


def documentos():
    """Todos los .md sobre los que tiene sentido comprobar algo.

    Se excluye `docs/auditoria_literatura/`: son transcripciones y análisis de
    PDFs externos, no afirmaciones sobre este repositorio.
    """
    for ruta in RAIZ.rglob('*.md'):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(('.venv/', 'docs/auditoria_literatura/')):
            continue
        yield ruta


def documentos_de_estado():
    """Los que describen el PRESENTE, y por tanto tienen que ser ciertos hoy.

    La ficha **D18** ya separó el repositorio en dos: `docs/` es producto y
    `proceso/` es el cuaderno del equipo. Esa separación resuelve exactamente
    esta pregunta: **un documento de `proceso/` describe el momento en que se
    escribió**, y «la CI corre cinco comprobaciones» en una entrada de julio es
    verdad histórica, no un error que corregir. Reescribirlo falsificaría el
    registro.

    Por eso las comprobaciones de estado solo miran producto. Las que valen
    para todo —que las rutas y los commits citados existan— siguen recorriendo
    el repositorio entero.
    """
    for ruta in documentos():
        if not ruta.relative_to(RAIZ).as_posix().startswith('proceso/'):
            yield ruta


# ---------------------------------------------------------------------------
# 1 · Las rutas que cita la documentación existen
# ---------------------------------------------------------------------------
def comprobar_rutas():
    titulo(1, 'Las rutas citadas en la documentación existen')

    patron = re.compile(r'`([^`\s]+\.(?:md|py|yml|yaml|toml|html|txt|bat|cfg))`')
    citadas = {}
    for doc in documentos():
        for m in patron.finditer(doc.read_text(encoding='utf-8')):
            ruta = m.group(1)
            if '/' not in ruta:          # nombres sueltos, no rutas
                continue
            citadas.setdefault(ruta, set()).add(doc.relative_to(RAIZ).as_posix())

    rotas = 0
    for ruta, quienes in sorted(citadas.items()):
        if '*' in ruta:          # `docs/decisiones_*.md` es un patrón, no una ruta
            continue
        # `lstrip('./')` NO sirve aquí: borra también la primera letra de
        # `.github/...`. Se quita solo el prefijo `./` si lo lleva.
        limpia = ruta[2:] if ruta.startswith('./') else ruta

        if limpia in RUTAS_HISTORICAS:
            continue

        # Una ruta se da por buena si resuelve desde la raíz, desde el paquete
        # Django, desde la carpeta del documento que la cita —que es como se leen
        # los enlaces de un README—, o desde cualquier app o carpeta de
        # plantillas: `tests/__init__.py` y `admin/base_site.html` se citan así,
        # sin el prefijo de su app, y son rutas correctas.
        candidatas = [RAIZ / limpia, PROYECTO / limpia]
        candidatas += [RAIZ / Path(quien).parent / limpia for quien in quienes]
        candidatas += [base / limpia for base in RAICES_DE_APP]
        if any(c.exists() for c in candidatas):
            continue

        rotas += 1
        falla('rutas', f'{ruta}  — citada en: {", ".join(sorted(quienes))}')
    if not rotas:
        ok(f'{len(citadas)} rutas citadas, todas existen')


# ---------------------------------------------------------------------------
# 2 · El conteo de pruebas publicado es el real
#
# LA DISTINCIÓN QUE HACE ÚTIL ESTA COMPROBACIÓN: la mayoría de las cifras que
# aparecen en la documentación son HISTORIA legítima — "PR #12, 340 tests OK"
# es correcto para agosto y debe seguir diciéndolo. Marcarlas todas produce
# cincuenta falsos positivos, y un barrido con cincuenta falsos positivos se
# ignora, que es peor que no tenerlo.
#
# Se comprueban dos cosas distintas:
#
#   a) Los ESCAPARATES —los sitios que describen el presente— deben decir el
#      número exacto de hoy.
#   b) NINGÚN documento puede citar una cifra MAYOR que la real, en ningún
#      contexto: una suite no puede haber tenido más pruebas en el pasado que
#      ahora sin que alguien las haya borrado. Si aparece, o la cifra es falsa
#      o se perdieron pruebas por el camino. Las dos cosas hay que mirarlas.
# ---------------------------------------------------------------------------
def comprobar_conteo_de_pruebas():
    titulo(2, 'El número de pruebas que publica la documentación es el real')

    guion = (
        "import django, os; "
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', "
        "'Registro_Post_Quirurgico.settings'); django.setup(); "
        "from django.test.runner import DiscoverRunner; "
        "print(DiscoverRunner(verbosity=0).build_suite([]).countTestCases())"
    )
    resultado = subprocess.run(
        [sys.executable, '-c', guion], cwd=PROYECTO,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    if resultado.returncode != 0:
        aviso('no se pudo contar la suite: ' + resultado.stderr.strip()[-200:])
        return

    real = int(resultado.stdout.strip().splitlines()[-1])
    print(f'   la suite tiene {real} pruebas')

    # (a) Los escaparates del presente.
    readme = (RAIZ / 'README.md').read_text(encoding='utf-8')
    roadmap = (RAIZ / 'ROADMAP_MONITOREO_POSQUIRURGICO.md').read_text(encoding='utf-8')
    escaparates = [
        ('insignia del README', re.search(r'badge/pruebas-(\d+)-', readme)),
        ('tabla del README', re.search(r'\|\s*\*\*Suite\*\*\s*\|\s*(\d+) pruebas', readme)),
        ('cabecera del ROADMAP', re.search(r'(\d+) tests OK\)', roadmap)),
    ]
    for nombre, m in escaparates:
        if m is None:
            aviso(f'no se encontró el escaparate: {nombre}')
        elif int(m.group(1)) != real:
            falla('conteo', f'{nombre} dice {m.group(1)} y la suite tiene {real}')
        else:
            ok(f'{nombre} dice {real} — correcto')

    # (b) Nadie puede citar una cifra mayor que la real.
    patron = re.compile(r'(\d{3})\s*(?:tests?|pruebas)\b', re.I)
    imposibles = 0
    for doc in documentos():
        rel = doc.relative_to(RAIZ).as_posix()
        texto = doc.read_text(encoding='utf-8')
        for m in patron.finditer(texto):
            if int(m.group(1)) > real:
                imposibles += 1
                contexto = ' '.join(texto[max(0, m.start() - 70):m.end() + 10].split())
                falla('conteo', f'{rel} cita {m.group(1)} pruebas, MÁS que las {real} que existen  → …{contexto}…')
    if not imposibles:
        ok('ningún documento cita más pruebas de las que existen')


# ---------------------------------------------------------------------------
# 3 · Las comprobaciones que la documentación atribuye a la CI existen
#
# POR QUÉ ESTO MIRA ESCAPARATES Y NO PROSA. El primer intento escaneaba todos
# los documentos buscando «N comprobaciones» y descartaba las anclada a una
# fecha o a un PR. Falló en las dos direcciones a la vez:
#
#   · marcaba historia correcta («la CI pasa de cinco a siete», de agosto);
#   · y **se le escapó la única que importaba** — `CLAUDE.md` decía «corre
#     nueve comprobaciones» en presente cuando ya eran diez, porque la viñeta
#     VECINA llevaba una fecha y la ventana de 140 caracteres la alcanzaba.
#
# Un falso negativo en la comprobación que más se quiere es peor que no
# tenerla, porque además tranquiliza. Distinguir «afirmación sobre hoy» de
# «registro histórico» dentro de prosa libre no es mecanizable de forma
# fiable, así que se nombran los escaparates: las frases concretas que
# describen el presente. Si alguien escribe una nueva, la añade aquí.
# ---------------------------------------------------------------------------
NO_SON_COMPROBACIONES = {
    'Traer el repositorio', 'Instalar Python', 'Instalar dependencias',
}

# (documento, expresión que captura el número escrito en presente)
ESCAPARATES_CI = [
    ('CLAUDE.md',
     r'`\.github/workflows/ci\.yml` corre \*\*(\w+)\s+comprobaciones\*\*'),
    ('CONTRIBUTING.md',
     r'La CI corre \*\*(\w+) comprobaciones\*\*'),
    ('docs/README.md',
     r'\*\*(\w+) comprobaciones\*\*'),
    ('.github/PULL_REQUEST_TEMPLATE.md',
     r'Las (\w+) comprobaciones de la CI'),
]

NUMEROS = {
    'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
    'once': 11, 'doce': 12,
}


def comprobar_ci():
    titulo(3, 'El número de comprobaciones de la CI que se publica es el real')

    ci = (RAIZ / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    pasos = re.findall(r'^      - name: (.+)$', ci, re.M)
    comprobaciones = [p.strip() for p in pasos
                      if p.strip() not in NO_SON_COMPROBACIONES]
    print(f'   la CI tiene {len(pasos)} pasos, de los cuales '
          f'{len(comprobaciones)} son comprobaciones:')
    for c in comprobaciones:
        print(f'      · {c}')

    for documento, expresion in ESCAPARATES_CI:
        ruta = RAIZ / documento
        if not ruta.exists():
            falla('ci', f'{documento} no existe y es un escaparate declarado')
            continue
        texto = ' '.join(ruta.read_text(encoding='utf-8').split())
        m = re.search(expresion, texto)
        if m is None:
            falla('ci', f'{documento}: no se encuentra la frase que dice cuántas comprobaciones tiene la CI — ¿se reescribió?')
            continue
        citado = NUMEROS.get(m.group(1).lower())
        if citado is None:
            falla('ci', f'{documento} dice "{m.group(1)}" y no es un número que este barrido sepa leer')
        elif citado != len(comprobaciones):
            falla('ci', f'{documento} dice "{m.group(1)} comprobaciones" y son {len(comprobaciones)}')
        else:
            ok(f'{documento} dice "{m.group(1)} comprobaciones" — correcto')

# ---------------------------------------------------------------------------
# 4 · Los umbrales del documento clínico son los del motor
# ---------------------------------------------------------------------------
def comprobar_umbrales():
    titulo(4, 'Los umbrales de reglas_clinicas.md son las constantes del motor')
    print('   (los dos lados se leen de su fuente; este script no guarda copia)')

    sys.path.insert(0, str(PROYECTO))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Registro_Post_Quirurgico.settings')
    import django
    django.setup()
    from signos_sintomas import alert_engine as motor

    doc = (RAIZ / 'docs' / 'reglas_clinicas.md').read_text(encoding='utf-8')

    def fila(prefijo):
        m = re.search(rf'^\| {re.escape(prefijo)} \| (.+?) \|', doc, re.M)
        return m.group(1) if m else None

    comprobaciones = [
        ('1a · fiebre ALTA', fila('1a'), str(motor.TEMPERATURA_ALTA)),
        ('1b · piso subfebrícula', fila('1b'), str(motor.TEMPERATURA_SUBFEBRICULA_MIN)),
        ('2a · drenajes ALTA', fila('2a'), None),
        ('2b · drenajes MEDIA', fila('2b'), None),
        ('3c · días sin gases ALTA', fila('3c'), str(motor.DIAS_SIN_GASES_ALTA)),
        ('3b · días sin gases MEDIA', fila('3b'), str(motor.DIAS_SIN_GASES_MEDIA)),
        ('4b · náuseas MEDIA', fila('4b'), str(motor.NAUSEAS_MEDIA_MIN)),
        ('4c · náuseas ALTA', fila('4c'), str(motor.NAUSEAS_ALTA_MIN)),
        ('4e · persistencia náuseas ALTA', fila('4e'), str(motor.DIAS_NAUSEAS_ALTA)),
        ('6b · días sin líquidos ALTA', fila('6b'), str(motor.DIAS_SIN_TOLERAR_LIQUIDOS_ALTA)),
        ('7c · días hinchazón ALTA', fila('7c'), str(motor.DIAS_HINCHAZON_MUCHO_ALTA)),
        ('8a · FC BAJA', fila('8a'), str(motor.FC_BAJA_MIN)),
        ('8b · FC MEDIA', fila('8b'), str(motor.FC_MEDIA_MIN)),
        ('8c · FC ALTA', fila('8c'), str(motor.FC_ALTA_MIN)),
    ]

    for nombre, texto_fila, valor in comprobaciones:
        if texto_fila is None:
            falla('umbrales', f'{nombre}: la fila no aparece en el documento')
            continue
        if valor is None:
            continue
        if valor in texto_fila:
            ok(f'{nombre}: el documento dice {valor}, el motor también')
        else:
            falla('umbrales',
                  f'{nombre}: el motor vale {valor} y el documento dice '
                  f'«{texto_fila.strip()}»')

    # Los aspectos de drenaje, comparados como conjuntos.
    for nombre, prefijo, constante in (
        ('2a', '2a', motor.DRENAJES_ALTA), ('2b', '2b', motor.DRENAJES_MEDIA),
    ):
        texto_fila = fila(prefijo) or ''
        faltan = [a for a in constante if a not in texto_fila]
        if faltan:
            falla('umbrales', f'regla {nombre}: el motor incluye {faltan} y el '
                              f'documento no los nombra')
        else:
            ok(f'regla {nombre}: aspectos {list(constante)} nombrados en el documento')

    # Las ventanas de dolor, contra la nota de la Regla 5.
    nota = re.search(r'POD 1-2 → BAJA (\d)-\d/MEDIA (\d)-\d/ALTA (\d+)-10', doc)
    if not nota:
        falla('umbrales', 'la nota de la Regla 5 no tiene el formato esperado')
    else:
        del_doc = tuple(int(g) for g in nota.groups())
        del_motor = tuple(motor.VENTANAS_DOLOR[0][1:])
        if del_doc == del_motor:
            ok(f'regla 5 · ventana POD 0-2: documento y motor coinciden en {del_doc}')
        else:
            falla('umbrales', f'regla 5 · ventana POD 0-2: el documento dice '
                              f'{del_doc} y el motor {del_motor}')

    delta = re.search(r'sube >=(\d+) puntos', doc)
    if delta and int(delta.group(1)) == motor.DOLOR_DELTA_TENDENCIA:
        ok(f'regla 5b · delta de tendencia: {motor.DOLOR_DELTA_TENDENCIA} en ambos')
    else:
        falla('umbrales', 'regla 5b · el delta de tendencia no coincide o no se '
                          'encuentra en el documento')


# ---------------------------------------------------------------------------
# 5 · El índice de decisiones cubre el cuerpo
# ---------------------------------------------------------------------------
def _sin_comentarios(ruta):
    """Devuelve el archivo sin sus comentarios.

    Un comentario que explica **por qué** se quitó un valor tiene todo el
    derecho a citarlo: «estaban copiados como texto (37.9°C, 101 lpm)». Sin esta
    poda, el propio comentario que documenta la corrección hace saltar la alarma
    — y una alarma que salta por su propia explicación se desactiva en una
    semana.

    Las cadenas SÍ se conservan: la plantilla HTML del panel vive dentro de una,
    y es justo donde estaban los literales que hay que impedir.
    """
    texto = ruta.read_text(encoding='utf-8')
    if ruta.suffix != '.py':
        # En las plantillas, los comentarios de Django y los de HTML.
        texto = re.sub(r'\{#.*?#\}|<!--.*?-->', '', texto, flags=re.S)
        return texto

    import io as _io
    import tokenize
    piezas = []
    try:
        for tok in tokenize.generate_tokens(_io.StringIO(texto).readline):
            if tok.type != tokenize.COMMENT:
                piezas.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        return texto          # ante la duda, se mira todo
    return '\n'.join(piezas)


def comprobar_umbrales_duplicados():
    """Ningún umbral clínico escrito a mano fuera de su fuente única (BE-02).

    **El caso que lo motiva es el mejor argumento.** El panel del médico traía
    los umbrales como texto —«umbral fiebre: 37.9°C», «101 lpm · 110 lpm»— y la
    auditoría avisó de lo evidente: el día que cambien, el médico verá la línea
    vieja. Pero el daño ya había ocurrido por otra puerta: la etiqueta decía
    **«Dolor EVA (1-10)»**, y la decisión **D20** abrió la escala a **0-10** el
    08/09/2026. El panel llevaba un día mintiéndole al médico sobre la escala, y
    lo rompió el propio equipo sin enterarse.

    Por eso esto no basta con arreglarlo: hay que impedir que vuelva. Se buscan
    los valores de las constantes en el código de presentación; si aparecen
    escritos, es que alguien volvió a copiarlos.
    """
    titulo(8, 'Ningún umbral clínico repetido fuera de alert_engine.py')

    sys.path.insert(0, str(PROYECTO))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Registro_Post_Quirurgico.settings')
    import django
    django.setup()
    from signos_sintomas import alert_engine as motor

    umbrales = {
        'TEMPERATURA_ALTA': str(motor.TEMPERATURA_ALTA),
        'FC_BAJA_MIN': str(motor.FC_BAJA_MIN),
        'FC_MEDIA_MIN': str(motor.FC_MEDIA_MIN),
        'FC_ALTA_MIN': str(motor.FC_ALTA_MIN),
    }

    # Dónde se mira: lo que ve el médico y lo que ve el paciente. NO se mira
    # `alert_engine.py` (es la fuente), ni las pruebas (ahí los valores tienen
    # que estar escritos: son justo las que fijan los umbrales), ni las
    # migraciones (código generado).
    vigilados = []
    for patron in ('signos_sintomas/admin.py', 'signos_sintomas/templatetags/*.py',
                   'signos_sintomas/bot.py', 'templates/**/*.html',
                   'signos_sintomas/templates/**/*.html'):
        vigilados += list(PROYECTO.glob(patron))

    encontrados = 0
    for ruta in vigilados:
        texto = _sin_comentarios(ruta)
        rel = ruta.relative_to(PROYECTO).as_posix()
        for nombre, valor in umbrales.items():
            # Se busca el número como valor suelto, no como parte de otro.
            if re.search(rf'(?<![\d.]){re.escape(valor)}(?![\d.])', texto):
                encontrados += 1
                falla('umbrales-copiados',
                      f'{rel} contiene «{valor}», que es {nombre}. Los umbrales '
                      f'se leen de `alert_engine`, no se reescriben (BE-02).')
    if not encontrados:
        ok(f'{len(vigilados)} archivos de presentación revisados, '
           f'ninguno repite un umbral')


def comprobar_fichas():
    titulo(5, 'El índice de decisiones lista todas las fichas del cuerpo')

    doc = (RAIZ / 'docs' / 'decisiones_correccion_auditoria.md').read_text(encoding='utf-8')
    cuerpo = set(re.findall(r'^## (D\d+) —', doc, re.M))
    indice = set(re.findall(r'^\| \[(D\d+)\]', doc, re.M))

    sin_indexar = sorted(cuerpo - indice, key=lambda d: int(d[1:]))
    fantasma = sorted(indice - cuerpo, key=lambda d: int(d[1:]))
    if sin_indexar:
        falla('fichas', f'en el cuerpo pero no en el índice: {sin_indexar}')
    if fantasma:
        falla('fichas', f'en el índice pero no en el cuerpo: {fantasma}')
    if not sin_indexar and not fantasma:
        ok(f'{len(cuerpo)} fichas, todas indexadas')


# ---------------------------------------------------------------------------
# 6 · Los commits que cita la documentación existen
# ---------------------------------------------------------------------------
def comprobar_commits():
    titulo(6, 'Los commits citados en la documentación existen en la historia')

    patron = re.compile(r'`([0-9a-f]{7,40})`')
    citados = {}
    for doc in documentos():
        for m in patron.finditer(doc.read_text(encoding='utf-8')):
            sha = m.group(1)
            if not re.fullmatch(r'[0-9a-f]{7}', sha):   # solo los cortos, que son los que se usan
                continue
            citados.setdefault(sha, set()).add(doc.relative_to(RAIZ).as_posix())

    rotos = 0
    for sha, quienes in sorted(citados.items()):
        if sha in COMMITS_HISTORICOS:
            continue
        r = subprocess.run(['git', 'cat-file', '-e', f'{sha}^{{commit}}'],
                           cwd=RAIZ, capture_output=True)
        if r.returncode != 0:
            rotos += 1
            falla('commits', f'{sha} no existe — citado en: {", ".join(sorted(quienes))}')
    if not rotos:
        ok(f'{len(citados)} commits citados, todos existen '
           f'({len(COMMITS_HISTORICOS)} declarados como borrados a propósito)')


# ---------------------------------------------------------------------------
# 7 · El comando documentado para correr manage.py funciona
# ---------------------------------------------------------------------------
def comprobar_comandos():
    titulo(7, 'El camino documentado hasta manage.py es correcto')

    claude = (RAIZ / 'CLAUDE.md').read_text(encoding='utf-8')
    m = re.search(r'^cd (\S+)', claude, re.M)
    if not m:
        aviso('no se encontró un `cd` en CLAUDE.md')
        return
    destino = RAIZ / m.group(1)
    if (destino / 'manage.py').exists():
        ok(f'`cd {m.group(1)}` desde la raíz lleva a manage.py')
    else:
        falla('comandos', f'`cd {m.group(1)}` desde la raíz NO lleva a manage.py')

    if '.venv' in claude:
        ok('CLAUDE.md menciona el entorno virtual del proyecto')
    else:
        falla('comandos', 'CLAUDE.md no dice cuál es el intérprete del proyecto')


def main():
    print('BARRIDO DE VERACIDAD DE LA DOCUMENTACIÓN')
    print(f'repositorio: {RAIZ}')

    comprobar_rutas()
    comprobar_conteo_de_pruebas()
    comprobar_ci()
    comprobar_umbrales()
    comprobar_umbrales_duplicados()
    comprobar_fichas()
    comprobar_commits()
    comprobar_comandos()

    print()
    print('=' * 78)
    if fallos:
        print(f'{len(fallos)} AFIRMACIONES FALSAS:')
        for comprobacion, detalle in fallos:
            print(f'  [{comprobacion}] {detalle}')
    else:
        print('Todo lo que la documentación afirma es cierto.')
    if avisos:
        print(f'\n{len(avisos)} avisos (no fallan el barrido):')
        for a in avisos:
            print(f'  {a}')
    print('=' * 78)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
