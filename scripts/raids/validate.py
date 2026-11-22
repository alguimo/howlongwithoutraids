"""Validación del snapshot contra el contrato.

Comprueba campos, identidad, coherencia de ``last_end_date`` y la ausencia de
cualquier conteo de días precalculado. Un snapshot inconsistente no debe
publicarse.
"""

import re
from datetime import datetime, timedelta, timezone

REQUIRED_FIELDS = (
    "dex_number",
    "form",
    "variant",
    "name",
    "is_legendary",
    "is_mythical",
    "is_baby",
    "is_ultra_beast",
    "types",
    "sprite_url",
    "current_start",
    "current_end",
    "last_regular_end_date",
    "last_regular_event_name",
    "last_special_event_end_date",
    "last_special_event_name",
    "last_end_date",
    "appearance_count",
    "tier",
    "last_tier",
    "current_event_name",
)

# PokeAPI categories: the source value or ``null``, never a default (RF-40).
CATEGORY_FIELDS = ("is_legendary", "is_mythical", "is_baby")
# Event names: a non-empty string or ``null``, never blank (RF-43).
EVENT_NAME_FIELDS = (
    "last_regular_event_name", "last_special_event_name", "current_event_name"
)
TIER_VALUES = frozenset(
    ("1", "2", "3", "4", "5", "MEGA", "MEGA_LEGENDARY", "SUPER_MEGA",
     "PRIMAL", "ELITE", "SHADOW_1", "SHADOW_3", "SHADOW_5")
)
VARIANT_VALUES = frozenset(("NORMAL", "MEGA", "PRIMAL", "SHADOW", "APEX"))
DATE_FIELDS = (
    "current_start", "current_end", "last_regular_end_date",
    "last_special_event_end_date", "last_end_date",
)

DAYS_TEXT = re.compile(r"hace\s+\d+|\b\d+\s+(?:days?|d[ií]as?)\b", re.IGNORECASE)


class InvalidSnapshot(ValueError):
    """El snapshot incumple el contrato y no debe escribirse."""


def _parse(value, *, allow_floating_local: bool = False):
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise InvalidSnapshot(f"invalid ISO date {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if allow_floating_local and "T" in str(value):
            return parsed.replace(tzinfo=timezone.utc)
        raise InvalidSnapshot(f"date {value!r} must include a timezone")
    return parsed


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
        extra = sorted(set(row) - set(REQUIRED_FIELDS))
        if extra:
            raise InvalidSnapshot(f"row {index} has unknown fields: {extra}")

        identity = (row["dex_number"], row["form"], row["variant"])
        if any(value is None or value == "" for value in identity):
            raise InvalidSnapshot(f"row {index} has an incomplete identity")
        if identity in seen:
            raise InvalidSnapshot(f"row {index} duplicates identity {identity}")
        seen.add(identity)

        if (
            not isinstance(row["dex_number"], int)
            or isinstance(row["dex_number"], bool)
            or row["dex_number"] <= 0
        ):
            raise InvalidSnapshot(f"row {index} dex_number must be a positive integer")
        if not isinstance(row["form"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", row["form"]):
            raise InvalidSnapshot(f"row {index} form is not a valid slug")
        if row["variant"] not in VARIANT_VALUES:
            raise InvalidSnapshot(f"row {index} variant is invalid")
        if not isinstance(row["name"], str) or not row["name"].strip():
            raise InvalidSnapshot(f"row {index} name must be a non-empty string")
        if not isinstance(row["types"], list) or not all(isinstance(item, str) for item in row["types"]):
            raise InvalidSnapshot(f"row {index} types must be a list of strings")
        if row["sprite_url"] is not None and not isinstance(row["sprite_url"], str):
            raise InvalidSnapshot(f"row {index} sprite_url must be a string or null")
        if not isinstance(row["appearance_count"], int) or isinstance(row["appearance_count"], bool) or row["appearance_count"] <= 0:
            raise InvalidSnapshot(f"row {index} appearance_count must be a positive integer")

        for field in CATEGORY_FIELDS:
            value = row[field]
            if value is not None and not isinstance(value, bool):
                raise InvalidSnapshot(
                    f"row {index} field {field!r} must be true, false or null"
                )

        if not isinstance(row["is_ultra_beast"], bool):
            raise InvalidSnapshot(
                f"row {index} field 'is_ultra_beast' must be a boolean"
            )

        for field in EVENT_NAME_FIELDS:
            value = row[field]
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise InvalidSnapshot(
                    f"row {index} field {field!r} must be null or a non-empty string"
                )

        for field in ("tier", "last_tier"):
            value = row[field]
            if value is not None and value not in TIER_VALUES:
                raise InvalidSnapshot(
                    f"row {index} field {field!r} must be null or a valid tier"
                )

        for key, value in row.items():
            if "days" in key.lower():
                raise InvalidSnapshot(f"row {index} has a precomputed days field {key!r}")
            if isinstance(value, str) and DAYS_TEXT.search(value):
                raise InvalidSnapshot(f"row {index} has precomputed days text in {key!r}")

        dates = {
            field: _parse(
                row[field], allow_floating_local=field in ("current_start", "current_end")
            )
            for field in DATE_FIELDS
        }
        if (dates["current_start"] is None) != (dates["current_end"] is None):
            raise InvalidSnapshot(f"row {index} current window must have both dates or neither")
        if dates["current_start"] is not None and dates["current_start"] > dates["current_end"]:
            raise InvalidSnapshot(f"row {index} current window starts after it ends")

        expected = _latest(
            dates["last_regular_end_date"], dates["last_special_event_end_date"]
        )
        if dates["last_end_date"] != expected:
            raise InvalidSnapshot(
                f"row {index} last_end_date {row['last_end_date']!r} is not the latest"
                " of the two varieties"
            )


def validate_snapshot_meta(meta) -> None:
    if not isinstance(meta, dict):
        raise InvalidSnapshot("snapshot metadata must be an object")

    for key, value in meta.items():
        if isinstance(key, str) and "days" in key.lower():
            raise InvalidSnapshot(f"snapshot metadata has a precomputed days field {key!r}")
        if isinstance(value, str) and DAYS_TEXT.search(value):
            raise InvalidSnapshot(f"snapshot metadata has precomputed days text in {key!r}")

    if "exported_at" not in meta:
        raise InvalidSnapshot("snapshot metadata is missing 'exported_at'")
    extra = sorted(set(meta) - {"exported_at"})
    if extra:
        raise InvalidSnapshot(f"snapshot metadata has unknown fields: {extra}")

    exported_at = meta["exported_at"]
    if not isinstance(exported_at, str) or not exported_at.strip():
        raise InvalidSnapshot("snapshot metadata 'exported_at' must be a non-empty string")
    if not exported_at.endswith("Z"):
        raise InvalidSnapshot("snapshot metadata 'exported_at' must use UTC Z suffix")
    parsed = _parse(exported_at)
    if parsed is None or parsed.utcoffset() != timedelta(0):
        raise InvalidSnapshot("snapshot metadata 'exported_at' must be UTC")
