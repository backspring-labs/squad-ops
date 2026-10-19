-- 1805_project_contributions.sql
-- SIP-0112 FR-06, E.4.3 (#2410): a source-backed run's verified change, contributed through the
-- product's own process, one per run.
--
-- The Project's contribution mode decides what a contribution is:
-- - patch_export: the run's captured commit's patch, kept as the run's artifact, and nothing
--   leaves the deploy;
-- - review_request: the commit pushed as branch squadops/<cycle_id>, never forced, with a review
--   request opened against the Project's base branch.
-- Either is recorded pending. A review request opened is not integration: the integrated revision
-- is recorded when the product takes it (FR-06, E.4.4), so a pending contribution and an
-- integrated one stay distinguishable (§B.7).

CREATE TABLE IF NOT EXISTS project_contributions (
    project_id     TEXT NOT NULL REFERENCES project_records (project_id),
    cycle_id       TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    commit         TEXT NOT NULL CHECK (commit ~ '^[0-9a-f]{40}$'),
    parent_commit  TEXT NOT NULL CHECK (parent_commit ~ '^[0-9a-f]{40}$'),
    mode           TEXT NOT NULL CHECK (mode IN ('patch_export', 'review_request')),
    state          TEXT NOT NULL CHECK (state IN ('pending', 'integrated', 'closed')),
    branch         TEXT,
    review_url     TEXT,
    contributed_by TEXT NOT NULL,
    contributed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (project_id, cycle_id, run_id),
    CHECK ((mode = 'review_request') = (branch IS NOT NULL AND review_url IS NOT NULL))
);

ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN (
        'seed', 'register', 'validate', 'configure', 'baseline', 'owner_decision', 'contribute'
    ));
