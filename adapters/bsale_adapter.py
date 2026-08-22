"""
bsale_adapter.py — Adaptador para Bsale (API REST v1/v2 chilena).

Refactorizado v0.2: usa core/http_client.py para eliminar duplicación
de código HTTP, retry y rate limiting.

Documentación: https://developer.bsale.cl/
"""
from typing import List, Optional
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido
from core.http_client import HTTPClient
from core.logger import get_logger

log = get_logger("bsale_adapter")

_PAGE_SIZE = 25  # Bsale default page size


class BsaleAdapter(ERPAdapter):
    """Adaptador para Bsale via API REST.

    Configuración esperada en tenant.json → erp:
      access_token : str  — API key del tenant
      office_ids   : list[int] — IDs de sucursales/bodegas a filtrar
      precio_tipo_id : int | None — tipo de precio (default: None = todos)
      api_version  : str  — "1" o "2" (default "1")
      timeout      : int  — segundos (default 30)
      max_paginas  : int  — límite de páginas (default 50)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._token = config["access_token"]
        self._office_ids = [int(x) for x in config.get("office_ids", [])]
        self._precio_tipo_id = config.get("precio_tipo_id")
        version = config.get("api_version", "1")
        self._base = f"https://api.bsale.cl/v{version}"
        self._max_pag = int(config.get("max_paginas", 50))

        self._client = HTTPClient(
            base_url=self._base,
            timeout=int(config.get("timeout", 30)),
            max_retries=3,
            backoff_base=2.0,
            rate_limit_delay=0.5,
            default_headers={
                "access_token": self._token,
                "Content-Type": "application/json",
            },
        )

    def _paginar(self, path: str, params: Optional[dict] = None) -> List[dict]:
        """Itera paginación de Bsale (limit/offset)."""
        params = dict(params or {})
        params["limit"] = _PAGE_SIZE
        todos = []
        offset = 0

        for _ in range(self._max_pag):
            params["offset"] = offset
            resp = self._client.get(path, params=params)
            items = resp.get("items", [])
            if not items:
                break
            todos.extend(items)
            if len(items) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        return todos

    @staticmethod
    def _fecha(timestamp: Optional[int]) -> str:
        """Convierte timestamp Unix a fecha ISO (YYYY-MM-DD)."""
        if not timestamp:
            return ""
        from datetime import datetime, timezone
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    def test_conexion(self) -> bool:
        try:
            resp = self._client.get("/products.json", params={"limit": 1})
            ok = "items" in resp
            log.info("test_conexion: %s", "OK" if ok else "SIN DATA")
            return ok
        except Exception as e:
            log.error("test_conexion falló: %s", e)
            return False

    def get_productos(self) -> List[Producto]:
        docs = self._paginar("/products.json")
        productos = []
        for doc in docs:
            nombre_base = doc.get("name", "")
            marca = doc.get("brand", "") or ""
            variants = doc.get("variants", {}).get("items", [])
            for var in variants:
                codigo = var.get("code", "")
                if not codigo:
                    continue
                desc = var.get("description", "")
                descripcion = f"{nombre_base} — {desc}" if desc else nombre_base
                costs = var.get("costs", {}).get("items", [])
                precio = 0.0
                if costs:
                    precio = float(costs[0].get("cost", 0))
                productos.append(Producto(
                    codigo=codigo,
                    descripcion=descripcion,
                    marca=marca or None,
                    precio=precio if precio > 0 else None,
                    activo=bool(var.get("state", 1)),
                ))
        log.info("get_productos: %d artículos", len(productos))
        return productos

    def get_stock(self) -> List[Stock]:
        docs = self._paginar("/stocks.json")
        stock = []
        for s in docs:
            office_id = s.get("officeId")
            if self._office_ids and office_id not in self._office_ids:
                continue
            codigo = s.get("variantCode", "")
            if not codigo:
                continue
            stock.append(Stock(
                codigo=codigo,
                bodega=s.get("officeName", str(office_id)) if office_id else "Principal",
                cantidad=float(s.get("quantityAvailable", 0)),
            ))
        log.info("get_stock: %d líneas (office_ids: %s)", len(stock), self._office_ids or "todas")
        return stock

    def get_ventas(self, desde: str, hasta: str) -> List[Venta]:
        docs = self._paginar("/documents.json", params={
            "expand": "details,office",
            "state": 0,
        })
        ventas = []
        for doc in docs:
            fecha_ts = doc.get("generationDate")
            fecha = self._fecha(fecha_ts)
            if not (desde <= fecha <= hasta):
                continue
            vendedor = doc.get("user", {}).get("firstName", "") + " " + doc.get("user", {}).get("lastName", "")
            vendedor = vendedor.strip() or None
            cliente = doc.get("client", {}).get("code", "") or None
            for linea in doc.get("details", {}).get("items", []):
                codigo = linea.get("variantCode", "")
                if not codigo:
                    continue
                ventas.append(Venta(
                    fecha=fecha,
                    codigo=codigo,
                    descripcion=linea.get("variantName", "") or codigo,
                    cantidad=float(linea.get("quantity", 0)),
                    precio=float(linea.get("netUnitValue", 0)),
                    vendedor=vendedor,
                    cliente=cliente,
                ))
        log.info("get_ventas (%s→%s): %d líneas", desde, hasta, len(ventas))
        return ventas

    def get_pedidos(self) -> List[Pedido]:
        docs = self._paginar("/purchase_orders.json", params={
            "state": "pending",
            "expand": "details,supplier",
        })
        pedidos = []
        for po in docs:
            numero = str(po.get("number", po.get("id", "")))
            if not numero:
                continue
            proveedor = po.get("supplier", {}).get("name", "")
            lineas = []
            for l in po.get("details", {}).get("items", []):
                lineas.append({
                    "codigo": l.get("variantCode", ""),
                    "descripcion": l.get("variantName", "") or l.get("description", ""),
                    "cantidad": float(l.get("quantity", 0)),
                })
            pedidos.append(Pedido(
                numero=numero,
                fecha=self._fecha(po.get("generationDate")),
                proveedor=proveedor,
                lineas=lineas,
            ))
        log.info("get_pedidos: %d órdenes", len(pedidos))
        return pedidos
