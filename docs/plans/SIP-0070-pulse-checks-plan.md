# SIP-0070 Pulse Checks and Verification Framework — Implementation Plan

## Context

The cycle execution pipeline (SIP-0066) dispatches tasks sequentially through `DistributedFlowExecutor` with no verification between tasks — a run either completes all tasks or fails on the first error. For long-running autonomous cycles, this means errors compound silently until the run produces "confident garbage."

SIP-0070 (Rev 12) adds **pulse-exit guardrail verification**: cadence-bounded execution intervals (pulses) with fast, mechanical checks at boundaries. If a check fails, a bounded repair loop (4-agent chain, max 2 attempts) runs before the cycle continues or fails with `VERIFICATION_EXHAUSTED`.

This plan targets **SquadOps 0.9.9 (Tier 1 only)**. Tier 2 integration checks and Tier 3 audit reviews are deferred to follow-up SIPs.

**SIP spec**: `sips/accepted/SIP-0070-Pulse-Checks-and-Verification.md` (Rev 12)

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Pulse domain models go in new `src/squadops/cycles/pulse_models.py` | Keeps pulse verification separate from cycle/run lifecycle models. Same frozen dataclass pattern. |
| D2 | New `CheckType` enum values added to existing `src/squadops/capabilities/models.py` | Shared vocabulary per SIP §5.4 — same `AcceptanceCheck` model, same engine. |
| D3 | `AcceptanceCheck` gains optional fields (`url`, `expected_status`, `container_name`, `command`, `cwd`, `env`, `schema`) with `None` defaults. `__post_init__` validates per check type. **Security**: `cwd` must be relative (absolute paths and `..` traversal rejected at validation); resolved relative to repo/workspace root at runtime. `env` is allowlist-only — only explicitly declared key-value pairs are passed; no host environment inheritance. A minimal safe baseline `PATH` (`/usr/bin:/usr/local/bin`) is always injected so commands resolve without requiring absolute paths. | Avoids separate dataclass per check type while maintaining the shared schema. Command execution is sandboxed: no shell expansion, no host env leakage, cwd confined to repo/workspace root, `..` traversal blocked. |
| D4 | New check implementations are **async**. Engine gains `evaluate_async()` and `evaluate_all_async()`. Existing sync `evaluate()`/`evaluate_all()` unchanged. `evaluate_all_async` is **sequential by design** in Tier 1 — no `asyncio.gather()`. Parallel check execution deferred to Tier 2 when check independence can be guaranteed. | `http_status`, `process_running`, `command_exit_code` all require async I/O. Existing workload acceptance tests use sync path — no regression risk. Sequential execution ensures deterministic ordering and predictable timeout behavior. |
| D5 | **Split boundary identity from cadence interval identity.** `boundary_id` (semantic, stable) derived from `after_task_types` resolution (e.g., `post_dev`, `post_build`) + implicit `end_of_run`. `cadence_interval_id` (runtime, sequential) incremented by executor on each cadence close. Suites bind to `boundary_id`; records/telemetry carry both. No plan-time pulse_id grouping. | Resolves tension between semantic binding targets (what CRP authors write) and runtime cadence tracking (what the executor counts). CRP authors reference `post_dev`, not `pulse_2`. Simplifies plan generator — no cadence grouping needed. |
| D5a | **Two binding modes in 0.9.9.** `binding_mode: "milestone"` (default) — suite runs when its `boundary_id` matches a resolved milestone. `binding_mode: "cadence"` — suite runs at every cadence close (heartbeat guardrail); `parse_pulse_checks()` enforces `boundary_id == "cadence"` for cadence-bound suites and rejects any other value. This prevents cadence suites from masquerading as milestone suites. | Enables both "check artifacts after dev" (milestone) and "check container is alive every N tasks" (cadence heartbeat) without verbose per-boundary duplication. Parse-time enforcement makes CRP YAML self-documenting. |
| D6 | `parse_pulse_checks()` factory in `pulse_models.py` rejects `suite_class="proof"` at load time with clear error. | SIP §5.2: reject at CRP validation / applied-defaults load, not at runtime. Fail early. |
| D7 | Verification runner is a standalone module `src/squadops/cycles/pulse_verification.py`. Executor calls it as a black box at boundaries. | Keeps executor focused on dispatch. Runner is testable in isolation. |
| D8 | `PulseVerificationRecord` persisted via `CycleRegistryPort.record_pulse_verification()`. Stored as JSONB in a new `pulse_verification_records` table (Postgres) or dict list (Memory). | Separate table avoids bloating `cycle_runs` row. Clean query path for RCA. |
| D9 | Repair handlers follow `_CycleTaskHandler` pattern in new `src/squadops/capabilities/handlers/repair_tasks.py`. | Same LLM→artifact pipeline. 4 new capability IDs: `data.analyze_verification`, `governance.root_cause_analysis`, `strategy.corrective_plan`, `development.repair`. |
| D10 | Repair task envelopes share the current boundary's `boundary_id`, `cadence_interval_id`, `suite_id`, `trace_id`, and `correlation_id`. | Maintains LangFuse trace linking and telemetry correlation within the repair loop. All three IDs carried so records link to semantic milestone, runtime interval, and specific suite. |
| D11 | `_APPLIED_DEFAULTS_EXTRA_KEYS` updated to include `"pulse_checks"` and `"cadence_policy"`. | Same pattern as `"build_tasks"` and `"plan_tasks"` — executor-consumed, not API DTO fields. |
| D12 | New pytest marker `domain_pulse_checks` registered in `pyproject.toml`. | `--strict-markers` is enabled; missing markers cause collection errors. |
| D13 | `AcceptanceContext` gains `run_id: str = ""` for `{run_id}` template resolution. | SIP §7.3 lists `{run_id}` as a supported variable. Default `""` preserves backward compatibility. |
| D14 | `VERIFICATION_EXHAUSTED` is a `FAILED` reason, not a new `RunStatus` enum value. | `FAILED` is already terminal. Error message carries `VERIFICATION_EXHAUSTED` as machine-readable reason. No enum change needed. |
| D15 | **Every suite carries a `suite_id: str`.** `PulseCheckDefinition.suite_id` is author-assigned in CRP YAML. `parse_pulse_checks()` validates uniqueness within a profile. `suite_id` is carried into `PulseVerificationRecord`, all `pulse_check.*` telemetry events, and repair envelope metadata. | Multiple suites can bind to the same boundary; records must be distinguishable. Composite key `(run_id, boundary_id, cadence_interval_id, suite_id, repair_attempt)` uniquely identifies every verification record. |
| D16 | **Per-suite records, boundary-level decisions (Option A).** `PulseVerificationRecord` is per-suite: contains `suite_id` + `suite_outcome` (`SuiteOutcome`: PASS/FAIL/SKIP). Records do NOT contain the boundary-level decision. Boundary decision (`PulseDecision`: PASS/FAIL/EXHAUSTED) is derived from suite outcomes + repair exhaustion, emitted as a separate `pulse_check.boundary_decision` telemetry event, and returned from `determine_boundary_decision()`. | Clean separation: records are facts (suite X produced outcome Y), decisions are derived (all suites PASS → boundary PASS). Avoids redundant/conflicting decision fields on per-suite rows. |
| D17 | **`truncate_repair_tasks()` removed for 0.9.9.** The repair chain is exactly 4 steps; truncation is dead code. If the chain grows in a future SIP, truncation can be added then. | YAGNI — 4 fixed steps, no configuration knob to exceed 4. |
| D18 | **Suite-timeout SKIP carries `reason_code`; suite_outcome = FAIL.** When `evaluate_all_async` hits the suite-level timeout, remaining checks are marked SKIP with `reason_code="suite_timeout"` in the `AcceptanceResult`. The suite's overall `suite_outcome` is **FAIL** — incomplete guardrail evidence is not a PASS (Tier 1 safety invariant). `determine_boundary_decision()` requires all suite_outcomes == PASS for boundary PASS. Telemetry and records propagate the reason_code. | Distinguishes "never reached due to timeout" from other failure modes. Incomplete evidence cannot assert "safe to continue" — FAIL is the only sound default. |
| D19 | **`CADENCE_BOUNDARY_ID = "cadence"` constant in `pulse_models.py`.** Used everywhere cadence-bound boundaries are emitted, compared, or validated: executor cadence close, `parse_pulse_checks()` cadence binding enforcement (D5a), telemetry payloads, record writing. No bare `"cadence"` string literals outside tests. | Prevents accidental drift (`"cadence"` vs `"heartbeat"`) that would silently break bindings and metrics. Single source of truth for the cadence boundary identifier. |
| D20 | **Command output truncation metadata in `AcceptanceResult`.** When `_check_command_exit_code` truncates stdout/stderr at `max_output_bytes`, the result's metadata includes: `truncated: true`, `stdout_bytes: int`, `stderr_bytes: int`, `stdout_truncated: bool`, `stderr_truncated: bool`. This metadata is preserved into `PulseVerificationRecord.check_results` and telemetry events. | Makes RCA and dashboards reliable — avoids "silent truncation" where a truncated 64KB output looks identical to a complete one. Repair handlers can detect when the real error may be past the cutoff. |

---

## Phase 1: Domain Models and Acceptance Extensions

**Goal**: All domain models, new check types, CRP schema changes, and registry port extension land. Everything testable in isolation. No executor integration.

### 1.1 New CheckType enum values + AcceptanceCheck fields

**File**: `src/squadops/capabilities/models.py`

Add to `CheckType` enum:
- `HTTP_STATUS = "http_status"`
- `PROCESS_RUNNING = "process_running"`
- `JSON_SCHEMA = "json_schema"`
- `COMMAND_EXIT_CODE = "command_exit_code"`

Add optional fields to `AcceptanceCheck` (after existing `description`):
- `url: str | None = None` — http_status
- `expected_status: int | None = None` — http_status
- `container_name: str | None = None` — process_running
- `command: tuple[str, ...] | None = None` — command_exit_code (argv list)
- `expected_exit_code: int = 0` — command_exit_code
- `cwd: str | None = None` — command_exit_code (relative path only; absolute rejected at validation)
- `env: tuple[tuple[str, str], ...] = ()` — command_exit_code (allowlist-only; no host env inheritance)
- `schema: str | None = None` — json_schema (relative path)

Extend `__post_init__`:
- `HTTP_STATUS` requires `url` and `expected_status`
- `PROCESS_RUNNING` requires `container_name`
- `JSON_SCHEMA` requires `target` (document path) and `schema`; reject absolute `schema` paths
- `COMMAND_EXIT_CODE` requires `command` (non-empty tuple); reject absolute `cwd` paths (`os.path.isabs(cwd)` → `ValueError`); reject `..` segments in `cwd` (`".." in Path(cwd).parts` → `ValueError`)

**Tests** (~15): `tests/unit/capabilities/test_acceptance_models_extended.py`

### 1.2 AcceptanceContext.run_id

**File**: `src/squadops/capabilities/models.py` — add `run_id: str = ""` to `AcceptanceContext`
**File**: `src/squadops/capabilities/acceptance.py` — add `{run_id}` to `resolve_template()`

**Tests** (~3): append to existing `tests/unit/capabilities/test_acceptance.py`

### 1.3 Async check type implementations

**File**: `src/squadops/capabilities/acceptance.py`

New methods on `AcceptanceCheckEngine`:

- `async _check_http_status(check, context, timeout)` — `httpx.AsyncClient.get()`, template-resolved URL
- `async _check_process_running(check, context, timeout)` — `asyncio.create_subprocess_exec("docker", "inspect", ...)`, check `.State.Running` + optional `.State.Health.Status`
- `async _check_json_schema(check, context, profile_dir)` — load document + schema, `jsonschema.validate()` (add `jsonschema` dependency)
- `async _check_command_exit_code(check, context, timeout, max_output_bytes)` — `asyncio.create_subprocess_exec()`, `shell=False`, `cwd` resolved relative to repo/workspace root (absolute and `..` already rejected by `__post_init__`), `env` is the declared allowlist merged onto a minimal safe baseline (`{"PATH": "/usr/bin:/usr/local/bin"}`; no `os.environ` inheritance), capture stdout/stderr to limit. When truncation occurs, `AcceptanceResult.metadata` populated with `truncated=True`, `stdout_bytes`, `stderr_bytes`, `stdout_truncated`, `stderr_truncated` (per D20)
- `async evaluate_async(check, context, *, max_check_seconds=10, max_output_bytes=65536) -> AcceptanceResult` — dispatches to check method, wraps in `asyncio.wait_for(timeout)`
- `async evaluate_all_async(checks, context, *, max_suite_seconds=30, max_check_seconds=10, max_output_bytes=65536) -> ValidationReport` — sequential, no short-circuit, suite-level timeout (remaining checks SKIPPED with `reason_code="suite_timeout"` in AcceptanceResult; suite_outcome = FAIL per D18 — incomplete evidence is not a PASS)

Existing sync `evaluate()` / `evaluate_all()` are **unchanged** — workload acceptance code is unaffected.

**Dependency**: add `jsonschema` to `pyproject.toml` `[project.dependencies]`

**Tests** (~35): `tests/unit/capabilities/test_acceptance_extended.py`
- http_status: mock httpx → PASS, FAIL, connection error, timeout
- process_running: mock subprocess → running, not running, healthy, unhealthy, container not found
- json_schema: valid PASS, invalid FAIL, missing document, absolute schema path rejected
- command_exit_code: exit 0 PASS, exit 1 FAIL, timeout, absolute cwd rejected, `..` traversal rejected, relative cwd resolved within workspace root, env allowlist-only (no host env leakage), minimal PATH baseline injected, output truncation populates metadata (truncated/bytes/per-stream flags)
- evaluate_async: per-check timeout enforcement
- evaluate_all_async: no short-circuit, suite timeout SKIPs remaining with `reason_code="suite_timeout"`, suite_outcome = FAIL (incomplete evidence)

### 1.4 Pulse domain models

**New file**: `src/squadops/cycles/pulse_models.py`

```python
CADENCE_BOUNDARY_ID = "cadence"  # single constant — no bare "cadence" literals outside tests (D19)

CadencePolicy          # frozen dataclass: max_pulse_seconds=600, max_tasks_per_pulse=5
PulseCheckDefinition   # frozen dataclass: suite_id, boundary_id, checks, suite_class,
                       #   after_task_types, binding_mode ("milestone"|"cadence",
                       #   default "milestone"), timeouts
PulseDecision          # enum: PASS, FAIL, EXHAUSTED  (boundary-level decision)
SuiteOutcome           # enum: PASS, FAIL, SKIP       (per-suite result)
PulseVerificationRecord # frozen dataclass (per-suite): suite_id, boundary_id,
                        #   cadence_interval_id, run_id, suite_outcome (SuiteOutcome),
                        #   check_results, repair_attempt_number, recorded_at,
                        #   repair_task_refs, notes
                        # NOTE: no boundary-level "decision" field — that is derived
                        # by determine_boundary_decision() from suite outcomes.

def parse_pulse_checks(raw_list, profile_dir=None) -> tuple[PulseCheckDefinition, ...]
    # Validates suite_class != "proof" (fail early with clear error)
    # Validates binding_mode in {"milestone", "cadence"}
    # Enforces: if binding_mode == "cadence" then boundary_id MUST == CADENCE_BOUNDARY_ID (reject otherwise)
    # Validates suite_id uniqueness within the profile
    # Resolves json_schema.schema relative to profile_dir
    # Converts check dicts to AcceptanceCheck objects
```

**Tests** (~22): `tests/unit/cycles/test_pulse_models.py`
- Construction with defaults, immutability
- `suite_id` required, carried through to record
- `binding_mode` defaults to "milestone", rejects unknown values
- Cadence binding: `boundary_id="cadence"` accepted, `boundary_id="post_dev"` with `binding_mode="cadence"` rejected
- `parse_pulse_checks()`: valid input, proof rejection, relative path resolution, bad input, cadence binding mode, duplicate suite_id rejected

### 1.5 CRP schema extension

**File**: `src/squadops/contracts/cycle_request_profiles/schema.py`

```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {"build_tasks", "plan_tasks", "pulse_checks", "cadence_policy"}
```

**Tests** (~5): `tests/unit/contracts/test_crp_schema_pulse.py`

### 1.6 CycleRegistryPort extension

**File**: `src/squadops/ports/cycles/cycle_registry.py`

Add abstract method:
```python
@abstractmethod
async def record_pulse_verification(self, run_id: str, record: PulseVerificationRecord) -> Run:
```

### 1.7 MemoryCycleRegistry implementation

**File**: `adapters/cycles/memory_cycle_registry.py`

- Add `_pulse_verifications: dict[str, list[dict]]` storage
- Implement `record_pulse_verification()`: validate run exists + not terminal, append serialized record

### 1.8 PostgresCycleRegistry + migration

**New file**: `infra/migrations/002_pulse_verification.sql`

```sql
CREATE TABLE IF NOT EXISTS pulse_verification_records (
    id                    SERIAL PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES cycle_runs(run_id),
    suite_id              TEXT NOT NULL,
    boundary_id           TEXT NOT NULL,
    cadence_interval_id   INTEGER NOT NULL,
    suite_outcome         TEXT NOT NULL,       -- SuiteOutcome: PASS, FAIL, SKIP
    repair_attempt        INTEGER NOT NULL DEFAULT 0,
    check_results         JSONB NOT NULL DEFAULT '[]',
    repair_task_refs      TEXT[] NOT NULL DEFAULT '{}',
    notes                 TEXT,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, boundary_id, cadence_interval_id, suite_id, repair_attempt)
);
CREATE INDEX IF NOT EXISTS idx_pvr_run ON pulse_verification_records(run_id);
CREATE INDEX IF NOT EXISTS idx_pvr_run_boundary ON pulse_verification_records(run_id, boundary_id);
CREATE INDEX IF NOT EXISTS idx_pvr_run_cadence ON pulse_verification_records(run_id, cadence_interval_id);
```

**File**: `adapters/cycles/postgres_cycle_registry.py` — implement `record_pulse_verification()` with INSERT + return updated Run

### 1.9 Contract tests

**File**: `tests/unit/cycles/test_cycle_registry_contract.py`

Add `TestRecordPulseVerification` (~8 tests): PASS/FAIL/EXHAUSTED records, multiple pulses, multiple attempts, RunNotFoundError

### 1.10 Pytest marker

**File**: `pyproject.toml` — add `"domain_pulse_checks: Pulse check verification domain tests"`

### Phase 1 totals: ~94 new tests

---

## Phase 2: Verification Runner + Executor Integration

**Goal**: Executor detects pulse boundaries via cadence policy. Verification suites run at boundaries. Telemetry events emitted. No repair loop — FAIL = run FAILED.

### 2.1 Verification runner module

**New file**: `src/squadops/cycles/pulse_verification.py`

```python
async def run_pulse_verification(
    suites: list[PulseCheckDefinition],
    context: AcceptanceContext,
    engine: AcceptanceCheckEngine,
    boundary_id: str,
    cadence_interval_id: int,
) -> list[PulseVerificationRecord]:
    """Execute all bound suites at a pulse boundary. Returns one record per suite.
    Each record carries suite_id, boundary_id (semantic), cadence_interval_id (runtime),
    and suite_outcome (SuiteOutcome). No boundary-level decision on records."""

def determine_boundary_decision(records: list[PulseVerificationRecord]) -> PulseDecision:
    """Derive boundary-level decision from per-suite outcomes.
    PASS if all suite_outcome == PASS; FAIL if any suite_outcome == FAIL.
    (EXHAUSTED set by caller when repair attempts are exhausted.)"""

def resolve_milestone_bindings(
    pulse_checks: tuple[PulseCheckDefinition, ...],
    plan: list[TaskEnvelope],
) -> dict[int, list[PulseCheckDefinition]]:
    """Map plan index -> milestone-bound suites. For each milestone suite, resolves
    after_task_types via prefix matching: after_task_type 'development' matches all tasks
    whose task_type starts with 'development.' (e.g., development.code, development.build).
    Milestone boundary = the last plan index whose task_type matches the bound family.
    The emitted boundary_id is the suite's declared semantic label (e.g., 'post_dev'),
    NOT derived from the plan — the plan only determines *where* to fire.
    Returns unmatched suites separately for WARN logging."""

def collect_cadence_bound_suites(
    pulse_checks: tuple[PulseCheckDefinition, ...],
) -> list[PulseCheckDefinition]:
    """Return suites with binding_mode='cadence' (heartbeat guardrails).
    These run at every cadence close regardless of boundary_id."""
```

**Tests** (~24): `tests/unit/cycles/test_pulse_verification.py`
- `resolve_milestone_bindings()`: maps after_task_types to plan indices via prefix match, boundary_id comes from suite declaration (not plan), unmatched suites warned
- `collect_cadence_bound_suites()`: filters by binding_mode
- `run_pulse_verification()`: records carry suite_id, boundary_id, cadence_interval_id, suite_outcome
- `determine_boundary_decision()`: all PASS → PASS, any FAIL → FAIL, SKIP ignored, mixed outcomes

### 2.2 Task plan generator: no changes needed

**File**: `src/squadops/cycles/task_plan.py`

Per D5, **no plan-time pulse_id grouping**. The existing `TaskEnvelope.pulse_id = uuid4().hex` per-task remains unchanged — it is a **legacy per-task correlation ID** unrelated to pulse boundary identity. Pulse boundary identity is `boundary_id` + `cadence_interval_id` (not `TaskEnvelope.pulse_id`). Cadence intervals are runtime-only (executor counts tasks and wall-clock time). Milestone boundaries are derived from `after_task_types` resolution against the plan's task types.

**Tests**: None — no code change. Existing tests remain valid.

### 2.3 Executor cadence tracking + verification calls

**File**: `adapters/cycles/distributed_flow_executor.py`

Changes to `_execute_sequential()`:

1. Parse `CadencePolicy` and `PulseCheckDefinition` list from `cycle.applied_defaults`
2. Pre-dispatch resolution:
   - `milestone_bindings = resolve_milestone_bindings(pulse_checks, plan)` → `dict[int, list[PulseCheckDefinition]]` (plan index → bound suites)
   - `cadence_suites = collect_cadence_bound_suites(pulse_checks)` → `list[PulseCheckDefinition]`
   - Derive `milestone_boundaries` from `resolve_milestone_bindings()`: map of plan index → list of bound suites. Milestone boundary = the last index in the plan whose `task_type` prefix-matches the suite's `after_task_types` family. The emitted `boundary_id` is the suite's declared semantic label (e.g., `post_dev`), not derived from the plan — the plan only determines *where* to fire. Implicit `end_of_run` boundary at last plan index.
3. Track inside loop: `cadence_task_count`, `cadence_start_time`, `cadence_interval_id` (starts at 1, incremented on each cadence close)
4. After each task dispatch, evaluate two boundary conditions. **`max_pulse_seconds` is evaluated between task dispatches; it does not preempt an in-flight task.**

   **Cadence close** (runtime):
   ```
   cadence_closed = (
       cadence_task_count >= cadence.max_tasks_per_pulse
       or elapsed >= cadence.max_pulse_seconds
       or last_task_in_plan
   )
   ```
   At cadence close: run `cadence_suites` (if any) with `boundary_id=CADENCE_BOUNDARY_ID`, persist per-suite records, derive boundary decision via `determine_boundary_decision()`, emit `pulse_check.boundary_decision` event, increment `cadence_interval_id`, reset counters.

   **Milestone boundary** (semantic):
   ```
   milestone_hit = current_task_index in milestone_boundaries
   ```
   At milestone: look up bound suites for this index, run them with each suite's declared `boundary_id`, persist per-suite records, derive boundary decision. Milestone checks run **in addition to** any cadence-close checks at the same dispatch point (each with its own boundary_id).

5. At any boundary: call `run_pulse_verification()` with `boundary_id` and `cadence_interval_id`, persist per-suite records, derive `PulseDecision` from `determine_boundary_decision()`
6. Phase 2: FAIL → `raise _ExecutionError(...)` (no repair yet)
7. Verification runs **before** gate check (existing gate handling after verification)

### 2.4 Telemetry events

**File**: `adapters/cycles/distributed_flow_executor.py`

Add `_emit_pulse_event()` helper using `self._llm_observability.record_event()`.

Events emitted in Phase 2 (all payloads carry `suite_id`, `boundary_id`, `cadence_interval_id`):
- `pulse_check.binding_skipped` — during milestone binding resolution (unmatched boundary_id)
- `pulse_check.suite_started` — before each suite evaluation
- `pulse_check.suite_passed` — suite_outcome PASS (per-suite)
- `pulse_check.suite_failed` — suite_outcome FAIL (per-suite)
- `pulse_check.boundary_decision` — boundary-level PulseDecision (PASS/FAIL) after all suites at a boundary complete

**Tests** (~15): added to `tests/unit/cycles/test_distributed_flow_executor.py`
- Cadence close by task count and wall-clock time (non-preemptive)
- Milestone boundary detection by task_type prefix match
- Cadence-bound suites run at every cadence close with `boundary_id=CADENCE_BOUNDARY_ID`
- Milestone-bound suites run only at matching boundary_id
- Both cadence and milestone suites run when boundaries coincide (separate boundary_ids)
- Per-suite telemetry events carry suite_id
- `pulse_check.boundary_decision` emitted once per boundary
- Verification PASS continues, FAIL raises error
- No pulse_checks = unchanged behavior (backward compat)

### Phase 2 totals: ~42 new tests

---

## Phase 3: Repair Loop

**Goal**: FAIL triggers bounded repair loop. 4-agent chain. Append-and-execute. Max 2 attempts before EXHAUSTED.

### 3.1 Repair handlers

**New file**: `src/squadops/capabilities/handlers/repair_tasks.py`

4 handlers extending `_CycleTaskHandler`:

| Handler | capability_id | role | artifact |
|---------|---------------|------|----------|
| `DataAnalyzeVerificationHandler` | `data.analyze_verification` | `data` | `verification_analysis.md` |
| `GovernanceRootCauseHandler` | `governance.root_cause_analysis` | `lead` | `root_cause_analysis.md` |
| `StrategyCorrectivePlanHandler` | `strategy.corrective_plan` | `strat` | `corrective_plan.md` |
| `DevelopmentRepairHandler` | `development.repair` | `dev` | `repair_output.md` |

Each overrides `_build_user_prompt()` to inject verification failure context. Strategy handler outputs structured repair task specs in its artifact.

### 3.2 Handler registration

**File**: `src/squadops/bootstrap/handlers.py`

Add to `HANDLER_CONFIGS`:
```python
# Repair handlers (SIP-0070: Pulse Check Verification)
(DataAnalyzeVerificationHandler, ("data",)),
(GovernanceRootCauseHandler, ("lead",)),
(StrategyCorrectivePlanHandler, ("strat",)),
(DevelopmentRepairHandler, ("dev",)),
```

### 3.3 Repair task builder

**File**: `src/squadops/cycles/pulse_verification.py`

```python
REPAIR_TASK_STEPS = [
    ("data.analyze_verification", "data"),
    ("governance.root_cause_analysis", "lead"),
    ("strategy.corrective_plan", "strat"),
    ("development.repair", "dev"),
]

def build_repair_task_envelopes(...) -> list[TaskEnvelope]:
    """Build 4 repair envelopes sharing current suite_id/boundary_id/cadence_interval_id/
    trace_id/correlation_id. Always exactly 4 steps in 0.9.9 (per D17)."""
```

### 3.4 Executor repair loop

**File**: `adapters/cycles/distributed_flow_executor.py`

Replace Phase 2 `FAIL → raise` with bounded repair:

```
at_boundary:
    records = run all bound suites (per-suite records with suite_outcome)
    boundary_decision = determine_boundary_decision(records)
    if boundary_decision == PASS: continue
    failed_suites = [suites where suite_outcome == FAIL]
    repair_attempt = 0
    while failed_suites:
        if repair_attempt >= max_repair_attempts:
            emit pulse_check.boundary_decision(EXHAUSTED)
            fail run with VERIFICATION_EXHAUSTED
        repair_attempt += 1
        emit pulse_check.repair_started
        build repair envelopes (4 steps, per D17)
        dispatch repair envelopes, collect artifacts (tag with repair_attempt)
        rerun ONLY previously-failed suites
        update failed_suites from new per-suite records
    emit pulse_check.boundary_decision(PASS)
```

### 3.5 Telemetry completion

Remaining events:
- `pulse_check.repair_started` — carries suite_id of failed suite(s), repair_attempt number
- `pulse_check.boundary_decision(EXHAUSTED)` — repair attempts exhausted, run will fail

### 3.6 Tests

**New file**: `tests/unit/capabilities/test_repair_handlers.py` (~16 tests)
- 4 handlers: LLM success, LLM failure, verification context in prompt

**New file**: `tests/unit/cycles/test_repair_loop.py` (~18 tests)
- `build_repair_task_envelopes()`: envelope structure, shared IDs (suite_id, boundary_id, cadence_interval_id)
- Executor: FAIL→repair→PASS, FAIL→repair×2→EXHAUSTED, rerun only failed suites (by suite_id), timed-out suite reruns from first check
- Telemetry: per-suite events, boundary_decision events, repair_started events

**Modified**: `tests/unit/cycles/test_distributed_flow_executor.py` (~14 new tests)

### Phase 3 totals: ~48 new tests

---

## Phase 4: CRP Profiles, Integration Tests, Documentation

**Goal**: Reference profiles, end-to-end tests, documentation, run report extension.

### 4.1 Reference CRP profiles

**New file**: `src/squadops/contracts/cycle_request_profiles/profiles/pulse-check.yaml`
- Full cycle with `defaults.pulse_checks` (post-dev file_exists + non_empty)
- `defaults.cadence_policy` with defaults

**New file**: `src/squadops/contracts/cycle_request_profiles/profiles/pulse-check-build.yaml`
- Plan+build cycle with pulse checks at dev and build boundaries
- Build boundary uses `command_exit_code` for smoke tests

### 4.2 Profile + integration tests

**New file**: `tests/unit/contracts/test_crp_pulse_profiles.py` (~8 tests)
- Profile loads and validates, parse_pulse_checks round-trip, proof rejection

**New file**: `tests/integration/test_pulse_check_e2e.py` (~5 tests, skipped without runtime deps)
- Full executor run with verification PASS
- Repair loop: failing check → repair → rerun → PASS
- EXHAUSTED: persistent failure → run FAILED
- Backward compat: no pulse_checks = unchanged

### 4.3 Run report extension

**File**: `adapters/cycles/distributed_flow_executor.py`

Update `_generate_run_report()` to add "## Pulse Verification" section: boundaries checked, PASS/FAIL/EXHAUSTED counts, repair attempts summary.

### 4.4 Documentation

**File**: `CLAUDE.md` — add pulse_checks/cadence_policy to CRP schema docs, domain_pulse_checks marker
**File**: `README.md` — note pulse check verification in feature list

### 4.5 Update regression suite script

**File**: `scripts/dev/run_new_arch_tests.sh` — verify `tests/unit/cycles/` and `tests/unit/capabilities/` already included (they are)

### Phase 4 totals: ~15 new tests

---

## Summary

| Phase | New Tests | New Files | Modified Files |
|-------|-----------|-----------|----------------|
| 1: Models + Checks | ~94 | 4 (pulse_models.py, migration, 2 test files) | 7 |
| 2: Runner + Executor | ~42 | 2 (pulse_verification.py, 1 test file) | 1 |
| 3: Repair Loop | ~48 | 3 (repair_tasks.py, 2 test files) | 3 |
| 4: Profiles + Docs | ~15 | 4 (2 profiles, 2 test files) | 3 |
| **Total** | **~199** | **13** | **~14** |

Phases are strictly sequential: 1→2→3→4. Each phase is independently testable via `run_new_arch_tests.sh`.

---

## Critical Files

| File | Phase | Role |
|------|-------|------|
| `src/squadops/capabilities/models.py` | 1 | CheckType enum, AcceptanceCheck fields, AcceptanceContext.run_id |
| `src/squadops/capabilities/acceptance.py` | 1 | 4 async check methods, evaluate_async, evaluate_all_async |
| `src/squadops/cycles/pulse_models.py` | 1 | CadencePolicy, PulseCheckDefinition, PulseVerificationRecord, parse_pulse_checks() |
| `src/squadops/cycles/pulse_verification.py` | 2 | run_pulse_verification(), resolve_milestone_bindings(), collect_cadence_bound_suites(), repair task builder |
| `src/squadops/cycles/task_plan.py` | — | No changes needed (per D5: no plan-time grouping) |
| `adapters/cycles/distributed_flow_executor.py` | 2,3,4 | Cadence tracking, boundary detection, verification calls, repair loop |
| `src/squadops/ports/cycles/cycle_registry.py` | 1 | record_pulse_verification() abstract method |
| `adapters/cycles/memory_cycle_registry.py` | 1 | Memory implementation |
| `adapters/cycles/postgres_cycle_registry.py` | 1 | Postgres implementation |
| `src/squadops/capabilities/handlers/repair_tasks.py` | 3 | 4 repair handlers |
| `src/squadops/bootstrap/handlers.py` | 3 | Register repair handlers |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | 1 | _APPLIED_DEFAULTS_EXTRA_KEYS |
| `infra/migrations/002_pulse_verification.sql` | 1 | Postgres DDL |

---

## Verification

After each phase, run:
```bash
./scripts/dev/run_new_arch_tests.sh -v
```

After Phase 4 (complete), also:
```bash
# Lint
ruff check . --fix && ruff format .

# Full regression suite should pass with ~199 new tests added
./scripts/dev/run_new_arch_tests.sh -v

# Verify CRP profiles load
python -c "from squadops.contracts.cycle_request_profiles import load_profile; p = load_profile('pulse-check'); print(p.name, len(p.defaults.get('pulse_checks', [])))"
```
