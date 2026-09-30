"""Identidad de un jefe de raid: ``(dex_number, form, variant)``.

``form`` es un slug inglés en minúsculas. MEGA, PRIMAL, SHADOW y APEX solo
viven en ``variant``, nunca en ``form``.
"""

import re
from dataclasses import dataclass

VARIANTS = frozenset({"NORMAL", "MEGA", "PRIMAL", "SHADOW", "APEX"})

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
    return re.sub(r"[^a-z0-9]+", "_", str(raw).strip().lower()).strip("_")


def normalize_form(raw: str) -> str:
    slug = slugify_form(raw)
    if slug.endswith("_form"):
        slug = slug[: -len("_form")]
    if slug.split("_", 1)[0] in VARIANT_KEYWORDS:
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


def normalize_dex_number(raw: object) -> int:
    try:
        dex_number = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise UnmappableIdentity(f"dex_number {raw!r} is not an integer") from exc
    if dex_number <= 0:
        raise UnmappableIdentity(f"dex_number {dex_number} must be positive")
    return dex_number


def resolve_identity(dex_number: object, form: object, variant: object = "NORMAL") -> Identity:
    return Identity(
        dex_number=normalize_dex_number(dex_number),
        form=normalize_form("" if form is None else str(form)),
        variant=normalize_variant(variant),
    )
