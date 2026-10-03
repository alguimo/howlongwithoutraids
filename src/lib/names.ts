import type { BossSnapshot, Language } from "./types";

export const NAME_DICTIONARIES: Record<Language, Record<string, string>> = {
  en: {},
  es: {
    "150": "Mewtwo",
    "157": "Typhlosion",
    "157-hisui": "Typhlosion de Hisui",
    "25": "Pikachu",
    "71": "Victreebel",
    "384": "Rayquaza",
    "642": "Thundurus",
    "716": "Xerneas",
  },
  fr: {
    "150": "Mewtwo",
    "71": "Empiflor",
    "71-mega": "Méga-Empiflor",
    "157-hisui": "Typhlosion de Hisui",
    "25": "Pikachu",
    "384": "Rayquaza",
    "642": "Thundurus",
    "716": "Xerneas",
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
