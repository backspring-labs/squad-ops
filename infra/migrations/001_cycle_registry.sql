-- 001_cycle_registry.sql
-- SIP-Postgres-Cycle-Registry §5.1: cycle, run, and gate-decision tables.
-- All DDL is idempotent (CREATE ... IF NOT EXISTS).

-- Cycles (SIP-0064 §8.2)
CREATE TABLE IF NOT EXISTS cycle_registry (
    cycle_id                    TEXT PRIMARY KEY,
    project_id                  TEXT NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by                  TEXT NOT NULL,
    prd_ref                     TEXT,
    squad_profile_id            TEXT NOT NULL,
    squad_profile_snapshot_ref  TEXT NOT NULL,
    task_flow_policy            JSONB NOT NULL,
    build_strategy              TEXT NOT NULL,
    applied_defaults            JSONB NOT NULL DEFAULT '{}',
    execution_overrides         JSONB NOT NULL DEFAULT '{}',
    expected_artifact_types     TEXT[] NOT NULL DEFAULT '{}',
    experiment_context          JSONB NOT NULL DEFAULT '{}',
    notes                       TEXT,
    cancelled                   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_cycle_registry_project
    ON cycle_registry(project_id);
CREATE INDEX IF NOT EXISTS idx_cycle_registry_created
    ON cycle_registry(created_at DESC);

-- Runs (SIP-0064 §8.4)
CREATE TABLE IF NOT EXISTS cycle_runs (
    run_id                  TEXT PRIMARY KEY,
    cycle_id                TEXT NOT NULL REFERENCES cycle_registry(cycle_id),
    run_number              INTEGER NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'queued',
    initiated_by            TEXT NOT NULL,
    resolved_config_hash    TEXT NOT NULL,
    resolved_config_ref     TEXT,
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    artifact_refs           TEXT[] NOT NULL DEFAULT '{}',

    UNIQUE (cycle_id, run_number)
);

CREATE INDEX IF NOT EXISTS idx_cycle_runs_cycle
    ON cycle_runs(cycle_id);
CREATE INDEX IF NOT EXISTS idx_cycle_runs_cycle_latest
    ON cycle_runs(cycle_id, run_number DESC);
CREATE INDEX IF NOT EXISTS idx_cycle_runs_status
    ON cycle_runs(status);

-- Gate decisions (SIP-0064 §8.4)
CREATE TABLE IF NOT EXISTS cycle_gate_decisions (
    id              SERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES cycle_runs(run_id),
    gate_name       TEXT NOT NULL,
    decision        TEXT NOT NULL,
    decided_by      TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL,
    notes           TEXT,

    UNIQUE (run_id, gate_name)
);

CREATE INDEX IF NOT EXISTS idx_cycle_gate_decisions_run
    ON cycle_gate_decisions(run_id);
