"""
buk_adapter.py — Modulo auxiliar de RR.HH. para Buk (API REST).

NO extiende ERPAdapter: Buk no es un ERP de inventario, es una plataforma
de gestion de personas. pipeline_runner.py lo carga opcionalmente cuando
el tenant declara un bloque "rrhh" en su tenants/{id}.json.

API: https://developers.buk.cl/
Autenticacion: header Authorization: Bearer <access_token>

Campos requeridos en tenant_config["rrhh"]:
    access_token : str — API key del tenant en Buk
    company_id   : int — ID de empresa en Buk (Configuracion > Empresa)

Campos opcionales:
    api_version  : str — version de la API (default "v1")
    timeout      : int — segundos de espera HTTP (default 30)
    max_paginas  : int — limite de paginas por endpoint (default 20)
"""
import json
import urllib.request
import urllib.parse
import urllib.error

from core.logger import get_logger

log = get_logger("buk_adapter")

_BASE = "https://app.buk.cl/api/{version}"
_PAGE_SIZE = 50


class BukAdapter:
    """Cliente para la API REST de Buk. Extrae resumen de dotacion."""

    def __init__(self, config: dict):
        self._token      = config["access_token"]
        self._company_id = int(config["company_id"])
        version          = config.get("api_version", "v1")
        self._base       = _BASE.format(version=version)
        self._timeout    = int(config.get("timeout", 30))
        self._max_pag    = int(config.get("max_paginas", 20))

    def _get(self, path: str, params: dict = None) -> dict:
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
        log.debug(f"GET {url}")
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error(f"HTTP {e.code} en {url}: {body[:200]}")
            raise
        except urllib.error.URLError as e:
            log.error(f"URLError en {url}: {e.reason}")
            raise

    def _paginar(self, path: str, params: dict = None) -> list[dict]:
        """Itera sobre todas las paginas del endpoint hasta max_paginas."""
        params = dict(params or {})
        todos = []
        for pagina in range(1, self._max_pag + 1):
            params["page"]     = pagina
            params["per_page"] = _PAGE_SIZE
            resp  = self._get(path, params)
            items = resp.get("data") or (resp if isinstance(resp, list) else [])
            todos.extend(items)
            if len(items) < _PAGE_SIZE:
                break
        return todos

    def test_conexion(self) -> bool:
        """Verifica credenciales consultando el endpoint de la empresa."""
        try:
            self._get(f"/companies/{self._company_id}", {"per_page": 1})
            log.info("test_conexion Buk: OK")
            return True
        except Exception as e:
            log.error(f"test_conexion Buk fallo: {e}")
            return False

    def get_resumen_dotacion(self) -> list[dict]:
        """Descarga empleados activos y devuelve un resumen normalizado.

        Cada registro: empleado_id, nombre, cargo, departamento, estado.
        """
        empleados_raw = self._paginar(f"/companies/{self._company_id}/employees")

        resumen = []
        for emp in empleados_raw:
            nombre = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            resumen.append({
                "empleado_id":  emp.get("id"),
                "nombre":       nombre,
                "cargo":        emp.get("job_title") or emp.get("position") or "",
                "departamento": emp.get("department") or "",
                "estado":       emp.get("status", "activo"),
            })

        log.info(f"get_resumen_dotacion: {len(resumen)} empleados")
        return resumen

    def get_ausencias(self, desde: str, hasta: str) -> list[dict]:
        """Descarga ausencias y licencias del rango [desde, hasta] (YYYY-MM-DD).

        Consulta /companies/{id}/leave_requests filtrando por fecha.
        Cada registro: empleado_id, nombre, tipo_ausencia, fecha_inicio,
        fecha_fin, dias_habiles, estado.

        Args:
            desde: Fecha inicio ISO (YYYY-MM-DD).
            hasta: Fecha fin ISO (YYYY-MM-DD).
        """
        params = {"start_date": desde, "end_date": hasta}
        raw = self._paginar(f"/companies/{self._company_id}/leave_requests", params)

        ausencias = []
        for item in raw:
            emp = item.get("employee") or {}
            nombre = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            ausencias.append({
                "empleado_id":   emp.get("id") or item.get("employee_id"),
                "nombre":        nombre,
                "tipo_ausencia": item.get("leave_type") or item.get("absence_type") or "",
                "fecha_inicio":  item.get("start_date") or "",
                "fecha_fin":     item.get("end_date") or "",
                "dias_habiles":  float(item.get("business_days") or item.get("days") or 0),
                "estado":        item.get("status") or "pendiente",
            })

        log.info(f"get_ausencias ({desde}→{hasta}): {len(ausencias)} registros")
        return ausencias
