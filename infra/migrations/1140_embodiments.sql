-- 1140_embodiments.sql
-- SIP-0090 Phase 1 §5.3: embodiments table.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).
--
-- Field semantics mirror src/squadops/runtime/embodiment.py::Embodiment. Enum-shaped
-- columns carry CHECK constraints matching the Literal types in code (D3).
-- `capability_set` is a JSONB array of capability strings (§5.7). `location_ref` is
-- opaque (§5.4) — stored/compared verbatim, never parsed by the platform.
-- `credentials_ref` is a `secret://` reference only, never a raw secret (§9); the
-- domain model enforces that invariant at construction.
--
-- agent_id is the owning agent. It is indexed (the port queries by agent) but
-- intentionally NOT a hard FK to agent_runtime_state: that row is created lazily by
-- heartbeat (Phase 1 ensure_state), so an embodiment may be written before the agent
-- has heartbeated (mirrors 1110/1120).

CREATE TABLE IF NOT EXISTS embodiments (
    embodiment_id         TEXT PRIMARY KEY,
    agent_id              TEXT NOT NULL,
    embodiment_type       TEXT NOT NULL
        CHECK (embodiment_type IN ('discord', 'browser', 'minecraft', 'cli', 'other')),
    platform              TEXT NOT NULL,
    attachment_state      TEXT NOT NULL
        CHECK (attachment_state IN
            ('unattached', 'attaching', 'attached', 'desynced', 'reconnecting', 'detached')),
    health                TEXT NOT NULL
        CHECK (health IN ('healthy', 'degraded', 'failed')),
    capability_set        JSONB NOT NULL DEFAULT '[]'::jsonb,
    location_ref          TEXT,
    last_health_check_at  TIMESTAMPTZ,
    credentials_ref       TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single active-embodiment invariant (§5.5): at most one *live* embodiment per agent.
-- A partial unique index over the active attachment states lets historical
-- (unattached / detached) rows accumulate freely while guaranteeing the agent has at
-- most one embodiment that is attached, desynced, or reconnecting at any time. This
-- is the hard backstop behind the EmbodimentCoordinator's logic-level guard.
CREATE UNIQUE INDEX IF NOT EXISTS uq_embodiments_one_active_per_agent
    ON embodiments (agent_id)
    WHERE attachment_state IN ('attached', 'desynced', 'reconnecting');

-- get_active_embodiment(agent_id) / list_for_agent(agent_id).
CREATE INDEX IF NOT EXISTS idx_embodiments_agent_id
    ON embodiments (agent_id);
