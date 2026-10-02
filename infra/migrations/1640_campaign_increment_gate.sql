-- 1640_campaign_increment_gate.sql
-- SIP-0109 §9.2 (#1801): the increment gate. A proposal is submitted to it (operation 'submit'),
-- and a ruling bound to a proposal or accepted tree that is no longer current is refused as
-- 'stale_binding'; a ruling the gate does not take ('approved_with_refinements') as
-- 'illegal_ruling'. campaigns.proposal is the proposal last submitted: the one a ruling binds to
-- and a repair or retry re-checks (§10a). Written only in a submission's transaction.
-- The CHECK lists are ControlOperation's and RefusalReason's values, held equal by
-- test_campaign_schema.py; each is replaced whole, by name, so re-applying is a no-op.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS proposal JSONB;

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched'));

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_refusal_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_refusal_check
    CHECK (refusal IN (
        'conflicting_idempotency_key', 'stale_state', 'illegal_transition', 'campaign_completed',
        'stale_binding', 'illegal_ruling'));
