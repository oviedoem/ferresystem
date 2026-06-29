# FerreSystem

**Plataforma SaaS multi-tenant ERP-agnóstica para el comercio y servicios en Chile.**

FerreSystem es un motor genérico que conecta cualquier ERP o sistema de gestión con paneles web white-label personalizados por cliente. Extrae datos de ventas, stock, pedidos y RR.HH., los normaliza en un contrato JSON estándar y los sirve en dashboards móviles para admin, vendedor y cliente final. Todo bajo un modelo multi-tenant: un mismo código, múltiples negocios, cero datos cruzados.

---

## ¿Para qué sirve?

La mayoría de los negocios medianos en Chile operan con ERPs locales (JustWeb, Transtecnia, Excel avanzado, etc.) pero no tienen dashboards modernos para su equipo. FerreSystem resuelve eso sin reemplazar el ERP existente: se conecta como capa intermedia, extrae lo que necesita y publica la información en paneles accesibles desde el celular.

---

## Arquitectura general

```
┌──────────────────────────────────────────────────────┐
│                     CLIENTE FINAL                     │
│          panel-cliente.html (white-label)             │
└─────────────────────┬────────────────────────────────┘
                      │ Firebase Hosting / CDN
┌─────────────────────▼────────────────────────────────┐
│              JSONs de salida estándar                 │
│   admin_dashboard.json  ·  stock.json  ·  ventas.json │
└─────────────────────┬────────────────────────────────┘
                      │ pipeline_runner.py
┌─────────────────────▼────────────────────────────────┐
│                  CORE (motor genérico)                │
│   ERPAdapter (ABC)  ·  validator  ·  json_writer      │
└──────┬─────────────────────────────┬─────────────────┘
       │                             │
┌──────▼──────┐               ┌──────▼──────┐
│  adapters/  │               │  adapters/  │
│  ERP local  │               │   RR.HH.    │
│ (JustWeb,   │               │  (Buk, etc.)│
│  Excel...)  │               └─────────────┘
└─────────────┘
```

Cada tenant vive en su propio archivo `tenants/{id}.json` con credenciales cifradas (DPAPI), bodegas, branding y configuración de pipeline. Nunca hay datos de un cliente en el código de otro.

---

## Estructura de carpetas

```
ferresystem/
├── README.md
├── AGENTS.md                    ← reglas para agentes de IA
├── .gitignore
│
├── core/                        ← motor reutilizable
│   ├── erp_adapter.py           ← clase base abstracta ERPAdapter
│   ├── pipeline_runner.py       ← orquestador del pipeline
│   ├── json_writer.py           ← escritor de JSONs estándar
│   ├── validator.py             ← validador de schemas
│   └── logger.py                ← logger centralizado
│
├── adapters/                    ← un archivo por ERP/sistema
│   ├── justweb_adapter.py
│   ├── buk_adapter.py           ← RR.HH. y remuneraciones
│   ├── transtecnia_adapter.py   ← contabilidad / facturación
│   ├── rexplus_adapter.py
│   └── excel_adapter.py         ← fallback universal
│
├── tenants/                     ← un archivo por cliente
│   └── ejemplo_tenant.json
│
├── pipeline/                    ← scripts del pipeline
│   ├── descargar_erp.py
│   ├── generar_jsons.py
│   ├── rotar_token.py
│   └── ACTUALIZAR_TODO.bat
│
├── paneles/                     ← HTML white-label
│   ├── panel-admin.html
│   ├── panel-vendedor.html
│   └── panel-cliente.html
│
├── branding/                    ← assets por cliente
│   └── ejemplo/
│       ├── branding.json
│       └── logo_placeholder.png
│
├── setup/                       ← onboarding nuevo cliente
│   ├── setup_tenant.py
│   └── checklist_instalacion.md
│
├── docs/                        ← documentación técnica
│   ├── arquitectura.md
│   ├── como_agregar_erp.md
│   └── como_agregar_cliente.md
│
└── landing/                     ← página web del producto
    ├── index.html
    └── style.css
```

---

## Adaptadores disponibles

| Adaptador | Sistema | Tipo | Estado |
|---|---|---|---|
| `justweb_adapter.py` | JustWeb | ERP comercial (ventas, stock) | 🟡 Esqueleto |
| `buk_adapter.py` | Buk | RR.HH., remuneraciones, asistencia | 🟡 Esqueleto |
| `transtecnia_adapter.py` | Transtecnia | Contabilidad, facturación electrónica | 🟡 Esqueleto |
| `rexplus_adapter.py` | Rex+ | Remuneraciones alternativo | 🟡 Esqueleto |
| `excel_adapter.py` | Excel / CSV | Fallback universal | 🟡 Esqueleto |

Para agregar un nuevo adaptador, ver `docs/como_agregar_erp.md`.

---

## Datos del tenant (`tenants/{id}.json`)

```json
{
  "tenant_id": "nombre-unico-cliente",
  "nombre_comercial": "Ferretería Ejemplo",
  "erp": {
    "tipo": "justweb|transtecnia|rexplus|excel",
    "host": "IP o URL del ERP",
    "puerto": 80,
    "usuario": "usuario_erp",
    "password_enc": "cifrado con DPAPI — nunca texto plano"
  },
  "rrhh": {
    "tipo": "buk",
    "base_url": "https://empresa.buk.cl",
    "api_key_enc": "cifrado con DPAPI"
  },
  "bodegas": {
    "comerciales": ["BOD1", "BOD2"],
    "logisticas": ["BOD3"],
    "bodega_principal": "BOD1"
  },
  "firebase": {
    "project_id": "nombre-proyecto-firebase",
    "hosting_url": "https://nombre.web.app"
  },
  "branding": {
    "nombre_corto": "Ejemplo",
    "color_primario": "#c0392b",
    "color_secundario": "#2c3e50",
    "logo": "branding/ejemplo/logo.png"
  },
  "pipeline": {
    "hora_sync_sql": "22:00",
    "ttl_token_horas": 8
  }
}
```

**Regla de oro:** ningún `tenant_id`, credencial, IP ni configuración va en el código. Todo en este archivo.

---

## Reglas para agentes de IA (AGENTS.md)

Resumen de las reglas que deben respetar todos los agentes antes de tocar código:

- **REGLA #0:** No romper producción. Cambios solo con respaldo previo.
- **REGLA #1:** Nunca hardcodear `tenant_id`, bodegas ni credenciales en el código.
- **REGLA #2:** Todo dato de cliente va en `tenants/{id}.json`, nunca en código.
- **REGLA #3:** Un adaptador por ERP, siempre hereda de `ERPAdapter` (ABC).
- **REGLA #4:** Siempre registrar operaciones en el logger centralizado.
- **REGLA #5:** Documentar todo cambio en `AGENTS.md` o `docs/`.

Ver `AGENTS.md` para el texto completo antes de hacer cualquier modificación.

---

## Instalación rápida (nuevo cliente)

```bash
# 1. Clonar el repositorio
git clone https://github.com/oviedoem/ferresystem
cd ferresystem

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear configuración del cliente
cp tenants/ejemplo_tenant.json tenants/mi-cliente.json
# Editar mi-cliente.json con los datos reales (credenciales cifradas con DPAPI)

# 5. Verificar conexión
python -c "from adapters.justweb_adapter import JustWebAdapter; ..."

# 6. Ejecutar pipeline completo
python pipeline/generar_jsons.py --tenant mi-cliente
```

Ver `setup/checklist_instalacion.md` para el proceso completo de onboarding.

---

## Pipeline de datos

El flujo de datos por cliente es:

```
ERP (SQL/HTTP) → descargar_erp.py → generar_jsons.py → Firebase → panel HTML
                                         ↑
                                    Buk API (RR.HH.)
```

El pipeline se puede automatizar con `ACTUALIZAR_TODO.bat` (Windows Task Scheduler) o cualquier cron. La frecuencia recomendada es:

| Dato | Frecuencia |
|---|---|
| Stock y productos | Cada 2 horas |
| Ventas del día | Cada hora |
| Resumen RR.HH. | Una vez al día (22:00) |
| Token Firebase | Cada 8 horas (rotar_token.py) |

---

## Posibilidad de expansión a otros rubros

FerreSystem fue diseñado para ferreterías pero su motor es **ERP-agnóstico y rubro-agnóstico**. El contrato JSON estándar y el patrón adaptador permiten aplicarlo a cualquier negocio con inventario, personal y ventas. A continuación, el análisis de factibilidad por rubro:

---

### 🛒 Supermercado / Minimarket

**Factibilidad: Alta**

El modelo de negocio es casi idéntico al de una ferretería: productos con código, bodegas, stock en tiempo real, caja/punto de venta y dotación de personal. La única diferencia relevante es el volumen: un supermercado puede tener 10.000–50.000 SKUs versus 2.000–8.000 de una ferretería. El pipeline debe optimizarse para manejar ese volumen sin generar JSONs de más de 10 MB.

Adaptaciones necesarias:
- Agrupación de productos por categoría (perecibles, abarrotes, limpieza, etc.)
- Alertas de quiebre de stock por categoría crítica (leche, pan, etc.)
- Módulo de precios por convenio (mayorista vs. minorista)
- Panel de cliente con lista de compras y precios actualizados

ERP compatibles habituales: Siesa, SAP Business One, Manager, Softland.

---

### 🔧 Servicio técnico de herramientas

**Factibilidad: Alta**

Este rubro tiene una necesidad particular que FerreSystem puede cubrir muy bien: **trazabilidad de órdenes de trabajo**. El panel de cliente necesita mostrar el estado del equipo en reparación, y el panel de admin debe cruzar horas técnico vs. facturación por orden.

Adaptaciones necesarias:
- Nuevo modelo `OrdenTrabajo` en `erp_adapter.py` (número, estado, técnico, diagnóstico, costo estimado)
- Panel de cliente con tracker de estado: Recibido → Diagnóstico → En reparación → Listo → Entregado
- Panel de vendedor enfocado en colas de trabajo por técnico
- Integración con sistemas como Syncrom, ServiceM8 o Excel avanzado

Buk aplica igualmente para la gestión de técnicos (asistencia, comisiones por orden).

---

### 🏪 Almacén / Distribuidora

**Factibilidad: Muy alta**

Es el caso más cercano a ferretería: mismo flujo de stock, pedidos a proveedor, ventas al mostrador. La ventaja adicional es que muchas distribuidoras trabajan con Excel como ERP, y FerreSystem ya tiene `excel_adapter.py` como fallback universal. Sin modificaciones mayores al core.

Adaptaciones necesarias:
- Módulo de rutas de reparto (si distribuye a domicilio)
- Panel de vendedor con lista de pedidos pendientes de despacho
- Alertas de quiebre por producto de alta rotación

Sin cambios al motor central. Solo configuración del `tenant.json` y branding.

---

### 💊 Farmacia

**Factibilidad: Media** (requiere cuidado regulatorio)

El rubro farmacéutico tiene restricciones legales importantes en Chile: control de medicamentos con receta, registro sanitario ISP, trazabilidad de lotes y fechas de vencimiento. El motor central sirve, pero hay campos nuevos obligatorios.

Adaptaciones necesarias:
- Campo `lote` y `fecha_vencimiento` en el modelo `Producto`
- Alertas automáticas de productos próximos a vencer (< 60 días)
- Bloqueo de visualización de medicamentos controlados en panel de cliente
- Integración con sistemas como Farmaloop, Siesa Farma, o Softland
- **No mostrar precio de medicamentos con receta en panel público** (riesgo regulatorio)

El panel de cliente en farmacia sería más acotado: solo disponibilidad de genéricos y OTC (over-the-counter), nunca stock ni precios de controlados.

---

### 🏫 Colegio / Establecimiento educacional

**Factibilidad: Media-baja** (requiere rediseño parcial del modelo de datos)

Un colegio no tiene "ventas" ni "stock" en el sentido convencional. El modelo de datos debe cambiar significativamente: en lugar de `Producto/Stock/Venta`, el core necesita `Alumno/Matrícula/Asistencia/Nota`. Sin embargo, el patrón técnico (adaptador → JSON estándar → panel HTML → Firebase) sigue siendo válido.

Lo que sí aplica directamente:
- Módulo RR.HH. con Buk (profesores, asistentes, administrativos)
- Panel de admin con KPIs de gestión: asistencia docente, horas extra, costo de remuneraciones por nivel
- Automatización de reportes via pipeline

Lo que requiere nuevo diseño:
- Nuevo contrato JSON (`notas.json`, `asistencia_alumnos.json`, `matriculas.json`)
- Nuevos modelos en `erp_adapter.py` (`Alumno`, `Curso`, `Asistencia`, `Nota`)
- Integración con sistemas SIGE (Chile), Junaeb, o plataformas como Alexia/Colegium

**Recomendación:** Si se quiere expandir a educación, crear un submódulo `ferresystem-edu` con su propio set de adaptadores y contratos JSON, en lugar de forzar el modelo comercial actual.

---

## Tabla resumen de expansión

| Rubro | Factibilidad | Cambios al core | Nuevos adaptadores | Restricciones |
|---|---|---|---|---|
| Supermercado | ⭐⭐⭐⭐⭐ Alta | Mínimos (volumen) | SAP B1, Siesa | Volumen de SKUs |
| Almacén / Distribuidora | ⭐⭐⭐⭐⭐ Alta | Ninguno | Excel (ya existe) | Ninguna |
| Servicio técnico | ⭐⭐⭐⭐ Alta | OrdenTrabajo model | Syncrom, ServiceM8 | Ninguna |
| Farmacia | ⭐⭐⭐ Media | Lote, vencimiento | Farmaloop, Softland | ISP, recetas, controlados |
| Colegio | ⭐⭐ Media-baja | Rediseño modelos | SIGE, Colegium, Alexia | MINEDUC, datos alumnos |

---

## Seguridad

- Las credenciales de ERP y sistemas externos **siempre se cifran con DPAPI** antes de guardar en `tenants/`.
- Los JSONs de salida son de **solo lectura** para los paneles: nunca exponen contraseñas ni configuración interna.
- Firebase Security Rules deben estar configuradas para que cada tenant solo lea sus propios datos.
- Nunca subir archivos `tenants/*.json` con datos reales al repositorio. Están en `.gitignore`.

---

## Roadmap

| Versión | Descripción |
|---|---|
| v0.1 | Estructura base, modelos abstractos, tenant template ✅ |
| v0.2 | JustWeb adapter funcional + panel admin con datos reales |
| v0.3 | Buk adapter (RR.HH. + asistencia) integrado en panel admin |
| v0.4 | Panel vendedor con buscador de productos y stock en tiempo real |
| v0.5 | Panel cliente con catálogo y cotización vía WhatsApp |
| v1.0 | Multi-tenant completo: setup automatizado, branding, Firebase |

---

## Contribuir

1. Leer `AGENTS.md` antes de cualquier cambio.
2. Crear rama: `git checkout -b feature/nombre-adaptador`
3. Nunca tocar datos de tenants en producción desde una rama de desarrollo.
4. PR con descripción clara del cambio y el rubro/ERP al que aplica.

---

## Licencia

Uso interno — Ferretería Oviedo / FerreSystem. Todos los derechos reservados.  
Para licenciar a terceros, contactar al equipo de desarrollo.

---

*FerreSystem v0.1 — Motor multi-tenant ERP-agnóstico · Junio 2026*
