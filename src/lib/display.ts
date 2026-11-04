import { CATALOGS, LANGUAGES, t } from "./i18n";
import { localizeName } from "./names";
import type { BossSnapshot, Language } from "./types";

/**
 * Nombre compuesto del jefe (spec 004 RF-01…RF-07, ampliado por spec 010 RF-08).
 *
 * Módulo puro: no lee el DOM ni la red. Compone `Base (Forma, Variante)` a
 * partir de la identidad del snapshot, el diccionario de nombres (`names.ts`),
 * las etiquetas de formas localizadas y el catálogo de textos (`i18n.ts`).
 */

export type NameBoss = Pick<BossSnapshot, "dex_number" | "form" | "variant" | "name">;

export const BASE_FORMS = ["normal", "hero-of-many-battles"] as const;

const BASE_FORM_SET: ReadonlySet<string> = new Set(BASE_FORMS);

export function isBaseForm(form: string): boolean {
  return BASE_FORM_SET.has(form);
}

export function baseName(boss: NameBoss, lang: Language): string {
  return localizeName(boss, lang);
}

const PUNCTUATION_FORMS: Record<string, string> = {
  exclamation: "!",
  question: "?",
};

const FORM_LABELS: Record<string, Record<Language, string>> = {
  alola: { en: "Alola", es: "Alola", fr: "Alola" },
  galar: { en: "Galar", es: "Galar", fr: "Galar" },
  hisui: { en: "Hisui", es: "Hisui", fr: "Hisui" },
  paldea: { en: "Paldea", es: "Paldea", fr: "Paldea" },
  "paldea-combat": { en: "Paldea Combat", es: "Paldea Combativa", fr: "Paldea Combative" },
  "paldea-blaze": { en: "Paldea Blaze", es: "Paldea Ardiente", fr: "Paldea Flamboyante" },
  "paldea-aqua": { en: "Paldea Aqua", es: "Paldea Acuática", fr: "Paldea Aquatique" },
  origin: { en: "Origin", es: "Origen", fr: "Origine" },
  altered: { en: "Altered", es: "Modificada", fr: "Alternative" },
  modified: { en: "Altered", es: "Modificada", fr: "Alternative" },
  crowned: { en: "Crowned", es: "Suprema", fr: "Suprême" },
  "dawn-wings": { en: "Dawn Wings", es: "Alas del Alba", fr: "Ailes de l'Aurore" },
  "dusk-mane": { en: "Dusk Mane", es: "Melena Crepuscular", fr: "Crinière du Couchant" },
  incarnate: { en: "Incarnate", es: "Avatar", fr: "Avatar" },
  therian: { en: "Therian", es: "Tótem", fr: "Totémique" },
  attack: { en: "Attack", es: "Ataque", fr: "Attaque" },
  defense: { en: "Defense", es: "Defensa", fr: "Défense" },
  speed: { en: "Speed", es: "Velocidad", fr: "Vitesse" },
  "burn-drive": { en: "Burn Drive", es: "PiroROM", fr: "Module Pyro" },
  "chill-drive": { en: "Chill Drive", es: "CrioROM", fr: "Module Cryo" },
  "douse-drive": { en: "Douse Drive", es: "HidroROM", fr: "Module Aqua" },
  "shock-drive": { en: "Shock Drive", es: "FulgoROM", fr: "Module Choc" },
  curly: { en: "Curly", es: "Curvada", fr: "Courbée" },
  droopy: { en: "Droopy", es: "Lánguida", fr: "Affalée" },
  stretchy: { en: "Stretchy", es: "Recta", fr: "Raide" },
  east: { en: "East Sea", es: "Mar Este", fr: "Mer Orient" },
  west: { en: "West Sea", es: "Mar Oeste", fr: "Mer Occident" },
  male: { en: "Male", es: "Macho", fr: "Mâle" },
  female: { en: "Female", es: "Hembra", fr: "Femelle" },
  natural: { en: "Natural", es: "Natural", fr: "Naturelle" },
  disguised: { en: "Disguised", es: "Disfraz", fr: "Déguisée" },
};

/** Capitaliza cada segmento separando por espacios (sin guiones crudos de BD). */
function presentationCase(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part[0]!.toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Etiqueta de **forma** localizada en `lang` sin guiones técnicos (010 RF-08).
 * Devuelve `null` si es una forma base (004 RF-06).
 */
export function formLabel(form: string, lang: Language = "en"): string | null {
  if (!form || isBaseForm(form)) return null;
  if (form in PUNCTUATION_FORMS) return PUNCTUATION_FORMS[form]!;
  const entry = FORM_LABELS[form];
  if (entry) return entry[lang] ?? entry.en;
  return presentationCase(form);
}

const VARIANT_KEYS: Record<string, string> = {
  MEGA: "variant_mega",
  SHADOW: "variant_shadow",
  PRIMAL: "variant_primal",
  APEX: "variant_apex",
};

const EXTRA_VARIANT_SYNONYMS: Record<string, readonly string[]> = {
  SHADOW: ["sombra"],
};

export function variantLabel(lang: Language, variant: string): string | null {
  if (!variant || variant === "NORMAL") return null;
  const key = VARIANT_KEYS[variant];
  if (!key) return null;
  const label = t(lang, key);
  return label === key ? null : label;
}

function normalizeLabel(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function containsWord(haystack: string, needle: string): boolean {
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(haystack);
}

function formSynonyms(form: string): string[] {
  const synonyms = new Set<string>([
    normalizeLabel(form),
    normalizeLabel(form.replace(/-/g, " ")),
  ]);
  const entry = FORM_LABELS[form];
  if (entry) {
    for (const lang of LANGUAGES) {
      if (entry[lang]) synonyms.add(normalizeLabel(entry[lang]));
    }
  }
  return [...synonyms];
}

function variantSynonyms(variant: string): string[] {
  const synonyms = new Set<string>();
  const key = VARIANT_KEYS[variant];
  if (key) {
    for (const lang of LANGUAGES) {
      const label = CATALOGS[lang][key];
      if (label) synonyms.add(normalizeLabel(label));
    }
  }
  for (const extra of EXTRA_VARIANT_SYNONYMS[variant] ?? []) {
    synonyms.add(normalizeLabel(extra));
  }
  return [...synonyms];
}

function alreadyHasLabel(
  labels: readonly string[],
  sources: readonly string[],
): boolean {
  const haystacks = sources.map(normalizeLabel);
  return labels.some((label) => {
    const needle = normalizeLabel(label);
    return needle.length > 0 && haystacks.some((h) => containsWord(h, needle));
  });
}

export function displayName(boss: NameBoss, lang: Language): string {
  const base = baseName(boss, lang);
  const sources = [base];

  const labels: string[] = [];

  const form = formLabel(boss.form, lang);
  if (form && !alreadyHasLabel(formSynonyms(boss.form), sources)) {
    labels.push(form);
  }

  const variant = variantLabel(lang, boss.variant);
  if (variant && !alreadyHasLabel(variantSynonyms(boss.variant), sources)) {
    labels.push(variant);
  }

  return labels.length > 0 ? `${base} (${labels.join(", ")})` : base;
}
