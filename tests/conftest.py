"""
conftest.py — Fixtures compartidos para la suite de tests de FerreSystem.

Proporciona directorios temporales y schemas de prueba reutilizables
para tests de validator, adapters y pipeline.
"""
import json
import os
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Directorio temporal con JSONs de prueba ya escritos."""
    return tmp_path


@pytest.fixture
def schema_wrapped():
    """Schema tipo 'wrapped' con campo de conteo — el más común en FerreSystem."""
    return {
        "productos.json": {
            "kind": "wrapped",
            "keys": ["fuente", "generado", "datos"],
            "array_field": "datos",
        }
    }


@pytest.fixture
def schema_raw_list():
    return {"items.json": {"kind": "raw_list"}}


@pytest.fixture
def schema_raw_dict():
    return {"config.json": {"kind": "raw_dict"}}


@pytest.fixture
def schema_opcional():
    return {"opcional.json": {"kind": "raw_list", "optional": True}}


def escribir_json(path, data):
    """Helper: escribe data como JSON en path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
