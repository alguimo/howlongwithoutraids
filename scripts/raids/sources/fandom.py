"""Parser del wikitext de las páginas anuales de Fandom.

Extrae **instantáneas** del roster, no ventanas: cada fila ``{{PL|...}}`` de una
tabla es el estado del jefe en la sección de cambio que abre su encabezado
``==Mes Día==``. La fusión en ventanas (RF-37) y la resolución de identidad
(``ci=``/``ct=``, RF-20/RF-29) y del nombre de evento (RF-42) llegan en tareas
posteriores; aquí solo se delimitan secciones, se mapea el tier y se conservan
el nombre crudo, los flags y los argumentos de ``{{PL}}``.

Sin DOM ni HTML: solo texto wiki, sin red y sin base de datos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping

from raids.events import extract_event_name
from raids.identity import Identity, UnmappableIdentity, classify_form_hint, resolve_identity
from raids.intervals import InvertedWindow, validate_window
from raids.log import log_omitted
from raids.time import to_utc

# The approved historical coverage, explicit and ordered (RF-27, RF-31).
FANDOM_PAGE_CATALOG = tuple(
    f"List_of_Raid_Bosses_changes/{year}" for year in range(2017, 2027)
)

_HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FILE_LINK = re.compile(r"\[\[File:[^\]]*\]\]", re.IGNORECASE)
_NTH_TEMPLATE = re.compile(r"\{\{\s*[Nn]th\s*\|\s*(\d+)\s*\}\}")
_TABLE = re.compile(r"\{\|(.*?)\|\}", re.DOTALL)
_PL = re.compile(r"\{\{PL\|([^}|]+)((?:\|[^{}]*)*)\}\}")

_MONTH_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DATE_HEADING = re.compile(
    rf"^({_MONTH_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?$", re.IGNORECASE
)

_TIER_BY_LABEL = {
    "tier 1": "1",
    "tier 2": "2",
    "tier 3": "3",
    "tier 4": "4",
    "tier 5": "5",
    "mega": "MEGA",
    "mega legendary": "MEGA_LEGENDARY",
    "primal": "PRIMAL",
    "elite": "ELITE",
    "super mega": "SUPER_MEGA",
    "shadow tier 1": "SHADOW_1",
    "shadow tier 3": "SHADOW_3",
    "shadow tier 5": "SHADOW_5",
}
_SHADOW_TIERS = frozenset({"SHADOW_1", "SHADOW_3", "SHADOW_5"})
_PARENTHETICAL = re.compile(r"\(.*?\)")
_WHITESPACE = re.compile(r"\s+")

_YEAR_IN_TITLE = re.compile(r"/(\d{4})$")


@dataclass(frozen=True)
class FandomSection:
    """A change section: from a date heading to the next date heading."""

    title: str
    page_title: str
    year: int
    start: date
    end: date | None
    body: str


@dataclass(frozen=True)
class FandomSnapshot:
    """An unresolved roster row, ready for the identity/event tasks."""

    name: str
    tier: str
    section: FandomSection
    args: Mapping[str, str]
    is_shadow: bool
    is_shiny: bool


@dataclass(frozen=True)
class FandomAppearance:
    """A raw snapshot resolved to a composite identity and an event name."""

    identity: Identity
    name: str
    tier: str
    section: FandomSection
    event_name: str | None = None


@dataclass(frozen=True)
class FandomWindow:
    """A real appearance window fused from per-section roster snapshots (RF-37).

    ``end`` is ``None`` for the still-open last heading of the timeline: the
    current-year page has no later date heading, so no end is invented (RF-04).
    Only an actuality source can close it later (RF-34). ``source`` and
    ``page_kind`` match the historical records the shared deduplicator and
    store consume.
    """

    identity: Identity
    name: str
    tier: str
    start: datetime
    end: datetime | None
    source: str = "fandom"
    page_title: str = ""
    page_kind: str = "year"
    event_name: str | None = None


def map_tier(label: str | None) -> str | None:
    """Translate a table header label to the closed tier enum (RF-39).

    The tier is the visible label next to the icon (``Tier 5``, ``Mega``,
    ``Shadow Tier 3``); an unrecognized label is not guessed and returns
    ``None`` so the caller can omit the rows and log them.
    """
    if not label:
        return None
    text = _HTML_COMMENT.sub("", label)
    text = _PARENTHETICAL.sub(" ", text)
    key = _WHITESPACE.sub(" ", text).strip().lower()
    return _TIER_BY_LABEL.get(key)


def page_year(page_title: str) -> int:
    """Return the year encoded in an approved annual Fandom page title."""
    match = _YEAR_IN_TITLE.search(page_title)
    if match is None:
        raise ValueError(f"page title {page_title!r} has no year")
    return int(match.group(1))


def _clean_heading(title: str) -> str:
    return _HTML_COMMENT.sub("", title).strip()


def _parse_date_heading(title: str) -> tuple[int, int] | None:
    """Return ``(month, day)`` for a ``Mes Día`` heading, else ``None``."""
    text = _NTH_TEMPLATE.sub(lambda match: match.group(1), _clean_heading(title))
    match = _DATE_HEADING.match(text)
    if match is None:
        return None
    month = _MONTHS[match.group(1)[:3].lower()]
    return month, int(match.group(2))


def split_date_sections(
    wikitext: str, *, page_title: str, year: int | None = None, logger=None
) -> list[FandomSection]:
    """Split a page into change sections delimited by date headings (RF-28).

    Only a date-formatted heading opens a section; every other heading
    (``==References==``, ``==See also==``, ``==Trivia==``…) is ignored wherever
    it appears and never closes a section. A December heading followed by a
    January heading in the same page rolls the calendar year forward.
    """
    if year is None:
        year = page_year(page_title)

    resolved: list[tuple[re.Match[str], str, date]] = []
    previous: tuple[int, int] | None = None
    for match in _HEADING.finditer(wikitext):
        title = match.group(2).strip()
        parsed = _parse_date_heading(title)
        if parsed is None:
            continue
        month, day = parsed
        heading_year = year
        if previous is not None:
            previous_month, previous_year = previous
            if month < previous_month:
                heading_year = previous_year + 1
        try:
            start = date(heading_year, month, day)
        except ValueError:
            log_omitted(
                "impossible Fandom section date",
                logger=logger,
                page=page_title,
                section=title,
            )
            continue
        resolved.append((match, title, start))
        previous = (month, heading_year)

    sections: list[FandomSection] = []
    for index, (match, title, start) in enumerate(resolved):
        has_next = index + 1 < len(resolved)
        body_end = resolved[index + 1][0].start() if has_next else len(wikitext)
        sections.append(
            FandomSection(
                title=title,
                page_title=page_title,
                year=start.year,
                start=start,
                end=resolved[index + 1][2] if has_next else None,
                body=wikitext[match.end():body_end],
            )
        )
    return sections


def _header_label(table_body: str) -> str:
    for line in table_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("!"):
            text = _FILE_LINK.sub("", _HTML_COMMENT.sub("", stripped.lstrip("!")))
            return text.split("|")[-1].strip()
    return ""


def _parse_pl_args(rest: str) -> dict[str, str]:
    args: dict[str, str] = {}
    for part in rest.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if key:
            args[key] = value.strip()
    return args


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"t", "true", "1", "yes"}


def _pl_rows(table_body: str) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for match in _PL.finditer(table_body):
        name = match.group(1).strip()
        if not name:
            continue
        rows.append((name, _parse_pl_args(match.group(2))))
    return rows


def parse_page(
    wikitext: str,
    *,
    page_title: str,
    year: int | None = None,
    logger=None,
) -> list[FandomSnapshot]:
    """Parse every valid row of a page into unresolved snapshots (RF-29).

    A table without a recognized tier omits its rows and logs them; a row with
    ``shadow=t`` under a tier that is not ``Shadow Tier n`` is ambiguous, so it
    is omitted and logged (RF-32). ``s=t`` is shiny and never implies Shadow.
    """
    snapshots: list[FandomSnapshot] = []
    for section in split_date_sections(
        wikitext, page_title=page_title, year=year, logger=logger
    ):
        for table in _TABLE.finditer(section.body):
            table_body = table.group(1)
            rows = _pl_rows(table_body)
            if not rows:
                continue
            tier = map_tier(_header_label(table_body))
            if tier is None:
                log_omitted(
                    "unrecognized Fandom table tier",
                    logger=logger,
                    page=page_title,
                    section=section.title,
                    label=_header_label(table_body),
                )
                continue
            is_shadow_tier = tier in _SHADOW_TIERS
            for name, args in rows:
                is_shadow = _is_truthy(args.get("shadow", ""))
                if is_shadow and not is_shadow_tier:
                    log_omitted(
                        "shadow flag under a non-Shadow tier",
                        logger=logger,
                        page=page_title,
                        section=section.title,
                        name=name,
                        tier=tier,
                    )
                    continue
                snapshots.append(
                    FandomSnapshot(
                        name=name,
                        tier=tier,
                        section=section,
                        args=args,
                        is_shadow=is_shadow,
                        is_shiny=_is_truthy(args.get("s", "")),
                    )
                )
    return snapshots


def resolve_identity_and_event(
    snapshot: FandomSnapshot, *, dex_number: int, logger=None
) -> FandomAppearance | None:
    """Resolve one raw Fandom row, or omit it and log it (RF-20, RF-29, RF-42).

    The dex number comes from the catalog (resolved by the caller from the boss
    name). The form/variant comes from ``ci=``/``ct=`` and the table tier; a
    ``Shadow Tier n`` header fixes ``variant=SHADOW``. The event name comes only
    from the section prose and the closed patterns (RF-42).
    """
    try:
        form, variant_hint = classify_form_hint(
            snapshot.args.get("ci"), snapshot.args.get("ct")
        )
    except UnmappableIdentity as exc:
        log_omitted(
            str(exc),
            logger=logger,
            page=snapshot.section.page_title,
            section=snapshot.section.title,
            name=snapshot.name,
        )
        return None

    if snapshot.is_shadow or snapshot.tier in _SHADOW_TIERS:
        variant = "SHADOW"
    else:
        variant = variant_hint or "NORMAL"

    try:
        identity = resolve_identity(dex_number, form, variant)
    except UnmappableIdentity as exc:
        log_omitted(
            str(exc),
            logger=logger,
            page=snapshot.section.page_title,
            section=snapshot.section.title,
            name=snapshot.name,
        )
        return None

    return FandomAppearance(
        identity=identity,
        name=snapshot.name,
        tier=snapshot.tier,
        section=snapshot.section,
        event_name=extract_event_name(snapshot.section.body),
    )


def _window_section_instant(section_start: date) -> datetime:
    """A date heading is an end-of-day instant in ``America/Los_Angeles`` (RF-18)."""
    return to_utc(section_start.isoformat())


def _identity_key(identity: Identity) -> tuple[int, str, str]:
    return identity.dex_number, identity.form, identity.variant


def _build_window(
    current: tuple[date, str, FandomAppearance],
    end_section: date | None,
    logger,
) -> FandomWindow | None:
    start_section, tier, appearance = current
    start = _window_section_instant(start_section)
    end = _window_section_instant(end_section) if end_section is not None else None
    if end is not None:
        try:
            validate_window(start, end)
        except InvertedWindow as exc:
            log_omitted(
                f"inverted Fandom window: {exc}",
                logger=logger,
                page=appearance.section.page_title,
                section=start_section.isoformat(),
                name=appearance.name,
            )
            return None
    return FandomWindow(
        identity=appearance.identity,
        name=appearance.name,
        tier=tier,
        start=start,
        end=end,
        source="fandom",
        page_title=appearance.section.page_title,
        page_kind="year",
        event_name=appearance.event_name,
    )


def fuse_fandom_windows(
    appearances,
    *,
    timeline=None,
    logger=None,
) -> list[FandomWindow]:
    """Fuse Fandom roster snapshots into continuity windows (RF-04, RF-37).

    Every row of a change table is a snapshot of the whole roster, so a boss
    that simply stays produces one row per heading. The fusion groups the
    resolved appearances by composite identity ``(dex_number, form, variant)``
    and walks a single chronological timeline of date headings:

    - a window opens at the first heading where the identity appears;
    - it closes at the next heading where the identity is gone **or** its tier
      changed (a tier change opens a new window);
    - the last heading of the timeline leaves its window open (``end=None``):
      it is the current-year page, and no end may be invented (RF-04, RF-34).

    ``timeline`` is the ordered list of every date heading (including headings
    whose rows were all omitted, so absence still closes a window). When it is
    omitted, it is derived from the appearances and sorted by date. A produced
    window whose end precedes its start is rejected and logged (RF-04).
    """
    appearances = list(appearances)
    if not appearances:
        return []
    if timeline is None:
        timeline = sorted({appearance.section.start for appearance in appearances})
    else:
        timeline = list(timeline)

    grouped: dict[tuple[int, str, str], list[FandomAppearance]] = {}
    for appearance in appearances:
        grouped.setdefault(_identity_key(appearance.identity), []).append(appearance)

    windows: list[FandomWindow] = []
    for key in sorted(grouped):
        by_section: dict[date, list[FandomAppearance]] = {}
        for appearance in sorted(grouped[key], key=lambda item: item.name):
            by_section.setdefault(appearance.section.start, []).append(appearance)

        current: tuple[date, str, FandomAppearance] | None = None
        for section_start in timeline:
            present = by_section.get(section_start)
            if present is None:
                if current is not None:
                    window = _build_window(current, section_start, logger)
                    if window is not None:
                        windows.append(window)
                    current = None
                continue
            if current is None:
                opening = present[0]
                current = (section_start, opening.tier, opening)
            elif current[1] not in {appearance.tier for appearance in present}:
                window = _build_window(current, section_start, logger)
                if window is not None:
                    windows.append(window)
                opening = present[0]
                current = (section_start, opening.tier, opening)
        if current is not None:
            window = _build_window(current, None, logger)
            if window is not None:
                windows.append(window)

    windows.sort(key=lambda window: (_identity_key(window.identity), window.start))
    return windows
