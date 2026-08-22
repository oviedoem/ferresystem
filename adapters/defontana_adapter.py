"""
defontana_adapter.py — Adaptador para Defontana (ERP SaaS chileno, API REST).

Defontana expone una API REST con autenticación OAuth2 client_credentials.
El token se obtiene una vez por instancia del adapter (una ejecución del pipeline)
y se reutiliza en todas las llamadas siguientes.

Documentación oficial: https://api.defontana.com/swagger/ui/index

Nada de este archivo conoce datos de ningún cliente real.
Todo viene de tenant_config["erp"] (tenants/{id}.json → "erp").

Campos requeridos en tenant_config["erp"]:
    client_id        : str — client ID de la app Defontana del tenant
    client_secret    : str — client secret (guardar cifrado en producción)
    company_id       : str — RUT o ID de la empresa en Defontana

Campos opcionales:
    api_base         : str — URL base (default "https://api.defontana.com")
    timeout          : int — segundos de espera HTTP (default 30)
    max_paginas      : int — límite de páginas por endpoint (default 100)
    warehouse_ids    : list[str] — IDs de bodegas a filtrar (default: todas)
"""
import json
import urllib.request
import urllib.parse
import urllib.error
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido
from core.logger import get_logger

log = get_logger("defontana_adapter")

_DEFAULT_BASE = "https://api.defontana.com"
_PAGE_SIZE = 100


class DefontanaAdapter(ERPAdapter):
    """Adaptador para Defontana via API REST con OAuth2 client_credentials.

    El token se obtiene en la primera llamada autenticada y se reutiliza
    durante toda la vida del objeto (un run del pipeline).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._client_id     = config["client_id"]
        self._client_secret = config["client_secret"]
        self._company_id    = config["company_id"]
        self._base          = config.get("api_base", _DEFAULT_BASE).rstrip("/")
        self._timeout       = int(config.get("timeout", 30))
        self._max_pag       = int(config.get("max_paginas", 100))
        self._wh_ids        = [str(w) for w in config.get("warehouse_ids", [])]
        self._token: str    = ""

    # -----------------------------------------------------------------------
    # Auth
    # -----------------------------------------------------------------------

    def _obtener_token(self) -> str:
        """Obtiene un access_token via OAuth2 client_credentials."""
        url  = f"{self._base}/api/Token"
        body = urllib.parse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                token = data.get("access_token") or data.get("token") or ""
                log.info("Token OAuth2 obtenido correctamente")
                return token
        except urllib.error.HTTPError as e:
            body_err = e.read().decode("utf-8", errors="replace")
            log.error(f"Error al obtener token ({e.code}): {body_err[:200]}")
            raise
        except urllib.error.URLError as e:
            log.error(f"URLError al obtener token: {e.reason}")
            raise

    def _token_header(self) -> dict:
        """Devuelve el header Authorization con el token, obteniéndolo si hace falta."""
        if not self._token:
            self._token = self._obtener_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type":  "application/json",
            "CompanyId":     self._company_id,
        }

    # -----------------------------------------------------------------------
    # Helpers HTTP
    # -----------------------------------------------------------------------

    def _get(self, path: str, params: dict = None) -> dict:
        """GET autenticado a la API de Defontana. Devuelve el JSON como dict."""
        url = self._base + path
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url += ("&" if "?" in url else "?") + qs
        log.debug(f"GET {url}")
        req = urllib.request.Request(url, headers=self._token_header())
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

    def _paginar(self, path: str, params: dict = None) -> list:
        """Itera sobre todas las páginas de un endpoint paginado de Defontana.

        Defontana usa page/pageSize. Respuesta esperada:
        { "success": true, "data": [...], "totalCount": N }
        """
        params = dict(params or {})
        params["pageSize"] = _PAGE_SIZE
        todos = []

        for pagina in range(1, self._max_pag + 1):
            params["page"] = pagina
            resp = self._get(path, params)

            # Defontana puede devolver data directamente o dentro de "data"
            items = resp.get("data") or resp.get("items") or []
            if isinstance(items, dict):
                items = list(items.values())

            todos.extend(items)

            total = resp.get("totalCount") or resp.get("total") or 0
            if len(todos) >= total or len(items) < _PAGE_SIZE:
                break

        return todos

    @staticmethod
    def _str(v) -> str:
        return str(v).strip() if v is not None else ""

    @staticmethod
    def _float(v) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    # -----------------------------------------------------------------------
    # Contrato ERPAdapter
    # -----------------------------------------------------------------------

    def test_conexion(self) -> bool:
        """Verifica credenciales obteniendo el token y consultando 1 producto."""
        try:
            self._token = self._obtener_token()
            resp = self._get("/api/sale/Item", {"page": 1, "pageSize": 1})
            ok = "data" in resp or "items" in resp
            log.info(f"test_conexion: {'OK' if ok else 'SIN DATA'}")
            return ok
        except Exception as e:
            log.error(f"test_conexion falló: {e}")
            return False

    def get_productos(self) -> list[Producto]:
        """Descarga el catálogo desde /api/sale/Item.

        Defontana devuelve artículos con código, descripción, marca y precio.
        Solo incluye artículos activos (Active == True).
        """
        items = self._paginar("/api/sale/Item")
        productos = []
        for it in items:
            codigo = self._str(it.get("Code") or it.get("ItemCode") or it.get("id"))
            if not codigo:
                continue
            if not it.get("Active", True):
                continue
            productos.append(Producto(
                codigo=codigo,
                descripcion=self._str(it.get("Name") or it.get("Description")),
                marca=self._str(it.get("Brand") or it.get("BrandName")) or None,
                precio=self._float(it.get("SalePrice") or it.get("Price")),
                activo=bool(it.get("Active", True)),
            ))
        log.info(f"get_productos: {len(productos)} artículos")
        return productos

    def get_stock(self) -> list[Stock]:
        """Descarga stock desde /api/inventory/Stock.

        Filtra por warehouse_ids si está configurado en el tenant.
        """
        items = self._paginar("/api/inventory/Stock")
        stock = []
        for s in items:
            bodega_id  = self._str(s.get("WarehouseId") or s.get("warehouseId") or "")
            bodega_nom = self._str(s.get("WarehouseName") or s.get("Warehouse") or bodega_id)
            if self._wh_ids and bodega_id not in self._wh_ids:
                continue
            codigo = self._str(s.get("ItemCode") or s.get("Code"))
            if not codigo:
                continue
            stock.append(Stock(
                codigo=codigo,
                bodega=bodega_nom or bodega_id,
                cantidad=self._float(s.get("Quantity") or s.get("Stock")),
            ))
        log.info(f"get_stock: {len(stock)} líneas (bodegas: {self._wh_ids or 'todas'})")
        return stock

    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        """Descarga ventas desde /api/sale/Sale para el rango [desde, hasta].

        Itera las líneas de detalle de cada documento de venta.
        """
        params = {
            "dateFrom": desde,
            "dateTo":   hasta,
            "status":   "Processed",
        }
        docs = self._paginar("/api/sale/Sale", params)
        ventas = []
        for doc in docs:
            fecha    = self._str(doc.get("Date") or doc.get("date") or "")[:10]
            vendedor = self._str(doc.get("SellerName") or doc.get("Seller"))
            cliente  = self._str(doc.get("ClientCode") or doc.get("ClientId"))

            for linea in (doc.get("Detail") or doc.get("Lines") or []):
                codigo = self._str(linea.get("ItemCode") or linea.get("Code"))
                if not codigo:
                    continue
                ventas.append(Venta(
                    fecha=fecha,
                    codigo=codigo,
                    descripcion=self._str(linea.get("ItemName") or linea.get("Description")),
                    cantidad=self._float(linea.get("Quantity")),
                    precio=self._float(linea.get("UnitPrice") or linea.get("NetUnitPrice")),
                    vendedor=vendedor or None,
                    cliente=cliente or None,
                ))
        log.info(f"get_ventas ({desde}→{hasta}): {len(ventas)} líneas")
        return ventas

    def get_pedidos(self) -> list[Pedido]:
        """Descarga órdenes de compra pendientes desde /api/purchase/PurchaseOrder."""
        params = {"status": "Pending"}
        docs = self._paginar("/api/purchase/PurchaseOrder", params)
        pedidos = []
        for po in docs:
            numero = self._str(po.get("Number") or po.get("Id") or po.get("id"))
            if not numero:
                continue
            pedidos.append(Pedido(
                numero=numero,
                fecha=self._str(po.get("Date") or "")[:10],
                proveedor=self._str(po.get("SupplierName") or po.get("Supplier")),
                lineas=[
                    {
                        "codigo":      self._str(l.get("ItemCode") or l.get("Code")),
                        "descripcion": self._str(l.get("ItemName") or l.get("Description")),
                        "cantidad":    self._float(l.get("Quantity")),
                    }
                    for l in (po.get("Detail") or po.get("Lines") or [])
                ],
            ))
        log.info(f"get_pedidos: {len(pedidos)} órdenes")
        return pedidos
