@echo off
title Sistema TaskCore - Servidor Principal
cd /d "%~dp0"
echo ======================================================================
echo             INICIANDO SISTEMA DE GESTION TASKCORE
echo ======================================================================
echo.

:: 1. Limpiar procesos de ejecuciones anteriores para evitar conflictos
echo [CLEANUP] Cerrando instancias y procesos anteriores...
taskkill /f /fi "windowtitle eq TaskCore - Guardian de Archivos" >nul 2>&1
echo [OK] Procesos anteriores finalizados de forma segura.
echo.

:: 2. Activar el entorno virtual si existe
if exist venv\Scripts\activate.bat (
    echo [INFO] Entorno virtual detectado. Activando...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] No se detecto la carpeta 'venv'. Se usara el Python global.
)
echo.

:: 3. Iniciar el vigilante de carpetas (auto_watcher.py) en una ventana nueva
echo [1/2] Iniciando Guardian de Archivos (auto_watcher.py)...
start "TaskCore - Guardian de Archivos" cmd /k "python auto_watcher.py"

:: 4. Iniciar la aplicacion web (app.py) en la ventana actual
echo [2/2] Iniciando Servidor Web (app.py)...
echo.
echo ======================================================================
echo Accede a la web en: http://localhost
echo.
echo Para cerrar todo, cierra las ventanas abiertas del Guardian y esta.
echo ======================================================================
echo.
python app.py

pause
