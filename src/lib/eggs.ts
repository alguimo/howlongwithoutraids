import type { FilterChipId } from "./categories";

export type RaidEggType =
  | "normal"
  | "rare"
  | "legendary"
  | "mega"
  | "primal"
  | "shadow"
  | "elite";

export interface TierBadgeStyle {
  badge: string;
  text: string;
}

/** Mapea el tier de incursión al tipo de huevo correspondiente en Pokémon GO. */
export function tierToEggType(tier: string | null | undefined): RaidEggType | null {
  if (!tier) return null;
  const normalized = tier.trim().toUpperCase();

  switch (normalized) {
    case "1":
    case "2":
      return "normal";
    case "3":
    case "4":
      return "rare";
    case "5":
      return "legendary";
    case "MEGA":
    case "SUPER_MEGA":
      return "mega";
    case "PRIMAL":
    case "MEGA_LEGENDARY":
      return "primal";
    case "SHADOW_1":
    case "SHADOW_3":
    case "SHADOW_5":
      return "shadow";
    case "ELITE":
      return "elite";
    default:
      return null;
  }
}

/** Devuelve las clases semánticas para el badge temático por tipo de huevo,
 *  resueltas en CSS para garantizar contraste WCAG AA ≥ 4.5:1 en modo claro y oscuro. */
export function tierBadgeStyles(type: RaidEggType | null): TierBadgeStyle {
  switch (type) {
    case "legendary":
      return {
        badge: "tier-badge tier-badge-legendary",
        text: "tier-text-legendary",
      };
    case "mega":
      return {
        badge: "tier-badge tier-badge-mega",
        text: "tier-text-mega",
      };
    case "shadow":
      return {
        badge: "tier-badge tier-badge-shadow",
        text: "tier-text-shadow",
      };
    case "normal":
      return {
        badge: "tier-badge tier-badge-normal",
        text: "tier-text-normal",
      };
    case "rare":
      return {
        badge: "tier-badge tier-badge-rare",
        text: "tier-text-rare",
      };
    case "primal":
      return {
        badge: "tier-badge tier-badge-primal",
        text: "tier-text-primal",
      };
    case "elite":
      return {
        badge: "tier-badge tier-badge-elite",
        text: "tier-text-elite",
      };
    default:
      return {
        badge: "tier-badge tier-badge-default",
        text: "tier-text-default",
      };
  }
}

const EGG_PATH =
  "M12 2.5C7.8 2.5 4.5 7.5 4.5 13.5C4.5 18 7.8 21.5 12 21.5C16.2 21.5 19.5 18 19.5 13.5C19.5 7.5 16.2 2.5 12 2.5Z";

function eggPattern(type: RaidEggType): string {
  switch (type) {
    case "normal":
      return `
        <path d="${EGG_PATH}" fill="#ec4899" stroke="#be185d" stroke-width="0.7" />
        <ellipse cx="9.2" cy="9.2" rx="1.9" ry="2.3" fill="#ffffff" opacity="0.9" />
        <ellipse cx="14.8" cy="13.8" rx="2.1" ry="2.6" fill="#ffffff" opacity="0.9" />
        <circle cx="9.8" cy="17" r="1.4" fill="#ffffff" opacity="0.9" />
      `;
    case "rare":
      return `
        <path d="${EGG_PATH}" fill="#facc15" stroke="#ca8a04" stroke-width="0.7" />
        <ellipse cx="9.8" cy="8.6" rx="2.3" ry="1.9" fill="#e11d48" opacity="0.9" />
        <ellipse cx="14.4" cy="13.6" rx="2.5" ry="2" fill="#e11d48" opacity="0.9" />
        <circle cx="8.8" cy="16.6" r="1.5" fill="#e11d48" opacity="0.9" />
      `;
    case "legendary":
      return `
        <path d="${EGG_PATH}" fill="#1e1b4b" stroke="#f59e0b" stroke-width="0.9" />
        <path d="M5.1 10.2Q12 11.4 18.9 10.2L19.3 14.6Q12 15.8 4.7 14.6Z" fill="#f59e0b" />
        <path d="M4.9 11.5Q12 12.6 19.1 11.5L19.2 13.3Q12 14.4 4.8 13.3Z" fill="#fef08a" />
        <path d="M12 5.4L13.6 9.4H17.8L14.4 11.9L15.7 16L12 13.5L8.3 16L9.6 11.9L6.2 9.4H10.4Z" fill="#ffffff" stroke="#1e1b4b" stroke-width="0.7" />
      `;
    case "mega":
      return `
        <path d="${EGG_PATH}" fill="#ecfeff" stroke="#0891b2" stroke-width="0.9" />
        <path d="M7.5 6.8C10.8 9.4 13.2 14.6 16.5 18.2" stroke="#06b6d4" stroke-width="2.5" stroke-linecap="round" />
        <path d="M16.5 6.8C13.2 9.4 10.8 14.6 7.5 18.2" stroke="#0e7490" stroke-width="1.9" stroke-linecap="round" />
        <circle cx="12" cy="12.5" r="2.3" fill="#22d3ee" stroke="#0e7490" stroke-width="0.6" />
      `;
    case "primal":
      return `
        <path d="${EGG_PATH}" fill="#881337" stroke="#fb7185" stroke-width="0.9" />
        <path d="M12 5.2V19M6.4 12.5H17.6" stroke="#fda4af" stroke-width="1.6" stroke-dasharray="2 1.8" stroke-linecap="round" />
        <circle cx="12" cy="12.5" r="3.4" fill="#4c0519" stroke="#38bdf8" stroke-width="1.7" />
      `;
    case "shadow":
      return `
        <path d="${EGG_PATH}" fill="#18181b" stroke="#9333ea" stroke-width="0.9" />
        <path d="M7.4 19.6C6.9 16 10.4 14.6 9.8 10.2C11.8 12.8 13.6 11.2 13 7.4C15.6 10.8 16.8 15.2 16.4 19.6C14.8 20.8 9.2 20.8 7.4 19.6Z" fill="#9333ea" />
        <path d="M9.4 20.2C9.5 17.2 11.6 15.8 11.3 12.8C12.8 14.6 13.9 13.8 13.5 10.5C15.1 13 15.6 16.8 14.6 20.2C13.2 21 10.8 21 9.4 20.2Z" fill="#d8b4fe" />
        <circle cx="9.2" cy="13" r="1" fill="#fb7185" />
        <circle cx="14.8" cy="13" r="1" fill="#fb7185" />
      `;
    case "elite":
      return `
        <path d="${EGG_PATH}" fill="#991b1b" stroke="#f87171" stroke-width="0.9" />
        <path d="M12 4.2L7 13.6L12 19.8L17 13.6Z" fill="#7f1d1d" stroke="#fca5a5" stroke-width="0.9" />
        <path d="M12 4.2V19.8" stroke="#fecaca" stroke-width="0.9" />
      `;
  }
}

/** Devuelve el SVG vectorial inline del huevo de incursión correspondiente. */
export function eggSvg(type: RaidEggType, className = "h-4 w-4 shrink-0"): string {
  const pattern = eggPattern(type).trim();
  return `<svg viewBox="0 0 24 24" fill="none" class="${className}" aria-hidden="true" focusable="false">${pattern}</svg>`;
}

/** Devuelve el glifo o icono SVG vectorial correspondiente a un filtro rápido. */
export function chipIconSvg(id: FilterChipId, className = "h-3.5 w-3.5 shrink-0"): string {
  switch (id) {
    case "active":
      return `<svg viewBox="0 0 16 16" fill="none" class="${className}" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="3.5" fill="#10b981"/><circle cx="8" cy="8" r="6" stroke="#10b981" stroke-width="1.4" opacity="0.55"/></svg>`;
    case "legendary":
      return eggSvg("legendary", className);
    case "mega":
      return eggSvg("mega", className);
    case "shadow":
      return eggSvg("shadow", className);
    case "ultra_beast":
      return `<svg viewBox="0 0 16 16" fill="none" class="${className}" aria-hidden="true" focusable="false"><path d="M8 1.8L10 6L14.2 8L10 10L8 14.2L6 10L1.8 8L6 6Z" fill="#0284c7"/><circle cx="8" cy="8" r="1.6" fill="#e0f2fe"/></svg>`;
    case "mythical":
      return `<svg viewBox="0 0 16 16" fill="none" class="${className}" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="3.2" fill="#db2777"/><path d="M8 1.5V4M8 12V14.5M1.5 8H4M12 8H14.5" stroke="#db2777" stroke-width="1.5" stroke-linecap="round"/></svg>`;
  }
}
