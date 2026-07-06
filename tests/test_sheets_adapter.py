"""
test_sheets_adapter.py — Tests unitarios para SheetsAdapter.

Todos los tests usan mocks; nunca tocan Google Sheets real.
Cubre: CSV público, API v4 con api_key, mapeo de campos,
fechas fuera de rango, filas sin código, pedidos agrupados.
"""
import io
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.sheets_adapter import SheetsAdapter
from core.erp_adapter import Producto, Stock, Venta, Pedido

# ---------------------------------------------------------------------------
# CSV fixture helpers
# ---------------------------------------------------------------------------

PRODUCTOS_CSV = (
    "codigo,descripcion,marca,precio,activo\r\n"
    "P001,Martillo,Tramontina,12500.0,true\r\n"
    "P002,Destornillador,Stanley,4990.0,false\r\n"
    "  ,Sin codigo,X,0.0,true\r\n"
)

STOCK_CSV = (
    "codigo,bodega,cantidad\r\n"
    "P001,BOD1,50\r\n"
    "P001,BOD2,20\r\n"
    "P002,BOD1,0\r\n"
)

VENTAS_CSV = (
    "fecha,codigo,descripcion,cantidad,precio,vendedor,cliente\r\n"
    "2025-01-10,P001,Martillo,2,12500.0,Juan,C001\r\n"
    "2025-01-15,P002,Destornillador,1,4990.0,,\r\n"
    "2025-02-01,P001,Martillo,3,12500.0,Juan,C002\r\n"
)

PEDIDOS_CSV = (
    "numero,fecha,proveedor,codigo,descripcion,cantidad\r\n"
    "OC001,2025-01-05,Proveedor A,P001,Martillo,10\r\n"
    "OC001,2025-01-05,Proveedor A,P002,Destornillador,5\r\n"
    "OC002,2025-01-06,Proveedor B,P001,Martillo,20\r\n"
)


def _make_response(content: str):
    resp = MagicMock()
    resp.read.return_value = content.encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@pytest.fixture
def config_publico():
    return {
        "spreadsheet_id": "ABC123",
        "sheet_productos": "Productos",
        "sheet_stock": "Stock",
        "sheet_ventas": "Ventas",
        "sheet_pedidos": "Pedidos",
        "timeout": 5,
    }


@pytest.fixture
def config_api_key(config_publico):
    return {**config_publico, "api_key": "MI_API_KEY"}


@pytest.fixture
def adapter(config_publico):
    return SheetsAdapter(config_publico)


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

class TestURLBuilding:
    def test_url_publica_contiene_gviz(self, adapter):
        url = adapter._build_url("MiHoja")
        assert "gviz/tq" in url
        assert "out:csv" in url or "out%3Acsv" in url
        assert "MiHoja" in url

    def test_url_api_key_usa_sheets_api(self, config_api_key):
        a = SheetsAdapter(config_api_key)
        url = a._build_url("MiHoja")
        assert "googleapis.com" in url
        assert "MI_API_KEY" in url
        assert "ABC123" in url


# ---------------------------------------------------------------------------
# get_productos
# ---------------------------------------------------------------------------

class TestGetProductos:
    def test_mapeo_basico(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PRODUCTOS_CSV)):
            prods = adapter.get_productos()
        assert len(prods) == 2  # fila sin código excluida
        p = prods[0]
        assert isinstance(p, Producto)
        assert p.codigo == "P001"
        assert p.descripcion == "Martillo"
        assert p.marca == "Tramontina"
        assert p.precio == 12500.0
        assert p.activo is True

    def test_activo_false(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PRODUCTOS_CSV)):
            prods = adapter.get_productos()
        assert prods[1].activo is False

    def test_fila_sin_codigo_excluida(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PRODUCTOS_CSV)):
            prods = adapter.get_productos()
        codigos = [p.codigo for p in prods]
        assert "" not in codigos

    def test_hoja_vacia(self, adapter):
        csv_vacio = "codigo,descripcion,marca,precio,activo\r\n"
        with patch("urllib.request.urlopen", return_value=_make_response(csv_vacio)):
            prods = adapter.get_productos()
        assert prods == []

    def test_error_http_propaga(self, adapter):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, None
        )):
            with pytest.raises(urllib.error.HTTPError):
                adapter.get_productos()


# ---------------------------------------------------------------------------
# get_stock
# ---------------------------------------------------------------------------

class TestGetStock:
    def test_mapeo_basico(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(STOCK_CSV)):
            stock = adapter.get_stock()
        assert len(stock) == 3
        s = stock[0]
        assert isinstance(s, Stock)
        assert s.codigo == "P001"
        assert s.bodega == "BOD1"
        assert s.cantidad == 50.0

    def test_bodega_default(self, adapter):
        csv = "codigo,cantidad\r\nP001,10\r\n"
        with patch("urllib.request.urlopen", return_value=_make_response(csv)):
            stock = adapter.get_stock()
        assert stock[0].bodega == "Principal"

    def test_cantidad_float(self, adapter):
        csv = "codigo,bodega,cantidad\r\nP001,BOD1,3.5\r\n"
        with patch("urllib.request.urlopen", return_value=_make_response(csv)):
            stock = adapter.get_stock()
        assert stock[0].cantidad == 3.5


# ---------------------------------------------------------------------------
# get_ventas
# ---------------------------------------------------------------------------

class TestGetVentas:
    def test_filtra_por_rango(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(VENTAS_CSV)):
            ventas = adapter.get_ventas("2025-01-01", "2025-01-31")
        fechas = [v.fecha for v in ventas]
        assert all(f.startswith("2025-01") for f in fechas)
        assert len(ventas) == 2

    def test_fecha_fuera_de_rango_excluida(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(VENTAS_CSV)):
            ventas = adapter.get_ventas("2025-02-01", "2025-02-28")
        assert len(ventas) == 1
        assert ventas[0].fecha == "2025-02-01"

    def test_vendedor_cliente_opcionales(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(VENTAS_CSV)):
            ventas = adapter.get_ventas("2025-01-15", "2025-01-15")
        v = ventas[0]
        assert v.vendedor is None
        assert v.cliente is None

    def test_retorna_venta_dataclass(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(VENTAS_CSV)):
            ventas = adapter.get_ventas("2025-01-01", "2025-01-31")
        assert all(isinstance(v, Venta) for v in ventas)

    def test_sin_resultados(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(VENTAS_CSV)):
            ventas = adapter.get_ventas("2030-01-01", "2030-12-31")
        assert ventas == []


# ---------------------------------------------------------------------------
# get_pedidos
# ---------------------------------------------------------------------------

class TestGetPedidos:
    def test_agrupa_lineas(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PEDIDOS_CSV)):
            pedidos = adapter.get_pedidos()
        assert len(pedidos) == 2
        oc1 = next(p for p in pedidos if p.numero == "OC001")
        assert len(oc1.lineas) == 2

    def test_retorna_pedido_dataclass(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PEDIDOS_CSV)):
            pedidos = adapter.get_pedidos()
        assert all(isinstance(p, Pedido) for p in pedidos)

    def test_linea_tiene_campos(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PEDIDOS_CSV)):
            pedidos = adapter.get_pedidos()
        oc1 = next(p for p in pedidos if p.numero == "OC001")
        linea = oc1.lineas[0]
        assert "codigo" in linea
        assert "descripcion" in linea
        assert "cantidad" in linea


# ---------------------------------------------------------------------------
# test_conexion
# ---------------------------------------------------------------------------

class TestConexion:
    def test_ok_cuando_hoja_responde(self, adapter):
        with patch("urllib.request.urlopen", return_value=_make_response(PRODUCTOS_CSV)):
            assert adapter.test_conexion() is True

    def test_false_en_error_red(self, adapter):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            assert adapter.test_conexion() is False


# ---------------------------------------------------------------------------
# Sheets API v4 (api_key path)
# ---------------------------------------------------------------------------

class TestSheetsApiKey:
    def test_parsea_respuesta_api(self, config_api_key):
        api_resp = {
            "values": [
                ["codigo", "descripcion", "marca", "precio", "activo"],
                ["P001", "Martillo", "Tramontina", "12500", "true"],
            ]
        }
        resp = _make_response(json.dumps(api_resp))
        a = SheetsAdapter(config_api_key)
        with patch("urllib.request.urlopen", return_value=resp):
            prods = a.get_productos()
        assert len(prods) == 1
        assert prods[0].codigo == "P001"

    def test_api_hoja_vacia(self, config_api_key):
        api_resp = {"values": []}
        resp = _make_response(json.dumps(api_resp))
        a = SheetsAdapter(config_api_key)
        with patch("urllib.request.urlopen", return_value=resp):
            prods = a.get_productos()
        assert prods == []
