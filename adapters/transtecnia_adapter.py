"""
transtecnia_adapter.py — Adaptador para ERP Transtecnia. Esqueleto vacío.
"""
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido


class TranstecniaAdapter(ERPAdapter):
    # TODO: implementar los 5 métodos abstractos para Transtecnia

    def get_productos(self) -> list[Producto]:
        raise NotImplementedError

    def get_stock(self) -> list[Stock]:
        raise NotImplementedError

    def get_ventas(self, desde: str, hasta: str) -> list[Venta]:
        raise NotImplementedError

    def get_pedidos(self) -> list[Pedido]:
        raise NotImplementedError

    def test_conexion(self) -> bool:
        raise NotImplementedError
