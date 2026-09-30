"""Ventanas de raid: validación, fusión por solape y marca de evento corto.

``raids.json`` define la ventana. ``events.json`` no crea ni alarga apariciones:
solo marca una ventana ya existente si solapa y es Raid Hour o Raid Day.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

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
