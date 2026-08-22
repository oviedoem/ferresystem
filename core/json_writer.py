"""
json_writer.py — Escritor estándar de JSONs de salida del pipeline.

Formato "wrapped" homologado entre clientes:
 {"generado": ISO8601, "fuente": str, "total": int, "registros": [...]}

v0.2: Agrega soporte de staging (escribe primero en .staging/ y promueve
solo si la validación pasa). Esto evita dejar JSONs rotos o parciales
en data/{tenant_id}/.
"""
import json
import os
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional


def _timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serializable(obj):
    """Convierte dataclasses a dict; el resto pasa tal cual."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Objeto no serializable: {type(obj)}")


def _ensure_dir(ruta: str) -> None:
    d = os.path.dirname(ruta)
    if d:
        os.makedirs(d, exist_ok=True)


def escribir_wrapped(
    ruta: str,
    registros: list,
    fuente: str,
    extra: Optional[dict] = None,
    staging: bool = False,
) -> str:
    """Arma el dict wrapped estándar y lo escribe en ruta (UTF-8, indent=2).

    Args:
        ruta: Ruta de destino del JSON.
        registros: Lista de dataclasses o dicts a serializar en "registros".
        fuente: Nombre del origen de datos (ej. "justweb", "excel").
        extra: Claves adicionales que se mezclan al nivel raíz del wrapper.
        staging: Si True, escribe en el directorio .staging/ paralelo a ruta.

    Returns:
        La ruta real donde se escribió el archivo (puede ser staging).
    """
    payload: dict = {
        "generado": _timestamp_iso(),
        "fuente": fuente,
        "total": len(registros),
        "registros": registros,
    }
    if extra:
        payload.update(extra)

    destino = ruta
    if staging:
        base = os.path.dirname(ruta) if os.path.dirname(ruta) else "."
        staging_dir = os.path.join(base, ".staging")
        os.makedirs(staging_dir, exist_ok=True)
        destino = os.path.join(staging_dir, os.path.basename(ruta))

    _ensure_dir(destino)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=_serializable)

    return destino


def escribir_raw_dict(ruta: str, datos: dict, staging: bool = False) -> str:
    """Escribe un dict plano keyed por código, sin envoltorio.

    Útil para lookups rápidos desde el panel (ej. stock_por_codigo.json).
    """
    destino = ruta
    if staging:
        base = os.path.dirname(ruta) if os.path.dirname(ruta) else "."
        staging_dir = os.path.join(base, ".staging")
        os.makedirs(staging_dir, exist_ok=True)
        destino = os.path.join(staging_dir, os.path.basename(ruta))

    _ensure_dir(destino)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=_serializable)

    return destino


def promover_staging(data_dir: str) -> list[str]:
    """Mueve todos los archivos de data_dir/.staging/ a data_dir/.

    Returns:
        Lista de rutas promovidas.
    """
    staging_dir = os.path.join(data_dir, ".staging")
    if not os.path.isdir(staging_dir):
        return []

    promovidos = []
    for nombre in os.listdir(staging_dir):
        src = os.path.join(staging_dir, nombre)
        dst = os.path.join(data_dir, nombre)
        shutil.move(src, dst)
        promovidos.append(dst)

    os.rmdir(staging_dir)
    return promovidos


def limpiar_staging(data_dir: str) -> None:
    """Borra data_dir/.staging/ sin promover (útil tras un error)."""
    staging_dir = os.path.join(data_dir, ".staging")
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir)
