-- 2103_goal_set_assessments.sql
-- SIP-0115 §5.7, Q43 (#2888, slice 5): the operator's assessments of a goal set's expected results, one
-- row per assessment. Append-only, in their own order: `sequence` counts them per goal set (Q44: a
-- Project has one). They are not goal-set revisions and write none. Nothing derived is stored:
-- `stale` and `conflicting` are read per Campaign (squadops.projects.goal_set_assessments).
--
-- `log_seq` is the Campaign's control-log row its evidence was read at, as the submitter states it
-- (never past the log's end at the write). It orders an assessment against that Campaign's
-- acceptances only: log positions can't be compared across Campaigns (§5.7).
--
-- The idempotency key is the write's own, kept on its row, as a revision's is (2100).
--
-- Not the held-out suite's store: the sweep (scripts/dev/heldout_sweep.py) searches this table with
-- every other table of the database (§7).

CREATE TABLE IF NOT EXISTS project_goal_set_assessments (
    project_id       TEXT NOT NULL REFERENCES project_records (project_id),
    sequence         INTEGER NOT NULL CHECK (sequence >= 1),
    campaign_id      TEXT NOT NULL REFERENCES campaigns (campaign_id),
    expected_result  TEXT NOT NULL,
    goals_revision   INTEGER NOT NULL,
    reading          TEXT NOT NULL CHECK (reading IN ('met', 'not_met', 'unclear')),
    cause            TEXT CHECK (
        cause IN ('app_work', 'framework_defect', 'framework_gap', 'needs_owner')
    ),
    issue            INTEGER CHECK (issue >= 1),
    evidence         JSONB NOT NULL,
    supersedes       INTEGER[] NOT NULL DEFAULT '{}',
    log_seq          INTEGER NOT NULL CHECK (log_seq >= 0),
    reason           TEXT NOT NULL CHECK (reason <> ''),
    source_ref       TEXT,
    author           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL,
    idempotency_key  TEXT NOT NULL,
    request_hash     TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence),
    FOREIGN KEY (project_id, goals_revision)
        REFERENCES project_goal_set_revisions (project_id, revision),
    -- A cause is a shortfall's, and only a framework cause names an issue (§5.7).
    CHECK ((cause IS NOT NULL) = (reading = 'not_met')),
    CHECK (
        (issue IS NOT NULL) = COALESCE(cause IN ('framework_defect', 'framework_gap'), FALSE)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS project_goal_set_assessments_idempotency
    ON project_goal_set_assessments (idempotency_key);

CREATE INDEX IF NOT EXISTS project_goal_set_assessments_campaign
    ON project_goal_set_assessments (campaign_id, sequence);
