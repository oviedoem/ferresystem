"""
setup_tenant.py — Wizard de onboarding para un cliente (tenant) nuevo.

Guía paso a paso la configuración inicial: genera tenants/{id}.json,
crea la carpeta de branding, valida la conexión ERP y deja el tenant
listo para el primer pipeline.

Uso:
    python setup_tenant.py              — wizard interactivo (pide tenant_id)
    python setup_tenant.py <tenant_id>  — inicia el wizard para ese id

El wizard NUNCA toca core/, adapters/ ni los paneles HTML.
Todos los datos del cliente quedan en tenants/{id}.json y branding/{id}/.
Las credenciales del ERP se guardan cifradas con DPAPI fuera del repo.
"""
import json
import os
import sys
import shutil

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TENANTS_DIR  = os.path.join(_ROOT, "tenants")
BRANDING_DIR = os.path.join(_ROOT, "branding")
TEMPLATE     = os.path.join(TENANTS_DIR, "ejemplo_tenant.json")

# ERPs soportados — clave usada en tenants/{id}.json → erp.tipo
ERPS_DISPONIBLES = {
    "1": ("justweb",    "JustWeb (SSRS/HTTP CSV)"),
    "2": ("transtecnia","Transtecnia (SQL directo)"),
    "3": ("rexplus",    "Rex Plus (SQL directo)"),
    "4": ("bsale",      "Bsale (API REST)"),
    "5": ("excel",      "Excel / CSV local"),
}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _titulo(texto: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {texto}")
    print("=" * 60)


def _paso(n: int, total: int, texto: str) -> None:
    print(f"\n[Paso {n}/{total}] {texto}")
    print("-" * 40)


def _pedir(prompt: str, default: str = "", requerido: bool = True) -> str:
    sufijo = f" [{default}]" if default else ""
    while True:
        valor = input(f"  {prompt}{sufijo}: ").strip()
        if not valor:
            valor = default
        if valor or not requerido:
            return valor
        print("  ⚠  Campo requerido.")


def _pedir_int(prompt: str, default: int) -> int:
    while True:
        raw = input(f"  {prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  ⚠  Debe ser un número entero.")


def _pedir_lista(prompt: str, ejemplo: str = "") -> list:
    """Pide valores separados por coma y devuelve una lista."""
    raw = _pedir(prompt + f" (separados por coma{', ej: ' + ejemplo if ejemplo else ''})")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _confirmar(prompt: str) -> bool:
    r = input(f"  {prompt} [s/N]: ").strip().lower()
    return r in ("s", "si", "sí", "y", "yes")


# ---------------------------------------------------------------------------
# Pasos del wizard
# ---------------------------------------------------------------------------

def _paso_identificacion() -> tuple[str, str, str]:
    _paso(1, 6, "Identificación del cliente")
    tenant_id = _pedir(
        "ID único del tenant (letras, números, guiones — sin espacios)",
        requerido=True,
    )
    # Validar formato básico
    import re
    if not re.match(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$', tenant_id):
        print("  ⚠  ID inválido. Usa solo minúsculas, números y guiones (mín 3 chars).")
        sys.exit(1)

    ruta_destino = os.path.join(TENANTS_DIR, f"{tenant_id}.json")
    if os.path.isfile(ruta_destino):
        print(f"\n  ⚠  Ya existe {ruta_destino}")
        if not _confirmar("¿Sobrescribir?"):
            print("  Operación cancelada.")
            sys.exit(0)

    nombre_comercial = _pedir("Nombre comercial del cliente", requerido=True)
    return tenant_id, nombre_comercial, ruta_destino


def _paso_erp() -> tuple[str, dict]:
    _paso(2, 6, "Configuración del ERP")
    print("  ERPs disponibles:")
    for k, (tipo, desc) in ERPS_DISPONIBLES.items():
        print(f"    {k}. {desc}")
    opcion = _pedir("Selecciona el ERP (número)", requerido=True)
    if opcion not in ERPS_DISPONIBLES:
        print("  ⚠  Opción inválida.")
        sys.exit(1)

    tipo, desc = ERPS_DISPONIBLES[opcion]
    erp_cfg: dict = {"tipo": tipo}

    if tipo == "bsale":
        erp_cfg["access_token"]  = _pedir("API key (access_token) de Bsale")
        ids_raw = _pedir_lista("IDs de sucursales/bodegas", "1, 2")
        erp_cfg["office_ids"]    = [int(x) for x in ids_raw if x.isdigit()]
        erp_cfg["api_version"]   = _pedir("Versión API Bsale", "1", requerido=False) or "1"
        erp_cfg["timeout"]       = _pedir_int("Timeout HTTP (segundos)", 30)
        erp_cfg["max_paginas"]   = _pedir_int("Máx. páginas por endpoint", 50)
        erp_cfg["precio_tipo_id"] = None

    elif tipo == "excel":
        erp_cfg["archivo_path"] = _pedir("Ruta al archivo Excel/CSV")

    else:
        erp_cfg["host"]         = _pedir("Host/IP del servidor ERP")
        erp_cfg["puerto"]       = _pedir_int("Puerto", 80)
        erp_cfg["usuario"]      = _pedir("Usuario ERP")
        print("  ℹ  La contraseña se almacenará como 'PENDIENTE_CIFRAR'.")
        print("     Cifrala con DPAPI después del wizard (ver checklist_instalacion.md).")
        erp_cfg["password_enc"] = "PENDIENTE_CIFRAR"

    return tipo, erp_cfg


def _paso_bodegas() -> dict:
    _paso(3, 6, "Bodegas / sucursales")
    comerciales = _pedir_lista("Bodegas comerciales", "BOD1, BOD2")
    logisticas  = _pedir_lista("Bodegas logísticas (puede ser la misma)", "BOD3")
    principal   = _pedir("Bodega principal (la más importante)", comerciales[0] if comerciales else "BOD1")
    return {
        "comerciales":    comerciales,
        "logisticas":     logisticas,
        "bodega_principal": principal,
    }


def _paso_firebase() -> dict:
    _paso(4, 6, "Firebase")
    project_id  = _pedir("Firebase project_id (ej: ferresystem-cliente)")
    hosting_url = _pedir("URL de hosting", f"https://{project_id}.web.app", requerido=False) or f"https://{project_id}.web.app"
    return {
        "project_id":   project_id,
        "hosting_url":  hosting_url,
    }


def _paso_branding(tenant_id: str) -> dict:
    _paso(5, 6, "Branding / apariencia")
    nombre_corto   = _pedir("Nombre corto para el panel (ej: Oviedo)")
    color_primario = _pedir("Color primario hex (ej: #c0392b)", "#c0392b", requerido=False) or "#c0392b"
    color_sec      = _pedir("Color secundario hex (ej: #2c3e50)", "#2c3e50", requerido=False) or "#2c3e50"
    logo           = f"branding/{tenant_id}/logo.png"

    branding_dir = os.path.join(BRANDING_DIR, tenant_id)
    os.makedirs(branding_dir, exist_ok=True)

    # Copiar branding template si existe
    template_branding = os.path.join(BRANDING_DIR, "ejemplo", "branding.json")
    branding_json = {
        "nombre_corto":      nombre_corto,
        "nombre_comercial":  nombre_corto,
        "color_primario":    color_primario,
        "color_secundario":  color_sec,
        "logo":              logo,
        "favicon":           f"branding/{tenant_id}/favicon.ico",
    }
    with open(os.path.join(branding_dir, "branding.json"), "w", encoding="utf-8") as f:
        json.dump(branding_json, f, ensure_ascii=False, indent=2)

    # Copiar placeholder de logo si el tenant no tiene uno
    logo_placeholder = os.path.join(BRANDING_DIR, "ejemplo", "logo_placeholder.png")
    logo_destino = os.path.join(branding_dir, "logo.png")
    if not os.path.isfile(logo_destino) and os.path.isfile(logo_placeholder):
        shutil.copy2(logo_placeholder, logo_destino)
        print(f"  ✓ Logo placeholder copiado a {logo_destino}")
    else:
        print(f"  ℹ  Sube el logo real a: {logo_destino}")

    return {
        "nombre_corto":    nombre_corto,
        "color_primario":  color_primario,
        "color_secundario": color_sec,
        "logo":            logo,
    }


def _paso_pipeline(erp_tipo: str) -> dict:
    _paso(6, 6, "Parámetros del pipeline")
    modo = _pedir("Modo de sync: (1) Hora fija  (2) Intervalo periódico", "1")
    pipeline_cfg: dict = {"activo": True, "max_reintentos": 3, "backoff_base_segundos": 60}

    if modo == "2":
        minutos = _pedir_int("Intervalo en minutos", 60)
        pipeline_cfg["intervalo_minutos"] = minutos
    else:
        hora = _pedir("Hora de sync diaria (HH:MM)", "22:00", requerido=False) or "22:00"
        pipeline_cfg["hora_sync_sql"] = hora

    pipeline_cfg["ttl_token_horas"] = _pedir_int("TTL del token de datos (horas)", 8)
    email_alerta = _pedir("Email de alerta ante fallos (opcional)", "", requerido=False)
    if email_alerta:
        pipeline_cfg["notificar_email"] = email_alerta

    return pipeline_cfg


# ---------------------------------------------------------------------------
# Generación del tenant.json
# ---------------------------------------------------------------------------

def _generar_tenant_json(
    tenant_id: str,
    nombre_comercial: str,
    erp_cfg: dict,
    bodegas_cfg: dict,
    firebase_cfg: dict,
    branding_cfg: dict,
    pipeline_cfg: dict,
    ruta_destino: str,
) -> None:
    config = {
        "_comentario": (
            f"Generado por setup_tenant.py para {nombre_comercial}. "
            "NUNCA commitear este archivo (ver .gitignore)."
        ),
        "tenant_id":        tenant_id,
        "nombre_comercial": nombre_comercial,
        "erp":              erp_cfg,
        "bodegas":          bodegas_cfg,
        "firebase":         firebase_cfg,
        "branding":         branding_cfg,
        "pipeline":         pipeline_cfg,
    }
    with open(ruta_destino, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ Configuración guardada en: {ruta_destino}")


# ---------------------------------------------------------------------------
# Test de conexión ERP
# ---------------------------------------------------------------------------

def _test_conexion(tenant_id: str) -> None:
    print("\n  Probando conexión con el ERP...")
    try:
        from core.pipeline_runner import cargar_tenant, construir_adapter
        cfg = cargar_tenant(tenant_id)
        adapter = construir_adapter(cfg)
        ok = adapter.test_conexion()
        if ok:
            print("  ✓ Conexión ERP OK")
        else:
            print("  ⚠  test_conexion() devolvió False — revisa credenciales y host")
    except NotImplementedError:
        print("  ℹ  Adapter aún no implementado completamente — omitiendo test")
    except Exception as e:
        print(f"  ⚠  Error al probar conexión: {e}")
        print("     Puedes correr el test manualmente después del wizard.")


# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------

def _resumen_final(tenant_id: str, ruta_json: str, erp_tipo: str) -> None:
    _titulo("Onboarding completado")
    print(f"""
  Tenant ID    : {tenant_id}
  Config       : {ruta_json}
  Branding     : {os.path.join(BRANDING_DIR, tenant_id)}/

  Próximos pasos:
  1. Sube el logo real a:  branding/{tenant_id}/logo.png
  2. {'Cifra la contraseña del ERP con DPAPI y actualiza password_enc en el JSON.' if erp_tipo != 'bsale' else 'Verifica que el access_token de Bsale es correcto.'}
  3. Ejecuta el primer pipeline:
       python pipeline/scheduler.py {tenant_id} --once
  4. Si el pipeline es OK, haz el deploy:
       firebase deploy --project {tenant_id}

  Ver: docs/como_agregar_cliente.md y setup/checklist_instalacion.md
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _titulo("FerreSystem — Wizard de onboarding")
    print("  Este wizard genera la configuración para un nuevo cliente.")
    print("  Ningún dato se sube a git (ver .gitignore).\n")

    # Aceptar tenant_id por argumento o pedirlo
    if len(sys.argv) >= 2:
        tenant_id_arg = sys.argv[1]
        print(f"  Tenant ID recibido por argumento: {tenant_id_arg}")
        # Inyectar en el flujo sin preguntar de nuevo
        import re
        if not re.match(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$', tenant_id_arg):
            print("  ⚠  ID inválido.")
            sys.exit(1)
        tenant_id = tenant_id_arg
        ruta_destino = os.path.join(TENANTS_DIR, f"{tenant_id}.json")
        if os.path.isfile(ruta_destino):
            print(f"\n  ⚠  Ya existe {ruta_destino}")
            if not _confirmar("¿Sobrescribir?"):
                print("  Operación cancelada.")
                sys.exit(0)
        nombre_comercial = _pedir("Nombre comercial del cliente", requerido=True)
    else:
        tenant_id, nombre_comercial, ruta_destino = _paso_identificacion()

    erp_tipo, erp_cfg    = _paso_erp()
    bodegas_cfg          = _paso_bodegas()
    firebase_cfg         = _paso_firebase()
    branding_cfg         = _paso_branding(tenant_id)
    pipeline_cfg         = _paso_pipeline(erp_tipo)

    _generar_tenant_json(
        tenant_id, nombre_comercial,
        erp_cfg, bodegas_cfg, firebase_cfg, branding_cfg, pipeline_cfg,
        ruta_destino,
    )

    if _confirmar("¿Probar la conexión con el ERP ahora?"):
        _test_conexion(tenant_id)

    _resumen_final(tenant_id, ruta_destino, erp_tipo)


if __name__ == "__main__":
    main()
