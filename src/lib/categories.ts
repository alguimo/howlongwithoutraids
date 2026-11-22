import { isActive } from "./counter";
import { normalizeText } from "./text";
import type { BossSnapshot } from "./types";

/**
 * Categorías del buscador y píldoras de filtro rápido (spec 004 RF-11…RF-13,
 * ampliado por spec 006 RF-04…RF-05).
 */
export type CategoryId =
  | "mega"
  | "legendary"
  | "mythical"
  | "ultra_beast"
  | "shadow"
  | "primal"
  | "baby";

export const FILTER_CHIPS = [
  "active",
  "legendary",
  "mega",
  "shadow",
  "ultra_beast",
  "mythical",
] as const;

export type FilterChipId = (typeof FILTER_CHIPS)[number];

const FILTER_CHIP_SET: ReadonlySet<string> = new Set(FILTER_CHIPS);

export function isFilterChipId(value: unknown): value is FilterChipId {
  return typeof value === "string" && FILTER_CHIP_SET.has(value);
}

export interface CategorySubject {
  variant: string;
  is_legendary?: boolean | null;
  is_mythical?: boolean | null;
  is_baby?: boolean | null;
  is_ultra_beast?: boolean | null;
}

/** Alias singulares y plurales válidos en cualquier idioma activo (004 RF-11, 006 RF-05). */
export const CATEGORY_ALIASES: Record<CategoryId, readonly string[]> = {
  mega: ["mega", "megas", "méga", "mégas"],
  legendary: [
    "legendario",
    "legendarios",
    "legendary",
    "legendaries",
    "légendaire",
    "légendaires",
  ],
  mythical: [
    "mítico",
    "míticos",
    "mythical",
    "mythicals",
    "mythique",
    "mythiques",
    "fabuleux",
  ],
  ultra_beast: [
    "ultraente",
    "ultraentes",
    "ultra beast",
    "ultra beasts",
    "ultra-chimère",
    "ultra-chimères",
  ],
  shadow: ["oscuro", "oscuros", "sombra", "sombras", "shadow", "shadows", "ombre", "ombres"],
  primal: ["primigenio", "primigenios", "primal", "primals", "primitif", "primitifs"],
  baby: ["bebé", "bebés", "baby", "babies", "bébé", "bébés"],
};

export const CATEGORY_PREDICATES: Record<
  CategoryId,
  (boss: CategorySubject) => boolean
> = {
  mega: (boss) => boss.variant === "MEGA",
  legendary: (boss) => boss.is_legendary === true,
  mythical: (boss) => boss.is_mythical === true,
  ultra_beast: (boss) => boss.is_ultra_beast === true,
  shadow: (boss) => boss.variant === "SHADOW",
  primal: (boss) => boss.variant === "PRIMAL",
  baby: (boss) => boss.is_baby === true,
};

const ALIAS_INDEX: ReadonlyMap<string, CategoryId> = (() => {
  const index = new Map<string, CategoryId>();
  for (const [id, aliases] of Object.entries(CATEGORY_ALIASES) as [
    CategoryId,
    readonly string[],
  ][]) {
    for (const alias of aliases) {
      index.set(normalizeText(alias), id);
    }
  }
  return index;
})();

export function matchCategory(query: string): CategoryId | null {
  const normalized = normalizeText(query).trim();
  if (!normalized) return null;
  return ALIAS_INDEX.get(normalized) ?? null;
}

export function matchesCategory(boss: CategorySubject, id: CategoryId): boolean {
  return CATEGORY_PREDICATES[id](boss);
}

export function matchesFilterChip(
  boss: BossSnapshot,
  chip: FilterChipId | null,
  now: Date,
): boolean {
  if (chip === null) return true;
  if (chip === "active") return isActive(boss, now);
  return matchesCategory(boss, chip);
}
