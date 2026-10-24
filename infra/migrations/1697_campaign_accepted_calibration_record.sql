-- 1697_campaign_accepted_calibration_record.sql
-- SIP-0109 §24bv point 1, §24cc: on a repository-backed Project the calibration is a record, not
-- a cycle, so the accepted tree names the cycle whose candidate it is or the calibration record
-- whose commit it is, exactly one of the two (AcceptedTree). It replaces 1630's
-- both-or-neither constraint, by name, so re-applying is a no-op.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS accepted_calibration_record_id TEXT;

ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS ck_campaigns_accepted_together;
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS ck_campaigns_accepted_names_one;
ALTER TABLE campaigns ADD CONSTRAINT ck_campaigns_accepted_names_one
    CHECK (
        (accepted_identity IS NULL
            AND accepted_cycle_id IS NULL
            AND accepted_calibration_record_id IS NULL)
        OR (accepted_identity IS NOT NULL
            AND (accepted_cycle_id IS NULL) <> (accepted_calibration_record_id IS NULL))
    );
