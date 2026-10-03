export type Language = "es" | "en" | "fr";

export interface BossSnapshot {
  dex_number: number;
  form: string;
  variant: string;
  name: string;
  types: string[];
  sprite_url: string | null;
  current_start: string | null;
  current_end: string | null;
  last_regular_end_date: string | null;
  last_special_event_end_date: string | null;
  last_end_date: string | null;
  appearance_count: number;
  tier: string | null;
}

export const SNAPSHOT_FIELDS = [
  "dex_number",
  "form",
  "variant",
  "name",
  "types",
  "sprite_url",
  "current_start",
  "current_end",
  "last_regular_end_date",
  "last_special_event_end_date",
  "last_end_date",
  "appearance_count",
  "tier",
] as const;
