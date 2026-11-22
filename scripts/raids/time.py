"""Fechas de la fuente a instantes UTC.

Toda fecha que traiga zona se convierte. Si no trae hora, se interpreta como
las 23:59:59 de ese día en ``America/Los_Angeles``, porque el fin de un día de
raid pertenece al día local del evento y no al UTC.
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

LOS_ANGELES = ZoneInfo("America/Los_Angeles")

END_OF_DAY = time(23, 59, 59)
ROTATION_LOCAL_START = time(10, 0, 0)


def _parse(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return datetime.combine(date.fromisoformat(text), END_OF_DAY)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def is_floating_local(value: str | datetime) -> bool:
    """True when ``value`` is a datetime with time-of-day and no timezone offset."""
    if isinstance(value, datetime):
        return value.tzinfo is None
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return False
    return _parse(text).tzinfo is None


def to_local_wall_utc(
    value: str | datetime, *, normalize_rotation_start: bool = False
) -> datetime:
    """Store a floating local wall-clock timestamp with UTC tzinfo (no shift).

    When ``normalize_rotation_start`` is set and the source marks an early
    morning egg-spawn hour (< 10:00), snaps the start to ``10:00:00`` local
    time, matching the actual Pokémon GO raid rotation switchover.
    """
    moment = value if isinstance(value, datetime) else _parse(value)
    if normalize_rotation_start and moment.time() < ROTATION_LOCAL_START:
        moment = moment.replace(
            hour=ROTATION_LOCAL_START.hour,
            minute=ROTATION_LOCAL_START.minute,
            second=ROTATION_LOCAL_START.second,
            microsecond=0,
        )
    return moment.replace(tzinfo=timezone.utc)


def to_utc(value: str | datetime) -> datetime:
    moment = value if isinstance(value, datetime) else _parse(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOS_ANGELES)
    return moment.astimezone(timezone.utc)
