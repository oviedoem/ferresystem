"""
health_monitor.py — Registra el estado de cada run del pipeline por tenant.

Escribe data/{tenant_id}/health.json con el resultado del último run
y un historial de los últimos HISTORIAL_MAX runs.

Sin lógica de negocio — solo observabilidad genérica.
"""
import json
import os
import time
from datetime import datetime, timezone


HISTORIAL_MAX = 10


class PipelineHealth:
    """Acumula métricas de un run del pipeline y las persiste en health.json.

    Uso típico en pipeline_runner:
        health = PipelineHealth(tenant_id, out_dir)
        health.iniciar()
        try:
            ...
            health.registrar("productos", len(productos))
        except Exception as exc:
            _error = str(exc)
            raise
        finally:
            health.finalizar(error=_error)
    """

    def __init__(self, tenant_id: str, out_dir: str) -> None:
        self._tenant_id = tenant_id
        self._ruta = os.path.join(out_dir, "health.json")
        self._inicio: float = 0.0
        self._inicio_iso: str = ""
        self._registros: dict = {}

    def iniciar(self) -> None:
        """Marca el inicio del run y registra el timestamp UTC."""
        self._inicio = time.monotonic()
        self._inicio_iso = _now_iso()

    def registrar(self, tipo: str, count: int) -> None:
        """Registra el conteo de un tipo de dato descargado (productos, ventas…)."""
        self._registros[tipo] = count

    def finalizar(self, error: str = None) -> None:
        """Persiste el resultado del run en health.json.

        Siempre escribe — incluso si el pipeline falló — para que el
        panel-admin pueda mostrar el estado real del último intento.
        No lanza excepción si el write falla (no debe romper el flujo).
        """
        duracion = round(time.monotonic() - self._inicio, 2) if self._inicio else 0.0

        entrada = {
            "inicio": self._inicio_iso,
            "fin": _now_iso(),
            "duracion_seg": duracion,
            "estado": "error" if error else "ok",
            "error": error,
            "registros": self._registros,
        }

        historial = _leer_historial(self._ruta)
        historial.insert(0, entrada)
        historial = historial[:HISTORIAL_MAX]

        payload = {
            "tenant_id": self._tenant_id,
            "ultimo_run": entrada,
            "historial": historial,
        }

        try:
            with open(self._ruta, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _leer_historial(ruta: str) -> list:
    """Lee el historial previo de health.json; devuelve lista vacía si no existe."""
    if not os.path.isfile(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("historial", [])
    except (json.JSONDecodeError, OSError):
        return []
