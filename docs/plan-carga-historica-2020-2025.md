# Plan de carga histórica 2020–2025

## Objetivo

Bajar 6 años de historia (2020-01 → 2025-12) del ERP del tenant piloto a la
base SQLite del tenant (`data/{tenant}/{tenant}.db`, ver `docs/modelo-datos.md`),
para poder **trabajar, analizar y enriquecer** los proyectos con datos reales
de largo plazo — la materia prima de los servicios de análisis.

Aplica a cualquier tenant cuyo ERP exponga historia (SQL directo, SSRS o
exportes); el piloto es el tenant ferretería con adapter JustWeb.

## Principios

- **Solo lectura contra el ERP** — la carga jamás escribe en la base de origen.
- **Reanudable** — la unidad de trabajo es el mes (`sync_log` registra cada
  mes cargado). Un corte de VPN no obliga a partir de cero.
- **Idempotente** — recargar un mes ya cargado no duplica filas
  (`INSERT OR REPLACE` + claves únicas `tipo_doc + numero`).
- **Verificable** — cada mes cargado se valida contra el conteo de origen antes
  de marcarse OK.
- **Fuera de horario** — la carga histórica corre de noche o fin de semana para
  no competir con el uso normal del ERP; el sync del proveedor (22:00 en el
  piloto) no afecta la historia, que es inmutable.

## Paso a paso

### Fase 0 — Preparación (una vez)

1. Aplicar el DDL de `docs/modelo-datos.md` → crea el `.db` vacío del tenant.
2. Verificar acceso al ERP con `test_conexion()` del adapter (VPN activa,
   credenciales desde el config del tenant — nunca en el repo).
3. Confirmar en el origen los años realmente disponibles:
   `SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM <tabla documentos>` — si el
   proveedor purgó años antiguos, el plan parte del primer año existente.

### Fase 1 — Dimensiones (una corrida, ~minutos)

Orden obligatorio (las tablas de hechos referencian a estas):

1. `productos` — catálogo completo, incluidos códigos inactivos (aparecen en
   ventas antiguas).
2. `entidades` — clientes y proveedores con RUT, razón social y sector.
3. `vendedores` — incluidos los que ya no trabajan (firman ventas históricas).
4. `bodegas` — todas las bodegas del tenant, con su tipo.

### Fase 2 — Documentos históricos (la carga grande)

Por cada mes de `2020-01` a `2025-12` (72 lotes):

1. ¿`sync_log` tiene el mes con `ok=1`? → saltar (reanudable).
2. Descargar encabezados del mes (ventas, NC, guías según los tipos de
   documento del tenant) + sus líneas.
3. Insertar en `documentos` + `documento_lineas` (transacción por mes:
   o entra el mes completo o no entra nada).
4. Validar: `COUNT(*)` local del mes == `COUNT(*)` en el origen.
5. Registrar en `sync_log` (mes, filas, ok, timestamp).

Estimación para un comercio mediano: 40–50 mil líneas de venta/año →
~300 mil filas totales → **la base completa queda bajo 500 MB**. Cabe en el
disco de trabajo actual; no se necesita hardware adicional.

### Fase 3 — Pedidos/OC históricos

Mismo esquema mensual que Fase 2, sobre `pedidos` + `pedido_lineas`. Si el ERP
solo conserva OCs recientes, se carga lo disponible y se registra el límite en
`sync_log`.

### Fase 4 — Stock

El stock histórico normalmente **no existe** en el ERP (solo hay foto actual).
Por eso `stock_snapshot` empieza a poblarse **desde hoy**, una foto por día en
el pipeline nocturno. En 6–12 meses el tenant tiene historia de stock propia —
otro dato que ningún ERP local le entrega y que vale como servicio.

### Fase 5 — Validación de cierre

1. Totales por año local vs origen (neto y cantidad de documentos): deben calzar.
2. Muestreo: 5 documentos al azar por año comparados línea a línea.
3. Registrar resumen de la carga en el doc de estado del tenant.

### Fase 6 — Régimen incremental

Terminada la histórica, el pipeline nocturno agrega solo el día/mes en curso
(mismo script, `sync_log` decide qué falta). Desde aquí:

- Los JSON del panel pueden regenerarse **desde la base** sin tocar el ERP.
- Cualquier análisis nuevo (menús del panel, reportes, modelos IA) consulta
  la base local, no el ERP.

## Script a construir

`pipeline/cargar_historico.py` (nuevo, genérico):

```
uso: python cargar_historico.py <tenant_id> --desde 2020-01 --hasta 2025-12
```

- Usa el adapter del tenant (`get_ventas(desde, hasta)` ya existe en el
  contrato `ERPAdapter`) — no requiere tocar `core/`.
- Escribe vía el futuro `core/db_writer.py`.
- Log por mes a consola + `sync_log`.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Corte de VPN a mitad de carga | Transacción por mes + `sync_log` → se reanuda |
| Timeout en meses grandes (dic.) | Bajar el lote a quincena solo para ese mes |
| Origen purga años antiguos | Fase 0 detecta el rango real antes de prometer 2020 |
| Datos sucios (RUT vacío, código huérfano) | FK laxas (LEFT JOIN en vistas) + reporte de huérfanos post-carga |
| Carga pesada en horario laboral | Correr 22:30+ o fin de semana |
