@echo off
title Desinstalador y Limpiador del Sistema TaskCore
cd /d "%~dp0"

:: Verificar si se ejecuta como Administrador
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Este script requiere privilegios de Administrador para limpiar el registro, hosts y firewall.
    echo Reabriendo como Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ======================================================================
echo       DESINSTALADOR Y LIMPIADOR DEL SISTEMA TASKCORE
echo ======================================================================
echo.
echo Este script realizara las siguientes operaciones de limpieza:
1. Cerrar procesos en ejecucion (python, docker compose).
echo 2. Eliminar el protocolo de registro "taskcore://".
echo 3. Eliminar politicas de lanzamiento automatico en navegadores.
echo 4. Limpiar el mapeo de red "taskcore" del archivo hosts.
echo 5. Borrar logs de depuracion temporales del sistema.
echo 6. Opcional: Limpiar bases de datos locales, venv, configuraciones y archivos.
echo.
set /p CONFIRM="¿Desea continuar con la desinstalacion/limpieza? (S/N): "
if /i "%CONFIRM%" neq "S" (
    echo Desinstalacion cancelada.
    pause
    exit /b
)

echo.
echo ======================================================================
echo 1. DETENIENDO PROCESOS EN EJECUCION
echo ======================================================================
echo [INFO] Cerrando servidores locales de Python...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /fi "windowtitle eq TaskCore - Guardian de Archivos" >nul 2>&1

:: Detener Docker compose si esta instalado y configurado
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Detectado Docker. Deteniendo y removiendo contenedores/volumenes...
    docker compose down -v >nul 2>&1
)
echo [OK] Procesos detenidos.
echo.

echo ======================================================================
echo 2. LIMPIANDO EL REGISTRO DE WINDOWS
echo ======================================================================
echo [INFO] Eliminando protocolo "taskcore://" y politicas de navegadores...

:: Eliminar protocolo URL
reg delete "HKEY_CLASSES_ROOT\taskcore" /f >nul 2>&1

:: Eliminar politicas de Chrome
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Google\Chrome" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1
reg delete "HKEY_CURRENT_USER\SOFTWARE\Policies\Google\Chrome" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1

:: Eliminar politicas de Edge
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Edge" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1
reg delete "HKEY_CURRENT_USER\SOFTWARE\Policies\Microsoft\Edge" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1

:: Eliminar politicas de Opera
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Opera" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1
reg delete "HKEY_CURRENT_USER\SOFTWARE\Policies\Opera" /v "AutoLaunchProtocolsFromOrigins" /f >nul 2>&1

echo [OK] Registro de Windows limpio.
echo.

echo ======================================================================
echo 3. RESTAURANDO ARCHIVO HOSTS
echo ======================================================================
echo [INFO] Removiendo direccion "taskcore" de hosts...
set HOSTS_PATH=%windir%\System32\drivers\etc\hosts
powershell -Command "(Get-Content '%HOSTS_PATH%') | Where-Object { $_ -notmatch 'taskcore' } | Set-Content '%HOSTS_PATH%'" >nul 2>&1
echo [OK] Archivo hosts restaurado.
echo.

echo ======================================================================
echo 4. ELIMINANDO ARCHIVOS TEMPORALES Y LOGS PUBLICOS
echo ======================================================================
echo [INFO] Eliminando logs de depuracion publica...
if exist "C:\Users\Public\taskcore_debug.txt" (
    del /f /q "C:\Users\Public\taskcore_debug.txt" >nul 2>&1
)
echo [OK] Archivos temporales eliminados.
echo.

echo ======================================================================
echo 5. PREPARANDO MARCA BLANCA (OPCIONES DE LIMPIEZA DE ARCHIVOS)
echo ======================================================================
set /p LIMPIAR_ARCHIVOS="¿Desea borrar las carpetas de archivos de produccion (TaskCore_Archivos / TaskCore_Archivos_Test)? (S/N): "
if /i "%LIMPIAR_ARCHIVOS%"=="S" (
    echo [INFO] Eliminando directorios de almacenamiento de archivos...
    if exist "TaskCore_Archivos" rd /s /q "TaskCore_Archivos" >nul 2>&1
    if exist "TaskCore_Archivos_Test" rd /s /q "TaskCore_Archivos_Test" >nul 2>&1
    if exist "D:\TaskCore_Archivos" rd /s /q "D:\TaskCore_Archivos" >nul 2>&1
    if exist "D:\TaskCore_Archivos_Test" rd /s /q "D:\TaskCore_Archivos_Test" >nul 2>&1
    if exist "E:\TaskCore_Archivos" rd /s /q "E:\TaskCore_Archivos" >nul 2>&1
    echo [OK] Carpetas de archivos eliminadas.
)

set /p LIMPIAR_DB="¿Desea borrar las bases de datos locales (SQLite test.db / .db)? (S/N): "
if /i "%LIMPIAR_DB%"=="S" (
    echo [INFO] Eliminando bases de datos locales SQLite...
    if exist "test.db" del /f /q "test.db" >nul 2>&1
    if exist "sistema_gestion_produccion_test.db" del /f /q "sistema_gestion_produccion_test.db" >nul 2>&1
    if exist "db_data" rd /s /q "db_data" >nul 2>&1
    echo [OK] Bases de datos eliminadas.
)

set /p LIMPIAR_VENV="¿Desea eliminar el entorno virtual de python (venv)? (S/N): "
if /i "%LIMPIAR_VENV%"=="S" (
    echo [INFO] Eliminando entorno virtual (venv)...
    if exist "venv" rd /s /q "venv" >nul 2>&1
    echo [OK] Entorno virtual venv eliminado.
)

set /p LIMPIAR_KEYS="¿Desea eliminar llaves de configuracion (.env)? (S/N): "
if /i "%LIMPIAR_KEYS%"=="S" (
    echo [INFO] Eliminando configuraciones locales...
    if exist ".env" del /f /q ".env" >nul 2>&1
    echo [OK] Configuraciones eliminadas.
)

echo.
echo ======================================================================
echo ¡PROCESO DE DESINSTALACION Y LIMPIEZA COMPLETADO CON EXITO!
echo El sistema se ha limpiado correctamente.
echo ======================================================================
echo.
pause
