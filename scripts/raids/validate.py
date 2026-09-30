"""Validación del snapshot contra el contrato.

Comprueba campos, identidad, coherencia de ``last_end_date`` y la ausencia de
cualquier conteo de días precalculado. Un snapshot inconsistente no debe
publicarse.
"""

import re
from datetime import datetime

REQUIRED_FIELDS = (
    "dex_number",
    "form",
    "variant",
    "name",
    "types",
    "sprite_url",
    "current_start",
    "current_end",
    "last_regular_end_date",
    "last_special_event_end_date",
    "last_end_date",
    "appearance_count",
    "tier",
)

DAYS_TEXT = re.compile(r"hace\s+\d+|\b\d+\s+(?:days?|d[ií]as?)\b", re.IGNORECASE)


class InvalidSnapshot(ValueError):
    """El snapshot incumple el contrato y no debe escribirse."""


def _parse(value):
    if value is None:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _latest(*values):
    present = [v for v in values if v is not None]
    return max(present) if present else None


def validate_snapshot(rows) -> None:
    if not isinstance(rows, list):
        raise InvalidSnapshot("snapshot must be a list of rows")

    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InvalidSnapshot(f"row {index} is not an object")

        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise InvalidSnapshot(f"row {index} is missing fields: {missing}")

        identity = (row["dex_number"], row["form"], row["variant"])
        if any(value is None or value == "" for value in identity):
            raise InvalidSnapshot(f"row {index} has an incomplete identity")
        if identity in seen:
            raise InvalidSnapshot(f"row {index} duplicates identity {identity}")
        seen.add(identity)

        for key, value in row.items():
            if "days" in key.lower():
                raise InvalidSnapshot(f"row {index} has a precomputed days field {key!r}")
            if isinstance(value, str) and DAYS_TEXT.search(value):
                raise InvalidSnapshot(f"row {index} has precomputed days text in {key!r}")

        expected = _latest(
            _parse(row["last_regular_end_date"]),
            _parse(row["last_special_event_end_date"]),
        )
        if _parse(row["last_end_date"]) != expected:
            raise InvalidSnapshot(
                f"row {index} last_end_date {row['last_end_date']!r} is not the latest"
                " of the two varieties"
            )
