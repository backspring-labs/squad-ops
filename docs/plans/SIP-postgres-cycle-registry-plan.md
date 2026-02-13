# Postgres Cycle Registry — Implementation Plan

## Context

The SIP (proposed, `sips/proposals/SIP-Postgres-Cycle-Registry.md`) replaces the in-memory `MemoryCycleRegistry` with a Postgres-backed adapter implementing `CycleRegistryPort`. All cycle, run, and gate-decision state becomes durable across runtime-api restarts. This is a prerequisite for the control plane UI (v1.0).

**SIP spec:** `sips/proposals/SIP-Postgres-Cycle-Registry.md`
**Depends on:** SIP-0064 (Cycle API models/ports), SIP-0055 (DB deployment profiles), SIP-0066 (Pipeline wiring)

---

## Key Discoveries from Exploration

1. **`CycleRegistryPort`** has 12 abstract methods. `MemoryCycleRegistry` is 212 lines with reconstruction helpers `_to_cycle()` / `_to_run()` that we'll mirror for asyncpg Records.

2. **`DBConfig` already has `MigrationConfig`** with `MigrationMode` enum (`off`, `startup`, `job`) at schema.py:57. The migration runner wires naturally to `mode=startup`.

3. **Existing `create_cycle_registry("memory")`** is already called in `main.py:234`. The factory (`adapters/cycles/factory.py`) already has the function — we just add the `"postgres"` branch.

4. **Pool creation** happens at `main.py` startup via `asyncpg.create_pool(POSTGRES_URL)`. The pool is stored as a module-level `pool` variable. We pass it to the Postgres adapter.

5. **`AppConfig` uses `extra = "forbid"`** (schema.py:566). Adding a new config field requires adding it to the model — we'll add `cycles` as a new top-level config block.

6. **Frozen dataclasses**: `Cycle` has nested `TaskFlowPolicy` with `Gate` tuples. JSONB round-trip requires the same reconstruction logic as `MemoryCycleRegistry._to_cycle()`.

7. **`derive_cycle_status()`** in `squadops/cycles/lifecycle.py` takes a list of `Run` objects and a `cycle_cancelled` bool. It only needs the latest run for derivation, but the memory adapter passes all runs.

8. **No `infra/migrations/` directory exists yet** — we create it.

9. **Canonical config path is `config.db`** (schema.py:511: `db: DBConfig`), NOT `config.database`. All code and examples must use `config.db`.

---

## Decisions (binding for implementation)

**D1) Migration runner at startup, config-driven path.** Migrations run in `startup_event()` after pool creation, before port initialization. The migrations directory is resolved from `config.db.migrations_dir` (new field on `DBConfig`, defaults to `"infra/migrations"` relative to cwd). Docker containers set an absolute path via compose env. No `Path(__file__).parents[N]`. Env var: `SQUADOPS__DB__MIGRATIONS_DIR`.

**D2) Transaction isolation is explicit everywhere.** `create_run()` uses `isolation="serializable"` (SIP §5.2.2). `record_gate_decision()` uses `isolation="read_committed"` (SIP §5.4). No default-isolation transactions.

**D3) Two-query assembly for runs + gate decisions.** `get_run()` does SELECT run + SELECT gate_decisions. `list_runs()` does SELECT runs + batch SELECT gate_decisions via `WHERE run_id = ANY($1)`. No `array_agg(g.*)` (SIP §5.2.4).

**D4) `decided_at` is caller-provided and preserved.** The adapter does not override with `now()`. The API layer stamps it at request receipt. **Non-API callers (e.g. internal orchestration, tests) MUST pass `decided_at` explicitly; the adapter never defaults.**

**D5) Artifact refs: insertion order preserved, Python de-duplication.** No SQL `DISTINCT`. De-dupe is global (SIP §5.2.3).

**D6) Status derivation uses `_latest_run_for_cycle()` only (correctness-first; optimize later).** Not paginated `list_runs()` which could truncate. Uses the `(cycle_id, run_number DESC)` index (SIP §5.5). This is N queries (one per cycle) — correct at any volume, fast at low volume. A batch LATERAL JOIN for UI pagination is deferred to a later SIP.

**D7) Single-PR constraint.** Port interface change (`limit`/`offset`) + `MemoryCycleRegistry` update + `PostgresCycleRegistry` + all test double updates land in one PR. See Phase 1.1 ripple checklist.

**D8) `run_number` is DB-authoritative.** `create_run()` ignores the caller-supplied `run_number`. Allocated under `SELECT ... FOR UPDATE` lock on the cycle row (SIP §5.2.2).

**D9) Error mapping is exhaustive.** Every `asyncpg` exception is caught and mapped. No DB exceptions leak. See SIP §5.6 for the mapping table.

**D10) Factory errors clearly on misconfiguration.** `create_cycle_registry("postgres")` requires a `pool` kwarg. If `provider == "postgres"` and `pool` is `None` or missing, the factory raises `ValueError("pool is required for postgres cycle registry provider")` immediately at startup. `main.py` only passes `pool` when `provider == "postgres"`.

**D11) Migration runner uses per-file transactions.** Each migration file: `BEGIN` → execute SQL → `INSERT INTO _schema_migrations` → `COMMIT`. On failure: `ROLLBACK`; partially-applied migrations are never marked as complete. The tracking table itself is created outside of per-file transactions (idempotent DDL).

**D12) Migration SQL style rules.** Migration files MUST:
  - Use only standard SQL (no `psql` meta-commands like `\d`, `\copy`, `\set`)
  - Not rely on statement separators beyond standard `;`
  - Use idempotent DDL (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
  - Be compatible with asyncpg `execute()` for multi-statement DDL
  - Use `DO $$ ... $$` blocks for complex conditional logic

**D13) Contract tests are purely behavioral — memory adapter only.** Contract tests verify `CycleRegistryPort` behavioral invariants against `MemoryCycleRegistry`. Postgres behavior is validated in integration tests against a real database. No mocked-asyncpg "contract" tests (they duplicate unit tests and give false confidence).

---

## Phase 1: Port Interface Change + Migration Runner + Schema DDL

Port interface change must land first (D7 — same PR as everything else).

### 1.1 Port interface: add `limit`/`offset` — `src/squadops/ports/cycles/cycle_registry.py`

```python
# list_cycles — add limit/offset with defaults
@abstractmethod
async def list_cycles(
    self, project_id: str, *,
    status: CycleStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Cycle]:

# list_runs — add limit/offset with defaults
@abstractmethod
async def list_runs(
    self, cycle_id: str, *,
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
```

**Ripple checklist (D7) — complete ALL before moving to Phase 1.2:**

1. Update `MemoryCycleRegistry.list_cycles()` and `list_runs()` signatures (Phase 1.2)
2. Update `PostgresCycleRegistry.list_cycles()` and `list_runs()` signatures (Phase 2.1)
3. Search `tests/` for any mock/fake/stub implementing `CycleRegistryPort`:
   - `tests/unit/conftest.py` fixtures (`mock_cycle_registry`, etc.)
   - `tests/unit/api/` — any `AsyncMock(spec=CycleRegistryPort)` instances
   - `tests/unit/cycles/` — any helper fakes
   - Inline `MagicMock`/`AsyncMock` in individual test files
4. Search `src/squadops/api/` for call sites passing positional args to `list_cycles`/`list_runs` — update to keyword-only where needed
5. Search `adapters/` for any DI providers or factory functions that type-check `CycleRegistryPort` signatures
6. Verify: `grep -rn "list_cycles\|list_runs" tests/ src/ adapters/` — every hit has been reviewed

### 1.2 Update `MemoryCycleRegistry` — `adapters/cycles/memory_cycle_registry.py`

Accept `limit`/`offset` on both methods, apply Python slicing:

```python
async def list_cycles(self, project_id, *, status=None, limit=50, offset=0):
    # ... existing logic ...
    return results[offset:offset + limit]

async def list_runs(self, cycle_id, *, limit=50, offset=0):
    results = [...]
    return results[offset:offset + limit]
```

### 1.3 Config: add `CyclesConfig` + `migrations_dir` — `src/squadops/config/schema.py`

Canonical field paths (used consistently in env vars, main.py, and all docs):

```python
class CyclesConfig(BaseModel):
    """Cycle registry configuration."""
    registry_provider: str = Field(
        default="memory",
        description="Cycle registry provider: 'memory' or 'postgres'",
    )

# On DBConfig (schema.py:63), add:
    migrations_dir: str = Field(
        default="infra/migrations",
        description="Path to SQL migrations directory",
    )

# On AppConfig (schema.py:507), add:
    cycles: CyclesConfig = Field(
        default_factory=CyclesConfig,
        description="Cycle registry configuration",
    )
```

**Canonical env vars** (matches `config.db` and `config.cycles` paths):
- `SQUADOPS__CYCLES__REGISTRY_PROVIDER=postgres`
- `SQUADOPS__DB__MIGRATIONS_DIR=/app/infra/migrations`

### 1.4 Migration runner — `src/squadops/api/runtime/migrations.py` (NEW)

Standalone module (not inlined in main.py) for testability. **Per-file transactions (D11):**

```python
"""Startup migration runner for runtime-api.

Applies pending SQL migrations from a configured directory.
Idempotent: tracks applied files in _schema_migrations table.
Each migration runs in its own transaction: execute SQL + record
applied row atomically. On failure the transaction rolls back and
the migration is not marked as applied.
"""
from pathlib import Path
import logging
import asyncpg

logger = logging.getLogger(__name__)

async def apply_migrations(pool: asyncpg.Pool, migrations_dir: Path) -> int:
    """Apply pending migrations. Returns count of newly applied files."""
    applied = 0
    async with pool.acquire() as conn:
        # Create tracking table (idempotent, outside per-file txn)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        if not migrations_dir.is_dir():
            logger.info("No migrations directory at %s — skipping", migrations_dir)
            return 0

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            already = await conn.fetchval(
                "SELECT 1 FROM _schema_migrations WHERE filename = $1",
                sql_file.name,
            )
            if already:
                continue

            sql = sql_file.read_text()
            # Per-file transaction: SQL + tracking row atomically
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _schema_migrations (filename) VALUES ($1)",
                    sql_file.name,
                )
            logger.info("Applied migration: %s", sql_file.name)
            applied += 1
    return applied
```

On failure: `conn.transaction()` context manager rolls back automatically. The migration file is not recorded in `_schema_migrations`, so the next startup retries it.

### 1.5 Schema DDL — `infra/migrations/001_cycle_registry.sql` (NEW)

Create the `infra/migrations/` directory and write the DDL exactly as specified in SIP §5.1:

- `cycle_registry` table (13 columns)
- `cycle_runs` table (10 columns + UNIQUE(cycle_id, run_number))
- `cycle_gate_decisions` table (7 columns + UNIQUE(run_id, gate_name))
- 5 indexes including `idx_cycle_runs_cycle_latest ON (cycle_id, run_number DESC)`

All `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` — idempotent (D12).

**No `psql` meta-commands. No non-standard statement separators. DDL must be idempotent.**

### 1.6 Tests for Phase 1

**`tests/unit/cycles/test_migration_runner.py`** (NEW):
- `test_apply_migrations_creates_tracking_table` — mock pool, verify CREATE TABLE
- `test_apply_migrations_skips_already_applied` — verify SELECT check
- `test_apply_migrations_applies_new_file` — verify execute + INSERT within transaction
- `test_apply_migrations_returns_count` — verify return value
- `test_apply_migrations_no_dir` — non-existent dir returns 0, no error
- `test_apply_migrations_idempotent` — run twice, second run applies nothing
- `test_apply_migrations_rollback_on_failure` — simulate SQL error, verify migration NOT recorded in tracking table
- `test_001_migration_no_forbidden_tokens` — load `001_cycle_registry.sql`, assert no `\d`, `\copy`, `\set` or other `psql` meta-commands

**Update existing test doubles (ripple checklist item 3)**: Any mock/fake `CycleRegistryPort` in existing tests that doesn't accept `limit`/`offset` kwargs must be updated. Search for `list_cycles` and `list_runs` in all test fixtures.

### Phase 1 verification

```bash
pytest tests/unit/cycles/test_migration_runner.py -v
./scripts/dev/run_new_arch_tests.sh -v  # All existing tests still pass
```

---

## Phase 2: Postgres Adapter

### 2.1 Adapter — `adapters/cycles/postgres_cycle_registry.py` (NEW)

Full `CycleRegistryPort` implementation (~300 lines). Structure:

```python
class PostgresCycleRegistry(CycleRegistryPort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- Cycle CRUD ---
    async def create_cycle(self, cycle: Cycle) -> Cycle: ...
    async def get_cycle(self, cycle_id: str) -> Cycle: ...
    async def list_cycles(self, project_id, *, status=None, limit=50, offset=0): ...
    async def cancel_cycle(self, cycle_id: str) -> None: ...

    # --- Run CRUD ---
    async def create_run(self, run: Run) -> Run: ...          # serializable txn (D2, D8)
    async def get_run(self, run_id: str) -> Run: ...           # two-query (D3)
    async def list_runs(self, cycle_id, *, limit=50, offset=0): ...  # batch gate fetch (D3)
    async def update_run_status(self, run_id, status): ...     # COALESCE timestamps
    async def cancel_run(self, run_id: str) -> None: ...
    async def append_artifact_refs(self, run_id, ids): ...     # Python de-dup (D5)

    # --- Gate decisions ---
    async def record_gate_decision(self, run_id, decision): ... # read_committed txn (D2, D4)

    # --- Internal helpers ---
    def _row_to_cycle(self, row: asyncpg.Record) -> Cycle: ...
    def _assemble_run(self, row, gate_rows) -> Run: ...
    async def _latest_run_for_cycle(self, cycle_id) -> Run | None: ...  # (D6)
```

**Method implementation details** (keyed to SIP sections):

| Method | Key behavior | SIP ref |
|--------|-------------|---------|
| `create_run` | `FOR UPDATE` on cycle row, `isolation="serializable"`, allocate `MAX(run_number)+1`, check `cancelled` flag in same txn | §5.2.2 |
| `update_run_status` | Python `validate_run_transition()` first, then `COALESCE(started_at, now())` / `COALESCE(finished_at, now())` | §5.2.1 |
| `append_artifact_refs` | Read existing array, de-dup in Python preserving order, write back | §5.2.3 |
| `get_run` / `list_runs` | Two queries: run rows + gate decision rows, assemble in Python | §5.2.4 |
| `record_gate_decision` | `isolation="read_committed"`, `FOR UPDATE` on run row, SELECT existing decision, three-way branch (insert/no-op/error) | §5.4 |
| `list_cycles(status=...)` | N+1 via `_latest_run_for_cycle()`, not paginated `list_runs()` (D6: correctness-first) | §5.5 |
| All methods | Wrap `asyncpg` exceptions → domain exceptions per mapping table | §5.6 |

### 2.2 Factory update — `adapters/cycles/factory.py`

Add `"postgres"` branch to `create_cycle_registry()` with clear misconfiguration error (D10):

```python
def create_cycle_registry(provider: str, **kwargs) -> CycleRegistryPort:
    if provider == "memory":
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
        return MemoryCycleRegistry()
    elif provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError(
                "pool is required for postgres cycle registry provider"
            )
        from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
        return PostgresCycleRegistry(pool=pool)
    raise ValueError(f"Unknown cycle registry provider: {provider}")
```

### 2.3 Tests for Phase 2

**`tests/unit/cycles/test_postgres_cycle_registry.py`** (NEW, ~18 tests):

Mock `asyncpg.Pool` with `AsyncMock`. Each test verifies the **SQL call pattern** and domain exception mapping. **Note: unit tests only assert SQL shape; only integration tests (Phase 3) validate uniqueness, locking, and concurrency correctness under real Postgres contention (D2, D8).**

- `test_create_cycle_inserts_row`
- `test_get_cycle_not_found` → `CycleNotFoundError`
- `test_create_run_on_cancelled_cycle_raises` → `IllegalStateTransitionError`
- `test_create_run_allocates_run_number_under_lock` — verify `FOR UPDATE` + `MAX+1` SQL shape
- `test_update_run_status_sets_started_at_once` — verify `COALESCE`
- `test_update_run_status_sets_finished_at_once` — verify `COALESCE`
- `test_update_run_status_does_not_reset_started_at` — paused→running keeps original
- `test_append_artifact_refs_preserves_order`
- `test_append_artifact_refs_deduplicates_globally`
- `test_record_gate_decision_idempotent` — same decision → no-op
- `test_record_gate_decision_conflict_raises` → `GateAlreadyDecidedError`
- `test_record_gate_decision_unknown_gate_raises` → `ValidationError`
- `test_record_gate_decision_terminal_run_raises` → `RunTerminalError`
- `test_list_cycles_with_status_filter` — verify N+1 derivation
- `test_row_to_cycle_reconstructs_frozen_dataclass`
- `test_row_to_run_reconstructs_gate_decisions`
- `test_error_mapping_fk_violation` → `CycleNotFoundError`
- `test_error_mapping_unique_violation` → `GateAlreadyDecidedError`

**`tests/unit/cycles/test_cycle_registry_contract.py`** (NEW):

Shared behavioral test suite for `CycleRegistryPort` invariants — **memory adapter only (D13)**:

```python
@pytest.fixture
def registry():
    return MemoryCycleRegistry()
```

Contract tests verify port-level behavioral invariants that any correct implementation must satisfy:
- Create cycle → get → fields match
- Create run → update status → get → status matches
- Illegal transition → `IllegalStateTransitionError`
- Gate decision: new → idempotent → conflict
- Cancel cycle → create run fails
- Append artifact refs: de-duplicated, order preserved
- Timestamp semantics: `started_at` set once, `finished_at` set once

Postgres behavioral correctness is validated by integration tests against a real database (Phase 3).

### Phase 2 verification

```bash
pytest tests/unit/cycles/test_postgres_cycle_registry.py -v
pytest tests/unit/cycles/test_cycle_registry_contract.py -v
./scripts/dev/run_new_arch_tests.sh -v
```

---

## Phase 3: Runtime Wiring + Integration Tests

### 3.1 Wire into `main.py` — `src/squadops/api/runtime/main.py`

In `startup_event()`, after pool creation and before cycle port initialization:

```python
# Apply migrations (idempotent)
from squadops.api.runtime.migrations import apply_migrations
migrations_dir = Path(config.db.migrations_dir)
await apply_migrations(pool, migrations_dir)

# Create cycle registry based on config (D10: pool only when postgres)
cycle_registry = create_cycle_registry(
    config.cycles.registry_provider,
    **({"pool": pool} if config.cycles.registry_provider == "postgres" else {}),
)
```

Replace the existing `create_cycle_registry("memory")` call (line 234).

### 3.2 Docker compose env — `docker-compose.yml`

Add to runtime-api environment:

```yaml
SQUADOPS__CYCLES__REGISTRY_PROVIDER: postgres
SQUADOPS__DB__MIGRATIONS_DIR: /app/infra/migrations
```

### 3.3 Integration tests — `tests/integration/cycles/test_postgres_cycle_registry_integration.py` (NEW)

Require running Postgres (`@pytest.mark.docker`):

- `test_full_cycle_crud` — create → list → get → cancel
- `test_full_run_lifecycle` — create → running → paused → running → completed
- `test_gate_decision_flow` — record → idempotent repeat → conflict
- `test_artifact_ref_accumulation` — multiple appends, order verified
- `test_pagination` — create 10 cycles, list with limit=3, offset=3
- `test_concurrent_run_creation` — `asyncio.gather(create_run(...))` x20 iterations → all get distinct run_numbers, no serialization errors leak (retry loop catches flakiness, not just "worked once")
- `test_migration_runner_idempotent` — run `apply_migrations()` twice, no error
- `test_timestamps_set_once` — running→paused→running→completed, verify `started_at` unchanged
- `test_cancel_cycle_blocks_new_runs` — cancel → create_run raises
- `test_cancel_existing_runs_independent` — cancel cycle, then cancel run separately
- `test_persistence_across_adapter_restart` — create cycle + run, instantiate a **new** `PostgresCycleRegistry` with the same pool (simulates process restart), verify cycle and run still present and fields match. This proves the core objective: durability across process lifetimes.

### 3.4 Switch default for Docker

Update `docker-compose.yml` to set `SQUADOPS__CYCLES__REGISTRY_PROVIDER=postgres` for the runtime-api service. Local development defaults to `memory` (no env override needed).

### Phase 3 verification

```bash
# Integration tests (requires docker-compose up -d postgres)
pytest tests/integration/cycles/test_postgres_cycle_registry_integration.py -v

# Full regression
./scripts/dev/run_new_arch_tests.sh -v

# E2E cycle test (per cheat sheet)
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api
squadops login -u squadops-admin -p admin123 --keycloak-url http://localhost:8180 --realm squadops-local --client-id squadops-cli
squadops cycles create play_game --squad-profile full-squad --profile selftest
# Verify cycle persists across runtime-api restart:
docker-compose restart runtime-api
squadops cycles show play_game <cycle_id>  # Should still show completed cycle
```

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/ports/cycles/cycle_registry.py` | Modify: add `limit`/`offset` to list methods | 1 |
| `adapters/cycles/memory_cycle_registry.py` | Modify: accept `limit`/`offset`, apply slicing | 1 |
| `src/squadops/config/schema.py` | Modify: add `CyclesConfig`, `migrations_dir` on `DBConfig` | 1 |
| `src/squadops/api/runtime/migrations.py` | **New**: startup migration runner (per-file transactions) | 1 |
| `infra/migrations/001_cycle_registry.sql` | **New**: schema DDL (3 tables, 5 indexes) | 1 |
| `tests/unit/cycles/test_migration_runner.py` | **New** (~8 tests incl. rollback + forbidden token check) | 1 |
| Existing test doubles | Modify: accept `limit`/`offset` kwargs (ripple checklist) | 1 |
| `adapters/cycles/postgres_cycle_registry.py` | **New**: Postgres adapter (~300 lines) | 2 |
| `adapters/cycles/factory.py` | Modify: add `"postgres"` branch with pool validation (D10) | 2 |
| `tests/unit/cycles/test_postgres_cycle_registry.py` | **New**: ~18 unit tests (SQL shape only) | 2 |
| `tests/unit/cycles/test_cycle_registry_contract.py` | **New**: behavioral contract suite (memory only, D13) | 2 |
| `src/squadops/api/runtime/main.py` | Modify: wire migrations + postgres registry | 3 |
| `docker-compose.yml` | Modify: add env vars for runtime-api | 3 |
| `tests/integration/cycles/test_postgres_cycle_registry_integration.py` | **New**: ~11 integration tests (incl. persistence + concurrency) | 3 |

---

## pytest Markers

No new markers needed. Existing markers cover all test categories:
- Unit tests: auto-marked by `tests/unit/` location
- Integration tests: `@pytest.mark.docker` (already registered)

---

## Regression Checkpoints

After each phase, run:
```bash
./scripts/dev/run_new_arch_tests.sh -v
```

Expected counts:
- Phase 1: ~1300 (current 1291 + ~8 migration runner tests + existing tests updated)
- Phase 2: ~1330 (+ ~18 unit + ~7 contract tests)
- Phase 3: ~1340 (+ ~11 integration tests)
