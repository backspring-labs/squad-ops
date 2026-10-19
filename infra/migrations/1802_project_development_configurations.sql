-- 1802_project_development_configurations.sql
-- SIP-0112 §B.5, E.4.2 (#2409): each Project's Development Configuration, one row per revision.
-- A revision is never edited: a change is the next revision, and a unit keeps the revision it
-- pinned (§B.5.1). The document is the record as stored and read: the shape the shared fixture
-- records (tests/fixtures/shared_contract/recorded/development_configuration), validated before
-- it is written. project_records.development_configuration_revision names the current one.

CREATE TABLE IF NOT EXISTS project_development_configurations (
    project_id           TEXT NOT NULL REFERENCES project_records (project_id),
    revision             INTEGER NOT NULL CHECK (revision >= 1),
    document             JSONB NOT NULL,
    validated_at_commit  TEXT NOT NULL,
    recorded_by          TEXT NOT NULL,
    recorded_at          TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (project_id, revision)
);

ALTER TABLE project_record_events DROP CONSTRAINT IF EXISTS project_record_events_operation_check;
ALTER TABLE project_record_events ADD CONSTRAINT project_record_events_operation_check
    CHECK (operation IN ('seed', 'register', 'validate', 'configure', 'owner_decision'));
