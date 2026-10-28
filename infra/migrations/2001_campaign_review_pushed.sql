-- 2001_campaign_review_pushed.sql
-- SIP-0109 §24ci (b) (#2619): each push of a repository-backed Campaign's review request is a
-- record-only control-log operation, 'review_pushed', whose commit is the next push's lease. The
-- CHECK list is the Python enum's values (ControlOperation), held equal by test_campaign_schema.py;
-- it is replaced whole, by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased',
        'review_pushed'));
