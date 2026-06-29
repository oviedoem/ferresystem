# AGENTS.md — FerreSystem
# Instrucciones del agente — plataforma SaaS multi-tenant ERP-agnóstica
# Versión activa: v0.1 (esqueleto inicial)

---

## REGLA #0 — Separación estricta entre motor y cliente

Este proyecto nace como generalización de la solución de Ferretería Oviedo
El Manzano. **Nunca** mezclar lógica o datos de un cliente específico con
el motor genérico:
- `core/` y `paneles/` no deben conocer el nombre, bodegas, ERP ni
  credenciales de ningún cliente real.
- Toda particularidad de un cliente vive en `tenants/{tenant_id}.json` y
  `branding/{tenant_id}/`.
- Si una función necesita "saber" algo de un cliente, ese dato debe venir
  por parámetro/config, nunca hardcodeado.

## REGLA #1 — Nunca hardcodear tenant_id, bodegas ni credenciales

Ningún archivo en `core/`, `adapters/`, `pipeline/` o `paneles/` debe
contener un `tenant_id`, nombre de bodega, IP, usuario o password literal.
Si aparece un valor así durante el desarrollo, es señal de que falta un
parámetro de configuración — agregarlo a `tenants/ejemplo_tenant.json` y
leerlo desde ahí.

## REGLA #2 — Todo dato de cliente va en tenants/{id}.json, nunca en código

Cualquier dato propio de un cliente (ERP, bodegas, branding, Firebase,
horarios de sync) se declara en `tenants/{tenant_id}.json`. Los archivos
reales de tenants **no se commitean** (ver `.gitignore`) — solo el
template `tenants/ejemplo_tenant.json`.

---

## SAFE CHANGE PROTOCOL

**Un prompt = una función tocada.** Si el fix requiere 2 funciones → dos
prompts separados. Si el agente dice "también modifiqué X para que
funcione" sin pedírselo → DETENER y revisar X.

### Antes de cualquier cambio de código

```
TOCO:        [función exacta]
ARCHIVO:     [archivo específico]
RAZÓN:       [una línea]
NO TOCO:     [qué queda igual y por qué]
```

### Cuándo aplicar SIEMPRE

- Modificar cualquier método de un `ERPAdapter` (`core/erp_adapter.py` o
  cualquier archivo en `adapters/`)
- Modificar `core/pipeline_runner.py`, `core/json_writer.py` o
  `core/validator.py` (afectan a todos los tenants a la vez)
- Modificar cualquier panel en `paneles/` (afecta a todos los clientes
  que usan ese panel white-label)
- Agregar un campo nuevo a `tenants/ejemplo_tenant.json` (requiere
  actualizar también `docs/como_agregar_cliente.md`)

---

## SEGURIDAD

- Nunca guardar archivos del proyecto en `C:` (proyecto en `E:\ferresystem\`)
- Nunca subir credenciales, IPs reales ni tokens de ningún cliente a git
- `tenants/*.json` reales y cualquier clave de servicio Firebase quedan
  fuera del repo (ver `.gitignore`)
- Este proyecto es independiente del proyecto Ferretería Oviedo
  (`E:\ferreteria-oviedo\`) — no se modifica ese proyecto desde aquí, y no
  se copian datos reales de producción de Oviedo a este repo.

---

## ESTRUCTURA DEL PROYECTO

Ver `README.md` y `docs/arquitectura.md` para el detalle de capas
(tenants → adapters → core → data → paneles).

## HISTORIAL

- v0.1 — Esqueleto inicial: estructura de carpetas, contrato `ERPAdapter`,
  validador y rotación de token genéricos (adaptados de Ferretería
  Oviedo), landing page, sin lógica de negocio de ningún cliente real.
