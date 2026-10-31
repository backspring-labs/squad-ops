-- SIP-0110 Appendix A §3.8 (T13, #2178): a run halted by a task instruction's emergency
-- withdrawal. One row per run, written once with the run's cancellation. restart_from_task_id is
-- the task its restart runs again from (NULL: the run only built on work that received the
-- instruction in an earlier run, so nothing in it restarts); restart_run_id is written once, by
-- the cycle that restarted it.
CREATE TABLE IF NOT EXISTS run_halts (
    run_id               TEXT        PRIMARY KEY REFERENCES cycle_runs (run_id) ON DELETE CASCADE,
    record_id            TEXT        NOT NULL,
    requested_by         TEXT        NOT NULL,
    why                  TEXT        NOT NULL,
    requested_at         TIMESTAMPTZ NOT NULL,
    restart_from_task_id TEXT,
    restart_run_id       TEXT
);
