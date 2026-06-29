"""
logger.py — Logger centralizado con timestamps para todos los scripts del pipeline.

Uso: from core.logger import get_logger; log = get_logger("nombre_paso")
"""
import logging
import sys


def get_logger(nombre: str) -> logging.Logger:
    """Configura y devuelve un logger con handler a stdout.

    Formato: [YYYY-MM-DD HH:MM:SS] [nombre] LEVEL msg
    Si el logger ya tiene handlers no los duplica (safe para re-import).
    """
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
