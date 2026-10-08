-- 1720_memory_lessons.sql
-- SIP-0110 §0.2, §0.6–§0.7 (slice 3c, #2096): the lessons (pattern revisions, immutable), the owner's
-- approvals of them, and each unit's pinned snapshot, stored whole so a pin never depends on rows read
-- later. Beside the cycle registry (the 2.2 plan's D13). A snapshot is unique per unit: the first pin
-- wins, so a restart reproduces it (§0.7). Bodies are `json`, which keeps their keys as written.

CREATE TABLE IF NOT EXISTS memory_revisions (
    revision_id    TEXT PRIMARY KEY,
    pattern_id     TEXT NOT NULL,
    revision       INTEGER NOT NULL,
    project_id     TEXT NOT NULL,
    revision_body  JSON NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pattern_id, revision)
);

CREATE TABLE IF NOT EXISTS memory_approvals (
    approval_id    TEXT PRIMARY KEY,
    revision_id    TEXT NOT NULL REFERENCES memory_revisions(revision_id),
    project_id     TEXT NOT NULL,
    approved_at    TIMESTAMPTZ NOT NULL,
    revoked_at     TIMESTAMPTZ,
    approval_body  JSON NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_snapshots (
    unit_kind      TEXT NOT NULL CHECK (unit_kind IN ('cycle', 'campaign')),
    unit_id        TEXT NOT NULL,
    snapshot_id    TEXT NOT NULL UNIQUE,
    pinned_at      TIMESTAMPTZ NOT NULL,
    snapshot_body  JSON NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (unit_kind, unit_id)
);

CREATE INDEX IF NOT EXISTS memory_revisions_project ON memory_revisions (project_id);
CREATE INDEX IF NOT EXISTS memory_approvals_project ON memory_approvals (project_id, approved_at);
