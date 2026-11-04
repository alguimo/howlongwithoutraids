"""Genera ``src/data/raids-snapshot.json``.

Orquesta construir, validar y escribir. Un snapshot vacío o inválido no pisa el
artefacto anterior.
"""

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from raids.export import (
    build_snapshot,
    build_snapshot_meta,
    write_snapshot,
    write_snapshot_meta,
)
from raids.validate import validate_snapshot, validate_snapshot_meta

DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "raids-snapshot.json"


def run(
    conn,
    path,
    *,
    as_of: datetime,
    meta_path: Path | None = None,
    logger=None,
) -> bool:
    rows = build_snapshot(conn, as_of=as_of)
    meta = build_snapshot_meta(as_of)
    validate_snapshot(rows)
    validate_snapshot_meta(meta)
    written = write_snapshot(path, rows, logger=logger)
    if written:
        target_meta = (
            Path(meta_path)
            if meta_path is not None
            else Path(path).with_name("snapshot-meta.json")
        )
        write_snapshot_meta(target_meta, meta)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--meta-out", type=Path, default=None)
    args = parser.parse_args(argv)

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        written = run(
            conn,
            args.out,
            as_of=datetime.now(timezone.utc),
            meta_path=args.meta_out,
        )
    print(f"snapshot written: {written}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
