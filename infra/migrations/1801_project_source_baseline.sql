-- 1801_project_source_baseline.sql
-- SIP-0112 E.4.2 (#2409): a registered Project's validation. It reaches the product's source
-- through the managed clone and records what the base ref names: the development baseline
-- commit, and the integrated upstream commit, which are equal at registration (FR-06, contract
-- 1's ProjectSourceContext). A failed validation keeps its diagnostic beside the
-- FAILED_REGISTRATION status (§B.6); a retry clears it.

ALTER TABLE project_records ADD COLUMN IF NOT EXISTS development_baseline_commit TEXT;
ALTER TABLE project_records ADD COLUMN IF NOT EXISTS integrated_upstream_commit TEXT;
ALTER TABLE project_records ADD COLUMN IF NOT EXISTS validation_diagnostic TEXT;

-- The operation list is replaced whole, by name, so re-applying is a no-op (the 1690 shape).
ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN ('seed', 'register', 'validate', 'owner_decision'));
