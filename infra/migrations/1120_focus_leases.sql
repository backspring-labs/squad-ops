-- 1120_focus_leases.sql
-- SIP-0089 Phase 3 §3.2: focus_leases table.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).
--
-- Field semantics mirror src/squadops/runtime/models.py::FocusLease (§10.4).
-- Enum-shaped columns carry CHECK constraints matching the Literal types in code
-- (D3). `expires_at` is nullable (a heartbeat-renewed lease may have no fixed
-- expiry). `released_at` is null while the lease is the agent's CURRENT/active
-- lease; the partial unique index below enforces at most one such row per agent.
--
-- agent_id is the holder of the lease. It is indexed (the port queries the
-- current lease by agent) but intentionally NOT a hard FK to agent_runtime_state:
-- that row is created lazily by heartbeat (Phase 1 ensure_state), so a lease may
-- legitimately be written before the agent has heartbeated (mirrors 1110).

CREATE TABLE IF NOT EXISTS focus_leases (
    lease_id          TEXT PRIMARY KEY,
    agent_id          TEXT NOT NULL,
    owner_type        TEXT NOT NULL
        CHECK (owner_type IN ('duty', 'cycle', 'ambient')),
    owner_ref         TEXT NOT NULL,
    acquired_at       TIMESTAMPTZ NOT NULL,
    expires_at        TIMESTAMPTZ,
    renewal_policy    TEXT NOT NULL
        CHECK (renewal_policy IN ('heartbeat', 'ttl', 'fixed_window')),
    interruptibility  TEXT NOT NULL
        CHECK (interruptibility IN ('none', 'low', 'medium', 'high')),
    recall_policy     TEXT NOT NULL
        CHECK (recall_policy IN ('immediate', 'graceful', 'none')),
    released_at       TIMESTAMPTZ,
    idempotency_key   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Single active-lease invariant (§3.2): at most one un-released lease per agent.
-- A partial unique index lets historical (released) rows accumulate freely while
-- guaranteeing only one current owner of an agent's primary attention.
CREATE UNIQUE INDEX IF NOT EXISTS uq_focus_leases_one_active_per_agent
    ON focus_leases (agent_id) WHERE released_at IS NULL;

-- get_current_lease(agent_id): look up the active lease for an agent.
CREATE INDEX IF NOT EXISTS idx_focus_leases_agent_id
    ON focus_leases (agent_id);

-- Replay-safe acquire/preempt (D12): an idempotency_key lookup must be cheap.
CREATE INDEX IF NOT EXISTS idx_focus_leases_idempotency_key
    ON focus_leases (idempotency_key);
