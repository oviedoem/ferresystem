# CLAUDE.md — FerreSystem
# Cargado automáticamente al inicio de cada sesión de Claude Code.

## LEER OBLIGATORIO ANTES DE CUALQUIER TAREA

1. Leer `AGENTS.md` (reglas de separación motor/cliente, Safe Change Protocol)
2. Leer `docs/arquitectura.md` para entender el diseño actual
3. Recién después ejecutar cualquier tarea

---

## STACK Y DIRECTORIO

- **Proyecto activo:** `E:\ferresystem\` — trabajar SIEMPRE aquí
- **Versión activa:** v0.1 (esqueleto — sin lógica de negocio real aún)
- **Stack:** Python (core + pipeline) · HTML/CSS/JS Vanilla (paneles white-label) · Firebase Hosting
- **Git:** `E:\git-portable\mingw64\bin\git.exe`

## ESTRUCTURA

```
core/        — motor genérico (adapters, pipeline_runner, validator, logger)
adapters/    — un adaptador por ERP soportado (NUNCA datos de cliente)
tenants/     — configuración por cliente en JSON (NUNCA se commitea el real)
pipeline/    — scripts sincronización ERP → JSON → Firebase
paneles/     — HTML white-label (admin / vendedor / cliente)
branding/    — assets por cliente
setup/       — onboarding cliente nuevo
docs/        — arquitectura, guías agregar cliente/ERP
```

## REGLAS CRÍTICAS

### Separación motor / cliente (REGLA #0)
- `core/` y `paneles/` NUNCA conocen nombre, bodegas, ERP ni credenciales de ningún cliente
- Toda particularidad de cliente vive en `tenants/{tenant_id}.json`
- Si una función necesita dato de cliente → debe llegar por parámetro/config, nunca hardcodeado

### Nunca hacer esto
- Hardcodear tenant_id, bodegas, IPs, usuarios o passwords en ningún archivo de `core/`, `adapters/`, `pipeline/` o `paneles/`
- Commitear archivos reales de tenants (solo `tenants/ejemplo_tenant.json`)
- Mezclar lógica específica de Ferretería Oviedo u otro cliente con el motor genérico
- Modificar `core/pipeline_runner.py`, `core/json_writer.py` o `core/validator.py` sin declarar alcance (afectan a todos los tenants)

### Antes de cualquier cambio de código
```
TOCO:        [función exacta]
ARCHIVO:     [archivo específico]
RAZÓN:       [una línea]
NO TOCO:     [qué queda igual y por qué]
```

### Al agregar campo a ejemplo_tenant.json
Actualizar también `docs/como_agregar_cliente.md` — siempre juntos.

---

## REFERENCIA CLAVE FERRETERÍA OVIEDO (solo lectura)
El código de referencia real del primer tenant vive en `E:\ferreteria-oviedo\`.
Solo leer para inspiración — nunca copiar credenciales, IPs ni tokens.

---

## HISTORIAL DE SESIONES

### Sesión 2026-08-22 (Claude Code) — validar_tenant_config + fix test flaky scheduler

**Resumen:** Loop sesión Pasos 0–5. Añadida validación de configuración de tenant antes del pipeline. Fix del test `test_proxima_hoy_si_falta` que fallaba en CI por depender de la hora real.

**Hecho:**
- `core/validator.py`: `validar_tenant_config(config: dict) -> bool` — valida campos raíz y `erp.tipo`; CLI `--tenant`
- `tenants/ejemplo_tenant.json`: `erp.tipo` corregido a `"bsale"` + campo `_tipo_opciones`
- `tests/test_scheduler.py`: mock `datetime.now()` con tiempo fijo en `test_proxima_hoy_si_falta`
- PR #25 mergeado · CI verde Python 3.10/3.11/3.12

**Pendiente:** ninguno

**Próxima sesión:** ver backlog en AGENTS.md (adapter funcional, panel datos reales)
