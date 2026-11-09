-- 2104_campaign_contribution_dismissed.sql
-- SIP-0109 §24dg (#2926): the owner's dismissal of a closed, unmerged Campaign contribution is a
-- record-only control-log operation, 'contribution_dismissed'. It clears the contribution from the
-- unintegrated set, and the contribution's own row stays as it was. The CHECK list is the Python
-- enum's values (ControlOperation), held equal by test_campaign_schema.py; it is replaced whole, by
-- name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased',
        'review_pushed', 'contribution_failed', 'goal_delegation_granted',
        'contribution_dismissed'));
