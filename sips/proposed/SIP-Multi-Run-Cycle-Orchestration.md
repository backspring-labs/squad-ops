---
title: Multi-Run Cycle Orchestration
status: proposed
authors: SquadOps Architecture
created_at: '2026-03-07'
revision: 3
---
# SIP: Multi-Run Cycle Orchestration

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-03-07
**Revision:** 3

## 1. Abstract

This SIP adds automatic multi-workload orchestration to the cycle execution pipeline. The `workload_sequence` key in cycle request profiles already declares multiple workloads (e.g., planning → implementation → wrapup) with inter-workload gates, but nothing in the executor iterates over it. Today the API creates a single Run for `workload_sequence[0]` and stops — running a full pipeline requires 3 separate manual cycle creations, breaking the design intent.

This SIP introduces `execute_cycle()` on `FlowExecutionPort`, which wraps `execute_run()` in a loop over `workload_sequence`. Each workload gets its own Run. Inter-workload gates control progression. The API changes one line: `execute_run(...)` → `execute_cycle(...)`.

## 2. Problem Statement

The `workload_sequence` infrastructure exists across multiple SIPs:

- **SIP-0076** defined `WorkloadType` and `workload_sequence` as a cycle request profile key.
- **SIP-0078** defined the planning workload protocol with `progress_plan_review` gates.
- **SIP-0079** defined the implementation workload with correction and contract mechanics.
- **SIP-0080** defined the wrapup workload protocol.

But there is no orchestration layer that connects them. Operators must manually:

1. Create a planning cycle, wait for it to complete, approve the gate.
2. Create a separate implementation cycle, manually wiring `plan_artifact_refs` in `execution_overrides`.
3. Create a separate wrapup cycle, manually wiring `impl_run_id`.

This defeats the purpose of `workload_sequence`. The gap creates operational friction, risks misconfiguration of artifact forwarding, and makes end-to-end pipeline execution unreliable.

## 3. Goals

1. Add `execute_cycle()` to `FlowExecutionPort` that iterates over `workload_sequence`, creating a Run per workload.
2. Handle inter-workload gate decisions (`approved`, `approved_with_refinements`, `rejected`) to control progression.
3. Write refinement notes as a `document` artifact when `approved_with_refinements` is used, making feedback auditable and forward-flowing.
4. Preserve the 1:1 Run ↔ Prefect flow run mapping — each workload gets its own flow run.
5. Provide a single-workload fast path that delegates directly to `execute_run()`.
6. Add `workload_progress` to `CycleResponse` for disambiguation when a cycle has multiple runs.
7. Emit lifecycle events for workload transitions.

## 4. Non-Goals

- **Changing the domain model or DB schema** — multiple Runs per Cycle are already supported.
- **Per-workload `applied_defaults`** — a single cycle-level defaults dict with workload-type-specific keys (`implementation_pulse_checks`, `build_tasks`, etc.) is sufficient.
- **Automatic recovery after process restart** — if the orchestration loop is interrupted, the operator can manually resume. Startup recovery is a future enhancement.
- **Dedicated worker process** — `execute_cycle()` runs as a background task, matching the existing `execute_run()` pattern. Moving to a separate worker is a future SIP.
- **Automatic retry-in-same-phase for `returned_for_revision`** — `returned_for_revision` is accepted by the gate API but is non-resuming in `_handle_gate()` and non-advancing in `execute_cycle()`. It fails the current run with a descriptive error. Automatic retry-in-same-phase is deferred to a follow-on SIP.
- **Changing `derive_cycle_status()`** — existing status derivation from the latest non-cancelled Run remains correct for multi-run cycles.

## 5. Design

### 5.0 Prerequisite: Fix `_handle_gate()` for All Decision Values

The existing `_handle_gate()` in `DistributedFlowExecutor` (line 1435) only recognizes `"approved"` and `"rejected"`. If an operator submits `approved_with_refinements` or `returned_for_revision` via the CLI or API, the gate decision is persisted on the Run but the executor never matches it — the polling loop continues indefinitely.

This is a pre-existing bug (not introduced by this SIP) that must be fixed before multi-workload orchestration can work. The fix is small and scoped to `_handle_gate()`:

```python
# Before (only 2 of 4 values handled):
if decision.decision == "approved":
    ...  # resume
elif decision.decision == "rejected":
    ...  # raise _ExecutionError

# After (3 of 4 values handled; returned_for_revision deferred):
if decision.decision in ("approved", "approved_with_refinements"):
    ...  # resume (refinement notes are informational at intra-run level)
elif decision.decision == "rejected":
    ...  # raise _ExecutionError
elif decision.decision == "returned_for_revision":
    ...  # raise _ExecutionError with descriptive message:
         #   "returned_for_revision requires manual retry-run creation (SIP-0076 §10.5).
         #    Automatic retry-in-same-phase is not yet implemented."
```

At the **intra-run gate** level, `approved_with_refinements` resumes the run — the notes are recorded on the `GateDecision` for auditability but have no distinct executor behavior within a single run. The richer semantics (refinement artifact writing) apply at the **inter-workload gate** level introduced by this SIP.

`returned_for_revision` is accepted by the gate API but is non-resuming in `_handle_gate()` and non-advancing in `execute_cycle()`. In this SIP it fails the current run with a descriptive error. Automatic retry-in-same-phase is deferred to a follow-on SIP.

The error message is standardized and actionable:

    returned_for_revision requires manual retry-run creation; automatic retry-in-same-phase is not implemented in this version.

This tells the operator what happened and what to do next. Silent infinite polling is eliminated.

This fix is included in Phase 1 and should be landed as a standalone PR before the orchestration work begins.

### 5.1 `execute_cycle()` Port Method

A new method on `FlowExecutionPort` with a default implementation that falls back to `execute_run()`:

```python
class FlowExecutionPort(ABC):
    @abstractmethod
    async def execute_run(self, cycle_id: str, run_id: str,
                          profile_id: str | None = None) -> None: ...

    @abstractmethod
    async def cancel_run(self, run_id: str) -> None: ...

    async def execute_cycle(self, cycle_id: str, run_id: str,
                            profile_id: str | None = None) -> None:
        """Execute a full cycle by iterating over workload_sequence.

        Default implementation delegates to execute_run() for backward
        compatibility with executors that do not support multi-workload
        orchestration.
        """
        await self.execute_run(cycle_id, run_id, profile_id)
```

`execute_cycle()` accepts the already-created first Run so cycle creation semantics remain unchanged and the executor can begin orchestration from the initial persisted Run. The default fallback ensures existing executor implementations (tests, in-process executor) continue to work without modification.

### 5.2 Orchestration Loop

`DistributedFlowExecutor.execute_cycle()` implements the multi-workload loop:

```
execute_cycle(cycle_id, first_run_id, profile_id):
    load cycle from registry
    load workload_sequence from cycle.applied_defaults

    if len(workload_sequence) <= 1:
        # Single-workload fast path
        return await execute_run(cycle_id, first_run_id, profile_id)

    current_run_id = first_run_id
    for i, workload_entry in enumerate(workload_sequence):
        # Execute current workload Run
        await execute_run(cycle_id, current_run_id, profile_id)

        # Reload run to check final status
        run = registry.get_run(current_run_id)
        if run.status in (RunStatus.FAILED, RunStatus.CANCELLED):
            emit(workload.completed, status=run.status)
            break  # Orchestration stops; derive_cycle_status() reflects the failed/cancelled run

        emit(workload.completed, status=completed)

        # Last workload — no gate check or next-run creation needed
        if i >= len(workload_sequence) - 1:
            break

        # Check for inter-workload gate
        gate_name = workload_entry.get("gate")
        if gate_name:
            emit(workload.gate_awaiting, gate_name=gate_name)
            decision = await poll_inter_workload_gate(run, gate_name)

            if decision.value == "rejected":
                # Orchestration stops. The completed run's gate_decisions
                # record the rejection. derive_cycle_status() shows COMPLETED
                # for the latest run; workload_progress shows the rejection.
                break

            if decision.value == "approved_with_refinements":
                write_refinement_artifact(run, decision.notes)

            # approved or approved_with_refinements: continue

        # Guard: verify next run does not already exist (idempotency
        # after process restart or duplicate invocation).
        # Check by sequence position: if the cycle already has more
        # non-cancelled runs than the current index, the next run exists.
        next_workload = workload_sequence[i + 1]
        all_runs = registry.list_runs(cycle_id, exclude_cancelled=True)
        if len(all_runs) > i + 1:
            current_run_id = all_runs[i + 1].run_id
        else:
            next_run = registry.create_run(
                cycle_id=cycle_id,
                workload_type=next_workload["type"],
                execution_overrides=build_forwarding_overrides(run),
            )
            current_run_id = next_run.run_id

        emit(workload.advanced, run_id=current_run_id)
```

### 5.3 Inter-Workload Gate Behavior

Three active decision values control inter-workload progression:

| Decision | Behavior |
|----------|----------|
| `approved` | Create next workload Run, proceed |
| `approved_with_refinements` | Write refinement notes as `document` artifact on completed Run (auditable, flows forward via artifact forwarding), then create next Run, proceed |
| `rejected` | Orchestration stops. The Run remains `COMPLETED` (terminal — cannot transition to `FAILED`). The rejection is recorded in `gate_decisions`. `workload_progress` surfaces the rejection; `derive_cycle_status()` shows `COMPLETED` for the latest run. |

`returned_for_revision` is not handled as an inter-workload advancement decision in this SIP. At the intra-run gate level it fails the run (§5.0), and the orchestration loop stops when it observes the failed run. `derive_cycle_status()` reflects the failure. Automatic retry-in-same-phase is deferred to a follow-on SIP.

### 5.4 Gate Polling

Inter-workload gate polling reuses the existing gate polling pattern from `DistributedFlowExecutor.execute_run()`. The executor:

1. Checks if the gate has already been decided (from the Run's `gate_decisions`).
2. If not, sleeps and re-polls at the configured interval.
3. Returns the `GateDecision` when found.

The gate decision is recorded against the **completed Run** — the Run whose artifacts are being reviewed. This is consistent with the existing intra-run gate pattern from SIP-0076.

### 5.5 Refinement Notes Artifact

When `approved_with_refinements` is the inter-workload gate decision, the orchestration loop writes the `notes` field as a `document` artifact on the completed Run:

- **Artifact type:** `document`
- **Filename:** `refinement_notes.md`
- **Producing task type:** `gate.refinement_notes` (synthetic — not from a handler)
- **Content:** The `notes` text from the gate decision, wrapped in a minimal markdown structure

This artifact is stored via the existing `ArtifactVaultPort` and becomes visible in `artifacts list`. It flows to the next workload's handlers via the existing artifact forwarding mechanism in the executor's `_resolve_artifact_inputs()`.

### 5.6 Artifact Forwarding Between Workloads

When creating the next workload's Run, the orchestration loop populates `execution_overrides` with references from the completed Run. The forwarding rules are deterministic and depend on the completed workload type:

| Completed workload | Key | Type | Value |
|--------------------|-----|------|-------|
| `planning` | `plan_artifact_refs` | list | All `document`-type artifact IDs from the completed Run (ordered by creation time) |
| `implementation` | `impl_run_id` | scalar | The completed Run's `run_id` |
| Any | `prior_workload_artifact_refs` | list | All artifact IDs from the completed Run with `promotion_status == "promoted"`. If no artifacts have been promoted, an empty list is written. |

Rules:
1. The orchestration loop calls `ArtifactVaultPort.list_artifacts(run_id=completed_run_id)` once per transition.
2. Filtering is by `artifact_type` and `promotion_status` metadata — not by filename or producing handler.
3. If the vault returns an empty list (no artifacts stored), the key is still written with an empty list (for list-valued keys) or `None` (for scalar keys). The orchestration loop does not fail on missing artifacts — downstream handlers decide whether missing inputs are fatal.
4. **Scalar keys** (e.g., `impl_run_id`): an explicit operator override wins; otherwise the auto-forwarded value is written.
5. **List keys** (e.g., `plan_artifact_refs`, `prior_workload_artifact_refs`): auto-forwarded values are merged with any existing values and deduplicated. Explicit operator overrides take precedence.
6. `prior_workload_artifact_refs` forwards only promoted artifacts. If no artifacts have been promoted, the list is empty — this forces downstream consumers to rely on intentional promotion rather than receiving everything by default.

This replaces the manual wiring operators currently perform.

### 5.7 Single-Workload Fast Path

When `workload_sequence` has 0 or 1 entries (or is absent from `applied_defaults`), `execute_cycle()` delegates directly to `execute_run()` with no overhead. This preserves backward compatibility for all existing cycle request profiles.

### 5.8 Workload Progress DTO

A new field on `CycleResponse` provides visibility into multi-workload progress:

```python
class WorkloadProgressEntry(BaseModel):
    index: int                    # Position in workload_sequence (0-based)
    workload_type: str
    run_id: str | None = None
    status: str  # "pending" | "running" | "completed" | "failed" | "gate_awaiting" | "rejected"

class CycleResponse(BaseModel):
    # ... existing fields ...
    workload_progress: list[WorkloadProgressEntry] = Field(default_factory=list)
```

`workload_progress` is computed at query time from `workload_sequence` and the cycle's Runs. It is not stored.

**Matching algorithm:** `workload_progress` is derived by aligning non-cancelled Runs to `workload_sequence` entries in creation order. The *n*th non-cancelled Run corresponds to the *n*th `workload_sequence` entry. Matching is purely positional — `workload_type` is copied from the sequence entry for display, not used as a join key. The `index` field on the DTO makes the positional mapping explicit for consumers.

### 5.9 API Change

One line changes in `src/squadops/api/routes/cycles/cycles.py`:

```python
# Before (line 125):
background_tasks.add_task(
    flow_executor.execute_run,
    cycle.cycle_id,
    run.run_id,
    body.squad_profile_id,
)

# After:
background_tasks.add_task(
    flow_executor.execute_cycle,
    cycle.cycle_id,
    run.run_id,
    body.squad_profile_id,
)
```

The first Run is still created atomically with the Cycle by the existing `create_cycle` route. `execute_cycle()` picks up from there.

### 5.10 New Event Types

Three new event types in the `workload` entity namespace:

```python
class EventType:
    # ... existing 25 types ...

    # --- Workload (3) — SIP-Multi-Run-Orchestration ---
    WORKLOAD_COMPLETED = "workload.completed"
    WORKLOAD_GATE_AWAITING = "workload.gate_awaiting"
    WORKLOAD_ADVANCED = "workload.advanced"
```

Event payloads use the existing `CycleEvent` model. Workload-specific context (workload type, gate name, next run ID) is carried in the `details` dict.

### 5.11 Cycle Request Profile Update

The existing `multi-phase.yaml` profile becomes functional:

```yaml
# Functional 3-workload pipeline with inter-workload gates.
name: multi-phase
description: "Planning → Implementation → Wrap-up multi-workload cycle"
defaults:
  squad_profile_id: full-squad
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: progress_plan_review
        description: "Review planning artifact before implementation"
        after_task_types:
          - governance.assess_readiness
      - name: progress_impl_review
        description: "Review implementation before wrap-up"
        after_task_types: []
  workload_sequence:
    - type: planning
      gate: progress_plan_review
    - type: implementation
      gate: progress_impl_review
    - type: wrapup
      gate: null
  plan_tasks: true
  build_tasks: true
  pulse_checks:
    - suite_id: planning_scope_guard
      boundary_id: post_strategy
      binding_mode: milestone
      after_task_types:
        - strategy
      checks:
        - check_type: file_exists
          target: "{run_root}/objective_frame.md"
        - check_type: non_empty
          target: "{run_root}/objective_frame.md"
      max_suite_seconds: 15
      max_check_seconds: 5
    - suite_id: planning_completeness
      boundary_id: post_consolidation
      binding_mode: milestone
      after_task_types:
        - governance
      checks:
        - check_type: file_exists
          target: "{run_root}/planning_artifact.md"
        - check_type: non_empty
          target: "{run_root}/planning_artifact.md"
      max_suite_seconds: 15
      max_check_seconds: 5
  cadence_policy:
    max_pulse_seconds: 5400
    max_tasks_per_pulse: 5
  experiment_context: {}
  notes: "Full pipeline: planning → implementation → wrap-up"
```

## 6. Key Design Decisions

### D1: Orchestration lives in the executor, not a new component

`execute_cycle()` wraps `execute_run()` in a loop. This reuses the executor's existing access to the registry, vault, queue, and event bus. No new service or component is introduced. The orchestration logic is intentionally small and localized to the executor, not split into a separate orchestration engine.

### D2: Gate decisions are recorded on the completed Run

The inter-workload gate decision is recorded against the Run whose artifacts are being reviewed (the just-completed Run). This is consistent with the existing intra-run gate pattern: gates belong to Runs, not Cycles. The completed Run's `gate_decisions` list includes both intra-run and inter-workload decisions.

### D3: Refinement notes are stored as a document artifact

When `approved_with_refinements` is used at an inter-workload gate, the decision's `notes` text is written as a `document` artifact on the completed Run. This makes refinement feedback:
- **Auditable** — visible in `artifacts list`, stored with full metadata.
- **Forward-flowing** — picked up by the next workload's handlers via existing artifact forwarding.
- **Consistent** — uses the same `ArtifactVaultPort` mechanism as all other artifacts.

The alternative (passing notes only via `execution_overrides`) loses auditability and discoverability.

### D4: No per-workload applied_defaults

The cycle carries a single `applied_defaults` dict. Workload-type-specific keys already exist (`implementation_pulse_checks`, `build_tasks`, `plan_tasks`, `time_budget_seconds`, etc.). Each workload's handlers read the keys relevant to them. This avoids nested-dict complexity and is consistent with how all existing SIPs use `applied_defaults`.

### D5: derive_cycle_status() is unchanged

The existing `derive_cycle_status()` derives cycle status from the **latest non-cancelled Run** (by `run_number`): `queued`/`running`/`paused` → ACTIVE, `completed` → COMPLETED, `failed` → FAILED. In multi-workload cycles, the latest Run is the most-recently-created workload Run, so the cycle status naturally reflects the current workload's state. No changes to `derive_cycle_status()` or `CycleStatus` are needed.

**Edge case — `rejected` at inter-workload gate:** For v1, cycle top-level status remains derived from the latest run and may therefore show `COMPLETED` even when inter-workload progression was halted by gate rejection. Consumers that care about full pipeline completion must inspect `workload_progress`, which shows the rejection and remaining workloads as `pending`. A future enhancement could add a `REJECTED` cycle status if this proves confusing operationally.

### D6: 1:1 Run ↔ Prefect flow run preserved

Each workload gets its own Run, and each Run maps to its own Prefect flow run. The `PrefectReporter` integration continues unchanged — `execute_run()` manages its own Prefect lifecycle. `execute_cycle()` does not create a parent Prefect flow run.

### D7: Single-workload fast path avoids overhead

When `workload_sequence` has 0 or 1 entries, `execute_cycle()` calls `execute_run()` directly with no loop setup, gate polling, or event emission. This preserves exact current behavior for all existing profiles.

### D8: Port method has a default implementation

`execute_cycle()` is not abstract — it has a default that delegates to `execute_run()`. This means existing `FlowExecutionPort` implementations (test doubles, in-process executor) continue to work without modification. Only `DistributedFlowExecutor` overrides it.

### D9: Artifact forwarding is deterministic with explicit scalar/list semantics

The orchestration loop populates `execution_overrides` using deterministic rules based on the completed workload type (§5.6). Filtering is by `artifact_type` and `promotion_status` metadata — not by filename or handler convention. Scalar keys (e.g., `impl_run_id`) use simple override precedence; list keys (e.g., `plan_artifact_refs`) merge and deduplicate. Promoted-only forwarding for `prior_workload_artifact_refs` prevents accidental downstream coupling to unreviewed artifacts. No new port methods needed.

### D10: `returned_for_revision` is non-resuming and non-advancing — deferred to follow-on SIP

`returned_for_revision` is accepted by the gate API but is non-resuming in `_handle_gate()` and non-advancing in `execute_cycle()`. In this SIP it fails the current run with a descriptive error: *"returned_for_revision requires manual retry-run creation; automatic retry-in-same-phase is not implemented in this version."* SIP-0076 §10.5 specifies that it should create a retry run in the same workload phase — implementing that (max retry limits, loop detection, operator notification) warrants a dedicated follow-on SIP.

### D11: Process restart does not auto-resume orchestration

If the runtime-api process restarts while `execute_cycle()` is polling a gate or between workloads, the orchestration state is lost. The cycle's Runs remain in the registry with accurate statuses. Manual recovery re-invokes `execute_cycle()` using the `cycle_id` and the original first-run ID; the positional duplicate-next-run guard (D14) prevents re-creation of already-created downstream Runs. Persistent orchestration state (e.g., storing progress in the DB) is a future enhancement.

### D12: workload_progress is computed by positional alignment, not stored

The `workload_progress` field on `CycleResponse` is derived at query time by aligning non-cancelled Runs to `workload_sequence` entries in creation order (§5.8). The *n*th non-cancelled Run corresponds to the *n*th sequence entry. Matching is purely positional. No new database columns or registry methods are needed.

### D13: Existing `_handle_gate()` must handle all 4 decision values (prerequisite fix)

The current executor only matches `"approved"` and `"rejected"` in `_handle_gate()`, causing `approved_with_refinements` and `returned_for_revision` to poll indefinitely. This is a pre-existing bug — the domain model (SIP-0076) defines 4 values, the API/CLI accept all 4, but the executor silently ignores 2. The fix is a prerequisite for this SIP and should land as a standalone PR. `approved_with_refinements` resumes the run (notes recorded for auditability). `returned_for_revision` is non-resuming — it fails the run with a descriptive error (per D10).

### D14: Duplicate-next-run guard is positional, matching the progress model

If `execute_cycle()` is interrupted after creating a next-workload Run but before executing it, a re-invocation must not create a duplicate. The guard is positional: if the cycle already has more non-cancelled Runs than the current sequence index, the next Run already exists and is reused (§5.2 pseudocode). This is consistent with the positional alignment used by `workload_progress` (D12) and avoids relying on `workload_type` as a join key.

## 7. File-Level Design

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/ports/cycles/flow_execution.py` | Add `execute_cycle()` with default fallback to `execute_run()` |
| `adapters/cycles/distributed_flow_executor.py` | Override `execute_cycle()`: workload loop, gate polling, Run creation, artifact forwarding, event emission |
| `src/squadops/api/routes/cycles/cycles.py` | Line 125: `flow_executor.execute_run` → `flow_executor.execute_cycle` |
| `src/squadops/events/types.py` | Add 3 workload event types, update `all()` count comment |
| `src/squadops/api/routes/cycles/dtos.py` | Add `WorkloadProgressEntry` model, add `workload_progress` field to `CycleResponse` |
| `src/squadops/contracts/cycle_request_profiles/profiles/multi-phase.yaml` | Update to functional 3-workload profile with `progress_impl_review` gate |

### New Test Files

| File | Contents |
|------|----------|
| `tests/unit/cycles/test_execute_cycle.py` | Orchestration loop: single-workload fast path, multi-workload progression, gate decisions (approved, approved_with_refinements, rejected), artifact forwarding, event emission |
| `tests/unit/ports/test_flow_execution_default.py` | Default `execute_cycle()` delegates to `execute_run()` |
| `tests/unit/api/routes/cycles/test_workload_progress.py` | `workload_progress` DTO computation from cycle + runs |
| `tests/unit/events/test_workload_events.py` | 3 new event type constants registered and emitted |
| `tests/unit/contracts/test_multi_phase_profile.py` | Updated multi-phase profile loads and validates |

### Files NOT Modified

| File | Why |
|------|-----|
| `src/squadops/cycles/models.py` | No new domain model fields — multiple Runs per Cycle already supported |
| `infra/migrations/` | No DB schema changes |
| `src/squadops/cycles/task_plan.py` | Task plan generation already workload-type-aware (SIP-0078) |
| `src/squadops/cycles/status.py` | `derive_cycle_status()` works correctly for multi-run cycles (D5) |

## 8. Implementation Phases

### Phase 1: Prerequisite Fix + Port + Events + Constants
- Fix `_handle_gate()` to handle all 4 `GateDecisionValue` values (D13). Land as standalone PR.
- Add `execute_cycle()` to `FlowExecutionPort` with default fallback.
- Add 3 workload event types to `EventType`.

### Phase 2: Executor Orchestration Loop
- Implement `execute_cycle()` in `DistributedFlowExecutor`.
- Workload loop: iterate `workload_sequence`, create Runs, call `execute_run()`.
- Gate polling between workloads (reuse existing pattern).
- Handle `approved` → proceed, `rejected` → stop.
- Single-workload fast path.
- Event emission at workload transitions.

### Phase 3: Refinement Artifact + Forwarding
- `approved_with_refinements` writes `refinement_notes.md` artifact on completed Run.
- Artifact forwarding: auto-populate `execution_overrides` on next Run creation.
- Forward `plan_artifact_refs`, `impl_run_id`, `prior_workload_artifact_refs`.

### Phase 4: API Integration + DTO + Profile
- Change `execute_run` → `execute_cycle` in cycle creation route.
- Add `WorkloadProgressEntry` and `workload_progress` to `CycleResponse`.
- Update `multi-phase.yaml` to functional 3-workload profile.

### Phase 5: E2E Validation
- E2E: create cycle with `multi-phase` profile, approve planning gate, verify implementation Run is auto-created.
- Verify `cycles show` displays `workload_progress`.

## 9. Known Risks

### Long-running background task
`execute_cycle()` may run for hours across multiple workloads with gate waits. This matches the existing `execute_run()` pattern (which also blocks on gate polling). Future SIPs could move orchestration to a dedicated worker with persistent state.

### Process restart loses orchestration state
If the runtime-api restarts mid-orchestration, the loop is lost. Runs remain in the registry with correct statuses. Manual recovery re-invokes `execute_cycle()` using the `cycle_id` and the original first-run ID created with the cycle. The positional duplicate-next-run guard (D14) prevents re-creation of already-created downstream Runs. Persistent orchestration checkpointing is a future enhancement.

### Interruption scenarios

| Interruption point | Registry state after restart | Manual recovery |
|--------------------|------------------------------|-----------------|
| During `execute_run()` | Current Run is `running` or `failed` | Resume or re-create the Run |
| During inter-workload gate polling | Current Run is `paused` (gate undecided) | Decide the gate; re-invoke `execute_cycle()` |
| After gate decided, before next Run created | Current Run is `completed` with gate decision | Re-invoke `execute_cycle()`; loop skips completed workloads |
| After next Run created, before `execute_run()` | Next Run is `queued` | Re-invoke `execute_cycle()`; D14 guard reuses existing Run |

### Gate polling resource usage
Each orchestration loop holds an async task polling for gate decisions. For a 3-workload cycle, at most 2 gates are polled (sequentially, not concurrently). This matches existing resource usage patterns.

## 10. Acceptance Criteria

1. `_handle_gate()` resumes runs for `approved` and `approved_with_refinements`; fails runs for `rejected` and `returned_for_revision`. No decision value causes indefinite polling.
2. A `returned_for_revision` gate decision never causes indefinite polling and never auto-advances to the next workload; it fails the current run with a descriptive error.
3. `execute_cycle()` exists on `FlowExecutionPort` with a default that delegates to `execute_run()`.
4. `DistributedFlowExecutor.execute_cycle()` iterates `workload_sequence`, creating a Run per workload.
5. Single-workload cycles (no `workload_sequence` or length 1) behave identically to today — `execute_run()` called directly.
6. `approved` gate decision creates the next workload Run and proceeds.
7. `approved_with_refinements` writes `refinement_notes.md` as a `document` artifact on the completed Run, then creates the next Run.
8. `rejected` gate decision stops orchestration. The Run remains `COMPLETED`; the rejection is recorded in `gate_decisions`. `workload_progress` surfaces the rejection and shows remaining workloads as `pending`.
9. Artifact forwarding populates `execution_overrides` on subsequent Runs using deterministic rules (§5.6). Explicit operator overrides take precedence over auto-forwarded values.
10. Three new event types (`workload.completed`, `workload.gate_awaiting`, `workload.advanced`) are emitted at correct transition points.
11. `CycleResponse.workload_progress` shows per-workload status with positional `index`, derived from Runs matched in creation order.
12. `multi-phase.yaml` profile creates a functional 3-workload cycle (planning → implementation → wrapup).
13. If a next-workload Run already exists (e.g., after process restart), the orchestration loop reuses it rather than creating a duplicate.
14. Existing single-workload tests pass without modification (no regressions).
15. No database schema changes required.

## 11. Scope Summary

- **New event types:** 3
- **Prerequisite PR:** Fix `_handle_gate()` to handle all 4 `GateDecisionValue` values
- **No new domain models, no DB migrations, no new ports**
