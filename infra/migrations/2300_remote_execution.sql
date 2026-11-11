-- 2300_remote_execution.sql
-- SIP-0117 R3.3, R5.4: the worker registry. A worker's sessions, the operations queued for
-- workers, each attempt at one, and the results that were refused.
--
-- Field semantics mirror src/squadops/remote_execution/workers.py. Enum-shaped columns carry
-- CHECK constraints matching the vocabularies in code (D3):
--   runtime_status  squadops.runtime.models.RuntimeStatus
--   state           OperationState
--   outcome         AttemptOutcome
--   refusal         FenceRefusal
-- The lease is the operation's own row (lease_id, session_id, lease_expires_at), so it
-- survives a runtime restart: the fence is what is stored here, never a process's memory.

CREATE TABLE IF NOT EXISTS remote_worker_sessions (
    session_id        TEXT PRIMARY KEY,
    worker_id         TEXT NOT NULL,
    platform          TEXT NOT NULL,
    tool_versions     JSONB NOT NULL,
    operations        JSONB NOT NULL,
    runtime_status    TEXT NOT NULL
        CHECK (runtime_status IN ('online', 'degraded', 'recovering', 'offline')),
    registered_at     TIMESTAMPTZ NOT NULL,
    last_heartbeat_at TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ
);

-- A worker has one live session. A worker that registers again ends its earlier one first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_remote_worker_sessions_one_live_per_worker
    ON remote_worker_sessions (worker_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS remote_operations (
    operation_id      TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    operation         TEXT NOT NULL,
    request           JSONB NOT NULL,
    origin            JSONB NOT NULL,
    max_attempts      INTEGER NOT NULL CHECK (max_attempts >= 1),
    state             TEXT NOT NULL CHECK (state IN ('queued', 'claimed', 'settled')),
    created_at        TIMESTAMPTZ NOT NULL,
    attempt           INTEGER NOT NULL CHECK (attempt >= 0 AND attempt <= max_attempts),
    lease_id          TEXT,
    session_id        TEXT,
    lease_expires_at  TIMESTAMPTZ,
    cancel_requested  BOOLEAN NOT NULL,
    result            JSONB,
    settled_at        TIMESTAMPTZ,
    -- Claimed is exactly "holds a lease", and settled is exactly "has its result".
    CHECK ((state = 'claimed') = (lease_id IS NOT NULL)),
    CHECK ((lease_id IS NULL) = (session_id IS NULL)),
    CHECK ((lease_id IS NULL) = (lease_expires_at IS NULL)),
    CHECK ((state = 'settled') = (result IS NOT NULL)),
    CHECK ((result IS NULL) = (settled_at IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_remote_operations_queue
    ON remote_operations (provider, operation, created_at) WHERE state = 'queued';
CREATE INDEX IF NOT EXISTS ix_remote_operations_claimed
    ON remote_operations (lease_expires_at) WHERE state = 'claimed';

CREATE TABLE IF NOT EXISTS remote_operation_attempts (
    operation_id      TEXT NOT NULL REFERENCES remote_operations (operation_id),
    attempt           INTEGER NOT NULL CHECK (attempt >= 1),
    session_id        TEXT NOT NULL REFERENCES remote_worker_sessions (session_id),
    worker_id         TEXT NOT NULL,
    lease_id          TEXT NOT NULL,
    claimed_at        TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ,
    outcome           TEXT CHECK (outcome IN ('accepted', 'expired')),
    PRIMARY KEY (operation_id, attempt),
    CHECK ((ended_at IS NULL) = (outcome IS NULL))
);

-- A worker holds at most one claim.
CREATE UNIQUE INDEX IF NOT EXISTS uq_remote_operation_attempts_one_open_per_worker
    ON remote_operation_attempts (worker_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_remote_operation_attempts_worker
    ON remote_operation_attempts (worker_id, claimed_at DESC);

-- A refused result, kept. operation_id has no foreign key: a result for an operation that
-- was never queued is one of the refusals.
CREATE TABLE IF NOT EXISTS remote_operation_refusals (
    refusal_id        BIGSERIAL PRIMARY KEY,
    operation_id      TEXT NOT NULL,
    attempt           INTEGER NOT NULL,
    session_id        TEXT NOT NULL,
    lease_id          TEXT NOT NULL,
    refusal           TEXT NOT NULL
        CHECK (refusal IN ('unknown_operation', 'already_settled', 'not_claimed',
                           'stale_attempt', 'stale_session', 'stale_lease', 'lease_expired')),
    received_at       TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_remote_operation_refusals_operation
    ON remote_operation_refusals (operation_id, refusal_id);
