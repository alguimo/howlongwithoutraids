"""Construcción y escritura del snapshot.

Una fila por jefe con al menos una aparición. El instante ``as_of`` entra como
parámetro: nunca se usa ``now()`` de la vista, para que el resultado sea
reproducible y no quede atado al reloj de la base.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from raids.intervals import Window, merge_windows
from raids.log import get_logger


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _max_datetime(values):
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _select(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [description.name for description in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _merged_appearances(appearances):
    buckets = {False: [], True: []}
    for appearance in appearances:
        buckets[appearance["is_special_event"]].append(
            Window(appearance["start_date"], appearance["end_date"])
        )
    merged = []
    for windows in buckets.values():
        merged.extend(merge_windows(windows))
    return merged


def _row(pokemon, appearances, as_of):
    active = [a for a in appearances if a["start_date"] <= as_of < a["end_date"]]
    if active:
        current = max(active, key=lambda a: (a["start_date"], a["end_date"]))
    else:
        upcoming = [a for a in appearances if a["start_date"] > as_of]
        current = min(upcoming, key=lambda a: a["start_date"]) if upcoming else None

    regular_end = _max_datetime(
        a["end_date"]
        for a in appearances
        if not a["is_special_event"] and a["end_date"] <= as_of
    )
    special_end = _max_datetime(
        a["end_date"]
        for a in appearances
        if a["is_special_event"] and a["end_date"] <= as_of
    )
    last_end = _max_datetime([regular_end, special_end])

    return {
        "dex_number": pokemon["dex_number"],
        "form": pokemon["form"],
        "variant": pokemon["variant"],
        "name": pokemon["name"],
        "types": list(pokemon["types"]),
        "sprite_url": pokemon["sprite_url"],
        "current_start": _iso(current["start_date"] if current else None),
        "current_end": _iso(current["end_date"] if current else None),
        "last_regular_end_date": _iso(regular_end),
        "last_special_event_end_date": _iso(special_end),
        "last_end_date": _iso(last_end),
        "appearance_count": len(_merged_appearances(appearances)),
        "tier": current["tier"] if current else None,
    }


def build_snapshot(conn, *, as_of: datetime) -> list[dict]:
    pokemon_rows = _select(
        conn,
        "SELECT id, dex_number, form, variant, name, types, sprite_url FROM pokemon",
    )
    appearance_rows = _select(
        conn,
        "SELECT pokemon_id, tier, start_date, end_date, is_special_event FROM raid_appearances",
    )

    by_pokemon: dict[int, list] = {}
    for appearance in appearance_rows:
        by_pokemon.setdefault(appearance["pokemon_id"], []).append(appearance)

    snapshot = []
    for pokemon in pokemon_rows:
        appearances = by_pokemon.get(pokemon["id"], [])
        if not appearances:
            continue
        snapshot.append(_row(pokemon, appearances, as_of))

    snapshot.sort(key=lambda row: (row["dex_number"], row["form"], row["variant"]))
    return snapshot


def write_snapshot(path, rows, *, logger=None) -> bool:
    if not rows:
        (logger or get_logger()).warning("snapshot not written: no rows")
        return False
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True
