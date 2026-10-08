-- 1730_memory_exposures.sql
-- SIP-0110 §0.2, §0.8 step 7 (slice 3c, #2096): each consuming task's recall, as it was answered, one per
-- task of a run: the query's scope, the snapshot, the disposition, the lessons supplied and those left
-- out with the reason. Recorded for every task at a consuming seam, a memory-disabled one included, and
-- joined to the task's authoring envelope by run and task. Beside the cycle registry (the 2.2 plan's
-- D13). The body is `json`, which keeps its keys as written.

CREATE TABLE IF NOT EXISTS memory_exposures (
    exposure_id    TEXT PRIMARY KEY,
    project_id     TEXT NOT NULL,
    cycle_id       TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    task_id        TEXT NOT NULL,
    task_type      TEXT NOT NULL,
    seam           TEXT NOT NULL,
    disposition    TEXT NOT NULL,
    snapshot_id    TEXT,
    exposure_body  JSON NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL,
    UNIQUE (run_id, task_id)
);

CREATE INDEX IF NOT EXISTS memory_exposures_run ON memory_exposures (run_id);
CREATE INDEX IF NOT EXISTS memory_exposures_project ON memory_exposures (project_id, recorded_at);
