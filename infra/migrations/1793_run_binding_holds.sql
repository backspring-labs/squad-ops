-- SIP-0110 Appendix A §3.6 (#2178): a run held on a task's binding sections, and its release.
-- One row per hold. A run is held while its last hold has no released_at and it is PAUSED. The
-- release is written once (a compare-and-set on released_at IS NULL), by whichever of a
-- re-supply, a cancel or a Campaign's ruling bound comes first.
--   unresolved: [[ref, reason, kind], ...], each kind store or input
--   cause:      how it was released
--   sections:   the binding sections that held, e.g. ["task_instructions"]; [] for a dispatch
--               turn not given
CREATE TABLE IF NOT EXISTS run_binding_holds (
    run_id      TEXT        NOT NULL REFERENCES cycle_runs (run_id) ON DELETE CASCADE,
    hold_id     TEXT        NOT NULL,
    task_id     TEXT        NOT NULL,
    task_type   TEXT        NOT NULL,
    unresolved  JSONB       NOT NULL,
    held_at     TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ,
    cause       TEXT CHECK (cause IN ('store_answered', 'instruction_changed', 'rebound', 'cancelled', 'expired')),
    sections    JSONB       NOT NULL DEFAULT '[]',
    PRIMARY KEY (run_id, hold_id),
    CHECK ((released_at IS NULL) = (cause IS NULL))
);
