"""
json_writer.py — Escritor estándar de JSONs de salida del pipeline.

Formato "wrapped" homologado entre clientes: {"generado": ISO8601, "fuente": str,
"total": int, "registros": [...]}. Mantener este contrato es lo que permite
que core/validator.py y los paneles white-label sean genéricos.
"""
import json
import os
from datetime import datetime, timezone


def escribir_wrapped(ruta: str, registros: list, fuente: str, extra: dict = None) -> None:
    """TODO: armar el dict wrapped estándar y escribirlo en ruta (UTF-8, indent)."""
    raise NotImplementedError


def escribir_raw_dict(ruta: str, datos: dict) -> None:
    """TODO: escribir un dict plano keyed por código, sin envoltorio."""
    raise NotImplementedError


def _timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
