"""
test_pipeline_runner.py — Tests de integración end-to-end del pipeline.
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.pipeline_runner import correr_pipeline, cargar_tenant, construir_adapter
from core.exceptions import (
    TenantNotFoundError,
    ERPTypeNotSupportedError,
    ERPConnectionError,
    PipelineLockedError,
)
from core.erp_adapter import Producto, Stock, Venta, Pedido


@pytest.fixture
def tenant_config(tmp_path):
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()
    config = {
        "tenant_id": "test-tenant",
        "nombre_comercial": "Test Ferretería",
        "erp": {
            "tipo": "mock",
            "host": "localhost",
            "puerto": 80,
            "usuario": "user",
            "password_enc": "pass",
        },
        "bodegas": {"comerciales": ["BOD1"], "logisticas": ["BOD2"], "bodega_principal": "BOD1"},
        "firebase": {"project_id": "test", "hosting_url": "https://test.web.app"},
        "branding": {"nombre_corto": "Test", "color_primario": "#000"},
    }
    ruta = tenants_dir / "test-tenant.json"
    ruta.write_text(json.dumps(config), encoding="utf-8")
    return str(tenants_dir), "test-tenant", config


@pytest.fixture
def mock_adapter_cls():
    from core.erp_adapter import ERPAdapter

    class MockAdapter(ERPAdapter):
        def __init__(self, config):
            super().__init__(config)
            self._productos = [Producto(codigo="A001", descripcion="Tornillo", precio=100.0)]
            self._stock = [Stock(codigo="A001", bodega="BOD1", cantidad=50.0)]
            self._ventas = [Venta(fecha="2026-07-01", codigo="A001", descripcion="Tornillo", cantidad=2, precio=100.0)]
            self._pedidos = [Pedido(numero="P001", fecha="2026-07-01", proveedor="Prov", lineas=[{"codigo": "A001", "cantidad": 5}])]

        def get_productos(self): return self._productos
        def get_stock(self): return self._stock
        def get_ventas(self, desde, hasta): return [v for v in self._ventas if desde <= v.fecha <= hasta]
        def get_pedidos(self): return self._pedidos
        def test_conexion(self): return True

    return MockAdapter


class TestCargarTenant:
    def test_carga_ok(self, tenant_config):
        tenants_dir, tid, _ = tenant_config
        with patch("core.pipeline_runner.TENANTS_DIR", tenants_dir):
            cfg = cargar_tenant(tid)
            assert cfg["tenant_id"] == tid

    def test_tenant_no_existe(self, tenant_config):
        tenants_dir, _, _ = tenant_config
        with patch("core.pipeline_runner.TENANTS_DIR", tenants_dir):
            with pytest.raises(TenantNotFoundError):
                cargar_tenant("no-existe")


class TestConstruirAdapter:
    def test_mock_adapter_registrado(self, tenant_config, mock_adapter_cls):
        tenants_dir, tid, config = tenant_config
        with patch.dict("core.pipeline_runner.ADAPTERS_DISPONIBLES", {"mock": mock_adapter_cls}, clear=False):
            adapter = construir_adapter(config)
            assert isinstance(adapter, mock_adapter_cls)

    def test_tipo_no_soportado(self, tenant_config):
        tenants_dir, tid, config = tenant_config
        config["erp"]["tipo"] = "inventado"
        with pytest.raises(ERPTypeNotSupportedError):
            construir_adapter(config)


class TestPipelineEndToEnd:
    def test_pipeline_ok_genera_jsons(self, tmp_path, tenant_config, mock_adapter_cls):
        tenants_dir, tid, _ = tenant_config
        data_dir = str(tmp_path / "data")

        with patch("core.pipeline_runner.TENANTS_DIR", tenants_dir), \
             patch("core.pipeline_runner.OUTPUT_DIR", data_dir), \
             patch.dict("core.pipeline_runner.ADAPTERS_DISPONIBLES", {"mock": mock_adapter_cls}, clear=False):

            res = correr_pipeline(tid, "2026-07-01", "2026-07-31", skip_validation=False)
            assert res["estado"] == "ok"
            assert res["error"] is None

            out = os.path.join(data_dir, tid)
            assert os.path.isfile(os.path.join(out, "productos.json"))
            assert os.path.isfile(os.path.join(out, "stock.json"))
            assert os.path.isfile(os.path.join(out, "health.json"))
            assert not os.path.isdir(os.path.join(out, ".staging"))

    def test_pipeline_falla_conexion(self, tmp_path, tenant_config, mock_adapter_cls):
        tenants_dir, tid, _ = tenant_config
        data_dir = str(tmp_path / "data")

        class BadAdapter(mock_adapter_cls):
            def test_conexion(self): return False

        with patch("core.pipeline_runner.TENANTS_DIR", tenants_dir), \
             patch("core.pipeline_runner.OUTPUT_DIR", data_dir), \
             patch.dict("core.pipeline_runner.ADAPTERS_DISPONIBLES", {"mock": BadAdapter}, clear=False):

            with pytest.raises(ERPConnectionError):
                correr_pipeline(tid, skip_validation=True)
            assert not os.path.isfile(os.path.join(data_dir, tid, ".pipeline.lock"))

    def test_pipeline_lock_evita_concurrencia(self, tmp_path, tenant_config, mock_adapter_cls):
        tenants_dir, tid, _ = tenant_config
        data_dir = str(tmp_path / "data")
        os.makedirs(os.path.join(data_dir, tid), exist_ok=True)
        with open(os.path.join(data_dir, tid, ".pipeline.lock"), "w") as f:
            f.write("pid=1234\n")

        with patch("core.pipeline_runner.TENANTS_DIR", tenants_dir), \
             patch("core.pipeline_runner.OUTPUT_DIR", data_dir), \
             patch.dict("core.pipeline_runner.ADAPTERS_DISPONIBLES", {"mock": mock_adapter_cls}, clear=False):

            with pytest.raises(PipelineLockedError):
                correr_pipeline(tid, skip_validation=True)
