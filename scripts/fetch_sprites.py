"""Descarga los sprites de los jefes de la base y guarda la ruta local.

Recorre la tabla ``pokemon``, resuelve la imagen de cada identidad (RF-01) con la
prioridad de la rotacion vigente (RF-02) y el repliegue al sprite del dex base
(RF-03), escribe el fichero en ``public/sprites/`` y actualiza
``pokemon.sprite_url`` con la ruta local. Un jefe sin imagen se queda en ``null``
y no impide continuar (RF-04).

La URL de la rotacion vive en ``pokemon.sprite_url`` hasta que este script la
sobrescribe, asi que se lee ANTES de escribir: es la unica copia de RF-02 y
sync_weekly la vuelve a poner en cada sincronizacion semanal.

    .venv/bin/python scripts/fetch_sprites.py
    .venv/bin/python scripts/fetch_sprites.py --force --delay 0.5

Orden del pipeline en frio: ``fetch_sprites`` -> ``export_json`` -> ``npm run
build``.
"""

import argparse
import os
from pathlib import Path

import psycopg

from raids.sprites import (
    Identity,
    build_index,
    download_sprites,
    load_catalog,
    local_sprite_url,
    resolve_local_sprite_name,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DSN = os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
DEFAULT_CATALOG = ROOT / "db" / "seeds" / "pokeapi_catalog.json"
DEFAULT_SPRITE_DIR = ROOT / "public" / "sprites"
DEFAULT_DELAY = 0.25


def boss_identities(conn) -> list[Identity]:
    """Identidades de la base, en orden estable."""
    rows = conn.execute(
        "SELECT dex_number, form, variant FROM pokemon ORDER BY dex_number, form, variant"
    ).fetchall()
    return [Identity(row[0], row[1], row[2]) for row in rows]


def rotation_images(conn) -> dict[Identity, str]:
    """URL de la rotacion por identidad, leida ANTES de sobrescribir `sprite_url`.

    Solo se acepta lo que parece una URL absoluta (http/https): una ruta local ya
    escrita por una pasada anterior no es una candidata de RF-02.
    """
    rows = conn.execute(
        "SELECT dex_number, form, variant, sprite_url FROM pokemon"
    ).fetchall()
    images: dict[Identity, str] = {}
    for dex_number, form, variant, sprite_url in rows:
        if sprite_url and sprite_url.startswith(("http://", "https://")):
            images[Identity(dex_number, form, variant)] = sprite_url
    return images


def store_sprite_urls(
    conn,
    sprite_dir: Path,
    resolved: dict[Identity, str | None] | None = None,
    *,
    catalog: dict | None = None,
) -> int:
    """Escribe en `pokemon.sprite_url` la ruta local del fichero resuelto.

    Se decide mirando el disco y no lo que se ha descargado en esta pasada, para
    que una segunda ejecucion sin red deje el snapshot igual y solo vuelva a
    arreglar lo que falte (RF-07).
    """
    updated = 0
    for identity in boss_identities(conn):
        # A run result is authoritative, including ``None``.  Falling back to a
        # stale base file here would silently undo RF-51 after a missing exact
        # resource (especially when --force is used).
        name = (
            resolved[identity]
            if resolved is not None and identity in resolved
            else resolve_local_sprite_name(identity, sprite_dir, catalog=catalog)
        )
        conn.execute(
            """
            UPDATE pokemon SET sprite_url = %s
            WHERE dex_number = %s AND form = %s AND variant = %s
            """,
            (
                local_sprite_url(name) if name else None,
                identity.dex_number,
                identity.form,
                identity.variant,
            ),
        )
        updated += 1
    return updated


def run(conn, sprite_dir, catalog, *, client=None, delay=DEFAULT_DELAY, force=False) -> dict:
    """Descarga lo que falte y deja `pokemon.sprite_url` al dia.

    `catalog` es el diccionario de PokeAPI ya cacheado (o el que sea, en tests) y
    `client` un cliente HTTP: ambos se inyectan para que el proceso sea probado
    sin red.
    """
    sprite_dir = Path(sprite_dir)
    index = build_index(catalog)
    identities = boss_identities(conn)
    # RF-02 se lee aqui, antes de que `store_sprite_urls` sobrescriba la columna.
    rotation = rotation_images(conn)

    resolved: dict[Identity, str] = {}

    def remember(identity: Identity, name: str) -> None:
        resolved[identity] = name

    stats = download_sprites(
        identities,
        index,
        sprite_dir,
        client=client,
        delay=delay,
        rotation_images=rotation,
        on_download=remember,
        force=force,
        catalog=catalog,
    )
    # ``download_sprites`` calls the callback only for successful/skipped
    # resources. Record failures explicitly so an old base PNG cannot be picked
    # up by the persistence pass.
    for identity in identities:
        resolved.setdefault(identity, None)
    stats["stored"] = store_sprite_urls(conn, sprite_dir, resolved, catalog=catalog)
    stats["total"] = len(identities)
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--sprite-dir", type=Path, default=DEFAULT_SPRITE_DIR)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    catalog = load_catalog(args.catalog)
    with psycopg.connect(args.dsn, autocommit=True) as conn:
        stats = run(
            conn,
            args.sprite_dir,
            catalog,
            delay=args.delay,
            force=args.force,
        )
        with_sprite = conn.execute(
            "SELECT count(*) FROM pokemon WHERE sprite_url IS NOT NULL"
        ).fetchone()[0]

    print(
        "sprites: "
        f"jefes={stats['total']} "
        f"descargados={stats['downloaded']} "
        f"saltados={stats['skipped']} "
        f"sin_imagen={stats['failed']} "
        f"con_sprite_url={with_sprite}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
