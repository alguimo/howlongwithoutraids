"""Ventanas de raid: validación, fusión por solape y marca de evento corto.

``raids.json`` define la ventana. ``events.json`` no crea ni alarga apariciones:
solo marca una ventana ya existente si solapa y es Raid Hour o Raid Day.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Iterable

from raids.log import log_overlap

SHORT_EVENT_KINDS = frozenset({"raid_hour", "raid_day"})


class InvertedWindow(ValueError):
    """La ventana tiene el inicio posterior al fin."""


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Event:
    start: datetime
    end: datetime
    kind: str


@dataclass(frozen=True)
class Appearance:
    start: datetime
    end: datetime
    is_special_event: bool = False


@dataclass(frozen=True)
class Origin:
    source: str
    page_title: str
    page_kind: str


@dataclass(frozen=True)
class ConsolidatedRecord:
    """A record plus every document that contributed to its window."""

    record: Any
    origins: tuple[Origin, ...]


@dataclass(frozen=True)
class WindowConflict:
    previous: Any
    current: Any
    chosen_end: datetime


@dataclass(frozen=True)
class WindowOverlap:
    """Two overlapping windows from different sources kept separate (RF-36)."""

    first: Any
    second: Any


@dataclass(frozen=True)
class ConsolidationResult:
    records: tuple[ConsolidatedRecord, ...]
    conflicts: tuple[WindowConflict, ...] = ()
    overlaps: tuple[WindowOverlap, ...] = ()


def validate_window(start: datetime, end: datetime) -> None:
    if end < start:
        raise InvertedWindow(f"start {start.isoformat()} is after end {end.isoformat()}")


def overlaps(a: Window, b: Window) -> bool:
    return a.start < b.end and b.start < a.end


def merge_windows(windows: Iterable[Window]) -> list[Window]:
    merged: list[Window] = []
    for window in sorted(windows, key=lambda item: (item.start, item.end)):
        validate_window(window.start, window.end)
        if merged and window.start < merged[-1].end:
            previous = merged[-1]
            merged[-1] = Window(previous.start, max(previous.end, window.end))
        else:
            merged.append(window)
    return merged


def is_short_event(kind: str) -> bool:
    normalized = str(kind).strip().lower().replace(" ", "_").replace("-", "_")
    return normalized in SHORT_EVENT_KINDS


def mark_events(raid_windows: Iterable[Window], events: Iterable[Event]) -> list[Appearance]:
    short_events = [
        Window(event.start, event.end) for event in events if is_short_event(event.kind)
    ]
    appearances = []
    for window in raid_windows:
        is_special = any(overlaps(window, event) for event in short_events)
        appearances.append(Appearance(window.start, window.end, is_special))
    return appearances


def _identity_key(record: Any) -> tuple[Any, ...]:
    identity = record.identity
    return identity.dex_number, identity.form, identity.variant


def _origin(record: Any) -> Origin:
    return Origin(record.source, record.page_title, record.page_kind)


def _record_key(record: Any) -> tuple[Any, ...]:
    return (*_identity_key(record), record.start, record.end)


def _with_window(record: Any, start: datetime, end: datetime) -> Any:
    return replace(record, start=start, end=end)


def deduplicate_records(records: Iterable[Any]) -> ConsolidationResult:
    """Collapse exact windows while retaining all their document origins.

    Windows are compared by ``(dex_number, form, variant, start, end)`` with
    exact UTC instants and independently of the source, so the same window
    reported by Fandom and Bulbapedia becomes one record with both origins
    (RF-36).  Different ends are not duplicates: they are kept separate and
    reported as cross-source overlaps by :func:`find_cross_source_overlaps`.
    """
    groups: dict[tuple[Any, ...], ConsolidatedRecord] = {}
    for record in records:
        validate_window(record.start, record.end)
        key = _record_key(record)
        existing = groups.get(key)
        origin = _origin(record)
        if existing is None:
            groups[key] = ConsolidatedRecord(record, (origin,))
        elif origin not in existing.origins:
            groups[key] = ConsolidatedRecord(existing.record, (*existing.origins, origin))
    return ConsolidationResult(tuple(groups.values()))


def _as_record(item: Any) -> Any:
    return item.record if isinstance(item, ConsolidatedRecord) else item


def find_cross_source_overlaps(records: Iterable[Any]) -> tuple[WindowOverlap, ...]:
    """Return windows from different sources that overlap but are not identical.

    Exact windows are duplicates (already collapsed by
    :func:`deduplicate_records`) and same-source overlaps are merged by
    :func:`merge_records_by_source` (RF-05), so neither counts here.  Each
    remaining pair is kept separate on purpose: merging it would invent a
    window no source published (RF-36).
    """
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for item in records:
        record = _as_record(item)
        groups.setdefault(_identity_key(record), []).append(record)

    overlaps: list[WindowOverlap] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda record: (record.start, record.end, record.source))
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if second.start >= first.end:
                    break
                if first.source == second.source:
                    continue
                if (first.start, first.end) == (second.start, second.end):
                    continue
                overlaps.append(WindowOverlap(first, second))
    return tuple(overlaps)


def merge_records_by_source(
    records: Iterable[Any], *, logger=None
) -> ConsolidationResult:
    """Merge overlapping windows only within the same source and identity.

    Exact windows across sources are first collapsed into one record with both
    origins (RF-36).  Remaining overlaps between different sources are kept
    separate and logged, never merged.
    """
    exact = deduplicate_records(records)
    buckets: dict[tuple[Any, ...], list[ConsolidatedRecord]] = {}
    for item in exact.records:
        key = (*_identity_key(item.record), item.record.source)
        buckets.setdefault(key, []).append(item)

    merged: list[ConsolidatedRecord] = []
    conflicts: list[WindowConflict] = list(exact.conflicts)
    for items in buckets.values():
        current: ConsolidatedRecord | None = None
        for item in sorted(items, key=lambda value: (value.record.start, value.record.end)):
            if current is None:
                current = item
                continue
            if item.record.start < current.record.end:
                end = max(current.record.end, item.record.end)
                if current.record.end != item.record.end:
                    conflicts.append(WindowConflict(current.record, item.record, end))
                current = ConsolidatedRecord(
                    _with_window(current.record, current.record.start, end),
                    tuple(dict.fromkeys((*current.origins, *item.origins))),
                )
            else:
                merged.append(current)
                current = item
        if current is not None:
            merged.append(current)
    merged.sort(key=lambda item: (*_identity_key(item.record), item.record.start, item.record.end))

    overlaps = find_cross_source_overlaps(merged)
    for overlap in overlaps:
        log_overlap(
            _window_label(overlap.first),
            _window_label(overlap.second),
            logger=logger,
        )
    return ConsolidationResult(tuple(merged), tuple(conflicts), overlaps)


def _window_label(record: Any) -> str:
    return (
        f"{record.start.isoformat()}/{record.end.isoformat()} "
        f"[{record.source}:{record.page_title}]"
    )
