import { matchCategory, matchesCategory } from "./categories";
import { baseName, displayName } from "./display";
import type { BossSnapshot, Language } from "./types";

export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/**
 * ¿Coincide el jefe con la consulta? (004 RF-11, RF-14, RF-15)
 *
 * La coincidencia es la **unión** de:
 *  - prefijo de dex (búsqueda heredada de 002 RF-11);
 *  - pertenencia a una categoría cuyo alias **iguala** el texto (RF-11);
 *  - nombre base (idioma activo o inglés) y nombre compuesto mostrado (RF-14).
 *
 * Una categoría nunca exige coincidencia de nombre: se suma. Un valor `null`
 * de categoría no entra porque el predicado exige `true` estricto (RF-13).
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

  return (
    normalize(baseName(boss, lang)).includes(query_) ||
    normalize(boss.name).includes(query_) ||
    normalize(displayName(boss, lang)).includes(query_)
  );
}
