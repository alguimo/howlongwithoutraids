import type { Language } from "./types";

export const STORAGE_KEY = "hlwr:lang";

const SUPPORTED: Language[] = ["es", "en", "fr"];

function isLanguage(value: unknown): value is Language {
  return SUPPORTED.includes(value as Language);
}

export interface LanguageStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function resolveInitialLanguage(
  navigatorLanguage: string | undefined | null,
  stored: string | null | undefined,
): Language {
  if (isLanguage(stored)) return stored;
  const base = (navigatorLanguage ?? "").slice(0, 2).toLowerCase();
  if (isLanguage(base)) return base;
  return "en";
}

export function readLanguage(storage: LanguageStorage): Language {
  return resolveInitialLanguage(undefined, storage.getItem(STORAGE_KEY));
}

export function writeLanguage(storage: LanguageStorage, lang: Language): void {
  storage.setItem(STORAGE_KEY, lang);
}
