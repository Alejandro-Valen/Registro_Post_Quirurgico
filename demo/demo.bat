@echo off
REM Lanzador de la demostracion. Doble clic, o `demo\demo.bat` desde la raiz.
REM
REM Usa el interprete del entorno virtual del proyecto para no depender de que
REM el `python` del PATH sea el correcto: en la maquina de trabajo hay varios.
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "demo\demo.py"
) else (
    echo No encontre .venv\Scripts\python.exe
    echo Crea el entorno virtual del proyecto antes de correr la demo.
    pause
    exit /b 1
)
endlocal
