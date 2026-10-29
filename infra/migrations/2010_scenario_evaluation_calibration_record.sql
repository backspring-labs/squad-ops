-- 2010_scenario_evaluation_calibration_record.sql
-- SIP-0113 §10l (#2619; shared contract 5): on a repository-backed Project a Campaign's calibration
-- is a record, not a cycle (SIP-0109 §24bv point 1), and its baseline reading evaluates the record's
-- commit. That evaluation names the calibration record in place of a cycle: exactly one of the two,
-- as the campaign's accepted tree names one (1697). Every row written before this names a cycle,
-- so the constraint holds on them. It is replaced whole, by name, so re-applying is a no-op.

ALTER TABLE scenario_evaluations ADD COLUMN IF NOT EXISTS calibration_record_id TEXT;
ALTER TABLE scenario_evaluations ALTER COLUMN cycle_id DROP NOT NULL;

ALTER TABLE scenario_evaluations DROP CONSTRAINT IF EXISTS ck_scenario_evaluations_names_one;
ALTER TABLE scenario_evaluations ADD CONSTRAINT ck_scenario_evaluations_names_one
    CHECK ((cycle_id IS NULL) <> (calibration_record_id IS NULL));

CREATE INDEX IF NOT EXISTS scenario_evaluations_calibration_record
    ON scenario_evaluations (calibration_record_id, evaluated_at)
    WHERE calibration_record_id IS NOT NULL;
