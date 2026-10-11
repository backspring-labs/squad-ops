-- 1696_cycle_ends_gate_failed.sql
-- SIP-0109 §12a (#2213): a cycle whose inter-workload gate raised before any decision ends `gate_failed`,
-- recorded at the completion boundary like every other ending. 1670's CHECK list is CycleStopReason's values,
-- and a table it already created keeps its old list, so the list is replaced here. Held equal to
-- CycleStopReason by tests/unit/cycles/test_cycle_ends.py, which reads the latest list. Idempotent DDL.

ALTER TABLE cycle_ends DROP CONSTRAINT IF EXISTS cycle_ends_stopped_because_check;
ALTER TABLE cycle_ends ADD CONSTRAINT cycle_ends_stopped_because_check CHECK (stopped_because IN ('sequence_completed', 'single_workload_ended', 'run_failed', 'run_cancelled', 'run_paused', 'run_not_terminal', 'plan_rejected', 'gate_rejected', 'revision_unavailable', 'gate_decision_unrecognized', 'gate_failed'));
