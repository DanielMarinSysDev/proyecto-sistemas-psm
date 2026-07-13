@echo off
title Configurar Cliente TaskCore
cd /d "%~dp0"

:: Verificar si se ejecuta como Administrador
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Este script requiere privilegios de Administrador.
    echo Reabriendo como Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ======================================================================
echo         CONFIGURANDO PC CLIENTE PARA EL SISTEMA TASKCORE
echo ======================================================================
echo.

:: 1. Importar el protocolo de Registro para abrir carpetas
echo [1/2] Instalando protocolo personalizado "taskcore://" en el registro...
if exist "instalar_protocolo.reg" (
    reg import "instalar_protocolo.reg" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Protocolo de registro instalado exitosamente.
    ) else (
        echo [WARNING] Hubo un problema al importar el registro.
    )
) else (
    echo [ERROR] No se encontro el archivo instalar_protocolo.reg en esta carpeta.
)
echo.

:: 2. Agregar direccion local "taskcore" al archivo hosts
echo [2/2] Configurando nombre amigable "taskcore" en el archivo hosts...
set HOSTS_PATH=%windir%\System32\drivers\etc\hosts
set IP_SERVER=192.168.0.19
set DOMAIN_NAME=taskcore

:: Buscar si ya existe la linea en el hosts
findstr /i /c:"%DOMAIN_NAME%" "%HOSTS_PATH%" >nul
if %errorlevel% equ 0 (
    echo [INFO] El nombre "%DOMAIN_NAME%" ya existe en el archivo hosts. No se realizaron cambios.
) else (
    echo. >> "%HOSTS_PATH%"
    echo %IP_SERVER%    %DOMAIN_NAME% >> "%HOSTS_PATH%"
    echo [OK] Se agrego "%IP_SERVER%    %DOMAIN_NAME%" al archivo hosts.
)
echo.
echo ======================================================================
echo ¡Configuracion de cliente finalizada con exito!
echo Ahora puedes abrir tu navegador y escribir: http://taskcore
echo ======================================================================
echo.
pause
