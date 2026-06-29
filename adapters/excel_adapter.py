"""
excel_adapter.py — Adaptador universal de fallback: lee planillas Excel/CSV
exportadas manualmente cuando el ERP no tiene integración directa.
"""
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido


class ExcelAdapter(ERPAdapter):
    # TODO: usar self.config['rutas'] (definidas en tenant.json) para ubicar
    # los archivos .xlsx/.csv de productos, stock, ventas y pedidos.

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
