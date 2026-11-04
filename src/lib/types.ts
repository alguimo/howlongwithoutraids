export type Language = "es" | "en" | "fr";

export interface SnapshotMeta {
  exported_at: string | null;
}

export interface BossSnapshot {
  dex_number: number;
  form: string;
  variant: string;
  name: string;
  is_legendary: boolean | null;
  is_mythical: boolean | null;
  is_baby: boolean | null;
  is_ultra_beast: boolean;
  types: string[];
  sprite_url: string | null;
  current_start: string | null;
  current_end: string | null;
  last_regular_end_date: string | null;
  last_regular_event_name: string | null;
  last_special_event_end_date: string | null;
  last_special_event_name: string | null;
  last_end_date: string | null;
  appearance_count: number;
  tier: string | null;
  last_tier: string | null;
  current_event_name: string | null;
}

export const SNAPSHOT_FIELDS = [
  "dex_number",
  "form",
  "variant",
  "name",
  "is_legendary",
  "is_mythical",
  "is_baby",
  "is_ultra_beast",
  "types",
  "sprite_url",
  "current_start",
  "current_end",
  "last_regular_end_date",
  "last_regular_event_name",
  "last_special_event_end_date",
  "last_special_event_name",
  "last_end_date",
  "appearance_count",
  "tier",
  "last_tier",
  "current_event_name",
] as const;
