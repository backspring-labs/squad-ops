-- 2100_project_goal_sets.sql
-- SIP-0115 §4, §8.1 (#2884): each Project's goal set, one row per revision. A revision is never
-- edited: any change, a reorder included, is the next revision, with its author and reason (as
-- 1802's Development Configuration is). The latest revision is the Project's one active goal set
-- (Q44). The document is the goal set as stored and read (``GoalSet.to_document``), validated
-- before it is written. Nothing derived is stored: an item's status is read from each Campaign's
-- control log (§4).
--
-- The idempotency key is the write's own, kept on its row: the goal set adds nothing to the
-- Project Record, so its writes are not project_record_events.
--
-- Not the held-out suite's store: the sweep (scripts/dev/heldout_sweep.py) searches this table
-- with every other table of the database (§7). A goal set never holds a scenario's steps or values.

CREATE TABLE IF NOT EXISTS project_goal_set_revisions (
    project_id       TEXT NOT NULL REFERENCES project_records (project_id),
    revision         INTEGER NOT NULL CHECK (revision >= 1),
    document         JSONB NOT NULL,
    reason           TEXT NOT NULL CHECK (reason <> ''),
    source_ref       TEXT,
    author           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL,
    idempotency_key  TEXT NOT NULL,
    request_hash     TEXT NOT NULL,
    PRIMARY KEY (project_id, revision)
);

CREATE UNIQUE INDEX IF NOT EXISTS project_goal_set_revisions_idempotency
    ON project_goal_set_revisions (idempotency_key);
