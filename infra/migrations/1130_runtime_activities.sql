-- 1130_runtime_activities.sql
-- SIP-0089 Phase 4 §4.2: runtime_activities table.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).
--
-- Field semantics mirror src/squadops/runtime/models.py::RuntimeActivity (§10.6).
-- Enum-shaped columns carry CHECK constraints matching the Literal types in code
-- (D3). Source identity is explicit: cycle_id/workload_id/task_id are queryable
-- columns; source_ref is opaque adapter detail core never parses (§4.1).
--
-- agent_id is the holder. It is indexed (the port looks up the current activity by
-- agent) but intentionally NOT a hard FK to agent_runtime_state: that row is
-- created lazily by heartbeat (Phase 1 ensure_state), so an activity may be
-- written before the agent has heartbeated (mirrors 1110/1120).

CREATE TABLE IF NOT EXISTS runtime_activities (
    runtime_activity_id    TEXT PRIMARY KEY,
    agent_id               TEXT NOT NULL,
    mode                   TEXT NOT NULL
        CHECK (mode IN ('duty', 'cycle', 'ambient')),
    activity_type          TEXT NOT NULL,
    goal                   TEXT NOT NULL,
    priority               INTEGER NOT NULL,
    state                  TEXT NOT NULL
        CHECK (state IN ('pending', 'running', 'paused', 'completed', 'aborted', 'failed')),
    source_kind            TEXT NOT NULL
        CHECK (source_kind IN (
            'cycle_task', 'workload', 'duty_handler', 'ambient_observation', 'embodied_action'
        )),
    cycle_id               TEXT,
    workload_id            TEXT,
    task_id                TEXT,
    source_ref             TEXT NOT NULL,
    can_pause              BOOLEAN NOT NULL,
    can_resume             BOOLEAN NOT NULL,
    can_abort              BOOLEAN NOT NULL,
    completion_conditions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_requirements  JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at             TIMESTAMPTZ,
    paused_at              TIMESTAMPTZ,
    ended_at               TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single active-activity invariant (D9 / §4.2): at most one row per agent in a
-- non-terminal state. A partial unique index lets terminal rows accumulate freely
-- while guaranteeing one current unit of work per agent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_runtime_activities_one_active_per_agent
    ON runtime_activities (agent_id)
    WHERE state IN ('pending', 'running', 'paused');

-- get_current_activity(agent_id): look up the active activity for an agent.
CREATE INDEX IF NOT EXISTS idx_runtime_activities_agent_id
    ON runtime_activities (agent_id);

-- Explicit source-identity columns are queryable (history-by-X), so index them.
CREATE INDEX IF NOT EXISTS idx_runtime_activities_cycle_id
    ON runtime_activities (cycle_id);
CREATE INDEX IF NOT EXISTS idx_runtime_activities_workload_id
    ON runtime_activities (workload_id);
CREATE INDEX IF NOT EXISTS idx_runtime_activities_task_id
    ON runtime_activities (task_id);
