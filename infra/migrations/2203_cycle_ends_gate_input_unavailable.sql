-- 2203_cycle_ends_gate_input_unavailable.sql
-- #3128 (SIP-0109 §24ei; the 2.9 plan's item 4): a gate between workloads that can't read an artifact
-- the run's record names ends the cycle `gate_input_unavailable`, a fault outside the work, and the
-- ending names the artifact in `detail`. 1670's CHECK list is CycleStopReason's values, and a table it
-- already created keeps its old list (1696, 2003 and 2202 each replaced it), so the list is replaced
-- again here. Held equal to CycleStopReason by tests/unit/cycles/test_cycle_ends.py, which reads the
-- latest list. Idempotent DDL.

ALTER TABLE cycle_ends ADD COLUMN IF NOT EXISTS detail TEXT;
ALTER TABLE cycle_ends DROP CONSTRAINT IF EXISTS cycle_ends_stopped_because_check;
ALTER TABLE cycle_ends ADD CONSTRAINT cycle_ends_stopped_because_check CHECK (stopped_because IN ('sequence_completed', 'single_workload_ended', 'run_failed', 'run_cancelled', 'run_paused', 'run_not_terminal', 'plan_rejected', 'gate_rejected', 'revision_unavailable', 'gate_decision_unrecognized', 'gate_failed', 'gate_input_unavailable', 'criteria_not_checkable', 'skill_stopped'));
