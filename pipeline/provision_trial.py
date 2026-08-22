"""
provision_trial.py — Cloud Function stub para auto-provisionar tenants de prueba.

Diseñado para ejecutarse como Google Cloud Function (HTTP trigger) o
como script manual por el equipo de FerreSystem.

Flujo:
  1. Recibe solicitud de trial (JSON POST con datos del formulario trial.html)
  2. Valida campos obligatorios y dominio de email
  3. Crea el directorio data/{tenant_id}/ si no existe
  4. Escribe tenants/{tenant_id}.json con configuración base del trial
  5. Registra la solicitud en solicitudes_trial.json para seguimiento
  6. (Stub) Envía email de bienvenida al contacto

En producción este módulo se despliega como Cloud Function con:
  - Trigger: HTTP POST /provision_trial
  - Auth: API key interna en header X-FerreSystem-Key
  - Timeout: 60s

Sin lógica de negocio de ningún cliente real.
Todo dato de cliente llega por el body del request o por tenant.json.
"""
import json
import os
import re
import sys
from datetime import date, timedelta, datetime, timezone


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TENANTS_DIR      = os.path.join(os.path.dirname(__file__), "..", "tenants")
DATA_DIR         = os.path.join(os.path.dirname(__file__), "..", "data")
SOLICITUDES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "solicitudes_trial.json")
TRIAL_DIAS       = 14

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# Funciones principales
# ---------------------------------------------------------------------------

def provisionar_trial(payload: dict) -> dict:
    """Provisiona un tenant de prueba a partir del payload del formulario.

    Args:
        payload: dict con campos del formulario trial.html:
            nombre_comercial (str, obligatorio)
            email (str, obligatorio)
            contacto (str)
            telefono (str, opcional)
            erp_tipo (str)
            tamanio (str, opcional)

    Returns:
        dict con {"ok": True, "tenant_id": ..., "vence": ...}
        o {"ok": False, "error": "..."}
    """
    # 1. Validar
    err = _validar(payload)
    if err:
        return {"ok": False, "error": err}

    tenant_id = _slugify(payload["nombre_comercial"])

    # 2. Evitar duplicados: si ya existe y el trial no venció, rechazar
    tenant_json_path = os.path.join(TENANTS_DIR, f"{tenant_id}.json")
    if os.path.isfile(tenant_json_path):
        existente = _leer_json(tenant_json_path)
        vence_str = existente.get("_trial", {}).get("fecha_vence", "")
        if vence_str and vence_str >= date.today().isoformat():
            return {
                "ok":       False,
                "error":    f"Ya existe un trial activo para '{tenant_id}' (vence {vence_str}).",
                "tenant_id": tenant_id,
            }

    # 3. Crear tenant.json de trial
    hoy    = date.today().isoformat()
    vence  = (date.today() + timedelta(days=TRIAL_DIAS)).isoformat()
    erp_tipo = payload.get("erp_tipo", "excel")
    if erp_tipo == "otro":
        erp_tipo = "excel"

    tenant_cfg = {
        "tenant_id":        tenant_id,
        "nombre_comercial": payload["nombre_comercial"],
        "erp": {
            "tipo":  erp_tipo,
            "_nota": "Credenciales pendientes de configurar por el equipo FerreSystem",
        },
        "bodegas": {
            "comerciales":     [],
            "logisticas":      [],
            "bodega_principal":"",
        },
        "firebase": {
            "project_id":  "",
            "hosting_url": "",
        },
        "branding": {
            "nombre_corto":     payload["nombre_comercial"].split()[-1],
            "color_primario":   "#c0392b",
            "color_secundario": "#2c3e50",
        },
        "modulos_activos": {
            "stock":         True,
            "ventas":        True,
            "cotizador":     True,
            "alertas":       True,
            "pedidos":       False,
            "despachos":     False,
            "merma":         False,
            "panel_cliente": True,
            "panel_admin":   False,
        },
        "pipeline": {
            "activo":                False,
            "hora_sync_sql":         "22:00",
            "max_reintentos":        3,
            "backoff_base_segundos": 60,
            "notificar_email":       payload["email"],
            "ttl_token_horas":       8,
        },
        "_trial": {
            "activo":       True,
            "fecha_inicio": hoy,
            "fecha_vence":  vence,
            "dias":         TRIAL_DIAS,
            "contacto":     payload.get("contacto", ""),
            "email":        payload["email"],
            "telefono":     payload.get("telefono", ""),
            "erp_solicitado": payload.get("erp_tipo", ""),
            "tamanio_catalogo": payload.get("tamanio", ""),
        },
    }

    # 4. Persistir
    os.makedirs(TENANTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, tenant_id), exist_ok=True)
    _escribir_json(tenant_json_path, tenant_cfg)

    # 5. Registrar en solicitudes_trial.json
    _registrar_solicitud({
        "tenant_id":   tenant_id,
        "email":       payload["email"],
        "contacto":    payload.get("contacto", ""),
        "erp_tipo":    erp_tipo,
        "fecha":       hoy,
        "vence":       vence,
        "estado":      "pendiente_configuracion",
        "timestamp":   _now_iso(),
    })

    # 6. Notificar (stub — en producción llama a SendGrid / Firebase Email)
    _enviar_bienvenida(
        email   = payload["email"],
        nombre  = payload.get("contacto", payload["nombre_comercial"]),
        tenant  = payload["nombre_comercial"],
        vence   = vence,
    )

    return {
        "ok":        True,
        "tenant_id": tenant_id,
        "vence":     vence,
        "message":   f"Trial '{tenant_id}' provisionado. Vence {vence}.",
    }


def activar_trial(tenant_id: str) -> dict:
    """Activa el pipeline de un trial una vez configuradas las credenciales ERP.

    El equipo de FerreSystem llama a esta función tras completar
    los campos de conexión en tenants/{tenant_id}.json.

    Returns: dict con {"ok": bool, "mensaje": str}
    """
    ruta = os.path.join(TENANTS_DIR, f"{tenant_id}.json")
    if not os.path.isfile(ruta):
        return {"ok": False, "mensaje": f"Tenant no encontrado: {ruta}"}

    cfg = _leer_json(ruta)
    if not cfg.get("_trial", {}).get("activo"):
        return {"ok": False, "mensaje": "Este tenant no es un trial."}

    vence = cfg["_trial"].get("fecha_vence", "")
    if vence and vence < date.today().isoformat():
        return {"ok": False, "mensaje": f"El trial venció el {vence}. Renovar o convertir a plan pago."}

    cfg["pipeline"]["activo"] = True
    _escribir_json(ruta, cfg)

    _actualizar_solicitud(tenant_id, {"estado": "activo"})

    return {"ok": True, "mensaje": f"Pipeline de '{tenant_id}' activado hasta {vence}."}


def expirar_trials_vencidos() -> list[str]:
    """Desactiva pipelines de trials vencidos. Ejecutar diariamente via cron.

    Returns: lista de tenant_ids desactivados.
    """
    hoy = date.today().isoformat()
    desactivados = []

    tenants_dir = TENANTS_DIR
    if not os.path.isdir(tenants_dir):
        return []

    for fname in os.listdir(tenants_dir):
        if not fname.endswith(".json") or fname == "ejemplo_tenant.json":
            continue
        ruta = os.path.join(tenants_dir, fname)
        try:
            cfg = _leer_json(ruta)
        except Exception:
            continue

        trial = cfg.get("_trial", {})
        if not trial.get("activo"):
            continue

        vence = trial.get("fecha_vence", "")
        if vence and vence < hoy and cfg.get("pipeline", {}).get("activo"):
            cfg["pipeline"]["activo"] = False
            cfg["_trial"]["activo"]   = False
            _escribir_json(ruta, cfg)
            _actualizar_solicitud(cfg["tenant_id"], {"estado": "expirado"})
            desactivados.append(cfg["tenant_id"])

    return desactivados


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _validar(payload: dict) -> str:
    """Devuelve mensaje de error o '' si es válido."""
    if not payload.get("nombre_comercial", "").strip():
        return "nombre_comercial es obligatorio."
    email = payload.get("email", "").strip()
    if not email:
        return "email es obligatorio."
    if not _EMAIL_RE.match(email):
        return f"email inválido: {email}"
    return ""


def _slugify(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "tenant"


def _leer_json(ruta: str) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _escribir_json(ruta: str, data: dict) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _registrar_solicitud(entrada: dict) -> None:
    """Agrega una entrada al log de solicitudes de trial."""
    solicitudes = []
    if os.path.isfile(SOLICITUDES_PATH):
        try:
            solicitudes = _leer_json(SOLICITUDES_PATH)
        except Exception:
            solicitudes = []
    solicitudes.append(entrada)
    os.makedirs(os.path.dirname(SOLICITUDES_PATH), exist_ok=True)
    _escribir_json(SOLICITUDES_PATH, solicitudes)


def _actualizar_solicitud(tenant_id: str, cambios: dict) -> None:
    """Actualiza el estado de una solicitud en solicitudes_trial.json."""
    if not os.path.isfile(SOLICITUDES_PATH):
        return
    try:
        solicitudes = _leer_json(SOLICITUDES_PATH)
    except Exception:
        return
    for s in solicitudes:
        if s.get("tenant_id") == tenant_id:
            s.update(cambios)
    _escribir_json(SOLICITUDES_PATH, solicitudes)


def _enviar_bienvenida(email: str, nombre: str, tenant: str, vence: str) -> None:
    """Stub de envío de email de bienvenida.

    En producción: llamar a SendGrid API o Firebase Extension Send Email.
    Por ahora imprime el contenido del email para que el equipo lo envíe manualmente.
    """
    print(f"""
[EMAIL DE BIENVENIDA — pendiente de enviar]
Para:    {email}
Asunto:  Tu prueba de FerreSystem está lista, {nombre}

Hola {nombre},

Gracias por registrarte en FerreSystem. Hemos recibido tu solicitud para
"{tenant}" y nuestro equipo te contactará en menos de 24 horas hábiles
para configurar tu período de prueba de {TRIAL_DIAS} días (vence: {vence}).

Mientras tanto, el archivo de configuración descargado (tenant.json) es
el que debes enviarnos junto con los datos de acceso a tu sistema ERP.

Equipo FerreSystem
""")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Entry point CLI (uso manual del equipo)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FerreSystem — Gestión de trials")
    sub = parser.add_subparsers(dest="cmd")

    p_prov = sub.add_parser("provisionar", help="Provisionar nuevo trial")
    p_prov.add_argument("--nombre",   required=True, help="Nombre comercial")
    p_prov.add_argument("--email",    required=True, help="Email del contacto")
    p_prov.add_argument("--contacto", default="")
    p_prov.add_argument("--erp",      default="excel", dest="erp_tipo")

    p_act = sub.add_parser("activar", help="Activar pipeline de un trial configurado")
    p_act.add_argument("tenant_id")

    p_exp = sub.add_parser("expirar", help="Desactivar trials vencidos")

    args = parser.parse_args()

    if args.cmd == "provisionar":
        resultado = provisionar_trial({
            "nombre_comercial": args.nombre,
            "email":            args.email,
            "contacto":         args.contacto,
            "erp_tipo":         args.erp_tipo,
        })
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        sys.exit(0 if resultado["ok"] else 1)

    elif args.cmd == "activar":
        resultado = activar_trial(args.tenant_id)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        sys.exit(0 if resultado["ok"] else 1)

    elif args.cmd == "expirar":
        desactivados = expirar_trials_vencidos()
        print(f"Trials expirados y desactivados: {desactivados or 'ninguno'}")

    else:
        parser.print_help()
