# FerreSystem

Plataforma SaaS multi-tenant, ERP-agnóstica, para ferreterías y comercios
similares. Nace como generalización de la solución desarrollada para
Ferretería Oviedo El Manzano, separando lo específico de un cliente (ERP,
bodegas, branding) de un motor genérico reutilizable.

## Estado

v0.1 — esqueleto inicial. Sin lógica de negocio de ningún cliente real.

## Estructura

- `core/` — motor genérico (adapters, pipeline runner, validador, logger)
- `adapters/` — un adaptador por ERP soportado
- `tenants/` — configuración por cliente (JSON, nunca código)
- `pipeline/` — scripts de sincronización ERP → JSON → Firebase
- `paneles/` — HTML white-label (admin / vendedor / cliente)
- `branding/` — assets por cliente
- `setup/` — onboarding de cliente nuevo
- `docs/` — documentación de arquitectura y extensión
- `landing/` — sitio de venta del servicio

Ver `AGENTS.md` para las reglas obligatorias antes de tocar código.
