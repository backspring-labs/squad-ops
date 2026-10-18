-- 1800_project_records.sql
-- SIP-0112 FR-03, E.4.1 (#2408): the writable Project registry. Selected by
-- `cycles.project_registry_provider: postgres`; before that cutover config/projects.yaml is the
-- only authority and these tables are read by nothing but the cutover's refusal (the owner's R3).
--
-- `project_records`, not `projects` (R2): infra/init.sql creates a legacy five-column `projects`
-- table on a fresh volume, and `CREATE TABLE IF NOT EXISTS projects` would silently adopt it.
--
-- The CHECK lists are the Python enums' values (ProjectLifecycleStatus, ProjectProvenance),
-- held equal by test_project_registry_schema.py. ACTIVE is derived from active work, never
-- stored (§B.6). No cycle or campaign table references these: Project IDs stay plain text
-- there by policy (1610), and the cutover reports unknown ones rather than enforcing a key.

CREATE TABLE IF NOT EXISTS project_records (
    project_id        TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    tags              TEXT[] NOT NULL,
    prd_path          TEXT,
    lifecycle_status  TEXT NOT NULL
        CHECK (lifecycle_status IN ('REGISTERING', 'READY', 'ARCHIVED', 'FAILED_REGISTRATION')),
    record_version    INTEGER NOT NULL CHECK (record_version >= 1),
    provenance        TEXT NOT NULL CHECK (provenance IN ('seeded', 'registered')),
    -- the external source binding (§B.5); null for a seeded sample application
    repo_uri          TEXT,
    base_ref          TEXT,
    contribution_mode TEXT,
    repository_root   TEXT,
    -- the product's authority (§B.5.1): owner, delegated actions, acceptance policy
    ownership         JSONB,
    development_configuration_revision INTEGER,
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL,
    -- listing order: the config file's order for seeded rows, then registration order
    listed_order      BIGINT GENERATED ALWAYS AS IDENTITY,
    CHECK ((repo_uri IS NULL) = (base_ref IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS project_records_listed_order ON project_records (listed_order);

-- Each change to a Project Record, append-only: the seed, a registration, an owner decision.
-- An idempotency key names one applied operation; the request hash is what it stood for, so a
-- retry with the same content replays and any other content under the key is a conflict.
CREATE TABLE IF NOT EXISTS project_record_events (
    event_id         TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES project_records (project_id),
    operation        TEXT NOT NULL CHECK (operation IN ('seed', 'register', 'owner_decision')),
    record_version   INTEGER NOT NULL,
    actor            TEXT NOT NULL,
    idempotency_key  TEXT,
    request_hash     TEXT,
    detail           JSONB NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL,
    CHECK ((idempotency_key IS NULL) = (request_hash IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS project_record_events_idempotency
    ON project_record_events (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS project_record_events_project
    ON project_record_events (project_id, recorded_at);

-- Which config/projects.yaml entries have been seeded, once each: an entry edited in the file
-- after its seed is not re-applied, since the writable registry is the authority from then on.
CREATE TABLE IF NOT EXISTS project_seed_log (
    project_id  TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    seeded_at   TIMESTAMPTZ NOT NULL
);
