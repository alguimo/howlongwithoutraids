import { baseName } from "./display";
import { eggSvg, tierBadgeStyles, tierToEggType } from "./eggs";
import { t } from "./i18n";
import type { SortMode } from "./order";
import type { PageState } from "./pagination";
import type { BossSnapshot, Language } from "./types";
import { detailLines, rowView } from "./view";

export function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
  );
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0]!.slice(0, 2).toUpperCase();
  return (words[0]![0]! + words[1]![0]!).toUpperCase();
}

export function formatDexNumber(dex: number): string {
  return String(Math.max(0, Math.trunc(dex))).padStart(4, "0");
}

export function droughtSeverityClass(days: number): string {
  if (days >= 730) return "drought-extreme";
  if (days >= 365) return "drought-long";
  if (days >= 90) return "drought-medium";
  return "drought-mild";
}

export function formatDate(iso: string, lang: Language): string {
  return new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeZone: "UTC" }).format(
    new Date(iso),
  );
}

export function footerUpdatedText(exportedAt: string | null, lang: Language): string | null {
  if (exportedAt === null) return null;
  return t(lang, "footer_updated", { date: formatDate(exportedAt, lang) });
}

/** Id del nodo único de detalle de un jefe (RF-39). */
export function detailRowId(key: string): string {
  return `detail-${key}`;
}

const HEAD_CELL_BASE =
  'scope="col" role="columnheader" class="table-head-cell px-3 py-1.5 text-xs font-medium uppercase tracking-wide';
const HEAD_CELL = `${HEAD_CELL_BASE} text-left"`;
const HEAD_CELL_RIGHT = `${HEAD_CELL_BASE} text-left md:text-right"`;

export function tableHeadHtml(lang: Language = "en", sort: SortMode = "recent"): string {
  const spriteHeader = `<th ${HEAD_CELL}><span class="sr-only">${escapeHtml(t(lang, "col_image"))}</span></th>`;

  const nameSortState = sort === "name" ? "ascending" : "none";
  const nameGlyph = sort === "name" ? " ↑" : "";
  const nameHeader = `<th ${HEAD_CELL} aria-sort="${nameSortState}"><button type="button" data-sort-col="name" class="sort-head-btn inline-flex items-center gap-1 uppercase tracking-wide">${escapeHtml(t(lang, "col_name"))}<span aria-hidden="true">${nameGlyph}</span></button></th>`;

  const statusSortState =
    sort === "drought" ? "descending" : sort === "recent" ? "ascending" : "none";
  const statusGlyph = sort === "drought" ? " ↓" : sort === "recent" ? " ↑" : "";
  const statusHeader = `<th ${HEAD_CELL_RIGHT} aria-sort="${statusSortState}"><button type="button" data-sort-col="status" class="sort-head-btn inline-flex items-center gap-1 uppercase tracking-wide">${escapeHtml(t(lang, "col_status"))}<span aria-hidden="true">${statusGlyph}</span></button></th>`;

  const dateHeader = `<th ${HEAD_CELL_RIGHT}>${escapeHtml(t(lang, "col_date"))}</th>`;
  const tierHeader = `<th ${HEAD_CELL}>${escapeHtml(t(lang, "col_tier"))}</th>`;

  return `<tr role="row">${spriteHeader}${nameHeader}${statusHeader}${dateHeader}${tierHeader}</tr>`;
}

export function formatTier(tier: string | null | undefined, lang: Language): string {
  if (!tier) return "";
  const key = `tier_${tier.toLowerCase()}`;
  const label = t(lang, key);
  return label === key ? tier : label;
}

function detailHtml(boss: BossSnapshot, now: Date, lang: Language): string {
  const lines = detailLines(boss, now, lang);
  if (lines.length === 0) return "";
  const body = lines
    .map((line) => {
      const eventName = line.eventName
        ? ` <span class="detail-event-name">${escapeHtml(line.eventName)}</span>`
        : "";
      const eventTag = line.event
        ? ` <span class="detail-event-tag rounded px-1.5 py-0.5 text-xs">${escapeHtml(t(lang, "event_tag"))}</span>`
        : "";
      return `<div class="flex items-center justify-between gap-3 py-0.5 text-sm detail-line"><span>${escapeHtml(line.label)}${eventName}${eventTag}</span><span class="tabular-nums">${escapeHtml(formatDate(line.iso, lang))}</span></div>`;
    })
    .join("");
  const countLine = `<div class="flex items-center justify-between gap-3 py-0.5 text-sm detail-line"><span>${escapeHtml(t(lang, "appearances_label"))}</span><span class="tabular-nums font-medium detail-count">${boss.appearance_count}</span></div>`;
  return `<div class="flex flex-wrap gap-x-8">${body}${countLine}</div>`;
}

export function rowHtml(boss: BossSnapshot, now: Date, lang: Language): string {
  const view = rowView(boss, now, lang);
  const key = `${boss.dex_number}-${boss.form}-${boss.variant}`.toLowerCase();
  const detailId = detailRowId(key);
  const rawDate = view.dateISO ? formatDate(view.dateISO, lang) : "";
  const dateLabel = !rawDate
    ? ""
    : view.kind === "active"
      ? t(lang, "date_until", { date: rawDate })
      : view.kind === "upcoming"
        ? t(lang, "date_from", { date: rawDate })
        : rawDate;

  const initialsFallback = (hidden = false): string =>
    `<span role="img" aria-label="${escapeHtml(view.name)}" class="${hidden ? "hidden " : ""}boss-initials flex h-9 w-9 items-center justify-center rounded-lg text-xs font-semibold">${escapeHtml(initials(baseName(boss, lang)))}</span>`;

  const avatar = boss.sprite_url
    ? `<img src="${escapeHtml(boss.sprite_url)}" alt="${escapeHtml(view.name)}" width="36" height="36" decoding="async" onerror="this.classList.add('hidden');this.nextElementSibling?.classList.remove('hidden')" class="boss-sprite h-9 w-9 object-contain" />${initialsFallback(true)}`
    : initialsFallback(false);

  let statusContent: string;
  if (view.kind === "active") {
    statusContent = `<span class="status-badge status-badge-active inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"><span class="status-dot-active h-1.5 w-1.5 rounded-full" aria-hidden="true"></span>${escapeHtml(view.statusText)}</span>`;
  } else if (view.kind === "upcoming") {
    statusContent = `<span class="status-badge status-badge-upcoming inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium">${escapeHtml(view.statusText)}</span>`;
  } else if (view.kind === "drought") {
    const severity = droughtSeverityClass(view.days ?? 0);
    const yearsBadge = view.approxYearsText
      ? `<span class="drought-years text-xs font-normal">${escapeHtml(view.approxYearsText)}</span>`
      : "";
    statusContent = `<span class="inline-flex items-baseline gap-1.5"><span class="drought-value ${severity} tabular-nums">${escapeHtml(view.statusText)}</span>${yearsBadge}</span>`;
  } else {
    statusContent = `<span class="drought-value drought-mild tabular-nums">${escapeHtml(view.statusText)}</span>`;
  }

  const upcomingEgg = tierToEggType(boss.tier);
  const upcomingEggIcon = upcomingEgg ? eggSvg(upcomingEgg, "h-3 w-3 shrink-0") : "";
  const upcomingTag =
    view.upcoming && view.kind !== "upcoming"
      ? `<span class="status-badge status-badge-upcoming inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium">${upcomingEggIcon}${escapeHtml(t(lang, "upcoming"))}</span>`
      : "";

  const rawTier = boss.tier ?? boss.last_tier;
  const formattedTier = formatTier(rawTier, lang);
  const eggType = tierToEggType(rawTier);
  const styles = tierBadgeStyles(eggType);
  const eggIcon = eggType ? eggSvg(eggType, "h-3.5 w-3.5 shrink-0") : "";
  const tierCell = formattedTier
    ? `<span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles.badge}">${eggIcon}<span>${escapeHtml(formattedTier)}</span></span>`
    : "";

  return `<tr class="boss-row align-middle" role="row">
  <td role="cell" class="px-2.5 py-1" data-label="${escapeHtml(t(lang, "col_image"))}">${avatar}</td>
  <td role="cell" class="boss-name-cell px-2.5 py-1 font-medium" data-label="${escapeHtml(t(lang, "col_name"))}"><span class="dex-num mr-1.5 text-xs font-normal tabular-nums"><span class="dex-hash">#</span>${formatDexNumber(boss.dex_number)}</span>${escapeHtml(view.name)}</td>
  <td role="cell" class="px-2.5 py-1 text-sm md:text-right" data-label="${escapeHtml(t(lang, "col_status"))}"><span class="flex items-center gap-2 md:justify-end">${statusContent}${upcomingTag}</span></td>
  <td role="cell" class="px-2.5 py-1 text-sm md:text-right" data-label="${escapeHtml(t(lang, "col_date"))}">
    <button type="button" data-detail aria-expanded="false" aria-controls="${detailId}" class="date-trigger underline decoration-dotted underline-offset-4 outline-none">${escapeHtml(dateLabel)}</button>
  </td>
  <td role="cell" class="px-2.5 py-1 text-xs" data-label="${escapeHtml(t(lang, "col_tier"))}">${tierCell}</td>
 </tr>
<tr id="${detailId}" class="detail-row hidden" role="row"><td role="cell" colspan="5" class="px-3 pb-2.5 pt-0">${detailHtml(boss, now, lang)}</td></tr>`;
}

export function listHtml(
  bosses: BossSnapshot[],
  now: Date,
  lang: Language,
): string {
  return bosses.map((boss) => rowHtml(boss, now, lang)).join("");
}

const PAGER_BUTTON =
  "pager-btn inline-flex h-9 min-w-9 items-center justify-center gap-1 rounded-md px-2.5 text-sm outline-none transition-colors disabled:cursor-not-allowed";

export interface PaginationView {
  label: string;
  firstLabel: string;
  prevLabel: string;
  nextLabel: string;
  lastLabel: string;
  range: string;
  firstDisabled: boolean;
  prevDisabled: boolean;
  nextDisabled: boolean;
  lastDisabled: boolean;
  empty: boolean;
}

export function paginationView(state: PageState, lang: Language): PaginationView {
  const { page, pages, total } = state;
  const atStart = page <= 1;
  const atEnd = pages <= 1 || page >= pages;
  return {
    label: t(lang, "pagination"),
    firstLabel: t(lang, "first_page"),
    prevLabel: t(lang, "prev_page"),
    nextLabel: t(lang, "next_page"),
    lastLabel: t(lang, "last_page"),
    range: t(lang, "page_range", { from: state.from, to: state.to, total }),
    firstDisabled: atStart,
    prevDisabled: atStart,
    nextDisabled: atEnd,
    lastDisabled: atEnd,
    empty: total === 0,
  };
}

const CHEVRON_FIRST = `<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M15.79 14.77a.75.75 0 01-1.06.02l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 111.04 1.08L11.832 10l3.938 3.71a.75.75 0 01.02 1.06zm-6 0a.75.75 0 01-1.06.02l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 111.04 1.08L5.832 10l3.938 3.71a.75.75 0 01.02 1.06z" clip-rule="evenodd" /></svg>`;
const CHEVRON_PREV = `<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" /></svg>`;
const CHEVRON_NEXT = `<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>`;
const CHEVRON_LAST = `<svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M4.21 5.23a.75.75 0 011.06-.02l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.04-1.08L8.168 10 4.23 6.29a.75.75 0 01-.02-1.06zm6 0a.75.75 0 011.06-.02l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.04-1.08L14.168 10l-3.938-3.71a.75.75 0 01-.02-1.06z" clip-rule="evenodd" /></svg>`;

export function paginationHtml(state: PageState, lang: Language): string {
  const view = paginationView(state, lang);
  const button = (
    which: "first" | "prev" | "next" | "last",
    label: string,
    disabled: boolean,
    glyph: string,
  ) =>
    `<button type="button" data-page-${which} aria-label="${escapeHtml(label)}" class="${PAGER_BUTTON}"${disabled ? " disabled" : ""}><span aria-hidden="true">${glyph}</span></button>`;

  return `<nav id="pagination" aria-label="${escapeHtml(view.label)}" class="mt-3 flex items-center justify-between gap-2">
  <div class="flex items-center gap-1.5">
    ${button("first", view.firstLabel, view.firstDisabled, CHEVRON_FIRST)}
    ${button("prev", view.prevLabel, view.prevDisabled, CHEVRON_PREV)}
  </div>
  <span data-page-range aria-live="polite" class="page-range text-sm tabular-nums">${escapeHtml(view.range)}</span>
  <div class="flex items-center gap-1.5">
    ${button("next", view.nextLabel, view.nextDisabled, CHEVRON_NEXT)}
    ${button("last", view.lastLabel, view.lastDisabled, CHEVRON_LAST)}
  </div>
</nav>`;
}
