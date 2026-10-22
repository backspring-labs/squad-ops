-- SIP-0113 §10p ruling 8 (#2564 build step 4): a failed or blocked page scenario's evidence, kept
-- for its evaluation. A screenshot of a filled form shows a step's values, so this table is held out
-- like scenario_suites: the store's alone, read under scenarios:approve, never by a squad identity
-- (tests/unit/architecture/test_held_out_scenarios_stay_out_of_the_squads_reach.py), and purged at
-- the line's cut. The sandbox caps it (512 KiB a scenario, 4 MiB an evaluation) and keeps no
-- screenshot from an evaluation that resolved a secret.

CREATE TABLE IF NOT EXISTS scenario_evidence (
    evaluation_id TEXT NOT NULL REFERENCES scenario_evaluations (evaluation_id),
    scenario_id TEXT NOT NULL,
    step INTEGER NOT NULL CHECK (step >= 1),
    screenshot BYTEA,
    details JSONB NOT NULL,
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size INTEGER NOT NULL CHECK (size >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (evaluation_id, scenario_id)
);
