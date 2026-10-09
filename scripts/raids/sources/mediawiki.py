"""Adaptador de MediaWiki.

Solo ``api.php?action=parse`` de las páginas fijadas y con un ``User-Agent``
descriptivo. Nunca se hace scraping del DOM ni se abren navegadores headless.
El transporte HTTP se inyecta: ``UrllibTransport`` (stdlib) para Fandom, porque
Cloudflare rechaza con 403 la huella TLS de ``httpx``, y el adaptador ``httpx``
para Bulbapedia.
"""

import json
from dataclasses import dataclass
from typing import Any

from raids.sources.transport import Transport
from raids.sources.transport import TransportError as TransportFailure

USER_AGENT = "howlongwithoutraids/0.1 (local ETL; +https://github.com/anomalyco/opencode)"
DEFAULT_API = "https://bulbapedia.bulbagarden.net/w/api.php"
FANDOM_API = "https://pokemongo.fandom.com/api.php"


class SourceError(Exception):
    """Base class for failures that must not reach the persistence layer."""


class HTTPSourceError(SourceError):
    """The MediaWiki endpoint returned an unsuccessful HTTP status."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.kind = "server" if status_code >= 500 else "http"
        super().__init__(f"MediaWiki request failed with HTTP {status_code}")


class TransportError(SourceError):
    """The request could not be completed by the HTTP transport."""


class InvalidSourcePayload(SourceError, ValueError):
    """La respuesta no es un ``action=parse`` válido."""


@dataclass(frozen=True)
class ParsedPage:
    title: str
    wikitext: str


def build_params(page: str) -> dict[str, str]:
    return {
        "action": "parse",
        "format": "json",
        "formatversion": "2",
        "prop": "wikitext",
        "page": page,
    }


def parse_response(payload: Any) -> ParsedPage:
    if not isinstance(payload, dict) or "parse" not in payload:
        raise InvalidSourcePayload("response is not an action=parse payload")
    parse = payload["parse"]
    if (
        not isinstance(parse, dict)
        or not isinstance(parse.get("wikitext"), str)
    ):
        raise InvalidSourcePayload("parse payload without wikitext")
    title = parse.get("title", "")
    if not isinstance(title, str):
        raise InvalidSourcePayload("parse payload with invalid title")
    return ParsedPage(title=title, wikitext=parse["wikitext"])


def fetch_page(transport: Transport, page: str, *, api: str = DEFAULT_API) -> ParsedPage:
    try:
        status, body = transport.fetch(
            api, build_params(page), {"User-Agent": USER_AGENT}
        )
    except TransportFailure as exc:
        raise TransportError(f"MediaWiki transport error: {exc}") from exc

    if not 200 <= status < 300:
        raise HTTPSourceError(status)

    if isinstance(body, (bytes, bytearray)):
        try:
            text = bytes(body).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidSourcePayload("response body is not valid UTF-8") from exc
    elif isinstance(body, str):
        text = body
    else:
        raise InvalidSourcePayload("response body is not bytes or text")

    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise InvalidSourcePayload("response body is not valid JSON") from exc
    return parse_response(payload)
