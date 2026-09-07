@echo off
title Entorno virtual - Registro Post-Quirurgico

cd /d "%~dp0"

REM Hasta el 07/09/2026 este script llamaba a `entorno_registro\Scripts\
REM activate.bat`, una carpeta que NO EXISTIA en disco: el proyecto llevaba
REM meses corriendo con el Python global. Ahora apunta a `.venv`, que es el
REM nombre estandar y el que documenta el README.

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo   No se encontro el entorno virtual en .venv
    echo.
    echo   Crealo con:
    echo       py -3.13 -m venv .venv
    echo       .venv\Scripts\python -m pip install -r requirements-dev.txt
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo   Entorno ".venv" activado.
echo.
echo   Comandos utiles (desde Registro_Post_Quirurgico\):
echo       python manage.py test --noinput      suite completa
echo       python manage.py runserver           http://127.0.0.1:8000/admin/
echo   Desde la raiz:
echo       ruff check .                         linter
echo.
cmd /k
