-- 1807_project_initializations.sql
-- SIP-0112 FR-01, UC-B, E.4.6 (#2412): a greenfield Project's first commit, once per Project.
--
-- The owner makes the repository and leaves it empty; SquadOps binds it and never creates one
-- (amendment H.1). Initializing renders a SIP-0105 blueprint's layout from the approved interface
-- manifest and pushes it as the branch's first commit, never forced. The manifest is kept as
-- submitted, so which approved structure was rendered stays readable after the Project moves on.

CREATE TABLE IF NOT EXISTS project_initializations (
    project_id       TEXT PRIMARY KEY REFERENCES project_records (project_id),
    commit           TEXT NOT NULL CHECK (commit ~ '^[0-9a-f]{40}$'),
    branch           TEXT NOT NULL,
    stack            TEXT NOT NULL,
    manifest_digest  TEXT NOT NULL CHECK (manifest_digest ~ '^sha256:[0-9a-f]{64}$'),
    manifest         TEXT NOT NULL,
    files            TEXT[] NOT NULL,
    initialized_by   TEXT NOT NULL,
    initialized_at   TIMESTAMPTZ NOT NULL
);

ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN (
        'seed', 'register', 'validate', 'configure', 'baseline', 'owner_decision', 'contribute',
        'sync', 'contribution_state', 'initialize'
    ));
