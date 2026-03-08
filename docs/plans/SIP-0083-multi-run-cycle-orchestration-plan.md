# SIP-0083: Multi-Run Cycle Orchestration — Implementation Plan (Rev 2)

**SIP:** `sips/accepted/SIP-0083-Multi-Run-Cycle-Orchestration.md` (Rev 4)
**Branch:** `feature/sip-0083-multi-run-cycle-orchestration`
**PR:** #28

---

## Completed Phases

Phases 1–5 and a Prefect dedup hotfix are committed on the feature branch.

| Phase | Commit(s) | Summary |
|-------|-----------|---------|
| 1a | `_handle_gate()` fix | All 4 `GateDecisionValue` values handled; `returned_for_revision` fails run with descriptive error |
| 1b | Port method | `execute_cycle()` on `FlowExecutionPort` with default fallback to `execute_run()` |
| 1c | Event types | 3 workload event types (`workload.completed`, `workload.gate_awaiting`, `workload.advanced`) |
| 2 | Executor loop | `execute_cycle()` in `DistributedFlowExecutor`: workload loop, gate polling, duplicate guard |
| 3 | Refinement + forwarding | `approved_with_refinements` artifact writing, `_build_forwarding_overrides()` |
| 4 | API + DTO + profile | `execute_run` → `execute_cycle`, `WorkloadProgressEntry`, `_compute_workload_progress()`, multi-phase.yaml |
| 5 | CLI + version bump | `--request-profile` flag, version 0.9.19 |
| Hotfix | `9007830` | Removed direct Prefect task calls from repair dispatch path; PrefectBridge exclusively manages task runs via events |

---

## E2E Bug Discovery (SIP Rev 4 Motivation)

E2E testing of the multi-phase profile revealed two inter-related bugs that prevent inter-workload gate decisions from working:

1. **`record_gate_decision()` rejects COMPLETED runs.** The guard uses `TERMINAL_STATES` (`{COMPLETED, FAILED, CANCELLED}`), but inter-workload gate decisions are by definition recorded against completed runs — the run whose artifacts are being reviewed (D2).

2. **`derive_cycle_status()` shows COMPLETED during gate polling.** The latest non-cancelled run is completed, so `derive_cycle_status()` returns `COMPLETED`. But the cycle is actually waiting for human input at an inter-workload gate. Operators and automation treating `COMPLETED` as "done" is dangerous.

These were addressed in SIP-0083 Rev 4 with design decisions D5 (revised), D15, D16. The following phase implements them.

---

## Phase 6: Cycle Status + Gate Guard Corrections

### Runtime Contracts

**P6-RC1 (Run stays COMPLETED):** A run is `COMPLETED` when its tasks and gates finish. Inter-workload gate decisions do not change run status. The gate decision is recorded on the completed run; the cycle-level status reflects the suspension.

**P6-RC2 (Cycle PAUSED is resolved, not stored):** `CycleStatus.PAUSED` is produced by `resolve_cycle_status()` at query time based on `workload_progress`. It is never written directly to the cycle model or database.

**P6-RC3 (GATE_REJECTED_STATES scope):** Only `record_gate_decision()` switches from `TERMINAL_STATES` to `GATE_REJECTED_STATES`. Other `TERMINAL_STATES` uses (`update_run_status` finished_at logic, `record_pulse_verification` guard) remain unchanged — those correctly reject operations on completed runs.

**P6-RC4 (derive_cycle_status backward compat):** `derive_cycle_status()` is preserved unchanged with its full test suite. Existing tests must not be modified or deleted. `resolve_cycle_status()` composes on top of it.

### 6a. Add `CycleStatus.PAUSED`

**File:** `src/squadops/cycles/models.py`

Add `PAUSED` to `CycleStatus` enum:

```python
class CycleStatus(StrEnum):
    """Cycle lifecycle status (derived from latest Run). SIP-0064 §6.1."""

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"      # SIP-0083 D16: waiting for human input at inter-workload gate
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**No tests needed** — `CycleStatus` is a simple enum. Testing that enum members equal their hardcoded values is tautological (CLAUDE.md test standard).

### 6b. Add `GATE_REJECTED_STATES` and `resolve_cycle_status()`

**File:** `src/squadops/cycles/lifecycle.py`

Add after `TERMINAL_STATES`:

```python
# States that reject gate decisions — COMPLETED is intentionally excluded
# because inter-workload gates are decided on completed runs (SIP-0083 D15).
GATE_REJECTED_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.FAILED, RunStatus.CANCELLED}
)
```

Add after `derive_cycle_status()`:

```python
def resolve_cycle_status(
    runs: Sequence[Run],
    cycle_cancelled: bool,
    workload_progress: Sequence | None = None,
) -> CycleStatus:
    """Resolve cycle status with workload awareness (SIP-0083 D5).

    Composes on top of derive_cycle_status():
    - If any workload_progress entry has status "gate_awaiting" → PAUSED
    - If any workload_progress entry has status "rejected" → FAILED
    - Otherwise → derive_cycle_status(runs, cycle_cancelled)

    When workload_progress is None or empty, this is equivalent to
    derive_cycle_status() — preserving backward compatibility for
    single-workload cycles.
    """
    if workload_progress:
        for entry in workload_progress:
            status = entry.status if hasattr(entry, "status") else entry.get("status")
            if status == "gate_awaiting":
                return CycleStatus.PAUSED
            if status == "rejected":
                return CycleStatus.FAILED

    return derive_cycle_status(runs, cycle_cancelled)
```

**Design note on the `workload_progress` parameter type:** The function accepts `Sequence | None` rather than importing `WorkloadProgressEntry` from `dtos.py`. This avoids a circular dependency between the domain layer (`cycles/lifecycle.py`) and the API layer (`api/routes/cycles/dtos.py`). It uses duck typing — any object with a `.status` attribute or dict with a `"status"` key works. The `hasattr` check supports both DTO instances and plain dicts, which is useful for testing.

**File:** `src/squadops/cycles/__init__.py`

Add to imports and `__all__`:

```python
from squadops.cycles.lifecycle import (
    GATE_REJECTED_STATES,
    compute_config_hash,
    compute_profile_snapshot_hash,
    derive_cycle_status,
    resolve_cycle_status,
    validate_run_transition,
)

__all__ = [
    # ...existing...
    # Lifecycle
    "validate_run_transition",
    "derive_cycle_status",
    "resolve_cycle_status",
    "compute_config_hash",
    "compute_profile_snapshot_hash",
    # Constants
    "GATE_REJECTED_STATES",
]
```

**Tests:** `tests/unit/cycles/test_lifecycle.py`

New class `TestResolveCycleStatus`:

| Test | What bug would this catch? |
|------|---------------------------|
| `test_no_workload_progress_delegates_to_derive` | `resolve_cycle_status` with `workload_progress=None` must match `derive_cycle_status` — ensures backward compat |
| `test_empty_workload_progress_delegates_to_derive` | Same, with empty list |
| `test_gate_awaiting_returns_paused` | Cycle at inter-workload gate must show PAUSED, not COMPLETED |
| `test_rejected_returns_failed` | Rejected gate must show FAILED, not COMPLETED |
| `test_gate_awaiting_takes_precedence_over_rejected` | If both exist (shouldn't happen, but defensive), PAUSED wins |
| `test_completed_without_gate_awaiting_stays_completed` | Cycle with completed workloads and no pending gates stays COMPLETED |
| `test_running_workload_stays_active` | Mid-workload execution shows ACTIVE via derive_cycle_status |
| `test_accepts_dict_workload_progress` | Duck typing: plain dicts with `"status"` key work |

New tests for `GATE_REJECTED_STATES`:

| Test | What bug would this catch? |
|------|---------------------------|
| `test_gate_rejected_states_excludes_completed` | `COMPLETED` NOT in `GATE_REJECTED_STATES` — core invariant of D15 |
| `test_gate_rejected_states_includes_failed_and_cancelled` | Both terminal-for-gates states included |

### 6c. Narrow gate decision guard in registries

**File:** `adapters/cycles/postgres_cycle_registry.py`

Line 16 — update import:
```python
from squadops.cycles.lifecycle import GATE_REJECTED_STATES, TERMINAL_STATES, derive_cycle_status, validate_run_transition
```

Line 289 — change guard:
```python
# Before:
if RunStatus(run_row["status"]) in TERMINAL_STATES:

# After:
if RunStatus(run_row["status"]) in GATE_REJECTED_STATES:
```

**File:** `adapters/cycles/memory_cycle_registry.py`

Line 12 — update import:
```python
from squadops.cycles.lifecycle import GATE_REJECTED_STATES, TERMINAL_STATES, validate_run_transition
```

Line 153 — change guard:
```python
# Before:
if current_status in TERMINAL_STATES:

# After:
if current_status in GATE_REJECTED_STATES:
```

**Important (P6-RC3):** Do NOT change the `TERMINAL_STATES` usage at:
- `postgres_cycle_registry.py` line 235 (`update_run_status` finished_at logic)
- `postgres_cycle_registry.py` line 355 (`record_pulse_verification` guard)
- `memory_cycle_registry.py` line 192 (`record_pulse_verification` guard)

These correctly use `TERMINAL_STATES` for their own purposes.

**Tests:** updates to existing files

`tests/unit/cycles/test_postgres_cycle_registry.py` — update `test_record_gate_decision_terminal_run_raises` (line 539):
- Rename to `test_record_gate_decision_failed_run_raises`
- Assert that `FAILED` runs still reject gate decisions
- Add `test_record_gate_decision_cancelled_run_raises`
- Add `test_record_gate_decision_completed_run_accepts` — COMPLETED runs now accept gate decisions (D15)

`tests/unit/cycles/test_adapters.py` — update the memory registry gate decision terminal test (line 351):
- Same pattern: FAILED/CANCELLED raise `RunTerminalError`, COMPLETED accepts

`tests/unit/cycles/test_cycle_registry_contract.py` — update if it tests terminal-state gate rejection:
- Add test that COMPLETED runs accept gate decisions

`tests/unit/cycles/test_gate_boundary_status.py` — verify line 119 (which tests gate decision rejection on a completed run):
- This test asserts `RunTerminalError` on a COMPLETED run — it must be updated to expect success

### 6d. Switch callers from `derive_cycle_status` to `resolve_cycle_status`

Four call sites need updating. Each needs `workload_progress` computed before resolving status.

**File:** `src/squadops/api/routes/cycles/mapping.py`

`cycle_to_response()` (line 135) — this is the central mapping function. Currently receives `status: str` as a parameter. Change to compute status internally:

```python
def cycle_to_response(cycle: Cycle, runs: list[Run]) -> CycleResponse:
    ws = cycle.applied_defaults.get("workload_sequence", [])
    progress = _compute_workload_progress(ws, runs)
    status = resolve_cycle_status(runs, cycle_cancelled=False, workload_progress=progress)
    return CycleResponse(
        # ...existing fields...
        status=status.value,
        runs=[run_to_response(r) for r in runs],
        workload_progress=progress,
    )
```

This removes the `status` parameter from `cycle_to_response()` — the function now owns status resolution. Callers simplify.

**File:** `src/squadops/api/routes/cycles/cycles.py`

Three call sites:

1. `list_cycles` (line 157–158):
```python
# Before:
derived = derive_cycle_status(runs, cycle_cancelled=False)
results.append(cycle_to_response(c, runs, derived.value))

# After:
results.append(cycle_to_response(c, runs))
```

2. `get_cycle` (line 172–173):
```python
# Before:
derived = derive_cycle_status(runs, cycle_cancelled=False)
return cycle_to_response(cycle, runs, derived.value)

# After:
return cycle_to_response(cycle, runs)
```

3. Import line 13 — remove `derive_cycle_status` (no longer needed here).

**File:** `src/squadops/api/routes/cycles/runs.py`

Line 195 — the resume route checks parent cycle status:
```python
# Before:
cycle_status = derive_cycle_status(runs, False)

# After:
from squadops.api.routes.cycles.mapping import _compute_workload_progress
cycle = await registry.get_cycle(cycle_id)
ws = cycle.applied_defaults.get("workload_sequence", [])
progress = _compute_workload_progress(ws, runs)
cycle_status = resolve_cycle_status(runs, False, workload_progress=progress)
```

Update import line 17 — switch from `derive_cycle_status` to `resolve_cycle_status`.

**Note on `CycleStatus.PAUSED` in the resume guard (line 196):** The current check rejects resume when cycle is `COMPLETED` or `CANCELLED`. A `PAUSED` cycle should allow run resume (the operator is making progress on the pipeline), so the existing guard `if cycle_status in (CycleStatus.COMPLETED, CycleStatus.CANCELLED)` remains correct without modification.

**Tests:** updates to existing API test files

`tests/unit/cycles/test_api_cycles.py` (or wherever `list_cycles`/`get_cycle` are tested):
- Update `cycle_to_response()` call signatures to remove the `status` parameter
- Verify that `workload_progress` with `gate_awaiting` produces `status: "paused"` on the response

`tests/unit/api/routes/cycles/test_workload_progress.py`:
- Add `test_gate_awaiting_produces_paused_cycle_status` — cycle response shows `status: "paused"` when a workload is `gate_awaiting`
- Add `test_rejected_produces_failed_cycle_status` — cycle response shows `status: "failed"` when a workload is `rejected`

### 6e. Commit and regression

1. Run `ruff check . --fix && ruff format .`
2. Run `./scripts/dev/run_regression_tests.sh -v`
3. Verify all existing `derive_cycle_status` tests still pass unchanged (P6-RC4)
4. Commit with message referencing D5, D15, D16

---

## Phase 7: E2E Revalidation

After Phase 6, rebuild and retest the multi-phase cycle flow that failed in the previous E2E attempt.

### Steps

1. Rebuild runtime-api and all agents:
   ```bash
   ./scripts/dev/ops/rebuild_and_deploy.sh all
   ```

2. Create multi-phase cycle:
   ```bash
   squadops cycles create play_game --squad-profile full-squad --request-profile multi-phase
   ```

3. Monitor planning workload in Prefect UI (`http://localhost:4200`)

4. After planning completes, verify:
   - `squadops cycles show <cycle-id>` shows `status: paused` (not `completed`)
   - `workload_progress[0]` shows `status: gate_awaiting` (planning run is completed with gate pending)
   - `workload_progress[1]` and `[2]` show `status: pending`

5. Approve the planning gate:
   ```bash
   squadops runs gate <run-id> progress_plan_review --approve
   ```

6. Verify orchestration advances:
   - New implementation run is auto-created
   - `squadops cycles show <cycle-id>` shows `status: active`
   - `workload_progress[0]` shows `status: completed`
   - `workload_progress[1]` shows `status: running`

7. After implementation completes, verify second gate:
   - `status: paused` again
   - Approve `progress_impl_review` gate
   - Wrapup workload starts

8. After wrapup completes:
   - `status: completed`
   - All 3 `workload_progress` entries show `status: completed`

### Negative path

- Create another multi-phase cycle
- After planning completes, reject the gate:
  ```bash
  squadops runs gate <run-id> progress_plan_review --reject --notes "Planning insufficient"
  ```
- Verify `status: failed` and `workload_progress[0].status: rejected`
- Verify no implementation run was created

---

## Key Implementation Notes

1. **`GATE_REJECTED_STATES` vs `TERMINAL_STATES` scope** — only `record_gate_decision()` switches guards. `update_run_status` (finished_at logic) and `record_pulse_verification` continue using `TERMINAL_STATES`. Do not conflate the two (P6-RC3).

2. **`resolve_cycle_status()` parameter type** — uses `Sequence | None` with duck typing to avoid circular imports between domain and API layers. Both `WorkloadProgressEntry` DTOs and plain dicts work.

3. **`cycle_to_response()` signature change** — the `status: str` parameter is removed. The function now internally calls `_compute_workload_progress()` then `resolve_cycle_status()`. All callers simplify.

4. **`cycle_cancelled` parameter** — currently hardcoded to `False` at all call sites (cancel logic uses a different path). This is existing behavior; no change needed.

5. **Test updates scope** — gate decision terminal-run tests in postgres registry, memory registry, contract, and boundary tests all need updating to expect COMPLETED runs to accept decisions. Search for `RunTerminalError` combined with `completed` status in test assertions.

6. **No DDL migration** — `CycleStatus.PAUSED` is a domain enum. The DB stores cycle status as a derived string (not a constrained column), so no migration is needed.

7. **`__init__.py` exports** — add `resolve_cycle_status` and `GATE_REJECTED_STATES` to both the import block and `__all__` in `src/squadops/cycles/__init__.py`.

8. **Emission count update** — if Phase 6 adds or removes any `self._cycle_event_bus.emit()` calls (it shouldn't — no executor changes), update `tests/unit/events/test_event_emission.py` accordingly. Current count is 48 emit calls / 38 with payloads.
