-- 1700_authoring_envelopes.sql
-- SIP-0110 §0.11 (#2105): each authoring seam's replay envelope, captured at the task's first
-- model call and recorded by the runtime as the reply arrives, on every dispatch path. Never a run
-- artifact: artifacts feed later tasks' prompts by producing task, and an envelope holds a whole
-- prompt. The seam CHECK is the Python enum's values (AuthoringSeam), held equal by a test. A
-- duplicate delivery of one capture keeps the first row (envelope_id is its content's identity).

CREATE TABLE IF NOT EXISTS authoring_envelopes (
    envelope_id      TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES cycle_runs(run_id),
    task_id          TEXT NOT NULL,
    task_type        TEXT NOT NULL,
    seam             TEXT NOT NULL
        CHECK (seam IN ('plan_writing', 'build_authoring', 'repair', 'proposal_writing')),
    captured_at      TIMESTAMPTZ NOT NULL,
    messages_sha256  TEXT NOT NULL,
    envelope         JSONB NOT NULL,
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS authoring_envelopes_run_id ON authoring_envelopes (run_id);
CREATE INDEX IF NOT EXISTS authoring_envelopes_task_id ON authoring_envelopes (task_id);
