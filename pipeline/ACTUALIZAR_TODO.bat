@echo off
REM ACTUALIZAR_TODO.bat — Pipeline genérico FerreSystem
REM Uso: ACTUALIZAR_TODO.bat <tenant_id>

REM PASO 1 — Descargar datos del ERP del tenant (pipeline\descargar_erp.py)
REM PASO 2 — Generar JSONs estandar en data\{tenant_id}\ (pipeline\generar_jsons.py)
REM PASO 3 — Validar JSONs antes de publicar (core\validator.py)
REM PASO 3.5 — Rotar token de archivos sensibles (pipeline\rotar_token.py)
REM PASO 4 — firebase deploy --project {firebase.project_id del tenant}

echo TODO: implementar pasos 1-4 para el tenant %1
