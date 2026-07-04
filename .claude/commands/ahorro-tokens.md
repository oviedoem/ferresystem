---
description: Comprime el contexto de la sesión y reporta estado del proyecto sin abrir archivos innecesarios.
---

## Ahorro de tokens — Ferretería Oviedo

Ejecuta este protocolo para reducir uso de contexto:

### 1. Reportar estado conciso

Sin leer archivos, responde:
- ¿Qué se ha cambiado en esta sesión? (archivos tocados)
- ¿Qué queda pendiente?
- ¿Qué archivos de datos están actualizados? (revisar timestamps solo si es necesario)

### 2. Compresión de contexto

- No leer AGENTS.md ni CLAUDE.md si ya están en contexto
- No releer archivos ya leídos — usar lo que ya está en memoria de sesión
- Para diagnósticos de pipeline: leer solo la sección relevante del log, no el log completo
- Para panel-admin.html: usar Grep en lugar de Read completo

### 3. Reglas de uso mínimo

Al buscar algo en el código:
1. Primero Grep → si encuentra el resultado exacto, no usar Read
2. Si necesita contexto: Read con offset+limit exactos (no todo el archivo)
3. Un solo PowerShell para múltiples verificaciones (no commands separados)

### 4. Estado rápido del proyecto

Para ver qué datos están actualizados:
```powershell
Get-ChildItem "E:\ferreteria-oviedo\data" -Filter "*.json" | Where-Object { $_.Name -match "ventas|recepciones|despachos|informe|pedidos" } | Sort-Object LastWriteTime -Descending | Select-Object Name, LastWriteTime, @{N="KB";E={[math]::Round($_.Length/1KB,1)}} | Format-Table -AutoSize
```

Reporta el resultado sin análisis adicional si el usuario solo quiere saber el estado.

### 5. Cuándo aplicar automáticamente

- Si el contexto supera 80% de capacidad → aplicar reglas 2 y 3 automáticamente
- Si se va a leer un archivo > 500 líneas → preguntar al usuario si es necesario
- Si se repite la misma query → usar el resultado anterior del contexto

### 6. Reanudar un plan multi-prompt entre sesiones (Safe-Change activo)

Cuando el usuario diga "continúa con el plan" o referencie un plan guardado en memory/:

1. Leer el `estado-sesion-YYYYMMDD*.md` más reciente en memory/ (ya indicado en CLAUDE.md) — ahí está la lista exacta de prompts hechos/pendientes. NO releer todo el historial de chat ni archivos ya descritos en ese estado.
2. Activar automáticamente, sin pedirlo, el **Safe-Change Protocol** de AGENTS.md (TOCO/ARCHIVO/RAZÓN/LLAMADA POR/LLAMA A/VARIABLES/TABS/NO TOCO) antes de tocar cualquier función — un prompt = una función.
3. Ejecutar los prompts pendientes en el orden listado en el estado de sesión, uno a la vez, con su checklist post-cambio. No reabrir archivos completos si el estado de sesión ya describe la función exacta y su ubicación (línea aprox.) — usar Grep/Read con offset dirigido.
4. Probar cada cambio en preview (mock de `window.db`, no login real) antes de pasar al siguiente prompt.
5. Recién al final del bloque de prompts (o cuando el usuario lo pida): deploy + commit + actualizar versión en AGENTS.md + nuevo estado-sesion.
