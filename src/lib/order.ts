import { effectiveLastEndDate, isActive } from "./counter";
import { displayName } from "./display";
import type { BossSnapshot, Language } from "./types";

export const SORT_MODES = ["recent", "drought", "dex", "name"] as const;
export type SortMode = (typeof SORT_MODES)[number];

const SORT_MODE_SET: ReadonlySet<string> = new Set(SORT_MODES);

export function isSortMode(value: unknown): value is SortMode {
  return typeof value === "string" && SORT_MODE_SET.has(value);
}

function byIdentity(a: BossSnapshot, b: BossSnapshot): number {
  if (a.dex_number !== b.dex_number) return a.dex_number - b.dex_number;
  if (a.form !== b.form) return a.form.localeCompare(b.form);
  return a.variant.localeCompare(b.variant);
}

function byDisplayName(a: BossSnapshot, b: BossSnapshot, lang: Language): number {
  const cmp = displayName(a, lang).localeCompare(displayName(b, lang));
  return cmp !== 0 ? cmp : byIdentity(a, b);
}

function compareRecent(
  a: BossSnapshot,
  b: BossSnapshot,
  now: Date,
  lang: Language,
): number {
  const activeA = isActive(a, now);
  const activeB = isActive(b, now);
  if (activeA !== activeB) return activeA ? -1 : 1;
  if (activeA && activeB) return byDisplayName(a, b, lang);

  const endA = effectiveLastEndDate(a, now);
  const endB = effectiveLastEndDate(b, now);
  if (endA && endB) {
    const diff = new Date(endB).getTime() - new Date(endA).getTime();
    if (diff !== 0) return diff;
  } else if (endA) {
    return -1;
  } else if (endB) {
    return 1;
  }
  return byDisplayName(a, b, lang);
}

function droughtBucket(boss: BossSnapshot, now: Date): { rank: number; endMs: number } {
  if (isActive(boss, now)) return { rank: 1, endMs: 0 };
  const endISO = effectiveLastEndDate(boss, now);
  if (endISO !== null) return { rank: 0, endMs: new Date(endISO).getTime() };
  return { rank: 2, endMs: 0 };
}

function compareDrought(
  a: BossSnapshot,
  b: BossSnapshot,
  now: Date,
  lang: Language,
): number {
  const bucketA = droughtBucket(a, now);
  const bucketB = droughtBucket(b, now);
  if (bucketA.rank !== bucketB.rank) return bucketA.rank - bucketB.rank;
  if (bucketA.rank === 0 && bucketA.endMs !== bucketB.endMs) {
    return bucketA.endMs - bucketB.endMs;
  }
  return byDisplayName(a, b, lang);
}

export function sortBosses(
  bosses: BossSnapshot[],
  now: Date,
  lang: Language,
  mode: SortMode = "recent",
): BossSnapshot[] {
  return [...bosses].sort((a, b) => {
    if (mode === "drought") return compareDrought(a, b, now, lang);
    if (mode === "dex") {
      return a.dex_number !== b.dex_number
        ? a.dex_number - b.dex_number
        : byDisplayName(a, b, lang);
    }
    if (mode === "name") return byDisplayName(a, b, lang);
    return compareRecent(a, b, now, lang);
  });
}
