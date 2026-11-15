-- 2005_box_operator_lease.sql
-- SIP-0109 §24dw (#2287): the operator's lease on the box, outside every campaign. The box's one
-- lease row may now be held by the operator, with an expiry and no campaign, and every change the
-- operator asks for is a row of its own log, applied or refused, with what the refusal read. The
-- holder's CHECK list is LeaseHolder's values, held equal by test_campaign_schema.py; the
-- operation, outcome and refusal lists are OperatorLeaseOperation's, ControlOutcome's and
-- OperatorLeaseRefusal's. Constraints are replaced by name, so re-applying is a no-op.

ALTER TABLE box_lease DROP CONSTRAINT IF EXISTS box_lease_holder_check;
ALTER TABLE box_lease ADD CONSTRAINT box_lease_holder_check
    CHECK (holder IN ('squad', 'supervisor', 'operator'));

-- 1690's table CHECK: a supervisor's lease, and only one, carries an expiry. Now the
-- supervisor's and the operator's do, and only the supervisor's names a campaign.
ALTER TABLE box_lease DROP CONSTRAINT IF EXISTS box_lease_check;
ALTER TABLE box_lease DROP CONSTRAINT IF EXISTS box_lease_expiry_check;
ALTER TABLE box_lease ADD CONSTRAINT box_lease_expiry_check
    CHECK ((holder <> 'squad') = (expires_at IS NOT NULL));
ALTER TABLE box_lease DROP CONSTRAINT IF EXISTS box_lease_operator_campaign_check;
ALTER TABLE box_lease ADD CONSTRAINT box_lease_operator_campaign_check
    CHECK (holder <> 'operator' OR campaign_id IS NULL);

CREATE TABLE IF NOT EXISTS box_lease_log (
    seq             BIGINT PRIMARY KEY,
    operation       TEXT NOT NULL CHECK (operation IN ('acquire', 'release')),
    outcome         TEXT NOT NULL CHECK (outcome IN ('applied', 'refused')),
    actor           TEXT NOT NULL,
    actor_role      TEXT NOT NULL,
    reason          TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    committed_at    TIMESTAMPTZ NOT NULL,
    expires_in_s    INTEGER,
    refusal         TEXT CHECK (refusal IN (
        'run_in_flight', 'campaign_live', 'box_held', 'not_lease_holder',
        'conflicting_idempotency_key')),
    reasons         JSONB NOT NULL DEFAULT '[]'::jsonb,
    CHECK ((operation = 'acquire') = (expires_in_s IS NOT NULL)),
    CHECK ((outcome = 'refused') = (refusal IS NOT NULL))
);
