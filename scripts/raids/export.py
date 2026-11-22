"""Construcción y escritura del snapshot.

Una fila por jefe con al menos una aparición. El instante ``as_of`` entra como
parámetro: nunca se usa ``now()`` de la vista, para que el resultado sea
reproducible y no quede atado al reloj de la base.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raids.intervals import Window, merge_windows
from raids.log import get_logger

TIER_PRECEDENCE = (
    "1", "2", "3", "4", "5", "MEGA", "MEGA_LEGENDARY", "SUPER_MEGA",
    "PRIMAL", "ELITE", "SHADOW_1", "SHADOW_3", "SHADOW_5",
)
_TIER_RANK = {tier: rank for rank, tier in enumerate(TIER_PRECEDENCE)}

def _iso(value: datetime | None, *, local_time: bool = False) -> str | None:
    if value is None:
        return None
    utc = value.astimezone(timezone.utc)
    if local_time:
        return utc.replace(tzinfo=None).isoformat(timespec="seconds")
    return utc.isoformat().replace("+00:00", "Z")


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


def _event_name_for(appearances, *, special, end):
    """Event name of the appearance that fixes ``last_*`` (RF-43).

    Only appearances of the requested variety whose ``end_date`` equals the
    fixed date count. If two of them disagree on the name, the tie is ambiguous
    and the field is ``null`` (RF-43); no name is invented.
    """
    if end is None:
        return None
    names = {
        appearance["event_name"]
        for appearance in appearances
        if appearance["is_special_event"] == special
        and appearance["end_date"] == end
        and appearance.get("event_name")
    }
    return names.pop() if len(names) == 1 else None


def last_tier_for(appearances, as_of):
    ended = [a for a in appearances if a["end_date"] <= as_of]
    if not ended:
        return None
    latest_end = max(a["end_date"] for a in ended)
    return max(
        (a["tier"] for a in ended if a["end_date"] == latest_end and a.get("tier") in _TIER_RANK),
        key=_TIER_RANK.get,
        default=None,
    )


def _current_event_name(appearances, current, as_of):
    if current is None:
        return None
    candidates = [
        a for a in appearances
        if a["start_date"] == current["start_date"]
        and (a["start_date"] <= as_of < a["end_date"] or a["start_date"] > as_of)
    ]
    names = {a.get("event_name") for a in candidates}
    if len(names) != 1:
        return None
    name = names.pop()
    return name if isinstance(name, str) and name else None


_LOCAL_TZ_MARGIN = timedelta(hours=14)


def _is_active_at(appearance, as_of: datetime) -> bool:
    if appearance.get("is_local_time"):
        return (
            appearance["start_date"] - _LOCAL_TZ_MARGIN
            <= as_of
            < appearance["end_date"] + _LOCAL_TZ_MARGIN
        )
    return appearance["start_date"] <= as_of < appearance["end_date"]


def _row(pokemon, appearances, as_of):
    active = [a for a in appearances if _is_active_at(a, as_of)]
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

    current_is_local = bool(current and current.get("is_local_time"))
    return {
        "dex_number": pokemon["dex_number"],
        "form": pokemon["form"],
        "variant": pokemon["variant"],
        "name": pokemon["name"],
        "is_legendary": pokemon["is_legendary"],
        "is_mythical": pokemon["is_mythical"],
        "is_baby": pokemon["is_baby"],
        "is_ultra_beast": bool(pokemon["is_ultra_beast"]),
        "types": list(pokemon["types"]),
        "sprite_url": pokemon["sprite_url"],
        "current_start": _iso(
            current["start_date"] if current else None, local_time=current_is_local
        ),
        "current_end": _iso(
            current["end_date"] if current else None, local_time=current_is_local
        ),
        "last_regular_end_date": _iso(regular_end),
        "last_regular_event_name": _event_name_for(
            appearances, special=False, end=regular_end
        ),
        "last_special_event_end_date": _iso(special_end),
        "last_special_event_name": _event_name_for(
            appearances, special=True, end=special_end
        ),
        "last_end_date": _iso(last_end),
        "appearance_count": len(_merged_appearances(appearances)),
        "tier": current["tier"] if current else None,
        "last_tier": last_tier_for(appearances, as_of),
        "current_event_name": _current_event_name(appearances, current, as_of),
    }


def build_snapshot(conn, *, as_of: datetime) -> list[dict]:
    pokemon_rows = _select(
        conn,
        "SELECT id, dex_number, form, variant, name, types, sprite_url,"
        " is_legendary, is_mythical, is_baby, is_ultra_beast FROM pokemon",
    )
    appearance_rows = _select(
        conn,
        "SELECT pokemon_id, tier, start_date, end_date, is_special_event,"
        " is_local_time, event_name FROM raid_appearances",
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


def _atomic_write_json(path, data) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def build_snapshot_meta(as_of: datetime) -> dict[str, str]:
    from raids.validate import InvalidSnapshot

    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise InvalidSnapshot("as_of must include a timezone")
    return {"exported_at": _iso(as_of)}


def write_snapshot_meta(path, meta: dict) -> None:
    from raids.validate import validate_snapshot_meta

    validate_snapshot_meta(meta)
    _atomic_write_json(path, meta)


def write_snapshot(path, rows, *, logger=None) -> bool:
    if not rows:
        (logger or get_logger()).warning("snapshot not written: no rows")
        return False
    # Keep this boundary safe for callers other than export_json.run too.  The
    # temporary file prevents a failed validation/serialization from truncating
    # the previous artifact.
    from raids.validate import validate_snapshot

    validate_snapshot(rows)
    _atomic_write_json(path, rows)
    return True
