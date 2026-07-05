"""
descargar_erp.py — Paso 1 del pipeline manual: descarga ERP y escribe JSONs.

Llama a correr_pipeline() del motor genérico, que conecta al ERP del tenant,
descarga productos/stock/ventas/pedidos y los escribe en data/{tenant_id}/
con el formato wrapped estándar. Equivale a correr los pasos 1 y 2 del
ACTUALIZAR_TODO.bat de forma integrada.

Uso:
    python pipeline/descargar_erp.py <tenant_id>
    python pipeline/descargar_erp.py <tenant_id> 2025-01-01 2025-01-31
"""
import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.pipeline_runner import correr_pipeline

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pipeline/descargar_erp.py <tenant_id> [fecha_desde] [fecha_hasta]")
        sys.exit(1)

    tenant_id   = sys.argv[1]
    fecha_desde = sys.argv[2] if len(sys.argv) > 2 else None
    fecha_hasta = sys.argv[3] if len(sys.argv) > 3 else None

    correr_pipeline(tenant_id, fecha_desde, fecha_hasta)
