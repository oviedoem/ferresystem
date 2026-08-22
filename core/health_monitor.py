"""
health_monitor.py — Registra el estado de cada run del pipeline por tenant.

Escribe dos archivos en data/{tenant_id}/:
  health.json — último run + historial de los últimos HISTORIAL_MAX runs
  usage.json  — métricas acumuladas por mes para billing

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
        self._ruta        = os.path.join(out_dir, "health.json")
        self._ruta_usage  = os.path.join(out_dir, "usage.json")
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

        self._actualizar_usage(entrada)

    def _actualizar_usage(self, entrada: dict) -> None:
        """Acumula métricas del run en usage.json (por mes, para billing).

        Formato:
        {
          "tenant_id": "...",
          "updated_at": "...",
          "meses": {
            "2025-01": {
              "runs_ok": 28, "runs_error": 2,
              "records": { "productos": 45000, ... }
            }
          }
        }
        """
        mes = (entrada.get("inicio") or _now_iso())[:7]  # YYYY-MM

        usage = _leer_usage(self._ruta_usage, self._tenant_id)

        bucket = usage["meses"].setdefault(mes, {
            "runs_ok": 0,
            "runs_error": 0,
            "records": {},
        })

        if entrada.get("estado") == "ok":
            bucket["runs_ok"] = bucket.get("runs_ok", 0) + 1
        else:
            bucket["runs_error"] = bucket.get("runs_error", 0) + 1

        for tipo, count in (entrada.get("registros") or {}).items():
            bucket["records"][tipo] = bucket["records"].get(tipo, 0) + count

        usage["updated_at"] = _now_iso()

        try:
            with open(self._ruta_usage, "w", encoding="utf-8") as f:
                json.dump(usage, f, ensure_ascii=False, indent=2)
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


def _leer_usage(ruta: str, tenant_id: str) -> dict:
    """Lee usage.json existente o devuelve un esqueleto vacío."""
    if os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("meses"), dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"tenant_id": tenant_id, "updated_at": "", "meses": {}}
