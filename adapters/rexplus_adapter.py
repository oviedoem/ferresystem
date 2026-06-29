"""
rexplus_adapter.py — Adaptador para ERP Rex Plus. Esqueleto vacío.
"""
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido


class RexPlusAdapter(ERPAdapter):
    # TODO: implementar los 5 métodos abstractos para Rex Plus

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
