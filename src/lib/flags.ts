import type { Language } from "./types";

/** Orden fijo del desplegable de idioma: el de los catálogos. */
export const FLAG_LANG: Language[] = ["es", "en", "fr"];

/** Proporción 3:2, la de todas las banderas de estado. */
const VIEW_BOX = 'viewBox="0 0 60 40"';

/* Banderas dibujadas a mano en SVG en línea (RF-26).
 *
 * - Sin emoji: en Windows no se dibujan.
 * - Sin `<img>`, `<use>` ni referencias externas: el marcado viaja con el HTML.
 * - Sin `xmlns`: en HTML5 es innecesario y su URL rompería la comprobación de
 *   que la bandera no pide nada por red.
 * - `aria-hidden="true"` y `focusable="false"`: son decorativas y el nombre
 *   accesible de la opción es el texto del idioma (RF-23).
 */
const FLAGS: Record<Language, string> = {
  // España: tres franjas horizontales, amarilla de doble anchura en el centro.
  es: `<svg ${VIEW_BOX} width="24" height="16" aria-hidden="true" focusable="false"><rect width="60" height="40" fill="#aa151b"/><rect y="10" width="60" height="20" fill="#f1bf00"/></svg>`,
  // Union Jack: azul con la cruz y la diagonal blancas, y la roja más estrecha encima.
  en: `<svg ${VIEW_BOX} width="24" height="16" aria-hidden="true" focusable="false"><rect width="60" height="40" fill="#012169"/><path d="M0 0 60 40M60 0 0 40" stroke="#ffffff" stroke-width="8"/><path d="M30 0V40M0 20H60" stroke="#ffffff" stroke-width="12"/><path d="M0 0 60 40M60 0 0 40" stroke="#c8102e" stroke-width="4"/><path d="M30 0V40M0 20H60" stroke="#c8102e" stroke-width="7"/></svg>`,
  // Francia: tres franjas verticales iguales.
  fr: `<svg ${VIEW_BOX} width="24" height="16" aria-hidden="true" focusable="false"><rect width="20" height="40" fill="#002395"/><rect x="20" width="20" height="40" fill="#ffffff"/><rect x="40" width="20" height="40" fill="#ed2939"/></svg>`,
};

/** Devuelve el marcado de la bandera de un idioma, lista para insertar en el
 *  HTML. Es decorativa: quien nombra el idioma es el texto, no el gráfico. */
export function flagSvg(lang: Language): string {
  return FLAGS[lang] ?? FLAGS.en;
}
