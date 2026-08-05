"""
pipeline_runner.py — Orquestador genérico del pipeline ERP -> JSON -> Firebase.

v0.2 cambios:
- Sin sys.exit() — lanza excepciones custom.
- Lock file para evitar ejecuciones concurrentes por tenant.
- Staging: escribe primero en .staging/, promueve solo si valida OK.
- Mejor manejo de errores y logging.
"""
import json
import os
import sys
from datetime import date
from typing import Optional

from core.erp_adapter import ERPAdapter
from core.health_monitor import PipelineHealth
from core.json_writer import (
    escribir_wrapped, escribir_raw_dict, promover_staging, limpiar_staging
)
from core.logger import get_logger
from core.exceptions import (
    TenantNotFoundError,
    ERPTypeNotSupportedError,
    ERPConnectionError,
    PipelineLockedError,
    ValidationError,
)
from core.validator import validar_pipeline

# ---------------------------------------------------------------------------
# Registro de adaptadores disponibles
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
    from adapters.bsale_adapter import BsaleAdapter
except ImportError:
    BsaleAdapter = None

try:
    from adapters.buk_adapter import BukAdapter
except ImportError:
    BukAdapter = None

try:
    from adapters.defontana_adapter import DefontanaAdapter
except ImportError:
    DefontanaAdapter = None

try:
    from adapters.sheets_adapter import SheetsAdapter
except ImportError:
    SheetsAdapter = None

ADAPTERS_DISPONIBLES: dict = {
    "justweb": JustWebAdapter,
    "excel": ExcelAdapter,
}
if TranstecniaAdapter:
    ADAPTERS_DISPONIBLES["transtecnia"] = TranstecniaAdapter
if RexPlusAdapter:
    ADAPTERS_DISPONIBLES["rexplus"] = RexPlusAdapter
if BsaleAdapter:
    ADAPTERS_DISPONIBLES["bsale"] = BsaleAdapter
if DefontanaAdapter:
    ADAPTERS_DISPONIBLES["defontana"] = DefontanaAdapter
if SheetsAdapter:
    ADAPTERS_DISPONIBLES["sheets"] = SheetsAdapter

log = get_logger("pipeline_runner")

TENANTS_DIR = os.path.join(os.path.dirname(__file__), "..", "tenants")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------

def _lock_path(tenant_id: str) -> str:
    return os.path.join(OUTPUT_DIR, tenant_id, ".pipeline.lock")


def _adquirir_lock(tenant_id: str) -> None:
    lock = _lock_path(tenant_id)
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    if os.path.isfile(lock):
        raise PipelineLockedError(
            f"Pipeline ya en ejecución para tenant '{tenant_id}'. "
            f"Borra manualmente {lock} si estás seguro de que no hay otra instancia corriendo."
        )
    with open(lock, "w", encoding="utf-8") as f:
        f.write(f"pid={os.getpid()}\nstarted={date.today().isoformat()}\n")
    log.debug("Lock adquirido: %s", lock)


def _liberar_lock(tenant_id: str) -> None:
    lock = _lock_path(tenant_id)
    try:
        if os.path.isfile(lock):
            os.remove(lock)
            log.debug("Lock liberado: %s", lock)
    except OSError as e:
        log.warning("No se pudo liberar lock %s: %s", lock, e)

# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def cargar_tenant(tenant_id: str) -> dict:
    """Lee tenants/{tenant_id}.json y devuelve el dict de configuración."""
    ruta = os.path.normpath(os.path.join(TENANTS_DIR, f"{tenant_id}.json"))
    if not os.path.isfile(ruta):
        raise TenantNotFoundError(f"Tenant no encontrado: {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def construir_adapter(tenant_config: dict) -> ERPAdapter:
    """Instancia el ERPAdapter según tenant_config['erp']['tipo']."""
    tipo = tenant_config.get("erp", {}).get("tipo", "")
    cls = ADAPTERS_DISPONIBLES.get(tipo)
    if cls is None:
        raise ERPTypeNotSupportedError(
            f"Tipo de ERP no soportado: '{tipo}'. "
            f"Disponibles: {list(ADAPTERS_DISPONIBLES.keys())}"
        )
    return cls(tenant_config["erp"])


def correr_pipeline(
    tenant_id: str,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    skip_validation: bool = False,
) -> dict:
    """Orquesta el pipeline completo para un tenant.

    Args:
        tenant_id: ID del cliente (debe coincidir con tenants/{id}.json).
        fecha_desde: ISO date (YYYY-MM-DD). Default: hoy.
        fecha_hasta: ISO date (YYYY-MM-DD). Default: hoy.
        skip_validation: Si True, omite la validación post-pipeline (útil para tests).

    Returns:
        Dict con resumen del run: {"estado": "ok"|"error", "registros": {...}, "error": str|None}

    Raises:
        TenantNotFoundError, ERPTypeNotSupportedError, ERPConnectionError,
        PipelineLockedError, ValidationError, o cualquier excepción del adapter.
    """
    hoy = date.today().isoformat()
    fecha_desde = fecha_desde or hoy
    fecha_hasta = fecha_hasta or hoy

    log.info("=== Iniciando pipeline para tenant: %s ===", tenant_id)

    _adquirir_lock(tenant_id)
    out_dir = os.path.normpath(os.path.join(OUTPUT_DIR, tenant_id))
    os.makedirs(out_dir, exist_ok=True)

    health = PipelineHealth(tenant_id, out_dir)
    health.iniciar()

    resultado = {"estado": "ok", "registros": {}, "error": None}

    try:
        # 1. Config
        tenant = cargar_tenant(tenant_id)
        nombre = tenant.get("nombre_comercial", tenant_id)
        log.info("Tenant cargado: %s", nombre)

        # 2. Adapter ERP
        adapter = construir_adapter(tenant)
        log.info("Adapter ERP: %s", type(adapter).__name__)

        # 3. Test de conexión
        if not adapter.test_conexion():
            raise ERPConnectionError("Fallo el test de conexion con el ERP")
        log.info("Conexion ERP: OK")

        fuente = tenant["erp"]["tipo"]

        # 4a. Productos
        log.info("Descargando productos...")
        productos = adapter.get_productos()
        health.registrar("productos", len(productos))
        escribir_wrapped(
            os.path.join(out_dir, "productos.json"),
            productos, fuente, staging=True
        )
        log.info("Productos escritos (staging): %d", len(productos))

        # 4b. Stock
        log.info("Descargando stock...")
        stock = adapter.get_stock()
        health.registrar("stock", len(stock))
        stock_dict = {s.codigo: {"bodega": s.bodega, "cantidad": s.cantidad} for s in stock}
        escribir_wrapped(
            os.path.join(out_dir, "stock.json"),
            stock, fuente, staging=True
        )
        escribir_raw_dict(
            os.path.join(out_dir, "stock_por_codigo.json"),
            stock_dict, staging=True
        )
        log.info("Stock escrito (staging): %d líneas", len(stock))

        # 4c. Ventas
        log.info("Descargando ventas %s → %s...", fecha_desde, fecha_hasta)
        ventas = adapter.get_ventas(fecha_desde, fecha_hasta)
        health.registrar("ventas", len(ventas))
        escribir_wrapped(
            os.path.join(out_dir, "ventas.json"),
            ventas, fuente,
            extra={"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
            staging=True,
        )
        log.info("Ventas escritas (staging): %d", len(ventas))

        # 4d. Pedidos
        log.info("Descargando pedidos...")
        pedidos = adapter.get_pedidos()
        health.registrar("pedidos", len(pedidos))
        escribir_wrapped(
            os.path.join(out_dir, "pedidos.json"),
            pedidos, fuente, staging=True
        )
        log.info("Pedidos escritos (staging): %d", len(pedidos))

        # 5. RR.HH. (Buk) — opcional
        rrhh_cfg = tenant.get("rrhh")
        if rrhh_cfg and BukAdapter:
            log.info("Procesando datos RR.HH. (Buk)...")
            try:
                buk = BukAdapter(rrhh_cfg)
                resumen_rrhh = buk.get_resumen_dotacion()
                health.registrar("rrhh", len(resumen_rrhh))
                escribir_wrapped(
                    os.path.join(out_dir, "rrhh_resumen.json"),
                    resumen_rrhh, "buk", staging=True
                )
                log.info("RR.HH. escrito (staging): %d registros", len(resumen_rrhh))
            except Exception as exc:
                log.warning("Error al obtener datos RR.HH.: %s (se continúa)", exc)

        # 6. Validación post-pipeline (sobre staging)
        if not skip_validation:
            schema = _build_schema(tenant)
            staging_dir = os.path.join(out_dir, ".staging")
            log.info("Validando JSONs en staging...")
            if not validar_pipeline(staging_dir, schema):
                limpiar_staging(out_dir)
                raise ValidationError(
                    "Los JSONs generados no pasaron la validación. "
                    "Revisa los logs arriba para ver qué archivo falló."
                )
            log.info("Validación OK")

        # 7. Promover staging → producción
        promovidos = promover_staging(out_dir)
        log.info("Archivos promovidos a producción: %d", len(promovidos))

        resultado["registros"] = dict(health._registros)
        log.info("=== Pipeline %s completado OK ===", tenant_id)

    except Exception as exc:
        resultado["estado"] = "error"
        resultado["error"] = str(exc)
        log.error("Pipeline abortado: %s", exc)
        limpiar_staging(out_dir)
        raise
    finally:
        health.finalizar(error=resultado.get("error"))
        _liberar_lock(tenant_id)

    return resultado


def _build_schema(tenant: dict) -> dict:
    """Arma el schema de validación según los módulos activos del tenant."""
    schema = {
        "productos.json": {
            "kind": "wrapped",
            "keys": ["generado", "fuente", "total", "registros"],
            "array_field": "registros",
        },
        "stock.json": {
            "kind": "wrapped",
            "keys": ["generado", "fuente", "total", "registros"],
            "array_field": "registros",
        },
        "stock_por_codigo.json": {
            "kind": "raw_dict",
        },
        "ventas.json": {
            "kind": "wrapped",
            "keys": ["generado", "fuente", "total", "registros"],
            "optional": True,
        },
        "pedidos.json": {
            "kind": "wrapped",
            "keys": ["generado", "fuente", "total", "registros"],
            "optional": True,
        },
        "rrhh_resumen.json": {
            "kind": "wrapped",
            "optional": True,
        },
    }
    return schema

# ---------------------------------------------------------------------------
# Entry point CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pipeline_runner.py <tenant_id> [fecha_desde] [fecha_hasta]")
        sys.exit(1)

    _tid = sys.argv[1]
    _desde = sys.argv[2] if len(sys.argv) > 2 else None
    _hasta = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        res = correr_pipeline(_tid, _desde, _hasta)
        print(f"\nResultado: {res['estado'].upper()}")
        if res["error"]:
            print(f"Error: {res['error']}")
        sys.exit(0 if res["estado"] == "ok" else 1)
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        sys.exit(1)
