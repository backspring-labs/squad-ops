-- 1900_scenario_suites.sql
-- SIP-0113 §4.1, §4.7 (#2413): Outcome Evaluation's held-out scenario store, never the artifact
-- vault. A suite is keyed by its content's digest; the campaign's pin is keyed by the campaign.

CREATE TABLE IF NOT EXISTS scenario_suites (
    digest TEXT PRIMARY KEY,
    content JSONB NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('draft', 'approved')),
    drafted_by TEXT NOT NULL,
    drafted_at TIMESTAMPTZ NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    CHECK ((state = 'approved') = (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS campaign_scenario_suites (
    campaign_id TEXT PRIMARY KEY,
    suite_digest TEXT NOT NULL REFERENCES scenario_suites (digest),
    pinned_by TEXT NOT NULL,
    pinned_at TIMESTAMPTZ NOT NULL
);
