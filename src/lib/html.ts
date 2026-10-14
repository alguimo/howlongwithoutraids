import { baseName } from "./display";
import { t } from "./i18n";
import type { PageState } from "./pagination";
import type { BossSnapshot, Language } from "./types";
import { detailLines, rowView } from "./view";

export function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
  );
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function formatDate(iso: string, lang: Language): string {
  return new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeZone: "UTC" }).format(
    new Date(iso),
  );
}

/** Id del nodo único de detalle de un jefe (RF-39). El botón de fecha apunta
 *  siempre a este id, en las dos modalidades del detalle. */
export function detailRowId(key: string): string {
  return `detail-${key}`;
}

// RF-21: `neutral-500` sobre `bg-neutral-950` daba 4.18:1 y no llegaba al 4.5:1
// que pide la spec. `neutral-400` se queda en 7.63:1 sin_volverse a competir con
// el texto de las celdas (`neutral-100`): el encabezado sigue siendo el tono bajo
// de la tabla porque además es `text-xs` y va en mayúsculas.
const HEAD_CELL =
  'scope="col" role="columnheader" class="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-neutral-400"';

export function tableHeadHtml(lang: Language = "en"): string {
  // El encabezado del sprite se oculta por dentro (RF-18, D3): el `<th>`
  // conserva su caja y su rol, y el texto vive en un `sr-only`. Si el
  // `sr-only` se pusiera en la celda, perdería el ancho y la tabla
  // redistribuiría las columnas en cada corte.
  const spriteHeader = `<th ${HEAD_CELL}><span class="sr-only">${escapeHtml(t(lang, "col_image"))}</span></th>`;
  const visible: string[] = (["col_name", "col_status", "col_date", "col_tier"] as const).map(
    (key) => `<th ${HEAD_CELL}>${escapeHtml(t(lang, key))}</th>`,
  );
  return `<tr role="row">${spriteHeader}${visible.join("")}</tr>`;
}

function detailHtml(boss: BossSnapshot, now: Date, lang: Language): string {
  const lines = detailLines(boss, now, lang);
  if (lines.length === 0) return "";
  const body = lines
    .map((line) => {
      // RF-17, RF-19: el nombre del evento se pinta junto a la etiqueta, solo
      // cuando existe, y siempre escapado (texto de una fuente externa).
      const eventName = line.eventName
        ? ` <span class="text-neutral-300">${escapeHtml(line.eventName)}</span>`
        : "";
      const eventTag = line.event
        ? ` <span class="rounded bg-neutral-800 px-2 py-0.5 text-xs">${escapeHtml(t(lang, "event_tag"))}</span>`
        : "";
      return `<div class="flex items-center justify-between gap-3 py-0.5 text-sm text-neutral-400"><span>${escapeHtml(line.label)}${eventName}${eventTag}</span><span>${escapeHtml(formatDate(line.iso, lang))}</span></div>`;
    })
    .join("");
  return `<div class="flex flex-wrap gap-x-8">${body}</div>`;
}

export function rowHtml(boss: BossSnapshot, now: Date, lang: Language): string {
  const view = rowView(boss, now, lang);
  const key = `${boss.dex_number}-${boss.form}-${boss.variant}`.toLowerCase();
  const detailId = detailRowId(key);
  const dateLabel = view.dateISO ? formatDate(view.dateISO, lang) : "";

  const avatar = boss.sprite_url
    ? `<img src="${escapeHtml(boss.sprite_url)}" alt="${escapeHtml(view.name)}" width="40" height="40" loading="lazy" class="h-10 w-10 rounded object-contain" />`
    : `<span role="img" aria-label="${escapeHtml(view.name)}" class="flex h-10 w-10 items-center justify-center rounded bg-neutral-800 text-xs font-semibold text-neutral-300">${escapeHtml(initials(baseName(boss, lang)))}</span>`;

  const upcomingTag =
    view.upcoming && view.kind !== "upcoming"
      ? `<span class="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300">${escapeHtml(t(lang, "upcoming"))}</span>`
      : "";

  // 003 RF-14: tier vigente/próximo y, si no lo hay, el último histórico
  // (`last_tier`). Un jefe terminado con tier conocido no se muestra vacío; solo
  // queda la celda sin badge cuando el snapshot no trae ninguno de los dos.
  const tier = boss.tier ?? boss.last_tier;
  const tierCell = tier
    ? `<span class="rounded bg-neutral-900 px-2 py-0.5 text-xs text-neutral-300">${escapeHtml(tier)}</span>`
    : "";

  // RF-11, RF-43: cinco celdas en el orden sprite · Pokémon · Última aparición ·
  // Fecha · Tier. Los roles van escritos porque el apilado a tarjetas de la
  // ventana estrecha cambia el `display` y el navegador recalcularía el rol
  // implícito a `generic`, dejando al lector de pantalla sin celdas.
  //
  // RF-39: el `<tr class="detail-row">` es el nodo único de detalle y el `<td>`
  // lleva `role="cell"` explícito. En ventana estrecha el CSS lo pasa a
  // `display: block` y, sin el rol escrito, el detalle desplegado quedaría como
  // texto suelto y no como celda navegable (deuda de V13/V14). Cuando V21 mueva
  // este nodo al host flotante sustituirá los roles de fila y celda por
  // `role="tooltip"`, para no dejar una celda dentro de un nodo que ya no es una
  // fila de tabla.
  return `<tr class="boss-row border-b border-neutral-900 align-middle" role="row">
  <td role="cell" class="px-3 py-2" data-label="${escapeHtml(t(lang, "col_image"))}">${avatar}</td>
  <td role="cell" class="px-3 py-2 font-medium" data-label="${escapeHtml(t(lang, "col_name"))}">${escapeHtml(view.name)}</td>
  <td role="cell" class="px-3 py-2 text-sm text-neutral-300" data-label="${escapeHtml(t(lang, "col_status"))}"><span class="flex items-center gap-2">${escapeHtml(view.statusText)}${upcomingTag}</span></td>
  <td role="cell" class="px-3 py-2 text-sm" data-label="${escapeHtml(t(lang, "col_date"))}">
    <button type="button" data-detail aria-expanded="false" aria-controls="${detailId}" class="text-neutral-300 underline underline-offset-4 outline-none focus-visible:ring-1 focus-visible:ring-neutral-400">${escapeHtml(dateLabel)}</button>
  </td>
  <td role="cell" class="px-3 py-2 text-xs" data-label="${escapeHtml(t(lang, "col_tier"))}">${tierCell}</td>
</tr>
<tr id="${detailId}" class="detail-row hidden" role="row"><td role="cell" colspan="5" class="px-3 pb-3 pt-0">${detailHtml(boss, now, lang)}</td></tr>`;
}

export function listHtml(
  bosses: BossSnapshot[],
  now: Date,
  lang: Language,
): string {
  return bosses.map((boss) => rowHtml(boss, now, lang)).join("");
}

const PAGER_BUTTON =
  "inline-flex h-10 min-w-10 items-center justify-center gap-1 rounded-md border border-neutral-700 px-3 text-sm text-neutral-200 outline-none transition-colors hover:border-neutral-500 focus-visible:border-neutral-400 focus-visible:ring-1 focus-visible:ring-neutral-300 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:text-neutral-400 disabled:hover:border-neutral-800";

export interface PaginationView {
  /** Texto accesible del contenedor de navegación. */
  label: string;
  prevLabel: string;
  nextLabel: string;
  /** Rango visible, p. ej. «1–20 de 116». */
  range: string;
  prevDisabled: boolean;
  nextDisabled: boolean;
  /** No hay nada que paginar. */
  empty: boolean;
}

/** Textos y estados deshabilitados de los controles, ya traducidos. Es la única
 *  fuente de verdad: la usan `paginationHtml` (servidor y primer render) y el
 *  cliente para actualizar los controles ya montados. */
export function paginationView(state: PageState, lang: Language): PaginationView {
  const { page, pages, total } = state;
  return {
    label: t(lang, "pagination"),
    prevLabel: t(lang, "prev_page"),
    nextLabel: t(lang, "next_page"),
    range: t(lang, "page_range", { from: state.from, to: state.to, total }),
    prevDisabled: page <= 1,
    nextDisabled: pages <= 1 || page >= pages,
    empty: total === 0,
  };
}

/** Marcado compartido por el servidor y el cliente. Los controles se quedan
 *  siempre visibles; solo se deshabilitan en los extremos. El rango lleva
 *  `aria-live` para que un lector de pantalla anuncie el cambio de página. */
export function paginationHtml(state: PageState, lang: Language): string {
  const view = paginationView(state, lang);
  const button = (which: "prev" | "next", label: string, disabled: boolean, glyph: string) =>
    `<button type="button" data-page-${which} aria-label="${escapeHtml(label)}" class="${PAGER_BUTTON}"${disabled ? " disabled" : ""}><span aria-hidden="true">${glyph}</span></button>`;

  return `<nav id="pagination" aria-label="${escapeHtml(view.label)}" class="mt-4 flex items-center justify-between gap-3">
  ${button("prev", view.prevLabel, view.prevDisabled, "←")}
  <span data-page-range aria-live="polite" class="text-sm tabular-nums text-neutral-400">${escapeHtml(view.range)}</span>
  ${button("next", view.nextLabel, view.nextDisabled, "→")}
</nav>`;
}
