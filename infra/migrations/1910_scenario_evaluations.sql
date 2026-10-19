-- 1910_scenario_evaluations.sql
-- SIP-0113 §4.1, §4.8 (#2415; shared contract 5): one record per evaluation run, a cycle evaluated
-- against one suite. Trees are named by SIP-0109's FileTree.identity, never by revision or commit.

CREATE TABLE IF NOT EXISTS scenario_evaluations (
    evaluation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    campaign_id TEXT,
    cycle_id TEXT NOT NULL,
    evaluated_tree_identity TEXT NOT NULL CHECK (evaluated_tree_identity ~ '^[0-9a-f]{64}$'),
    previous_accepted_tree_identity TEXT
        CHECK (previous_accepted_tree_identity ~ '^[0-9a-f]{64}$'),
    suite_digest TEXT NOT NULL REFERENCES scenario_suites (digest),
    outcomes JSONB NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS scenario_evaluations_cycle ON scenario_evaluations (cycle_id, evaluated_at);
