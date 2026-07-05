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
