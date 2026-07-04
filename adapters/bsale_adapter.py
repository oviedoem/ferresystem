"""
bsale_adapter.py — Adaptador para Bsale (SaaS POS/ERP chileno, API REST v1).

Bsale expone una API REST documentada en developers.bsale.cl.
Autenticación: header "access_token" con la API key del tenant.
Paginación: parámetro "offset" + campo "count" en la respuesta.
Todos los montos en Bsale vienen como enteros (centavos no — CLP sin decimales).

Nada de este archivo conoce datos de ningún cliente real.
Todo viene de tenant_config["erp"] (tenants/{id}.json → "erp").

Campos requeridos en tenant_config["erp"]:
    access_token   : API key de Bsale del tenant (sin esquema, solo el token)
    office_ids     : list[int] — IDs de las sucursales/bodegas a consultar
                     (equivalente a "bodegas" en otros adapters)

Campos opcionales:
    api_version    : str — versión de la API (default "1")
    timeout        : int — segundos de espera HTTP (default 30)
    max_paginas    : int — límite de páginas por endpoint (default 50, ~2500 registros)
    precio_tipo_id : int — ID del tipo de precio a usar como precio de venta
                     (si no se especifica se usa el primero disponible)
"""
import json
import urllib.request
import urllib.parse
import urllib.error
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido
from core.logger import get_logger

log = get_logger("bsale_adapter")

_BASE = "https://api.bsale.cl/v{version}"
_PAGE_SIZE = 50  # límite por página que acepta Bsale


class BsaleAdapter(ERPAdapter):
    """Adaptador para Bsale via API REST.

    Implementa el contrato ERPAdapter mapeando los endpoints de Bsale
    a las 4 entidades genéricas (Producto, Stock, Venta, Pedido).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._token      = config["access_token"]
        self._office_ids = [int(x) for x in config.get("office_ids", [])]
        version          = config.get("api_version", "1")
        self._base       = _BASE.format(version=version)
        self._timeout    = int(config.get("timeout", 30))
        self._max_pag    = int(config.get("max_paginas", 50))
        self._precio_tid = config.get("precio_tipo_id")  # None = primer tipo

    # -----------------------------------------------------------------------
    # Helpers privados
    # -----------------------------------------------------------------------

    def _get(self, path: str, params: dict = None) -> dict:
        """GET autenticado a la API de Bsale. Devuelve el JSON como dict."""
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        log.debug(f"GET {url}")
        req = urllib.request.Request(url, headers={
            "access_token": self._token,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error(f"HTTP {e.code} en {url}: {body[:200]}")
            raise
        except urllib.error.URLError as e:
            log.error(f"URLError en {url}: {e.reason}")
            raise

    def _paginar(self, path: str, params: dict = None) -> list[dict]:
        """Itera sobre todas las páginas de un endpoint paginado de Bsale.

        Bsale devuelve { count, limit, offset, items: [...] }.
        Detiene cuando items está vacío o se alcanza max_paginas.
        """
        params = dict(params or {})
        params["limit"] = _PAGE_SIZE
        params["offset"] = 0
        todos = []

        for pagina in range(self._max_pag):
            params["offset"] = pagina * _PAGE_SIZE
            resp = self._get(path, params)
            items = resp.get("items") or []
            todos.extend(items)
            if len(items) < _PAGE_SIZE:
                break  # última página

        return todos

    @staticmethod
    def _fecha(ts) -> str:
        """Convierte timestamp Unix (int) a ISO date YYYY-MM-DD."""
        if not ts:
            return ""
        import datetime
        try:
            return datetime.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except Exception:
            return str(ts)

    @staticmethod
    def _precio_neto(precio_bruto: float, tasa_iva: float = 0.19) -> float:
        """Convierte precio bruto (con IVA) a neto."""
        if not precio_bruto:
            return 0.0
        return round(precio_bruto / (1 + tasa_iva), 2)

    # -----------------------------------------------------------------------
    # Métodos públicos (contrato ERPAdapter)
    # -----------------------------------------------------------------------

    def test_conexion(self) -> bool:
        """Consulta /products.json?limit=1 para verificar credenciales."""
        try:
            resp = self._get("/products.json", {"limit": 1})
            ok = "items" in resp
            log.info(f"test_conexion: {'OK' if ok else 'SIN ITEMS'}")
            return ok
        except Exception as e:
            log.error(f"test_conexion falló: {e}")
            return False

    def get_productos(self) -> list[Producto]:
        """Descarga el catálogo de productos desde /products.json.

        Bsale devuelve cada producto con sus variantes y tipos de precio.
        Se usa el tipo de precio configurado en precio_tipo_id, o el primero
        disponible si no está configurado.
        """
        items = self._paginar("/products.json", {"state": 1})  # state=1 activos
        productos = []
        for p in items:
            for variante in (p.get("variants", {}).get("items") or []):
                codigo = variante.get("code") or str(variante.get("id", ""))
                if not codigo:
                    continue

                # Precio: buscar el tipo configurado o tomar el primero
                precio = None
                costs = variante.get("costs", {}).get("items") or []
                if costs:
                    if self._precio_tid:
                        match = next((c for c in costs if c.get("variantCostType", {}).get("id") == self._precio_tid), None)
                        precio = float(match["cost"]) if match else float(costs[0].get("cost", 0))
                    else:
                        precio = float(costs[0].get("cost", 0))

                descripcion = p.get("name", "")
                if variante.get("description"):
                    descripcion += f" — {variante['description']}"

                productos.append(Producto(
                    codigo=codigo.strip(),
                    descripcion=descripcion.strip(),
                    marca=p.get("brand") or None,
                    precio=precio,
                    activo=variante.get("state", 1) == 1,
                ))

        log.info(f"get_productos: {len(productos)} variantes")
        return productos

    def get_stock(self) -> list[Stock]:
        """Descarga stock por sucursal desde /stocks.json.

        Filtra por los office_ids configurados en el tenant.
        Si office_ids está vacío, trae todas las sucursales.
        """
        params = {}
        items = self._paginar("/stocks.json", params)

        stock = []
        for s in items:
            office_id = s.get("officeId") or s.get("office", {}).get("id")
            if self._office_ids and office_id not in self._office_ids:
                continue
            codigo = s.get("variantCode") or str(s.get("variantId", ""))
            if not codigo:
                continue
            bodega = s.get("officeName") or str(office_id)
            cantidad = float(s.get("quantityAvailable") or s.get("quantity") or 0)
            stock.append(Stock(
                codigo=codigo.strip(),
                bodega=bodega.strip(),
                cantidad=cantidad,
            ))

        log.info(f"get_stock: {len(stock)} líneas (oficinas: {self._office_ids or 'todas'})")
        return stock

    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        """Descarga documentos de venta del rango [desde, hasta] (YYYY-MM-DD).

        Usa /documents.json filtrando por emissiondaterange.
        Solo considera documentos de tipo venta (typeId en tipos configurados
        o cualquier tipo si no se especifica).
        """
        import datetime

        def _a_ts(fecha_str: str) -> int:
            return int(datetime.datetime.strptime(fecha_str, "%Y-%m-%d").timestamp())

        params = {
            "emissiondaterange": f"[{_a_ts(desde)},{_a_ts(hasta) + 86399}]",
            "state": 0,  # 0 = vigentes
        }
        items = self._paginar("/documents.json", params)

        ventas = []
        for doc in items:
            fecha = self._fecha(doc.get("emissionDate"))
            vendedor = doc.get("seller", {}).get("firstName", "") if doc.get("seller") else None
            cliente = doc.get("client", {}).get("code") if doc.get("client") else None

            for linea in (doc.get("details", {}).get("items") or []):
                codigo = linea.get("code") or str(linea.get("variantId", ""))
                if not codigo:
                    continue
                ventas.append(Venta(
                    fecha=fecha,
                    codigo=codigo.strip(),
                    descripcion=(linea.get("variantDescription") or linea.get("description") or "").strip(),
                    cantidad=float(linea.get("quantity") or 0),
                    precio=float(linea.get("netUnitValue") or linea.get("unitValue") or 0),
                    vendedor=vendedor,
                    cliente=cliente,
                ))

        log.info(f"get_ventas ({desde}→{hasta}): {len(ventas)} líneas")
        return ventas

    def get_pedidos(self) -> list[Pedido]:
        """Descarga pedidos de compra pendientes desde /purchase_orders.json.

        Bsale llama a esto "órdenes de compra" (purchase orders).
        state=0 = pendiente/en proceso.
        """
        items = self._paginar("/purchase_orders.json", {"state": 0})

        pedidos = []
        for po in items:
            numero = str(po.get("number") or po.get("id", ""))
            if not numero:
                continue
            proveedor = ""
            if po.get("contact"):
                proveedor = po["contact"].get("firstName") or po["contact"].get("company") or ""

            lineas = []
            for det in (po.get("details", {}).get("items") or []):
                codigo = det.get("code") or str(det.get("variantId", ""))
                lineas.append({
                    "codigo":      codigo.strip(),
                    "descripcion": (det.get("description") or "").strip(),
                    "cantidad":    float(det.get("quantity") or 0),
                })

            pedidos.append(Pedido(
                numero=numero,
                fecha=self._fecha(po.get("createdAt")),
                proveedor=proveedor.strip(),
                lineas=lineas,
            ))

        log.info(f"get_pedidos: {len(pedidos)} órdenes de compra")
        return pedidos
