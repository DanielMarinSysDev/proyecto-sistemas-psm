@echo on
title Sistema TaskCore (Docker + Host Services)
echo ======================================================================
echo          INICIANDO INFRAESTRUCTURA TASKCORE CON DOCKER
echo ======================================================================
echo.

:: Definir ruta base de archivos adaptable (E: para producción, o D: / local para pruebas)
set BASE_DIR=%CD%\TaskCore_Archivos
if exist D:\ (
    set BASE_DIR=D:\TaskCore_Archivos
)
if exist E:\ (
    set BASE_DIR=E:\TaskCore_Archivos
)
set BASE_DIR_HOST=%BASE_DIR%

set DATABASE_URL=postgresql://taskcore_user:taskcore_pass_123@localhost:5432/sistema_taskcore

:: Crear directorios base si no existen
if not exist "%BASE_DIR%" (
    echo [INFO] Creando directorio base: %BASE_DIR%...
    mkdir "%BASE_DIR%"
)

:: 1. Limpiar procesos locales huérfanos del guardián
echo [CLEANUP] Cerrando instancias y procesos anteriores locales...
taskkill /f /fi "windowtitle eq TaskCore - Guardian de Archivos" >nul 2>&1
echo [OK] Limpieza completada.
echo.

:: 2. Levantar la base de datos PostgreSQL y la App en Docker
echo [1/2] Esperando a que el motor de Docker esté listo...
:wait_docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 >nul
    goto wait_docker
)
echo [OK] Motor de Docker activo.
echo Levantando Base de Datos y Servidor Web en Docker...
docker compose up -d --build
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo levantar Docker Compose.
    pause
    exit /b %errorlevel%
)
echo [OK] Contenedores activos en segundo plano.
echo.

:: 3. Activar entorno virtual y arrancar el auto_watcher local apuntando a PostgreSQL
if exist venv\Scripts\activate.bat (
    echo [INFO] Entorno virtual detectado. Activando para el Guardian...
    call venv\Scripts\activate.bat
)

echo [2/2] Iniciando Guardian de Archivos (auto_watcher.py) enlazado a PostgreSQL...
start "TaskCore - Guardian de Archivos" cmd /k "set DATABASE_URL=%DATABASE_URL%&& set BASE_DIR=%BASE_DIR%&& python auto_watcher.py"

echo.
echo ======================================================================
echo ¡Despliegue y Servicios Inicializados Correctamente!
echo Accede a la web local en: http://localhost (o la IP del Servidor)
echo.
echo Para apagar la base de datos, ejecuta: docker compose down
echo ======================================================================
echo.
pause
