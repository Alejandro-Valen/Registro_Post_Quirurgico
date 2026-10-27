#!/usr/bin/env bash
# ¿La imagen de producción se construye, arranca healthy y sin root?
#
# Lo corre la CI (job «Imagen de producción») y se puede correr a mano desde la
# raíz del repositorio, con Docker encendido y SECRET_KEY_DOCKER definida:
#
#   SECRET_KEY_DOCKER=relleno bash proceso/verificaciones/2026-10-27_imagen_arranca.sh
#
# En Git Bash de Windows, anteponer MSYS_NO_PATHCONV=1: si no, las rutas que
# se pasan a `docker exec` llegan mutiladas.
#
# Por qué existe: del 07/09 al 27/10/2026 la imagen no se construía y nada lo
# dijo. Verificado en las dos direcciones el 27/10/2026: con el `.dockerignore`
# de `b85c83c` falla en la construcción; con el de `db17fed` pasa.
#
# Deja el entorno limpio al salir, pase o falle: `down -v` borra contenedores y
# la base de prueba.
set -euo pipefail

limpiar() { docker compose down -v >/dev/null 2>&1 || true; }
trap limpiar EXIT

docker compose up --build -d

web=$(docker compose ps -q web)
estado=desconocido
for _ in $(seq 1 60); do
  estado=$(docker inspect -f '{{.State.Health.Status}}' "$web")
  [ "$estado" = healthy ] || [ "$estado" = unhealthy ] && break
  sleep 5
done

if [ "$estado" != healthy ]; then
  echo "::error::El contenedor web terminó en '$estado', no en healthy."
  docker compose logs web | tail -60
  exit 1
fi
echo "HEALTHCHECK: healthy"

uid=$(docker exec "$web" id -u)
if [ "$uid" = 0 ]; then
  echo "::error::El contenedor corre como root (SEC-13)."
  exit 1
fi
echo "Usuario del proceso: uid $uid (no root)"
