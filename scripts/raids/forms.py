"""Taxonomía ampliada de formas de Fandom (RF-20, RF-29, RF-44, RF-46).

Tabla verificada ``origen -> slug`` de la decisión cerrada de la spec. El parser
de Fandom la usa para resolver ``ci=``/``ct=`` (T23); el catálogo y el resolutor
de sprites la reutilizarán para construir la identidad y el nombre de forma de
PokeAPI (T24), de modo que identidad e imagen no diverjan.

Un valor fuera de esta tabla, del catálogo o de la lista cosmética se omite y se
registra (RF-20). Los clones y formas no listadas (``Hoopa unbound``,
``Necrozma ultra``, ``Tatsugiri-*-mega``…) no entran.
"""

from __future__ import annotations

import re

# Ordered ``(origin marker, slug)``; matched against the lowercased hint text
# with alphanumeric boundaries, most specific first. Multi-word markers let the
# source spell a form either as ``Genesect burn`` or ``Burn Drive Genesect``.
EXPANDED_FORM_MARKERS: tuple[tuple[str, str], ...] = (
    # Deoxys (base stays ``normal`` because it carries no hint).
    ("deoxys attack", "attack"),
    ("deoxys defense", "defense"),
    ("deoxys speed", "speed"),
    # Genesect
    ("genesect burn", "burn-drive"),
    ("burn drive", "burn-drive"),
    ("genesect chill", "chill-drive"),
    ("chill drive", "chill-drive"),
    ("genesect douse", "douse-drive"),
    ("douse drive", "douse-drive"),
    ("genesect shock", "shock-drive"),
    ("shock drive", "shock-drive"),
    # Tauros de Paldea
    ("paldea combat", "paldea-combat"),
    ("combat breed", "paldea-combat"),
    ("tauros combat", "paldea-combat"),
    ("paldea blaze", "paldea-blaze"),
    ("blaze breed", "paldea-blaze"),
    ("tauros blaze", "paldea-blaze"),
    ("paldea aqua", "paldea-aqua"),
    ("aqua breed", "paldea-aqua"),
    ("tauros aqua", "paldea-aqua"),
    # Necrozma
    ("necrozma dusk mane", "dusk-mane"),
    ("dusk mane", "dusk-mane"),
    ("necrozma dawn wings", "dawn-wings"),
    ("dawn wings", "dawn-wings"),
    # Zacian / Zamazenta (``crown`` cosmetic is a different, listed marker).
    ("crowned", "crowned"),
    # Tatsugiri
    ("tatsugiri curly", "curly"),
    ("curly tatsugiri", "curly"),
    ("tatsugiri droopy", "droopy"),
    ("droopy tatsugiri", "droopy"),
    ("tatsugiri stretchy", "stretchy"),
    ("stretchy tatsugiri", "stretchy"),
    # Shellos
    ("shellos east", "east"),
    ("east sea", "east"),
    ("shellos west", "west"),
    ("west sea", "west"),
)

# Unown is anchored to the ``unown`` species (RF-46): a bare ``-<letter>`` suffix
# must never match, so ``porygon-z``/``nidoran-f``/``jangmo-o`` cannot collide.
_UNOWN_LETTER = re.compile(r"(?<![a-z0-9])unown[\s-]+([a-z])(?![a-z0-9])")
_UNOWN_PUNCTUATION = re.compile(r"(?<![a-z0-9])unown[\s-]*([!?])")
_UNOWN_PUNCTUATION_SLUGS = {"!": "exclamation", "?": "question"}


def _contains_marker(text: str, marker: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _resolve_unown(text: str) -> str | None:
    match = _UNOWN_LETTER.search(text)
    if match is not None:
        return match.group(1)
    match = _UNOWN_PUNCTUATION.search(text)
    if match is not None:
        return _UNOWN_PUNCTUATION_SLUGS[match.group(1)]
    return None


def resolve_expanded_form(text: str) -> str | None:
    """Return the canonical slug for a taxonomy hint, else ``None`` (RF-29)."""
    for marker, slug in EXPANDED_FORM_MARKERS:
        if _contains_marker(text, marker):
            return slug
    return _resolve_unown(text)


# ``slug -> nombre de forma de PokeAPI`` (RF-46). La tabla es explicita y esta
# anclada a la especie de PokeAPI; no es una regla de sufijo generico. Hace
# falta la especie porque ``crowned`` comparte slug entre Zacian y Zamazenta,
# ``dusk-mane`` no se llama ``necrozma-dusk-mane`` en PokeAPI, y Unown no puede
# resolverse por una letra suelta (``porygon-z``, ``nidoran-f``/``nidoran-m``,
# ``jangmo-o``/``hakamo-o``/``kommo-o``). Cada fila es
# ``(especie PokeAPI, sufijo de forma PokeAPI, slug)``.
_UNOWN_FORM_MARKERS: tuple[tuple[str, str, str], ...] = tuple(
    ("unown", chr(ord("a") + offset), chr(ord("a") + offset))
    for offset in range(26)
)

POKEAPI_FORM_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("deoxys", "attack", "attack"),
    ("deoxys", "defense", "defense"),
    ("deoxys", "speed", "speed"),
    ("genesect", "burn", "burn-drive"),
    ("genesect", "chill", "chill-drive"),
    ("genesect", "douse", "douse-drive"),
    ("genesect", "shock", "shock-drive"),
    ("tauros", "paldea-combat-breed", "paldea-combat"),
    ("tauros", "paldea-blaze-breed", "paldea-blaze"),
    ("tauros", "paldea-aqua-breed", "paldea-aqua"),
    ("necrozma", "dusk", "dusk-mane"),
    ("necrozma", "dawn", "dawn-wings"),
    ("zacian", "crowned", "crowned"),
    ("zamazenta", "crowned", "crowned"),
    ("tatsugiri", "curly", "curly"),
    ("tatsugiri", "droopy", "droopy"),
    ("tatsugiri", "stretchy", "stretchy"),
    ("shellos", "east", "east"),
    ("shellos", "west", "west"),
) + _UNOWN_FORM_MARKERS + (
    ("unown", "exclamation", "exclamation"),
    ("unown", "question", "question"),
)

# Direccion inversa ``slug -> nombres de forma de PokeAPI`` (RF-46). Un slug
# puede tener mas de un nombre (``crowned`` -> Zacian y Zamazenta).
POKEAPI_FORM_NAMES_BY_SLUG: dict[str, tuple[str, ...]] = {
    slug: tuple(
        f"{species}-{suffix}"
        for species, suffix, candidate in POKEAPI_FORM_MARKERS
        if candidate == slug
    )
    for _, _, slug in POKEAPI_FORM_MARKERS
}

# Form names which are part of the identity contract.  This is deliberately a
# table, rather than a "take the last suffix" rule: a one-letter suffix is
# meaningful only for Unown and must never turn Porygon-Z or Nidoran into a
# made-up form.
REGIONAL_FORM_NAMES: dict[str, str] = {
    "alola": "{species}-alola",
    "galar": "{species}-galar",
    "hisui": "{species}-hisui",
    "paldea": "{species}-paldea",
    "origin": "{species}-origin",
    "altered": "{species}-altered",
    "incarnate": "{species}-incarnate",
    "therian": "{species}-therian",
    "disguised": "{species}-disguised",
    "hero-of-many-battles": "{species}-hero-of-many-battles",
}


def explicit_pokeapi_form_name(
    species: str, form: str, variant: str
) -> tuple[str, ...]:
    """Return the exact PokeAPI form-name candidates for an identity.

    Candidates are ordered and finite.  In particular, this function never
    derives a form from an arbitrary final character or segment.
    """
    species = species.lower()
    if variant == "MEGA":
        return (f"{species}-mega", f"{species}-mega-x", f"{species}-mega-y")
    if form == "normal":
        return (species,)
    expanded = tuple(
        name for name in POKEAPI_FORM_NAMES_BY_SLUG.get(form, ())
        if name.startswith(f"{species}-")
    )
    if expanded:
        return expanded
    template = REGIONAL_FORM_NAMES.get(form)
    return (template.format(species=species),) if template else ()


def match_pokeapi_form(
    form_name: str, species_by_name: dict[str, int]
) -> tuple[int, str] | None:
    """Resuelve ``(dex, slug)`` de una forma de la taxonomia ampliada (RF-46).

    El emparejamiento es exacto y esta anclado a la especie de PokeAPI, asi que
    ``unown-a`` no colisiona con ``porygon-z`` y no existe ninguna regla de
    sufijo generico de una letra. Devuelve ``None`` para cualquier forma fuera
    de la tabla (``necrozma-ultra``, ``tatsugiri-*-mega``...), que el llamante
    deja caer al sprite base.
    """
    for species, suffix, slug in POKEAPI_FORM_MARKERS:
        if form_name == f"{species}-{suffix}":
            dex = species_by_name.get(species)
            if dex is not None:
                return dex, slug
    return None
