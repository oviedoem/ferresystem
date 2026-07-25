"""
test_bsale_adapter.py — Tests unitarios para BsaleAdapter refactorizado.
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.bsale_adapter import BsaleAdapter


@pytest.fixture
def config():
    return {
        "access_token": "tok_test_abc123",
        "office_ids": [1, 2],
        "timeout": 5,
        "max_paginas": 3,
    }


@pytest.fixture
def adapter(config):
    return BsaleAdapter(config)


class TestBsaleAdapter:
    def _mock_get(self, adapter, responses: dict):
        def fake_get(path, params=None):
            for key, val in responses.items():
                if key in path:
                    return val
            return {"items": []}
        return patch.object(adapter._client, "get", side_effect=fake_get)

    def test_get_productos_mapea_variantes(self, adapter):
        resp = {
            "items": [{
                "name": "Tornillo", "brand": "Heco",
                "variants": {"items": [
                    {"id": 1, "code": "TOR-001", "description": '6x1"', "state": 1,
                     "costs": {"items": [{"cost": 1490}]}},
                ]},
            }],
            "count": 1,
        }
        with self._mock_get(adapter, {"products": resp}):
            prods = adapter.get_productos()
            assert len(prods) == 1
            assert prods[0].codigo == "TOR-001"
            assert prods[0].precio == 1490.0
            assert prods[0].activo is True

    def test_get_stock_filtra_por_office_ids(self, adapter):
        resp = {
            "items": [
                {"variantCode": "A001", "officeName": "Suc1", "officeId": 1, "quantityAvailable": 50},
                {"variantCode": "A001", "officeName": "Suc3", "officeId": 3, "quantityAvailable": 10},
                {"variantCode": "A002", "officeName": "Suc2", "officeId": 2, "quantityAvailable": 20},
            ],
            "count": 3,
        }
        with self._mock_get(adapter, {"stocks": resp}):
            stock = adapter.get_stock()
            assert len(stock) == 2
            assert "Suc3" not in {s.bodega for s in stock}

    def test_test_conexion_ok(self, adapter):
        with patch.object(adapter._client, "get", return_value={"items": [{"id": 1}]}):
            assert adapter.test_conexion() is True

    def test_test_conexion_excepcion_false(self, adapter):
        with patch.object(adapter._client, "get", side_effect=Exception("timeout")):
            assert adapter.test_conexion() is False
