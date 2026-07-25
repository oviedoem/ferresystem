"""
scheduler.py — Scheduler nativo de FerreSystem.

Reemplaza al .bat manual y permite ejecutar el pipeline:
- Una vez (--once)
- En loop con intervalo (--intervalo-minutos)
- A una hora fija diaria (--hora HH:MM)

Incluye lock por tenant, logging estructurado y manejo de errores.

Uso:
  python pipeline/scheduler.py <tenant_id> --once
  python pipeline/scheduler.py <tenant_id> --intervalo-minutos 30
  python pipeline/scheduler.py <tenant_id> --hora 22:00
  python pipeline/scheduler.py <tenant_id> --hora 22:00 --fecha-desde 2026-07-01 --fecha-hasta 2026-07-31
"""
import argparse
import os
import sys
import time
from datetime import datetime, timedelta

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.pipeline_runner import correr_pipeline
from core.exceptions import (
    FerreSystemError,
    TenantNotFoundError,
    ERPTypeNotSupportedError,
    ERPConnectionError,
    PipelineLockedError,
)
from core.logger import get_logger

log = get_logger("scheduler")


def _parse_hora(hora_str: str) -> tuple[int, int]:
    """Parsea 'HH:MM' a (hora, minuto)."""
    try:
        h, m = hora_str.split(":")
        return int(h), int(m)
    except ValueError:
        raise ValueError(f"Formato de hora inválido: '{hora_str}'. Use HH:MM (ej. 22:00)")


def _proxima_ejecucion(hora: int, minuto: int) -> datetime:
    """Calcula el próximo datetime a la hora indicada."""
    ahora = datetime.now()
    prox = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if prox <= ahora:
        prox += timedelta(days=1)
    return prox


def _esperar_hasta(prox: datetime) -> None:
    """Espera activa con logging cada minuto hasta la hora indicada."""
    while True:
        ahora = datetime.now()
        if ahora >= prox:
            break
        restante = (prox - ahora).total_seconds()
        if restante > 60:
            log.info("Próxima ejecución a las %s (faltan %d minutos)", prox.strftime("%H:%M"), int(restante / 60))
            time.sleep(60)
        else:
            time.sleep(1)


def _run_once(tenant_id: str, fecha_desde: str | None, fecha_hasta: str | None) -> bool:
    """Ejecuta el pipeline una vez y devuelve True si fue exitoso."""
    log.info("=" * 60)
    log.info("Ejecutando pipeline para tenant: %s", tenant_id)
    if fecha_desde:
        log.info("Rango de ventas: %s → %s", fecha_desde, fecha_hasta)

    try:
        res = correr_pipeline(tenant_id, fecha_desde, fecha_hasta)
        if res["estado"] == "ok":
            log.info("Pipeline completado OK. Registros: %s", res["registros"])
            return True
        else:
            log.error("Pipeline falló: %s", res["error"])
            return False
    except PipelineLockedError as e:
        log.warning("Pipeline bloqueado (otra instancia corriendo): %s", e)
        return False
    except (TenantNotFoundError, ERPTypeNotSupportedError, ERPConnectionError) as e:
        log.error("Error de configuración o conexión: %s", e)
        return False
    except Exception as e:
        log.exception("Error inesperado en pipeline: %s", e)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Scheduler nativo de FerreSystem",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s mi-tenant --once
  %(prog)s mi-tenant --intervalo-minutos 30
  %(prog)s mi-tenant --hora 22:00
  %(prog)s mi-tenant --hora 22:00 --fecha-desde 2026-07-01 --fecha-hasta 2026-07-31
        """,
    )
    parser.add_argument("tenant_id", help="ID del tenant (archivo tenants/{id}.json)")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola vez y salir")
    parser.add_argument("--intervalo-minutos", type=int, metavar="N", help="Ejecutar cada N minutos")
    parser.add_argument("--hora", type=str, metavar="HH:MM", help="Ejecutar diariamente a esta hora (ej. 22:00)")
    parser.add_argument("--fecha-desde", type=str, metavar="YYYY-MM-DD", help="Fecha inicio para ventas")
    parser.add_argument("--fecha-hasta", type=str, metavar="YYYY-MM-DD", help="Fecha fin para ventas")

    args = parser.parse_args()

    modos = sum([bool(args.once), bool(args.intervalo_minutos), bool(args.hora)])
    if modos == 0:
        parser.error("Debes especificar --once, --intervalo-minutos o --hora")
    if modos > 1:
        parser.error("Solo puedes usar uno de: --once, --intervalo-minutos, --hora")

    if args.fecha_desde and args.fecha_hasta:
        try:
            datetime.strptime(args.fecha_desde, "%Y-%m-%d")
            datetime.strptime(args.fecha_hasta, "%Y-%m-%d")
        except ValueError:
            parser.error("Las fechas deben estar en formato YYYY-MM-DD")
    elif args.fecha_desde or args.fecha_hasta:
        parser.error("Debes especificar ambas fechas: --fecha-desde y --fecha-hasta")

    log.info("Scheduler iniciado para tenant: %s", args.tenant_id)

    if args.once:
        ok = _run_once(args.tenant_id, args.fecha_desde, args.fecha_hasta)
        sys.exit(0 if ok else 1)

    if args.intervalo_minutos:
        if args.intervalo_minutos < 1:
            parser.error("El intervalo debe ser al menos 1 minuto")
        intervalo_seg = args.intervalo_minutos * 60
        log.info("Modo intervalo: cada %d minutos", args.intervalo_minutos)

        while True:
            inicio = time.monotonic()
            _run_once(args.tenant_id, args.fecha_desde, args.fecha_hasta)
            transcurrido = time.monotonic() - inicio
            espera = max(0, intervalo_seg - transcurrido)
            if espera > 0:
                log.info("Esperando %d segundos hasta próxima ejecución...", int(espera))
                time.sleep(espera)

    if args.hora:
        hora, minuto = _parse_hora(args.hora)
        log.info("Modo hora fija: todos los días a las %02d:%02d", hora, minuto)

        while True:
            prox = _proxima_ejecucion(hora, minuto)
            _esperar_hasta(prox)
            _run_once(args.tenant_id, args.fecha_desde, args.fecha_hasta)
            time.sleep(5)


if __name__ == "__main__":
    main()
