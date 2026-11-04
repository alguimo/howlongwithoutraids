"""Sincronización semanal desde ScrapedDuck.

``raids.json`` aporta el roster y el tier; los eventos ``raid-battles`` de
``events.json`` aportan la ventana. Una fuente caída no bloquea a la otra.
"""

import argparse
import os
from datetime import datetime, timezone

import httpx
import psycopg

from raids.identity import UnmappableIdentity
from raids.log import log_omitted, log_source_failure
from raids.pokedex import Catalog, canonical_species_name, identity_from_boss
from raids.sources.scrapedduck import (
    mark_windows,
    parse_events,
    parse_raids,
)
from raids.store import AppearanceRecord, store_records, upsert_pokemon

DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
ROSTER_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json"
EVENTS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
USER_AGENT = "howlongwithoutraids/0.1 (local ETL)"


def _tier_by_name(roster) -> dict[str, str]:
    return {entry.name.strip().lower(): entry.tier for entry in roster if entry.tier}


def run(conn, fetch_roster, fetch_events, *, now=None, logger=None) -> dict:
    roster = []
    try:
        roster = parse_raids(fetch_roster())
    except Exception as exc:
        log_source_failure(f"raids.json: {exc}", logger=logger)

    initial_catalog = Catalog.from_conn(conn)
    tiers = _tier_by_name(roster)
    for entry in roster:
        try:
            identity = identity_from_boss(entry.name, entry.sprite_url)
        except UnmappableIdentity as exc:
            log_omitted(str(exc), logger=logger, name=entry.name)
            continue
        if identity is None:
            log_omitted("no dex in sprite filename", logger=logger, name=entry.name)
            continue
        upsert_pokemon(
            conn,
            identity,
            name=canonical_species_name(
                entry.name, catalog=initial_catalog, dex_number=identity.dex_number
            ),
            types=entry.types,
            sprite_url=entry.sprite_url,
        )

    catalog = Catalog.from_conn(conn)

    try:
        parsed = parse_events(fetch_events(), now=now)
    except Exception as exc:
        log_source_failure(f"events.json: {exc}", logger=logger)
        return {"written": 0}

    records = []
    for appearance in mark_windows(parsed.windows, parsed.short_events):
        resolved = catalog.resolve(appearance.boss_name)
        if resolved is None:
            log_omitted("boss not in catalog", logger=logger, name=appearance.boss_name)
            continue
        tier = tiers.get(appearance.boss_name.strip().lower())
        if tier is None:
            log_omitted(
                "no valid roster tier for boss", logger=logger, name=appearance.boss_name
            )
            continue
        records.append(
            AppearanceRecord(
                identity=resolved.identity,
                name=canonical_species_name(
                    appearance.boss_name,
                    catalog=catalog,
                    dex_number=resolved.identity.dex_number,
                ),
                types=resolved.types,
                sprite_url=None,
                tier=tier,
                start=appearance.start,
                end=appearance.end,
                source="scrapedduck",
                is_special_event=appearance.is_special_event,
                event_name=appearance.event_name,
            )
        )

    return {"written": store_records(conn, records, logger=logger)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args(argv)

    def fetch(url):
        return lambda: httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30).json()

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        result = run(
            conn,
            fetch(ROSTER_URL),
            fetch(EVENTS_URL),
            now=datetime.now(timezone.utc),
        )
    print(f"appearances: {result['written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
