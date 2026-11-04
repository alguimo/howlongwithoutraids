import { isFilterChipId, type FilterChipId } from "./categories";
import { isSortMode, type SortMode } from "./order";

export interface UrlState {
  q: string;
  filter: FilterChipId | null;
  sort: SortMode;
  page: number;
}

export const DEFAULT_URL_STATE: Readonly<UrlState> = {
  q: "",
  filter: null,
  sort: "recent",
  page: 1,
};

function parsePositiveInt(raw: string | null): number {
  if (!raw || !/^[1-9]\d*$/.test(raw)) return 1;
  const parsed = Number(raw);
  return Number.isSafeInteger(parsed) && parsed >= 1 ? parsed : 1;
}

export function parseUrlState(search: string): UrlState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const q = (params.get("q") ?? "").trim();
  const rawFilter = params.get("filter");
  const rawSort = params.get("sort");
  const page = parsePositiveInt(params.get("page"));

  return {
    q,
    filter: isFilterChipId(rawFilter) ? rawFilter : null,
    sort: isSortMode(rawSort) ? rawSort : "recent",
    page,
  };
}

export function buildUrlSearch(state: UrlState): string {
  const params = new URLSearchParams();
  const q = state.q.trim();
  if (q) params.set("q", q);
  if (state.filter !== null && isFilterChipId(state.filter)) {
    params.set("filter", state.filter);
  }
  if (state.sort !== "recent" && isSortMode(state.sort)) {
    params.set("sort", state.sort);
  }
  if (Number.isInteger(state.page) && state.page > 1) {
    params.set("page", String(state.page));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function formatRelativeUrl(pathname: string, state: UrlState, hash: string = ""): string {
  return `${pathname || "/"}${buildUrlSearch(state)}${hash}`;
}
