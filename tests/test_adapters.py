"""
test_adapters.py — Tests unitarios para adapters ERP.

Usa unittest.mock para interceptar llamadas HTTP/SQL — nunca toca
un ERP real. Valida que cada adapter:
  1. Mapea correctamente los campos al schema genérico
  2. Maneja respuestas vacías sin crashear
  3. Maneja errores de red graciosamente
  4. Aplica la configuración del tenant (no hardcodea nada)

Adapters cubiertos:
  - JustWebAdapter (CSV sobre HTTP)
  - BsaleAdapter (API REST JSON)
  - ExcelAdapter (archivo local)
"""
import io
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.erp_adapter import Producto, Stock, Venta, Pedido


# ─── JustWebAdapter ──────────────────────────────────────────────────────────

class TestJustWebAdapter:
    """Tests para adapters/justweb_adapter.py — descarga CSV desde SSRS."""

    @pytest.fixture
    def config(self):
        return {
            "host": "erp.ejemplo.cl",
            "puerto": 80,
            "usuario": "user",
            "password_enc": "pass",
            "timeout": 5,
        }

    @pytest.fixture
    def adapter(self, config):
        from adapters.justweb_adapter import JustWebAdapter
        return JustWebAdapter(config)

    def _mock_csv(self, contenido: str):
        """Devuelve un context manager que simula urlopen con CSV."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = contenido.encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    # --- get_productos ---

    def test_get_productos_parsea_correctamente(self, adapter):
        csv = "CODIGO;DESCRIPCION;MARCA;PRECIO_VENTA;ACTIVO\nA001;Tornillo 6x1;Heco;1490;1\nA002;Martillo;Stanley;8990;1\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            prods = adapter.get_productos()
        assert len(prods) == 2
        assert prods[0].codigo == "A001"
        assert prods[0].descripcion == "Tornillo 6x1"
        assert prods[0].marca == "Heco"
        assert prods[0].precio == 1490.0
        assert prods[0].activo is True

    def test_get_productos_fila_sin_codigo_ignorada(self, adapter):
        csv = "CODIGO;DESCRIPCION\n;Sin codigo\nB001;Con codigo\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            prods = adapter.get_productos()
        assert len(prods) == 1
        assert prods[0].codigo == "B001"

    def test_get_productos_inactivo(self, adapter):
        csv = "CODIGO;DESCRIPCION;MARCA;PRECIO_VENTA;ACTIVO\nX001;Producto;M;100;N\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            prods = adapter.get_productos()
        assert prods[0].activo is False

    def test_get_productos_csv_vacio_devuelve_lista_vacia(self, adapter):
        csv = "CODIGO;DESCRIPCION\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            prods = adapter.get_productos()
        assert prods == []

    # --- get_stock ---

    def test_get_stock_parsea_correctamente(self, adapter):
        csv = "CODIGO;BODEGA;CANTIDAD\nA001;BOD1;150\nA001;BOD2;25\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            stock = adapter.get_stock()
        assert len(stock) == 2
        assert stock[0].codigo == "A001"
        assert stock[0].bodega == "BOD1"
        assert stock[0].cantidad == 150.0

    def test_get_stock_cantidad_formato_chileno(self, adapter):
        csv = "CODIGO;BODEGA;CANTIDAD\nA001;BOD1;1.234,56\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            stock = adapter.get_stock()
        assert stock[0].cantidad == pytest.approx(1234.56)

    # --- get_ventas ---

    def test_get_ventas_parsea_correctamente(self, adapter):
        csv = "FECHA;CODIGO;DESCRIPCION;CANTIDAD;PRECIO;VENDEDOR;RUT_CLIENTE\n2026-07-01;A001;Tornillo;10;1490;Pedro;12345678\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            ventas = adapter.get_ventas("2026-07-01", "2026-07-01")
        assert len(ventas) == 1
        v = ventas[0]
        assert v.fecha == "2026-07-01"
        assert v.codigo == "A001"
        assert v.cantidad == 10.0
        assert v.precio == 1490.0
        assert v.vendedor == "Pedro"

    # --- test_conexion ---

    def test_test_conexion_ok(self, adapter):
        csv = "CODIGO;DESCRIPCION\nA001;Prod\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            assert adapter.test_conexion() is True

    def test_test_conexion_sin_datos_false(self, adapter):
        csv = "CODIGO;DESCRIPCION\n"
        with patch("urllib.request.urlopen", return_value=self._mock_csv(csv)):
            assert adapter.test_conexion() is False

    def test_test_conexion_error_red_false(self, adapter):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            assert adapter.test_conexion() is False

    # --- _num helper ---

    def test_num_convierte_formato_chileno(self, adapter):
        assert adapter._num("1.234,56") == pytest.approx(1234.56)
        assert adapter._num("500") == 500.0
        assert adapter._num("") == 0.0
        assert adapter._num("abc") == 0.0


# ─── BsaleAdapter ────────────────────────────────────────────────────────────

class TestBsaleAdapter:
    """Tests para adapters/bsale_adapter.py — API REST Bsale v1."""

    @pytest.fixture
    def config(self):
        return {
            "access_token": "tok_test_abc123",
            "office_ids": [1, 2],
            "timeout": 5,
            "max_paginas": 3,
        }

    @pytest.fixture
    def adapter(self, config):
        from adapters.bsale_adapter import BsaleAdapter
        return BsaleAdapter(config)

    def _mock_get(self, adapter, responses: dict):
        """
        Parchea adapter._client.get para devolver respuestas según el path.
        responses: { path_substring: dict_respuesta }
        """
        def fake_get(path, params=None):
            for key, val in responses.items():
                if key in path:
                    return val
            return {"items": []}
        return patch.object(adapter._client, "get", side_effect=fake_get)

    # --- get_productos ---

    def test_get_productos_mapea_variantes(self, adapter):
        resp_page1 = {
            "items": [{
                "name": "Tornillo", "brand": "Heco",
                "variants": {"items": [
                    {"id": 1, "code": "TOR-001", "description": "6x1\"", "state": 1,
                     "costs": {"items": [{"cost": 1490}]}},
                ]},
            }],
            "count": 1,
        }
        with self._mock_get(adapter, {"/products": resp_page1}):
            prods = adapter.get_productos()
        assert len(prods) == 1
        assert prods[0].codigo == "TOR-001"
        assert prods[0].descripcion == 'Tornillo — 6x1"'
        assert prods[0].marca == "Heco"
        assert prods[0].precio == 1490.0
        assert prods[0].activo is True

    def test_get_productos_variante_inactiva(self, adapter):
        resp = {
            "items": [{"name": "Prod", "brand": None,
                        "variants": {"items": [{"id":1,"code":"X","description":"","state":0,"costs":{"items":[]}}]}}],
            "count": 1,
        }
        with self._mock_get(adapter, {"/products": resp}):
            prods = adapter.get_productos()
        assert prods[0].activo is False

    def test_get_productos_sin_variantes_ignorado(self, adapter):
        resp = {"items": [{"name": "Prod", "brand": None, "variants": {"items": []}}], "count": 1}
        with self._mock_get(adapter, {"/products": resp}):
            prods = adapter.get_productos()
        assert prods == []

    def test_get_productos_respuesta_vacia(self, adapter):
        with self._mock_get(adapter, {"/products": {"items": [], "count": 0}}):
            assert adapter.get_productos() == []

    # --- get_stock ---

    def test_get_stock_filtra_por_office_ids(self, adapter):
        resp = {
            "items": [
                {"variantCode": "A001", "officeName": "Suc1", "officeId": 1, "quantityAvailable": 50},
                {"variantCode": "A001", "officeName": "Suc3", "officeId": 3, "quantityAvailable": 10},
                {"variantCode": "A002", "officeName": "Suc2", "officeId": 2, "quantityAvailable": 20},
            ],
            "count": 3,
        }
        with self._mock_get(adapter, {"/stocks": resp}):
            stock = adapter.get_stock()
        # Solo office_ids [1, 2] — debe excluir officeId 3
        assert len(stock) == 2
        oficinas = {s.bodega for s in stock}
        assert "Suc3" not in oficinas

    def test_get_stock_sin_filtro_trae_todo(self, config):
        config_sin_filtro = {**config, "office_ids": []}
        from adapters.bsale_adapter import BsaleAdapter
        adapter_sin = BsaleAdapter(config_sin_filtro)
        resp = {
            "items": [
                {"variantCode": "A001", "officeName": "Suc1", "officeId": 1, "quantityAvailable": 5},
                {"variantCode": "A001", "officeName": "Suc9", "officeId": 9, "quantityAvailable": 3},
            ],
            "count": 2,
        }
        with patch.object(adapter_sin._client, "get", return_value=resp):
            stock = adapter_sin.get_stock()
        assert len(stock) == 2

    def test_get_stock_cantidad_disponible(self, adapter):
        resp = {"items": [
            {"variantCode": "B01", "officeName": "X", "officeId": 1, "quantityAvailable": 42.5}
        ], "count": 1}
        with self._mock_get(adapter, {"/stocks": resp}):
            stock = adapter.get_stock()
        assert stock[0].cantidad == pytest.approx(42.5)

    # --- test_conexion ---

    def test_test_conexion_ok(self, adapter):
        with patch.object(adapter._client, "get", return_value={"items": [{"id": 1}]}):
            assert adapter.test_conexion() is True

    def test_test_conexion_sin_key_items_false(self, adapter):
        with patch.object(adapter._client, "get", return_value={"error": "bad token"}):
            assert adapter.test_conexion() is False

    def test_test_conexion_excepcion_false(self, adapter):
        import urllib.error
        with patch.object(adapter._client, "get", side_effect=urllib.error.URLError("401")):
            assert adapter.test_conexion() is False

    # --- _fecha helper ---

    def test_fecha_convierte_timestamp(self, adapter):
        # Verifica que el timestamp se convierte a fecha ISO sin crashear
        # Usamos una fecha conocida: 2000-01-01 00:00:00 UTC = 946684800
        resultado = adapter._fecha(946684800)
        assert resultado == "2000-01-01"

    def test_fecha_none_devuelve_cadena_vacia(self, adapter):
        assert adapter._fecha(None) == ""

    def test_fecha_cero_devuelve_vacia(self, adapter):
        assert adapter._fecha(0) == ""

    # --- config desde tenant ---

    def test_config_no_hardcodea_nada(self, config):
        config_custom = {
            "access_token": "otro_token",
            "office_ids": [99],
            "api_version": "2",
            "timeout": 10,
        }
        from adapters.bsale_adapter import BsaleAdapter
        a = BsaleAdapter(config_custom)
        assert a._token == "otro_token"
        assert a._office_ids == [99]
        assert "v2" in a._base
        assert a._client._timeout == 10


# ─── ERPAdapter (contrato base) ───────────────────────────────────────────────

class TestERPAdapterContrato:
    """Verifica que el contrato base funcione correctamente."""

    def test_adapter_concreto_implementa_todos_los_metodos(self):
        from adapters.justweb_adapter import JustWebAdapter
        from core.erp_adapter import ERPAdapter
        assert issubclass(JustWebAdapter, ERPAdapter)
        for metodo in ("get_productos", "get_stock", "get_ventas", "get_pedidos", "test_conexion"):
            assert hasattr(JustWebAdapter, metodo)

    def test_bsale_implementa_todos_los_metodos(self):
        from adapters.bsale_adapter import BsaleAdapter
        from core.erp_adapter import ERPAdapter
        assert issubclass(BsaleAdapter, ERPAdapter)

# ─── BukAdapter ──────────────────────────────────────────────────────────────

class TestBukAdapter:
    """Tests para adapters/buk_adapter.py — API REST Buk RR.HH."""

    @pytest.fixture
    def config(self):
        return {
            "access_token": "tok_buk_test",
            "company_id": 42,
            "timeout": 5,
            "max_paginas": 3,
        }

    @pytest.fixture
    def adapter(self, config):
        from adapters.buk_adapter import BukAdapter
        return BukAdapter(config)

    def _mock_paginar(self, adapter, items: list):
        return patch.object(adapter, "_paginar", return_value=items)

    # --- get_resumen_dotacion ---

    def test_get_resumen_dotacion_normaliza_campos(self, adapter):
        raw = [{
            "id": 1, "first_name": "Ana", "last_name": "López",
            "job_title": "Vendedora", "department": "Ventas", "status": "activo",
        }]
        with self._mock_paginar(adapter, raw):
            resultado = adapter.get_resumen_dotacion()
        assert len(resultado) == 1
        r = resultado[0]
        assert r["empleado_id"] == 1
        assert r["nombre"] == "Ana López"
        assert r["cargo"] == "Vendedora"
        assert r["departamento"] == "Ventas"
        assert r["estado"] == "activo"

    def test_get_resumen_dotacion_usa_position_si_no_hay_job_title(self, adapter):
        raw = [{"id": 2, "first_name": "Luis", "last_name": "R",
                "job_title": None, "position": "Bodeguero", "department": "", "status": "activo"}]
        with self._mock_paginar(adapter, raw):
            resultado = adapter.get_resumen_dotacion()
        assert resultado[0]["cargo"] == "Bodeguero"

    def test_get_resumen_dotacion_vacia_devuelve_lista_vacia(self, adapter):
        with self._mock_paginar(adapter, []):
            assert adapter.get_resumen_dotacion() == []

    # --- get_ausencias ---

    def test_get_ausencias_normaliza_campos(self, adapter):
        raw = [{
            "employee": {"id": 5, "first_name": "Carlos", "last_name": "M"},
            "leave_type": "Licencia médica",
            "start_date": "2026-07-01", "end_date": "2026-07-05",
            "business_days": 4.0, "status": "aprobada",
        }]
        with self._mock_paginar(adapter, raw):
            resultado = adapter.get_ausencias("2026-07-01", "2026-07-31")
        assert len(resultado) == 1
        a = resultado[0]
        assert a["empleado_id"] == 5
        assert a["nombre"] == "Carlos M"
        assert a["tipo_ausencia"] == "Licencia médica"
        assert a["fecha_inicio"] == "2026-07-01"
        assert a["dias_habiles"] == 4.0
        assert a["estado"] == "aprobada"

    def test_get_ausencias_usa_employee_id_si_no_hay_objeto_employee(self, adapter):
        raw = [{"employee_id": 9, "employee": None,
                "leave_type": "Vacaciones", "start_date": "2026-08-01",
                "end_date": "2026-08-10", "days": 8, "status": "aprobada"}]
        with self._mock_paginar(adapter, raw):
            resultado = adapter.get_ausencias("2026-08-01", "2026-08-31")
        assert resultado[0]["empleado_id"] == 9
        assert resultado[0]["dias_habiles"] == 8.0

    def test_get_ausencias_vacia_devuelve_lista_vacia(self, adapter):
        with self._mock_paginar(adapter, []):
            assert adapter.get_ausencias("2026-07-01", "2026-07-31") == []

    # --- test_conexion ---

    def test_test_conexion_ok(self, adapter):
        with patch.object(adapter, "_get", return_value={"id": 42, "name": "Empresa"}):
            assert adapter.test_conexion() is True

    def test_test_conexion_error_red_false(self, adapter):
        import urllib.error
        with patch.object(adapter, "_get", side_effect=urllib.error.URLError("timeout")):
            assert adapter.test_conexion() is False

    # --- config ---

    def test_config_lee_company_id_desde_tenant(self, config):
        config_custom = {**config, "company_id": 99, "access_token": "otro_tok"}
        from adapters.buk_adapter import BukAdapter
        a = BukAdapter(config_custom)
        assert a._company_id == 99
        assert a._token == "otro_tok"


class TestERPAdapterContrato:
    """Verifica que el contrato base funcione correctamente."""

    def test_adapter_concreto_implementa_todos_los_metodos(self):
        p = Producto(codigo="A1", descripcion="Test")
        assert p.codigo == "A1"
        assert p.activo is True  # default

        s = Stock(codigo="A1", bodega="BOD1", cantidad=10.0)
        assert s.cantidad == 10.0

        v = Venta(fecha="2026-07-01", codigo="A1", descripcion="X", cantidad=1, precio=100)
        assert v.vendedor is None  # default

        ped = Pedido(numero="P001", fecha="2026-07-01", proveedor="Prov")
        assert ped.lineas == []  # default
