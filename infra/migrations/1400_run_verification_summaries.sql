-- 1400_run_verification_summaries.sql
-- SIP-0096 Phase 3 (§10): durable per-run verification verdict/summary.
-- One row per run, written at run finalization (upsert on re-finalize). Feeds
-- the CycleOutcome roll-up (aggregate_cycle_outcome). verdict is the SIP-0096
-- run verdict, NOT a RunStatus (§6.5); the CHECK matches the RunVerdict StrEnum.

CREATE TABLE IF NOT EXISTS run_verification_summaries (
    run_id       TEXT PRIMARY KEY REFERENCES cycle_runs(run_id),
    verdict      TEXT NOT NULL CHECK (verdict IN ('accepted', 'rejected', 'blocked_unverified')),
    summary      JSONB NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rvs_verdict ON run_verification_summaries(verdict);
