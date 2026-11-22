# How Long Without Raids

Fast, static web app to check how long each Pokémon — including regional forms, Mega Evolutions, Primal forms, and Shadow variants — has gone without appearing in Pokémon GO raids, plus an **Upcoming** tab for announced rotations and Raid Days.

**Live site:** [https://alguimo.github.io/howlongwithoutraids/](https://alguimo.github.io/howlongwithoutraids/)

## Features

- **Zero backend in production:** built as a strict static Astro site (`output: "static"`). The browser makes zero external API calls at runtime.
- **Client-side drought calculation:** dates are stored as ISO timestamps and evaluated against the visitor's local clock (with local-time `10:00` rotation switchovers for Pokémon GO raid windows).
- **Instant search & quick filters:** search by localized name, form, Pokédex number, or category (`Legendary`, `Mega`, `Shadow`, `Ultra Beasts`, `Mythical`, `Active`), with URL-synced state.
- **Dedicated Upcoming tab:** chronological view of announced future raids showing countdowns, event names, and the drought each returning boss breaks (or `Debut` for first-time bosses).
- **Trilingual UI & dual theme:** Spanish, English, and French (auto-detected from browser language, defaulting to English), plus Warm Stone light mode and Warm Charcoal dark mode (WCAG 2.1 AA contrast verified).
- **Automated daily updates:** a GitHub Actions workflow syncs new rotations, caches sprites locally, persists the PostgreSQL state to a release artifact, and deploys to GitHub Pages.

## Architecture

1. **Local / CI Data Pipeline (`scripts/` & `db/`):**
   - PostgreSQL 16 (via Docker Compose locally or as a GitHub Actions service).
   - Python 3.11+ ETL scripts (`init_pokedex.py`, `backfill_history.py`, `sync_weekly.py`, `fetch_sprites.py`, `export_json.py`) that ingest historical and current raid rotations and export a validated, denormalized static snapshot (`src/data/raids-snapshot.json`).
2. **Static Frontend (`src/`):**
   - Astro 5 + TypeScript (strict) + Tailwind CSS 4.
   - Lightweight vanilla TypeScript client island (`src/client/`) with no heavy runtime framework.

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (only needed to run or update the local PostgreSQL pipeline)

### Run the data pipeline

```bash
docker compose up -d
python -m venv .venv
.venv/bin/pip install -e ./scripts

# First-time bootstrap (catalog + 2017–present history)
.venv/bin/python scripts/init_pokedex.py
.venv/bin/python scripts/backfill_history.py

# Weekly sync, local sprite download, and snapshot export
.venv/bin/python scripts/sync_weekly.py
.venv/bin/python scripts/fetch_sprites.py
.venv/bin/python scripts/export_json.py
```

### Run the frontend

```bash
npm ci
npm run dev
```

### Tests & production build

```bash
# Frontend tests (Vitest)
npm test

# ETL unit tests (offline)
.venv/bin/python -m pytest scripts/tests -m "not integration"

# ETL integration tests (requires Docker Postgres running)
.venv/bin/python -m pytest scripts/tests -m integration

# Static build
npm run build
```

## Data Sources & Attribution

- **Current & upcoming rotations:** [LeekDuck](https://leekduck.com) via [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck)
- **Historical raid archive (2017–present):** [Pokémon GO Wiki (Fandom)](https://pokemongo.fandom.com) and [Bulbapedia](https://bulbapedia.bulbagarden.net) (via MediaWiki API)
- **Species catalog, localized names & sprites:** [PokéAPI](https://pokeapi.co)

## Disclaimer

This is an unofficial, non-commercial, ad-free fan project. Pokémon and Pokémon GO are trademarks of Nintendo, Creatures Inc., GAME FREAK Inc., and Niantic, Inc.
