-- 1660_campaign_classify.sql
-- SIP-0109 §9.4: the supervisor's classification of what went wrong with a proposal, recorded as
-- a control-log row ('classify', record-only). The proposal ledger is read from the control log
-- (the submission, the ruling, the decision and the classification of each proposal version), so
-- no second table can disagree with it. The operation CHECK list is ControlOperation's values,
-- held equal by test_campaign_schema.py; it is replaced whole, by name.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify'));
