-- 1500_run_loop_summaries.sql
-- SIP-0108 §4.1: the run summary — one durable row per run with the loop facts no store held
-- (LLM usage accounted at _llm_call; refunds, movement and the terminal decision join as fields
-- of the same JSONB). Written at run finalization beside run_verification_summaries (upsert on
-- re-finalize). A historical run has no row: its indicators read unaskable, never backfilled.

CREATE TABLE IF NOT EXISTS run_loop_summaries (
    run_id           TEXT PRIMARY KEY REFERENCES cycle_runs(run_id),
    summary_version  INTEGER NOT NULL,
    summary          JSONB NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
