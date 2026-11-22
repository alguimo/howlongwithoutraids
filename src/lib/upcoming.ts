import { calendarDaysBetween, effectiveLastEndDate } from "./counter";
import { baseName, displayName } from "./display";
import { eggSvg, tierBadgeStyles, tierToEggType } from "./eggs";
import {
  assetUrl,
  droughtSeverityClass,
  escapeHtml,
  formatDate,
  formatDexNumber,
  formatTier,
  initials,
} from "./html";
import { t } from "./i18n";
import type { BossSnapshot, Language } from "./types";
import { formatDayCount } from "./view";

export type ViewTab = "history" | "upcoming";

export function parseViewTab(search: string): ViewTab {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return params.get("tab") === "upcoming" ? "upcoming" : "history";
}

export function isUpcomingBoss(boss: BossSnapshot, now: Date): boolean {
  return !!boss.current_start && new Date(boss.current_start).getTime() > now.getTime();
}

export function daysUntilStart(startISO: string, now: Date): number {
  return Math.max(0, -calendarDaysBetween(startISO, now));
}

export function upcomingBosses(
  bosses: readonly BossSnapshot[],
  now: Date,
  lang: Language,
): BossSnapshot[] {
  return bosses
    .filter((boss) => isUpcomingBoss(boss, now))
    .sort((a, b) => {
      const diff =
        new Date(a.current_start!).getTime() - new Date(b.current_start!).getTime();
      if (diff !== 0) return diff;
      return displayName(a, lang).localeCompare(displayName(b, lang));
    });
}

function countdownLabel(startISO: string, now: Date, lang: Language): string {
  const days = daysUntilStart(startISO, now);
  if (days === 0) return t(lang, "starts_today");
  if (days === 1) return t(lang, "starts_in_day");
  return t(lang, "starts_in_days", { n: formatDayCount(days, lang) });
}

function returnAfterHtml(boss: BossSnapshot, now: Date, lang: Language): string {
  const endISO = effectiveLastEndDate(boss, now);
  if (!endISO) {
    return `<span class="status-badge status-badge-upcoming inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">${escapeHtml(t(lang, "debut_badge"))}</span>`;
  }
  const days = Math.max(0, calendarDaysBetween(endISO, now));
  const severity = droughtSeverityClass(days);
  const label =
    days === 1
      ? t(lang, "after_day")
      : t(lang, "after_days", { n: formatDayCount(days, lang) });
  return `<span class="drought-value ${severity} tabular-nums">${escapeHtml(label)}</span>`;
}

export function upcomingTableHtml(
  bosses: readonly BossSnapshot[],
  now: Date,
  lang: Language,
): string {
  if (bosses.length === 0) {
    return `<p class="upcoming-empty rounded-lg px-4 py-8 text-center text-sm">${escapeHtml(t(lang, "no_upcoming"))}</p>`;
  }

  const headCell =
    'scope="col" class="table-head-cell px-3 py-1.5 text-xs font-medium uppercase tracking-wide';
  const head = `<thead><tr>
    <th ${headCell} text-left"><span class="sr-only">${escapeHtml(t(lang, "col_image"))}</span></th>
    <th ${headCell} text-left">${escapeHtml(t(lang, "col_name"))}</th>
    <th ${headCell} text-left">${escapeHtml(t(lang, "upcoming_col_window"))}</th>
    <th ${headCell} text-left md:text-right">${escapeHtml(t(lang, "upcoming_col_drought"))}</th>
    <th ${headCell} text-left">${escapeHtml(t(lang, "col_tier"))}</th>
  </tr></thead>`;

  const rows = bosses
    .map((boss) => {
      const name = displayName(boss, lang);
      const fallback = (hidden: boolean) =>
        `<span role="img" aria-label="${escapeHtml(name)}" class="${hidden ? "hidden " : ""}boss-initials flex h-9 w-9 items-center justify-center rounded-lg text-xs font-semibold">${escapeHtml(initials(baseName(boss, lang)))}</span>`;
      const avatar = boss.sprite_url
        ? `<img src="${escapeHtml(assetUrl(boss.sprite_url))}" alt="${escapeHtml(name)}" width="36" height="36" decoding="async" onerror="this.classList.add('hidden');this.nextElementSibling?.classList.remove('hidden')" class="boss-sprite h-9 w-9 object-contain" />${fallback(true)}`
        : fallback(false);

      const startISO = boss.current_start!;
      const startText = formatDate(startISO, lang);
      const endText = boss.current_end ? formatDate(boss.current_end, lang) : null;
      const dateRange =
        endText && endText !== startText ? `${startText} – ${endText}` : startText;
      const countdown = countdownLabel(startISO, now, lang);
      const eventLine = boss.current_event_name
        ? `<span class="upcoming-event block text-xs">${escapeHtml(boss.current_event_name)}</span>`
        : "";

      const rawTier = boss.tier ?? boss.last_tier;
      const formattedTier = formatTier(rawTier, lang);
      const eggType = tierToEggType(rawTier);
      const styles = tierBadgeStyles(eggType);
      const eggIcon = eggType ? eggSvg(eggType, "h-3.5 w-3.5 shrink-0") : "";
      const tierCell = formattedTier
        ? `<span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles.badge}">${eggIcon}<span>${escapeHtml(formattedTier)}</span></span>`
        : "";

      return `<tr class="boss-row align-middle">
        <td class="px-2.5 py-1.5" data-label="${escapeHtml(t(lang, "col_image"))}">${avatar}</td>
        <td class="boss-name-cell px-2.5 py-1.5 font-medium" data-label="${escapeHtml(t(lang, "col_name"))}"><span class="dex-num mr-1.5 text-xs font-normal tabular-nums"><span class="dex-hash">#</span>${formatDexNumber(boss.dex_number)}</span>${escapeHtml(name)}</td>
        <td class="px-2.5 py-1.5 text-sm" data-label="${escapeHtml(t(lang, "upcoming_col_window"))}"><span class="inline-flex flex-wrap items-baseline gap-x-2 gap-y-0.5"><span class="upcoming-countdown font-medium tabular-nums">${escapeHtml(countdown)}</span><span class="upcoming-range text-xs tabular-nums">${escapeHtml(dateRange)}</span></span>${eventLine}</td>
        <td class="px-2.5 py-1.5 text-sm md:text-right" data-label="${escapeHtml(t(lang, "upcoming_col_drought"))}">${returnAfterHtml(boss, now, lang)}</td>
        <td class="px-2.5 py-1.5 text-xs" data-label="${escapeHtml(t(lang, "col_tier"))}">${tierCell}</td>
      </tr>`;
    })
    .join("");

  return `<div class="overflow-x-auto"><table class="w-full border-collapse">${head}<tbody>${rows}</tbody></table></div>`;
}
