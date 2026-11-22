/**
 * Popover de idioma: teclado y lector de pantalla (RF-24, RF-25).
 *
 * El autómata de apertura/navegación/selección vive en funciones puras
 * (`initialMenuState`, `menuReducer`, `actionForKey`, `selectedLanguage`,
 * `buttonAriaExpanded`), separado del DOM por la misma razón que
 * `detail-toggle.ts` y `tooltip.ts`: el repositorio no tiene jsdom y la lógica
 * se prueba con `npm test` sin navegador. `mountLanguageMenu` es el único punto
 * que toca el DOM; lo llama `app.ts` en V20 (V19 no cablea la app para no
 * invadir el reparto de esa tarea).
 *
 * Patrón listbox elegido: el foco **real** entra en las opciones (cada una
 * lleva `tabindex="-1"`), en lugar de quedarse en el botón con
 * `aria-activedescendant`. Es la variante que funciona igual con lector de
 * pantalla y no necesita ids por opción; el estado anunciado sigue siendo
 * `aria-expanded` en el botón y `aria-selected` en la opción elegida.
 */

import { flagSvg } from "../lib/flags";
import { LANGUAGES } from "../lib/i18n";
import type { Language } from "../lib/types";

/** Orden de las opciones. Igual que el marcado de `LanguageSelector.astro`. */
export const MENU_LANGS: readonly Language[] = LANGUAGES;

/** Estado del desplegable: si está abierto y qué opción está activa. */
export interface MenuState {
  open: boolean;
  activeIndex: number;
}

export type MenuAction = "open" | "close" | "next" | "prev" | "first" | "last" | "select";

/** Claves que, con el botón cerrado, abren la lista. */
const OPEN_KEYS = new Set(["Enter", " ", "Spacebar", "ArrowDown", "ArrowUp"]);

function clampIndex(index: number, count: number): number {
  if (index < 0) return 0;
  if (index >= count) return count - 1;
  return index;
}

/** Estado inicial: cerrado y con la opción activa sobre el idioma elegido. */
export function initialMenuState(
  langs: readonly Language[],
  selected: Language,
): MenuState {
  const index = langs.indexOf(selected);
  return { open: false, activeIndex: index >= 0 ? index : 0 };
}

/**
 * Autómata del menú. `count` es el número de opciones; los movimientos
 * envuelven (de la última a la primera y al revés) y con lista vacía no se
 * toca nada, para no poder indexar fuera de rango.
 */
export function menuReducer(state: MenuState, action: MenuAction, count: number): MenuState {
  if (count <= 0) return state;
  switch (action) {
    case "open":
      return { open: true, activeIndex: clampIndex(state.activeIndex, count) };
    case "close":
      return { open: false, activeIndex: state.activeIndex };
    case "next":
      return { open: state.open, activeIndex: (state.activeIndex + 1) % count };
    case "prev":
      return { open: state.open, activeIndex: (state.activeIndex - 1 + count) % count };
    case "first":
      return { open: state.open, activeIndex: 0 };
    case "last":
      return { open: state.open, activeIndex: count - 1 };
    case "select":
      // Elegir no cambia el estado: la opción se resuelve con `selectedLanguage`.
      return state;
  }
}

/**
 * Traduce una tecla a una acción, según el patrón listbox: con el botón
 * cerrado, Enter/Espacio/flechas abren; con la lista abierta, las flechas y
 * Home/End navegan, Enter/Espacio eligen y Escape cierra. `Tab` y el resto de
 * teclas se dejan al navegador y devuelven `null`.
 */
export function actionForKey(key: string, open: boolean): MenuAction | null {
  if (!open) return OPEN_KEYS.has(key) ? "open" : null;
  switch (key) {
    case "ArrowDown":
      return "next";
    case "ArrowUp":
      return "prev";
    case "Home":
      return "first";
    case "End":
      return "last";
    case "Enter":
    case " ":
    case "Spacebar":
      return "select";
    case "Escape":
      return "close";
    default:
      return null;
  }
}

/** Idioma de la opción activa, o `null` si la lista está cerrada o el índice
 *  está fuera de rango. */
export function selectedLanguage(
  state: MenuState,
  langs: readonly Language[],
): Language | null {
  if (!state.open) return null;
  return langs[state.activeIndex] ?? null;
}

/** Valor de `aria-expanded` del botón (RF-22). */
export function buttonAriaExpanded(state: MenuState): "true" | "false" {
  return state.open ? "true" : "false";
}

/** `aria-selected` que le corresponde a una opción para el idioma activo
 *  (RF-23). Lo comparten el momento de elegir (`select`) y el de volcar el
 *  idioma al marcado tras un repintado (`sync`), para que no discrepen. */
export function optionAriaSelected(option: Language, active: Language): "true" | "false" {
  return option === active ? "true" : "false";
}

export interface LanguageMenuOptions {
  /** Se llama con el idioma elegido. Es el gancho que cablea `app.ts` en V20:
   *  persistir, repintar y cerrar el desplegable son de esa tarea. */
  onSelect(lang: Language): void;
}

/** Control del popover montado. `close` es el gancho de repintado que usa V20
 *  (RF-25: al cambiar de página, idioma o búsqueda); `sync` vuelca el idioma
 *  resuelto al marcado (bandera del botón y `aria-selected` de las opciones),
 *  algo necesario porque el servidor pinta siempre `en`; `destroy` quita los
 *  listeners. */
export interface LanguageMenuHandle {
  close(): void;
  sync(lang: Language): void;
  destroy(): void;
}

const NOOP_HANDLE: LanguageMenuHandle = { close() {}, sync() {}, destroy() {} };

/**
 * Conecta el popover ya renderizado. Devuelve un control con `close` y
 * `destroy`. Sin `selector`, busca `[data-language-selector]` en el documento.
 */
export function mountLanguageMenu(
  options: LanguageMenuOptions,
  selector: HTMLElement | null = document.querySelector<HTMLElement>(
    "[data-language-selector]",
  ),
): LanguageMenuHandle {
  if (!selector) return NOOP_HANDLE;

  const button = selector.querySelector<HTMLButtonElement>("#language");
  const menu = selector.querySelector<HTMLElement>("#language-menu");
  if (!button || !menu) return NOOP_HANDLE;

  const optionEls = Array.from(
    menu.querySelectorAll<HTMLElement>('[role="option"][data-lang]'),
  );
  const langs = optionEls
    .map((el) => el.dataset.lang)
    .filter((lang): lang is Language => MENU_LANGS.includes(lang as Language));
  if (langs.length === 0) return NOOP_HANDLE;

  const selectedIndex = optionEls.findIndex(
    (el) => el.getAttribute("aria-selected") === "true",
  );
  let state = initialMenuState(
    langs,
    selectedIndex >= 0 ? (langs[selectedIndex] as Language) : (langs[0] as Language),
  );

  /** Vuelca el estado al marcado: `aria-expanded`, `hidden` y foco real. */
  const apply = (): void => {
    button.setAttribute("aria-expanded", buttonAriaExpanded(state));
    menu.hidden = !state.open;
    if (state.open) optionEls[state.activeIndex]?.focus();
  };

  /** Elige un idioma: actualiza el estado, marca la opción y avisa a V20. */
  const select = (lang: Language): void => {
    state = initialMenuState(langs, lang);
    optionEls.forEach((el) => {
      el.setAttribute("aria-selected", optionAriaSelected(el.dataset.lang as Language, lang));
    });
    apply();
    button.focus();
    options.onSelect(lang);
  };

  /**
   * Vuelca el idioma resuelto al marcado sin tocar la apertura: la bandera del
   * botón y el `aria-selected` de las opciones (V20, RF-27). Lo llama `app.ts`
   * tras cada repintado, porque el HTML del servidor sale siempre en `en`.
   */
  const sync = (lang: Language): void => {
    const index = langs.indexOf(lang);
    state = { open: state.open, activeIndex: index >= 0 ? index : 0 };
    optionEls.forEach((el) => {
      el.setAttribute("aria-selected", optionAriaSelected(el.dataset.lang as Language, lang));
    });
    const flagEl = button.querySelector<HTMLElement>("[data-language-flag]");
    if (flagEl) flagEl.innerHTML = flagSvg(lang);
  };

  /** Cierra la lista; `returnFocus` la devuelve al botón (RF-24, Escape). */
  const setClosed = (returnFocus: boolean): void => {
    if (!state.open) return;
    state = menuReducer(state, "close", langs.length);
    apply();
    if (returnFocus) button.focus();
  };

  const onButtonClick = (): void => {
    state = menuReducer(state, state.open ? "close" : "open", langs.length);
    apply();
  };

  const onKeyDown = (event: KeyboardEvent): void => {
    const action = actionForKey(event.key, state.open);
    if (!action) return;
    event.preventDefault();

    if (action === "close") {
      setClosed(true);
      return;
    }
    if (action === "select") {
      const lang = selectedLanguage(state, langs);
      if (lang) select(lang);
      return;
    }
    state = menuReducer(state, action, langs.length);
    apply();
  };

  const onMenuClick = (event: MouseEvent): void => {
    const option = (event.target as HTMLElement).closest<HTMLElement>(
      '[role="option"][data-lang]',
    );
    const lang = option?.dataset.lang as Language | undefined;
    if (lang && langs.includes(lang)) select(lang);
  };

  /** RF-25: un clic fuera del componente cierra el desplegable. */
  const onDocumentClick = (event: MouseEvent): void => {
    if (!state.open) return;
    const target = event.target as Node | null;
    if (target && selector.contains(target)) return;
    setClosed(false);
  };

  button.addEventListener("click", onButtonClick);
  selector.addEventListener("keydown", onKeyDown);
  menu.addEventListener("click", onMenuClick);
  document.addEventListener("click", onDocumentClick);

  return {
    close: () => setClosed(false),
    sync,
    destroy: () => {
      button.removeEventListener("click", onButtonClick);
      selector.removeEventListener("keydown", onKeyDown);
      menu.removeEventListener("click", onMenuClick);
      document.removeEventListener("click", onDocumentClick);
    },
  };
}
