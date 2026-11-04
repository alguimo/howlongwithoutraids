import { t } from "../lib/i18n";
import {
  THEME_STORAGE_KEY,
  isTheme,
  nextTheme,
  resolveTheme,
  themeColorMeta,
  themeToggleLabelKey,
  type Theme,
} from "../lib/theme";
import type { Language } from "../lib/types";

export interface ThemeControllerHandle {
  sync: (lang: Language) => void;
}

function readStoredTheme(): string | null {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* storage unavailable; keep in-memory theme */
  }
}

export function mountThemeController(initialLang: Language): ThemeControllerHandle {
  const button = document.getElementById("theme-toggle") as HTMLButtonElement | null;
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  let currentLang = initialLang;
  const initialStored = readStoredTheme();
  let hasManualPreference = isTheme(initialStored);
  let currentTheme: Theme = resolveTheme(initialStored, media ? media.matches : true);

  const apply = (): void => {
    document.documentElement.dataset.theme = currentTheme;
    if (meta) {
      meta.setAttribute("content", themeColorMeta(currentTheme));
    }
    if (button) {
      button.setAttribute("aria-label", t(currentLang, themeToggleLabelKey(currentTheme)));
    }
  };

  button?.addEventListener("click", () => {
    currentTheme = nextTheme(currentTheme);
    hasManualPreference = true;
    writeStoredTheme(currentTheme);
    apply();
  });

  media?.addEventListener("change", (event) => {
    if (hasManualPreference) return;
    currentTheme = resolveTheme(null, event.matches);
    apply();
  });

  apply();

  return {
    sync: (lang: Language) => {
      currentLang = lang;
      apply();
    },
  };
}
