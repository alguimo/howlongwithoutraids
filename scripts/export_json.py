"""Genera ``src/data/raids-snapshot.json``.

Orquesta construir, validar y escribir. Un snapshot vacío o inválido no pisa el
artefacto anterior.
"""

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from raids.export import build_snapshot, write_snapshot
from raids.validate import validate_snapshot

DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "raids-snapshot.json"


def run(conn, path, *, as_of: datetime, logger=None) -> bool:
    rows = build_snapshot(conn, as_of=as_of)
    validate_snapshot(rows)
    return write_snapshot(path, rows, logger=logger)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        written = run(conn, args.out, as_of=datetime.now(timezone.utc))
    print(f"snapshot written: {written}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
