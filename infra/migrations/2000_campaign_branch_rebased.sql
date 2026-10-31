-- 2000_campaign_branch_rebased.sql
-- SIP-0109 §24bv point 4, §24cd point 2 (#2619): a repository-backed campaign's branch rebased
-- onto the commit its Project reconciled is a control-log operation, 'branch_rebased', and a
-- pending repair or retry it leaves nothing to continue is marked 'superseded' in the same
-- transaction. SIP-0109's range (1600-1699) is full, so its later migrations take 2000-2099.
-- Both CHECK lists are the Python enums' values (ControlOperation, LaunchIntentState), held equal
-- by test_campaign_schema.py; each is replaced whole, by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased'));

ALTER TABLE campaign_launch_intents DROP CONSTRAINT IF EXISTS campaign_launch_intents_state_check;
ALTER TABLE campaign_launch_intents ADD CONSTRAINT campaign_launch_intents_state_check
    CHECK (state IN ('pending', 'launched', 'superseded'));
