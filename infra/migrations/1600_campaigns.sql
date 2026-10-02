-- 1600_campaigns.sql
-- SIP-0109 §13, §12b, §16 (#1799): the campaign, its control log and its launch outbox.
-- The control log is the authority: one append-only row per control operation, written in the
-- transaction of the state change it records. A launch intent is written in its decision's
-- transaction and marked launched with its cycle. The other §16 tables (the ledger, frozen
-- criteria, the box lease, verifier bundles) arrive with the steps that write them.
-- Each CHECK list is the Python enum's values (squadops.campaigns.models), held equal by
-- tests/unit/campaigns/test_campaign_schema.py. All DDL is idempotent.

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    objective   JSONB NOT NULL,
    policy      JSONB NOT NULL,
    state       TEXT NOT NULL CHECK (state IN (
        'draft', 'calibrating', 'at_proposal', 'awaiting_ruling', 'building', 'evaluating',
        'promoting', 'repairing', 'retrying', 'launch_blocked', 'paused', 'escalated',
        'completed')),
    outcome     TEXT CHECK (outcome IN ('success', 'failure', 'aborted', 'exhausted')),
    created_at  TIMESTAMPTZ NOT NULL,
    created_by  TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    CHECK ((state = 'completed') = (outcome IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_campaigns_project ON campaigns (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS campaign_control_log (
    entry_id        TEXT PRIMARY KEY,
    campaign_id     TEXT NOT NULL REFERENCES campaigns (campaign_id),
    seq             INTEGER NOT NULL,
    operation       TEXT NOT NULL CHECK (operation IN (
        'create', 'pause', 'resume', 'abort', 'rule', 'decide', 'promote', 'mark_launched')),
    actor           TEXT NOT NULL,
    actor_role      TEXT NOT NULL,
    reason          TEXT NOT NULL,
    target          TEXT,
    idempotency_key TEXT NOT NULL,
    request_hash    TEXT NOT NULL,
    binding         JSONB NOT NULL,
    outcome         TEXT NOT NULL CHECK (outcome IN ('applied', 'refused')),
    refusal         TEXT CHECK (refusal IN (
        'conflicting_idempotency_key', 'stale_state', 'illegal_transition',
        'campaign_completed')),
    prior_state     TEXT,
    next_state      TEXT NOT NULL,
    committed_at    TIMESTAMPTZ NOT NULL,
    launch_id       TEXT,
    UNIQUE (campaign_id, seq),
    CHECK ((outcome = 'refused') = (refusal IS NOT NULL))
);

-- An idempotency key names one applied operation per campaign. Refusals hold no key: the same
-- key, once legal, still applies.
CREATE UNIQUE INDEX IF NOT EXISTS uq_campaign_control_log_applied_key
    ON campaign_control_log (campaign_id, idempotency_key) WHERE outcome = 'applied';

-- Append-only: a control-log row is evidence, and evidence is never rewritten (§14).
CREATE OR REPLACE FUNCTION campaign_control_log_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'campaign_control_log is append-only (SIP-0109 §13): % refused', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER campaign_control_log_append_only
    BEFORE UPDATE OR DELETE ON campaign_control_log
    FOR EACH ROW EXECUTE FUNCTION campaign_control_log_is_append_only();

CREATE TABLE IF NOT EXISTS campaign_launch_intents (
    launch_id         TEXT PRIMARY KEY,
    campaign_id       TEXT NOT NULL REFERENCES campaigns (campaign_id),
    decision_entry_id TEXT NOT NULL UNIQUE REFERENCES campaign_control_log (entry_id),
    cycle_kind        TEXT NOT NULL CHECK (cycle_kind IN (
        'calibration', 'increment', 'repair', 'retry')),
    cycle_request     JSONB NOT NULL,
    state             TEXT NOT NULL CHECK (state IN ('pending', 'launched')),
    created_at        TIMESTAMPTZ NOT NULL,
    cycle_id          TEXT,
    launched_at       TIMESTAMPTZ,
    CHECK ((state = 'launched') = (cycle_id IS NOT NULL AND launched_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_campaign_launch_intents_pending
    ON campaign_launch_intents (created_at) WHERE state = 'pending';
