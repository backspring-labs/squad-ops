-- 1920_intervention_ledger.sql
-- SIP-0113 §4.3 (#2417): the intervention ledger's classifications, keyed by the control-log row
-- they classify, and the declared entries for actions outside the interface. Never control-log rows.

CREATE TABLE IF NOT EXISTS intervention_classifications (
    entry_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('clarification','planning','implementation','verification','environment','tool','coordination','memory_or_context','judgement_or_escalation','authorization')),
    severity TEXT NOT NULL CHECK (severity IN ('advisory','unblock','recovery','abort')),
    squad_could_resolve BOOLEAN,
    note TEXT NOT NULL DEFAULT '',
    classified_by TEXT NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS intervention_classifications_campaign
    ON intervention_classifications (campaign_id);

CREATE TABLE IF NOT EXISTS declared_interventions (
    declared_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('clarification','planning','implementation','verification','environment','tool','coordination','memory_or_context','judgement_or_escalation','authorization')),
    severity TEXT NOT NULL CHECK (severity IN ('advisory','unblock','recovery','abort')),
    description TEXT NOT NULL CHECK (description <> ''),
    occurred_at TIMESTAMPTZ NOT NULL,
    declared_by TEXT NOT NULL,
    declared_at TIMESTAMPTZ NOT NULL,
    squad_could_resolve BOOLEAN
);

CREATE INDEX IF NOT EXISTS declared_interventions_campaign ON declared_interventions (campaign_id);
