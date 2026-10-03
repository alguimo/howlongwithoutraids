import type { BossSnapshot } from "./types";

export type StatusKind = "active" | "drought" | "ended_today" | "upcoming";

export interface Status {
  kind: StatusKind;
  days: number | null;
  upcoming: boolean;
}

const DAY_MS = 86_400_000;

function localDateMs(date: Date): number {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
}

export function calendarDaysBetween(fromISO: string, now: Date): number {
  return Math.round((localDateMs(now) - localDateMs(new Date(fromISO))) / DAY_MS);
}

export function isActive(boss: BossSnapshot, now: Date): boolean {
  if (!boss.current_start || !boss.current_end) return false;
  const start = new Date(boss.current_start).getTime();
  const end = new Date(boss.current_end).getTime();
  return start <= now.getTime() && now.getTime() < end;
}

export function evaluate(boss: BossSnapshot, now: Date): Status {
  if (isActive(boss, now)) {
    return { kind: "active", days: 0, upcoming: false };
  }

  const upcoming =
    !!boss.current_start && new Date(boss.current_start).getTime() > now.getTime();

  if (boss.last_end_date) {
    const days = calendarDaysBetween(boss.last_end_date, now);
    return { kind: days === 0 ? "ended_today" : "drought", days, upcoming };
  }

  return { kind: "upcoming", days: null, upcoming: true };
}
