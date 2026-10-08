-- 1740_memory_assessments.sql
-- SIP-0110 §0.10 (slice 3d, #2096): each target's state in one exposure's authored output (present,
-- absent after assessment, not applicable, unassessed), judged by the target's template rubric.
-- Append-only: a reassessment is a new row, and the latest per exposure and target is read.
-- Beside the cycle registry (the 2.2 plan's D13). The body is `json`, which keeps its keys as written.

CREATE TABLE IF NOT EXISTS memory_assessments (
    assessment_id    TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL,
    exposure_id      TEXT NOT NULL REFERENCES memory_exposures(exposure_id),
    pattern_id       TEXT NOT NULL,
    state            TEXT NOT NULL
                     CHECK (state IN ('present', 'absent', 'not_applicable', 'unassessed')),
    assessed_at      TIMESTAMPTZ NOT NULL,
    assessment_body  JSON NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_assessments_project ON memory_assessments (project_id, assessed_at);
CREATE INDEX IF NOT EXISTS memory_assessments_exposure ON memory_assessments (exposure_id, pattern_id);
