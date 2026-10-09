import { isActive } from "./counter";
import { displayName } from "./display";
import type { BossSnapshot, Language } from "./types";

/**
 * Orden por defecto (spec 004, RF-08…RF-10):
 * activos primero; después, `last_end_date` descendente con los nulos al
 * final; empate alfabético por el nombre compuesto mostrado.
 *
 * Función pura: recibe «ahora» y no lee el DOM ni la red. El orden es por
 * instante de última aparición, no por días, así que no depende de la zona
 * horaria del visitante (ya no usa `evaluate`/`calendarDaysBetween`).
 */
function byDisplayName(a: BossSnapshot, b: BossSnapshot, lang: Language): number {
  return displayName(a, lang).localeCompare(displayName(b, lang));
}

export function sortBosses(
  bosses: BossSnapshot[],
  now: Date,
  lang: Language,
): BossSnapshot[] {
  return [...bosses].sort((a, b) => {
    const activeA = isActive(a, now);
    const activeB = isActive(b, now);

    // 1. Los activos van primero.
    if (activeA !== activeB) return activeA ? -1 : 1;

    // Dentro de los activos, el desempate es alfabético (la fecha no ordena).
    if (activeA && activeB) return byDisplayName(a, b, lang);

    // 2. `last_end_date` descendente; los nulos van después de todos.
    const endA = a.last_end_date;
    const endB = b.last_end_date;
    if (endA && endB) {
      const diff = new Date(endB).getTime() - new Date(endA).getTime();
      if (diff !== 0) return diff;
    } else if (endA) {
      return -1;
    } else if (endB) {
      return 1;
    }

    // 3. Empate (misma fecha o dos «Próximo» puros): alfabético por compuesto.
    return byDisplayName(a, b, lang);
  });
}
