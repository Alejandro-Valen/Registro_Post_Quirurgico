# Build determinista para Railway.
#
# Por qué Dockerfile y no Nixpacks: Nixpacks arma el entorno con Nix, y al
# personalizar la instalación pip/venv no quedan disponibles (Nix no trae
# ensurepip). Con python:3.13-slim, pip existe siempre. Además controlamos
# explícitamente el layout no estándar de este repo: manage.py vive en la
# subcarpeta Registro_Post_Quirurgico/.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_production

WORKDIR /app

# Dependencias de producción. Se declaran en `pyproject.toml`, que desde el
# 07/09/2026 es la fuente única: antes había tres `requirements*.txt` y el que
# llevaba el nombre canónico era un `pip freeze` de la máquina de desarrollo
# —con paquetes solo-Windows que ni siquiera instalaban aquí—, así que este
# Dockerfile tenía que esquivarlo a mano.
#
# `pip install .` instala solo las nueve dependencias de runtime; el extra
# `dev` (linter, pip-audit, freezegun) se queda fuera a propósito.
#
# psycopg2-binary, gunicorn, whitenoise y el resto vienen como wheels: no hace
# falta compilador ni libpq del sistema.
#
# Se copian ANTES que el código para que la capa de dependencias quede en caché
# y un cambio en la app no obligue a reinstalarlas. LICENSE y README.md entran
# aquí porque `pyproject.toml` los referencia y sin ellos la instalación falla.
COPY pyproject.toml LICENSE README.md ./
RUN pip install .

# Código de la app.
COPY . .

# collectstatic, migrate y gunicorn corren en el ARRANQUE (no en el build):
# en un build de Docker en Railway las variables del servicio no están
# disponibles, y settings_production las necesita para importar. En runtime sí
# están. --chdir entra a la subcarpeta donde vive manage.py para que el módulo
# WSGI (Registro_Post_Quirurgico.wsgi) sea importable.
CMD python Registro_Post_Quirurgico/manage.py collectstatic --noinput \
 && python Registro_Post_Quirurgico/manage.py migrate --noinput \
 && ( [ "$RESET_AXES" = "1" ] && python Registro_Post_Quirurgico/manage.py axes_reset || true ) \
 && (python Registro_Post_Quirurgico/manage.py crear_admin || true) \
 && python Registro_Post_Quirurgico/manage.py crear_medico \
 && gunicorn Registro_Post_Quirurgico.wsgi:application \
      --chdir Registro_Post_Quirurgico --bind 0.0.0.0:${PORT:-8000}
