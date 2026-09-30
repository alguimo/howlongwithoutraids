"""Catálogo maestro e identidad derivada del nombre y del sprite.

MEGA, PRIMAL, SHADOW y APEX viven en ``variant``; las formas regionales van en
``form``. El nombre del jefe y el nombre del fichero de sprite se usan como
pistas para reconstruir la identidad.
"""

import re
from dataclasses import dataclass

from raids.identity import Identity, UnmappableIdentity, resolve_identity

VARIANT_PREFIXES = (
    ("shadow", "SHADOW"),
    ("mega", "MEGA"),
    ("primal", "PRIMAL"),
    ("apex", "APEX"),
)

FORM_ADJECTIVES = {
    "hisuian": "hisui",
    "hisui": "hisui",
    "alolan": "alola",
    "alola": "alola",
    "galarian": "galar",
    "galar": "galar",
    "paldean": "paldea",
    "paldea": "paldea",
}

PARENTHETICAL_FORMS = {
    "incarnate": "incarnate",
    "therian": "therian",
    "origin": "origin",
    "altered": "altered",
    "disguised": "disguised",
    "hero of many battles": "hero-of-many-battles",
}

IMAGE_FORM_CODES = {
    "HISUIAN": "hisui",
    "ALOLA": "alola",
    "GALAR": "galar",
    "PALDEA": "paldea",
    "INCARNATE": "incarnate",
    "ORIGIN": "origin",
    "ALTERED": "altered",
    "THERIAN": "therian",
    "DISGUISED": "disguised",
}

IMAGE_VARIANT_CODES = {"MEGA": "MEGA", "PRIMAL": "PRIMAL", "SHADOW": "SHADOW", "APEX": "APEX"}

_DEX_PM = re.compile(r"pm(\d+)\.", re.IGNORECASE)
_DEX_ICON = re.compile(r"pokemon_icon_(\d+)_")
_IMAGE_FORM = re.compile(r"\.f([A-Z]+)\.", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\(([^)]+)\)\s*$")


@dataclass(frozen=True)
class CatalogEntry:
    identity: Identity
    name: str
    types: tuple[str, ...]
    sprite_url: str | None


@dataclass(frozen=True)
class Resolved:
    identity: Identity
    types: tuple[str, ...]
    sprite_url: str | None


def parse_catalog(payload) -> list[CatalogEntry]:
    entries = []
    for item in payload:
        identity = resolve_identity(
            item["dex_number"], item.get("form", "normal"), item.get("variant", "NORMAL")
        )
        entries.append(
            CatalogEntry(
                identity=identity,
                name=str(item["name"]),
                types=tuple(item.get("types", ())),
                sprite_url=item.get("sprite_url") or item.get("image"),
            )
        )
    return entries


def parse_boss_name(name) -> tuple[str, str, str]:
    text = str(name).strip()
    variant = "NORMAL"
    form = "normal"
    lowered = text.lower()

    for prefix, value in VARIANT_PREFIXES:
        if lowered.startswith(prefix + " "):
            variant = value
            text = text[len(prefix) + 1 :].strip()
            lowered = text.lower()
            break

    for adjective, value in FORM_ADJECTIVES.items():
        if lowered.startswith(adjective + " "):
            form = value
            text = text[len(adjective) + 1 :].strip()
            lowered = text.lower()
            break

    match = _PARENTHETICAL.search(text)
    if match:
        key = match.group(1).strip().lower()
        if key in PARENTHETICAL_FORMS:
            form = PARENTHETICAL_FORMS[key]
        text = text[: match.start()].strip()

    return text.strip(), variant, form


def dex_from_image(image) -> int | None:
    if not image:
        return None
    match = _DEX_PM.search(image)
    if match:
        return int(match.group(1))
    match = _DEX_ICON.search(image)
    if match:
        return int(match.group(1))
    return None


def form_variant_from_image(image) -> tuple[str | None, str | None]:
    if not image:
        return None, None
    match = _IMAGE_FORM.search(image)
    if match:
        code = match.group(1).upper()
        if code in IMAGE_VARIANT_CODES:
            return None, IMAGE_VARIANT_CODES[code]
        return IMAGE_FORM_CODES.get(code, code.lower()), None
    return None, None


def identity_from_boss(name, image=None) -> Identity | None:
    dex_number = dex_from_image(image)
    if dex_number is None:
        return None

    _, variant, form = parse_boss_name(name)
    image_form, image_variant = form_variant_from_image(image)
    if form == "normal" and image_form:
        form = image_form
    if variant == "NORMAL" and image_variant:
        variant = image_variant

    return resolve_identity(dex_number, form, variant)


class Catalog:
    def __init__(self, entries):
        self._by_name: dict[str, CatalogEntry] = {}
        for entry in entries:
            self._by_name.setdefault(entry.name.strip().lower(), entry)

    @classmethod
    def from_conn(cls, conn) -> "Catalog":
        rows = conn.execute(
            "SELECT dex_number, form, variant, name, types, sprite_url FROM pokemon"
        ).fetchall()
        entries = [
            CatalogEntry(Identity(row[0], row[1], row[2]), row[3], tuple(row[4]), row[5])
            for row in rows
        ]
        return cls(entries)

    def resolve(self, boss_name) -> Resolved | None:
        base, variant, form = parse_boss_name(boss_name)
        entry = self._by_name.get(base.strip().lower())
        if entry is None:
            return None

        if form == "normal":
            form = entry.identity.form
        if variant == "NORMAL":
            variant = entry.identity.variant

        try:
            identity = resolve_identity(entry.identity.dex_number, form, variant)
        except UnmappableIdentity:
            return None
        return Resolved(identity=identity, types=entry.types, sprite_url=entry.sprite_url)
