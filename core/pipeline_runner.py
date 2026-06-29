"""
pipeline_runner.py — Orquestador genérico del pipeline ERP -> JSON -> Firebase.

Lee un tenant.json, instancia el ERPAdapter correspondiente (registrado en
adapters/), corre los pasos de descarga/generación, valida con
core/validator.py y deja los JSON listos para deploy. Sin lógica de negocio
de ningún cliente — eso vive en cada adapter.
"""

# TODO: registro de adapters por "tipo" (justweb, transtecnia, rexplus, excel)
ADAPTERS_DISPONIBLES = {
    # "justweb": JustWebAdapter,
    # "transtecnia": TranstecniaAdapter,
    # "rexplus": RexPlusAdapter,
    # "excel": ExcelAdapter,
}


def cargar_tenant(tenant_id: str) -> dict:
    """TODO: leer tenants/{tenant_id}.json y devolver el dict de config."""
    raise NotImplementedError


def construir_adapter(tenant_config: dict):
    """TODO: instanciar el ERPAdapter según tenant_config['erp']['tipo']."""
    raise NotImplementedError


def correr_pipeline(tenant_id: str) -> None:
    """TODO: orquestar get_productos/get_stock/get_ventas/get_pedidos,
    escribir con core/json_writer.py y validar con core/validator.py."""
    raise NotImplementedError


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python pipeline_runner.py <tenant_id>")
        sys.exit(1)
    correr_pipeline(sys.argv[1])
