-- 1110_assignments.sql
-- SIP-0089 Phase 2 §2.2: agent_assignments table.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).
--
-- Field semantics mirror src/squadops/runtime/models.py::Assignment +
-- DutyWindow (the nested active_window flattens to window_start/window_end/
-- timezone here). Enum-shaped columns carry CHECK constraints matching the
-- Literal types in code (D3). Durations are stored as INTERVAL.
--
-- agent_id is the holder of the assignment. It is indexed (the port queries
-- assignments by agent) but intentionally NOT a hard FK to agent_runtime_state:
-- that row is created lazily by heartbeat (Phase 1 ensure_state), so an
-- assignment may legitimately be written before the agent has heartbeated.

CREATE TABLE IF NOT EXISTS agent_assignments (
    assignment_id              TEXT PRIMARY KEY,
    agent_id                   TEXT NOT NULL,
    assignment_type            TEXT NOT NULL
        CHECK (assignment_type IN ('duty', 'reserve', 'cycle_eligibility')),
    assigned_role              TEXT NOT NULL,
    priority                   INTEGER NOT NULL,
    strictness                 TEXT NOT NULL
        CHECK (strictness IN ('hard', 'soft')),
    window_start               TIMESTAMPTZ NOT NULL,
    window_end                 TIMESTAMPTZ NOT NULL,
    timezone                   TEXT NOT NULL,
    reserve_before_window      INTERVAL NOT NULL,
    reserve_after_window       INTERVAL NOT NULL,
    recall_policy              TEXT NOT NULL
        CHECK (recall_policy IN ('immediate', 'graceful', 'none')),
    graceful_window            INTERVAL NOT NULL,
    missed_window_policy       TEXT NOT NULL
        CHECK (missed_window_policy IN (
            'skip', 'start_late_within_grace', 'require_operator_review'
        )),
    -- Literal-element membership ('ambient'|'cycle'|'duty') is enforced in code;
    -- Postgres array-element CHECKs are omitted to match the Phase 1 convention
    -- of CHECKing scalar enum columns only.
    allowed_off_window_modes   TEXT[] NOT NULL,
    active                     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (window_end > window_start)
);

-- list_assignments_for_agent(agent_id)
CREATE INDEX IF NOT EXISTS idx_agent_assignments_agent_id
    ON agent_assignments (agent_id);

-- list_active_assignments(now) / list_claimable_windows(now): scan active rows
-- by window bounds.
CREATE INDEX IF NOT EXISTS idx_agent_assignments_active_window
    ON agent_assignments (active, window_start, window_end);
