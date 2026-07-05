# Contrato JSON de salida — FerreSystem

Los paneles white-label y cualquier consumidor externo deben leer
exclusivamente estos archivos. Nunca consultar el ERP directamente
desde el panel.

---

## Estructura de directorios

```
data/
└── {tenant_id}/
    ├── productos.json
    ├── stock.json
    ├── stock_por_codigo.json
    ├── ventas.json
    ├── pedidos.json
    └── rrhh_resumen.json   ← solo si el tenant tiene bloque "rrhh"
```

---

## Envelope estándar (formato "wrapped")

Todos los archivos salvo `stock_por_codigo.json` usan este wrapper:

```json
{
  "generado":  "2026-07-05T14:30:00+00:00",
  "fuente":    "bsale",
  "total":     1240,
  "registros": [ ... ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `generado` | ISO 8601 UTC | Timestamp de generación del archivo |
| `fuente` | string | Clave del ERP origen (`justweb`, `bsale`, `excel`, etc.) |
| `total` | int | Cantidad de registros en el array |
| `registros` | array | Lista de entidades (ver esquemas por archivo) |

---

## productos.json

**Registros:** array de `Producto`

```json
{
  "generado": "...",
  "fuente": "bsale",
  "total": 3200,
  "registros": [
    {
      "codigo":      "TOR-001",
      "descripcion": "Tornillo Heco 6x1\"",
      "marca":       "Heco",
      "precio":      1490.0,
      "activo":      true
    }
  ]
}
```

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `codigo` | string | No | Código único de la variante/SKU |
| `descripcion` | string | No | Nombre y descripción del producto |
| `marca` | string | Sí | Marca o fabricante |
| `precio` | float | Sí | Precio de venta neto (sin IVA) en CLP |
| `activo` | bool | No | `false` si el producto está dado de baja |

---

## stock.json

**Registros:** array de `Stock`

```json
{
  "generado": "...",
  "fuente": "bsale",
  "total": 6400,
  "registros": [
    {
      "codigo":   "TOR-001",
      "bodega":   "Sucursal Central",
      "cantidad": 150.0
    }
  ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo` | string | Código de variante (mismo que en productos) |
| `bodega` | string | Nombre de la bodega/sucursal |
| `cantidad` | float | Unidades disponibles |

Un mismo `codigo` puede aparecer en múltiples filas (una por bodega).

---

## stock_por_codigo.json

Formato **raw dict** (sin envelope) para lookups O(1) desde el panel.

```json
{
  "TOR-001": { "bodega": "Sucursal Central", "cantidad": 150.0 },
  "MAR-002": { "bodega": "Bodega Norte",     "cantidad": 12.0  }
}
```

Cuando un producto tiene stock en varias bodegas, el dict contiene
la última bodega escrita por el pipeline. Para stock multi-bodega
usar `stock.json`.

---

## ventas.json

**Registros:** array de `Venta`. Incluye dos campos extra en el wrapper:

```json
{
  "generado":    "...",
  "fuente":      "bsale",
  "total":       320,
  "fecha_desde": "2026-07-01",
  "fecha_hasta": "2026-07-05",
  "registros": [
    {
      "fecha":       "2026-07-03",
      "codigo":      "TOR-001",
      "descripcion": "Tornillo Heco 6x1\"",
      "cantidad":    10.0,
      "precio":      1490.0,
      "vendedor":    "Pedro",
      "cliente":     "12345678-9"
    }
  ]
}
```

| Campo | Tipo | Nullable | Descripción |
|---|---|---|---|
| `fecha` | YYYY-MM-DD | No | Fecha de emisión del documento |
| `codigo` | string | No | Código de variante vendida |
| `descripcion` | string | No | Descripción de la línea |
| `cantidad` | float | No | Unidades vendidas |
| `precio` | float | No | Precio neto unitario en CLP |
| `vendedor` | string | Sí | Nombre o ID del vendedor |
| `cliente` | string | Sí | RUT u otro identificador del cliente |

---

## pedidos.json

**Registros:** array de `Pedido`

```json
{
  "generado": "...",
  "fuente": "bsale",
  "total": 5,
  "registros": [
    {
      "numero":    "OC-2026-0041",
      "fecha":     "2026-07-01",
      "proveedor": "Distribuidora Heco",
      "lineas": [
        {
          "codigo":      "TOR-001",
          "descripcion": "Tornillo 6x1\"",
          "cantidad":    500.0
        }
      ]
    }
  ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `numero` | string | Número o ID del pedido de compra |
| `fecha` | YYYY-MM-DD | Fecha de creación |
| `proveedor` | string | Nombre del proveedor |
| `lineas` | array | Líneas del pedido (ver sub-tabla) |

**Líneas de pedido:**

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo` | string | Código de variante |
| `descripcion` | string | Descripción del ítem |
| `cantidad` | float | Unidades pedidas |

---

## rrhh_resumen.json

Solo se genera si `tenants/{id}.json` tiene bloque `"rrhh"` y el
tenant usa BukAdapter. Fuente siempre `"buk"`.

```json
{
  "generado": "...",
  "fuente":   "buk",
  "total":    24,
  "registros": [
    {
      "empleado_id":  5,
      "nombre":       "Ana López",
      "cargo":        "Vendedora",
      "departamento": "Ventas",
      "estado":       "activo"
    }
  ]
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `empleado_id` | int | ID interno del empleado en Buk |
| `nombre` | string | Nombre completo |
| `cargo` | string | Título del cargo |
| `departamento` | string | Área o departamento |
| `estado` | string | `"activo"` u otro estado según Buk |

---

## Reglas para consumidores (paneles)

1. **Nunca asumir campos adicionales** — leer solo los documentados aquí.
2. **Siempre verificar `total > 0`** antes de renderizar listas.
3. **Usar `generado` para mostrar** cuándo fue la última sincronización.
4. **`stock_por_codigo.json`** es el archivo correcto para buscar
   stock de un código específico; `stock.json` es para listados.
5. **`ventas.json` puede tener rango acotado** — verificar `fecha_desde`
   y `fecha_hasta` antes de mostrar totales históricos.
