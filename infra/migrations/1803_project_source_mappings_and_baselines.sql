-- 1803_project_source_mappings_and_baselines.sql
-- SIP-0112 §8.2.2, FR-20, E.4.2 (#2409).
--
-- project_source_mappings: each tree a Project's source took in the sandbox, named by all three
-- of its identifiers (contracts 3 and 4): the Git commit, the sandbox revision ID and SIP-0109's
-- FileTree.identity. They are different hashes of the same files and never stand in for one
-- another; this table is the only place they meet. "seeded" is a commit checked out into a
-- workspace; "captured" a verified revision committed back (E.4.3).
--
-- project_inherited_baselines: the product's own checks, run on the pinned, unmodified source
-- (FR-20). The document is the shape the shared fixture records; each check's evidence (exit
-- status, duration, bounded output) is kept beside it.

CREATE TABLE IF NOT EXISTS project_source_mappings (
    project_id           TEXT NOT NULL REFERENCES project_records (project_id),
    workspace_id         TEXT NOT NULL,
    direction            TEXT NOT NULL CHECK (direction IN ('seeded', 'captured')),
    commit               TEXT NOT NULL CHECK (commit ~ '^[0-9a-f]{40}$'),
    sandbox_revision_id  TEXT NOT NULL CHECK (sandbox_revision_id ~ '^[0-9a-f]{64}$'),
    tree_identity        TEXT NOT NULL CHECK (tree_identity ~ '^[0-9a-f]{64}$'),
    cycle_id             TEXT,
    campaign_id          TEXT,
    recorded_at          TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (workspace_id, direction, sandbox_revision_id)
);

CREATE INDEX IF NOT EXISTS project_source_mappings_commit
    ON project_source_mappings (project_id, commit);
CREATE INDEX IF NOT EXISTS project_source_mappings_tree
    ON project_source_mappings (project_id, tree_identity);

CREATE TABLE IF NOT EXISTS project_inherited_baselines (
    project_id                          TEXT NOT NULL REFERENCES project_records (project_id),
    captured_seq                        INTEGER NOT NULL CHECK (captured_seq >= 1),
    commit                              TEXT NOT NULL,
    development_configuration_revision  INTEGER NOT NULL,
    document                            JSONB NOT NULL,
    evidence                            JSONB NOT NULL,
    captured_by                         TEXT NOT NULL,
    captured_at                         TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (project_id, captured_seq)
);

ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN ('seed', 'register', 'validate', 'configure', 'baseline', 'owner_decision'));
