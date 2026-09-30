"""Backfill del histórico 2017-presente desde MediaWiki ``action=parse``.

Solo se leen tablas wikitext de las páginas fijadas; nunca se toca el DOM.
"""

import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime

import httpx
import psycopg

from raids.log import log_omitted
from raids.pokedex import Catalog
from raids.sources import mediawiki
from raids.store import record_appearance, upsert_pokemon
from raids.time import to_utc

DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")

_ROW = re.compile(
    r"^\|\s*(.+?)\s*\|\|\s*(.+?)\s*\|\|\s*(.+?)\s*\|\|\s*(.+?)\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class ChangeRow:
    start: datetime
    end: datetime
    boss_name: str
    tier: str


def parse_changes(wikitext: str) -> list[ChangeRow]:
    rows = []
    for match in _ROW.finditer(wikitext):
        start, end, boss_name, tier = (cell.strip() for cell in match.groups())
        rows.append(ChangeRow(to_utc(start), to_utc(end), boss_name, tier))
    return rows


def run(conn, *, client, pages, api=mediawiki.DEFAULT_API, logger=None) -> int:
    catalog = Catalog.from_conn(conn)
    written = 0
    for page in pages:
        parsed = mediawiki.fetch_page(client, page, api=api)
        for row in parse_changes(parsed.wikitext):
            resolved = catalog.resolve(row.boss_name)
            if resolved is None:
                log_omitted("boss not in catalog", logger=logger, name=row.boss_name)
                continue
            pokemon_id = upsert_pokemon(
                conn,
                resolved.identity,
                name=row.boss_name,
                types=resolved.types,
                sprite_url=resolved.sprite_url,
            )
            record_appearance(
                conn,
                pokemon_id,
                tier=row.tier,
                start=row.start,
                end=row.end,
                source="pogo_wiki",
                logger=logger,
            )
            written += 1
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("pages", nargs="+")
    args = parser.parse_args(argv)

    with httpx.Client(headers={"User-Agent": mediawiki.USER_AGENT}) as client:
        with psycopg.connect(args.dsn, autocommit=True) as conn:
            written = run(conn, client=client, pages=args.pages)
    print(f"appearances: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
