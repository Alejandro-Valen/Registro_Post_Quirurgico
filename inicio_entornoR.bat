@echo off
title Activar entorno virtual Python

cd /d "%~dp0"

call entorno_registro\Scripts\activate.bat

echo.
echo Entorno virtual "entorno_registro" activado.
cmd /k