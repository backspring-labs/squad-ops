-- 1680_campaign_ruling_overdue.sql
-- SIP-0109 §9.2, §9.5 (§24ae): the increment gate waited past a seat's ruling bound, recorded as a
-- control-log row ('ruling_overdue') that keeps the campaign awaiting_ruling. The operation CHECK
-- list is ControlOperation's values, held equal by test_campaign_schema.py; it is replaced whole,
-- by name.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue'));
