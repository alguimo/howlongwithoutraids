/**
 * Categorías del buscador (spec 004, RF-11…RF-13, RNF-04).
 *
 * Módulo puro, sin DOM ni red. El buscador (T5) combina estas categorías con la
 * búsqueda por nombre/dex: `matchCategory` traduce un texto a una categoría y
 * `matchesCategory` evalúa el predicado sobre un jefe.
 */
export type CategoryId =
  | "mega"
  | "legendary"
  | "mythical"
  | "ultra_beast"
  | "shadow"
  | "primal"
  | "baby";

/**
 * Campos mínimos que necesita un jefe para evaluar categorías. `BossSnapshot`
 * es asignable a este tipo; se declara aparte para no acoplar el módulo a los
 * campos booleanos que `types.ts` aún no declara (nota de implementación 004).
 */
export interface CategorySubject {
  variant: string;
  is_legendary?: boolean | null;
  is_mythical?: boolean | null;
  is_baby?: boolean | null;
  is_ultra_beast?: boolean | null;
}

/** Alias válidos en cualquier idioma activo (RF-11). */
export const CATEGORY_ALIASES: Record<CategoryId, readonly string[]> = {
  mega: ["mega", "méga"],
  legendary: ["legendario", "legendary", "légendaire"],
  mythical: ["mítico", "mythical", "mythique", "fabuleux"],
  ultra_beast: ["ultraente", "ultra beast", "ultra-chimère"],
  shadow: ["oscuro", "sombra", "shadow", "ombre"],
  primal: ["primigenio", "primal", "primitif"],
  baby: ["bebé", "baby", "bébé"],
};

/** Predicados de categoría contra el snapshot de 001 (RF-12). */
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

/** Igual que `search.normalize`, replicado aquí para no crear un ciclo T5→T2. */
function normalizeAlias(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

const ALIAS_INDEX: ReadonlyMap<string, CategoryId> = (() => {
  const index = new Map<string, CategoryId>();
  for (const [id, aliases] of Object.entries(CATEGORY_ALIASES) as [
    CategoryId,
    readonly string[],
  ][]) {
    for (const alias of aliases) {
      index.set(normalizeAlias(alias), id);
    }
  }
  return index;
})();

/**
 * Categoría cuyo alias **iguala** el texto normalizado (sin acentos y en
 * minúsculas), o `null` si no es ningún alias. Igualdad exacta, no prefijo.
 */
export function matchCategory(query: string): CategoryId | null {
  const normalized = normalizeAlias(query).trim();
  if (!normalized) return null;
  return ALIAS_INDEX.get(normalized) ?? null;
}

/**
 * Evalúa el predicado de la categoría. Solo `true` estricto (o el enum exacto)
 * cuenta: `false`, `null` y un valor ausente no coinciden (RF-13).
 */
export function matchesCategory(boss: CategorySubject, id: CategoryId): boolean {
  return CATEGORY_PREDICATES[id](boss);
}
