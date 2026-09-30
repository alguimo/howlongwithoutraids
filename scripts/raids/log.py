"""Log del pipeline: filas omitidas y valores desplazados.

Va al log del script, no a un archivo junto al snapshot.
"""

import logging
from typing import Any

LOGGER_NAME = "raids"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def _suffix(context: dict[str, Any]) -> str:
    if not context:
        return ""
    pairs = " ".join(f"{key}={value}" for key, value in sorted(context.items()))
    return f" | {pairs}"


def log_omitted(reason: str, *, logger: logging.Logger | None = None, **context: Any) -> None:
    (logger or get_logger()).warning("row omitted: %s%s", reason, _suffix(context))


def log_displaced(
    previous: object,
    current: object,
    *,
    logger: logging.Logger | None = None,
    **context: Any,
) -> None:
    (logger or get_logger()).info(
        "value displaced: previous=%s current=%s%s", previous, current, _suffix(context)
    )


def log_source_failure(
    reason: str, *, logger: logging.Logger | None = None, **context: Any
) -> None:
    (logger or get_logger()).warning("source ingest skipped: %s%s", reason, _suffix(context))
