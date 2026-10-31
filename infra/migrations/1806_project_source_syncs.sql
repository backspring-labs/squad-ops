-- 1806_project_source_syncs.sql
-- SIP-0112 FR-09, FR-21, §B.5.1 drift detection; E.4.4 (#2411).
--
-- project_source_syncs: each time a Project's upstream was read against its approved development
-- baseline. The document names what changed, path by path, by the category of evidence it
-- invalidates (instructions, the declared commands' inputs, dependencies, toolchain,
-- contribution policy, source), and where each pending contribution stood. A later unit
-- resolves "the drift findings since" from here (FR-09 item 5). A sync moves nothing: the
-- baseline advances through validation.
--
-- project_contributions.integrated_commit: the commit through which the product took a
-- contribution. It is the contribution's own commit, or the merge a squash made. It is NULL
-- while the contribution is pending or closed.

CREATE TABLE IF NOT EXISTS project_source_syncs (
    project_id       TEXT NOT NULL REFERENCES project_records (project_id),
    synced_seq       INTEGER NOT NULL CHECK (synced_seq >= 1),
    baseline_commit  TEXT NOT NULL CHECK (baseline_commit ~ '^[0-9a-f]{40}$'),
    upstream_commit  TEXT NOT NULL CHECK (upstream_commit ~ '^[0-9a-f]{40}$'),
    document         JSONB NOT NULL,
    synced_by        TEXT NOT NULL,
    synced_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (project_id, synced_seq)
);

ALTER TABLE project_contributions ADD COLUMN IF NOT EXISTS integrated_commit TEXT
    CHECK (integrated_commit IS NULL OR integrated_commit ~ '^[0-9a-f]{40}$');

ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN (
        'seed', 'register', 'validate', 'configure', 'baseline', 'owner_decision', 'contribute',
        'sync', 'contribution_state'
    ));
