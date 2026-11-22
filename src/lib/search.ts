import { matchCategory, matchesCategory } from "./categories";
import { baseName, displayName, isBaseForm } from "./display";
import { normalizeText } from "./text";
import type { BossSnapshot, Language } from "./types";

export const normalize = normalizeText;

/**
 * ¿Coincide el jefe con la consulta? (004 RF-11, RF-14, RF-15; 010 RF-08)
 */
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

  const category = matchCategory(query_);
  if (category && matchesCategory(boss, category)) {
    return true;
  }

  const formSlugMatch =
    !isBaseForm(boss.form) &&
    (normalize(boss.form).includes(query_) ||
      normalize(boss.form.replace(/-/g, " ")).includes(query_));

  return (
    formSlugMatch ||
    normalize(baseName(boss, lang)).includes(query_) ||
    normalize(boss.name).includes(query_) ||
    normalize(displayName(boss, lang)).includes(query_)
  );
}
