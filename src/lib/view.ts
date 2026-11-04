import { effectiveLastEndDate, evaluate, type StatusKind } from "./counter";
import { displayName } from "./display";
import { t } from "./i18n";
import type { BossSnapshot, Language } from "./types";

export interface RowView {
  name: string;
  kind: StatusKind;
  days: number | null;
  upcoming: boolean;
  dateISO: string | null;
  statusText: string;
  approxYearsText: string | null;
}

export interface DetailLine {
  label: string;
  iso: string;
  event: boolean;
  /** Nombre del evento de esa aparición o de la ventana vigente/próxima. */
  eventName: string | null;
}

export function formatDayCount(days: number, lang: Language): string {
  return new Intl.NumberFormat(lang, { useGrouping: "always" }).format(days);
}

export function formatApproxYears(days: number | null, lang: Language): string | null {
  if (days === null || days < 365) return null;
  const raw = days / 365.25;
  const rounded = raw >= 5 ? Math.round(raw) : Math.round(raw * 2) / 2;
  const formatted = new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(rounded);
  return t(lang, "approx_years", { y: formatted });
}

export function rowView(boss: BossSnapshot, now: Date, lang: Language): RowView {
  const status = evaluate(boss, now);

  let statusText: string;
  if (status.kind === "active") {
    statusText = t(lang, "active_now");
  } else if (status.kind === "ended_today") {
    statusText = t(lang, "ended_today");
  } else if (status.kind === "upcoming") {
    statusText = t(lang, "upcoming");
  } else {
    const count = status.days ?? 0;
    const key = count === 1 ? "day" : "days";
    statusText = t(lang, key, { n: formatDayCount(count, lang) });
  }

  const dateISO =
    status.kind === "active"
      ? boss.current_end
      : status.kind === "upcoming"
        ? boss.current_start
        : effectiveLastEndDate(boss, now);

  const approxYearsText =
    status.kind === "drought" ? formatApproxYears(status.days, lang) : null;

  return {
    name: displayName(boss, lang),
    kind: status.kind,
    days: status.days,
    upcoming: status.upcoming,
    dateISO,
    statusText,
    approxYearsText,
  };
}

export function detailLines(
  boss: BossSnapshot,
  now: Date,
  lang: Language,
): DetailLine[] {
  const lines: DetailLine[] = [];

  if (boss.last_regular_end_date) {
    lines.push({
      label: t(lang, "last_regular"),
      iso: boss.last_regular_end_date,
      event: false,
      eventName: boss.last_regular_event_name,
    });
  }
  if (boss.last_special_event_end_date) {
    lines.push({
      label: t(lang, "last_special"),
      iso: boss.last_special_event_end_date,
      event: true,
      eventName: boss.last_special_event_name,
    });
  }
  if (boss.current_start && boss.current_end) {
    const startMs = new Date(boss.current_start).getTime();
    const endMs = new Date(boss.current_end).getTime();
    const nowMs = now.getTime();
    if (startMs > nowMs) {
      lines.push({
        label: t(lang, "next_window"),
        iso: boss.current_start,
        event: false,
        eventName: boss.current_event_name,
      });
    } else if (endMs > nowMs) {
      lines.push({
        label: t(lang, "current_window"),
        iso: boss.current_start,
        event: false,
        eventName: boss.current_event_name,
      });
    } else {
      lines.push({
        label: t(lang, "last_window"),
        iso: boss.current_end,
        event: false,
        eventName: boss.current_event_name,
      });
    }
  }

  return lines;
}
