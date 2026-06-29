"""
setup_tenant.py — Onboarding de un cliente nuevo.

Uso: python setup_tenant.py <tenant_id>

TODO:
1. Pedir/generar tenants/{tenant_id}.json a partir de tenants/ejemplo_tenant.json
2. Crear proyecto Firebase (o pedir project_id existente) y guardar en config
3. Generar firestore.rules / firestore.indexes.json base para el tenant
4. Crear carpeta branding/{tenant_id}/ con branding.json + logo
5. Cifrar credenciales del ERP con DPAPI y guardar fuera del repo
6. Validar conexión con test_conexion() del adapter elegido
"""

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python setup_tenant.py <tenant_id>")
        sys.exit(1)
    raise NotImplementedError
