export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_STORAGE_KEY = "hlwr_theme";
export const LIGHT_THEME_COLOR = "#f6f5f1";
export const DARK_THEME_COLOR = "#121110";

export function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

export function resolveTheme(stored: string | null | undefined, prefersDark: boolean): Theme {
  if (isTheme(stored)) return stored;
  return prefersDark ? "dark" : "light";
}

export function nextTheme(current: Theme): Theme {
  return current === "dark" ? "light" : "dark";
}

export function themeColorMeta(theme: Theme): string {
  return theme === "light" ? LIGHT_THEME_COLOR : DARK_THEME_COLOR;
}

export function themeToggleLabelKey(current: Theme): "theme_switch_light" | "theme_switch_dark" {
  return current === "dark" ? "theme_switch_light" : "theme_switch_dark";
}
