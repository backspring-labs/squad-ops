-- 2102_campaign_goal_delegation.sql
-- SIP-0115 Q41, §10c; SIP-0109 §24dd (#2886): the owner's grant of a Campaign's goal-set curation
-- to the operator is a record-only control-log operation, 'goal_delegation_granted', which a live
-- Campaign alone takes. The operator's promotion, drop and split read it. The CHECK list is the Python
-- enum's values (ControlOperation), held equal by test_campaign_schema.py; it is replaced whole,
-- by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased',
        'review_pushed', 'contribution_failed', 'goal_delegation_granted'));
