"""Adaptador de ScrapedDuck.

``events.json`` trae las ventanas: los eventos ``raid-battles`` son la rotación
y ``raid-hour``/``raid-day`` marcan evento corto. ``raids.json`` es el roster
actual (identidad, tier, tipos, sprite), sin fechas.
"""

from dataclasses import dataclass
from datetime import datetime
import re
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
    "super mega raids": "SUPER_MEGA",
    "primal raids": "PRIMAL",
    "elite raids": "ELITE",
}

_EVENT_TIER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsuper\s+mega\s+raids?\b", re.IGNORECASE), "SUPER_MEGA"),
    (re.compile(r"\bmega\s+legendary\s+raids?\b", re.IGNORECASE), "MEGA_LEGENDARY"),
    (re.compile(r"\bmega\s+raids?\b", re.IGNORECASE), "MEGA"),
    (re.compile(r"\bprimal\s+raids?\b", re.IGNORECASE), "PRIMAL"),
    (re.compile(r"\belite\s+raids?\b", re.IGNORECASE), "ELITE"),
)
_STAR_EVENT_TIER_RE = re.compile(
    r"\b([1-5])-star\s+raid(?:s|\s+battles?)\b", re.IGNORECASE
)
_SHADOW_PREFIX_RE = re.compile(r"^shadow\s+", re.IGNORECASE)
_IN_SHADOW_RAIDS_RE = re.compile(r"\bin\s+shadow\s+raids?\b", re.IGNORECASE)
_IN_CLAUSE_RE = re.compile(r"\s+in\s+", re.IGNORECASE)


def tier_from_event_name(name: str | None) -> str | None:
    """Extract an explicit raid tier declared in an event title.

    Returns ``None`` for generic event titles or indeterminate Shadow Raids
    that do not specify a star level (Principle 13).
    """
    if not name:
        return None
    for pattern, tier in _EVENT_TIER_PATTERNS:
        if pattern.search(name):
            return tier
    star_match = _STAR_EVENT_TIER_RE.search(name)
    if star_match:
        return star_match.group(1)
    return None

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
        raw_name = str(entry["name"])
        tier = normalize_tier(entry.get("tier"))
        if tier in {"1", "3", "5"} and _SHADOW_PREFIX_RE.match(raw_name.strip()):
            tier = f"SHADOW_{tier}"
        roster.append(
            RosterEntry(
                name=raw_name,
                tier=tier,
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


def _ensure_shadow_prefix(name: str, is_shadow_event: bool) -> str:
    cleaned = name.strip()
    if is_shadow_event and cleaned and not _SHADOW_PREFIX_RE.match(cleaned):
        return f"Shadow {cleaned}"
    return cleaned


def _bosses_from_event_title(event_name: str | None) -> list[str]:
    if not event_name or not _IN_CLAUSE_RE.search(event_name):
        return []
    prefix = _IN_CLAUSE_RE.split(event_name, maxsplit=1)[0].strip()
    if not prefix or "(" in prefix:
        return [prefix] if prefix else []
    parts = [part.strip() for part in re.split(r",\s+and\s+|\s+and\s+|,\s*", prefix)]
    return [part for part in parts if part]


def _event_bosses(event: dict) -> list[str]:
    event_name = _clean_event_name(event.get("name"))
    is_shadow_event = bool(
        event_name
        and (_SHADOW_PREFIX_RE.match(event_name) or _IN_SHADOW_RAIDS_RE.search(event_name))
    )
    extra = event.get("extraData") or {}
    raidbattles = extra.get("raidbattles") or {}
    bosses = raidbattles.get("bosses") or []
    explicit = [
        _ensure_shadow_prefix(str(boss["name"]), is_shadow_event)
        for boss in bosses
        if isinstance(boss, dict) and "name" in boss
    ]
    if explicit:
        return explicit
    return [
        _ensure_shadow_prefix(name, is_shadow_event)
        for name in _bosses_from_event_title(event_name)
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
    for suffix, is_mega in (
        ("Super Mega Raid Day", True),
        ("Mega Raid Day", True),
        ("Raid Day", False),
        ("Raid Hour", False),
    ):
        if name.lower().endswith(suffix.lower()):
            boss = name[: -len(suffix)].strip()
            if not boss:
                return ""
            if is_mega and not boss.lower().startswith("mega "):
                return f"Mega {boss}"
            return boss
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
    name. Standalone ``raid-day`` events with an identifiable boss that do not
    overlap any ``raid-battles`` window are emitted as their own special
    appearances.
    """
    shorts = list(short_events)
    matched_short_ids: set[str] = set()
    appearances = []
    for window in windows:
        matched = _matching_short_event(window, shorts)
        if matched is not None:
            matched_short_ids.add(matched.event_id)
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
    for event in shorts:
        if event.kind != "raid-day" or event.event_id in matched_short_ids:
            continue
        boss_name = short_event_boss(event)
        if not boss_name:
            continue
        appearances.append(
            BossAppearance(
                boss_name=boss_name,
                start=event.start,
                end=event.end,
                is_special_event=True,
                event_name=_clean_event_name(event.name),
                event_id=event.event_id,
            )
        )
    return appearances
