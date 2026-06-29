# Arquitectura — FerreSystem

## Principio rector

Separar lo genérico (motor, panel, validación) de lo específico de cliente
(ERP, bodegas, branding, credenciales). Lo específico vive siempre en datos
(`tenants/{id}.json`), nunca en código.

## Capas

```
tenants/{id}.json          ← config de un cliente (ERP, bodegas, branding, firebase)
        │
        ▼
adapters/{erp}_adapter.py  ← traduce el ERP concreto a las 4 entidades genéricas
        │  (Producto, Stock, Venta, Pedido)
        ▼
core/pipeline_runner.py    ← orquesta: descarga → genera JSON → valida → rota token
        │
        ▼
data/{id}/*.json           ← salida estándar, igual forma para cualquier cliente
        │
        ▼
paneles/*.html             ← UI white-label, lee branding + datos, sin lógica de cliente
```

## Por qué un adapter por ERP

Cada ERP (JustWeb, Transtecnia, Rex Plus, planillas Excel) expone los datos
de forma distinta (SSRS/HTTP, SQL directo, archivos). El resto del sistema
(`core/`, `paneles/`) solo conoce las 4 dataclasses de `core/erp_adapter.py`
(`Producto`, `Stock`, `Venta`, `Pedido`). Agregar un ERP nuevo nunca debería
tocar `core/` ni los paneles — ver `docs/como_agregar_erp.md`.

## Multi-tenant

Un mismo despliegue de código sirve a N clientes. Lo que cambia entre
clientes es exclusivamente:
- `tenants/{id}.json`
- `branding/{id}/`
- el proyecto Firebase de destino

## Seguridad

- Credenciales del ERP: cifradas con DPAPI, fuera del repo.
- JSON de datos sensibles: rotados con `pipeline/rotar_token.py` (carpeta de
  nombre aleatorio + token vigente en Firestore protegido por reglas).
- `tenants/*.json` reales nunca se commitean (ver `.gitignore`), solo el
  template `ejemplo_tenant.json`.
