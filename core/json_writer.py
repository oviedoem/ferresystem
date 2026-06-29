"""
json_writer.py — Escritor estándar de JSONs de salida del pipeline.

Formato "wrapped" homologado entre clientes:
  {"generado": ISO8601, "fuente": str, "total": int, "registros": [...]}

Mantener este contrato es lo que permite que core/validator.py y los
paneles white-label sean genéricos.
"""
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone


def _timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serializable(obj):
    """Convierte dataclasses a dict; el resto pasa tal cual."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Objeto no serializable: {type(obj)}")


def escribir_wrapped(ruta: str, registros: list, fuente: str, extra: dict = None) -> None:
    """Arma el dict wrapped estándar y lo escribe en ruta (UTF-8, indent=2).

    Args:
        ruta:      Ruta de destino del JSON (se crea el directorio si no existe).
        registros: Lista de dataclasses o dicts a serializar en "registros".
        fuente:    Nombre del origen de datos (ej. "justweb", "excel").
        extra:     Claves adicionales que se mezclan al nivel raíz del wrapper.
    """
    os.makedirs(os.path.dirname(ruta) if os.path.dirname(ruta) else ".", exist_ok=True)

    payload: dict = {
        "generado": _timestamp_iso(),
        "fuente": fuente,
        "total": len(registros),
        "registros": registros,
    }
    if extra:
        payload.update(extra)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=_serializable)


def escribir_raw_dict(ruta: str, datos: dict) -> None:
    """Escribe un dict plano keyed por código, sin envoltorio.

    Útil para lookups rápidos desde el panel (ej. stock_por_codigo.json).
    """
    os.makedirs(os.path.dirname(ruta) if os.path.dirname(ruta) else ".", exist_ok=True)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=_serializable)
