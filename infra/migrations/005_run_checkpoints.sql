-- SIP-0079: Run checkpoints for implementation run checkpoint/resume.

CREATE TABLE IF NOT EXISTS run_checkpoints (
    run_id            TEXT        NOT NULL REFERENCES cycle_runs(run_id),
    checkpoint_index  INTEGER     NOT NULL,
    completed_task_ids JSONB      NOT NULL DEFAULT '[]',
    prior_outputs     JSONB       NOT NULL DEFAULT '{}',
    artifact_refs     JSONB       NOT NULL DEFAULT '[]',
    plan_delta_refs   JSONB       NOT NULL DEFAULT '[]',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, checkpoint_index)
);
