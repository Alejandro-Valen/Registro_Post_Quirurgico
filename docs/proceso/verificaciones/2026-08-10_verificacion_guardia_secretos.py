"""Verificación independiente de la guardia de secretos (10/08/2026).

QUÉ COMPRUEBA
=============

Que el sexto check de la CI —`gitleaks` sobre la historia completa— **de verdad
detiene un secreto**, y que no detiene el código sano.

Por qué hace falta un script para esto. Un check que nadie ha visto fallar no
prueba nada: podría estar mirando el archivo equivocado, escaneando un rango
vacío, o no estar mirando nada. Es la lección que dejó el hallazgo bloqueante
del 22/07/2026 —280 pruebas en verde que no medían el requisito— y por eso aquí
se comprueba en las dos direcciones:

  1. Secretos que DEBEN detener la CI  → se espera código de salida 1
  2. Código correcto que NO debe detenerla → se espera código de salida 0

La segunda mitad no es adorno. Una guardia que dice que todo es un secreto es
igual de inútil que una que no ve ninguno: se desactiva a la semana.

UN TROPIEZO QUE VALE LA PENA CONTAR
===================================

La primera versión de esta verificación daba rojo en los cinco casos, incluidos
los que debían pasar. La causa: se había hecho `git stash` antes de correrla, y
eso se llevó `.gitleaksignore` fuera del árbol. Sin ese archivo reaparece el
hallazgo histórico del Sprint 0 y **todo** da rojo, por un motivo que no tiene
nada que ver con lo que se estaba probando.

Es decir: los tres primeros casos "pasaban" por la razón equivocada. Si solo se
hubiera comprobado la mitad de los casos —los que deben fallar— el arnés roto
habría pasado por bueno. Por eso están las dos mitades.

CÓMO SE CORRE
=============

    python docs/proceso/verificaciones/2026-08-10_verificacion_guardia_secretos.py

Necesita `gitleaks` en el PATH. Si no está:

    Windows:  descargar de https://github.com/gitleaks/gitleaks/releases
    Linux:    misma página, o el paquete de la distribución

El script trabaja sobre una rama desechable y la borra al terminar, pase lo que
pase. No toca la rama en la que estabas ni deja archivos sueltos.
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
ARCHIVO_CEBO = RAIZ / "Registro_Post_Quirurgico" / "filtracion_de_prueba.py"
RAMA = "verificacion-guardia-secretos"

# --- Los cebos ------------------------------------------------------------
#
# Se arman por concatenación en vez de escribirse enteros, y no es manía: la
# primera versión los llevaba literales, y en cuanto este archivo entró en un
# commit, gitleaks empezó a encontrarlos AQUÍ. La guardia se disparaba contra
# su propia verificación y todo escaneo daba rojo.
#
# La salida fácil habría sido meter esta ruta en la allowlist de
# `.gitleaks.toml`. No se hizo: eso dejaría un archivo del repositorio donde un
# secreto de verdad podría esconderse para siempre sin que nadie lo vea.
# Partidos en dos, los cebos siguen siendo secretos perfectamente válidos
# cuando el script los escribe en disco, pero no existen como texto contiguo en
# ningún archivo versionado. Nada que silenciar.
CEBO_TWILIO = "SK" + "0123456789abcdef0123456789abcdef"
CEBO_DJANGO = "django-insecure-" + "abc123def456ghi789jkl012mno345pqr"
CEBO_RSA = (
    "-----BEGIN RSA " + "PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAvR2VzcmV0bm90cmVhbGx5YXNlY3JldGtleWZvcnRlc3Rpbmc=\n"
    "-----END RSA " + "PRIVATE KEY-----"
)

# (titulo, contenido del archivo, codigo de salida esperado)
CASOS = [
    ("clave de Twilio",
     "TWILIO_AUTH_TOKEN = '%s'" % CEBO_TWILIO, 1),
    ("SECRET_KEY de Django literal (regla propia del proyecto)",
     "SECRET_KEY = '%s'" % CEBO_DJANGO, 1),
    ("clave privada RSA",
     CEBO_RSA, 1),
    ("SECRET_KEY leída del entorno (la forma correcta)",
     "SECRET_KEY = config_obligatoria('SECRET_KEY')", 0),
    ("valor de relleno que usa la propia CI",
     "SECRET_KEY = 'ci-clave-de-relleno-sin-valor-fuera-de-este-runner-efimero'", 0),
]


def git(*args, **kwargs):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, **kwargs)


def escanear():
    """Corre gitleaks igual que la CI y devuelve su código de salida."""
    completado = subprocess.run(
        ["gitleaks", "git", "--log-opts=--all", "-c", ".gitleaks.toml",
         "--redact", "--exit-code", "1", "--no-banner"],
        cwd=RAIZ, capture_output=True,
    )
    return completado.returncode


def main():
    if shutil.which("gitleaks") is None:
        print("FALTA gitleaks. Ver las instrucciones en la cabecera de este archivo.")
        return 2

    sucio = git("status", "--porcelain").stdout.decode().strip()
    if sucio:
        print("El árbol tiene cambios sin commitear. Guárdalos antes de correr esto:")
        print("  (y no con `git stash` a medias: ver el tropiezo que cuenta la cabecera)")
        print(sucio)
        return 2

    rama_origen = git("rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
    print("Rama de partida: %s" % rama_origen)
    git("checkout", "--quiet", "-b", RAMA)

    fallos = 0
    try:
        for titulo, contenido, esperado in CASOS:
            ARCHIVO_CEBO.write_text(contenido + "\n", encoding="utf-8")
            git("add", str(ARCHIVO_CEBO))
            git("commit", "--quiet", "--no-verify", "-m", "temporal: cebo de verificacion")

            obtenido = escanear()
            git("reset", "--quiet", "--hard", "HEAD~1")

            debe = "detenerse" if esperado == 1 else "pasar"
            if obtenido == esperado:
                print("  OK    [%s] %s" % (debe, titulo))
            else:
                print("  FALLA [%s] %s — salida %d, esperada %d"
                      % (debe, titulo, obtenido, esperado))
                fallos += 1
    finally:
        git("checkout", "--quiet", rama_origen)
        git("branch", "-D", RAMA, "--quiet")
        if ARCHIVO_CEBO.exists():
            ARCHIVO_CEBO.unlink()

    print()
    if fallos:
        print("HAY %d COMPROBACIONES FALLIDAS" % fallos)
        return 1
    print("TODO CORRECTO: la guardia detiene los secretos y deja pasar el código sano.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
