"""
justweb_adapter.py — Adaptador para ERP JustWeb (reportes SSRS vía HTTP).

Basado en el flujo real documentado en AGENTS.md para Ferretería Oviedo:
  - Los reportes se exponen como CSV descargables desde el servidor SSRS.
  - El separador es punto y coma (;).
  - Los números usan punto como separador de miles y coma como decimal
    (ej. "1.234,56" → 1234.56).
  - La autenticación es HTTP Basic (usuario/contraseña del ERP).

NO hay ningún host, usuario, bodega ni tenant_id hardcodeado en este archivo.
Todo viene de config (tenants/{id}.json → "erp").
"""
import csv
import io
import urllib.request
import urllib.parse
import urllib.error
from base64 import b64encode
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido
from core.logger import get_logger

log = get_logger("justweb_adapter")

# Nombres de reportes SSRS — se configuran en tenants/{id}.json → erp.reportes
# Si el tenant no los define, se usan estos defaults.
DEFAULT_REPORTES = {
    "productos": "/ReportServer/Pages/ReportViewer.aspx?%2fListaProductos&rs:Format=CSV",
    "stock":     "/ReportServer/Pages/ReportViewer.aspx?%2fStockBodegas&rs:Format=CSV",
    "ventas":    "/ReportServer/Pages/ReportViewer.aspx?%2fVentasDiarias&rs:Format=CSV",
    "pedidos":   "/ReportServer/Pages/ReportViewer.aspx?%2fPedidosPendientes&rs:Format=CSV",
}


class JustWebAdapter(ERPAdapter):
    """Adaptador para JustWeb. Descarga reportes SSRS y parsea el CSV.

    config esperado (bloque erp del tenant.json):
        host         : IP o hostname del servidor JustWeb (sin esquema ni slash)
        puerto       : Puerto HTTP (int, default 80)
        usuario      : Usuario del ERP
        password_enc : Contraseña descifrada externamente antes de pasarse aquí
                       (la desencriptación DPAPI corre en pipeline/descargar_erp.py)
        reportes     : (opcional) dict que sobreescribe DEFAULT_REPORTES
        timeout      : (opcional) segundos de espera HTTP (default 30)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        host   = config["host"]
        puerto = config.get("puerto", 80)
        self._base_url = f"http://{host}:{puerto}"
        self._usuario  = config["usuario"]
        self._password = config["password_enc"]  # ya descifrado por el caller
        self._timeout  = int(config.get("timeout", 30))
        self._reportes = {**DEFAULT_REPORTES, **config.get("reportes", {})}

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _auth_header(self) -> dict:
        credenciales = f"{self._usuario}:{self._password}"
        token = b64encode(credenciales.encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _descargar_csv(self, path_reporte: str, params: dict = None) -> list[dict]:
        """Descarga un reporte SSRS y lo parsea como lista de dicts.

        Maneja el encoding cp1252 habitual en SSRS chileno y el
        BOM UTF-8 que algunos reportes agregan.
        """
        url = self._base_url + path_reporte
        if params:
            url += "&" + urllib.parse.urlencode(params)

        log.debug(f"GET {url}")
        req = urllib.request.Request(url, headers=self._auth_header())
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.URLError as e:
            log.error(f"Error HTTP al descargar reporte: {e}")
            raise

        # Detectar encoding: intentar UTF-8, caer a cp1252
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            texto = raw.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(texto), delimiter=";")
        return list(reader)

    @staticmethod
    def _num(valor: str) -> float:
        """Convierte '1.234,56' → 1234.56 (formato chileno JustWeb)."""
        if not valor or valor.strip() == "":
            return 0.0
        limpio = valor.strip().replace(".", "").replace(",", ".")
        try:
            return float(limpio)
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    # Métodos públicos (contrato ERPAdapter)
    # ------------------------------------------------------------------

    def test_conexion(self) -> bool:
        """Intenta descargar el reporte de productos; devuelve True si hay datos."""
        try:
            filas = self._descargar_csv(self._reportes["productos"])
            ok = len(filas) > 0
            log.info(f"test_conexion: {'OK' if ok else 'SIN DATOS'}")
            return ok
        except Exception as e:
            log.error(f"test_conexion falló: {e}")
            return False

    def get_productos(self) -> list[Producto]:
        """Descarga y parsea el reporte de productos.

        Columnas esperadas en el CSV (nombres exactos del reporte SSRS):
          CODIGO, DESCRIPCION, MARCA, PRECIO_VENTA, ACTIVO
        Nombres alternativos se mapean vía _COL_PRODUCTOS.
        """
        COL = {
            "codigo":      ("CODIGO", "Codigo", "codigo", "SKU"),
            "descripcion": ("DESCRIPCION", "Descripcion", "descripcion", "NOMBRE"),
            "marca":       ("MARCA", "Marca", "marca"),
            "precio":      ("PRECIO_VENTA", "Precio", "PRECIO", "precio"),
            "activo":      ("ACTIVO", "Activo", "activo", "ESTADO"),
        }

        def _get(row: dict, nombres: tuple, default=""):
            for n in nombres:
                if n in row:
                    return row[n]
            return default

        filas = self._descargar_csv(self._reportes["productos"])
        productos = []
        for fila in filas:
            codigo = _get(fila, COL["codigo"]).strip()
            if not codigo:
                continue
            activo_raw = _get(fila, COL["activo"], "1").strip().upper()
            activo = activo_raw not in ("0", "N", "NO", "FALSE", "INACTIVO")
            productos.append(Producto(
                codigo=codigo,
                descripcion=_get(fila, COL["descripcion"]).strip(),
                marca=_get(fila, COL["marca"]).strip() or None,
                precio=self._num(_get(fila, COL["precio"])) or None,
                activo=activo,
            ))
        log.info(f"get_productos: {len(productos)} productos")
        return productos

    def get_stock(self) -> list[Stock]:
        """Descarga y parsea el reporte de stock por bodega.

        Columnas esperadas:
          CODIGO, BODEGA, CANTIDAD
        """
        COL = {
            "codigo":   ("CODIGO", "Codigo", "codigo", "SKU"),
            "bodega":   ("BODEGA", "Bodega", "bodega", "COD_BODEGA"),
            "cantidad": ("CANTIDAD", "Cantidad", "cantidad", "STOCK"),
        }

        def _get(row, nombres, default=""):
            for n in nombres:
                if n in row:
                    return row[n]
            return default

        filas = self._descargar_csv(self._reportes["stock"])
        stock = []
        for fila in filas:
            codigo = _get(fila, COL["codigo"]).strip()
            if not codigo:
                continue
            stock.append(Stock(
                codigo=codigo,
                bodega=_get(fila, COL["bodega"]).strip(),
                cantidad=self._num(_get(fila, COL["cantidad"])),
            ))
        log.info(f"get_stock: {len(stock)} líneas")
        return stock

    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        """Descarga ventas en el rango [desde, hasta] (formato YYYY-MM-DD).

        Columnas esperadas:
          FECHA, CODIGO, DESCRIPCION, CANTIDAD, PRECIO, VENDEDOR, RUT_CLIENTE
        El rango se pasa como parámetros al reporte SSRS.
        """
        COL = {
            "fecha":       ("FECHA", "Fecha", "fecha"),
            "codigo":      ("CODIGO", "Codigo", "codigo", "SKU"),
            "descripcion": ("DESCRIPCION", "Descripcion", "descripcion"),
            "cantidad":    ("CANTIDAD", "Cantidad", "cantidad"),
            "precio":      ("PRECIO", "Precio", "precio", "PRECIO_VENTA"),
            "vendedor":    ("VENDEDOR", "Vendedor", "vendedor"),
            "cliente":     ("RUT_CLIENTE", "Cliente", "cliente", "RUT"),
        }

        def _get(row, nombres, default=""):
            for n in nombres:
                if n in row:
                    return row[n]
            return default

        params = {"rs:ParameterLanguage": "", "FechaDesde": desde, "FechaHasta": hasta}
        filas = self._descargar_csv(self._reportes["ventas"], params)
        ventas = []
        for fila in filas:
            codigo = _get(fila, COL["codigo"]).strip()
            if not codigo:
                continue
            ventas.append(Venta(
                fecha=_get(fila, COL["fecha"]).strip(),
                codigo=codigo,
                descripcion=_get(fila, COL["descripcion"]).strip(),
                cantidad=self._num(_get(fila, COL["cantidad"])),
                precio=self._num(_get(fila, COL["precio"])),
                vendedor=_get(fila, COL["vendedor"]).strip() or None,
                cliente=_get(fila, COL["cliente"]).strip() or None,
            ))
        log.info(f"get_ventas ({desde}→{hasta}): {len(ventas)} líneas")
        return ventas

    def get_pedidos(self) -> list[Pedido]:
        """Descarga pedidos pendientes.

        Columnas esperadas:
          NUMERO, FECHA, PROVEEDOR, CODIGO_PROD, DESCRIPCION, CANTIDAD
        Las líneas se agrupan por NUMERO de pedido.
        """
        COL = {
            "numero":      ("NUMERO", "Numero", "numero", "N_PEDIDO"),
            "fecha":       ("FECHA", "Fecha", "fecha"),
            "proveedor":   ("PROVEEDOR", "Proveedor", "proveedor"),
            "cod_prod":    ("CODIGO_PROD", "Codigo", "codigo", "SKU"),
            "descripcion": ("DESCRIPCION", "Descripcion", "descripcion"),
            "cantidad":    ("CANTIDAD", "Cantidad", "cantidad"),
        }

        def _get(row, nombres, default=""):
            for n in nombres:
                if n in row:
                    return row[n]
            return default

        filas = self._descargar_csv(self._reportes["pedidos"])
        pedidos_map: dict = {}
        for fila in filas:
            numero = _get(fila, COL["numero"]).strip()
            if not numero:
                continue
            if numero not in pedidos_map:
                pedidos_map[numero] = Pedido(
                    numero=numero,
                    fecha=_get(fila, COL["fecha"]).strip(),
                    proveedor=_get(fila, COL["proveedor"]).strip(),
                    lineas=[],
                )
            pedidos_map[numero].lineas.append({
                "codigo":      _get(fila, COL["cod_prod"]).strip(),
                "descripcion": _get(fila, COL["descripcion"]).strip(),
                "cantidad":    self._num(_get(fila, COL["cantidad"])),
            })

        pedidos = list(pedidos_map.values())
        log.info(f"get_pedidos: {len(pedidos)} pedidos")
        return pedidos
