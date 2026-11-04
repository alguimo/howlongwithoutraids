/**
 * Control del detalle de fechas (RF-13, RF-35, RF-36, RF-38, RF-39, RF-40,
 * RF-41).
 *
 * Resuelve el modo con `matchMedia("(hover: none)")` —nunca con el ancho—,
 * mueve el **nodo único** de detalle entre `<tbody>` y el host flotante, y
 * mantiene `aria-expanded` igual a lo visible. La máquina de estados del
 * disparador es pura y se prueba sin navegador: el repositorio no tiene jsdom.
 * Este módulo es el único punto que toca el DOM; `app.ts` solo lo monta y llama
 * a `closeAllDetails()` en cada repintado.
 *
 * Dos reglas que el CSS sostiene y aquí se respetan:
 *   - En `(hover: hover)` la fila desplegable es imposible dentro de la tabla
 *     (`tbody .detail-row { display: none }`), así que la única representación
 *     es el tooltip y este se mueve fuera de `<tbody>`.
 *   - Un `<tr>` fuera de `<tbody>` no se pinta si nadie le da caja: el host
 *     flotante fuerza `display: block` en la fila y su celda (`global.css`).
 */

import { HIDDEN_CLASS, foldOtherDetails, type DetailPair } from "../lib/detail-toggle";
import {
  TOOLTIP_GAP,
  TOOLTIP_MARGIN,
  placeTooltip,
  type Rect,
} from "../lib/tooltip";

/** Tooltip flotante (`(hover: hover)`) o fila desplegable (`(hover: none)`). */
export type DetailMode = "tooltip" | "row";

/** Evento que puede cambiar el estado del detalle, ya sin DOM. */
export type DetailTrigger =
  | "pointerenter"
  | "pointerleave"
  | "focus"
  | "blur"
  | "activate"
  | "repaint"
  | "modechange"
  | "resize";

/** Qué hacer con el detalle ante un disparador. */
export type DetailAction = "open" | "close" | "toggle" | "none";

/** Corte de layout de la spec: estrecho es ≤767 px y ancho ≥768 px. */
export const NARROW_MAX_WIDTH = 767;

/** Id del host flotante. Lo crea este módulo al montar (D4), no `index.astro`. */
export const LAYER_ID = "detail-layer";

export const TOOLTIP_ROLE = "tooltip";
export const ROW_ROLE = "row";
export const CELL_ROLE = "cell";

/** El modo lo decide la media query, no el ancho de la ventana (RF-41). */
export function resolveDetailMode(hoverNone: boolean): DetailMode {
  return hoverNone ? "row" : "tooltip";
}

/** Roles que le corresponden al nodo único según cómo se presente (RF-39):
 *  flotando es un `tooltip` y su celda pierde el rol; desplegado recupera la
 *  semántica de fila y celda de tabla (RF-43). */
export function panelRoles(mode: DetailMode): { row: string; cell: string | null } {
  return mode === "tooltip"
    ? { row: TOOLTIP_ROLE, cell: null }
    : { row: ROW_ROLE, cell: CELL_ROLE };
}

/**
 * Máquina del disparador. En `(hover: hover)` gobiernan el puntero y el foco:
 * entrar abre, salir cierra, y `activate` (clic o Enter/Espacio) no cambia nada
 * (RF-41). En `(hover: none)` `activate` alterna la fila y el puntero y el foco
 * no hacen nada (RF-33). En los dos modos, repintar, cambiar de modo o cruzar el
 * corte cierran (RF-40). Un jefe sin contenido nunca abre ni alterna.
 */
export function detailActionFor(
  trigger: DetailTrigger,
  mode: DetailMode,
  hasContent = true,
): DetailAction {
  if (trigger === "repaint" || trigger === "modechange" || trigger === "resize") {
    return "close";
  }

  if (mode === "tooltip") {
    switch (trigger) {
      case "pointerenter":
      case "focus":
        return hasContent ? "open" : "none";
      case "pointerleave":
      case "blur":
        return "close";
      case "activate":
        return hasContent ? "toggle" : "none";
      default:
        return "none";
    }
  }

  switch (trigger) {
    case "activate":
      return hasContent ? "toggle" : "none";
    default:
      return "none";
  }
}

/** `aria-expanded` resultante de una acción (RF-36). */
export function nextExpanded(current: boolean, action: DetailAction): boolean {
  switch (action) {
    case "open":
      return true;
    case "close":
      return false;
    case "toggle":
      return !current;
    case "none":
      return current;
  }
}

/** ¿Un cambio de tamaño cruzó el corte de 768 px? (RF-40). */
export function crossesNarrowBreakpoint(
  previousWidth: number,
  nextWidth: number,
  max: number = NARROW_MAX_WIDTH,
): boolean {
  const narrow = (width: number): boolean => width <= max;
  return narrow(previousWidth) !== narrow(nextWidth);
}

/** Control del detalle montado. `closeAllDetails` es el gancho de repintado. */
export interface DetailsHandle {
  closeAllDetails(): void;
  destroy(): void;
}

interface OpenDetail {
  button: HTMLButtonElement;
  panel: HTMLTableRowElement;
  floating: boolean;
  pinned: boolean;
  /** Posición original del nodo en `<tbody>`, para devolverlo al cerrar. */
  home: { parent: Node; next: Node | null } | null;
}

function toRect(rect: DOMRect): Rect {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

function ensureLayer(doc: Document): HTMLElement {
  const existing = doc.getElementById(LAYER_ID);
  if (existing) return existing;
  const layer = doc.createElement("div");
  layer.id = LAYER_ID;
  doc.body.appendChild(layer);
  return layer;
}

/**
 * Conecta el detalle a la tabla. `listEl` es el `<tbody>` que `app.ts` repinta;
 * los nodos se resuelven por `aria-controls` en cada interacción, así que
 * sobreviven al `innerHTML` completo.
 */
export function mountDetails(
  listEl: HTMLElement,
  options: { document?: Document; window?: Window } = {},
): DetailsHandle {
  const doc = options.document ?? document;
  const win = options.window ?? window;

  const host = ensureLayer(doc);
  const media = win.matchMedia("(hover: none)");
  let mode = resolveDetailMode(media.matches);
  let current: OpenDetail | null = null;
  let lastWidth = win.innerWidth;

  const buttonIn = (cell: HTMLElement | null): HTMLButtonElement | null =>
    (cell?.querySelector("[data-detail]") as HTMLButtonElement | null) ?? null;

  /** La celda de fecha: la única `td` que contiene el botón de detalle. */
  const dateCell = (target: EventTarget | null): HTMLElement | null => {
    const cell = ((target as HTMLElement | null)?.closest?.("td") as HTMLElement | null) ?? null;
    return cell && cell.querySelector("[data-detail]") ? cell : null;
  };

  const buttonFrom = (target: EventTarget | null): HTMLButtonElement | null =>
    ((target as HTMLElement | null)?.closest?.("[data-detail]") as HTMLButtonElement | null) ??
    null;

  const panelFor = (button: HTMLButtonElement): HTMLTableRowElement | null => {
    const id = button.getAttribute("aria-controls");
    return id ? (doc.getElementById(id) as HTMLTableRowElement | null) : null;
  };

  const hasContent = (panel: HTMLElement): boolean => {
    const cell = panel.querySelector("td");
    return !!cell && !!cell.textContent && cell.textContent.trim().length > 0;
  };

  const allPairs = (): DetailPair[] => {
    const pairs: DetailPair[] = [];
    listEl.querySelectorAll<HTMLButtonElement>("[data-detail]").forEach((button) => {
      const panel = panelFor(button);
      if (panel) pairs.push({ panel, button });
    });
    return pairs;
  };

  const setRoles = (panel: HTMLTableRowElement, next: DetailMode): void => {
    const roles = panelRoles(next);
    panel.setAttribute("role", roles.row);
    const cell = panel.querySelector("td");
    if (!cell) return;
    if (roles.cell) cell.setAttribute("role", roles.cell);
    else cell.removeAttribute("role");
  };

  const clearPosition = (panel: HTMLElement): void => {
    panel.style.removeProperty("left");
    panel.style.removeProperty("top");
    panel.style.removeProperty("height");
  };

  const restoreToTable = (open: OpenDetail): void => {
    setRoles(open.panel, "row");
    clearPosition(open.panel);
    const home = open.home;
    if (home && home.parent.isConnected) home.parent.insertBefore(open.panel, home.next);
    else open.panel.remove();
    open.home = null;
  };

  const place = (button: HTMLButtonElement, panel: HTMLTableRowElement): boolean => {
    clearPosition(panel);
    const cell = (button.closest("td") as HTMLElement | null) ?? button;
    const viewport: Rect = { left: 0, top: 0, width: win.innerWidth, height: win.innerHeight };
    const position = placeTooltip(
      toRect(cell.getBoundingClientRect()),
      toRect(panel.getBoundingClientRect()),
      viewport,
      TOOLTIP_GAP,
      TOOLTIP_MARGIN,
    );
    if (!position) return false;
    panel.style.left = `${Math.round(position.left)}px`;
    panel.style.top = `${Math.round(position.top)}px`;
    if (position.vertical === "clipped") {
      panel.style.height = `${Math.round(position.height)}px`;
    }
    return true;
  };

  const openDetail = (button: HTMLButtonElement, pinned = false): void => {
    if (current?.button === button) {
      if (pinned) current.pinned = true;
      return;
    }
    closeAllDetails();
    const panel = panelFor(button);
    if (!panel || !hasContent(panel)) return;

    if (mode === "tooltip") {
      const home = { parent: panel.parentNode as Node, next: panel.nextSibling };
      host.appendChild(panel);
      setRoles(panel, "tooltip");
      panel.classList.remove(HIDDEN_CLASS);
      if (!place(button, panel)) {
        // No cabe en ningún lado: se deshace el traslado y todo queda cerrado.
        current = { button, panel, floating: true, pinned: false, home };
        closeAllDetails();
        return;
      }
      current = { button, panel, floating: true, pinned, home };
      button.setAttribute("aria-describedby", LAYER_ID);
    } else {
      setRoles(panel, "row");
      panel.classList.remove(HIDDEN_CLASS);
      current = { button, panel, floating: false, pinned: true, home: null };
    }
    button.setAttribute("aria-expanded", "true");
  };

  const closeAllDetails = (): void => {
    if (current?.button) {
      current.button.removeAttribute("aria-describedby");
    }
    // Devolver el nodo a la tabla ANTES de plegar: el nodo único vuelve a vivir
    // en `<tbody>` (RF-39) y el siguiente `openDetail` puede reubicarlo.
    if (current?.floating) restoreToTable(current);
    foldOtherDetails(allPairs());
    current = null;
  };

  const handle = (trigger: DetailTrigger, button: HTMLButtonElement): void => {
    const panel = panelFor(button);
    const action = detailActionFor(trigger, mode, !!panel && hasContent(panel));
    if (action === "none") return;
    const shouldOpen = nextExpanded(current?.button === button, action);
    if (shouldOpen) openDetail(button);
    else closeAllDetails();
  };

  const onPointerOver = (event: Event): void => {
    if (mode !== "tooltip") return;
    const cell = dateCell(event.target);
    const button = cell && buttonIn(cell);
    if (button) handle("pointerenter", button);
  };

  const onPointerOut = (event: Event): void => {
    if (mode !== "tooltip" || current?.pinned) return;
    const cell = dateCell(event.target);
    if (!cell) return;
    // Mover el puntero dentro de la misma celda no es «salir».
    const to = (event as PointerEvent).relatedTarget as Node | null;
    if (to && cell.contains(to)) return;
    const button = buttonIn(cell);
    if (!button || current?.button !== button) return;
    handle("pointerleave", button);
  };

  const onFocusIn = (event: Event): void => {
    if (mode !== "tooltip") return;
    const button = buttonFrom(event.target);
    if (button) handle("focus", button);
  };

  const onFocusOut = (event: Event): void => {
    if (mode !== "tooltip" || current?.pinned) return;
    const button = buttonFrom(event.target);
    if (!button || current?.button !== button) return;
    handle("blur", button);
  };

  const onListClick = (event: Event): void => {
    const button = buttonFrom(event.target);
    if (!button) return;
    if (mode === "tooltip") {
      if (current?.button === button && !current.pinned) {
        current.pinned = true;
        return;
      }
      const panel = panelFor(button);
      const action = detailActionFor("activate", mode, !!panel && hasContent(panel));
      if (action === "none") return;
      if (nextExpanded(current?.button === button, action)) openDetail(button, true);
      else closeAllDetails();
      return;
    }
    handle("activate", button);
  };

  /** En táctil o con tooltip fijado por clic, tocar/clicar fuera cierra el detalle. */
  const onDocumentClick = (event: Event): void => {
    if (mode !== "row" && !current?.pinned) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest("[data-detail]")) return;
    if (target?.closest(".detail-row")) return;
    closeAllDetails();
  };

  /** R3: si cambia la media query (se enchufa un ratón, se abre en modo
   *  táctil), se cierra en vez de trasladarse (RF-40). */
  const onModeChange = (): void => {
    mode = resolveDetailMode(media.matches);
    closeAllDetails();
  };

  const onResize = (): void => {
    const width = win.innerWidth;
    if (crossesNarrowBreakpoint(lastWidth, width)) closeAllDetails();
    lastWidth = width;
  };

  const onKeyDown = (event: Event): void => {
    if ((event as KeyboardEvent).key === "Escape") {
      closeAllDetails();
    }
  };

  listEl.addEventListener("pointerover", onPointerOver);
  listEl.addEventListener("pointerout", onPointerOut);
  listEl.addEventListener("focusin", onFocusIn);
  listEl.addEventListener("focusout", onFocusOut);
  listEl.addEventListener("click", onListClick);
  doc.addEventListener("click", onDocumentClick);
  doc.addEventListener("keydown", onKeyDown);
  media.addEventListener("change", onModeChange);
  win.addEventListener("resize", onResize);

  return {
    closeAllDetails,
    destroy(): void {
      listEl.removeEventListener("pointerover", onPointerOver);
      listEl.removeEventListener("pointerout", onPointerOut);
      listEl.removeEventListener("focusin", onFocusIn);
      listEl.removeEventListener("focusout", onFocusOut);
      listEl.removeEventListener("click", onListClick);
      doc.removeEventListener("click", onDocumentClick);
      doc.removeEventListener("keydown", onKeyDown);
      media.removeEventListener("change", onModeChange);
      win.removeEventListener("resize", onResize);
      if (host.childElementCount === 0) host.remove();
    },
  };
}
