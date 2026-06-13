-- 1100_agent_runtime_state.sql
-- SIP-0089 Phase 1 §1.2: agent_runtime_state table.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).
--
-- Field semantics mirror src/squadops/runtime/models.py::AgentRuntimeState.
-- Enum-shaped columns carry CHECK constraints matching the Literal types
-- in code (D3). `mode`, `focus`, `current_runtime_activity_id`, and
-- `current_assignment_ref` are coordinator-owned (D16); heartbeat may
-- write only `last_heartbeat_at` and `runtime_status` (D17).

CREATE TABLE IF NOT EXISTS agent_runtime_state (
    agent_id                       TEXT PRIMARY KEY,
    mode                           TEXT NOT NULL
        CHECK (mode IN ('duty', 'cycle', 'ambient')),
    runtime_status                 TEXT NOT NULL
        CHECK (runtime_status IN ('online', 'degraded', 'recovering', 'offline')),
    focus                          TEXT NOT NULL DEFAULT '',
    current_runtime_activity_id    TEXT,
    interruptibility               TEXT NOT NULL
        CHECK (interruptibility IN ('none', 'low', 'medium', 'high')),
    last_heartbeat_at              TIMESTAMPTZ NOT NULL,
    current_assignment_ref         TEXT,
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
