"""
pipeline_runner.py — Orquestador genérico del pipeline ERP -> JSON -> Firebase.

Lee un tenant.json, instancia el ERPAdapter correspondiente (registrado en
ADAPTERS_DISPONIBLES), corre los pasos de descarga/generación, valida con
core/validator.py y deja los JSON listos para deploy.

Sin lógica de negocio de ningún cliente — eso vive en cada adapter.
"""
import json
import os
import sys
from datetime import date

from core.erp_adapter import ERPAdapter
from core.json_writer import escribir_wrapped, escribir_raw_dict
from core.logger import get_logger

# ---------------------------------------------------------------------------
# Registro de adaptadores disponibles
# Para agregar uno nuevo: importarlo aquí y añadirlo al dict.
# ---------------------------------------------------------------------------
from adapters.justweb_adapter import JustWebAdapter
from adapters.excel_adapter import ExcelAdapter

try:
    from adapters.transtecnia_adapter import TranstecniaAdapter
except ImportError:
    TranstecniaAdapter = None

try:
    from adapters.rexplus_adapter import RexPlusAdapter
except ImportError:
    RexPlusAdapter = None

try:
    from adapters.buk_adapter import BukAdapter
except ImportError:
    BukAdapter = None

ADAPTERS_DISPONIBLES: dict = {
    "justweb": JustWebAdapter,
    "excel": ExcelAdapter,
}
if TranstecniaAdapter:
    ADAPTERS_DISPONIBLES["transtecnia"] = TranstecniaAdapter
if RexPlusAdapter:
    ADAPTERS_DISPONIBLES["rexplus"] = RexPlusAdapter

log = get_logger("pipeline_runner")

TENANTS_DIR = os.path.join(os.path.dirname(__file__), "..", "tenants")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def cargar_tenant(tenant_id: str) -> dict:
    """Lee tenants/{tenant_id}.json y devuelve el dict de configuración."""
    ruta = os.path.normpath(os.path.join(TENANTS_DIR, f"{tenant_id}.json"))
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"Tenant no encontrado: {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def construir_adapter(tenant_config: dict) -> ERPAdapter:
    """Instancia el ERPAdapter según tenant_config['erp']['tipo']."""
    tipo = tenant_config.get("erp", {}).get("tipo", "")
    cls = ADAPTERS_DISPONIBLES.get(tipo)
    if cls is None:
        raise ValueError(
            f"Tipo de ERP no soportado: '{tipo}'. "
            f"Disponibles: {list(ADAPTERS_DISPONIBLES.keys())}"
        )
    return cls(tenant_config["erp"])


def correr_pipeline(tenant_id: str, fecha_desde: str = None, fecha_hasta: str = None) -> None:
    """Orquesta el pipeline completo para un tenant:

    1. Carga configuración del tenant.
    2. Instancia el adapter ERP.
    3. Verifica conexión.
    4. Descarga productos, stock, ventas y pedidos.
    5. Escribe los JSON de salida en data/{tenant_id}/.
    6. Si hay adapter RR.HH. (Buk), agrega resumen de dotación.

    Args:
        tenant_id:   ID del cliente (debe coincidir con tenants/{id}.json).
        fecha_desde: ISO date (YYYY-MM-DD). Default: hoy.
        fecha_hasta: ISO date (YYYY-MM-DD). Default: hoy.
    """
    hoy = date.today().isoformat()
    fecha_desde = fecha_desde or hoy
    fecha_hasta = fecha_hasta or hoy

    log.info(f"=== Iniciando pipeline para tenant: {tenant_id} ===")

    # 1. Config
    tenant = cargar_tenant(tenant_id)
    nombre = tenant.get("nombre_comercial", tenant_id)
    log.info(f"Tenant cargado: {nombre}")

    # 2. Adapter ERP
    adapter = construir_adapter(tenant)
    log.info(f"Adapter ERP: {type(adapter).__name__}")

    # 3. Test de conexión
    if not adapter.test_conexion():
        log.error("Fallo el test de conexion con el ERP. Pipeline abortado.")
        sys.exit(1)
    log.info("Conexion ERP: OK")

    # Directorio de salida por tenant
    out_dir = os.path.normpath(os.path.join(OUTPUT_DIR, tenant_id))
    os.makedirs(out_dir, exist_ok=True)
    fuente = tenant["erp"]["tipo"]

    # 4a. Productos
    log.info("Descargando productos...")
    productos = adapter.get_productos()
    escribir_wrapped(
        os.path.join(out_dir, "productos.json"),
        productos, fuente
    )
    log.info(f"Productos escritos: {len(productos)}")

    # 4b. Stock
    log.info("Descargando stock...")
    stock = adapter.get_stock()
    # Además del wrapped, un dict keyed por código para lookups O(1)
    stock_dict = {s.codigo: {"bodega": s.bodega, "cantidad": s.cantidad} for s in stock}
    escribir_wrapped(
        os.path.join(out_dir, "stock.json"),
        stock, fuente
    )
    escribir_raw_dict(
        os.path.join(out_dir, "stock_por_codigo.json"),
        stock_dict
    )
    log.info(f"Stock escrito: {len(stock)} líneas")

    # 4c. Ventas
    log.info(f"Descargando ventas {fecha_desde} → {fecha_hasta}...")
    ventas = adapter.get_ventas(fecha_desde, fecha_hasta)
    escribir_wrapped(
        os.path.join(out_dir, "ventas.json"),
        ventas, fuente,
        extra={"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta}
    )
    log.info(f"Ventas escritas: {len(ventas)}")

    # 4d. Pedidos
    log.info("Descargando pedidos...")
    pedidos = adapter.get_pedidos()
    escribir_wrapped(
        os.path.join(out_dir, "pedidos.json"),
        pedidos, fuente
    )
    log.info(f"Pedidos escritos: {len(pedidos)}")

    # 5. RR.HH. (Buk) — opcional
    rrhh_cfg = tenant.get("rrhh")
    if rrhh_cfg and BukAdapter:
        log.info("Procesando datos RR.HH. (Buk)...")
        try:
            buk = BukAdapter(rrhh_cfg)
            resumen_rrhh = buk.get_resumen_dotacion()
            escribir_wrapped(
                os.path.join(out_dir, "rrhh_resumen.json"),
                resumen_rrhh, "buk"
            )
            log.info(f"RR.HH. escrito: {len(resumen_rrhh)} registros")
        except Exception as exc:
            log.warning(f"Error al obtener datos RR.HH.: {exc} (se continúa)")

    log.info(f"=== Pipeline {tenant_id} completado OK ===")


# ---------------------------------------------------------------------------
# Entry point CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pipeline_runner.py <tenant_id> [fecha_desde] [fecha_hasta]")
        sys.exit(1)

    _tid   = sys.argv[1]
    _desde = sys.argv[2] if len(sys.argv) > 2 else None
    _hasta = sys.argv[3] if len(sys.argv) > 3 else None
    correr_pipeline(_tid, _desde, _hasta)
