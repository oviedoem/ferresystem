@echo off
REM ACTUALIZAR_TODO.bat — Pipeline generico FerreSystem
REM Uso: ACTUALIZAR_TODO.bat <tenant_id>
REM
REM Pasos:
REM   1 - Descarga ERP y genera JSONs en data\{tenant_id}\
REM   2 - Valida los JSONs antes del deploy
REM   3 - Rota token de archivos sensibles (requiere Firebase configurado)
REM   4 - Firebase Hosting deploy al proyecto del tenant

setlocal enabledelayedexpansion

set TENANT=%1
if "%TENANT%"=="" (
    echo.
    echo  Uso: ACTUALIZAR_TODO.bat ^<tenant_id^>
    echo  Ej:  ACTUALIZAR_TODO.bat ferreteria-cliente
    echo.
    exit /b 1
)

echo.
echo ================================================
echo  FerreSystem -- Pipeline de actualizacion
echo  Tenant: %TENANT%
echo ================================================
echo.

REM --- PASO 1: Descargar ERP y generar JSONs ---
echo [1/4] Descargando ERP y generando JSONs...
python pipeline\descargar_erp.py %TENANT%
if errorlevel 1 (
    echo [ERROR] Paso 1 fallido. Abortando.
    exit /b 1
)
echo [OK] Paso 1 completado.
echo.

REM --- PASO 2: Validar JSONs generados ---
echo [2/4] Validando JSONs...
python pipeline\generar_jsons.py %TENANT%
if errorlevel 1 (
    echo [ERROR] Paso 2 fallido -- JSONs invalidos. Abortando deploy.
    exit /b 1
)
echo [OK] Paso 2 completado.
echo.

REM --- PASO 3: Rotar token de archivos sensibles ---
REM Requiere: service-account JSON del tenant y firebase-admin instalado.
REM Descomentar y ajustar la ruta del config cuando Firebase este activo:
REM
REM echo [3/4] Rotando token...
REM python pipeline\rotar_token.py tenants\%TENANT%-rotar.json
REM if errorlevel 1 (echo [ERROR] Paso 3 fallido. && exit /b 1)
REM echo [OK] Paso 3 completado.
echo [3/4] Rotacion de token: omitida (ver comentario en ACTUALIZAR_TODO.bat).
echo.

REM --- PASO 4: Firebase Hosting deploy ---
echo [4/4] Publicando en Firebase Hosting...
firebase deploy --project %TENANT%
if errorlevel 1 (
    echo [ERROR] Paso 4 fallido.
    echo         Verifica que la Firebase CLI este instalada (npm install -g firebase-tools)
    echo         y autenticada (firebase login).
    exit /b 1
)
echo [OK] Paso 4 completado.
echo.

echo ================================================
echo  Pipeline completado: %TENANT%
echo ================================================
echo.
endlocal
