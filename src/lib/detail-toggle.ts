/**
 * Cierre del detalle de fechas al tocar fuera (RF-33).
 *
 * Solo la parte que V15 necesita: plegar una fila desplegable y devolver su
 * `aria-expanded` a `false`. El modo (`hover: hover` / `hover: none`), el
 * tooltip, el `Enter`/`Espacio` y el nodo único los trae V16 y V21 en
 * `src/client/detail.ts`; este módulo no los anticipa, solo deja el plegado
 * escrito de forma comprobable.
 *
 * Los tipos son estructurales a propósito: el repositorio no tiene entorno de
 * DOM en los tests, así que el plegado se prueba con dobles en lugar de con un
 * navegador, y a la vez sigue aceptando los nodos reales tal cual.
 */

/** Clase que `html.ts` escribe cerrada y `global.css` esconde. */
export const HIDDEN_CLASS = "hidden";

/** Lo mínimo de una fila de detalle que hace falta para plegarla. */
export interface PanelTarget {
  classList: { add(className: string): void };
}

/** Lo mínimo de un botón de fecha que hace falta para desmarcarlo. */
export interface ButtonTarget {
  setAttribute(name: string, value: string): void;
}

/** Una fila de detalle y el botón de fecha que la controla. */
export interface DetailPair {
  panel: PanelTarget;
  button: ButtonTarget;
}

/**
 * Plega todos los detalles salvo el que se está tocando, para que nunca haya
 * más de una fila desplegada a la vez. Sin `keep` los plega todos: es lo que
 * hace un toque fuera de cualquier fecha.
 *
 * Solo añade la clase y pone `aria-expanded="false"`: nunca quita nada, así que
 * repetir el plegado no pisa el estado que V21 añada más adelante.
 */
export function foldOtherDetails(pairs: readonly DetailPair[], keep?: ButtonTarget): void {
  for (const pair of pairs) {
    if (keep && pair.button === keep) continue;
    pair.panel.classList.add(HIDDEN_CLASS);
    pair.button.setAttribute("aria-expanded", "false");
  }
}