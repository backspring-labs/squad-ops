-- 1690_box_lease.sql
-- SIP-0109 §9.3 (#1802): the box's one lease, held by the squad or by the supervisor, and the
-- control-log operations that change it ('lease_acquire', 'lease_release') or record a launch the
-- box refused ('launch_blocked', 'launch_unblocked'). The lease's single row is seeded, held by
-- the squad, so a change always takes its row lock. A supervisor's lease, and only one, carries
-- an expiry. The CHECK lists are the Python enums' values (LeaseHolder, ControlOperation,
-- RefusalReason), held equal by test_campaign_schema.py; the control log's are replaced whole,
-- by name, so re-applying is a no-op.

CREATE TABLE IF NOT EXISTS box_lease (
    box_id      TEXT PRIMARY KEY CHECK (box_id = 'box'),
    holder      TEXT NOT NULL CHECK (holder IN ('squad', 'supervisor')),
    held_by     TEXT NOT NULL,
    campaign_id TEXT REFERENCES campaigns(campaign_id),
    acquired_at TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ,
    CHECK ((holder = 'supervisor') = (expires_at IS NOT NULL))
);

INSERT INTO box_lease (box_id, holder, held_by, campaign_id, acquired_at, expires_at)
VALUES ('box', 'squad', 'squadops', NULL, now(), NULL)
ON CONFLICT (box_id) DO NOTHING;

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked'));

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_refusal_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_refusal_check
    CHECK (refusal IN (
        'conflicting_idempotency_key', 'stale_state', 'illegal_transition', 'campaign_completed',
        'stale_binding', 'illegal_ruling', 'gate_not_open', 'run_in_flight', 'box_held',
        'not_lease_holder'));
