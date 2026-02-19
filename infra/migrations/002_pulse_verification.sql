-- SIP-0070: Pulse Verification Records (D8)
-- Per-suite verification records with composite unique key.

CREATE TABLE IF NOT EXISTS pulse_verification_records (
    id                    SERIAL PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES cycle_runs(run_id),
    suite_id              TEXT NOT NULL,
    boundary_id           TEXT NOT NULL,
    cadence_interval_id   INTEGER NOT NULL,
    suite_outcome         TEXT NOT NULL,
    repair_attempt        INTEGER NOT NULL DEFAULT 0,
    check_results         JSONB NOT NULL DEFAULT '[]',
    repair_task_refs      TEXT[] NOT NULL DEFAULT '{}',
    notes                 TEXT,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, boundary_id, cadence_interval_id, suite_id, repair_attempt)
);

CREATE INDEX IF NOT EXISTS idx_pvr_run ON pulse_verification_records(run_id);
CREATE INDEX IF NOT EXISTS idx_pvr_run_boundary ON pulse_verification_records(run_id, boundary_id);
CREATE INDEX IF NOT EXISTS idx_pvr_run_cadence ON pulse_verification_records(run_id, cadence_interval_id);
