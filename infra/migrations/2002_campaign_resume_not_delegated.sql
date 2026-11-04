-- 2002_campaign_resume_not_delegated.sql
-- SIP-0109 §24da (#2891): a resume the crew's supervisor principal asked for that the Campaign did
-- not delegate to it is refused and recorded as 'resume_not_delegated'. The CHECK list is the
-- Python enum's values (RefusalReason), held equal by test_campaign_schema.py; it is replaced
-- whole, by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_refusal_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_refusal_check
    CHECK (refusal IN (
        'conflicting_idempotency_key', 'stale_state', 'illegal_transition', 'campaign_completed',
        'stale_binding', 'illegal_ruling', 'gate_not_open', 'run_in_flight', 'box_held',
        'not_lease_holder', 'resume_not_delegated'));
