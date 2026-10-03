import { localizeName } from "./names";
import type { BossSnapshot, Language } from "./types";

export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function matches(
  boss: BossSnapshot,
  query: string,
  lang: Language,
): boolean {
  const query_ = normalize(query).trim();
  if (!query_) return true;

  if (/^\d+$/.test(query_) && String(boss.dex_number).startsWith(query_)) {
    return true;
  }

  return (
    normalize(localizeName(boss, lang)).includes(query_) ||
    normalize(boss.name).includes(query_)
  );
}
