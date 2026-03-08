# SIP-0083: Multi-Run Cycle Orchestration — Implementation Plan

**SIP:** `sips/accepted/SIP-0083-Multi-Run-Cycle-Orchestration.md`
**Branch:** `feature/sip-0083-multi-run-cycle-orchestration`

## Phase 1: Prerequisite Fix + Port + Events

### 1a. Fix `_handle_gate()` (standalone PR candidate)

**File:** `adapters/cycles/distributed_flow_executor.py`

Current `_handle_gate()` (line 1435) only matches `"approved"` and `"rejected"`. Fix:

```python
# In _handle_gate(), replace the decision matching block:
if decision.decision in (
    GateDecisionValue.APPROVED,
    GateDecisionValue.APPROVED_WITH_REFINEMENTS,
):
    await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)
    self._cycle_event_bus.emit(
        EventType.RUN_RESUMED,
        entity_type="run",
        entity_id=run_id,
        context={"cycle_id": cycle.cycle_id, "run_id": run_id},
        payload={"gate_name": gate_name},
    )
    logger.info("Gate %r %s, resuming run %s", gate_name, decision.decision, run_id)
    return
elif decision.decision == GateDecisionValue.REJECTED:
    raise _ExecutionError(f"Gate {gate_name!r} rejected: {decision.notes}")
elif decision.decision == GateDecisionValue.RETURNED_FOR_REVISION:
    raise _ExecutionError(
        f"Gate {gate_name!r} returned_for_revision: "
        "returned_for_revision requires manual retry-run creation; "
        "automatic retry-in-same-phase is not implemented in this version."
    )
```

Import `GateDecisionValue` from `squadops.cycles.models` (already imported in the file via `from squadops.cycles.models import ...`; add `GateDecisionValue` to the existing import).

**Tests:** `tests/unit/cycles/test_handle_gate_decisions.py`
- `approved` resumes run (existing behavior, re-verify)
- `approved_with_refinements` resumes run
- `rejected` raises `_ExecutionError`
- `returned_for_revision` raises `_ExecutionError` with descriptive message
- No decision value causes indefinite polling

### 1b. Add `execute_cycle()` to `FlowExecutionPort`

**File:** `src/squadops/ports/cycles/flow_execution.py`

Add non-abstract method after `cancel_run()`:

```python
async def execute_cycle(
    self, cycle_id: str, first_run_id: str, profile_id: str | None = None
) -> None:
    """Execute a full cycle by iterating over workload_sequence.

    Default implementation delegates to execute_run() for backward
    compatibility with executors that do not support multi-workload
    orchestration. execute_cycle() accepts the already-created first Run
    so cycle creation semantics remain unchanged and the executor can
    begin orchestration from the initial persisted Run.
    """
    await self.execute_run(cycle_id, first_run_id, profile_id)
```

**Tests:** `tests/unit/ports/test_flow_execution_default.py`
- Default `execute_cycle()` calls `execute_run()` with same args
- Subclass that overrides `execute_cycle()` does not call default

### 1c. Add 3 workload event types

**File:** `src/squadops/events/types.py`

Add after the Correction section:

```python
    # --- Workload (3) — SIP-0083 ---
    WORKLOAD_COMPLETED = "workload.completed"
    WORKLOAD_GATE_AWAITING = "workload.gate_awaiting"
    WORKLOAD_ADVANCED = "workload.advanced"
```

Update module docstring: `25 event types` → `28 event types across 9 entity types`.
Update `all()` docstring: `25 event type constants` → `28 event type constants`.

**File:** `tests/unit/events/test_event_emission.py`

Update event type count assertion from `== 25` to `== 28`. Update total emit count assertion to reflect new workload emit calls after Phase 2 is complete (do not hardcode a guess — count actual `self._cycle_event_bus.emit(` calls in `distributed_flow_executor.py` after implementation).

**Tests:** `tests/unit/events/test_workload_events.py`
- All 3 constants exist on `EventType`
- Values follow `workload.{transition}` format
- Included in `EventType.all()`

---

## Phase 2: Executor Orchestration Loop

**File:** `adapters/cycles/distributed_flow_executor.py`

### Core assumption

`execute_cycle()` assumes `execute_run()` returns only after the run has reached a terminal or gate-resolved state suitable for workload progression checks. This is true of the current `execute_run()` implementation, which runs to completion/failure/cancellation before returning. If `execute_run()` semantics ever change to return early (e.g., fire-and-forget), the orchestration loop would need a separate terminal-state poll.

### Implementation

Override `execute_cycle()` in `DistributedFlowExecutor`:

```python
async def execute_cycle(
    self, cycle_id: str, first_run_id: str, profile_id: str | None = None
) -> None:
    """Execute a full cycle by iterating over workload_sequence.

    Assumes execute_run() returns only after the run reaches a terminal
    state (completed, failed, cancelled). Decision semantics for inter-
    workload gates are interpreted here, not in the polling helper.
    """
    cycle = await self._cycle_registry.get_cycle(cycle_id)
    workload_sequence = cycle.applied_defaults.get("workload_sequence", [])

    # Single-workload fast path (D7)
    if len(workload_sequence) <= 1:
        await self.execute_run(cycle_id, first_run_id, profile_id)
        return

    current_run_id = first_run_id
    for i, workload_entry in enumerate(workload_sequence):
        await self.execute_run(cycle_id, current_run_id, profile_id)

        # Check terminal status (compare persisted string values)
        run = await self._cycle_registry.get_run(current_run_id)
        if run.status in (RunStatus.FAILED.value, RunStatus.CANCELLED.value):
            self._cycle_event_bus.emit(
                EventType.WORKLOAD_COMPLETED,
                entity_type="workload",
                entity_id=current_run_id,
                context={"cycle_id": cycle_id, "run_id": current_run_id},
                payload={
                    "workload_type": workload_entry.get("type"),
                    "terminal_status": run.status,
                },
            )
            break

        self._cycle_event_bus.emit(
            EventType.WORKLOAD_COMPLETED,
            entity_type="workload",
            entity_id=current_run_id,
            context={"cycle_id": cycle_id, "run_id": current_run_id},
            payload={
                "workload_type": workload_entry.get("type"),
                "terminal_status": RunStatus.COMPLETED.value,
            },
        )

        # Last workload — done
        if i >= len(workload_sequence) - 1:
            break

        # Inter-workload gate
        gate_name = workload_entry.get("gate")
        if gate_name:
            self._cycle_event_bus.emit(
                EventType.WORKLOAD_GATE_AWAITING,
                entity_type="workload",
                entity_id=current_run_id,
                context={"cycle_id": cycle_id, "run_id": current_run_id},
                payload={"gate_name": gate_name},
            )
            decision = await self._poll_inter_workload_gate(
                current_run_id, cycle, gate_name,
            )

            if decision.decision == GateDecisionValue.REJECTED:
                break  # Run stays COMPLETED; rejection in gate_decisions

            # approved_with_refinements artifact writing (Phase 3)

        # Positional duplicate guard (D14).
        # Assumes runs are created in sequence order by this orchestration
        # loop and no out-of-band run creation targets the same position.
        next_workload = workload_sequence[i + 1]
        all_runs = await self._cycle_registry.list_runs(cycle_id)
        non_cancelled = sorted(
            [r for r in all_runs if r.status != RunStatus.CANCELLED.value],
            key=lambda r: r.run_number,
        )

        if len(non_cancelled) > i + 1:
            current_run_id = non_cancelled[i + 1].run_id
        else:
            next_run = await self._create_next_workload_run(
                cycle, run, next_workload,
                config_hash=run.resolved_config_hash,
            )
            current_run_id = next_run.run_id

        self._cycle_event_bus.emit(
            EventType.WORKLOAD_ADVANCED,
            entity_type="workload",
            entity_id=current_run_id,
            context={"cycle_id": cycle_id, "run_id": current_run_id},
            payload={"workload_type": next_workload.get("type")},
        )
```

### Helper: `_poll_inter_workload_gate()`

Polls until it finds a decision for the named gate. Does not interpret the decision — `execute_cycle()` owns decision semantics. The run is already COMPLETED (not PAUSED), so run status is not changed.

```python
async def _poll_inter_workload_gate(
    self, run_id: str, cycle: Cycle, gate_name: str
) -> GateDecision:
    """Poll for and return the inter-workload gate decision on a completed run.

    Decision semantics (approved, rejected, etc.) are interpreted by
    execute_cycle(), not here. This helper only waits for any decision
    to appear on the named gate.
    """
    poll_interval = 2.0
    while True:
        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)
        run = await self._cycle_registry.get_run(run_id)
        for decision in run.gate_decisions:
            if decision.gate_name == gate_name:
                return decision
        await asyncio.sleep(poll_interval)
```

### Helper: `_create_next_workload_run()`

The `Run` frozen dataclass requires these fields. All optional fields default to `None`/`()`:

```python
async def _create_next_workload_run(
    self, cycle: Cycle, completed_run: Run, workload_entry: dict,
    config_hash: str,
) -> Run:
    """Create the next workload Run with forwarded overrides."""
    all_runs = await self._cycle_registry.list_runs(cycle.cycle_id)
    next_number = max(r.run_number for r in all_runs) + 1

    # Build forwarding overrides (Phase 3 adds artifact forwarding)
    execution_overrides = dict(cycle.execution_overrides)

    next_run = Run(
        run_id=f"run_{uuid4().hex[:12]}",
        cycle_id=cycle.cycle_id,
        run_number=next_number,
        status=RunStatus.QUEUED.value,
        initiated_by="system",
        resolved_config_hash=config_hash,
        workload_type=workload_entry.get("type"),
    )
    return await self._cycle_registry.create_run(next_run)
```

**Tests:** `tests/unit/cycles/test_execute_cycle.py`

Key test cases:
- Single-workload fast path delegates to `execute_run()` directly
- Multi-workload (2 entries) creates second Run after first completes
- Multi-workload (3 entries) creates all Runs sequentially
- Failed run stops orchestration (no next Run created)
- Cancelled run stops orchestration
- `approved` gate advances to next workload
- `rejected` gate stops orchestration; run stays COMPLETED
- Positional duplicate guard: existing next run is reused, not re-created
- Event emission: `WORKLOAD_COMPLETED`, `WORKLOAD_GATE_AWAITING`, `WORKLOAD_ADVANCED` at correct points
- `WORKLOAD_COMPLETED` payload includes `terminal_status` even for failed/cancelled outcomes
- Missing `workload_sequence` key → delegates to `execute_run()`
- Empty `workload_sequence` list → delegates to `execute_run()`

Test strategy: mock `self._cycle_registry` and `self._cycle_event_bus`. Patch `execute_run` on the executor instance to track calls without actually dispatching tasks.

---

## Phase 3: Refinement Artifact + Forwarding

### 3a. `approved_with_refinements` artifact writing

In `execute_cycle()`, after the gate decision check for `rejected`, add:

```python
if decision.decision == GateDecisionValue.APPROVED_WITH_REFINEMENTS:
    if decision.notes:
        artifact_content = f"# Refinement Notes\n\n{decision.notes}\n"
        artifact_ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            run_id=current_run_id,
            artifact_type="document",
            filename="refinement_notes.md",
            content_hash=sha256(artifact_content.encode()).hexdigest(),
            size_bytes=len(artifact_content.encode()),
            media_type="text/markdown",
            created_at=datetime.now(UTC),
            metadata={"producing_task_type": "gate.refinement_notes"},
        )
        await self._artifact_vault.store_artifact(
            artifact_ref, artifact_content.encode()
        )
```

**Artifact registration:** `store_artifact()` both persists the content and registers the `ArtifactRef` in the vault index. Verify this during implementation by checking the `ArtifactVaultPort.store_artifact()` contract and the filesystem adapter's implementation. If `store_artifact()` does not register the ref on the run's `artifact_refs` tuple in the registry, a separate `update_run` call would be needed to append the artifact_id — but based on the existing executor pattern (which calls `store_artifact` and expects artifacts to appear in `list_artifacts`), this should be sufficient.

### 3b. Artifact forwarding in `_create_next_workload_run()`

Build `execution_overrides` from the completed run's artifacts:

```python
async def _build_forwarding_overrides(
    self, cycle: Cycle, completed_run: Run,
) -> dict:
    """Build execution_overrides with artifact refs from the completed run.

    Forwarded artifact lists are sorted by creation time for deterministic
    ordering. Operator-supplied overrides in cycle.execution_overrides
    always take precedence.

    Merge semantics:
    - List keys (plan_artifact_refs, prior_workload_artifact_refs):
      merge with existing values, deduplicate.
    - Scalar keys (impl_run_id): only write when no explicit override exists.
    """
    overrides = dict(cycle.execution_overrides)  # Start from cycle-level overrides

    # promoted artifacts only — empty list if nothing promoted (D9, §5.6 rule 6)
    promoted = await self._artifact_vault.list_artifacts(
        run_id=completed_run.run_id, promotion_status="promoted",
    )
    promoted_refs = [a.artifact_id for a in sorted(promoted, key=lambda a: a.created_at)]
    if "prior_workload_artifact_refs" in overrides:
        # Merge with existing, deduplicate
        existing = overrides["prior_workload_artifact_refs"]
        seen = set(existing)
        merged = list(existing) + [r for r in promoted_refs if r not in seen]
        overrides["prior_workload_artifact_refs"] = merged
    else:
        overrides["prior_workload_artifact_refs"] = promoted_refs

    # workload-type-specific keys
    wt = completed_run.workload_type
    if wt == "planning":
        # For v1, plan_artifact_refs forwards promoted planning documents
        # from the immediately preceding planning run.
        plan_docs = await self._artifact_vault.list_artifacts(
            run_id=completed_run.run_id,
            artifact_type="document",
            promotion_status="promoted",
        )
        plan_refs = [a.artifact_id for a in sorted(plan_docs, key=lambda a: a.created_at)]
        if "plan_artifact_refs" in overrides:
            existing = overrides["plan_artifact_refs"]
            seen = set(existing)
            merged = list(existing) + [r for r in plan_refs if r not in seen]
            overrides["plan_artifact_refs"] = merged
        else:
            overrides["plan_artifact_refs"] = plan_refs
    elif wt == "implementation":
        # Scalar key — only write when no explicit override exists
        if "impl_run_id" not in overrides:
            overrides["impl_run_id"] = completed_run.run_id

    return overrides
```

Wire into `_create_next_workload_run()` — replace `execution_overrides = dict(cycle.execution_overrides)` with a call to `_build_forwarding_overrides()`.

**Tests:** additions to `tests/unit/cycles/test_execute_cycle.py`
- `approved_with_refinements` writes `refinement_notes.md` artifact via `store_artifact()`
- `approved_with_refinements` with empty/None notes does not write artifact
- `approved_with_refinements` does not alter `workload_progress` status — the workload still appears as `completed`
- Planning → implementation forwards `plan_artifact_refs` (promoted documents only)
- Implementation → wrapup forwards `impl_run_id`
- Promoted artifacts forwarded as `prior_workload_artifact_refs`
- No promoted artifacts → empty list (not all artifacts)
- Explicit operator override for scalar key (`impl_run_id`) is not overwritten
- Explicit operator override for list key (`plan_artifact_refs`) is merged with forwarded refs, deduplicated
- Forwarded artifact lists are sorted by creation time

---

## Phase 4: API Integration + DTO + Profile

### 4a. API route change

**File:** `src/squadops/api/routes/cycles/cycles.py` line 124-128

```python
# Change:
background_tasks.add_task(
    flow_executor.execute_run,
    cycle.cycle_id,
    run.run_id,
    body.squad_profile_id,
)
# To:
background_tasks.add_task(
    flow_executor.execute_cycle,
    cycle.cycle_id,
    run.run_id,
    body.squad_profile_id,
)
```

### 4b. WorkloadProgressEntry DTO

**File:** `src/squadops/api/routes/cycles/dtos.py`

Add before `CycleResponse`:

```python
class WorkloadProgressEntry(BaseModel):
    index: int
    workload_type: str
    run_id: str | None = None
    status: str  # "pending" | "running" | "completed" | "failed" | "gate_awaiting" | "rejected"
```

Add field to `CycleResponse`:

```python
class CycleResponse(BaseModel):
    # ... existing fields ...
    workload_progress: list[WorkloadProgressEntry] = Field(default_factory=list)
```

### 4c. Compute workload_progress

**File:** `src/squadops/api/routes/cycles/cycles.py` — in the `get_cycle` route where `CycleResponse` is constructed.

Add a helper function. This maps domain run statuses into the DTO vocabulary explicitly rather than passing through raw status strings:

```python
_RUN_STATUS_TO_PROGRESS: dict[str, str] = {
    RunStatus.QUEUED.value: "pending",
    RunStatus.RUNNING.value: "running",
    RunStatus.PAUSED.value: "gate_awaiting",
    RunStatus.COMPLETED.value: "completed",
    RunStatus.FAILED.value: "failed",
    # CANCELLED excluded from alignment, never reaches this map
}


def _compute_workload_progress(
    workload_sequence: list[dict], runs: list[Run],
) -> list[WorkloadProgressEntry]:
    """Derive workload_progress by positional alignment (SIP-0083 §5.8).

    Non-cancelled runs are sorted by run_number and aligned to
    workload_sequence entries positionally. Domain run statuses are
    mapped to the DTO vocabulary; raw status values are never passed
    through.
    """
    non_cancelled = sorted(
        [r for r in runs if r.status != RunStatus.CANCELLED.value],
        key=lambda r: r.run_number,
    )
    entries = []
    for i, ws_entry in enumerate(workload_sequence):
        if i < len(non_cancelled):
            run = non_cancelled[i]
            # Check for rejected gate decision on this workload's gate
            gate_name = ws_entry.get("gate")
            rejected = gate_name and any(
                gd.decision == GateDecisionValue.REJECTED
                for gd in run.gate_decisions
                if gd.gate_name == gate_name
            )
            if rejected:
                status = "rejected"
            else:
                status = _RUN_STATUS_TO_PROGRESS.get(run.status, run.status)
            entries.append(WorkloadProgressEntry(
                index=i,
                workload_type=ws_entry.get("type", "unknown"),
                run_id=run.run_id,
                status=status,
            ))
        else:
            entries.append(WorkloadProgressEntry(
                index=i,
                workload_type=ws_entry.get("type", "unknown"),
                run_id=None,
                status="pending",
            ))
    return entries
```

### 4d. Update multi-phase.yaml

**File:** `src/squadops/contracts/cycle_request_profiles/profiles/multi-phase.yaml`

Replace with functional 3-workload profile per SIP §5.11. Add `progress_impl_review` gate, update `workload_sequence` to include `wrapup`, add `after_task_types` to `progress_plan_review`.

**Compatibility checkpoint:** before committing, verify no existing tests, CLI examples, or docs reference the prior `multi-phase.yaml` shape (2-workload, no `progress_impl_review`). Search for `multi-phase` across tests and docs.

### 4e. Tests

**File:** `tests/unit/api/routes/cycles/test_workload_progress.py`
- Empty `workload_sequence` → empty `workload_progress`
- 3-entry sequence with 1 completed run → first entry has run_id/completed, others pending
- All runs completed → all entries have run_ids and `completed` status
- Cancelled run excluded from positional alignment
- Rejected gate → status is `"rejected"` (not raw run status)
- Paused run → status is `"gate_awaiting"` (not `"paused"`)
- Queued run → status is `"pending"` (not `"queued"`)
- Running run → status is `"running"`
- `approved_with_refinements` gate does not change workload_progress status (still `completed`)

**File:** `tests/unit/contracts/test_multi_phase_profile.py`
- Profile loads without validation errors
- Has 3 workload_sequence entries (planning, implementation, wrapup)
- Has 2 gates (progress_plan_review, progress_impl_review)

---

## Phase 5: E2E Validation

- **Happy path:** create cycle with `multi-phase` profile, approve planning gate, verify implementation Run is auto-created
- **Negative path:** create cycle with `multi-phase` profile, reject planning gate, verify no implementation Run is created and orchestration stops
- Verify `cycles show` displays `workload_progress`
- Verify `artifacts list` shows `refinement_notes.md` when `approved_with_refinements` is used

---

## Test Emission Count Update

After all phases, update `tests/unit/events/test_event_emission.py`:
- Event type count: `25` → `28`
- Total emit count: update to reflect actual executor emit calls (count `self._cycle_event_bus.emit(` in `distributed_flow_executor.py` after implementation — do not guess the number in advance)

---

## Key Implementation Notes

1. **`list_runs()` has no `exclude_cancelled` param** — filter in Python: `[r for r in runs if r.status != RunStatus.CANCELLED.value]`
2. **`create_run()` takes a `Run` domain object**, not keyword args — construct the full frozen dataclass. Required fields: `run_id`, `cycle_id`, `run_number`, `status`, `initiated_by`, `resolved_config_hash`. Optional: `resolved_config_ref`, `started_at`, `finished_at`, `gate_decisions`, `artifact_refs`, `workload_type`.
3. **Run IDs**: use `f"run_{uuid4().hex[:12]}"` pattern (matches route)
4. **`initiated_by`**: use `"system"` for orchestration-created runs (vs `"api"` for route-created)
5. **Import `GateDecisionValue`** in the executor — add to existing `from squadops.cycles.models import ...` line
6. **`_poll_inter_workload_gate()` does NOT change run status and does NOT interpret decisions** — the run is already COMPLETED (not PAUSED like intra-run gates); `execute_cycle()` owns decision semantics
7. **Artifact forwarding merge semantics:** list-valued keys merge with existing values and deduplicate; scalar keys only write when no explicit override exists
8. **Deterministic artifact ordering:** sort forwarded artifact lists by `created_at` before writing to `execution_overrides`. Verify `list_artifacts()` return order; if not stable, sort explicitly.
9. **Status comparison:** executor logic compares persisted string values (e.g., `run.status == RunStatus.FAILED.value`). DTO mapping normalizes to the `workload_progress` vocabulary separately. Do not mix enum members and raw strings in the same comparison.
10. **`workload_sequence` entry access:** use `.get("type")` defensively. Profile contract guarantees `type` key, but `.get()` is safer against malformed data.
11. **Duplicate-next-run guard assumption:** runs are created in sequence order by this orchestration loop. No out-of-band run creation targets the same sequence position during normal operation.
