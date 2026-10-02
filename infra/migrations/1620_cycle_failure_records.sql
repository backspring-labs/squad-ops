-- 1620_cycle_failure_records.sql
-- SIP-0109 §14, §16 (#1710): a cycle's failure records, persisted at completion by the one
-- producer (failure_events) before the attribution is computed from them. A set is one ending's
-- records, appended in one transaction; a resumed run that ends the cycle again appends another,
-- and the latest set is the cycle's. A set with no records says "recorded, no failures", where no
-- set says "never recorded". Both tables are append-only: a record is evidence (§14).
-- No foreign key to cycle_registry: evidence about a cycle never blocks removing the cycle's row
-- (1051's reasoning). The state and class CHECK lists are the Python enums' values, held equal by
-- tests/unit/cycles/test_failure_records.py. All DDL is idempotent.

CREATE TABLE IF NOT EXISTS cycle_failure_record_sets (
    cycle_id TEXT NOT NULL,
    set_index INTEGER NOT NULL,
    last_run_id TEXT NOT NULL,
    registry_version INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (cycle_id, set_index)
);

CREATE TABLE IF NOT EXISTS cycle_failure_records (
    cycle_id TEXT NOT NULL,
    set_index INTEGER NOT NULL,
    event_index INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('recorded', 'unaskable')),
    registry_version INTEGER NOT NULL,
    event JSONB,
    attribution_class TEXT CHECK (attribution_class IN ('producer_output_failure', 'verification_artifact_failure', 'handoff_or_convergence_failure', 'input_contract_failure', 'budget_exhaustion', 'plan_gate_failure', 'criteria_or_contract_failure', 'write_authority_violation', 'environment_or_infrastructure_failure', 'unattributed')),
    unasked_input TEXT,
    campaign_id TEXT,
    increment_id TEXT,
    PRIMARY KEY (cycle_id, set_index, event_index),
    FOREIGN KEY (cycle_id, set_index) REFERENCES cycle_failure_record_sets (cycle_id, set_index),
    CHECK ((state = 'recorded') = (event IS NOT NULL)),
    CHECK ((state = 'unaskable') = (unasked_input IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_cycle_failure_records_class
    ON cycle_failure_records (attribution_class) WHERE attribution_class IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cycle_failure_records_campaign
    ON cycle_failure_records (campaign_id) WHERE campaign_id IS NOT NULL;

CREATE OR REPLACE FUNCTION cycle_failure_records_are_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only (SIP-0109 §14): % refused', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER cycle_failure_record_sets_append_only
    BEFORE UPDATE OR DELETE ON cycle_failure_record_sets
    FOR EACH ROW EXECUTE FUNCTION cycle_failure_records_are_append_only();

CREATE OR REPLACE TRIGGER cycle_failure_records_append_only
    BEFORE UPDATE OR DELETE ON cycle_failure_records
    FOR EACH ROW EXECUTE FUNCTION cycle_failure_records_are_append_only();
