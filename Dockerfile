# Build determinista para Railway.
#
# Por qué Dockerfile y no Nixpacks: Nixpacks arma el entorno con Nix, y al
# personalizar la instalación pip/venv no quedan disponibles (Nix no trae
# ensurepip). Con python:3.13-slim, pip existe siempre. Además controlamos
# explícitamente el layout no estándar de este repo (manage.py vive en la
# subcarpeta Registro_Post_Quirurgico/) y evitamos el requirements.txt de
# desarrollo (pip freeze con paquetes solo-Windows que romperían el build).

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=Registro_Post_Quirurgico.settings_production

WORKDIR /app

# Dependencias de producción LIMPIAS (no el pip freeze de requirements.txt).
# psycopg2-binary, gunicorn, whitenoise y el resto vienen como wheels: no hace
# falta compilador ni libpq del sistema.
COPY requirements-runtime.txt .
RUN pip install -r requirements-runtime.txt

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
