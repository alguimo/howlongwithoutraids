import { CATALOGS, LANGUAGES, t } from "./i18n";
import { localizeName } from "./names";
import type { BossSnapshot, Language } from "./types";

/**
 * Nombre compuesto del jefe (spec 004, RF-01…RF-07).
 *
 * Módulo puro: no lee el DOM ni la red. Compone `Base (Forma, Variante)` a
 * partir de la identidad del snapshot, el diccionario de nombres (`names.ts`)
 * y el catálogo de textos (`i18n.ts`). Ninguna etiqueta sale del snapshot.
 */

/** Campos que necesita la composición del nombre. */
export type NameBoss = Pick<BossSnapshot, "dex_number" | "form" | "variant" | "name">;

/**
 * Formas base que **no** se etiquetan. `normal` es la especie por defecto y
 * `hero-of-many-battles` la forma base de Zacian/Zamazenta: se muestran como
 * `Zacian`/`Zamazenta`, sin paréntesis. Ampliar esta lista es un cambio de spec.
 */
export const BASE_FORMS = ["normal", "hero-of-many-battles"] as const;

const BASE_FORM_SET: ReadonlySet<string> = new Set(BASE_FORMS);

/** ¿Es una forma base (no se etiqueta)? */
export function isBaseForm(form: string): boolean {
  return BASE_FORM_SET.has(form);
}

/** Nombre base localizado de la especie (repliegue de 002 RF-16, vía `names.ts`). */
export function baseName(boss: NameBoss, lang: Language): string {
  return localizeName(boss, lang);
}

/** Primera letra de cada segmento en mayúscula, conservando los guiones. */
function presentationCase(slug: string): string {
  return slug
    .split("-")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join("-");
}

/**
 * Etiqueta de **forma** en «case de presentación» (RF-03): `alola`→`Alola`,
 * `paldea-combat`→`Paldea-Combat`, `crowned`→`Crowned`, `a`→`A`.
 * Devuelve `null` si es una forma base (RF-06).
 */
export function formLabel(form: string): string | null {
  if (!form || isBaseForm(form)) return null;
  return presentationCase(form);
}

const VARIANT_KEYS: Record<string, string> = {
  MEGA: "variant_mega",
  SHADOW: "variant_shadow",
  PRIMAL: "variant_primal",
  APEX: "variant_apex",
};

/**
 * Sinónimos adicionales de una variante que no salen del catálogo de textos.
 * El resto de sinónimos se derivan de las traducciones de T1 (todas válidas,
 * se escriba la interfaz en el idioma que se escriba).
 */
const EXTRA_VARIANT_SYNONYMS: Record<string, readonly string[]> = {
  SHADOW: ["sombra"],
};

/**
 * Etiqueta de **variante** traducida al idioma activo (RF-02). Devuelve `null`
 * para `NORMAL` —nunca se muestra— y para una variante sin clave en el catálogo.
 */
export function variantLabel(lang: Language, variant: string): string | null {
  if (!variant || variant === "NORMAL") return null;
  const key = VARIANT_KEYS[variant];
  if (!key) return null;
  const label = t(lang, key);
  // `t` devuelve la clave si no existe la traducción: eso no es una etiqueta.
  return label === key ? null : label;
}

/** Normaliza para comparar: NFD, sin acentos y en minúsculas (RNF-04). */
function normalizeLabel(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/**
 * ¿Aparece `needle` como **palabra completa** dentro de `haystack`? Se
 * considera frontera cualquier cosa que no sea letra latina o dígito, así que
 * sirven el espacio, el guion (`Méga-Empiflor`), el paréntesis
 * (`Giratina (Origin)`) y los signos de puntuación. Evita falsos positivos como
 * `Meganium` conteniendo `mega`.
 */
function containsWord(haystack: string, needle: string): boolean {
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(haystack);
}

/** Todas las formas que puede adoptar una etiqueta de variante, normalizadas. */
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

/**
 * ¿Trae ya el nombre base mostrado la etiqueta que íbamos a añadir (RF-05)?
 *
 * Se comprueba **solo el nombre que se va a mostrar como base** (el localizado
 * para el idioma activo), buscando cada etiqueta/sinónimo como palabra completa.
 * No se compara contra el `boss.name` crudo de la fuente: si la base localizada
 * no trae la etiqueta, se añade aunque el crudo sí la traiga (p. ej. en español
 * `Mega Victreebel` → `Victreebel (Mega)`). Las comprobaciones de forma y
 * variante son independientes.
 */
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

/**
 * Nombre compuesto mostrado (RF-01…RF-06):
 * `Base`, `Base (Forma)`, `Base (Variante)` o `Base (Forma, Variante)`,
 * con la forma siempre primero. Omite la etiqueta que el nombre ya trae (RF-05).
 */
export function displayName(boss: NameBoss, lang: Language): string {
  const base = baseName(boss, lang);
  // El dedup mira solo el nombre base que se va a mostrar, no el `boss.name`
  // crudo (RF-05): el crudo puede traer una etiqueta que la base localizada no.
  const sources = [base];

  const labels: string[] = [];

  const form = formLabel(boss.form);
  if (form && !alreadyHasLabel([boss.form], sources)) {
    labels.push(form);
  }

  const variant = variantLabel(lang, boss.variant);
  if (variant && !alreadyHasLabel(variantSynonyms(boss.variant), sources)) {
    labels.push(variant);
  }

  return labels.length > 0 ? `${base} (${labels.join(", ")})` : base;
}
