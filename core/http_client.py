"""
http_client.py — Cliente HTTP genérico con retry, rate-limit y logging.

Usado por todos los adapters para eliminar duplicación de código
(urllib, retry, parseo de errores, etc.).
"""
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional
from core.logger import get_logger

log = get_logger("http_client")


class HTTPClient:
    """Cliente HTTP minimalista con retry integrado y rate-limit básico."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        rate_limit_delay: float = 0.0,
        default_headers: Optional[dict] = None,
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._rate_limit_delay = rate_limit_delay
        self._default_headers = default_headers or {}
        self._last_request_time: float = 0.0

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[bytes] = None,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Ejecuta un request con retry automático y rate limiting."""
        url = self._base + path
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url += ("&" if "?" in url else "?") + qs

        merged_headers = {**self._default_headers, **(headers or {})}

        if self._rate_limit_delay > 0:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._rate_limit_delay:
                time.sleep(self._rate_limit_delay - elapsed)

        ultimo_exc = None
        for intento in range(1, self._max_retries + 1):
            try:
                self._last_request_time = time.monotonic()
                req = urllib.request.Request(
                    url, data=data, headers=merged_headers, method=method
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:500]
                ultimo_exc = e
                log.warning(
                    "HTTP %s en %s (intento %d/%d): %s",
                    e.code, url, intento, self._max_retries, body,
                )
                if intento < self._max_retries:
                    time.sleep(self._backoff_base ** intento)
            except urllib.error.URLError as e:
                ultimo_exc = e
                log.warning(
                    "URLError en %s (intento %d/%d): %s",
                    url, intento, self._max_retries, e.reason,
                )
                if intento < self._max_retries:
                    time.sleep(self._backoff_base ** intento)
            except json.JSONDecodeError as e:
                ultimo_exc = e
                log.warning(
                    "JSON inválido en %s (intento %d/%d): %s",
                    url, intento, self._max_retries, e,
                )
                if intento < self._max_retries:
                    time.sleep(self._backoff_base ** intento)

        raise ultimo_exc

    def get(self, path: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
        return self._request("GET", path, headers=headers, params=params)

    def post(
        self,
        path: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        body = urllib.parse.urlencode(data or {}).encode("utf-8") if data else None
        merged = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
        return self._request("POST", path, data=body, headers=merged, params=params)

    def post_json(
        self,
        path: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        body = json.dumps(data or {}).encode("utf-8") if data else None
        merged = {"Content-Type": "application/json", **(headers or {})}
        return self._request("POST", path, data=body, headers=merged, params=params)
