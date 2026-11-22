CREATE TYPE raid_variant AS ENUM (
  'NORMAL',
  'MEGA',
  'PRIMAL',
  'SHADOW',
  'APEX'
);

CREATE TYPE raid_tier AS ENUM (
  '1',
  '2',
  '3',
  '4',
  '5',
  'MEGA',
  'MEGA_LEGENDARY',
  'SUPER_MEGA',
  'PRIMAL',
  'ELITE',
  'SHADOW_1',
  'SHADOW_3',
  'SHADOW_5'
);

CREATE TYPE raid_source AS ENUM (
  'scrapedduck',
  'pogo_wiki',
  'bulbapedia',
  'fandom'
);

CREATE TABLE pokemon (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dex_number integer NOT NULL CHECK (dex_number > 0),
  form text NOT NULL DEFAULT 'normal' CHECK (form = lower(form) AND form <> ''),
  variant raid_variant NOT NULL DEFAULT 'NORMAL',
  name text NOT NULL CHECK (name <> ''),
  types text[] NOT NULL DEFAULT '{}',
  sprite_url text,
  -- PokeAPI species categories: true/false from the source, NULL when the
  -- species is absent from the catalog or the field is missing. Never a
  -- default false (constitution principle 13). is_ultra_beast comes from the
  -- canonical hard-coded dex list, so it is always known.
  is_legendary boolean,
  is_mythical boolean,
  is_baby boolean,
  is_ultra_beast boolean NOT NULL DEFAULT false,
  UNIQUE (dex_number, form, variant)
);

CREATE TABLE raid_appearances (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pokemon_id bigint NOT NULL REFERENCES pokemon (id),
  tier raid_tier NOT NULL,
  start_date timestamptz NOT NULL,
  end_date timestamptz NOT NULL,
  is_special_event boolean NOT NULL DEFAULT false,
  is_local_time boolean NOT NULL DEFAULT false,
  source raid_source NOT NULL,
  -- Raw event name of this appearance, populated by the pipeline sources
  -- (Fandom prose, Bulbapedia section heading, ScrapedDuck field). The
  -- snapshot does not store last_regular_event_name/last_special_event_name:
  -- export derives them from the appearance that fixes each last_* date.
  event_name text CHECK (event_name IS NULL OR btrim(event_name) <> ''),
  published_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date >= start_date)
);

CREATE TABLE raid_appearance_origins (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  appearance_id bigint NOT NULL REFERENCES raid_appearances (id) ON DELETE CASCADE,
  source raid_source NOT NULL,
  page_title text NOT NULL CHECK (btrim(page_title) <> ''),
  page_kind text NOT NULL CHECK (page_kind IN ('year', 'season', 'shadow')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (appearance_id, source, page_title)
);

CREATE INDEX raid_appearance_origins_appearance_idx
  ON raid_appearance_origins (appearance_id);

CREATE INDEX raid_appearances_pokemon_end_idx
  ON raid_appearances (pokemon_id, end_date DESC);

CREATE INDEX raid_appearances_pokemon_start_idx
  ON raid_appearances (pokemon_id, start_date DESC);
