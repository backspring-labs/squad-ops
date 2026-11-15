-- 2201_campaign_equipment_operations.sql
-- SIP-0116 §10, phase 5 (#3037): a Campaign pins the equipment of its first launched cycle, a
-- later launch whose equipment differs is refused with the parts named, and the owner's
-- transition accepts what it found. Three record-only control-log operations: 'equipment_pinned',
-- 'equipment_changed' and 'equipment_transition'. The CHECK list is the Python enum's values
-- (ControlOperation), held equal by test_campaign_schema.py; it is replaced whole, by name, so
-- re-applying is a no-op.

ALTER TABLE campaign_control_log DROP CONSTRAINT IF EXISTS campaign_control_log_operation_check;
ALTER TABLE campaign_control_log ADD CONSTRAINT campaign_control_log_operation_check
    CHECK (operation IN (
        'create', 'start', 'pause', 'resume', 'abort', 'submit', 'rule', 'decide', 'promote',
        'mark_launched', 'classify', 'ruling_overdue', 'lease_acquire', 'lease_release',
        'launch_blocked', 'launch_unblocked', 'launch_refused', 'escalation_opened',
        'escalation_closed', 'escalation_answered', 'rebind', 'instruct', 'branch_rebased',
        'review_pushed', 'contribution_failed', 'goal_delegation_granted',
        'contribution_dismissed', 'equipment_pinned', 'equipment_changed',
        'equipment_transition'));
