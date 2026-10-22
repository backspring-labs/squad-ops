-- 1960_quality_remeasures.sql
-- SIP-0113 §10j, §10n ruling 1 (#2562): re-measures of an evaluated tree's quality readings, taken
-- again later, in a table of their own. Never rows of scenario_evaluations: there a re-measure would
-- become its cycle's latest record and replace the real one in every package rebuilt after.

CREATE TABLE IF NOT EXISTS quality_remeasures (
    remeasure_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES scenario_evaluations (evaluation_id),
    project_id TEXT NOT NULL,
    campaign_id TEXT,
    cycle_id TEXT NOT NULL,
    evaluated_tree_identity TEXT NOT NULL CHECK (evaluated_tree_identity ~ '^[0-9a-f]{64}$'),
    previous_accepted_tree_identity TEXT
        CHECK (previous_accepted_tree_identity ~ '^[0-9a-f]{64}$'),
    provenance TEXT NOT NULL CHECK (length(trim(provenance)) > 0),
    round INTEGER NOT NULL CHECK (round >= 1),
    measured_at TIMESTAMPTZ NOT NULL,
    quality JSONB,
    lint JSONB,
    quality_seeded JSONB,
    UNIQUE (evaluation_id, provenance, round)
);

CREATE INDEX IF NOT EXISTS quality_remeasures_cycle ON quality_remeasures (cycle_id, provenance);
