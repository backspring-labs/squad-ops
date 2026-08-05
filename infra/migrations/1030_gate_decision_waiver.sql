-- SIP-0096 #682 (1.5 A2): operator gate waiver — accept-with-waiver records the
-- waived checks and reason ON the gate decision (§6.5/AC#12), above the evidence,
-- never mutating it. Additive + nullable: NULL (historical rows / no waiver) is
-- distinguishable from a recorded waiver; old code ignores the columns entirely
-- (1010-pattern compatibility). Forward-only; downgrade unsupported by policy.
ALTER TABLE cycle_gate_decisions ADD COLUMN IF NOT EXISTS waived_checks JSONB;
ALTER TABLE cycle_gate_decisions ADD COLUMN IF NOT EXISTS waiver_reason TEXT;
