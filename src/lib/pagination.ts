/** Filas por página en SSR y vista móvil estrecha (≤767 px). En escritorio
 *  (≥768 px) el cliente ajusta dinámicamente el tamaño al alto del viewport. */
export const MOBILE_PAGE_SIZE = 12;
export const PAGE_SIZE = MOBILE_PAGE_SIZE;

export const MIN_DESKTOP_PAGE_SIZE = 6;
export const MAX_DESKTOP_PAGE_SIZE = 25;
export const DESKTOP_ROW_HEIGHT = 46;
export const DESKTOP_MIN_WIDTH = 768;

export interface PageState {
  /** Página actual, siempre >= 1. */
  page: number;
  /** Número total de páginas; 0 cuando no hay filas. */
  pages: number;
  /** Número total de filas filtradas. */
  total: number;
  /** Primera fila de la página en base 1; 0 cuando no hay filas. */
  from: number;
  /** Última fila de la página en base 1; 0 cuando no hay filas. */
  to: number;
  /** Filas por página. */
  size: number;
}

function safeSize(size: number): number {
  return Number.isFinite(size) ? Math.max(0, Math.trunc(size)) : PAGE_SIZE;
}

function safeTotal(total: number): number {
  return Number.isFinite(total) ? Math.max(0, Math.trunc(total)) : 0;
}

/** Calcula cuántas filas enteras caben en el espacio vertical libre de escritorio
 *  (`≥768 px`), acotado entre `MIN_DESKTOP_PAGE_SIZE` y `MAX_DESKTOP_PAGE_SIZE`. */
export function computeDesktopPageSize(
  availableHeightPx: number,
  rowHeightPx: number = DESKTOP_ROW_HEIGHT,
): number {
  if (!Number.isFinite(availableHeightPx) || !Number.isFinite(rowHeightPx) || rowHeightPx <= 0) {
    return PAGE_SIZE;
  }
  const fit = Math.floor(availableHeightPx / rowHeightPx);
  return Math.min(MAX_DESKTOP_PAGE_SIZE, Math.max(MIN_DESKTOP_PAGE_SIZE, fit));
}

/** Resuelve el tamaño de página según el corte único de layout (`767px` / `768px`). */
export function resolveViewportPageSize(
  viewportWidth: number,
  availableHeightPx: number,
  rowHeightPx: number = DESKTOP_ROW_HEIGHT,
): number {
  if (!Number.isFinite(viewportWidth) || viewportWidth < DESKTOP_MIN_WIDTH) {
    return MOBILE_PAGE_SIZE;
  }
  return computeDesktopPageSize(availableHeightPx, rowHeightPx);
}

/** Número de páginas necesarias para `total` filas. 0 si no hay filas. */
export function pageCount(total: number, size: number = PAGE_SIZE): number {
  const rows = safeTotal(total);
  const perPage = safeSize(size);
  if (perPage === 0) return 0;
  return Math.ceil(rows / perPage);
}

/** `true` solo si la página existe en la lista. */
export function isValidPage(page: number, pages: number): boolean {
  return Number.isInteger(page) && page >= 1 && page <= pages;
}

/** Recorta la página al rango disponible. Sin filas devuelve 1. */
export function clampPage(page: number, pages: number): number {
  if (pages <= 0) return 1;
  if (!Number.isFinite(page)) return 1;
  return Math.min(Math.max(Math.trunc(page), 1), pages);
}

/** Recorta la página a la última existente si `total` no llena la actual. */
export function clampPageForTotal(
  page: number,
  total: number,
  size: number = PAGE_SIZE,
): number {
  return clampPage(page, pageCount(total, size));
}

/** Las filas de la página pedida, ya recortada al rango válido. */
export function pageSlice<T>(
  items: readonly T[],
  page: number,
  size: number = PAGE_SIZE,
): T[] {
  const perPage = safeSize(size);
  if (perPage === 0) return [];
  const current = clampPageForTotal(page, items.length, perPage);
  const start = (current - 1) * perPage;
  return items.slice(start, start + perPage);
}

/** Estado completo de la paginación, ya recortado, para pintar y etiquetar. */
export function pageState(
  total: number,
  page: number,
  size: number = PAGE_SIZE,
): PageState {
  const rows = safeTotal(total);
  const perPage = safeSize(size);
  const pages = pageCount(rows, perPage);
  const current = clampPage(page, pages);
  const empty = rows === 0 || perPage === 0;
  return {
    page: current,
    pages,
    total: rows,
    from: empty ? 0 : (current - 1) * perPage + 1,
    to: empty ? 0 : Math.min(rows, current * perPage),
    size: perPage,
  };
}
