CREATE TYPE raid_variant AS ENUM (
  'NORMAL',
  'MEGA',
  'PRIMAL',
  'SHADOW',
  'APEX'
);

CREATE TYPE raid_tier AS ENUM (
  '1',
  '3',
  '4',
  '5',
  'MEGA',
  'MEGA_LEGENDARY',
  'PRIMAL',
  'ELITE',
  'SHADOW_1',
  'SHADOW_3',
  'SHADOW_5'
);

CREATE TYPE raid_source AS ENUM (
  'scrapedduck',
  'pogo_wiki',
  'bulbapedia'
);

CREATE TABLE pokemon (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dex_number integer NOT NULL CHECK (dex_number > 0),
  form text NOT NULL DEFAULT 'normal' CHECK (form = lower(form) AND form <> ''),
  variant raid_variant NOT NULL DEFAULT 'NORMAL',
  name text NOT NULL CHECK (name <> ''),
  types text[] NOT NULL DEFAULT '{}',
  sprite_url text,
  UNIQUE (dex_number, form, variant)
);

CREATE TABLE raid_appearances (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pokemon_id bigint NOT NULL REFERENCES pokemon (id),
  tier raid_tier NOT NULL,
  start_date timestamptz NOT NULL,
  end_date timestamptz NOT NULL,
  is_special_event boolean NOT NULL DEFAULT false,
  source raid_source NOT NULL,
  published_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date >= start_date)
);

CREATE INDEX raid_appearances_pokemon_end_idx
  ON raid_appearances (pokemon_id, end_date DESC);

CREATE INDEX raid_appearances_pokemon_start_idx
  ON raid_appearances (pokemon_id, start_date DESC);
