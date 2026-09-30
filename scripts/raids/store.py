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
from raids.log import log_displaced, log_source_failure


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


def upsert_pokemon(
    conn: psycopg.Connection,
    identity: Identity,
    *,
    name: str,
    types: Iterable[str] = (),
    sprite_url: str | None = None,
) -> int:
    row = conn.execute(
        """
        INSERT INTO pokemon (dex_number, form, variant, name, types, sprite_url)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (dex_number, form, variant) DO UPDATE
          SET name = EXCLUDED.name,
              types = EXCLUDED.types,
              sprite_url = EXCLUDED.sprite_url
        RETURNING id
        """,
        (
            identity.dex_number,
            identity.form,
            identity.variant,
            name,
            list(types),
            sprite_url,
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
    published_at: datetime | None = None,
    logger=None,
) -> str:
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
                published_at = COALESCE(%s, now())
            WHERE id = %s
            """,
            (tier, start, end, is_special_event, published_at, keep_id),
        )
        extra_ids = [row[0] for row in overlapping[1:]]
        if extra_ids:
            conn.execute("DELETE FROM raid_appearances WHERE id = ANY(%s)", (extra_ids,))
        return "replaced"

    conn.execute(
        """
        INSERT INTO raid_appearances
            (pokemon_id, tier, start_date, end_date, is_special_event, source, published_at)
        VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
        """,
        (pokemon_id, tier, start, end, is_special_event, source, published_at),
    )
    return "inserted"


def store_records(
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
            logger=logger,
        )
        written += 1
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

    return store_records(conn, records, logger=logger)
