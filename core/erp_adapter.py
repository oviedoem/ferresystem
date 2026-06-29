"""
erp_adapter.py — Contrato base que debe implementar cada ERP soportado.

Todo adaptador en adapters/ debe heredar de ERPAdapter e implementar los
5 métodos abstractos. El resto del pipeline (core/pipeline_runner.py) solo
conoce esta interfaz, nunca el ERP concreto.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


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
