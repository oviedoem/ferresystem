# Cómo agregar un ERP nuevo

## 1. Crear el adaptador

Nuevo archivo en `adapters/{nombre}_adapter.py`, clase que hereda de
`core.erp_adapter.ERPAdapter`.

## 2. Implementar los 5 métodos abstractos

`get_productos()`, `get_stock()`, `get_ventas(desde, hasta)`,
`get_pedidos()`, `test_conexion()`. Cada uno debe devolver instancias de
las dataclasses genéricas (`Producto`, `Stock`, `Venta`, `Pedido`) —
nunca estructuras propias del ERP.

## 3. Registrar en pipeline_runner.py

Agregar la clase a `ADAPTERS_DISPONIBLES` en `core/pipeline_runner.py`
con la misma clave que usará `tenants/{id}.json -> erp.tipo`.

## 4. Probar con test_conexion()

Antes de correr el pipeline completo, validar que `test_conexion()`
devuelve `True` contra el ERP real del cliente piloto.

## 5. Agregar al tenant.json

En `tenants/{id}.json`, setear `erp.tipo` al nombre registrado en el
paso 3, y completar host/puerto/usuario/password_enc.
