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


def log_overlap(
    first: object,
    second: object,
    *,
    logger: logging.Logger | None = None,
    **context: Any,
) -> None:
    (logger or get_logger()).info(
        "window overlap kept separate: first=%s second=%s%s", first, second, _suffix(context)
    )


def log_source_failure(
    reason: str, *, logger: logging.Logger | None = None, **context: Any
) -> None:
    (logger or get_logger()).warning("source ingest skipped: %s%s", reason, _suffix(context))


def log_page_failure(
    reason: str, *, logger: logging.Logger | None = None, **context: Any
) -> None:
    (logger or get_logger()).warning("page ingest rolled back: %s%s", reason, _suffix(context))


def log_contrast(counts: object, *, logger: logging.Logger | None = None) -> None:
    """Log the observable Fandom <-> Bulbapedia contrast (RF-45).

    The counts come straight from the parser output (coincident identities and
    exact windows versus identities/windows present in only one source); nothing
    is inferred or invented. They make the contrast auditable after a run.
    """
    (logger or get_logger()).info(
        "source contrast: identities_matched=%s identities_fandom_only=%s "
        "identities_bulbapedia_only=%s windows_matched=%s windows_fandom_only=%s "
        "windows_bulbapedia_only=%s",
        counts.identities_matched,
        counts.identities_fandom_only,
        counts.identities_bulbapedia_only,
        counts.windows_matched,
        counts.windows_fandom_only,
        counts.windows_bulbapedia_only,
    )
