"""
erp_adapter.py — Contrato base que debe implementar cada ERP soportado.

Todo adaptador en adapters/ debe heredar de ERPAdapter e implementar los
5 métodos abstractos. El resto del pipeline (core/pipeline_runner.py) solo
conoce esta interfaz, nunca el ERP concreto.
"""
import functools
import logging as _logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

_log = _logging.getLogger("ferresystem.retry")


@dataclass
class Producto:
    codigo: str
    descripcion: str
    marca: Optional[str] = None
    precio: Optional[float] = None
    activo: bool = True


@dataclass
class Stock:
    codigo: str
    bodega: str
    cantidad: float


@dataclass
class Venta:
    fecha: str
    codigo: str
    descripcion: str
    cantidad: float
    precio: float
    vendedor: Optional[str] = None
    cliente: Optional[str] = None


@dataclass
class Pedido:
    numero: str
    fecha: str
    proveedor: str
    lineas: list = field(default_factory=list)


class ERPAdapter(ABC):
    """Interfaz que todo adaptador de ERP debe cumplir.

    config viene de tenants/{tenant_id}.json → bloque "erp".
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def get_productos(self) -> list[Producto]:
        ...

    @abstractmethod
    def get_stock(self) -> list[Stock]:
        ...

    @abstractmethod
    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        ...

    @abstractmethod
    def get_pedidos(self) -> list[Pedido]:
        ...

    @abstractmethod
    def test_conexion(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# Decorador de reintento
# ---------------------------------------------------------------------------

def with_retry(
    max_intentos: int = 3,
    backoff_base: float = 2.0,
    excepciones: tuple = (Exception,),
):
    """Decorador de reintento con backoff exponencial para métodos de ERPAdapter.

    Parámetros:
        max_intentos:  Número máximo de intentos (default 3).
        backoff_base:  Base del backoff en segundos — espera backoff_base^intento
                       entre reintentos: 2s → 4s → 8s con base=2 (default).
        excepciones:   Tupla de tipos de excepción que activan el reintento.
                       Por defecto captura cualquier Exception.

    Uso:
        class MiAdapter(ERPAdapter):
            @with_retry()
            def get_productos(self):
                ...

            @with_retry(max_intentos=5, backoff_base=1.5, excepciones=(IOError,))
            def get_ventas(self, desde, hasta):
                ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            ultimo_exc = None
            for intento in range(1, max_intentos + 1):
                try:
                    return fn(*args, **kwargs)
                except excepciones as exc:
                    ultimo_exc = exc
                    if intento == max_intentos:
                        break
                    espera = backoff_base ** intento
                    _log.warning(
                        "with_retry: %s() intento %d/%d falló (%s). "
                        "Reintentando en %.1fs.",
                        getattr(fn, "__name__", repr(fn)),
                        intento, max_intentos, exc, espera,
                    )
                    time.sleep(espera)
            raise ultimo_exc
        return wrapper
    return decorator
