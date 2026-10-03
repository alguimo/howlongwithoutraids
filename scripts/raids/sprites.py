"""Sprites desde PokeAPI.

El pipeline resuelve la imagen y guarda una ruta local en
``pokemon.sprite_url``. La UI solo pinta lo que le llega en el snapshot.

PokeAPI no tiene sprites de Shadow, asi que un jefe sombra cae al sprite de su
forma base, que es lo mejor disponible sin inventar nada.

Las formas de PokeAPI se nombran con SUFIJO: ``sandslash-alola``, ``wooper-paldea``,
``giratina-origin``, ``charizard-mega-x``. Nunca con prefijo. El sufijo a interpretar
es el ultimo segmento tras el ultimo guion, asi que un nombre compuesto como
``raticate-totem-alola`` sigue siendo una forma regional de ``raticate``.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
FORM_URL = "https://pokeapi.co/api/v2/pokemon-form?limit=2000"
USER_AGENT = "howlongwithoutraids/0.1 (local ETL; +https://github.com/alguimo/howlongwithoutraids)"

# Sufijos de PokeAPI -> nuestro slug de `form`. El sufijo se busca al final del
# nombre, nunca al principio.
FORM_SUFFIXES = {
    "alola": "alola",
    "galar": "galar",
    "hisui": "hisui",
    "paldea": "paldea",
    "origin": "origin",
    "altered": "altered",
    "incarnate": "incarnate",
    "therian": "therian",
    "disguised": "disguised",
    "hero-of-many-battles": "hero-of-many-battles",
    "eternamax": "eternamax",
}

# `shadow` no entra a proposito: no es una forma de nuestra identidad, asi que
# `calyrex-shadow` cae a la especie base por el fallback de resolve_sprite_id.

# Los sufijos mas largos primero: `hero-of-many-battles` gana a cualquier coincidencia
# parcial de sus segmentos intermedios.
FORM_SUFFIXES_BY_LENGTH = sorted(FORM_SUFFIXES, key=len, reverse=True)


class SpriteError(RuntimeError):
    """No se pudo resolver ni descargar un sprite."""


@dataclass(frozen=True)
class Identity:
    dex_number: int
    form: str
    variant: str


def sprite_key(identity: Identity) -> str:
    """Nombre estable y derivado de la identidad. Cambia la cache del navegador."""
    key = str(identity.dex_number)
    if identity.form and identity.form != "normal":
        key += f"-{identity.form}"
    if identity.variant and identity.variant != "NORMAL":
        key += f"-{identity.variant.lower()}"
    return key


def _index_from_listing(payload: dict) -> dict[str, int]:
    """Convierte un listado de PokeAPI en {nombre: id}."""
    index: dict[str, int] = {}
    for result in payload.get("results", []):
        index[result["name"]] = int(result["url"].rstrip("/").split("/")[-1])
    return index


def load_catalog(cache_path: Path, *, client: httpx.Client | None = None) -> dict:
    """Descarga el catalogo de especies y formas una vez y lo cachea en disco."""
    cache_path = Path(cache_path)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    owns_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
    )
    try:
        species = _index_from_listing(client.get(SPECIES_URL).json())
        forms = _index_from_listing(client.get(FORM_URL).json())
    finally:
        if owns_client:
            client.close()

    catalog = {"species": species, "forms": forms}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return catalog


def build_index(catalog: dict) -> dict[tuple[int, str, str], int]:
    """Construye {(dex, form, variant): sprite_id} a partir del catalogo."""
    species_by_name: dict[str, int] = catalog["species"]

    index: dict[tuple[int, str, str], int] = {}
    for form_name, form_id in catalog["forms"].items():
        dex, form, variant = _match_form(form_name, species_by_name)
        if dex is None:
            continue
        # Un mismo nombre puede repetirse; el primero gana.
        index.setdefault((dex, form, variant), form_id)
    return index


def _lookup_species(name: str, species_by_name: dict[str, int]) -> int | None:
    """Busca una especie por nombre, probando tambien nombres mas cortos.

    Asi ``raticate-totem-alola`` (ya sin el sufijo) y ``deoxys-attack`` caen a
    ``raticate`` y ``deoxys`` cuando el nombre completo no es una especie.
    """
    parts = name.split("-")
    while parts:
        dex = species_by_name.get("-".join(parts))
        if dex is not None:
            return dex
        parts.pop()
    return None


def _match_form(form_name: str, species_by_name: dict[str, int]) -> tuple:
    """Traduce un nombre de forma de PokeAPI a (dex, form, variant)."""
    # Mega es una variante, no una forma: el sprite va en `variant`.
    # PokeAPI escribe `charizard-mega`, `charizard-mega-x`, `beedrill-mega`.
    parts = form_name.split("-")
    if "mega" in parts:
        before = parts[: parts.index("mega")]
        dex = _lookup_species("-".join(before), species_by_name) if before else None
        if dex is not None:
            # PokeAPI distingue mega X e Y con un sufijo que nuestro modelo no
            # guarda; colapsamos ambos en la misma identidad.
            return dex, "normal", "MEGA"

    for suffix in FORM_SUFFIXES_BY_LENGTH:
        marker = f"-{suffix}"
        if form_name.endswith(marker):
            dex = _lookup_species(form_name[: -len(marker)], species_by_name)
            if dex is not None:
                return dex, FORM_SUFFIXES[suffix], "NORMAL"

    # Forma base: el nombre de la especie a secas, o una variante que no modelamos
    # (cosplay, gmax, attack/defense...) y que cae a la especie base.
    dex = _lookup_species(form_name, species_by_name)
    if dex is not None:
        return dex, "normal", "NORMAL"
    return None, "normal", "NORMAL"


def resolve_sprite_id(index: dict, identity: Identity) -> int:
    """Devuelve el id de sprite para la identidad, con caida al dex base."""
    exact = index.get((identity.dex_number, identity.form, identity.variant))
    if exact is not None:
        return exact
    base = index.get((identity.dex_number, "normal", "NORMAL"))
    if base is not None:
        return base
    return identity.dex_number


def sprite_url(identity: Identity, index: dict) -> str:
    return f"{SPRITE_BASE}/{resolve_sprite_id(index, identity)}.png"


def download_sprites(
    identities: list[Identity],
    index: dict,
    out_dir: Path,
    *,
    client: httpx.Client | None = None,
    delay: float = 0.2,
    on_download=None,
) -> dict[str, int]:
    """Descarga en orden y de una en una. Salta lo ya descargado y para si falla."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    owns_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
    )
    try:
        for identity in identities:
            key = sprite_key(identity)
            target = out_dir / f"{key}.png"
            if target.exists():
                stats["skipped"] += 1
                continue
            url = sprite_url(identity, index)
            try:
                response = client.get(url)
            except Exception as exc:
                raise SpriteError(f"descarga abortada en {url}: {exc}") from exc
            if response.status_code != 200:
                stats["failed"] += 1
                continue
            target.write_bytes(response.content)
            stats["downloaded"] += 1
            if on_download:
                on_download(identity, key)
            time.sleep(delay)
    finally:
        if owns_client:
            client.close()

    return stats
