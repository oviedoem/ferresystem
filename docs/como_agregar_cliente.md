# Cómo agregar un cliente (tenant) nuevo

Ver checklist operativo completo en `setup/checklist_instalacion.md`.
Resumen técnico:

1. Copiar `tenants/ejemplo_tenant.json` a `tenants/{tenant_id}.json` y
   completar todos los campos (nunca dejar placeholders en producción).
2. Crear `branding/{tenant_id}/branding.json` + logo.
3. Elegir o crear el adapter de ERP correspondiente
   (ver `docs/como_agregar_erp.md` si es uno nuevo).
4. Crear proyecto Firebase y completar el bloque `firebase` del tenant.
5. Correr `setup/setup_tenant.py {tenant_id}`.
6. Correr `pipeline/ACTUALIZAR_TODO.bat {tenant_id}` y validar JSONs.
7. `firebase deploy --project {project_id}`.

Ningún paso debe requerir tocar `core/`, `adapters/` (salvo ERP nuevo) ni
los paneles HTML.
