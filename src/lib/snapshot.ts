import { SNAPSHOT_FIELDS, type BossSnapshot, type SnapshotMeta } from "./types";

export { SNAPSHOT_FIELDS } from "./types";

export class SnapshotError extends Error {}

/** `true`/`false`, o `null` cuando el catálogo no trae el dato (001 RF-40). */
function isBooleanOrNull(value: unknown): boolean {
  return typeof value === "boolean" || value === null;
}

/** `true`/`false`; nunca `null` (001 RF-41, lista canónica de Ultraentes). */
function isBoolean(value: unknown): boolean {
  return typeof value === "boolean";
}

/** Cadena no vacía o `null` (001, contrato de nombres de evento). */
function isEventName(value: unknown): boolean {
  return value === null || (typeof value === "string" && value.length > 0);
}

/**
 * Tipos del contrato de 001 para los campos que no basta con exigir por
 * presencia. El resto de campos mantienen el comportamiento actual de
 * `parseSnapshot` (solo se comprueba que la clave exista).
 */
const FIELD_TYPES: Record<string, (value: unknown) => boolean> = {
  is_legendary: isBooleanOrNull,
  is_mythical: isBooleanOrNull,
  is_baby: isBooleanOrNull,
  is_ultra_beast: isBoolean,
  last_regular_event_name: isEventName,
  last_special_event_name: isEventName,
  current_event_name: isEventName,
};

const VALID_TIERS = new Set([
  "1", "2", "3", "4", "5", "MEGA", "MEGA_LEGENDARY", "SUPER_MEGA",
  "PRIMAL", "ELITE", "SHADOW_1", "SHADOW_3", "SHADOW_5",
]);

function validateRow(row: unknown, index: number): BossSnapshot {
  if (typeof row !== "object" || row === null) {
    throw new SnapshotError(`row ${index} is not an object`);
  }
  const record = row as Record<string, unknown>;
  for (const field of SNAPSHOT_FIELDS) {
    if (!(field in record)) {
      throw new SnapshotError(`row ${index} is missing ${field}`);
    }
  }
  for (const [field, check] of Object.entries(FIELD_TYPES)) {
    if (!check(record[field])) {
      throw new SnapshotError(`row ${index} has an invalid ${field}`);
    }
  }
  for (const field of ["tier", "last_tier"] as const) {
    if (record[field] !== null && !VALID_TIERS.has(record[field] as string)) {
      throw new SnapshotError(`row ${index} has an invalid ${field}`);
    }
  }
  for (const key of ["dex_number", "form", "variant"] as const) {
    const value = record[key];
    if (value === null || value === undefined || value === "") {
      throw new SnapshotError(`row ${index} has an incomplete identity`);
    }
  }
  return record as unknown as BossSnapshot;
}

export function parseSnapshot(value: unknown): BossSnapshot[] {
  if (!Array.isArray(value)) {
    throw new SnapshotError("snapshot must be an array");
  }
  return value.map((row, index) => validateRow(row, index));
}

export function parseSnapshotMeta(value: unknown): SnapshotMeta {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new SnapshotError("snapshot metadata must be an object");
  }
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.length !== 1 || !("exported_at" in record)) {
    throw new SnapshotError("snapshot metadata must only contain exported_at");
  }
  const exportedAt = record.exported_at;
  if (exportedAt === null) {
    return { exported_at: null };
  }
  if (typeof exportedAt !== "string") {
    throw new SnapshotError("snapshot metadata exported_at must be a string or null");
  }
  const trimmed = exportedAt.trim();
  if (trimmed.length === 0 || !trimmed.endsWith("Z") || Number.isNaN(Date.parse(trimmed))) {
    throw new SnapshotError("snapshot metadata exported_at must be a valid UTC ISO string");
  }
  return { exported_at: exportedAt };
}
