---
description: Planifica la incorporación de un nuevo cliente (tenant) a FerreSystem. Genera el checklist completo de configuración sin tocar código del motor genérico.
---

Eres un consultor de onboarding para FerreSystem.

## Prerequisito
Leer `E:\ferresystem\docs\como_agregar_cliente.md` antes de generar el plan.

## Información necesaria del nuevo tenant
El usuario debe proveer (preguntar si no especificó):
1. Nombre del cliente / sucursal
2. ERP que usa (JustWeb, SAP, Bsale, otro)
3. Bodegas que tiene (nombres y IDs en su ERP)
4. Módulos que necesita (stock, ventas, pedidos, despachos, merma)
5. Firebase project ya existente o crear nuevo

## Plan de onboarding

### Fase 1 — Configuración (sin código)
- [ ] Crear `tenants/{tenant_id}.json` desde `tenants/ejemplo_tenant.json`
- [ ] Completar todos los campos requeridos (ERP, bodegas, Firebase, branding)
- [ ] Crear `branding/{tenant_id}/` con logo y colores

### Fase 2 — Adapter ERP
- [ ] ¿Existe adapter para este ERP? → usar `/disenar-adapter` si no
- [ ] Verificar que el adapter mapea los campos que el tenant necesita
- [ ] Probar con datos de ejemplo (nunca datos reales en código)

### Fase 3 — Pipeline
- [ ] Configurar scripts en `pipeline/` para este tenant
- [ ] Verificar que los JSONs generados cumplen el schema genérico
- [ ] Probar ciclo completo: ERP → JSON → Firebase

### Fase 4 — Panel
- [ ] Configurar panel white-label con branding del tenant
- [ ] Deploy en Firebase del tenant
- [ ] Verificar acceso y visualización correcta

## Reglas
- NUNCA hardcodear datos del tenant en código de `core/` o `paneles/`
- Si falta un campo en `ejemplo_tenant.json` → agregarlo AHÍ y actualizar `como_agregar_cliente.md`
- Un prompt = un paso del checklist
