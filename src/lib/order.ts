import { evaluate, type Status } from "./counter";
import { localizeName } from "./names";
import type { BossSnapshot, Language } from "./types";

function group(status: Status): number {
  if (status.kind === "active") return 0;
  if (status.kind === "upcoming") return 2;
  return 1;
}

export function sortBosses(
  bosses: BossSnapshot[],
  now: Date,
  lang: Language,
): BossSnapshot[] {
  return [...bosses].sort((a, b) => {
    const statusA = evaluate(a, now);
    const statusB = evaluate(b, now);
    const groupA = group(statusA);
    const groupB = group(statusB);
    if (groupA !== groupB) return groupA - groupB;

    if (groupA === 1 && statusA.days !== statusB.days) {
      return (statusB.days ?? 0) - (statusA.days ?? 0);
    }

    return localizeName(a, lang).localeCompare(localizeName(b, lang));
  });
}
