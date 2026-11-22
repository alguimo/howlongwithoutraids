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
import { readStorage, writeStorage } from "./storage";

export interface ThemeControllerHandle {
  sync: (lang: Language) => void;
}

export function mountThemeController(initialLang: Language): ThemeControllerHandle {
  const button = document.getElementById("theme-toggle") as HTMLButtonElement | null;
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  let currentLang = initialLang;
  const initialStored = readStorage(THEME_STORAGE_KEY);
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
    writeStorage(THEME_STORAGE_KEY, currentTheme);
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
