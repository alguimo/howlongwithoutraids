import type { Language } from "./types";

export const LANGUAGES: Language[] = ["es", "en", "fr"];

export const CATALOGS: Record<Language, Record<string, string>> = {
  en: {
    title: "How Long Without Raids",
    search_placeholder: "Search by name or dex",
    no_results: "No results",
    clear: "Clear",
    language_label: "Language",
    active_now: "Active now",
    ended_today: "Ended today",
    upcoming: "Upcoming",
    day: "{n} day",
    days: "{n} days",
    last_regular: "Last rotation",
    last_special: "Last event",
    event_tag: "Event",
    current_window: "Current window",
    next_window: "Next window",
    footer_data: "Data from",
    col_image: "Image",
    col_name: "Name",
    col_status: "Status",
    col_date: "Date",
    col_tier: "Tier",
    pagination: "Pagination",
    prev_page: "Previous page",
    next_page: "Next page",
    page_range: "{from}–{to} of {total}",
  },
  es: {
    title: "How Long Without Raids",
    search_placeholder: "Buscar por nombre o dex",
    no_results: "Sin resultados",
    clear: "Limpiar",
    language_label: "Idioma",
    active_now: "Activo ahora",
    ended_today: "Terminó hoy",
    upcoming: "Próximo",
    day: "{n} día",
    days: "{n} días",
    last_regular: "Última rotación",
    last_special: "Último evento",
    event_tag: "Evento",
    current_window: "Ventana vigente",
    next_window: "Próxima ventana",
    footer_data: "Datos de",
    col_image: "Imagen",
    col_name: "Nombre",
    col_status: "Estado",
    col_date: "Fecha",
    col_tier: "Tier",
    pagination: "Paginación",
    prev_page: "Página anterior",
    next_page: "Página siguiente",
    page_range: "{from}–{to} de {total}",
  },
  fr: {
    title: "How Long Without Raids",
    search_placeholder: "Rechercher par nom ou dex",
    no_results: "Aucun résultat",
    clear: "Effacer",
    language_label: "Langue",
    active_now: "Actif maintenant",
    ended_today: "Terminé aujourd'hui",
    upcoming: "À venir",
    day: "{n} jour",
    days: "{n} jours",
    last_regular: "Dernière rotation",
    last_special: "Dernier événement",
    event_tag: "Événement",
    current_window: "Fenêtre en cours",
    next_window: "Prochaine fenêtre",
    footer_data: "Données de",
    col_image: "Image",
    col_name: "Nom",
    col_status: "État",
    col_date: "Date",
    col_tier: "Tier",
    pagination: "Pagination",
    prev_page: "Page précédente",
    next_page: "Page suivante",
    page_range: "{from}–{to} sur {total}",
  },
};

export function t(
  lang: Language,
  key: string,
  params?: Record<string, string | number>,
): string {
  const catalog = CATALOGS[lang] ?? CATALOGS.en;
  let text = catalog[key] ?? CATALOGS.en[key] ?? key;
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}
