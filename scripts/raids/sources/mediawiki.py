"""Adaptador de MediaWiki.

Solo ``api.php?action=parse`` de las páginas fijadas y con un ``User-Agent``
descriptivo. Nunca se hace scraping del DOM ni se abren navegadores headless.
"""

from dataclasses import dataclass
from typing import Any

import httpx

USER_AGENT = "howlongwithoutraids/0.1 (local ETL; +https://github.com/anomalyco/opencode)"
DEFAULT_API = "https://pokemongo.fandom.com/api.php"


class InvalidSourcePayload(ValueError):
    """La respuesta no es un ``action=parse`` válido."""


@dataclass(frozen=True)
class ParsedPage:
    title: str
    wikitext: str


def build_params(page: str, *, prop: str = "wikitext") -> dict[str, str]:
    return {
        "action": "parse",
        "format": "json",
        "formatversion": "2",
        "prop": prop,
        "page": page,
    }


def parse_response(payload: Any) -> ParsedPage:
    if not isinstance(payload, dict) or "parse" not in payload:
        raise InvalidSourcePayload("response is not an action=parse payload")
    parse = payload["parse"]
    if not isinstance(parse, dict) or "wikitext" not in parse:
        raise InvalidSourcePayload("parse payload without wikitext")
    return ParsedPage(title=str(parse.get("title", "")), wikitext=str(parse["wikitext"]))


def fetch_page(client: httpx.Client, page: str, *, api: str = DEFAULT_API) -> ParsedPage:
    response = client.get(
        api, params=build_params(page), headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    return parse_response(response.json())
