---
title: Postgres Cycle Registry — Durable Persistence for Cycles, Runs, and Gate Decisions
status: implemented
author: Jason Ladd
created_at: '2026-02-12T00:00:00Z'
sip_number: 67
updated_at: '2026-02-12T22:10:34.934970Z'
---
# SIP-00XX: Postgres Cycle Registry — Durable Persistence for Cycles, Runs, and Gate Decisions

**Status:** Proposed
**Created:** 2026-02-12
**Owner:** SquadOps Core
**Target Release:** v1.0
**Related:** SIP-0064 (Cycle API models/ports), SIP-0055 (DB deployment profiles), SIP-0066 (Pipeline wiring)

---

## 1. Intent

Replace the in-memory `MemoryCycleRegistry` with a Postgres-backed adapter that implements `CycleRegistryPort`. All cycle, run, and gate-decision state must survive runtime-api restarts and be queryable by the upcoming control plane UI.

---

## 2. Problem Statement

`MemoryCycleRegistry` (SIP-0064, T1) was explicitly scoped as a v0.9.3 placeholder. It has three production blockers:

1. **Volatile state**: All cycles, runs, gate decisions, and artifact refs are lost on every runtime-api restart or redeployment.
2. **No query surface for the UI**: The control plane needs paginated cycle history, run timelines, and gate-decision audit trails — none of which can be served from a dict that resets to empty.
3. **Single-process limitation**: If the runtime-api scales horizontally (multiple replicas behind a load balancer), each instance has its own isolated memory store.

---

## 3. Goals

1. **Drop-in replacement**: `PostgresCycleRegistry` implements `CycleRegistryPort` with identical semantics to `MemoryCycleRegistry` — all 12 methods, same exception hierarchy, same validation rules.
2. **Schema migration**: New tables added via `infra/migrations/` SQL files, applied at runtime-api startup (§5.8).
3. **Connection pooling**: Reuse the existing `asyncpg` pool already created in `main.py` startup (SIP-0055 pattern).
4. **Frozen-dataclass round-trip**: Postgres rows serialize/deserialize to the existing frozen dataclasses (`Cycle`, `Run`, `GateDecision`, `TaskFlowPolicy`, `Gate`) without modifying the domain models.
5. **Backward compatibility**: `MemoryCycleRegistry` remains available for unit tests and local development. Factory selects adapter by config.
6. **Timestamps**: Populate `started_at` and `finished_at` on `Run` during status transitions using `COALESCE` semantics — each is set exactly once (§5.2.1).
7. **Port interface change**: Adding `limit`/`offset` parameters to `list_cycles` and `list_runs` is a **breaking change to `CycleRegistryPort`**. All implementers (`MemoryCycleRegistry`, `PostgresCycleRegistry`) and all test doubles must be updated. Existing callers are unaffected because the new parameters have defaults.

---

## 4. Non-Goals

- **ORM**: No SQLAlchemy or other ORM. Raw `asyncpg` queries, consistent with all existing Postgres adapters in the codebase.
- **Event sourcing**: State is mutable rows, not an append-only event log.
- **Cross-database joins**: Cycle tables live in the default `squadops` database. No joins to the `langfuse` or `keycloak` databases.
- **Artifact content in Postgres**: Artifact blobs stay in the filesystem vault (`ArtifactVaultPort`). Only `artifact_refs` (IDs) are stored on runs.
- **Project CRUD via Postgres**: `ProjectRegistryPort` remains config-file-seeded for now (separate SIP if needed).
- **Multi-tenant / row-level security**: Out of scope for v1.0.
- **DB-level enum validation**: Status and decision string validation is enforced entirely in Python (domain layer). The DB does not validate enum values by design — this keeps the schema simple and avoids migration churn when enums evolve.

---

## 5. Proposed Design

### 5.1 Schema

Three new tables added via migration file `infra/migrations/001_cycle_registry.sql`:

```sql
-- Cycles (SIP-0064 §8.2)
CREATE TABLE IF NOT EXISTS cycle_registry (
    cycle_id        TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT NOT NULL,
    prd_ref         TEXT,
    squad_profile_id TEXT NOT NULL,
    squad_profile_snapshot_ref TEXT NOT NULL,
    task_flow_policy JSONB NOT NULL,    -- {mode, gates[]}
    build_strategy  TEXT NOT NULL,
    applied_defaults JSONB NOT NULL DEFAULT '{}',
    execution_overrides JSONB NOT NULL DEFAULT '{}',
    expected_artifact_types TEXT[] NOT NULL DEFAULT '{}',
    experiment_context JSONB NOT NULL DEFAULT '{}',
    notes           TEXT,
    cancelled       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_cycle_registry_project
    ON cycle_registry(project_id);
CREATE INDEX IF NOT EXISTS idx_cycle_registry_created
    ON cycle_registry(created_at DESC);

-- Runs (SIP-0064 §8.4)
CREATE TABLE IF NOT EXISTS cycle_runs (
    run_id              TEXT PRIMARY KEY,
    cycle_id            TEXT NOT NULL REFERENCES cycle_registry(cycle_id),
    run_number          INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued',
    initiated_by        TEXT NOT NULL,
    resolved_config_hash TEXT NOT NULL,
    resolved_config_ref TEXT,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    artifact_refs       TEXT[] NOT NULL DEFAULT '{}',

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
    decision        TEXT NOT NULL,       -- 'approved' | 'rejected'
    decided_by      TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL,
    notes           TEXT,

    UNIQUE (run_id, gate_name)
);

CREATE INDEX IF NOT EXISTS idx_cycle_gate_decisions_run
    ON cycle_gate_decisions(run_id);
```

**Design decisions:**
- `cycle_registry` not `cycles` — avoids collision with the legacy `cycle` table from SIP-0024/0047.
- `task_flow_policy` stored as JSONB — the nested `Gate` objects serialize naturally and are reconstructed on read.
- `cancelled` is a boolean column rather than a derived status — matches the memory adapter's `_cancelled_cycles` set. `cancel_cycle(cycle_id)` prevents new runs; existing runs may still be cancelled independently via `cancel_run()`.
- `artifact_refs` stored as `TEXT[]` on `cycle_runs`. Insertion order is preserved (§5.2.3).
- Gate decisions in a separate table with `UNIQUE(run_id, gate_name)` — used as a concurrency guard, not as the sole conflict detection mechanism (§5.4).
- `expected_artifact_types` stored as `TEXT[]` — maps directly to the `tuple[str, ...]` field.
- No `ON DELETE CASCADE` — cycles and runs are never deleted in v1.0. If delete support is added later, cascades can be added via a migration.

### 5.2 Adapter: `PostgresCycleRegistry`

**File:** `adapters/cycles/postgres_cycle_registry.py`

Constructor takes an `asyncpg.Pool` (injected, not created):

```python
class PostgresCycleRegistry(CycleRegistryPort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
```

**Method mapping:**

| Port method | SQL pattern |
|---|---|
| `create_cycle(cycle)` | `INSERT INTO cycle_registry ...` |
| `get_cycle(cycle_id)` | `SELECT ... WHERE cycle_id = $1` |
| `list_cycles(project_id, status=)` | Correctness path (§5.5) or optimized path (§5.5.1) |
| `cancel_cycle(cycle_id)` | `UPDATE cycle_registry SET cancelled = TRUE WHERE cycle_id = $1` |
| `create_run(run)` | Transactional: lock cycle row + allocate run_number + insert (§5.2.2) |
| `get_run(run_id)` | Two queries: `SELECT ... FROM cycle_runs` + `SELECT ... FROM cycle_gate_decisions WHERE run_id = $1`, assembled in Python (§5.2.4) |
| `list_runs(cycle_id)` | Two queries: `SELECT ... FROM cycle_runs WHERE cycle_id = $1 ORDER BY run_number` + batch gate decision fetch, assembled in Python (§5.2.4) |
| `update_run_status(run_id, status)` | Transition validation in Python, then `UPDATE ... SET status, started_at, finished_at` with `COALESCE` (§5.2.1) |
| `cancel_run(run_id)` | `update_run_status(run_id, RunStatus.CANCELLED)` |
| `append_artifact_refs(run_id, ids)` | De-duplicate in Python, then `UPDATE ... SET artifact_refs = $1` (§5.2.3) |
| `record_gate_decision(run_id, decision)` | Transactional SELECT-then-INSERT (§5.4) |

**Transition validation**: Same `validate_run_transition()` function from `squadops.cycles.lifecycle` — called in Python before the UPDATE, consistent with the memory adapter. Status machine logic stays in the domain layer, not in SQL.

#### 5.2.1 Timestamp Rules

Timestamps are set exactly once using `COALESCE` to prevent re-entrancy from overwriting historical timings:

- `started_at`: Set on first transition to `RUNNING`.
  ```sql
  UPDATE cycle_runs SET status = $1,
      started_at = COALESCE(started_at, now())
  WHERE run_id = $2 AND status IN (...)  -- only on RUNNING transition
  ```
- `finished_at`: Set on first transition to any terminal state (`COMPLETED`, `FAILED`, `CANCELLED`).
  ```sql
  UPDATE cycle_runs SET status = $1,
      finished_at = COALESCE(finished_at, now())
  WHERE run_id = $2
  ```

A paused → running → completed cycle never resets `started_at`. A re-entrant status update never resets `finished_at`.

#### 5.2.2 Concurrency-Safe `run_number` Allocation

`create_run()` allocates `run_number` inside a serializable transaction with a row lock on the parent cycle:

```python
async def create_run(self, run: Run) -> Run:
    async with self._pool.acquire() as conn:
        async with conn.transaction(isolation="serializable"):
            # Lock cycle row and check cancelled in one query
            row = await conn.fetchrow(
                "SELECT cancelled FROM cycle_registry WHERE cycle_id = $1 FOR UPDATE",
                run.cycle_id,
            )
            if row is None:
                raise CycleNotFoundError(f"Cycle not found: {run.cycle_id}")
            if row["cancelled"]:
                raise IllegalStateTransitionError(
                    f"Cannot create run on cancelled cycle: {run.cycle_id}"
                )

            # Allocate next run_number under the lock
            next_num = await conn.fetchval(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM cycle_runs WHERE cycle_id = $1",
                run.cycle_id,
            )

            # Insert with allocated run_number
            await conn.execute(
                "INSERT INTO cycle_runs (...) VALUES ($1, $2, $3, ...)",
                run.run_id, run.cycle_id, next_num, ...
            )
    return dataclasses.replace(run, run_number=next_num)
```

The `SELECT ... FOR UPDATE` on the cycle row serializes concurrent `create_run()` calls for the same cycle. Transaction isolation is `serializable` to prevent phantom reads on the `MAX(run_number)` query. The caller-supplied `run.run_number` is ignored — the DB-allocated value is authoritative.

#### 5.2.3 Artifact Refs: Order Preservation and De-duplication

Artifact refs represent a timeline of produced artifacts. **Insertion order matters** (earlier tasks produce earlier refs).

De-duplication happens in Python before the UPDATE to preserve order:

```python
async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run:
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT artifact_refs FROM cycle_runs WHERE run_id = $1", run_id
        )
        if row is None:
            raise RunNotFoundError(f"Run not found: {run_id}")

        existing = list(row["artifact_refs"])
        existing_set = set(existing)
        for aid in artifact_ids:
            if aid not in existing_set:
                existing.append(aid)
                existing_set.add(aid)

        await conn.execute(
            "UPDATE cycle_runs SET artifact_refs = $1 WHERE run_id = $2",
            existing, run_id,
        )
    return await self.get_run(run_id)
```

De-duplication is **global** — an artifact ID already present from a prior append is never re-added. SQL `ARRAY(SELECT DISTINCT ...)` is NOT used because it scrambles order.

#### 5.2.4 Run + Gate Decision Assembly

`get_run()` and `list_runs()` use **two separate queries** rather than a `LEFT JOIN ... array_agg(g.*)` aggregate. Aggregating composite row types via `array_agg` produces awkward nested record types in asyncpg that require custom type codecs. Two simple queries are cleaner:

```python
async def get_run(self, run_id: str) -> Run:
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM cycle_runs WHERE run_id = $1", run_id
        )
        if row is None:
            raise RunNotFoundError(f"Run not found: {run_id}")

        gate_rows = await conn.fetch(
            "SELECT gate_name, decision, decided_by, decided_at, notes "
            "FROM cycle_gate_decisions WHERE run_id = $1 ORDER BY id",
            run_id,
        )
        return self._assemble_run(row, gate_rows)
```

For `list_runs()`, gate decisions are fetched in a single batch query for all run IDs in the result set, then grouped in Python:

```python
async def list_runs(self, cycle_id: str, *, limit=50, offset=0) -> list[Run]:
    async with self._pool.acquire() as conn:
        run_rows = await conn.fetch(
            "SELECT * FROM cycle_runs WHERE cycle_id = $1 "
            "ORDER BY run_number LIMIT $2 OFFSET $3",
            cycle_id, limit, offset,
        )
        if not run_rows:
            return []

        run_ids = [r["run_id"] for r in run_rows]
        gate_rows = await conn.fetch(
            "SELECT run_id, gate_name, decision, decided_by, decided_at, notes "
            "FROM cycle_gate_decisions WHERE run_id = ANY($1) ORDER BY id",
            run_ids,
        )
        gates_by_run: dict[str, list] = {}
        for g in gate_rows:
            gates_by_run.setdefault(g["run_id"], []).append(g)

        return [
            self._assemble_run(r, gates_by_run.get(r["run_id"], []))
            for r in run_rows
        ]
```

This avoids N+1 for gate decisions while keeping the query shapes simple.

### 5.3 Row-to-Model Reconstruction

The adapter reconstructs frozen dataclasses from rows:

```python
def _row_to_cycle(self, row: asyncpg.Record) -> Cycle:
    gates = tuple(
        Gate(name=g["name"], description=g["description"],
             after_task_types=tuple(g["after_task_types"]))
        for g in row["task_flow_policy"].get("gates", ())
    )
    return Cycle(
        cycle_id=row["cycle_id"],
        project_id=row["project_id"],
        ...
        task_flow_policy=TaskFlowPolicy(
            mode=row["task_flow_policy"]["mode"], gates=gates
        ),
        expected_artifact_types=tuple(row["expected_artifact_types"]),
        ...
    )
```

This mirrors the existing `_to_cycle()` / `_to_run()` helpers in `MemoryCycleRegistry` — same reconstruction logic, different source (asyncpg Record vs dict).

### 5.4 Gate Decision Validation

Gate decisions are recorded using a **transactional SELECT-then-INSERT** pattern. The `UNIQUE(run_id, gate_name)` constraint is a safety net, not the primary conflict detection mechanism.

```python
async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run:
    async with self._pool.acquire() as conn:
        # read_committed is sufficient: the FOR UPDATE row lock on run_id
        # serializes concurrent decisions, and the UNIQUE(run_id, gate_name)
        # constraint guards against any remaining races.
        async with conn.transaction(isolation="read_committed"):
            # 1. Load run + validate not terminal
            run_row = await conn.fetchrow(
                "SELECT status, cycle_id FROM cycle_runs WHERE run_id = $1 FOR UPDATE",
                run_id,
            )
            if run_row is None:
                raise RunNotFoundError(f"Run not found: {run_id}")
            if RunStatus(run_row["status"]) in TERMINAL_STATES:
                raise RunTerminalError(...)

            # 2. Validate gate_name exists in cycle's policy
            cycle_row = await conn.fetchrow(
                "SELECT task_flow_policy FROM cycle_registry WHERE cycle_id = $1",
                run_row["cycle_id"],
            )
            policy = cycle_row["task_flow_policy"]
            gate_names = {g["name"] for g in policy.get("gates", ())}
            if decision.gate_name not in gate_names:
                raise ValidationError(f"Gate {decision.gate_name!r} not in policy")

            # 3. Check existing decision for this gate
            existing = await conn.fetchrow(
                "SELECT decision FROM cycle_gate_decisions "
                "WHERE run_id = $1 AND gate_name = $2",
                run_id, decision.gate_name,
            )
            if existing is not None:
                if existing["decision"] == decision.decision:
                    # Idempotent — same decision is a no-op
                    return await self.get_run(run_id)
                else:
                    raise GateAlreadyDecidedError(
                        f"Gate {decision.gate_name!r} already decided "
                        f"as {existing['decision']!r}"
                    )

            # 4. Insert new decision (decided_at is caller-provided and preserved)
            await conn.execute(
                "INSERT INTO cycle_gate_decisions "
                "(run_id, gate_name, decision, decided_by, decided_at, notes) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                run_id, decision.gate_name, decision.decision,
                decision.decided_by, decision.decided_at, decision.notes,
            )

    return await self.get_run(run_id)
```

The three-way logic (new → insert, same → no-op, different → error) is explicit in Python. The UNIQUE constraint catches any race between concurrent transactions as a last resort.

**`decided_at` is caller-provided and preserved as-is.** The adapter does not override it with `now()`. This allows the API layer to stamp the decision time at request receipt, which is the authoritative audit timestamp. The adapter is a dumb store for this field.

### 5.5 CycleStatus Derivation

`CycleStatus` is **derived** from runs, not stored — consistent with the existing `derive_cycle_status()` function in `squadops/cycles/lifecycle.py`.

**Correctness-first path** (N+1, used in v1.0):

```python
async def list_cycles(self, project_id, *, status=None, limit=50, offset=0):
    rows = await self._pool.fetch(
        "SELECT * FROM cycle_registry WHERE project_id = $1 "
        "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        project_id, limit, offset,
    )
    cycles = [self._row_to_cycle(r) for r in rows]
    if status is None:
        return cycles

    # N+1: fetch latest run per cycle to derive status.
    # Uses _latest_run_for_cycle() (not paginated list_runs) to avoid
    # truncation from limit/offset defaults producing incorrect derivation.
    result = []
    for cycle in cycles:
        latest = await self._latest_run_for_cycle(cycle.cycle_id)
        derived = derive_cycle_status(
            [latest] if latest else [],
            cycle_cancelled=cycle.cancelled,
        )
        if derived == status:
            result.append(cycle)
    return result

async def _latest_run_for_cycle(self, cycle_id: str) -> Run | None:
    """Fetch the single most recent run for status derivation."""
    async with self._pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM cycle_runs WHERE cycle_id = $1 "
            "ORDER BY run_number DESC LIMIT 1",
            cycle_id,
        )
        if row is None:
            return None
        gate_rows = await conn.fetch(
            "SELECT gate_name, decision, decided_by, decided_at, notes "
            "FROM cycle_gate_decisions WHERE run_id = $1 ORDER BY id",
            row["run_id"],
        )
        return self._assemble_run(row, gate_rows)
```

This is explicitly **correctness-first and non-optimized** (N+1 queries, one per cycle in the page). It exists for behavioral parity with the memory adapter and is intended for:
- Test environments
- Low-volume operational use (< 50 cycles per project)
- API callers that omit the `status` filter (no N+1 — just a single paginated query)

**The control plane UI must not use the status-filtered path at scale.** UI pages that need status filtering should use unfiltered pagination and filter client-side, or wait for the optimized SQL path (§5.5.1). This is a known limitation, not a bug.

#### 5.5.1 UI-Ready Query (Deferred Enhancement)

When the control plane UI requires filtered pagination, replace the N+1 path with a single SQL query that derives status in the database:

```sql
SELECT cr.*,
    CASE
        WHEN cr.cancelled THEN 'cancelled'
        WHEN latest_run.status IS NULL THEN 'created'
        WHEN latest_run.status IN ('completed') THEN 'completed'
        WHEN latest_run.status IN ('failed') THEN 'failed'
        WHEN latest_run.status IN ('cancelled') THEN 'cancelled'
        ELSE 'active'
    END AS derived_status
FROM cycle_registry cr
LEFT JOIN LATERAL (
    SELECT status FROM cycle_runs
    WHERE cycle_id = cr.cycle_id
    ORDER BY run_number DESC LIMIT 1
) latest_run ON TRUE
WHERE cr.project_id = $1
    AND (CASE ... END) = $2  -- optional status filter
ORDER BY cr.created_at DESC
LIMIT $3 OFFSET $4;
```

This is **not implemented in v1.0** but is documented here so the optimization path is clear when needed.

### 5.6 Error Mapping

All `asyncpg` exceptions are caught and mapped to domain exceptions. No `asyncpg` exceptions leak to callers.

| asyncpg Exception | Domain Exception | When |
|---|---|---|
| `ForeignKeyViolationError` on `cycle_runs.cycle_id` | `CycleNotFoundError` | `create_run()` with nonexistent cycle |
| `UniqueViolationError` on `(run_id, gate_name)` | `GateAlreadyDecidedError` | Race between concurrent gate decisions (safety net; primary detection is in Python §5.4) |
| `UniqueViolationError` on `(cycle_id, run_number)` | Should not occur — `run_number` is allocated under lock (§5.2.2). If it does, retry once. |
| Empty `SELECT` result | `CycleNotFoundError` / `RunNotFoundError` | `get_cycle()`, `get_run()`, etc. |

The adapter wraps all database calls in a try/except that translates `asyncpg` exceptions:

```python
try:
    await conn.execute(...)
except asyncpg.ForeignKeyViolationError:
    raise CycleNotFoundError(...)
except asyncpg.UniqueViolationError:
    raise GateAlreadyDecidedError(...)
```

### 5.7 Factory Selection

**File:** `adapters/cycles/factory.py`

```python
def create_cycle_registry(provider: str, **kwargs) -> CycleRegistryPort:
    if provider == "memory":
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
        return MemoryCycleRegistry()
    elif provider == "postgres":
        from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
        return PostgresCycleRegistry(pool=kwargs["pool"])
    raise ValueError(f"Unknown cycle registry provider: {provider}")
```

**Config**: `SQUADOPS__CYCLES__REGISTRY_PROVIDER=postgres` (default: `memory` for backward compat).

### 5.8 Runtime Wiring

**File:** `src/squadops/api/runtime/main.py`

In `startup_event()`, after the asyncpg pool is created:

```python
# Apply migrations (idempotent)
await _apply_migrations(pool)

if config.cycles.registry_provider == "postgres":
    cycle_registry = create_cycle_registry("postgres", pool=pool)
else:
    cycle_registry = create_cycle_registry("memory")
```

The pool already exists (SIP-0055) — no new connections needed.

### 5.9 Migration Strategy

**File:** `infra/migrations/001_cycle_registry.sql`

Migrations are applied by the **runtime-api at startup** — not by `docker-entrypoint-initdb.d` (which only runs on first PG volume init and is unreliable for existing deployments).

The migration runner is a small function in `main.py` (or a shared utility):

```python
async def _apply_migrations(pool: asyncpg.Pool, migrations_dir: Path) -> None:
    """Apply pending SQL migrations at startup.

    Idempotent: uses a migrations tracking table to skip already-applied files.
    """
    async with pool.acquire() as conn:
        # Ensure tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        # Find and apply pending migrations
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            already = await conn.fetchval(
                "SELECT 1 FROM _schema_migrations WHERE filename = $1",
                sql_file.name,
            )
            if already:
                continue
            sql = sql_file.read_text()
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _schema_migrations (filename) VALUES ($1)",
                sql_file.name,
            )
            logger.info("Applied migration: %s", sql_file.name)
```

The `migrations_dir` is resolved from config, not from `__file__` parents:

```python
# In startup_event():
migrations_dir = Path(config.database.migrations_dir)  # e.g., "/app/infra/migrations"
await _apply_migrations(pool, migrations_dir)
```

**Config**: `SQUADOPS__DATABASE__MIGRATIONS_DIR` — defaults to `infra/migrations` (relative to working directory). Docker containers set it to an absolute path via the compose environment block.

**Key properties:**
- Runs on every startup — safe for existing PG volumes, new volumes, and redeployments.
- `_schema_migrations` table tracks which files have been applied.
- Migration files are sorted alphabetically (`001_...`, `002_...`) for deterministic ordering.
- All DDL in migration files uses `IF NOT EXISTS` as a defense-in-depth measure.
- Migration files must be compatible with `asyncpg`'s `execute()` for multi-statement DDL. Each migration file is executed as a single `execute()` call. Complex migrations requiring statement-level error handling should be wrapped in a `DO $$ ... $$` block.
- The legacy `cycle` table (SIP-0024) is **not modified or dropped** — it serves the health-check dashboard.

---

## 6. Pagination Extension

Add optional `limit` and `offset` to list methods on the port:

```python
# CycleRegistryPort (updated)
@abstractmethod
async def list_cycles(
    self, project_id: str, *,
    status: CycleStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Cycle]:

@abstractmethod
async def list_runs(
    self, cycle_id: str, *,
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
```

**This is a breaking change to `CycleRegistryPort`.** All implementers must be updated:
- `MemoryCycleRegistry`: Accept params, apply Python slicing (`results[offset:offset+limit]`).
- `PostgresCycleRegistry`: Append `LIMIT $N OFFSET $M` to queries.
- All test doubles (mocks, fakes) in existing tests must accept the new kwargs.

Callers that don't pass `limit`/`offset` are unaffected (defaults apply).

---

## 7. Test Plan

### 7.1 Unit Tests (`tests/unit/cycles/test_postgres_cycle_registry.py`)

Mock `asyncpg.Pool` (same pattern as existing persistence tests):

- `test_create_cycle_inserts_row` — verify INSERT called with correct params
- `test_get_cycle_not_found` — verify `CycleNotFoundError` on empty result
- `test_create_run_on_cancelled_cycle_raises` — verify check before insert
- `test_create_run_allocates_run_number_under_lock` — verify FOR UPDATE + MAX+1
- `test_update_run_status_sets_started_at_once` — verify `COALESCE(started_at, now())`
- `test_update_run_status_sets_finished_at_once` — verify `COALESCE(finished_at, now())`
- `test_update_run_status_does_not_reset_started_at` — paused→running keeps original
- `test_append_artifact_refs_preserves_order` — verify insertion order maintained
- `test_append_artifact_refs_deduplicates_globally` — already-present ID not re-added
- `test_record_gate_decision_idempotent` — same decision → no-op
- `test_record_gate_decision_conflict_raises` — different decision → `GateAlreadyDecidedError`
- `test_record_gate_decision_unknown_gate_raises` — `ValidationError`
- `test_record_gate_decision_terminal_run_raises` — `RunTerminalError`
- `test_list_cycles_with_status_filter` — verify derived status filtering
- `test_row_to_cycle_reconstructs_frozen_dataclass` — round-trip fidelity
- `test_row_to_run_reconstructs_gate_decisions` — verify nested reconstruction
- `test_error_mapping_fk_violation` — `asyncpg.ForeignKeyViolationError` → `CycleNotFoundError`
- `test_error_mapping_unique_violation` — `asyncpg.UniqueViolationError` → `GateAlreadyDecidedError`

### 7.2 Contract Tests (`tests/unit/cycles/test_cycle_registry_contract.py`)

A shared test suite that runs against **both** `MemoryCycleRegistry` and `PostgresCycleRegistry` (with a real or mock pool) to verify behavioral parity:

- Create cycle → get cycle → fields match
- Create run → update status → get run → status matches
- Illegal transition → `IllegalStateTransitionError`
- Gate decision → idempotent → conflict → correct exceptions
- Cancel cycle → create run fails
- Append artifact refs → de-duplicated, order preserved
- Timestamp semantics: started_at set once, finished_at set once

This ensures the Postgres adapter is a true drop-in replacement.

### 7.3 Integration Tests (`tests/integration/cycles/test_postgres_cycle_registry_integration.py`)

Require running Postgres (`@pytest.mark.docker`):

- Full CRUD cycle: create → list → get → cancel
- Full run lifecycle: create → running → paused → running → completed
- Gate decision flow: record → idempotent repeat → conflict
- Artifact ref accumulation across multiple appends, order verified
- Pagination: create 10 cycles, list with limit=3, offset=3
- Concurrent run creation: two async create_run() calls → distinct run_numbers, no collision
- Migration runner: verify `_apply_migrations()` is idempotent (run twice, no error)

### 7.4 Regression

All existing tests in `run_new_arch_tests.sh` pass unchanged — `MemoryCycleRegistry` remains the default. Test doubles updated to accept `limit`/`offset` kwargs.

---

## 8. Files Summary

| File | Action |
|------|--------|
| `infra/migrations/001_cycle_registry.sql` | **New**: Schema DDL |
| `adapters/cycles/postgres_cycle_registry.py` | **New**: Postgres adapter |
| `adapters/cycles/factory.py` | Modify: add `create_cycle_registry()` factory |
| `src/squadops/ports/cycles/cycle_registry.py` | Modify: add `limit`/`offset` params to list methods (**breaking port change**) |
| `adapters/cycles/memory_cycle_registry.py` | Modify: accept `limit`/`offset`, apply Python slicing |
| `src/squadops/api/runtime/main.py` | Modify: wire Postgres registry via config, add `_apply_migrations()` |
| `src/squadops/config/schema.py` | Modify: add `registry_provider` to cycles config |
| `tests/unit/cycles/test_postgres_cycle_registry.py` | **New** |
| `tests/unit/cycles/test_cycle_registry_contract.py` | **New** |
| `tests/integration/cycles/test_postgres_cycle_registry_integration.py` | **New** |
| Existing test doubles | Modify: accept `limit`/`offset` kwargs |

---

## 9. Rollout

1. **Phase 1**: Migration runner + schema DDL + adapter + unit tests + contract tests. Default remains `memory`. **Single-PR constraint**: the port interface update (`limit`/`offset`), `MemoryCycleRegistry` update, `PostgresCycleRegistry`, and all test double updates must land in the same PR to avoid breaking the build.
2. **Phase 2**: Wire into runtime-api, integration tests, switch default to `postgres` for Docker deployments.
3. **Phase 3**: Backfill any in-flight cycles from memory to Postgres (manual — no auto-migration needed since memory state is ephemeral).

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Schema conflicts with legacy `cycle` table | New tables use distinct names (`cycle_registry`, `cycle_runs`, `cycle_gate_decisions`) |
| `asyncpg` pool exhaustion under load | Reuse existing pool with established limits; cycle operations are low-frequency |
| JSONB serialization drift | Contract tests verify round-trip fidelity against both adapters |
| Migration not applied on existing PG volumes | Runtime startup migration runner (§5.9) — not reliant on `docker-entrypoint-initdb.d` |
| Concurrent `run_number` collision | `SELECT ... FOR UPDATE` on cycle row serializes allocation (§5.2.2) |
| Gate decision race between concurrent transactions | Explicit SELECT-then-INSERT in transaction (§5.4); UNIQUE constraint as safety net |
| `list_cycles(status=)` N+1 performance | Acknowledged as correctness-first path; UI-ready SQL documented in §5.5.1 for future optimization |
| Leaky `asyncpg` exceptions | Explicit error mapping table (§5.6); all DB exceptions translated to domain exceptions |
| Port interface change breaks test doubles | Called out in §3.7 and §8; all implementers and mocks updated in same PR |
