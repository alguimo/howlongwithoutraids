import speciesNames from "../data/species-names.json";
import type { BossSnapshot, Language } from "./types";

const MANUAL_OVERRIDES: Record<Language, Record<string, string>> = {
  en: {},
  es: {
    "157-hisui": "Typhlosion de Hisui",
  },
  fr: {
    "71-mega": "Méga-Empiflor",
    "157-hisui": "Typhlosion de Hisui",
  },
};

export const NAME_DICTIONARIES: Record<Language, Record<string, string>> = {
  en: {},
  es: {
    ...(speciesNames as { es: Record<string, string>; fr: Record<string, string> }).es,
    ...MANUAL_OVERRIDES.es,
  },
  fr: {
    ...(speciesNames as { es: Record<string, string>; fr: Record<string, string> }).fr,
    ...MANUAL_OVERRIDES.fr,
  },
};

export function nameKey(boss: Pick<BossSnapshot, "dex_number" | "form" | "variant">): string {
  let key = String(boss.dex_number);
  const form = boss.form && boss.form !== "normal" ? boss.form : null;
  const variant = boss.variant && boss.variant !== "NORMAL" ? boss.variant.toLowerCase() : null;
  if (form) key += `-${form}`;
  if (variant) key += `-${variant}`;
  return key;
}

export function localizeName(
  boss: Pick<BossSnapshot, "dex_number" | "form" | "variant" | "name">,
  lang: Language,
): string {
  if (lang === "en") return boss.name;
  const dictionary = NAME_DICTIONARIES[lang] ?? {};
  return (
    dictionary[nameKey(boss)] ??
    dictionary[String(boss.dex_number)] ??
    boss.name
  );
}
