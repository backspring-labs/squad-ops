-- 1791_campaign_instruct.sql
-- SIP-0110 Appendix A §3.5 (#2178): a task instruction added to, revised on or withdrawn from a
-- campaign's cycle after its admission is recorded in the campaign's control log as a record-only
-- operation, 'instruct'. The control log's operation CHECK list is the Python enum's values
-- (ControlOperation), held equal by test_campaign_schema.py; it is replaced whole, by name, so
-- re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct'));
