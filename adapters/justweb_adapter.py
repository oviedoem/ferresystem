"""
justweb_adapter.py — Adaptador para ERP JustWeb (SSRS + HTTP).

Basado en el flujo real usado en Ferretería Oviedo (ver AGENTS.md de ese
proyecto, sección FLUJO ERP), pero sin ninguna IP, usuario ni bodega
hardcodeada: todo viene de config (tenants/{id}.json -> "erp").
"""
from core.erp_adapter import ERPAdapter, Producto, Stock, Venta, Pedido


class JustWebAdapter(ERPAdapter):
    """TODO: implementar usando self.config['host'], ['puerto'], ['usuario'],
    ['password_enc'] descifrado. Reportes SSRS vía HTTP, parseo CSV con
    punto=miles / coma=decimal (ver docs/como_agregar_erp.md)."""

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
