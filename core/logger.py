"""
logger.py — Logger centralizado con timestamps para todos los scripts del pipeline.

Uso: from core.logger import get_logger; log = get_logger("nombre_paso")
"""
import logging
import sys


def get_logger(nombre: str) -> logging.Logger:
    """TODO: configurar handler a stdout con formato '[YYYY-MM-DD HH:MM:SS] [nombre] msg'."""
    raise NotImplementedError
