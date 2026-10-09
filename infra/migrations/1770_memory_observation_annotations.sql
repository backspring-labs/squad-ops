-- 1770_memory_observation_annotations.sql
-- SIP-0110 §0.4 (#2160): a reviewed annotation, the way a historical return classified only in prose enters. It sits
-- beside its observation and never edits it: the observation keeps its identity, its original classification and its
-- evidence, so an annotation adds no occurrence. It classifies only once reviewed (`reviewed_at`), and the first
-- review stands. Beside the cycle registry (the 2.2 plan's D13). The body is `json`, which keeps its keys as written.

CREATE TABLE IF NOT EXISTS memory_observation_annotations (
    annotation_id    TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL,
    source_id        TEXT NOT NULL REFERENCES memory_observations(source_id),
    annotated_at     TIMESTAMPTZ NOT NULL,
    reviewed_at      TIMESTAMPTZ,
    annotation_body  JSON NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_observation_annotations_project
    ON memory_observation_annotations (project_id, annotated_at);
CREATE INDEX IF NOT EXISTS memory_observation_annotations_source
    ON memory_observation_annotations (source_id);
