---
name: loop-sesion
description: "Guía la sesión a través del Loop 0-5: Arrancar → Abrir → Alinear → Ejecutar → Validar → Cerrar. Invocar al inicio (/loop-sesion 0) o para el siguiente paso (/loop-sesion N). TRIGGER: usuario dice 'empecemos', 'inicio sesión', 'arrancar', 'loop', 'qué sigue'."
---

# Skill: Loop de Sesión (0-5) — Motor FerreSystem

El agente trabaja en ciclos. Cada sesión sigue estos 6 pasos en orden.
Invocar `/loop-sesion [N]` para ejecutar ese paso. Sin número → mostrar estado actual.

---

## PASO 0 — ARRANCAR
*Cargar estado. No ejecutar nada todavía.*

1. `git log --oneline -5` — ver últimos cambios
2. Identificar pendientes de la sesión anterior (CLAUDE.md o PR abiertos)
3. Leer CRITERIO.md — activar el "cerebro" para esta sesión

```
ESTADO:
- Último cambio: [commit message]
- Pendiente anterior: [item]
- Propuesta para hoy: [tarea candidata]
```

---

## PASO 1 — ABRIR
*Definir el alcance. Una tarea por sesión.*

1. Usuario declara (o el agente propone) la tarea
2. Filtrar con CRITERIO.md:
   - ¿El cambio toca `core/`? → verificar que no hardcodea datos de cliente
   - ¿Afecta `pipeline_runner.py`, `json_writer.py` o `validator.py`? → invocar `/debate` primero
   - ¿Es un cambio pequeño y claro? → ir al Paso 2

```
SESIÓN DE HOY:
Tarea: [una línea]
Alcance: [qué entra] / [qué NO entra]
Archivos: [lista]
Tenants afectados: [todos | solo ejemplo | ninguno]
```

---

## PASO 2 — ALINEAR
*Acordar antes de escribir código.*

```
TOCO:    [función exacta]
ARCHIVO: [core/... | adapters/... | tenants/...]
RAZÓN:   [una línea]
NO TOCO: [qué queda igual]
```

Confirmar reglas CRITERIO.md:
- ¿El cambio en `core/` hardcodea algún dato de cliente?
- ¿El cambio en `tenants/` solo toca `ejemplo_tenant.json`?
- ¿El cambio en `docs/` refleja lo que cambia en `ejemplo_tenant.json`?

**El usuario aprueba antes de pasar al Paso 3.**

---

## PASO 3 — EJECUTAR
*Hacer el trabajo. Un cambio a la vez.*

- Aplicar solo lo declarado en Paso 2
- Si aparece algo adicional → pausar, registrar, no tocar
- Usar `/caveman` si el código resultante es más complejo de lo necesario
- Usar `/disenar-adapter` si se agrega soporte de un nuevo ERP

---

## PASO 4 — VALIDAR
*Probar antes de declarar listo.*

| Tipo de cambio | Validación |
|---|---|
| Python | `python -m py_compile [archivo]` |
| Adapter nuevo | `python core/pipeline_runner.py --tenant ejemplo --dry-run` |
| JSON schema | Validar contra `tenants/ejemplo_tenant.json` |
| Docs | Verificar que `docs/como_agregar_cliente.md` refleja el cambio |

Si falla → volver al Paso 3.

---

## PASO 5 — CERRAR

```bash
git add [archivos del alcance]
git status  # verificar sin archivos inesperados
git commit -m "[tipo]: [descripción]"
git push -u origin claude/claude-codex-os-system-hxard7
```

Si se tocó `tenants/ejemplo_tenant.json` → también actualizar `docs/como_agregar_cliente.md`.

```
CIERRE:
Commit: [hash]
Hecho: [una línea]
Pendiente: [lista]
Próxima sesión: [primera acción]
```

---

## Reglas del loop

- No saltar pasos — `core/` es compartido por todos los tenants; un error afecta a todos
- No acumular scope — lo nuevo va al backlog, no a este loop
- El Paso 5 es obligatorio — un cambio sin commit no existió
