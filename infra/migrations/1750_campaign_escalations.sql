-- 1750_campaign_escalations.sql
-- SIP-0109 §24bj, §24bk (#1708): the plan-review tier's escalation queue is two record-only
-- control-log operations, 'escalation_opened' and 'escalation_closed'. The control log's operation
-- CHECK list is the Python enum's values (ControlOperation), held equal by test_campaign_schema.py;
-- it is replaced whole, by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed'));
