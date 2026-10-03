import { evaluate, type StatusKind } from "./counter";
import { t } from "./i18n";
import { localizeName } from "./names";
import type { BossSnapshot, Language } from "./types";

export interface RowView {
  name: string;
  kind: StatusKind;
  days: number | null;
  upcoming: boolean;
  dateISO: string | null;
  statusText: string;
}

export interface DetailLine {
  label: string;
  iso: string;
  event: boolean;
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
    const key = status.days === 1 ? "day" : "days";
    statusText = t(lang, key, { n: status.days ?? 0 });
  }

  const dateISO =
    status.kind === "active"
      ? boss.current_end
      : status.kind === "upcoming"
        ? boss.current_start
        : boss.last_end_date;

  return {
    name: localizeName(boss, lang),
    kind: status.kind,
    days: status.days,
    upcoming: status.upcoming,
    dateISO,
    statusText,
  };
}

export function detailLines(
  boss: BossSnapshot,
  now: Date,
  lang: Language,
): DetailLine[] {
  const lines: DetailLine[] = [];

  if (boss.last_regular_end_date) {
    lines.push({ label: t(lang, "last_regular"), iso: boss.last_regular_end_date, event: false });
  }
  if (boss.last_special_event_end_date) {
    lines.push({ label: t(lang, "last_special"), iso: boss.last_special_event_end_date, event: true });
  }
  if (boss.current_start && boss.current_end) {
    const label =
      new Date(boss.current_start).getTime() > now.getTime()
        ? t(lang, "next_window")
        : t(lang, "current_window");
    lines.push({ label, iso: boss.current_start, event: false });
  }

  return lines;
}
