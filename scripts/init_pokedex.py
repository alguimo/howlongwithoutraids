"""Carga el catálogo maestro de Pokémon en la tabla ``pokemon``.

El adaptador de red (PoGoAPI / PokéAPI) queda inyectado: la CLI lee por defecto
un fichero local de datos maestros.
"""

import argparse
import json
import os
from pathlib import Path

import psycopg

from raids.pokedex import parse_catalog
from raids.store import upsert_pokemon

DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "db" / "seeds" / "pokedex.json"


def run(conn, fetch_catalog) -> int:
    entries = parse_catalog(fetch_catalog())
    for entry in entries:
        upsert_pokemon(
            conn,
            entry.identity,
            name=entry.name,
            types=entry.types,
            sprite_url=entry.sprite_url,
        )
    return len(entries)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args(argv)

    def fetch_catalog():
        return json.loads(args.catalog.read_text(encoding="utf-8"))

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        written = run(conn, fetch_catalog)
    print(f"catalog entries: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
