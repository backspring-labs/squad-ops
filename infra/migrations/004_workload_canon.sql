-- 004_workload_canon.sql
-- SIP-0076 Workload & Gate Canon: workload_type on runs.
-- All DDL is idempotent.

ALTER TABLE cycle_runs
    ADD COLUMN IF NOT EXISTS workload_type TEXT;

CREATE INDEX IF NOT EXISTS idx_cycle_runs_workload_type
    ON cycle_runs(workload_type)
    WHERE workload_type IS NOT NULL;
