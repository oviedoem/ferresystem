"""Tests para core/health_monitor.py"""
import json
import pytest
from core.health_monitor import PipelineHealth, HISTORIAL_MAX


def test_run_ok_escribe_health_json(tmp_path):
    hm = PipelineHealth("test_tenant", str(tmp_path))
    hm.iniciar()
    hm.registrar("productos", 100)
    hm.registrar("ventas", 5)
    hm.finalizar()

    ruta = tmp_path / "health.json"
    assert ruta.exists()
    data = json.loads(ruta.read_text())
    assert data["ultimo_run"]["estado"] == "ok"
    assert data["ultimo_run"]["error"] is None
    assert data["ultimo_run"]["registros"]["productos"] == 100
    assert data["ultimo_run"]["registros"]["ventas"] == 5
    assert data["ultimo_run"]["duracion_seg"] >= 0
    assert len(data["historial"]) == 1


def test_run_error_registra_estado_y_mensaje(tmp_path):
    hm = PipelineHealth("test_tenant", str(tmp_path))
    hm.iniciar()
    hm.finalizar(error="Fallo la conexion al ERP")

    data = json.loads((tmp_path / "health.json").read_text())
    assert data["ultimo_run"]["estado"] == "error"
    assert "Fallo la conexion" in data["ultimo_run"]["error"]


def test_historial_acumula_en_orden_cronologico_inverso(tmp_path):
    for i in range(3):
        hm = PipelineHealth("test_tenant", str(tmp_path))
        hm.iniciar()
        hm.registrar("productos", i * 10)
        hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert len(data["historial"]) == 3
    # el más reciente queda primero
    assert data["historial"][0]["registros"]["productos"] == 20
    assert data["historial"][2]["registros"]["productos"] == 0


def test_historial_no_supera_max(tmp_path):
    for _ in range(HISTORIAL_MAX + 5):
        hm = PipelineHealth("test_tenant", str(tmp_path))
        hm.iniciar()
        hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert len(data["historial"]) == HISTORIAL_MAX


def test_tenant_id_incluido_en_payload(tmp_path):
    hm = PipelineHealth("mi_cliente", str(tmp_path))
    hm.iniciar()
    hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert data["tenant_id"] == "mi_cliente"


def test_ultimo_run_coincide_con_primer_historial(tmp_path):
    hm = PipelineHealth("t", str(tmp_path))
    hm.iniciar()
    hm.registrar("stock", 42)
    hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert data["ultimo_run"] == data["historial"][0]


def test_finalizar_sin_iniciar_no_lanza(tmp_path):
    hm = PipelineHealth("test_tenant", str(tmp_path))
    hm.finalizar()  # sin llamar iniciar()
    assert (tmp_path / "health.json").exists()
    data = json.loads((tmp_path / "health.json").read_text())
    assert data["ultimo_run"]["duracion_seg"] == 0.0


def test_health_json_corrupto_no_bloquea_siguiente_run(tmp_path):
    (tmp_path / "health.json").write_text("{ json roto")
    hm = PipelineHealth("test_tenant", str(tmp_path))
    hm.iniciar()
    hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert data["ultimo_run"]["estado"] == "ok"
    # el historial corrupto se descarta limpiamente
    assert len(data["historial"]) == 1


def test_run_sin_registros_es_valido(tmp_path):
    hm = PipelineHealth("t", str(tmp_path))
    hm.iniciar()
    hm.finalizar()

    data = json.loads((tmp_path / "health.json").read_text())
    assert data["ultimo_run"]["registros"] == {}
