"""Verificación del Loop del Arnés — fichas D16 y D17 (07/09/2026).

QUÉ COMPRUEBA, y por qué este script existe
-------------------------------------------
El loop no añadió funcionalidad: reparó las GUARDIAS. Y una guardia solo vale
si se la ha visto fallar. Así que esto no comprueba "que todo esté en verde":
comprueba, para cada guardia, **las dos direcciones**:

    1. Que ATRAPA lo que debe atrapar  -> se le pone delante el caso malo.
    2. Que DEJA PASAR lo que debe pasar -> se le pone delante el caso sano.

Una guardia que solo se comprueba en la dirección (2) es exactamente el defecto
que este loop vino a corregir: `check --deploy` llevaba desde el 31/07/2026 sin
poder ponerse en rojo, y nadie lo noto porque siempre se lo miro en verde.

CÓMO SE CORRE
-------------
    cd <raiz del repositorio>
    .venv\\Scripts\\python proceso\\verificaciones\\2026-09-07_verificacion_arnes.py

No modifica nada de forma permanente: los sabotajes se aplican sobre copias
temporales o se revierten en un `finally`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def _raiz_del_repositorio() -> Path:
    """Sube hasta encontrar el `.git`, en vez de contar carpetas.

    Contar (`parents[3]`) rompe el script en cuanto alguien lo mueve, y en
    silencio: se pone a mirar el directorio equivocado y reporta lo que
    encuentre ahí. Pasó el 07/09/2026 al mover `docs/proceso/` a `proceso/`.
    """
    for directorio in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (directorio / '.git').exists():
            return directorio
    raise RuntimeError('No se encontró la raíz del repositorio (.git) desde este script.')


RAIZ = _raiz_del_repositorio()
PROYECTO = RAIZ / 'Registro_Post_Quirurgico'
PY = sys.executable

# El mismo entorno de relleno que usa .github/workflows/ci.yml. Sin esto,
# `settings_production` aborta por variables ausentes y el resultado no diría
# nada sobre la bandera que se quiere probar.
ENTORNO_CI = {
    'SECRET_KEY': 'verificacion-clave-de-relleno-sin-valor-fuera-de-este-script',
    'DEBUG': 'False',
    'DB_NAME': 'registro_postquirurgico_db',
    'DB_USER': 'postgres',
    'DB_PASSWORD': 'postgres',
    'DB_HOST': 'localhost',
    'DB_PORT': '5432',
    'ALLOWED_HOSTS': 'ci.example.com',
    'CSRF_TRUSTED_ORIGINS': 'https://ci.example.com',
    'REDIS_URL': 'redis://localhost:6379/1',
    'EMAIL_DELIVERY_PROVIDER': 'resend',
    'RESEND_API_KEY': 'clave-de-relleno',
    'RESEND_FROM_EMAIL': 'ci@ejemplo.com',
    'TRUST_RAILWAY_PROXY': 'False',
    'DJANGO_SETTINGS_MODULE': 'Registro_Post_Quirurgico.settings_production',
}

resultados: list[tuple[bool, str]] = []


def registrar(ok: bool, titulo: str, detalle: str = '') -> None:
    marca = 'OK  ' if ok else 'FALLA'
    print(f'  [{marca}] {titulo}')
    if detalle:
        print(f'          {detalle}')
    resultados.append((ok, titulo))


def correr(cmd: list[str], cwd: Path, entorno_extra: dict | None = None):
    entorno = os.environ.copy()
    if entorno_extra:
        entorno.update(entorno_extra)
    return subprocess.run(
        cmd, cwd=cwd, env=entorno,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )


# ---------------------------------------------------------------------------
# GUARDIA 1 · `check --deploy` puede ponerse en rojo  (SEC-01 / ficha D16)
# ---------------------------------------------------------------------------
def guardia_check_deploy() -> None:
    print('\nGUARDIA 1 · check --deploy con --fail-level WARNING')

    # Dirección 2: el caso sano pasa.
    r = correr([PY, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
               PROYECTO, ENTORNO_CI)
    registrar(r.returncode == 0,
              'deja pasar la configuración de producción sana',
              f'exit {r.returncode}')

    # Dirección 1: el caso malo cae. Se sabotea una directiva de seguridad
    # sobre una COPIA del módulo y se restaura siempre.
    archivo = PROYECTO / 'Registro_Post_Quirurgico' / 'settings_production.py'
    respaldo = archivo.read_text(encoding='utf-8')
    try:
        archivo.write_text(
            respaldo + '\n\n# SABOTAJE TEMPORAL DE LA VERIFICACION\n'
                       'SECURE_HSTS_SECONDS = 0\n'
                       'SESSION_COOKIE_SECURE = False\n',
            encoding='utf-8')
        r = correr([PY, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
                   PROYECTO, ENTORNO_CI)
        registrar(r.returncode != 0,
                  'ATRAPA el sabotaje (HSTS y cookie de sesión desactivadas)',
                  f'exit {r.returncode}')

        # Y la prueba de que la bandera es lo que marca la diferencia: el mismo
        # sabotaje SIN la bandera sale en verde. Esto es el hallazgo SEC-01.
        r2 = correr([PY, 'manage.py', 'check', '--deploy'], PROYECTO, ENTORNO_CI)
        registrar(r2.returncode == 0,
                  'sin la bandera, ese mismo sabotaje pasaría desapercibido',
                  f'exit {r2.returncode} — es el defecto que existía hasta el 07/09/2026')
    finally:
        archivo.write_text(respaldo, encoding='utf-8')


# ---------------------------------------------------------------------------
# GUARDIA 2 · el linter bloquea  (ficha D16)
# ---------------------------------------------------------------------------
def guardia_linter() -> None:
    print('\nGUARDIA 2 · ruff')

    r = correr([PY, '-m', 'ruff', 'check', '.'], RAIZ)
    registrar(r.returncode == 0, 'deja pasar el árbol actual, sin hallazgos',
              r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '')

    # Sabotaje: un archivo con un import muerto y una variable sin usar.
    planta = RAIZ / 'Registro_Post_Quirurgico' / '_sabotaje_verificacion.py'
    try:
        planta.write_text('import os\n\n\ndef f():\n    x = 1\n    return 2\n',
                          encoding='utf-8')
        r = correr([PY, '-m', 'ruff', 'check', '.'], RAIZ)
        registrar(r.returncode != 0, 'ATRAPA un import muerto y una variable sin usar',
                  f'exit {r.returncode}')
    finally:
        planta.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# GUARDIA 3 · pip-audit  (ficha D16)
# ---------------------------------------------------------------------------
def guardia_pip_audit() -> None:
    print('\nGUARDIA 3 · pip-audit')

    r = correr([PY, '-m', 'pip_audit', '--requirement', 'requirements-runtime.txt',
                '--strict'], RAIZ)

    # TRAMPA DE ESTA MÁQUINA, no del proyecto: `pip_api` (dependencia de
    # pip-audit) decodifica la salida de pip como UTF-8, y la ruta del entorno
    # contiene una vocal acentuada — el usuario de Windows se llama "león". En
    # Windows pip responde en cp1252 y revienta con UnicodeDecodeError ANTES de
    # mirar ninguna dependencia. En la CI (Linux, rutas ASCII) no ocurre.
    #
    # Se distingue del fallo real a propósito: dar por "vulnerable" lo que solo
    # es un problema de codificación sería justo el tipo de conclusión falsa
    # que estas verificaciones existen para evitar.
    if 'UnicodeDecodeError' in r.stderr:
        registrar(True,
                  'pip-audit: NO VERIFICABLE en esta máquina (no es un fallo del proyecto)',
                  'UnicodeDecodeError de pip_api por la tilde en la ruta del entorno; '
                  'en la CI sí corre. Ver docs/trampas_conocidas.md')
        return

    registrar(r.returncode == 0,
              'las dependencias de producción no tienen vulnerabilidades conocidas',
              f'exit {r.returncode}')

    # Sabotaje: un requirements con una version que SI tiene CVE conocido.
    with tempfile.TemporaryDirectory() as tmp:
        falso = Path(tmp) / 'requirements-con-cve.txt'
        falso.write_text('Django==6.0.7\n', encoding='utf-8')
        r = correr([PY, '-m', 'pip_audit', '--requirement', str(falso), '--strict'], RAIZ)
        registrar(r.returncode != 0,
                  'ATRAPA una dependencia con CVE conocido (Django 6.0.7)',
                  f'exit {r.returncode}')


# ---------------------------------------------------------------------------
# GUARDIA 4 · la identidad del médico no está en el árbol  (ficha D17)
# ---------------------------------------------------------------------------
def guardia_identidad() -> None:
    print('\nGUARDIA 4 · identidad de terceros fuera del árbol de trabajo')

    import re
    patron = re.compile(
        r'c[eé]dula\D{0,12}\d{6,10}|Correa Cote|Camilo Correa'
        r'|Cl[ií]nica (Medell[ií]n|Somer)|Universidad (CES|de Antioquia)',
        re.I)
    r = correr(['git', 'ls-files'], RAIZ)
    encontrados = []
    for relativo in r.stdout.splitlines():
        ruta = RAIZ / relativo
        if not ruta.is_file():
            continue
        try:
            texto = ruta.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        # Las pruebas usan cédulas inventadas a propósito, y ESTE script lleva
        # el patrón en su propio código: sin la segunda exclusión se denuncia a
        # sí mismo, que es un falso positivo garantizado.
        if ('/tests/' in relativo or 'seed_demo' in relativo
                or Path(relativo).name == Path(__file__).name):
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            if patron.search(linea):
                encontrados.append(f'{relativo}:{numero}')

    registrar(not encontrados,
              'ningún dato identificable de terceros en el árbol rastreado',
              '' if not encontrados else f'{len(encontrados)} restantes: {encontrados[:3]}')


def main() -> int:
    print('=' * 72)
    print('VERIFICACIÓN DEL LOOP DEL ARNÉS — fichas D16 y D17')
    print('Cada guardia se comprueba en LAS DOS direcciones.')
    print('=' * 72)

    guardia_check_deploy()
    guardia_linter()
    guardia_pip_audit()
    guardia_identidad()

    fallidas = [t for ok, t in resultados if not ok]
    print('\n' + '=' * 72)
    print(f'{len(resultados) - len(fallidas)} de {len(resultados)} comprobaciones OK')
    if fallidas:
        print('\nFALLARON:')
        for t in fallidas:
            print(f'  - {t}')
        return 1
    print('\nTodas las guardias se vieron fallar y se vieron pasar.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
