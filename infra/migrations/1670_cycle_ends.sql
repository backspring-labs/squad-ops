-- 1670_cycle_ends.sql
-- SIP-0109 §12a (#1803): each ending of a cycle, recorded at the completion boundary before its
-- campaign is told, so a campaign whose completion hook did not decide (it failed, or the process
-- stopped first) is re-heard at startup from what the cycle recorded — never from a stop reason
-- reconstructed out of its runs. One row per ending, appended: a resumed run that ends the cycle
-- again appends another, and the latest is the cycle's. Append-only, like the failure records
-- beside it (1620). No foreign key to cycle_registry (1051's reasoning). The CHECK list is
-- CycleStopReason's values, held equal by tests/unit/cycles/test_cycle_ends.py. Idempotent DDL.

CREATE TABLE IF NOT EXISTS cycle_ends (
    cycle_id TEXT NOT NULL,
    end_index INTEGER NOT NULL,
    last_run_id TEXT NOT NULL,
    stopped_because TEXT NOT NULL CHECK (stopped_because IN ('sequence_completed', 'single_workload_ended', 'run_failed', 'run_cancelled', 'run_paused', 'run_not_terminal', 'plan_rejected', 'gate_rejected', 'revision_unavailable', 'gate_decision_unrecognized')),
    recorded_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (cycle_id, end_index)
);

CREATE OR REPLACE FUNCTION cycle_ends_are_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only (SIP-0109 §12a): % refused', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER cycle_ends_append_only
    BEFORE UPDATE OR DELETE ON cycle_ends
    FOR EACH ROW EXECUTE FUNCTION cycle_ends_are_append_only();
