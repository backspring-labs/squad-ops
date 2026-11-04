-- 2004_campaign_contribution_failed.sql
-- SIP-0109 §24dc (#2861): a closed Campaign's contribution to the product that could not be
-- opened is a record-only control-log operation, 'contribution_failed', naming why; the
-- contribution stays due and the next attempt opens it. The CHECK list is the Python enum's
-- values (ControlOperation), held equal by test_campaign_schema.py; it is replaced whole, by name,
-- so re-applying is a no-op. (2002 is PR #2914's and 2003 is held for another branch.)

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased',
        'review_pushed', 'contribution_failed'));
