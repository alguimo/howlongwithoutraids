"""Adaptador de ScrapedDuck.

``events.json`` trae las ventanas: los eventos ``raid-battles`` son la rotación
y ``raid-hour``/``raid-day`` marcan evento corto. ``raids.json`` es el roster
actual (identidad, tier, tipos, sprite), sin fechas.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from raids.intervals import Window, is_short_event, overlaps
from raids.log import log_omitted
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
    event_name: str | None = None


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
    event_name: str | None = None
    event_id: str = ""


def normalize_raid_windows(payload: Any, now: datetime) -> ParsedEvents:
    """Normalize complete raid windows without inventing an open-ended end.

    This is deliberately limited to the source-level window rules. Roster
    resolution and persistence remain in the weekly sync pipeline.
    """
    now = to_utc(now)
    events = _as_list(payload)
    known_starts = []
    for event in events:
        if not isinstance(event, dict) or event.get("eventType") != RAID_BATTLES:
            continue
        if event.get("start") is not None:
            try:
                known_starts.append(to_utc(event["start"]))
            except (TypeError, ValueError):
                continue
    known_starts.sort()

    windows: list[BossWindow] = []
    short_events: list[ShortEvent] = []
    for event in events:
        if not isinstance(event, dict):
            raise InvalidSourcePayload("event is not an object")
        kind = event.get("eventType")
        event_id = str(event.get("eventID", ""))
        start_value = event.get("start")
        end_value = event.get("end")

        if kind == RAID_BATTLES:
            if start_value is None:
                log_omitted("missing start", event_id=event_id)
                continue
            try:
                start = to_utc(start_value)
            except (TypeError, ValueError):
                log_omitted("invalid start", event_id=event_id)
                continue

            if end_value is None:
                later_starts = [candidate for candidate in known_starts if candidate > start]
                end = derive_past_end(start, later_starts, now)
                if end is None:
                    log_omitted("missing end", event_id=event_id)
                    continue
            else:
                try:
                    end = to_utc(end_value)
                except (TypeError, ValueError):
                    log_omitted("invalid end", event_id=event_id)
                    continue

            if start >= end:
                log_omitted("invalid window", event_id=event_id)
                continue
            event_name = _clean_event_name(event.get("name"))
            for boss_name in _event_bosses(event):
                windows.append(
                    BossWindow(event_id, boss_name, start, end, event_name)
                )
        elif kind and is_short_event(kind):
            if start_value is None:
                log_omitted("missing start", event_id=event_id)
                continue
            if end_value is None:
                log_omitted("missing end", event_id=event_id)
                continue
            try:
                start = to_utc(start_value)
                end = to_utc(end_value)
            except (TypeError, ValueError):
                log_omitted("invalid window", event_id=event_id)
                continue
            if start >= end:
                log_omitted("invalid window", event_id=event_id)
                continue
            short_events.append(
                ShortEvent(
                    event_id,
                    str(kind),
                    str(event.get("name", "")),
                    start,
                    end,
                )
            )
    return ParsedEvents(tuple(windows), tuple(short_events))


def derive_past_end(
    start: datetime,
    later_rotation_starts: Iterable[datetime],
    now: datetime,
) -> datetime | None:
    """Return the first later rotation start only for a closed past window.

    A later start that is still in the future does not prove that the current
    rotation ended, so open current and future rotations deliberately return
    ``None``.  The caller logs the omission because this pure helper has no
    logging side effect.
    """
    start = to_utc(start)
    now = to_utc(now)
    if start >= now:
        return None
    candidates = tuple(
        candidate
        for candidate in (to_utc(value) for value in later_rotation_starts)
        if start < candidate <= now
    )
    return min(candidates, default=None)


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


def _clean_event_name(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _event_bosses(event: dict) -> list[str]:
    extra = event.get("extraData") or {}
    raidbattles = extra.get("raidbattles") or {}
    bosses = raidbattles.get("bosses") or []
    return [
        str(boss["name"])
        for boss in bosses
        if isinstance(boss, dict) and "name" in boss
    ]


def parse_events(payload: Any, *, now: datetime | None = None) -> ParsedEvents:
    """Parse events, optionally applying explicit open-window normalization.

    The no-``now`` form remains for callers that only parse already complete
    fixtures. State-dependent normalization must provide ``now`` explicitly.
    """
    if now is not None:
        return normalize_raid_windows(payload, now)
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
            event_name = _clean_event_name(event.get("name"))
            for boss_name in _event_bosses(event):
                windows.append(
                    BossWindow(
                        event_id=event_id,
                        boss_name=boss_name,
                        start=to_utc(start),
                        end=to_utc(end),
                        event_name=event_name,
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


def _matching_short_event(
    window: BossWindow, shorts: list[ShortEvent]
) -> ShortEvent | None:
    return next(
        (
            event
            for event in shorts
            if short_event_boss(event).lower() == window.boss_name.lower()
            and overlaps(
                Window(window.start, window.end), Window(event.start, event.end)
            )
        ),
        None,
    )


def mark_windows(
    windows: Iterable[BossWindow], short_events: Iterable[ShortEvent]
) -> list[BossAppearance]:
    """Mark a rotation as a short event and carry the right event name.

    RF-16 restricts ``last_special_event_end_date`` to Raid Hour/Day, and RF-43
    names the appearance that fixes that date. The model keeps one ``event_name``
    per appearance, so a window marked as special stores the short event's
    ``name`` (Raid Hour/Day); a regular window keeps the ``raid-battles`` event
    name. Choosing the rotation name for a special window would mislabel the
    special date.
    """
    shorts = list(short_events)
    appearances = []
    for window in windows:
        matched = _matching_short_event(window, shorts)
        event_name = (
            _clean_event_name(matched.name) if matched else window.event_name
        )
        appearances.append(
            BossAppearance(
                window.boss_name,
                window.start,
                window.end,
                matched is not None,
                event_name=event_name,
                event_id=window.event_id,
            )
        )
    return appearances
