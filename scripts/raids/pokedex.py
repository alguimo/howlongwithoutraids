"""Catálogo maestro e identidad derivada del nombre y del sprite.

MEGA, PRIMAL, SHADOW y APEX viven en ``variant``; las formas regionales van en
``form``. El nombre del jefe y el nombre del fichero de sprite se usan como
pistas para reconstruir la identidad.
"""

import re
import unicodedata
from dataclasses import dataclass

from raids.forms import match_pokeapi_form
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

_APOSTROPHES = re.compile(r"['\u2019\u02bc`\u00b4]")
_SEPARATORS = re.compile(r"[\s.]+")
_NON_KEY_CHARS = re.compile(r"[^a-z0-9-]+")
_REPEATED_HYPHENS = re.compile(r"-+")


def normalize_name_key(name: object) -> str:
    """Canonical lookup key shared by catalog names and Fandom boss names.

    Fandom and PokeAPI spell the same species differently (``Ho-Oh``/``Ho Oh``,
    ``Farfetch'd``/``Farfetchd``, ``Mr. Mime``/``Mr Mime``, ``Nidoran♀``/
    ``Nidoran F``, ``Jangmo-o``/``Jangmo O``, ``Flabébé``/``Flabebe``). Both
    sides are folded to the same slug: case and accents dropped, apostrophes
    removed, gender symbols and separators turned into hyphens.
    """
    text = unicodedata.normalize("NFKD", str(name).strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("♀", "-f").replace("♂", "-m")
    text = _APOSTROPHES.sub("", text)
    text = _SEPARATORS.sub("-", text)
    text = _NON_KEY_CHARS.sub("", text)
    return _REPEATED_HYPHENS.sub("-", text).strip("-")


def _suffixed_default_base(
    form_name: str, species: dict, form_id: object
) -> int | None:
    """Dex when ``form_name`` is a species' suffixed default form (RF-46).

    PokeAPI writes the default form with a suffix when the species has no plain
    entry (``xerneas-active``, ``burmy-plant``). The default is the form whose
    numeric id equals the species dex; a non-default form (``burmy-sandy``)
    keeps a different id and must not collapse to the base. Returns ``None`` for
    every other shape, including when the catalog record has no id.
    """
    try:
        numeric_id = int(form_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    parts = form_name.split("-")
    while len(parts) > 1:
        parts.pop()
        dex = species.get("-".join(parts))
        if dex is not None and int(dex) == numeric_id:
            return int(dex)
    return None


# RF-40: categorias de especie que PokeAPI expone en `/pokemon-species/{id}`.
SPECIES_CATEGORY_FIELDS = ("is_legendary", "is_mythical", "is_baby")

# RF-41: lista canonica, explicita y versionada de Ultraentes por numero de dex.
# PokeAPI no expone ninguna marca de Ultraente, asi que `is_ultra_beast` es la
# excepcion aprobada y versionada al principio 13. Anadir un dex es un cambio de
# spec: la lista es un dato de la franquicia, no una inferencia.
ULTRA_BEASTS = frozenset({793, 794, 795, 796, 797, 798, 799, 803, 804, 805, 806})


def read_species_categories(source: dict | None = None) -> dict[str, bool | None]:
    """Lee las tres categorias con estricta fidelidad a la fuente (RF-40).

    Devuelve ``True``/``False`` solo cuando la fuente responde ese booleano; un
    campo ausente o un valor que no sea booleano da ``None``. Nunca ``false``
    por defecto.
    """
    source = source if isinstance(source, dict) else {}
    categories: dict[str, bool | None] = {}
    for field in SPECIES_CATEGORY_FIELDS:
        raw = source.get(field)
        categories[field] = raw if isinstance(raw, bool) else None
    return categories


def is_ultra_beast(dex_number: int) -> bool:
    """``True`` si el dex esta en la lista canonica; siempre conocido (RF-41)."""
    return int(dex_number) in ULTRA_BEASTS


@dataclass(frozen=True)
class CatalogEntry:
    identity: Identity
    name: str
    types: tuple[str, ...]
    sprite_url: str | None
    is_legendary: bool | None = None
    is_mythical: bool | None = None
    is_baby: bool | None = None


@dataclass(frozen=True)
class Resolved:
    identity: Identity
    types: tuple[str, ...]
    sprite_url: str | None
    is_legendary: bool | None = None
    is_mythical: bool | None = None
    is_baby: bool | None = None


def parse_catalog(payload) -> list[CatalogEntry]:
    if isinstance(payload, dict) and "forms" in payload:
        entries = []
        species = payload.get("species", {})
        categories_by_dex = payload.get("species_categories", {})
        for form_name, raw in payload["forms"].items():
            record = raw if isinstance(raw, dict) else {"id": raw}
            dex_number, form, variant = _catalog_form_identity(
                form_name, species, record.get("id")
            )
            if dex_number is None:
                continue
            categories = read_species_categories(_categories_for_dex(categories_by_dex, dex_number))
            entries.append(
                CatalogEntry(
                    identity=resolve_identity(dex_number, form, variant),
                    name=_catalog_display_name(form_name, species),
                    types=tuple(record.get("types", ())),
                    sprite_url=record.get("sprite_url"),
                    **categories,
                )
            )
        return entries

    entries = []
    for item in payload:
        identity = resolve_identity(
            item["dex_number"], item.get("form", "normal"), item.get("variant", "NORMAL")
        )
        categories = read_species_categories(item)
        entries.append(
            CatalogEntry(
                identity=identity,
                name=str(item["name"]),
                types=tuple(item.get("types", ())),
                sprite_url=item.get("sprite_url") or item.get("image"),
                **categories,
            )
        )
    return entries


def _categories_for_dex(categories_by_dex: dict, dex_number: int) -> dict:
    """Busca la entrada de una especie, aceptando claves int o string (JSON)."""
    if not isinstance(categories_by_dex, dict):
        return {}
    record = categories_by_dex.get(dex_number)
    if record is None:
        record = categories_by_dex.get(str(dex_number))
    return record if isinstance(record, dict) else {}


def _catalog_form_identity(
    form_name: str, species: dict, form_id: object = None
) -> tuple[int | None, str, str]:
    parts = form_name.split("-")
    if "mega" in parts:
        base = "-".join(parts[: parts.index("mega")])
        if base in species:
            return int(species[base]), "normal", "MEGA"
    # RF-46: taxonomia ampliada compartida con el resolutor de sprites.
    expanded = match_pokeapi_form(form_name, species)
    if expanded is not None:
        dex, form = expanded
        return dex, form, "NORMAL"
    for suffix, form in (
        ("alola", "alola"), ("galar", "galar"), ("hisui", "hisui"),
        ("paldea", "paldea"), ("origin", "origin"), ("altered", "altered"),
        ("incarnate", "incarnate"), ("therian", "therian"),
        ("disguised", "disguised"), ("hero-of-many-battles", "hero-of-many-battles"),
    ):
        marker = f"-{suffix}"
        if form_name.endswith(marker) and form_name[:-len(marker)] in species:
            return int(species[form_name[:-len(marker)]]), form, "NORMAL"
    # Forma por defecto con sufijo: la especie no tiene entrada plana y PokeAPI
    # nombra su forma base ``<especie>-<sufijo>`` (``xerneas-active``). El id
    # identifica la forma por defecto y evita colapsar las demas.
    default_dex = _suffixed_default_base(form_name, species, form_id)
    if default_dex is not None:
        return default_dex, "normal", "NORMAL"
    if form_name in species:
        return int(species[form_name]), "normal", "NORMAL"
    return None, "normal", "NORMAL"


def _catalog_display_name(form_name: str, species: dict) -> str:
    base = form_name.split("-mega")[0]
    for name in species:
        if form_name == name or form_name.startswith(name + "-"):
            base = name
            break
    return base.replace("-", " ").title()


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
            self._by_name.setdefault(normalize_name_key(entry.name), entry)

    @classmethod
    def from_conn(cls, conn) -> "Catalog":
        rows = conn.execute(
            """
            SELECT dex_number, form, variant, name, types, sprite_url,
                   is_legendary, is_mythical, is_baby
            FROM pokemon
            """
        ).fetchall()
        entries = [
            CatalogEntry(
                Identity(row[0], row[1], row[2]),
                row[3],
                tuple(row[4]),
                row[5],
                is_legendary=row[6],
                is_mythical=row[7],
                is_baby=row[8],
            )
            for row in rows
        ]
        return cls(entries)

    def resolve(self, boss_name) -> Resolved | None:
        base, variant, form = parse_boss_name(boss_name)
        key = normalize_name_key(base)
        entry = self._by_name.get(key)
        # ScrapedDuck labels Charizard's two mega forms as "Mega Charizard X/Y",
        # while the identity model deliberately collapses them to MEGA.
        if entry is None and variant == "MEGA" and key.endswith(("-x", "-y")):
            entry = self._by_name.get(key[:-2])
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
        return Resolved(
            identity=identity,
            types=entry.types,
            sprite_url=entry.sprite_url,
            is_legendary=entry.is_legendary,
            is_mythical=entry.is_mythical,
            is_baby=entry.is_baby,
        )
