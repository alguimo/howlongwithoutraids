"""Adaptador de ScrapedDuck.

``events.json`` trae las ventanas: los eventos ``raid-battles`` son la rotación
y ``raid-hour``/``raid-day`` marcan evento corto. ``raids.json`` es el roster
actual (identidad, tier, tipos, sprite), sin fechas.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from raids.intervals import Window, is_short_event, overlaps
from raids.time import to_utc

RAID_BATTLES = "raid-battles"

TIER_LABELS = {
    "1-star raids": "1",
    "3-star raids": "3",
    "4-star raids": "4",
    "5-star raids": "5",
    "mega raids": "MEGA",
    "mega legendary raids": "MEGA_LEGENDARY",
    "primal raids": "PRIMAL",
    "elite raids": "ELITE",
}


class InvalidSourcePayload(ValueError):
    """El cuerpo de la fuente no tiene la forma esperada."""


@dataclass(frozen=True)
class RosterEntry:
    name: str
    tier: str | None
    types: tuple[str, ...]
    sprite_url: str | None


@dataclass(frozen=True)
class BossWindow:
    event_id: str
    boss_name: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class ShortEvent:
    event_id: str
    kind: str
    name: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class ParsedEvents:
    windows: tuple[BossWindow, ...]
    short_events: tuple[ShortEvent, ...]


@dataclass(frozen=True)
class BossAppearance:
    boss_name: str
    start: datetime
    end: datetime
    is_special_event: bool


def _as_list(payload: Any) -> list:
    if not isinstance(payload, list):
        raise InvalidSourcePayload("expected a JSON list at the top level")
    return payload


def normalize_tier(raw: Any) -> str | None:
    if raw is None:
        return None
    return TIER_LABELS.get(str(raw).strip().lower())


def parse_raids(payload: Any) -> list[RosterEntry]:
    roster = []
    for entry in _as_list(payload):
        if not isinstance(entry, dict) or "name" not in entry:
            raise InvalidSourcePayload("roster entry without a name")
        types = entry.get("types") or []
        if not isinstance(types, list):
            raise InvalidSourcePayload("roster entry 'types' must be a list")
        roster.append(
            RosterEntry(
                name=str(entry["name"]),
                tier=normalize_tier(entry.get("tier")),
                types=tuple(
                    str(item["name"])
                    for item in types
                    if isinstance(item, dict) and "name" in item
                ),
                sprite_url=entry.get("image"),
            )
        )
    return roster


def _event_bosses(event: dict) -> list[str]:
    extra = event.get("extraData") or {}
    raidbattles = extra.get("raidbattles") or {}
    bosses = raidbattles.get("bosses") or []
    return [
        str(boss["name"])
        for boss in bosses
        if isinstance(boss, dict) and "name" in boss
    ]


def parse_events(payload: Any) -> ParsedEvents:
    windows: list[BossWindow] = []
    short_events: list[ShortEvent] = []
    for event in _as_list(payload):
        if not isinstance(event, dict):
            raise InvalidSourcePayload("event is not an object")
        kind = event.get("eventType")
        start = event.get("start")
        end = event.get("end")
        event_id = str(event.get("eventID", ""))
        if kind == RAID_BATTLES:
            if start is None or end is None:
                continue
            for boss_name in _event_bosses(event):
                windows.append(
                    BossWindow(
                        event_id=event_id,
                        boss_name=boss_name,
                        start=to_utc(start),
                        end=to_utc(end),
                    )
                )
        elif kind and is_short_event(kind):
            if start is None or end is None:
                continue
            short_events.append(
                ShortEvent(
                    event_id=event_id,
                    kind=str(kind),
                    name=str(event.get("name", "")),
                    start=to_utc(start),
                    end=to_utc(end),
                )
            )
    return ParsedEvents(tuple(windows), tuple(short_events))


def short_event_boss(event: ShortEvent) -> str:
    name = event.name.strip()
    for suffix in ("Raid Hour", "Raid Day"):
        if name.lower().endswith(suffix.lower()):
            return name[: -len(suffix)].strip()
    return name


def mark_windows(
    windows: Iterable[BossWindow], short_events: Iterable[ShortEvent]
) -> list[BossAppearance]:
    shorts = list(short_events)
    appearances = []
    for window in windows:
        is_special = any(
            short_event_boss(event).lower() == window.boss_name.lower()
            and overlaps(
                Window(window.start, window.end), Window(event.start, event.end)
            )
            for event in shorts
        )
        appearances.append(
            BossAppearance(window.boss_name, window.start, window.end, is_special)
        )
    return appearances
