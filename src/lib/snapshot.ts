import { SNAPSHOT_FIELDS, type BossSnapshot } from "./types";

export { SNAPSHOT_FIELDS } from "./types";

export class SnapshotError extends Error {}

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
