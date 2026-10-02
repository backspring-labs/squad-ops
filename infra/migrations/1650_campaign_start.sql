-- 1650_campaign_start.sql
-- SIP-0109 §17 (#1799, #1709): the owner's start — a draft campaign moves to calibrating and
-- its calibration cycle's launch intent is written in the same transaction. The operation CHECK
-- list is ControlOperation's values, held equal by test_campaign_schema.py; it is replaced
-- whole, by name, so re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched'));
