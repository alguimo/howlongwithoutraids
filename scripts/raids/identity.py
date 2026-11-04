"""Identidad de un jefe de raid: ``(dex_number, form, variant)``.

``form`` es un slug inglés en minúsculas con guiones como separador de
palabras (``hero-of-many-battles``). MEGA, PRIMAL, SHADOW y APEX solo viven en
``variant``, nunca en ``form``.
"""

import re
from dataclasses import dataclass

from raids.forms import resolve_expanded_form

VARIANTS = frozenset({"NORMAL", "MEGA", "PRIMAL", "SHADOW", "APEX"})
# RF-19: ``2`` existed until August 2020 and ``SUPER_MEGA`` names the 2026 label.
TIERS = frozenset({
    "1", "2", "3", "4", "5", "MEGA", "MEGA_LEGENDARY", "SUPER_MEGA", "PRIMAL",
    "ELITE", "SHADOW_1", "SHADOW_3", "SHADOW_5",
})

VARIANT_KEYWORDS = frozenset({"mega", "primal", "shadow", "apex"})

FORM_ALIASES = {
    "alolan": "alola",
    "galarian": "galar",
    "hisuian": "hisui",
    "paldean": "paldea",
    "default": "normal",
    "origen": "origin",
    "modificada": "modified",
    "disfraz": "disguised",
    # PokeAPI suffixes keep the base slug: ``origin``/``altered``, not
    # ``origin-forme``/``altered-forme`` (RF-44).
    "origin-forme": "origin",
    "altered-forme": "altered",
}

# Fandom ``ci=``/``ct=`` form hints. These are the catalog form markers the
# historical pages use; anything else falls through to the expanded taxonomy,
# the cosmetic list, or is omitted (RF-20, RF-29).
FORM_MARKERS = {
    "alolan": "alola",
    "galarian": "galar",
    "hisuian": "hisui",
    "paldean": "paldea",
    "origin": "origin",
    "altered": "altered",
    "incarnate": "incarnate",
    "therian": "therian",
    "disguised": "disguised",
    "hero of many battles": "hero-of-many-battles",
}

# RF-29: closed list of cosmetic markers. A match means the row keeps the base
# identity (``form=normal``); it never invents a form. ``cloak`` names Burmy's
# Plant/Sandy/Trash Cloak: Burmy is always Bug-type with the same stats and the
# catalog models only its base ``normal`` form (the cloak only decides
# Wormadam's evolution), so it is cosmetic and not a modeled form.
COSMETIC_MARKERS = frozenset({
    "hat", "party", "holiday", "halloween", "new year", "safari", "varsity",
    "crown", "armored", "explorer", "bow", "cake", "flower", "fall",
    "sunglasses", "black", "white", "mischief", "trash", "festive", "stantler",
    "cloak", "astronaut",
})

# Mega/Primal/Super Mega never live in ``form``: only their ``variant`` changes.
VARIANT_MARKERS = {"mega": "MEGA", "primal": "PRIMAL"}

# Spec 005 RF-09: closed table of species whose default GO form has its own
# slug rather than ``normal``, so base appearances never split across two rows.
CANONICAL_DEFAULT_FORMS: dict[int, str] = {
    487: "altered",
    641: "incarnate",
    642: "incarnate",
    645: "incarnate",
    888: "hero-of-many-battles",
    889: "hero-of-many-battles",
    905: "incarnate",
}


class UnmappableIdentity(ValueError):
    """La fila no se puede mapear a una identidad válida y debe omitirse."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Identity:
    dex_number: int
    form: str
    variant: str


def slugify_form(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(raw).strip().lower()).strip("-")


def normalize_form(raw: str) -> str:
    slug = slugify_form(raw)
    # RF-44: the official ``Forme`` spelling (Bulbapedia, PokeAPI) must
    # canonicalize to the same slug Fandom emits, so ``Attack Forme`` becomes
    # ``attack`` and never the false identity ``attack-forme``. ``Form`` is the
    # other spelling the history uses (``Alolan Form``).
    for suffix in ("-forme", "-form"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    if any(part in VARIANT_KEYWORDS for part in slug.split("-")):
        raise UnmappableIdentity(
            f"form {raw!r} names a variant; use the variant field instead"
        )
    slug = FORM_ALIASES.get(slug, slug)
    if not slug:
        raise UnmappableIdentity(f"form {raw!r} is empty after slugify")
    return slug


def normalize_variant(raw: object) -> str:
    if raw is None or str(raw).strip() == "":
        return "NORMAL"
    variant = str(raw).strip().upper()
    if variant not in VARIANTS:
        raise UnmappableIdentity(f"variant {raw!r} is not in {sorted(VARIANTS)}")
    return variant


def normalize_tier(raw: object) -> str:
    """Normalize and validate the closed raid-tier enum."""
    if raw is None or str(raw).strip() == "":
        raise UnmappableIdentity("tier is empty")
    tier = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
    if tier not in TIERS:
        raise UnmappableIdentity(f"tier {raw!r} is not in {sorted(TIERS)}")
    return tier


def _contains_marker(text: str, marker: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def is_cosmetic_marker(text: object) -> bool:
    """``True`` when the text carries a marker of the closed cosmetic list (RF-29).

    Single canonicalization point shared by both sources: Fandom's ``ci=``/``ct=``
    hints and Bulbapedia's raw ``form=`` values go through this same list, so a
    cosmetic never invents a form of its own. Matching is on word boundaries, so
    ``crowned`` is not ``crown``.
    """
    lowered = str(text).strip().lower()
    return any(_contains_marker(lowered, marker) for marker in COSMETIC_MARKERS)


def classify_form_hint(ci: object = None, ct: object = None) -> tuple[str, str | None]:
    """Resolve the Fandom ``ci=``/``ct=`` hints into ``(form, variant)`` (RF-29).

    The hint text is scanned against the closed catalog-form markers, then the
    expanded form taxonomy (Deoxys, Genesect, Tauros de Paldea, Necrozma,
    Zacian/Zamazenta crowned, Unown, Tatsugiri, Shellos), then the Mega/Primal
    variant markers, then the closed cosmetic list. Empty hints mean the base
    boss and yield ``("normal", None)``. A non-empty hint that matches none of
    those raises :class:`UnmappableIdentity` so the caller omits and logs the row
    (RF-20) instead of collapsing it to ``normal``.
    """
    parts = [str(part).strip().lower() for part in (ci, ct) if part is not None and str(part).strip()]
    text = " ".join(parts)
    if not text:
        return "normal", None
    for marker in sorted(FORM_MARKERS, key=len, reverse=True):
        if _contains_marker(text, marker):
            return FORM_MARKERS[marker], None
    expanded = resolve_expanded_form(text)
    if expanded is not None:
        return expanded, None
    for marker, variant in VARIANT_MARKERS.items():
        if _contains_marker(text, marker):
            return "normal", variant
    if is_cosmetic_marker(text):
        return "normal", None
    raise UnmappableIdentity(
        f"form hint {text!r} is neither a catalog form, an expanded taxonomy "
        "form, nor a listed cosmetic"
    )


def normalize_dex_number(raw: object) -> int:
    try:
        dex_number = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise UnmappableIdentity(f"dex_number {raw!r} is not an integer") from exc
    if dex_number <= 0:
        raise UnmappableIdentity(f"dex_number {dex_number} must be positive")
    return dex_number


def resolve_identity(dex_number: object, form: object, variant: object = "NORMAL") -> Identity:
    dex = normalize_dex_number(dex_number)
    normalized_form = normalize_form("" if form is None else str(form))
    if normalized_form == "normal" and dex in CANONICAL_DEFAULT_FORMS:
        normalized_form = CANONICAL_DEFAULT_FORMS[dex]
    return Identity(
        dex_number=dex,
        form=normalized_form,
        variant=normalize_variant(variant),
    )
