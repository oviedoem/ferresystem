"""
scheduler.py — Scheduler genérico del pipeline FerreSystem.

Ejecuta correr_pipeline() para uno o todos los tenants activos, respetando
el intervalo de sync configurado en cada tenants/{id}.json → pipeline.
Reintenta automáticamente ante fallos transitorios (ERP caído, timeout de red)
con backoff exponencial. Notifica por email si un tenant falla N veces seguidas.

Diseñado para correr como proceso permanente (python scheduler.py) o ser
llamado desde una tarea programada (Windows Task Scheduler / cron) para
ejecuciones únicas (python scheduler.py <tenant_id> --once).

Nada aquí hardcodea datos de ningún cliente — todo viene de tenants/{id}.json.

Campos leídos de tenants/{id}.json → "pipeline":
    hora_sync_sql          : str  — hora fija de sync "HH:MM" (modo hora fija)
    intervalo_minutos      : int  — intervalo en minutos (modo continuo); si
                                    se define, tiene precedencia sobre hora_sync_sql
    max_reintentos         : int  — veces que se reintenta antes de escalar (default 3)
    backoff_base_segundos  : int  — base del backoff exponencial (default 60)
    notificar_email        : str  — email al que notificar fallos repetidos (opcional)
    activo                 : bool — si False, el tenant se omite en el loop (default True)
"""
import json
import os
import sys
import time
import smtplib
import traceback
from email.message import EmailMessage
from datetime import datetime, timedelta

# Añadimos el directorio raíz al path para importar core/
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.pipeline_runner import correr_pipeline, cargar_tenant
from core.logger import get_logger

log = get_logger("scheduler")

TENANTS_DIR = os.path.join(_ROOT, "tenants")
_OMITIR_PREFIJOS = ("ejemplo_",)  # archivos template que nunca se ejecutan


# ---------------------------------------------------------------------------
# Config SMTP para notificaciones (variables de entorno — nunca hardcodeado)
# ---------------------------------------------------------------------------
SMTP_HOST = os.environ.get("FERRESYSTEM_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("FERRESYSTEM_SMTP_PORT", 587))
SMTP_USER = os.environ.get("FERRESYSTEM_SMTP_USER", "")
SMTP_PASS = os.environ.get("FERRESYSTEM_SMTP_PASS", "")
SMTP_FROM = os.environ.get("FERRESYSTEM_SMTP_FROM", SMTP_USER)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _listar_tenants_activos() -> list[str]:
    """Devuelve IDs de todos los tenants activos en tenants/."""
    ids = []
    for fname in os.listdir(TENANTS_DIR):
        if not fname.endswith(".json"):
            continue
        if any(fname.startswith(p) for p in _OMITIR_PREFIJOS):
            continue
        tenant_id = fname[:-5]
        try:
            cfg = cargar_tenant(tenant_id)
            if cfg.get("pipeline", {}).get("activo", True):
                ids.append(tenant_id)
        except Exception as e:
            log.warning(f"No se pudo cargar tenant '{tenant_id}': {e}")
    return ids


def _pipeline_cfg(tenant_id: str) -> dict:
    """Devuelve el bloque pipeline del tenant o {} si no existe."""
    try:
        return cargar_tenant(tenant_id).get("pipeline", {})
    except Exception:
        return {}


def _proximo_run(tenant_id: str, ultimo_run: datetime) -> datetime:
    """Calcula cuándo debe correr el próximo sync para este tenant."""
    cfg = _pipeline_cfg(tenant_id)

    if "intervalo_minutos" in cfg:
        minutos = int(cfg["intervalo_minutos"])
        return ultimo_run + timedelta(minutes=minutos)

    if "hora_sync_sql" in cfg:
        hm = cfg["hora_sync_sql"]  # "HH:MM"
        hora, minuto = (int(x) for x in hm.split(":"))
        proximo = ultimo_run.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        if proximo <= ultimo_run:
            proximo += timedelta(days=1)
        return proximo

    # Default: cada 60 minutos
    return ultimo_run + timedelta(minutes=60)


def _notificar_fallo(tenant_id: str, error: str, intentos: int, email: str) -> None:
    """Envía un email de alerta si SMTP está configurado."""
    if not SMTP_HOST or not email:
        log.warning(f"[{tenant_id}] Notificación omitida — SMTP no configurado o email no definido")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[FerreSystem] Pipeline FALLIDO: {tenant_id} ({intentos} intentos)"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.set_content(
            f"El pipeline del tenant '{tenant_id}' falló {intentos} veces consecutivas.\n\n"
            f"Último error:\n{error}\n\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        log.info(f"[{tenant_id}] Notificación enviada a {email}")
    except Exception as e:
        log.error(f"[{tenant_id}] No se pudo enviar notificación: {e}")


# ---------------------------------------------------------------------------
# Lógica de ejecución con reintentos
# ---------------------------------------------------------------------------

def ejecutar_con_reintentos(tenant_id: str) -> bool:
    """Corre el pipeline para un tenant con backoff exponencial.

    Devuelve True si tuvo éxito, False si agotó los reintentos.
    """
    cfg = _pipeline_cfg(tenant_id)
    max_r = int(cfg.get("max_reintentos", 3))
    backoff = int(cfg.get("backoff_base_segundos", 60))
    email_alerta = cfg.get("notificar_email", "")

    ultimo_error = ""
    for intento in range(1, max_r + 2):  # +1 intento inicial
        try:
            log.info(f"[{tenant_id}] Iniciando pipeline (intento {intento}/{max_r + 1})")
            correr_pipeline(tenant_id)
            log.info(f"[{tenant_id}] Pipeline completado OK")
            return True
        except SystemExit as e:
            ultimo_error = f"Pipeline abortó con sys.exit({e.code})"
            log.error(f"[{tenant_id}] {ultimo_error}")
        except Exception:
            ultimo_error = traceback.format_exc()
            log.error(f"[{tenant_id}] Error en intento {intento}:\n{ultimo_error}")

        if intento <= max_r:
            espera = backoff * (2 ** (intento - 1))  # backoff exponencial
            log.info(f"[{tenant_id}] Reintentando en {espera}s...")
            time.sleep(espera)

    log.error(f"[{tenant_id}] Agotó {max_r + 1} intentos. Escalando.")
    _notificar_fallo(tenant_id, ultimo_error, max_r + 1, email_alerta)
    return False


# ---------------------------------------------------------------------------
# Modos de ejecución
# ---------------------------------------------------------------------------

def modo_once(tenant_id: str) -> None:
    """Corre el pipeline una sola vez y sale."""
    log.info(f"=== Modo --once: {tenant_id} ===")
    ok = ejecutar_con_reintentos(tenant_id)
    sys.exit(0 if ok else 1)


def modo_loop(tenant_ids: list[str]) -> None:
    """Loop permanente: ejecuta cada tenant según su configuración de intervalo."""
    log.info(f"=== Modo loop activo para {len(tenant_ids)} tenants: {tenant_ids} ===")

    # Inicializar próximo run para cada tenant
    ahora = datetime.now()
    proximos: dict = {}
    for tid in tenant_ids:
        cfg = _pipeline_cfg(tid)
        if "intervalo_minutos" in cfg:
            # Correr de inmediato en el primer ciclo
            proximos[tid] = ahora
        elif "hora_sync_sql" in cfg:
            proximos[tid] = _proximo_run(tid, ahora)
            log.info(f"[{tid}] Primer sync programado: {proximos[tid].strftime('%H:%M')}")
        else:
            proximos[tid] = ahora  # default: correr ahora

    while True:
        ahora = datetime.now()

        for tid in list(proximos.keys()):
            if ahora >= proximos[tid]:
                ejecutar_con_reintentos(tid)
                proximos[tid] = _proximo_run(tid, ahora)
                log.info(f"[{tid}] Próximo sync: {proximos[tid].strftime('%Y-%m-%d %H:%M')}")

        time.sleep(30)  # revisar cada 30s si algún tenant debe correr


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """
    Uso:
        python scheduler.py                        — loop todos los tenants activos
        python scheduler.py <tenant_id>            — loop solo ese tenant
        python scheduler.py <tenant_id> --once     — ejecutar una vez y salir
    """
    args = sys.argv[1:]

    if "--once" in args:
        args = [a for a in args if a != "--once"]
        if not args:
            print("Uso: python scheduler.py <tenant_id> --once")
            sys.exit(1)
        modo_once(args[0])
    elif args:
        tenant_id = args[0]
        modo_loop([tenant_id])
    else:
        tenants = _listar_tenants_activos()
        if not tenants:
            log.warning("No hay tenants activos en tenants/. Saliendo.")
            sys.exit(0)
        modo_loop(tenants)


if __name__ == "__main__":
    main()
