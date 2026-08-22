"""
sheets_adapter.py — Adaptador para Google Sheets (hoja pública o con service account).

Lee datos desde una Google Spreadsheet usando la URL de exportación CSV pública
(hoja compartida como "cualquiera con el enlace puede ver") o, si se provee
api_key, usa la Sheets API v4 via urllib sin dependencias adicionales.

Nada de este archivo conoce datos de ningún cliente real.
Todo viene de tenant_config["erp"] (tenants/{id}.json → "erp").

Campos requeridos en tenant_config["erp"]:
    spreadsheet_id   : str — ID de la Google Spreadsheet
                        (la parte entre /d/ y /edit en la URL)

Campos opcionales:
    api_key          : str — API key de Google (solo lectura). Si se omite, la
                        hoja debe ser pública ("cualquiera con el enlace").
    sheet_productos  : str — nombre de la pestaña de productos  (default "Productos")
    sheet_stock      : str — nombre de la pestaña de stock       (default "Stock")
    sheet_ventas     : str — nombre de la pestaña de ventas      (default "Ventas")
    sheet_pedidos    : str — nombre de la pestaña de pedidos     (default "Pedidos")
    timeout          : int — segundos de espera HTTP             (default 30)

Formato esperado de las pestañas (primera fila = encabezados):
  Productos : codigo, descripcion, marca, precio, activo
  Stock     : codigo, bodega, cantidad
  Ventas    : fecha, codigo, descripcion, cantidad, precio, vendedor, cliente
  Pedidos   : numero, fecha, proveedor, codigo, descripcion, cantidad
"""
import csv
import io
import urllib.request
import urllib.parse
import urllib.error
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido
from core.logger import get_logger

log = get_logger("sheets_adapter")

_CSV_EXPORT_BASE = "https://docs.google.com/spreadsheets/d/{sid}/gviz/tq"
_SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{sheet}"


class SheetsAdapter(ERPAdapter):
    """Adaptador para Google Sheets via exportación CSV pública o API v4 con api_key."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._sid           = config["spreadsheet_id"]
        self._api_key       = config.get("api_key", "")
        self._sh_productos  = config.get("sheet_productos", "Productos")
        self._sh_stock      = config.get("sheet_stock", "Stock")
        self._sh_ventas     = config.get("sheet_ventas", "Ventas")
        self._sh_pedidos    = config.get("sheet_pedidos", "Pedidos")
        self._timeout       = int(config.get("timeout", 30))

    # -----------------------------------------------------------------------
    # Descarga CSV
    # -----------------------------------------------------------------------

    def _descargar_csv(self, sheet_name: str) -> list[dict]:
        """Descarga una pestaña de la Spreadsheet como CSV y devuelve lista de dicts."""
        url = self._build_url(sheet_name)
        log.debug(f"GET {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "FerreSystem/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error(f"HTTP {e.code} al descargar hoja '{sheet_name}': {body[:200]}")
            raise
        except urllib.error.URLError as e:
            log.error(f"URLError al descargar hoja '{sheet_name}': {e.reason}")
            raise

        rows = list(csv.DictReader(io.StringIO(raw)))
        # gviz/tq devuelve a veces encabezados con espacios extra; normalizar
        rows = [{k.strip(): v.strip() for k, v in row.items()} for row in rows]
        log.debug(f"Hoja '{sheet_name}': {len(rows)} filas")
        return rows

    def _build_url(self, sheet_name: str) -> str:
        """Construye la URL de exportación según si hay api_key o no."""
        if self._api_key:
            url = _SHEETS_API_BASE.format(sid=self._sid, sheet=urllib.parse.quote(sheet_name))
            return f"{url}?key={urllib.parse.quote(self._api_key)}"
        # Hoja pública: exportar como CSV via gviz endpoint
        qs = urllib.parse.urlencode({
            "tqx":   "out:csv",
            "sheet": sheet_name,
        })
        return _CSV_EXPORT_BASE.format(sid=self._sid) + "?" + qs

    def _descargar_api(self, sheet_name: str) -> list[dict]:
        """Descarga vía Sheets API v4 (requiere api_key). Devuelve lista de dicts."""
        url = self._build_url(sheet_name)
        req = urllib.request.Request(url, headers={"User-Agent": "FerreSystem/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                import json
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error(f"HTTP {e.code} Sheets API hoja '{sheet_name}': {body[:200]}")
            raise
        except urllib.error.URLError as e:
            log.error(f"URLError Sheets API hoja '{sheet_name}': {e.reason}")
            raise

        values = data.get("values", [])
        if not values:
            return []
        headers = [h.strip() for h in values[0]]
        rows = []
        for row in values[1:]:
            padded = list(row) + [""] * (len(headers) - len(row))
            rows.append({h: v.strip() for h, v in zip(headers, padded)})
        return rows

    def _fetch_sheet(self, sheet_name: str) -> list[dict]:
        """Elige la estrategia de descarga según configuración."""
        if self._api_key:
            return self._descargar_api(sheet_name)
        return self._descargar_csv(sheet_name)

    # -----------------------------------------------------------------------
    # Helpers de conversión
    # -----------------------------------------------------------------------

    @staticmethod
    def _str(row: dict, *keys: str) -> str:
        for k in keys:
            v = row.get(k, "").strip()
            if v:
                return v
        return ""

    @staticmethod
    def _float(row: dict, *keys: str) -> float:
        for k in keys:
            raw = row.get(k, "").strip().replace(",", ".")
            try:
                return float(raw)
            except (ValueError, TypeError):
                continue
        return 0.0

    @staticmethod
    def _bool(row: dict, *keys: str, default: bool = True) -> bool:
        for k in keys:
            v = row.get(k, "").strip().lower()
            if v in ("false", "0", "no", "inactivo", "inactive"):
                return False
            if v in ("true", "1", "si", "sí", "activo", "active", "yes"):
                return True
        return default

    # -----------------------------------------------------------------------
    # Contrato ERPAdapter
    # -----------------------------------------------------------------------

    def test_conexion(self) -> bool:
        """Verifica acceso descargando 1 fila de la pestaña de productos."""
        try:
            rows = self._fetch_sheet(self._sh_productos)
            ok = isinstance(rows, list)
            log.info(f"test_conexion: {'OK' if ok else 'SIN DATA'} ({len(rows)} filas en '{self._sh_productos}')")
            return ok
        except Exception as e:
            log.error(f"test_conexion falló: {e}")
            return False

    def get_productos(self) -> list[Producto]:
        """Lee la pestaña de productos. Columnas: codigo, descripcion, marca, precio, activo."""
        rows = self._fetch_sheet(self._sh_productos)
        productos = []
        for row in rows:
            codigo = self._str(row, "codigo", "Codigo", "CODIGO", "code", "Code")
            if not codigo:
                continue
            productos.append(Producto(
                codigo=codigo,
                descripcion=self._str(row, "descripcion", "Descripcion", "DESCRIPCION", "name", "Name"),
                marca=self._str(row, "marca", "Marca", "MARCA", "brand") or None,
                precio=self._float(row, "precio", "Precio", "PRECIO", "price"),
                activo=self._bool(row, "activo", "Activo", "ACTIVO", "active"),
            ))
        log.info(f"get_productos: {len(productos)} artículos desde '{self._sh_productos}'")
        return productos

    def get_stock(self) -> list[Stock]:
        """Lee la pestaña de stock. Columnas: codigo, bodega, cantidad."""
        rows = self._fetch_sheet(self._sh_stock)
        stock = []
        for row in rows:
            codigo = self._str(row, "codigo", "Codigo", "CODIGO", "code")
            if not codigo:
                continue
            stock.append(Stock(
                codigo=codigo,
                bodega=self._str(row, "bodega", "Bodega", "BODEGA", "warehouse") or "Principal",
                cantidad=self._float(row, "cantidad", "Cantidad", "CANTIDAD", "qty", "quantity"),
            ))
        log.info(f"get_stock: {len(stock)} líneas desde '{self._sh_stock}'")
        return stock

    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        """Lee la pestaña de ventas filtrando por rango de fechas ISO."""
        rows = self._fetch_sheet(self._sh_ventas)
        ventas = []
        for row in rows:
            fecha = self._str(row, "fecha", "Fecha", "FECHA", "date", "Date")[:10]
            if not fecha:
                continue
            if not (desde <= fecha <= hasta):
                continue
            codigo = self._str(row, "codigo", "Codigo", "CODIGO", "code")
            if not codigo:
                continue
            ventas.append(Venta(
                fecha=fecha,
                codigo=codigo,
                descripcion=self._str(row, "descripcion", "Descripcion", "DESCRIPCION", "name"),
                cantidad=self._float(row, "cantidad", "Cantidad", "CANTIDAD", "qty"),
                precio=self._float(row, "precio", "Precio", "PRECIO", "price"),
                vendedor=self._str(row, "vendedor", "Vendedor", "VENDEDOR", "seller") or None,
                cliente=self._str(row, "cliente", "Cliente", "CLIENTE", "client") or None,
            ))
        log.info(f"get_ventas ({desde}→{hasta}): {len(ventas)} líneas desde '{self._sh_ventas}'")
        return ventas

    def get_pedidos(self) -> list[Pedido]:
        """Lee la pestaña de pedidos agrupando líneas por número de pedido."""
        rows = self._fetch_sheet(self._sh_pedidos)
        pedidos_map: dict[str, Pedido] = {}
        for row in rows:
            numero = self._str(row, "numero", "Numero", "NUMERO", "number", "Number", "id")
            if not numero:
                continue
            if numero not in pedidos_map:
                pedidos_map[numero] = Pedido(
                    numero=numero,
                    fecha=self._str(row, "fecha", "Fecha", "FECHA", "date")[:10],
                    proveedor=self._str(row, "proveedor", "Proveedor", "PROVEEDOR", "supplier"),
                    lineas=[],
                )
            codigo = self._str(row, "codigo", "Codigo", "CODIGO", "code")
            if codigo:
                pedidos_map[numero].lineas.append({
                    "codigo":      codigo,
                    "descripcion": self._str(row, "descripcion", "Descripcion", "DESCRIPCION"),
                    "cantidad":    self._float(row, "cantidad", "Cantidad", "CANTIDAD", "qty"),
                })
        pedidos = list(pedidos_map.values())
        log.info(f"get_pedidos: {len(pedidos)} órdenes desde '{self._sh_pedidos}'")
        return pedidos
