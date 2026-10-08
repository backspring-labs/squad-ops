-- 1710_memory_observations.sql
-- SIP-0110 §0.2–§0.3 (slice 3a, #2096): Cross-Cycle Memory's observations, one row per source record
-- (a rejected plan, a failed correction round, a returned proposal), projected idempotently from the
-- records that stay authoritative. Stored beside the cycle registry (the 2.2 plan's D13). No foreign
-- key to cycles: a returned proposal may name no cycle, and an observation outlives a cleared cycle.
-- The source CHECK is the Python enum's values (ObservationSource), held equal by a test.

CREATE TABLE IF NOT EXISTS memory_observations (
    source_id       TEXT PRIMARY KEY,
    source          TEXT NOT NULL
        CHECK (source IN ('plan_review', 'correction_round', 'proposal_ruling')),
    project_id      TEXT NOT NULL,
    campaign_id     TEXT,
    cycle_id        TEXT,
    run_id          TEXT,
    task_id         TEXT,
    observed_at     TIMESTAMPTZ NOT NULL,
    classification  JSONB NOT NULL,
    evidence        JSONB NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_observations_project
    ON memory_observations (project_id, observed_at);
