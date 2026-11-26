-- 2202_cycle_ends_skill_stopped.sql
-- SIP-0116 §17o (#3041): a run whose task was answered with a stop one of its skills declares ends
-- `skill_stopped`, and its cycle's ending is recorded as that at the completion boundary, like every
-- other ending. 1670's CHECK list is CycleStopReason's values, and a table it already created keeps its
-- old list (1696 and 2003 each replaced it), so the list is replaced again here. Held equal to
-- CycleStopReason by tests/unit/cycles/test_cycle_ends.py, which reads the latest list. Idempotent DDL.

ALTER TABLE cycle_ends DROP CONSTRAINT IF EXISTS cycle_ends_stopped_because_check;
ALTER TABLE cycle_ends ADD CONSTRAINT cycle_ends_stopped_because_check CHECK (stopped_because IN ('sequence_completed', 'single_workload_ended', 'run_failed', 'run_cancelled', 'run_paused', 'run_not_terminal', 'plan_rejected', 'gate_rejected', 'revision_unavailable', 'gate_decision_unrecognized', 'gate_failed', 'criteria_not_checkable', 'skill_stopped'));
