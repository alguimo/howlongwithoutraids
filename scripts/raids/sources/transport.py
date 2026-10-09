"""Transportes HTTP inyectables.

Fandom vive detrás de Cloudflare, que rechaza con 403 a ``httpx`` por su huella
TLS; el ``urllib`` del stdlib sí responde. Ambos adaptadores comparten una
interfaz mínima para que ``mediawiki.fetch_page`` no sepa cuál usa::

    fetch(url, params, headers) -> (status_code, body_bytes)

No se añade ninguna dependencia (RF-38).
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol, runtime_checkable


class TransportError(Exception):
    """The request could not be completed by the HTTP transport."""


@runtime_checkable
class Transport(Protocol):
    def fetch(
        self, url: str, params: dict[str, str], headers: dict[str, str]
    ) -> tuple[int, bytes]: ...


class UrllibTransport:
    """stdlib transport for endpoints behind Cloudflare (Fandom)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(
        self, url: str, params: dict[str, str], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(_with_query(url, params), headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            # The status is data for the caller; only transport failures raise.
            return exc.code, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            raise TransportError(f"urllib transport error: {exc}") from exc


class HttpxTransport:
    """Adapter over the existing ``httpx`` client (Bulbapedia)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def fetch(
        self, url: str, params: dict[str, str], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        import httpx

        try:
            response = self._client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise TransportError(f"httpx transport error: {exc}") from exc
        return response.status_code, response.content


def _with_query(url: str, params: dict[str, str]) -> str:
    query = urllib.parse.urlencode(params)
    return f"{url}?{query}" if query else url
