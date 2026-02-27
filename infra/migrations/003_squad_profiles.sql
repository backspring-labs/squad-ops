-- Squad profile storage (SIP-0075 §5.2)
--
-- Postgres-backed squad profiles with YAML seeding.
-- Profiles are the operator's primary experimentation lever:
-- model assignments, config overrides, squad composition.

CREATE TABLE IF NOT EXISTS squad_profiles (
    profile_id     TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    version        INTEGER NOT NULL DEFAULT 1,
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    agents         JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- At most one active profile at a time.
-- Partial unique index: only rows where is_active = TRUE are constrained.
CREATE UNIQUE INDEX IF NOT EXISTS idx_squad_profiles_active
    ON squad_profiles (is_active) WHERE is_active = TRUE;

-- Seed log: tracks profile_ids that have ever been seeded from YAML.
-- Prevents deleted profiles from being re-seeded on restart.
CREATE TABLE IF NOT EXISTS squad_profiles_seed_log (
    profile_id  TEXT PRIMARY KEY,
    seeded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
