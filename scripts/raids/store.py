"""Persistencia de apariciones.

Escribe por fuente y nunca borra por ausencia: una sincronización que no trae a
un jefe no toca su ventana guardada. Si la fuente falla, el pipeline no llama
aquí y lo almacenado queda intacto.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

import psycopg

from raids.identity import Identity
from raids.intervals import Origin
from raids.log import log_displaced, log_overlap, log_page_failure, log_source_failure
from raids.pokedex import is_ultra_beast


@dataclass(frozen=True)
class AppearanceRecord:
    identity: Identity
    name: str
    types: tuple[str, ...]
    sprite_url: str | None
    tier: str
    start: datetime
    end: datetime
    source: str
    is_special_event: bool = False
    is_local_time: bool = False
    page_title: str | None = None
    page_kind: str | None = None
    event_name: str | None = None
    # A consolidated record can carry every page that contributed to it (RF-30,
    # RF-36). Single-origin callers keep using source/page_title/page_kind.
    origins: tuple[Origin, ...] = ()


def clean_event_name(value: str | None) -> str | None:
    """Normalize an event name: a blank string is not a valid event (RF-42, RF-43).

    The schema rejects empty and whitespace-only names, so an undeterminable
    name travels as ``None`` instead of an empty string.
    """
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def upsert_pokemon(
    conn: psycopg.Connection,
    identity: Identity,
    *,
    name: str,
    types: Iterable[str] = (),
    sprite_url: str | None = None,
    is_legendary: bool | None = None,
    is_mythical: bool | None = None,
    is_baby: bool | None = None,
    update_categories: bool = False,
) -> int:
    """Insert or update a pokemon row.

    The three PokeAPI species categories (RF-40) are written on insert. On
    conflict they are only overwritten when ``update_categories`` is set, so an
    appearance ingestion (which carries no categories) never wipes the catalog
    values with a default ``NULL``. ``is_ultra_beast`` is always derived from the
    canonical dex list (RF-41) and is therefore always safe to refresh.
    """
    category_updates = ""
    if update_categories:
        category_updates = (
            "is_legendary = EXCLUDED.is_legendary, "
            "is_mythical = EXCLUDED.is_mythical, "
            "is_baby = EXCLUDED.is_baby, "
        )
    row = conn.execute(
        f"""
        INSERT INTO pokemon (
            dex_number, form, variant, name, types, sprite_url,
            is_legendary, is_mythical, is_baby, is_ultra_beast
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (dex_number, form, variant) DO UPDATE
          SET name = EXCLUDED.name,
              types = CASE
                  WHEN cardinality(EXCLUDED.types) > 0 THEN EXCLUDED.types
                  ELSE pokemon.types
              END,
              sprite_url = COALESCE(EXCLUDED.sprite_url, pokemon.sprite_url),
              {category_updates}is_ultra_beast = EXCLUDED.is_ultra_beast
        RETURNING id
        """,
        (
            identity.dex_number,
            identity.form,
            identity.variant,
            name,
            list(types),
            sprite_url,
            is_legendary,
            is_mythical,
            is_baby,
            is_ultra_beast(identity.dex_number),
        ),
    ).fetchone()
    return row[0]


def count_appearances(conn: psycopg.Connection, pokemon_id: int) -> int:
    return conn.execute(
        "SELECT count(*) FROM raid_appearances WHERE pokemon_id = %s", (pokemon_id,)
    ).fetchone()[0]


def record_appearance(
    conn: psycopg.Connection,
    pokemon_id: int,
    *,
    tier: str,
    start: datetime,
    end: datetime,
    source: str,
    is_special_event: bool = False,
    is_local_time: bool = False,
    published_at: datetime | None = None,
    page_title: str | None = None,
    page_kind: str | None = None,
    event_name: str | None = None,
    origins: tuple[Origin, ...] | None = None,
    logger=None,
) -> str:
    event_name = clean_event_name(event_name)
    origins = _resolve_origins(source, page_title, page_kind, origins)

    # RF-36: an exact window already stored, even from another source, is the
    # same appearance. Keep one row and attach every origin instead of
    # duplicating the count.
    exact = conn.execute(
        """
        SELECT id, source
        FROM raid_appearances
        WHERE pokemon_id = %s
          AND start_date = %s
          AND end_date = %s
        ORDER BY id
        LIMIT 1
        """,
        (pokemon_id, start, end),
    ).fetchone()
    if exact is not None and exact[1] != source:
        keep_id = exact[0]
        conn.execute(
            """
            UPDATE raid_appearances
            SET tier = %s,
                -- Exact-window deduplication merges facts from both sources:
                -- an absent optional value must not erase one already known.
                is_special_event = is_special_event OR %s,
                event_name = COALESCE(%s, event_name),
                published_at = COALESCE(%s, now())
            WHERE id = %s
            """,
            (tier, is_special_event, event_name, published_at, keep_id),
        )
        _record_origins(conn, keep_id, origins)
        return "deduplicated"

    overlapping = conn.execute(
        """
        SELECT id, start_date, end_date
        FROM raid_appearances
        WHERE pokemon_id = %s
          AND source = %s
          AND start_date < %s
          AND end_date > %s
        ORDER BY start_date, id
        """,
        (pokemon_id, source, end, start),
    ).fetchall()

    if overlapping:
        keep_id, previous_start, previous_end = overlapping[0]
        if (previous_start, previous_end) != (start, end):
            log_displaced(
                f"{previous_start.isoformat()}/{previous_end.isoformat()}",
                f"{start.isoformat()}/{end.isoformat()}",
                logger=logger,
                pokemon_id=pokemon_id,
                source=source,
            )
        conn.execute(
            """
            UPDATE raid_appearances
            SET tier = %s,
                start_date = %s,
                end_date = %s,
                is_special_event = %s,
                is_local_time = %s,
                event_name = %s,
                published_at = COALESCE(%s, now())
            WHERE id = %s
            """,
            (tier, start, end, is_special_event, is_local_time, event_name, published_at, keep_id),
        )
        extra_ids = [row[0] for row in overlapping[1:]]
        if extra_ids:
            conn.execute("DELETE FROM raid_appearances WHERE id = ANY(%s)", (extra_ids,))
        _record_origins(conn, keep_id, origins)
        return "replaced"

    # RF-36: an overlap from another source that is not identical is a distinct
    # appearance. Keep it separate and log the overlap; never merge it or
    # invent a window no source published.
    for other_source, other_start, other_end in conn.execute(
        """
        SELECT source, start_date, end_date
        FROM raid_appearances
        WHERE pokemon_id = %s
          AND source <> %s
          AND start_date < %s
          AND end_date > %s
        ORDER BY start_date, id
        """,
        (pokemon_id, source, end, start),
    ).fetchall():
        log_overlap(
            f"{other_start.isoformat()}/{other_end.isoformat()}",
            f"{start.isoformat()}/{end.isoformat()}",
            logger=logger,
            pokemon_id=pokemon_id,
            source=other_source,
        )

    appearance_id = conn.execute(
        """
        INSERT INTO raid_appearances
            (pokemon_id, tier, start_date, end_date, is_special_event, is_local_time, source, event_name, published_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
        RETURNING id
        """,
        (pokemon_id, tier, start, end, is_special_event, is_local_time, source, event_name, published_at),
    ).fetchone()[0]
    _record_origins(conn, appearance_id, origins)
    return "inserted"


def _resolve_origins(
    source: str,
    page_title: str | None,
    page_kind: str | None,
    origins: tuple[Origin, ...] | None,
) -> tuple[Origin, ...]:
    """Return the record origins, falling back to the single legacy origin."""
    if origins:
        return tuple(dict.fromkeys(origins))
    if page_title is None and page_kind is None:
        return ()
    if not page_title or not page_kind:
        raise ValueError("page_title and page_kind must be supplied together")
    return (Origin(source, page_title, page_kind),)


def _record_origins(
    conn: psycopg.Connection,
    appearance_id: int,
    origins: tuple[Origin, ...],
) -> None:
    """Attach every source document without changing the canonical source."""
    for origin in origins:
        conn.execute(
            """
            INSERT INTO raid_appearance_origins (appearance_id, source, page_title, page_kind)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (appearance_id, source, page_title) DO NOTHING
            """,
            (appearance_id, origin.source, origin.page_title, origin.page_kind),
        )


def _store_records(
    conn: psycopg.Connection,
    records: Iterable[AppearanceRecord],
    *,
    logger=None,
) -> int:
    written = 0
    for record in records:
        pokemon_id = upsert_pokemon(
            conn,
            record.identity,
            name=record.name,
            types=record.types,
            sprite_url=record.sprite_url,
        )
        record_appearance(
            conn,
            pokemon_id,
            tier=record.tier,
            start=record.start,
            end=record.end,
            source=record.source,
            is_special_event=record.is_special_event,
            is_local_time=record.is_local_time,
            page_title=record.page_title,
            page_kind=record.page_kind,
            event_name=record.event_name,
            origins=record.origins or None,
            logger=logger,
        )
        written += 1
    return written


def store_records(
    conn: psycopg.Connection,
    records: Iterable[AppearanceRecord],
    *,
    logger=None,
) -> int:
    """Write a record batch atomically."""
    with conn.transaction():
        return _store_records(conn, records, logger=logger)


def store_page(
    conn: psycopg.Connection,
    records: Iterable[AppearanceRecord],
    *,
    logger=None,
) -> int:
    """Write one already parsed page atomically.

    The caller decides whether a page is absent or failed before calling this
    function.  Any exception raised while writing rolls back the page, including
    its pokemon and origin rows, and is deliberately allowed to propagate so an
    orchestrator can continue with another page.
    """
    with conn.transaction():
        return _store_records(conn, records, logger=logger)


def store_pages(
    conn: psycopg.Connection,
    pages: Iterable[Iterable[AppearanceRecord]],
    *,
    logger=None,
) -> int:
    """Persist pages independently, keeping valid pages after a page failure."""
    written = 0
    for records in pages:
        try:
            written += store_page(conn, records, logger=logger)
        except Exception as exc:
            log_page_failure(str(exc), logger=logger)
    return written


def ingest(
    conn: psycopg.Connection,
    fetch: Callable[[], object],
    build_records: Callable[[object], Iterable[AppearanceRecord]],
    *,
    logger=None,
) -> int:
    try:
        payload = fetch()
        records = list(build_records(payload))
    except Exception as exc:
        log_source_failure(str(exc), logger=logger)
        return 0

    return store_page(conn, records, logger=logger)
