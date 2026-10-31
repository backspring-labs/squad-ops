-- SIP-0110 Appendix A (§A.3.2–§A.3.4, §A.3.8; #2177): the typed memory records, append-only.
-- A record's identity, kind and scope; its immutable revisions, each its whole document; and its
-- status changes. One table for the three kinds (notes, preferences, instructions): they share
-- identity, revisions, provenance and withdrawal, and differ only in their revision's fields.

CREATE TABLE IF NOT EXISTS memory_records (
    record_id   TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    scope       TEXT NOT NULL,
    project_id  TEXT,
    owner_id    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_records_project ON memory_records(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memory_records_owner ON memory_records(owner_id, created_at);

CREATE TABLE IF NOT EXISTS memory_record_revisions (
    record_id   TEXT NOT NULL REFERENCES memory_records(record_id),
    number      INTEGER NOT NULL,
    document    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (record_id, number)
);

CREATE TABLE IF NOT EXISTS memory_record_status_changes (
    seq         BIGSERIAL PRIMARY KEY,
    record_id   TEXT NOT NULL REFERENCES memory_records(record_id),
    status      TEXT NOT NULL,
    changed_by  TEXT NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL,
    why         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_record_status_changes_record
    ON memory_record_status_changes(record_id, seq);

-- §A.3.3: a chat session's project binding, set server-side when it opens. Existing sessions stay
-- unbound (NULL) and see only their owner's private records.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS project_id TEXT;
