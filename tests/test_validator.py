"""
test_validator.py — Tests unitarios para core/validator.py

Cubre todas las ramas de validar_pipeline():
- Archivo no existe (obligatorio y opcional)
- Archivo vacío
- JSON inválido
- kind raw_list: lista OK, vacía, no-lista
- kind raw_dict: dict OK, vacío, no-dict
- kind wrapped: claves OK, claves faltantes, array_field OK, vacío, no-lista/dict
- kind desconocido
- Múltiples archivos: todos OK, algunos errores
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.validator import validar_pipeline
from tests.conftest import escribir_json


# ─── raw_list ────────────────────────────────────────────────────────────────

class TestRawList:
    def test_lista_ok(self, tmp_path, schema_raw_list):
        escribir_json(tmp_path / "items.json", [{"a": 1}, {"b": 2}])
        assert validar_pipeline(str(tmp_path), schema_raw_list) is True

    def test_lista_vacia_falla(self, tmp_path, schema_raw_list):
        escribir_json(tmp_path / "items.json", [])
        assert validar_pipeline(str(tmp_path), schema_raw_list) is False

    def test_no_es_lista_falla(self, tmp_path, schema_raw_list):
        escribir_json(tmp_path / "items.json", {"clave": "valor"})
        assert validar_pipeline(str(tmp_path), schema_raw_list) is False

    def test_lista_un_elemento_ok(self, tmp_path, schema_raw_list):
        escribir_json(tmp_path / "items.json", [42])
        assert validar_pipeline(str(tmp_path), schema_raw_list) is True


# ─── raw_dict ────────────────────────────────────────────────────────────────

class TestRawDict:
    def test_dict_ok(self, tmp_path, schema_raw_dict):
        escribir_json(tmp_path / "config.json", {"key": "val"})
        assert validar_pipeline(str(tmp_path), schema_raw_dict) is True

    def test_dict_vacio_falla(self, tmp_path, schema_raw_dict):
        escribir_json(tmp_path / "config.json", {})
        assert validar_pipeline(str(tmp_path), schema_raw_dict) is False

    def test_no_es_dict_falla(self, tmp_path, schema_raw_dict):
        escribir_json(tmp_path / "config.json", [1, 2, 3])
        assert validar_pipeline(str(tmp_path), schema_raw_dict) is False


# ─── wrapped ─────────────────────────────────────────────────────────────────

class TestWrapped:
    def _schema(self, **kwargs):
        spec = {"kind": "wrapped", "keys": ["fuente", "datos"], "array_field": "datos"}
        spec.update(kwargs)
        return {"productos.json": spec}

    def test_wrapped_ok(self, tmp_path):
        schema = self._schema()
        escribir_json(tmp_path / "productos.json", {
            "fuente": "justweb", "datos": [{"sku": "A1"}]
        })
        assert validar_pipeline(str(tmp_path), schema) is True

    def test_wrapped_clave_faltante(self, tmp_path):
        schema = self._schema()
        # Falta "fuente"
        escribir_json(tmp_path / "productos.json", {"datos": [{"sku": "A1"}]})
        assert validar_pipeline(str(tmp_path), schema) is False

    def test_wrapped_array_field_vacio(self, tmp_path):
        schema = self._schema()
        escribir_json(tmp_path / "productos.json", {
            "fuente": "justweb", "datos": []
        })
        assert validar_pipeline(str(tmp_path), schema) is False

    def test_wrapped_array_field_no_es_lista_ni_dict(self, tmp_path):
        schema = self._schema()
        escribir_json(tmp_path / "productos.json", {
            "fuente": "justweb", "datos": "cadena"
        })
        assert validar_pipeline(str(tmp_path), schema) is False

    def test_wrapped_array_field_es_dict_ok(self, tmp_path):
        # array_field puede ser dict (stock_por_codigo.json)
        schema = {"config.json": {"kind": "wrapped", "keys": ["fuente"], "array_field": "mapa"}}
        escribir_json(tmp_path / "config.json", {
            "fuente": "test", "mapa": {"A1": 5, "A2": 3}
        })
        assert validar_pipeline(str(tmp_path), schema) is True

    def test_wrapped_sin_array_field_ok(self, tmp_path):
        schema = {"meta.json": {"kind": "wrapped", "keys": ["version"]}}
        escribir_json(tmp_path / "meta.json", {"version": "1.0"})
        assert validar_pipeline(str(tmp_path), schema) is True

    def test_wrapped_keys_vacias_ok(self, tmp_path):
        # Si keys=[] no hay claves requeridas — solo valida que sea dict
        schema = {"meta.json": {"kind": "wrapped"}}
        escribir_json(tmp_path / "meta.json", {"cualquier": "cosa"})
        assert validar_pipeline(str(tmp_path), schema) is True

    def test_wrapped_no_es_dict_falla(self, tmp_path):
        schema = self._schema()
        escribir_json(tmp_path / "productos.json", [1, 2, 3])
        assert validar_pipeline(str(tmp_path), schema) is False


# ─── Archivos ausentes y opcionales ──────────────────────────────────────────

class TestAusentes:
    def test_archivo_no_existe_falla(self, tmp_path, schema_raw_list):
        # No creamos el archivo
        assert validar_pipeline(str(tmp_path), schema_raw_list) is False

    def test_archivo_opcional_no_existe_no_falla(self, tmp_path, schema_opcional):
        assert validar_pipeline(str(tmp_path), schema_opcional) is True

    def test_archivo_vacio_falla(self, tmp_path, schema_raw_list):
        (tmp_path / "items.json").write_bytes(b"")
        assert validar_pipeline(str(tmp_path), schema_raw_list) is False

    def test_json_invalido_falla(self, tmp_path, schema_raw_list):
        (tmp_path / "items.json").write_text("{no es json}", encoding="utf-8")
        assert validar_pipeline(str(tmp_path), schema_raw_list) is False


# ─── Kind desconocido ────────────────────────────────────────────────────────

class TestKindDesconocido:
    def test_kind_desconocido_falla(self, tmp_path):
        schema = {"x.json": {"kind": "inventado"}}
        escribir_json(tmp_path / "x.json", {"a": 1})
        assert validar_pipeline(str(tmp_path), schema) is False


# ─── Múltiples archivos ───────────────────────────────────────────────────────

class TestMultiplesArchivos:
    def test_todos_ok(self, tmp_path):
        schema = {
            "a.json": {"kind": "raw_list"},
            "b.json": {"kind": "raw_dict"},
        }
        escribir_json(tmp_path / "a.json", [1])
        escribir_json(tmp_path / "b.json", {"x": 1})
        assert validar_pipeline(str(tmp_path), schema) is True

    def test_uno_falla_devuelve_false(self, tmp_path):
        schema = {
            "ok.json":  {"kind": "raw_list"},
            "mal.json": {"kind": "raw_list"},
        }
        escribir_json(tmp_path / "ok.json", [1])
        escribir_json(tmp_path / "mal.json", [])  # vacía → error
        assert validar_pipeline(str(tmp_path), schema) is False

    def test_opcional_no_cuenta_como_error(self, tmp_path):
        schema = {
            "real.json":     {"kind": "raw_list"},
            "opcional.json": {"kind": "raw_list", "optional": True},
        }
        escribir_json(tmp_path / "real.json", [1, 2])
        # opcional.json no existe — no debe fallar
        assert validar_pipeline(str(tmp_path), schema) is True
