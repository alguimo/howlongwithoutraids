import data from "../data/raids-snapshot.json";
import metaData from "../data/snapshot-meta.json";
import { type FilterChipId, isFilterChipId, matchesFilterChip } from "../lib/categories";
import { isActive } from "../lib/counter";
import {
  footerUpdatedText,
  listHtml,
  paginationView,
  tableHeadHtml,
} from "../lib/html";
import { t } from "../lib/i18n";
import { STORAGE_KEY, resolveInitialLanguage } from "../lib/language";
import { type SortMode, isSortMode, sortBosses } from "../lib/order";
import {
  DESKTOP_MIN_WIDTH,
  DESKTOP_ROW_HEIGHT,
  PAGE_SIZE,
  pageSlice,
  pageState,
  resolveViewportPageSize,
  type PageState,
} from "../lib/pagination";
import { matches } from "../lib/search";
import { parseSnapshot, parseSnapshotMeta } from "../lib/snapshot";
import type { Language } from "../lib/types";
import { formatRelativeUrl, parseUrlState } from "../lib/url-state";
import { formatDayCount } from "../lib/view";
import { mountDetails } from "./detail";
import { mountLanguageMenu } from "./language-menu";
import { readStorage, writeStorage } from "./storage";
import { mountThemeController } from "./theme-controller";

function verticalMargins(el: HTMLElement | null): number {
  if (!el) return 0;
  const style = window.getComputedStyle(el);
  return (Number.parseFloat(style.marginTop) || 0) + (Number.parseFloat(style.marginBottom) || 0);
}

function verticalPadding(el: HTMLElement | null): number {
  if (!el) return 0;
  const style = window.getComputedStyle(el);
  return (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.paddingBottom) || 0);
}

export function start(): void {
  const bosses = parseSnapshot(data);
  const meta = parseSnapshotMeta(metaData);
  const headerEl = document.querySelector<HTMLElement>(".app-header");
  const mainEl = document.querySelector<HTMLElement>("main");
  const filterBarEl = document.querySelector<HTMLElement>(".filter-bar");
  const tableWrapEl = document.getElementById("table-wrap");
  const listEl = document.getElementById("boss-list") as HTMLTableSectionElement | null;
  const headEl = document.getElementById("boss-head");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search") as HTMLInputElement | null;
  const searchClearBtn = document.getElementById("search-clear-btn") as HTMLButtonElement | null;
  const clearEl = document.getElementById("clear");
  const sortEl = document.getElementById("sort") as (HTMLElement & { value: string }) | null;
  const chipEls = document.querySelectorAll<HTMLButtonElement>("[data-filter-chip]");
  const resultsCountEl = document.querySelector<HTMLElement>("[data-results-count]");
  const pagerEl = document.getElementById("pagination");
  const footerEl = document.querySelector<HTMLElement>("footer");

  if (!listEl || !headEl || !emptyEl || !searchEl || !clearEl) return;

  const initialUrlState = parseUrlState(window.location.search);
  searchEl.value = initialUrlState.q;
  let filter: FilterChipId | null = initialUrlState.filter;
  let sort: SortMode = initialUrlState.sort;
  let page = initialUrlState.page;
  if (sortEl) sortEl.value = sort;

  let totalPages = 1;
  let lang: Language = resolveInitialLanguage(navigator.language, readStorage(STORAGE_KEY));
  const themeHandle = mountThemeController(lang);

  let cachedTheadHeight = 32;
  let cachedRowHeight = DESKTOP_ROW_HEIGHT;
  let cachedPagerHeight = 48;

  const measurePageSize = (): number => {
    const vw = window.innerWidth;
    if (vw < DESKTOP_MIN_WIDTH) {
      return resolveViewportPageSize(vw, 0);
    }

    const headRect = headEl.getBoundingClientRect().height;
    if (headRect > 0) cachedTheadHeight = headRect;

    const sampleRow = listEl.querySelector<HTMLElement>(".boss-row");
    const rowRect = sampleRow ? sampleRow.getBoundingClientRect().height : 0;
    if (rowRect >= 32) cachedRowHeight = Math.ceil(rowRect);

    const pagerParent = pagerEl?.parentElement ?? pagerEl;
    if (pagerEl && !pagerEl.hidden && pagerParent) {
      const pHeight = pagerParent.getBoundingClientRect().height + verticalMargins(pagerEl);
      if (pHeight > 0) cachedPagerHeight = pHeight;
    }

    const headerHeight = headerEl?.getBoundingClientRect().height ?? 0;
    const mainPad = verticalPadding(mainEl);
    const filterHeight = filterBarEl
      ? filterBarEl.getBoundingClientRect().height + verticalMargins(filterBarEl)
      : 0;
    const tableMargins = verticalMargins(tableWrapEl);
    const footerHeight = footerEl ? footerEl.getBoundingClientRect().height + 16 : 0;

    const chromeHeight =
      headerHeight +
      mainPad +
      filterHeight +
      tableMargins +
      cachedTheadHeight +
      cachedPagerHeight +
      footerHeight +
      8;

    return resolveViewportPageSize(vw, window.innerHeight - chromeHeight, cachedRowHeight);
  };

  let currentPageSize = PAGE_SIZE;

  const syncSearchAffordances = (): void => {
    const hasSearch = searchEl.value.trim().length > 0;
    if (searchClearBtn) searchClearBtn.hidden = !hasSearch;
  };

  const applyStaticText = (now: Date = new Date()): void => {
    document.documentElement.lang = lang;
    document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
      el.textContent = t(lang, el.dataset.i18n!);
    });
    document.querySelectorAll<HTMLElement>("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", t(lang, el.dataset.i18nPlaceholder!));
    });
    document.querySelectorAll<HTMLElement>("[data-i18n-aria-label]").forEach((el) => {
      el.setAttribute("aria-label", t(lang, el.dataset.i18nAriaLabel!));
    });
    const updated = footerUpdatedText(meta.exported_at, lang);
    const updatedWrap = document.querySelector<HTMLElement>("[data-footer-updated-wrap]");
    const updatedEl = document.querySelector<HTMLElement>("[data-footer-updated]");
    if (updatedWrap) updatedWrap.hidden = updated === null;
    if (updatedEl) updatedEl.textContent = updated ?? "";
    const activeEl = document.querySelector<HTMLElement>("[data-active-raids-count]");
    if (activeEl) {
      const activeCount = bosses.filter((b) => isActive(b, now)).length;
      activeEl.textContent = t(lang, "active_raids_count", { count: activeCount });
    }
    menuHandle.sync(lang);
    themeHandle.sync(lang);
  };

  const syncChips = (): void => {
    chipEls.forEach((btn) => {
      const id = btn.getAttribute("data-filter-chip") ?? "";
      btn.setAttribute("aria-pressed", String(id === filter));
    });
  };

  const menuHandle = mountLanguageMenu({
    onSelect: (next) => {
      lang = next;
      writeStorage(STORAGE_KEY, lang);
      page = 1;
      applyStaticText();
      render();
    },
  });

  const detailsHandle = mountDetails(listEl);

  const render = (): void => {
    menuHandle.close();
    detailsHandle.closeAllDetails();
    const now = new Date();
    const visible = sortBosses(bosses, now, lang, sort).filter(
      (boss) => matchesFilterChip(boss, filter, now) && matches(boss, searchEl.value, lang),
    );

    currentPageSize = measurePageSize();
    const state = pageState(visible.length, page, currentPageSize);
    page = state.page;
    totalPages = state.pages;

    listEl.innerHTML = listHtml(pageSlice(visible, state.page, state.size), now, lang);
    headEl.innerHTML = tableHeadHtml(lang, sort);
    if (tableWrapEl) tableWrapEl.hidden = visible.length === 0;
    emptyEl.hidden = visible.length > 0;
    if (resultsCountEl) {
      resultsCountEl.textContent = t(lang, "results_count", {
        count: formatDayCount(visible.length, lang),
      });
    }

    syncChips();
    renderPagination(state);
    syncSearchAffordances();

    const relativeUrl = formatRelativeUrl(
      window.location.pathname,
      { q: searchEl.value, filter, sort, page },
      window.location.hash,
    );
    window.history.replaceState(null, "", relativeUrl);
  };

  const renderPagination = (state: PageState): void => {
    if (!pagerEl) return;
    const view = paginationView(state, lang);
    pagerEl.hidden = view.empty;
    pagerEl.setAttribute("aria-label", view.label);

    const first = pagerEl.querySelector<HTMLButtonElement>("[data-page-first]");
    const prev = pagerEl.querySelector<HTMLButtonElement>("[data-page-prev]");
    const next = pagerEl.querySelector<HTMLButtonElement>("[data-page-next]");
    const last = pagerEl.querySelector<HTMLButtonElement>("[data-page-last]");
    const range = pagerEl.querySelector<HTMLElement>("[data-page-range]");
    if (first) {
      first.disabled = view.firstDisabled;
      first.setAttribute("aria-label", view.firstLabel);
    }
    if (prev) {
      prev.disabled = view.prevDisabled;
      prev.setAttribute("aria-label", view.prevLabel);
    }
    if (next) {
      next.disabled = view.nextDisabled;
      next.setAttribute("aria-label", view.nextLabel);
    }
    if (last) {
      last.disabled = view.lastDisabled;
      last.setAttribute("aria-label", view.lastLabel);
    }
    if (range && range.textContent !== view.range) range.textContent = view.range;
  };

  const goTo = (next: number): void => {
    page = Math.max(1, next);
    render();
    if (window.innerWidth < DESKTOP_MIN_WIDTH && mainEl && mainEl.getBoundingClientRect().top < 0) {
      mainEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  searchEl.addEventListener("input", () => {
    page = 1;
    render();
  });

  searchClearBtn?.addEventListener("click", () => {
    searchEl.value = "";
    page = 1;
    render();
    searchEl.focus();
  });

  window.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tag = document.activeElement?.tagName;
      if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        searchEl.focus();
        searchEl.select();
      }
    }
  });

  window.addEventListener("resize", () => {
    const nextSize = measurePageSize();
    if (nextSize !== currentPageSize) {
      render();
    }
  });

  clearEl.addEventListener("click", () => {
    searchEl.value = "";
    filter = null;
    page = 1;
    render();
    searchEl.focus();
  });

  chipEls.forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-filter-chip");
      if (!isFilterChipId(id)) return;
      filter = filter === id ? null : id;
      page = 1;
      render();
    });
  });

  sortEl?.addEventListener("input", () => {
    if (isSortMode(sortEl.value)) {
      sort = sortEl.value;
      page = 1;
      render();
    }
  });

  headEl.addEventListener("click", (event) => {
    const trigger = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-sort-col]");
    if (!trigger) return;
    const col = trigger.getAttribute("data-sort-col");
    if (col === "name") {
      sort = "name";
    } else if (col === "status") {
      sort = sort === "drought" ? "recent" : "drought";
    } else {
      return;
    }
    if (sortEl) sortEl.value = sort;
    page = 1;
    render();
  });

  pagerEl?.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(
      "[data-page-first], [data-page-prev], [data-page-next], [data-page-last]",
    );
    if (!button || button.disabled) return;
    if (button.hasAttribute("data-page-first")) {
      goTo(1);
    } else if (button.hasAttribute("data-page-prev")) {
      goTo(page - 1);
    } else if (button.hasAttribute("data-page-next")) {
      goTo(page + 1);
    } else if (button.hasAttribute("data-page-last")) {
      goTo(totalPages);
    }
  });

  applyStaticText();
  render();
  // Segunda comprobación tras pintar fuentes/layout inicial por si la altura de fila difiere del SSR
  const settledSize = measurePageSize();
  if (settledSize !== currentPageSize) {
    render();
  }
}
