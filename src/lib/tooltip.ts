/**
 * Colocación del tooltip de fechas (RF-32).
 *
 * Función pura: recibe el rectángulo del ancla (la celda de fecha), el tamaño
 * del panel y el rectángulo visible de la ventana, y devuelve la posición en
 * píxeles de viewport. No toca el DOM, no lee el reloj y no mide nada por su
 * cuenta: quien la llama le pasa rectángulos ya medidos con
 * `getBoundingClientRect()`. El repositorio no tiene jsdom, así que toda la
 * geometría de RF-32 se prueba sin navegador en `tests/tooltip.test.ts`; mover
 * el nodo y escuchar `matchMedia` es de V21.
 *
 * Orden de preferencia (RF-32), sin atajos:
 *   1. Horizontal: a la derecha; si no cabe, a la izquierda; si tampoco,
 *      alineado con el borde izquierdo del ancla y ajustado al margen derecho.
 *   2. Vertical: debajo con `gap`; si no cabe, encima con `gap`; si tampoco,
 *      recortado al lado con más espacio.
 *   3. Márgenes: al menos `margin` px con cada borde de la ventana.
 *   4. Si no cabe de ninguna forma, no se abre (`null`).
 */

/** Rectángulo medido en coordenadas de viewport. El ancho y el alto bastan;
 *  los bordes se derivan para no duplicar campos que puedan desincronizarse. */
export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Dónde acabó el panel respecto al ancla en el eje horizontal. */
export type HorizontalPlacement = "right" | "left" | "clamped";

/** Dónde acabó el panel respecto al ancla en el eje vertical. `clipped` es el
 *  recorte de altura del último recurso de RF-32. */
export type VerticalPlacement = "below" | "above" | "clipped";

export interface TooltipPosition {
  /** Coordenada izquierda en píxeles de viewport. */
  left: number;
  /** Coordenada superior en píxeles de viewport. */
  top: number;
  /** Altura visible; solo es menor que la del panel en el recorte vertical. */
  height: number;
  horizontal: HorizontalPlacement;
  vertical: VerticalPlacement;
}

/** Separación entre el ancla y el panel (RF-32). */
export const TOOLTIP_GAP = 8;
/** Separación mínima con cada borde de la ventana (RF-32). */
export const TOOLTIP_MARGIN = 8;

function right(rect: Rect): number {
  return rect.left + rect.width;
}

function bottom(rect: Rect): number {
  return rect.top + rect.height;
}

export function placeTooltip(
  anchor: Rect,
  tip: Rect,
  viewport: Rect,
  gap: number = TOOLTIP_GAP,
  margin: number = TOOLTIP_MARGIN,
): TooltipPosition | null {
  const innerLeft = viewport.left + margin;
  const innerRight = right(viewport) - margin;
  const innerTop = viewport.top + margin;
  const innerBottom = bottom(viewport) - margin;

  const availableWidth = innerRight - innerLeft;
  const availableHeight = innerBottom - innerTop;

  // RF-32.4: sin sitio ni siquiera entre márgenes, no se abre.
  if (availableWidth <= 0 || availableHeight <= 0) return null;
  if (tip.width > availableWidth) return null;

  // --- Horizontal: derecha → izquierda → ajuste al margen derecho.
  let left: number;
  let horizontal: HorizontalPlacement;
  const anchorRight = right(anchor);
  if (anchorRight + tip.width <= innerRight) {
    left = anchorRight;
    horizontal = "right";
  } else if (anchor.left - tip.width >= innerLeft) {
    left = anchor.left - tip.width;
    horizontal = "left";
  } else {
    // No cabe entero en ninguno de los dos lados: se alinea con el borde
    // izquierdo del ancla y se ajusta para no rebasar el margen derecho.
    // Puede solaparse en horizontal con el ancla, que es lo que permite RF-32.
    left = Math.max(Math.min(anchor.left, innerRight - tip.width), innerLeft);
    horizontal = "clamped";
  }

  // --- Vertical: debajo (gap) → encima (gap) → recorte al lado más holgado.
  let top: number;
  let height: number;
  let vertical: VerticalPlacement;
  const belowTop = bottom(anchor) + gap;
  if (belowTop + tip.height <= innerBottom) {
    top = belowTop;
    height = tip.height;
    vertical = "below";
  } else if (anchor.top - gap - tip.height >= innerTop) {
    top = anchor.top - gap - tip.height;
    height = tip.height;
    vertical = "above";
  } else {
    const spaceBelow = innerBottom - belowTop;
    const spaceAbove = anchor.top - gap - innerTop;
    if (spaceBelow <= 0 && spaceAbove <= 0) return null;
    if (spaceBelow >= spaceAbove) {
      // Recorte por debajo: el borde inferior queda en el margen.
      height = Math.min(tip.height, spaceBelow);
      top = belowTop;
    } else {
      // Recorte por encima: el borde superior queda en el margen.
      height = Math.min(tip.height, spaceAbove);
      top = anchor.top - gap - height;
    }
    vertical = "clipped";
  }

  return { left, top, height, horizontal, vertical };
}
