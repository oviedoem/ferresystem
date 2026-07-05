"""
generar_jsons.py — Paso 2 del pipeline manual: valida los JSONs generados.

Verifica que los archivos en data/{tenant_id}/ tengan la estructura correcta
antes de rotar el token y hacer el deploy. Bloquea con exit(1) si algún
archivo está vacío, roto o le faltan claves obligatorias.

Debe ejecutarse DESPUÉS de descargar_erp.py y ANTES de rotar_token.py.

Uso:
    python pipeline/generar_jsons.py <tenant_id>
"""
import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.validator import validar_pipeline

SCHEMA = {
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pipeline/generar_jsons.py <tenant_id>")
        sys.exit(1)

    tenant_id  = sys.argv[1]
    output_dir = os.path.normpath(os.path.join(_ROOT, "data", tenant_id))

    if not os.path.isdir(output_dir):
        print(f"[ERROR] Directorio no existe: {output_dir}")
        print(f"        Ejecuta primero: python pipeline/descargar_erp.py {tenant_id}")
        sys.exit(1)

    ok = validar_pipeline(output_dir, SCHEMA)
    sys.exit(0 if ok else 1)
