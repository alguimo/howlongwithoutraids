import data from "../data/raids-snapshot.json";
import { listHtml, paginationHtml, paginationView, tableHeadHtml } from "../lib/html";
import { t } from "../lib/i18n";
import { STORAGE_KEY, resolveInitialLanguage } from "../lib/language";
import { sortBosses } from "../lib/order";
import { pageSlice, pageState, type PageState } from "../lib/pagination";
import { matches } from "../lib/search";
import { parseSnapshot } from "../lib/snapshot";
import type { Language } from "../lib/types";
import { mountDetails } from "./detail";
import { mountLanguageMenu } from "./language-menu";

function storedLanguage(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistLanguage(lang: Language): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* storage unavailable; keep the in-memory language */
  }
}

export function start(): void {
  const bosses = parseSnapshot(data);
  const listEl = document.getElementById("boss-list") as HTMLTableSectionElement | null;
  const headEl = document.getElementById("boss-head");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search") as HTMLInputElement | null;
  const clearEl = document.getElementById("clear");

  const pagerEl = document.getElementById("pagination");

  if (!listEl || !headEl || !emptyEl || !searchEl || !clearEl) return;

  let lang: Language = resolveInitialLanguage(navigator.language, storedLanguage());
  /** Página visible. La búsqueda y el idioma la devuelven a 1; además se recorta
   *  en cada render por si la lista se ha encogido. */
  let page = 1;

  const applyStaticText = (): void => {
    document.documentElement.lang = lang;
    document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
      el.textContent = t(lang, el.dataset.i18n!);
    });
    document.querySelectorAll<HTMLElement>("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(lang, el.dataset.i18nPlaceholder!));
    });
  };

  // RF-19, RF-25: el idioma ya no se elige con un `<select>` nativo, sino con
  // el popover. Elegir persiste, vuelve a la página 1 y repinta; `render()`
  // cierra el desplegable y vuelca el idioma resuelto al marcado.
  const menuHandle = mountLanguageMenu({
    onSelect: (next) => {
      lang = next;
      persistLanguage(lang);
      page = 1;
      render();
    },
  });

  // V21: el detalle de fechas vive en su propio control (modo por `matchMedia`,
  // nodo único movido al host flotante, `aria-expanded`). `render()` lo cierra
  // en cada repintado; el marcado se resuelve por delegación, así que sobrevive
  // al `innerHTML` completo de `<tbody>`.
  const detailsHandle = mountDetails(listEl);

  const render = (): void => {
    // RF-40: cualquier repintado de la lista (página, idioma o búsqueda) cierra
    // el desplegable; su `aria-expanded` vuelve a `false`.
    menuHandle.close();
    detailsHandle.closeAllDetails();
    const now = new Date();
    const visible = sortBosses(bosses, now, lang).filter((boss) =>
      matches(boss, searchEl.value, lang),
    );

    // Recorta la página antes de pintar: si la lista se ha encogido (por ejemplo
    // al cambiar de idioma) y la página actual quedaría vacía, cae a la última
    // válida, que para una lista vacía es la 1.
    const state = pageState(visible.length, page);
    page = state.page;

    listEl.innerHTML = listHtml(pageSlice(visible, state.page), now, lang);
    headEl.innerHTML = tableHeadHtml(lang);
    emptyEl.hidden = visible.length > 0;
    // El servidor pinta siempre `en`; aquí la bandera del botón y las opciones
    // pasan a reflejar el idioma resuelto (RF-27).
    menuHandle.sync(lang);
    renderPagination(state);
    applyStaticText();
  };

  const renderPagination = (state: PageState): void => {
    if (!pagerEl) return;
    const view = paginationView(state, lang);
    pagerEl.hidden = view.empty;
    pagerEl.setAttribute("aria-label", view.label);

    const prev = pagerEl.querySelector<HTMLButtonElement>("[data-page-prev]");
    const next = pagerEl.querySelector<HTMLButtonElement>("[data-page-next]");
    const range = pagerEl.querySelector<HTMLElement>("[data-page-range]");
    if (prev) {
      prev.disabled = view.prevDisabled;
      prev.setAttribute("aria-label", view.prevLabel);
    }
    if (next) {
      next.disabled = view.nextDisabled;
      next.setAttribute("aria-label", view.nextLabel);
    }
    if (range && range.textContent !== view.range) range.textContent = view.range;
  };

  const goTo = (next: number): void => {
    page = Math.max(1, next);
    render();
    // El foco se queda en el control pulsado: el marcado no se regenera.
  };

  searchEl.addEventListener("input", () => {
    page = 1;
    render();
  });

  clearEl.addEventListener("click", () => {
    searchEl.value = "";
    page = 1;
    render();
    searchEl.focus();
  });

  pagerEl?.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(
      "[data-page-prev], [data-page-next]",
    );
    if (!button || button.disabled) return;
    goTo(button.hasAttribute("data-page-next") ? page + 1 : page - 1);
  });

  render();
}
