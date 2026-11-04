"""Hybrid historical backfill.

Fandom ``List_of_Raid_Bosses_changes/YYYY`` (2017-2026) is the main historical
coverage; Bulbapedia stays as a contrast source (its closed catalog does not
change). Both are persisted with their own ``source`` and deduplicated across
sources by exact window, and every run logs the observable contrast counts
(RF-45). Each page is isolated: a 403/404/429/5xx or invalid payload is logged
and never deletes stored data or blocks the following pages.

The legacy isolated page run (``pages=...``) is kept for the contract fixtures
and never touches Fandom.
"""

import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from raids.log import log_contrast
from raids.log import log_source_failure
from raids.log import log_omitted
from raids.identity import UnmappableIdentity, normalize_tier
from raids.pokedex import Catalog
from raids.sources import mediawiki
from raids.sources import transport as transport_module
from raids.sources.fandom import FANDOM_PAGE_CATALOG
from raids.sources import fandom as fandom_source
from raids.store import AppearanceRecord, store_pages
from raids.time import to_utc
from raids.intervals import merge_records_by_source


# Keep this tuple explicit and ordered: it is the approved historical
# coverage, not a list discovered from links or from user input.
HISTORICAL_PAGE_CATALOG = (
    "List_of_Raid_Boss_changes_in_2017-2018",
    "List_of_Raid_Boss_changes_in_2019",
    "List_of_Raid_Boss_changes_in_2020",
    "List_of_Raid_Boss_changes_in_2021",
    "List_of_Raid_Boss_changes_in_2022",
    "List_of_Raid_Boss_changes_in_Season_1",
    "List_of_Raid_Boss_changes_in_Season_2",
    "List_of_Raid_Boss_changes_in_Season_3",
    "List_of_Raid_Boss_changes_in_Season_4",
    "List_of_Raid_Boss_changes_in_Season_5",
    "List_of_Raid_Boss_changes_in_Season_6",
    "List_of_Raid_Boss_changes_in_Season_7",
    "List_of_Raid_Boss_changes_in_Season_8",
    "List_of_Raid_Boss_changes_in_Season_9",
    "List_of_Raid_Boss_changes_in_Season_10",
    "List_of_Raid_Boss_changes_in_Season_11",
    "List_of_Shadow_Raid_Boss_changes",
)

_ROW = re.compile(
    r"^\|\s*(.+?)\s*\|\|\s*(.+?)\s*\|\|\s*(.+?)\s*\|\|\s*(.+?)\s*$",
    re.MULTILINE,
)

_HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.MULTILINE)
_ISO_DATE = r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?"
_MONTH_DATE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,?\s+\d{4})?"
_DATE = re.compile(rf"(?:{_ISO_DATE}|{_MONTH_DATE})", re.IGNORECASE)

# A section heading like ``November 28 - December 18`` or
# ``January 1, 2024 – January 8, 2024`` names a window, not an event (RF-42).
# Event headings such as ``Ultra Bonus 2019`` or ``Mega week`` do not match.
_MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_BULBA_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_BULBA_MONTH_DATE = rf"{_MONTH_NAMES}\s+{_BULBA_DAY}(?:,?\s+\d{{4}})?"
_BULBA_MONTH_YEAR = rf"{_MONTH_NAMES}\s+\d{{4}}"
_ISO_DAY = r"\d{4}-\d{2}-\d{2}"
_BULBA_DATE = rf"(?:{_BULBA_MONTH_DATE}|{_BULBA_MONTH_YEAR}|{_ISO_DAY})"
_DATE_HEADING = re.compile(
    rf"^{_BULBA_DATE}"
    rf"(?:\s*(?:-|–|—|to|through|until)\s*(?:{_BULBA_DATE}|{_BULBA_DAY}))?$",
    re.IGNORECASE,
)


def _is_date_heading(title: str) -> bool:
    return bool(_DATE_HEADING.match(title.strip()))


def _event_name_from_sections(section_path: tuple[str, ...]) -> str | None:
    """Return the nearest non-date section heading as the event name (RF-42).

    Bulbapedia mixes window headings (``November 28 - December 18``) with event
    headings (``Ultra Bonus 2019``). The deepest event heading names the
    appearance; if every heading is a date, there is no determinable name.
    """
    for heading in reversed(section_path):
        title = heading.strip()
        if title and not _is_date_heading(title):
            return title
    return None

# Bulbapedia's numbered seasons are calendar periods, not a year value.  Keep
# this deliberately explicit: changing the current date must never change the
# meaning of an old page.  Seasons 1-4 are the 2020/2021 periods; seasons 5-11
# are the consecutive periods documented by Bulbapedia from Dec 2021 onward.
SEASON_YEAR_RANGES = {
    1: (2020, 2021), 2: (2021, 2021), 3: (2021, 2021), 4: (2021, 2021),
    5: (2021, 2022), 6: (2022, 2022), 7: (2022, 2022), 8: (2022, 2022),
    9: (2022, 2023), 10: (2023, 2023), 11: (2023, 2023),
}


@dataclass(frozen=True)
class SectionContext:
    """Temporal heading context retained for provenance and later resolution."""

    title: str
    path: tuple[str, ...]
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class HistoricalRecord:
    """Structured, deliberately unresolved output of the regular-page parser."""

    name: str
    dex_number: str | None
    form: str | None
    variant: str | None
    tier: str | None
    start: str | None
    end: str | None
    source: str
    page_title: str
    page_kind: str
    section_title: str
    section_path: tuple[str, ...]
    template_name: str


@dataclass(frozen=True)
class ResolvedHistoricalRecord:
    """A parser record with domain identity, UTC dates and a closed tier."""

    identity: Any
    name: str
    tier: str
    start: datetime
    end: datetime
    source: str
    page_title: str
    page_kind: str
    event_name: str | None = None


_SHADOW_STARS = re.compile(r"(?:shadow[^\n]*?)?\b([135])\s*(?:-?star|stars)\b", re.I)
_SHADOW_LEVEL = re.compile(r"\b(?:tier|level)\s*([135])\b", re.I)
_SHADOW_TIER = re.compile(r"\bshadow[_ -]?([135])\b", re.I)


_FIELD_NAMES = {
    "name": {"name", "boss", "pokemon", "pokémon", "mon"},
    "dex_number": {"dex", "dexnumber", "dex_number", "number", "id", "pokedex"},
    "form": {"form", "forme"},
    "variant": {"variant", "type", "varianttype"},
    "tier": {"tier", "stars", "star", "raidtier"},
    "start": {"start", "from", "begin", "beginning", "datestart"},
    "end": {"end", "to", "finish", "ending", "dateend"},
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    value = re.sub(r"<!--.*?-->", "", str(value), flags=re.DOTALL).strip()
    return value or None


def _template_parts(raw: str) -> tuple[str, list[str]]:
    text = raw[2:-2]
    parts, current, depth = [], [], 0
    for char in text:
        if char == "{" and depth >= 0:
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        if char == "|" and depth == 0:
            parts.append("".join(current)); current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts[0].strip(), parts[1:]


def _arguments(parts: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    positional = 1
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            values[key.strip().lower().replace(" ", "")] = _clean(value) or ""
        else:
            values[str(positional)] = _clean(part) or ""
            positional += 1
    return values


def _field(values: dict[str, str], field: str, positional: int | None = None) -> str | None:
    for key in _FIELD_NAMES[field]:
        if key in values and values[key]:
            return values[key]
    return values.get(str(positional)) if positional else None


def _row_values(values: dict[str, str]) -> dict[str, str]:
    """Accommodate the compact positional row used by older page revisions."""
    # Some revisions put the tier immediately after the dex number.  Do not
    # reinterpret a named field, and never turn an arbitrary value into a tier.
    if "tier" not in values and values.get("3", "").strip().lower() in {"1", "3", "4", "5", "mega", "primal"}:
        values = dict(values)
        values["tier"] = values["3"]
        values.pop("3", None)
    return values


_DEX_CODE = re.compile(r"^(\d+)[A-Za-z]*$")


def _real_positional_row(values: dict[str, str]) -> bool:
    """Bulbapedia's current GO row starts with a dex code, then the name.

    Older fixtures use ``name|dex|form|variant|tier``.  A code-shaped first
    argument is unambiguous enough to select the real layout without guessing
    at arbitrary positional values.
    """
    return bool(_DEX_CODE.fullmatch(values.get("1", ""))) and bool(values.get("2"))


def _dex_from_code(value: str | None) -> str | None:
    if not value:
        return None
    match = _DEX_CODE.fullmatch(value.strip())
    return match.group(1) if match else value


def _real_row_fields(values: dict[str, str], metadata: dict[str, str]) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Return name, dex, form, variant and tier for a structured GO row."""
    merged = {**metadata, **values}
    if not _real_positional_row(values):
        return (
            _field(merged, "name", 1) or "",
            _field(merged, "dex_number", 2),
            _field(merged, "form", 3),
            _field(merged, "variant", 4),
            _field(merged, "tier", 5),
        )

    form = _field(values, "form")
    variant = _field(values, "variant")
    if values.get("shadow", "").strip().lower() in {"yes", "true", "1"}:
        variant = "SHADOW"
    # Mega/Primal are variants, never forms.  Keep the base form for catalog
    # resolution instead of allowing these labels into normalize_form().
    if form and form.strip().lower().startswith(("mega", "primal")):
        variant = variant or form.strip().split()[0].upper()
        form = None
    return values["2"], _dex_from_code(values["1"]), form, variant, _field(merged, "tier")


def _heading_dates(title: str) -> tuple[str | None, str | None, bool]:
    dates = _DATE.findall(title)
    if len(dates) == 2:
        return dates[0], dates[1], False
    return None, None, len(dates) > 2


def _date_for_time_parser(value: str) -> str:
    """Convert Bulbapedia's month-name headings to the time module format."""
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            continue
    return value


def _looks_like_date(value: str) -> bool:
    return bool(_DATE.fullmatch(value.strip())) or bool(re.match(rf"^(?:{_ISO_DATE})$", value.strip()))


def _page_year_range(page_title: str) -> tuple[int, int] | None:
    annual = re.search(r"(?:_| )in(?:_| )(\d{4})(?:-(\d{4}))?$", page_title)
    if annual:
        first = int(annual.group(1))
        return first, int(annual.group(2) or first)
    season = re.search(r"(?:_| )in(?:_| )Season(?:_| )(\d+)$", page_title)
    if season:
        return SEASON_YEAR_RANGES.get(int(season.group(1)))
    return None


def _has_year(value: str) -> bool:
    return bool(re.search(r"\b\d{4}\b", value)) or bool(re.match(r"\d{4}-", value.strip()))


def _infer_date_range(start: str, end: str, page_title: str, logger=None) -> tuple[str, str] | None:
    """Complete month-name dates using only an approved page calendar."""
    if _has_year(start) and _has_year(end):
        return start, end
    years = _page_year_range(page_title)
    if years is None:
        log_omitted("cannot infer year safely", logger=logger, page=page_title, start=start, end=end)
        return None
    def parse_month_day(value: str, year: int):
        for pattern in ("%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(f"{value.strip()} {year}", pattern)
            except ValueError:
                continue
        return None

    start_date = parse_month_day(start, years[0]) if not _has_year(start) else None
    end_date = parse_month_day(end, years[0]) if not _has_year(end) else None
    if not _has_year(start) and start_date is None:
        return start, end
    if not _has_year(end) and end_date is None:
        return start, end
    if _has_year(start):
        start_date = datetime.fromisoformat(_date_for_time_parser(start).replace("Z", "+00:00"))
    if _has_year(end):
        end_date = datetime.fromisoformat(_date_for_time_parser(end).replace("Z", "+00:00"))
    assert start_date is not None and end_date is not None
    if not _has_year(start) and _has_year(end) and start_date.month > end_date.month:
        start_date = start_date.replace(year=end_date.year - 1)
    elif not _has_year(end) and end_date.month < start_date.month:
        end_date = end_date.replace(year=start_date.year + 1)
    return (
        start if _has_year(start) else start_date.date().isoformat(),
        end if _has_year(end) else end_date.date().isoformat(),
    )


def _sections(wikitext: str):
    matches = list(_HEADING.finditer(wikitext))
    stack: list[tuple[int, str, str | None, str | None]] = []
    for index, match in enumerate(matches):
        level, title = len(match.group(1)), match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        own_start, own_end, ambiguous = _heading_dates(title)
        stack.append((level, title, own_start, own_end))
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(wikitext)
        inherited = next(((item[2], item[3]) for item in reversed(stack) if item[2] and item[3]), (None, None))
        yield wikitext[match.end():body_end], SectionContext(
            title, tuple(item[1] for item in stack), own_start or inherited[0], own_end or inherited[1]
        ), ambiguous


def _templates(text: str):
    """Yield balanced template invocations, including nested template values."""
    start = None
    depth = 0
    index = 0
    while index < len(text) - 1:
        pair = text[index:index + 2]
        if pair == "{{":
            if depth == 0:
                start = index
            depth += 1
            index += 2
            continue
        if pair == "}}" and depth:
            depth -= 1
            index += 2
            if depth == 0 and start is not None:
                yield text[start:index]
                start = None
            continue
        index += 1


def parse_regular_wikitext(wikitext: str, *, page_title: str, page_kind: str = "year", logger=None) -> list[HistoricalRecord]:
    """Parse regular Bulbapedia templates without resolving domain values yet."""
    records: list[HistoricalRecord] = []
    if page_kind == "year" and re.search(r"(?:_| )in(?:_| )Season(?:_| )\d+$", page_title):
        page_kind = "season"
    for body, context, ambiguous in _sections(wikitext):
        metadata: dict[str, str] = {}
        if ambiguous:
            log_omitted("ambiguous temporal section", logger=logger, page=page_title, section=context.title)
            continue
        for invocation in _templates(body):
            name, parts = _template_parts(invocation)
            normalized = name.strip().lower()
            if normalized == "lop/raid/go-head":
                head = _arguments(parts)
                # The real header uses its first positional value for the
                # stars/tier; named values are retained unchanged.
                if "tier" not in head and head.get("1"):
                    head["tier"] = head["1"]
                if "start" not in head and head.get("2") and _looks_like_date(head["2"]):
                    head["start"] = head["2"]
                if "end" not in head and head.get("3") and _looks_like_date(head["3"]):
                    head["end"] = head["3"]
                metadata.update(head)
                continue
            if normalized != "lop/raid/go":
                log_omitted("unknown historical template", logger=logger, page=page_title, template=name)
                continue
            row_arguments = _arguments(parts)
            values = _row_values({**metadata, **row_arguments})
            name, dex_number, form, variant, tier = _real_row_fields(row_arguments, metadata)
            real_layout = _real_positional_row(row_arguments)
            start = (_field(values, "start") if real_layout else _field(values, "start", 6)) or context.start
            end = (_field(values, "end") if real_layout else _field(values, "end", 7)) or context.end
            if start and end:
                inferred = _infer_date_range(start, end, page_title, logger=logger)
                if inferred is None:
                    continue
                start, end = inferred
            record = HistoricalRecord(
                name=name,
                dex_number=dex_number,
                form=form,
                variant=variant,
                tier=tier,
                start=start,
                end=end,
                source="bulbapedia", page_title=page_title, page_kind=page_kind,
                section_title=context.title, section_path=context.path, template_name=name.strip(),
            )
            if not record.name or not record.start or not record.end:
                log_omitted("incomplete historical template", logger=logger, page=page_title, template=name)
                continue
            records.append(record)
    return records


def _shadow_tier(record: HistoricalRecord) -> str | None:
    """Derive a Shadow tier only from an explicit tier or star heading."""
    for value in (record.tier, record.section_title, *record.section_path):
        text = str(value or "")
        match = _SHADOW_TIER.search(text) or _SHADOW_STARS.search(text) or _SHADOW_LEVEL.search(text)
        if match:
            return f"SHADOW_{match.group(1)}"
        if text.strip() in {"1", "3", "5"}:
            return f"SHADOW_{text.strip()}"
    return None


def _page_kind(page: str) -> str:
    """Return the stable provenance kind for an approved page title."""
    if page == "List_of_Shadow_Raid_Boss_changes":
        return "shadow"
    if "Season_" in page:
        return "season"
    return "year"


def resolve_historical_record(record: HistoricalRecord, catalog: Catalog, logger=None):
    """Resolve one parsed row; invalid rows are logged and omitted."""
    try:
        resolved = catalog.resolve(record.name)
        if resolved is None:
            raise UnmappableIdentity(f"boss {record.name!r} is not in catalog")

        identity = resolved.identity
        # Structured fields are authoritative when supplied by the template,
        # but forms and variants still pass through the same strict resolver.
        # The raw Bulbapedia ``form=`` is canonicalized through the shared
        # closed cosmetic list first (RF-29): a listed cosmetic keeps the base
        # ``normal`` identity instead of inventing a spurious form that only
        # this source would emit.
        if record.form or record.variant:
            from raids.identity import is_cosmetic_marker, resolve_identity
            form = record.form or identity.form
            if record.form and is_cosmetic_marker(record.form):
                form = "normal"
            identity = resolve_identity(
                record.dex_number or identity.dex_number,
                form,
                record.variant or identity.variant,
            )

        tier = _shadow_tier(record) if record.page_kind == "shadow" else normalize_tier(record.tier)
        if tier is None:
            raise UnmappableIdentity("shadow tier is indeterminate")
        if record.page_kind == "shadow" and identity.variant != "SHADOW":
            identity = identity.__class__(identity.dex_number, identity.form, "SHADOW")
        start = to_utc(_date_for_time_parser(record.start))
        end = to_utc(_date_for_time_parser(record.end))
        if start > end:
            raise ValueError(f"inverted window: {start.isoformat()} > {end.isoformat()}")
        return ResolvedHistoricalRecord(
            identity, record.name,
            tier, start, end, record.source, record.page_title, record.page_kind,
            event_name=_event_name_from_sections(record.section_path),
        )
    except (UnmappableIdentity, ValueError, TypeError) as exc:
        log_omitted(str(exc), logger=logger, page=record.page_title, name=record.name)
        return None


resolve_record = resolve_historical_record


def deduplicate_historical_records(records, *, logger=None):
    """Consolidate parsed historical records without touching persistence.

    Exact windows collapse into one record with every origin (RF-36) and
    overlaps within the same source merge (RF-05); overlapping windows from
    different sources stay separate and are logged, never merged.
    """
    return merge_records_by_source(records, logger=logger)


# Short adapter name for callers that already call the historical parser
# directly; keeping it here avoids coupling T4 callers to orchestration.
parse_regular = parse_regular_wikitext


@dataclass(frozen=True)
class ChangeRow:
    start: datetime
    end: datetime
    boss_name: str
    tier: str


def parse_changes(wikitext: str) -> list[ChangeRow]:
    """Legacy table adapter retained until the structured parser task.

    T3 does not add heading/template parsing: new callers use
    :func:`download_pages` and receive raw wikitext.
    """

    rows = []
    for match in _ROW.finditer(wikitext):
        start, end, boss_name, tier = (cell.strip() for cell in match.groups())
        rows.append(ChangeRow(to_utc(start), to_utc(end), boss_name, tier))
    return rows


def download_pages(
    transport,
    *,
    pages: tuple[str, ...] = HISTORICAL_PAGE_CATALOG,
    api: str = mediawiki.DEFAULT_API,
    logger=None,
) -> list[mediawiki.ParsedPage]:
    """Fetch pages independently and return only their raw wikitext.

    A source error is page-local.  In particular, no caller receives a
    partial result for a failed page and no persistence operation is made in
    this download layer.
    """

    downloaded = []
    for page in pages:
        try:
            downloaded.append(mediawiki.fetch_page(transport, page, api=api))
        except mediawiki.SourceError as exc:
            log_source_failure(str(exc), logger=logger, page=page)
    return downloaded


FANDOM_SOURCE = "fandom"
BULBAPEDIA_SOURCE = "bulbapedia"
AVAILABLE_SOURCES = (FANDOM_SOURCE, BULBAPEDIA_SOURCE)


@dataclass(frozen=True)
class ContrastCounts:
    """Observable Fandom <-> Bulbapedia contrast computed from records (RF-45).

    Identities are ``(dex_number, form, variant)`` and windows add the exact UTC
    ``start``/``end``. The counts are read from the parser output, never inferred:
    they are the auditable check that a run's contrast is non-empty and sound.
    """

    identities_matched: int
    identities_fandom_only: int
    identities_bulbapedia_only: int
    windows_matched: int
    windows_fandom_only: int
    windows_bulbapedia_only: int


def _identity_key(record) -> tuple[Any, ...]:
    return record.identity.dex_number, record.identity.form, record.identity.variant


def _window_key(record) -> tuple[Any, ...]:
    return (*_identity_key(record), record.start, record.end)


def contrast_counts(fandom_records, bulbapedia_records) -> ContrastCounts:
    """Compare the two sources by identity and by exact window (RF-45)."""
    fandom_identities = {_identity_key(record) for record in fandom_records}
    bulbapedia_identities = {_identity_key(record) for record in bulbapedia_records}
    fandom_windows = {_window_key(record) for record in fandom_records}
    bulbapedia_windows = {_window_key(record) for record in bulbapedia_records}
    return ContrastCounts(
        identities_matched=len(fandom_identities & bulbapedia_identities),
        identities_fandom_only=len(fandom_identities - bulbapedia_identities),
        identities_bulbapedia_only=len(bulbapedia_identities - fandom_identities),
        windows_matched=len(fandom_windows & bulbapedia_windows),
        windows_fandom_only=len(fandom_windows - bulbapedia_windows),
        windows_bulbapedia_only=len(bulbapedia_windows - fandom_windows),
    )


def build_fandom_records(downloaded, catalog, *, logger=None):
    """Parse Fandom pages, fuse snapshots and keep closed windows (RF-29, RF-37).

    Fandom rows are roster snapshots, so they are first fused by identity
    continuity into real windows. The current-year open window has no end and is
    not modeled (RF-04): it is logged and skipped, never given an invented end.
    Download and parse happen before any persistence.
    """
    appearances: list = []
    timeline: list = []
    for parsed in downloaded:
        try:
            for section in fandom_source.split_date_sections(
                parsed.wikitext, page_title=parsed.title, logger=logger
            ):
                timeline.append(section.start)
            for snapshot in fandom_source.parse_page(
                parsed.wikitext, page_title=parsed.title, logger=logger
            ):
                resolved = catalog.resolve(snapshot.name)
                if resolved is None:
                    log_omitted(
                        f"Fandom boss {snapshot.name!r} is not in the catalog",
                        logger=logger,
                        page=parsed.title,
                        name=snapshot.name,
                    )
                    continue
                appearance = fandom_source.resolve_identity_and_event(
                    snapshot, dex_number=resolved.identity.dex_number, logger=logger
                )
                if appearance is not None:
                    appearances.append(appearance)
        except Exception as exc:
            # A parser regression is page-local, exactly like a source failure.
            log_source_failure(str(exc), logger=logger, page=parsed.title)

    windows = fandom_source.fuse_fandom_windows(
        appearances, timeline=sorted(set(timeline)), logger=logger
    )
    records = []
    for window in windows:
        if window.end is None:
            log_omitted(
                "open Fandom window is not modeled",
                logger=logger,
                page=window.page_title,
                name=window.name,
                start=window.start.isoformat(),
            )
            continue
        records.append(
            ResolvedHistoricalRecord(
                identity=window.identity,
                name=window.name,
                tier=window.tier,
                start=window.start,
                end=window.end,
                source=FANDOM_SOURCE,
                page_title=window.page_title,
                page_kind=window.page_kind,
                event_name=window.event_name,
            )
        )
    return records


def build_bulbapedia_records(downloaded, catalog, *, logger=None):
    """Resolve downloaded Bulbapedia pages into contrast records (RF-45)."""
    parsed_records = []
    for parsed in downloaded:
        page_kind = _page_kind(parsed.title)
        try:
            rows = parse_regular_wikitext(
                parsed.wikitext, page_title=parsed.title, page_kind=page_kind, logger=logger
            )
            # Keep the narrow legacy table adapter for explicitly selected
            # fixture pages.  It is not used to discover or expand the closed
            # Bulbapedia catalog, and structured templates always win.
            if not rows and parsed.title not in HISTORICAL_PAGE_CATALOG:
                rows = [
                    HistoricalRecord(
                        name=row.boss_name, dex_number=None, form=None, variant=None,
                        tier=row.tier, start=row.start.isoformat(), end=row.end.isoformat(),
                        source=BULBAPEDIA_SOURCE, page_title=parsed.title, page_kind=page_kind,
                        section_title="", section_path=(), template_name="legacy-table",
                    )
                    for row in parse_changes(parsed.wikitext)
                ]
            for row in rows:
                resolved = resolve_historical_record(row, catalog, logger=logger)
                if resolved is not None:
                    parsed_records.append(resolved)
        except Exception as exc:
            # Parser regressions are page-local just like source failures.
            log_source_failure(str(exc), logger=logger, page=parsed.title)
    return parsed_records


def _consolidated_to_pages(consolidated, catalog):
    """Turn consolidated records into per-origin persistable pages."""
    from raids.pokedex import canonical_species_name

    pages_to_store = []
    for item in consolidated.records:
        record = item.record
        exact = (
            catalog.entry_for_identity(record.identity)
            if hasattr(catalog, "entry_for_identity")
            else None
        )
        by_dex = (
            catalog.entry_for_dex(record.identity.dex_number)
            if hasattr(catalog, "entry_for_dex")
            else None
        )
        resolved = catalog.resolve(record.name)
        types = (
            exact.types
            if exact is not None and exact.types
            else by_dex.types
            if by_dex is not None and by_dex.types
            else resolved.types
            if resolved is not None
            else ()
        )
        species_name = canonical_species_name(
            record.name, catalog=catalog, dex_number=record.identity.dex_number
        )
        records = []
        for origin in item.origins:
            records.append(
                AppearanceRecord(
                    identity=record.identity,
                    name=species_name,
                    types=types,
                    sprite_url=None,
                    tier=record.tier,
                    start=record.start,
                    end=record.end,
                    source=origin.source,
                    page_title=origin.page_title,
                    page_kind=origin.page_kind,
                    event_name=record.event_name,
                    origins=(origin,),
                )
            )
        pages_to_store.append(records)
    return pages_to_store


def _consolidate_and_store(conn, records, catalog, *, logger=None):
    """Cross-source dedup (T20/RF-36) and per-page transactional persistence."""
    consolidated = merge_records_by_source(records, logger=logger)
    return store_pages(
        conn, _consolidated_to_pages(consolidated, catalog), logger=logger
    )


def _resolve_transport(*, transport=None, client=None):
    """Accept an injected transport or adapt a legacy ``httpx`` client."""
    if transport is not None:
        return transport
    if client is not None:
        return transport_module.HttpxTransport(client)
    raise TypeError("run() requires an injected transport (or an httpx client)")


def _fandom_transport(*, transport=None, fandom_transport=None):
    """Fandom needs stdlib urllib behind Cloudflare (RF-38); tests inject one."""
    if fandom_transport is not None:
        return fandom_transport
    if transport is not None:
        return transport
    raise TypeError("Fandom requires an injected transport")


def _bulbapedia_transport(*, transport=None, client=None):
    if transport is not None:
        return transport
    if client is not None:
        return transport_module.HttpxTransport(client)
    raise TypeError("Bulbapedia requires an injected transport or an httpx client")


def run(
    conn=None,
    *,
    transport=None,
    client=None,
    fandom_transport=None,
    pages=None,
    api=None,
    fandom_api=mediawiki.FANDOM_API,
    bulbapedia_api=mediawiki.DEFAULT_API,
    catalog=None,
    logger=None,
    sources=AVAILABLE_SOURCES,
    fandom_pages=None,
    bulbapedia_pages=None,
):
    """Run the historical backfill, isolating every page.

    Two transparent entry points, both offline-testable with injected
    transports:

    - ``pages`` set: an isolated Bulbapedia page run (the legacy contract
      fixtures path). It never touches Fandom.
    - ``pages`` unset: the hybrid backfill. ``sources`` selects ``fandom`` (main
      historical coverage 2017-2026), ``bulbapedia`` (contrast) or both;
      ``fandom_pages``/``bulbapedia_pages`` override the closed catalogs.

    Fetching and parsing happen before persistence, so a failed page never opens
    a transaction, while ``store_pages`` gives each valid page its own rollback
    boundary. The hybrid run logs the observable contrast counts (RF-45).
    """
    if pages is not None:
        resolved_transport = _resolve_transport(transport=transport, client=client)
        downloaded = download_pages(
            resolved_transport,
            pages=tuple(pages),
            api=api or mediawiki.DEFAULT_API,
            logger=logger,
        )
        if conn is None:
            return downloaded
        catalog = catalog or Catalog.from_conn(conn)
        records = build_bulbapedia_records(downloaded, catalog, logger=logger)
        return _consolidate_and_store(conn, records, catalog, logger=logger)

    selected = tuple(dict.fromkeys(sources))
    unknown = sorted(set(selected) - set(AVAILABLE_SOURCES))
    if unknown:
        raise ValueError(f"unknown sources: {unknown}")
    if not selected:
        raise ValueError("no sources selected")

    if conn is not None:
        catalog = catalog or Catalog.from_conn(conn)
    if catalog is None:
        raise TypeError("hybrid run() requires a catalog or a connection")

    fandom_records = []
    if FANDOM_SOURCE in selected:
        selected_fandom = FANDOM_PAGE_CATALOG if fandom_pages is None else tuple(fandom_pages)
        downloaded = download_pages(
            _fandom_transport(transport=transport, fandom_transport=fandom_transport),
            pages=selected_fandom,
            api=fandom_api,
            logger=logger,
        )
        fandom_records = build_fandom_records(downloaded, catalog, logger=logger)

    bulbapedia_records = []
    if BULBAPEDIA_SOURCE in selected:
        selected_bulbapedia = (
            HISTORICAL_PAGE_CATALOG if bulbapedia_pages is None else tuple(bulbapedia_pages)
        )
        downloaded = download_pages(
            _bulbapedia_transport(transport=transport, client=client),
            pages=selected_bulbapedia,
            api=bulbapedia_api,
            logger=logger,
        )
        bulbapedia_records = build_bulbapedia_records(downloaded, catalog, logger=logger)

    counts = contrast_counts(fandom_records, bulbapedia_records)
    log_contrast(counts, logger=logger)

    if conn is None:
        return {
            FANDOM_SOURCE: fandom_records,
            BULBAPEDIA_SOURCE: bulbapedia_records,
            "contrast": counts,
        }

    return _consolidate_and_store(
        conn, [*fandom_records, *bulbapedia_records], catalog, logger=logger
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pages",
        nargs="*",
        help=(
            "explicit pages for an isolated Bulbapedia run; omit to run the hybrid "
            "backfill selected with --source"
        ),
    )
    parser.add_argument(
        "--source",
        choices=("fandom", "bulbapedia", "both"),
        default="both",
        help=(
            "historical source selection: 'fandom' (main coverage, urllib), "
            "'bulbapedia' (contrast, httpx) or 'both'"
        ),
    )
    parser.add_argument("--api", default=mediawiki.DEFAULT_API, help="Bulbapedia API endpoint")
    parser.add_argument(
        "--fandom-api", default=mediawiki.FANDOM_API, help="Fandom API endpoint"
    )
    parser.add_argument(
        "--dsn", default=os.environ.get("RAIDS_DSN", "postgresql://raids:raids@localhost:5433/raids")
    )
    args = parser.parse_args(argv)

    import psycopg

    if args.pages:
        # Explicit pages keep the isolated legacy path (contract fixtures).
        if args.api == mediawiki.FANDOM_API:
            # Cloudflare rejects httpx on Fandom (403); stdlib urllib works (RF-38).
            with psycopg.connect(args.dsn) as conn:
                written = run(
                    conn,
                    transport=transport_module.UrllibTransport(),
                    pages=tuple(args.pages),
                    api=args.api,
                )
        else:
            with httpx.Client(headers={"User-Agent": mediawiki.USER_AGENT}) as client:
                with psycopg.connect(args.dsn) as conn:
                    written = run(
                        conn,
                        transport=transport_module.HttpxTransport(client),
                        pages=tuple(args.pages),
                        api=args.api,
                    )
        print(f"appearances written: {written}")
        return 0

    selected_sources = (
        AVAILABLE_SOURCES if args.source == "both" else (args.source,)
    )
    with httpx.Client(headers={"User-Agent": mediawiki.USER_AGENT}) as client:
        with psycopg.connect(args.dsn) as conn:
            written = run(
                conn,
                transport=transport_module.HttpxTransport(client),
                fandom_transport=transport_module.UrllibTransport(),
                fandom_api=args.fandom_api,
                bulbapedia_api=args.api,
                sources=selected_sources,
            )
    print(f"appearances written: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
