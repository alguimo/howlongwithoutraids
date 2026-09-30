"""Fechas de la fuente a instantes UTC.

Toda fecha que traiga zona se convierte. Si no trae hora, se interpreta como
las 23:59:59 de ese día en ``America/Los_Angeles``, porque el fin de un día de
raid pertenece al día local del evento y no al UTC.
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

LOS_ANGELES = ZoneInfo("America/Los_Angeles")

END_OF_DAY = time(23, 59, 59)


def _parse(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return datetime.combine(date.fromisoformat(text), END_OF_DAY)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def to_utc(value: str | datetime) -> datetime:
    moment = value if isinstance(value, datetime) else _parse(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOS_ANGELES)
    return moment.astimezone(timezone.utc)
