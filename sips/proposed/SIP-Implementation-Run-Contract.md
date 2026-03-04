# SIP-0XXX: Implementation Run Contract & Correction Protocol

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Updated:** 2026-03-04
**Revision:** 2

---

## 1. Abstract

This SIP defines the contract and runtime protocol for the **Implementation Workload** — the core execution phase of a SquadOps Cycle. The Implementation Run operates from an approved planning artifact and owns the full dev/test/fix convergence loop. It introduces a formal correction protocol (detect → RCA → decide → record plan delta → resume), bounded retry/timebox limits, durable state for checkpoint/resume, and structured task outcome classification required for controlled long-duration execution.

The SIP is the fourth in the Spark-critical sequence (after SIP-0076 Workload & Gate Canon, SIP-0077 Cycle Event System, SIP-0078 Planning Workload Protocol) and must land before the first local validation milestone.

---

## 2. Terminology

| Term | Definition |
|------|-----------|
| **Implementation Run** | A run with `workload_type = "implementation"` that executes the dev/test/fix convergence loop against an approved planning artifact. |
| **Run Contract** | A structured, durable artifact produced at implementation run start that captures objective, acceptance criteria, non-goals, time budget, stop conditions, and required wrap-up outputs. Stored as a run-level artifact and referenced by all pulse checks and correction decisions. |
| **Checkpoint** | A durable snapshot of task completion state taken at each task boundary. Records which tasks have completed, their outputs, and all artifacts produced up to that point. |
| **Plan Delta** | An append-only artifact recording what changed from the original plan during execution — what, why, classification, and new approach. Plan deltas layer on top of the original plan; they never mutate it. |
| **Correction Protocol** | The defined sequence for handling detected problems: detect → root cause analysis → decide → record plan delta → resume. |
| **Correction Path** | One of four bounded options for a correction decision: `continue`, `patch`, `rewind`, `abort`. |
| **Structured Outcome** | A classified task result that distinguishes mechanical failure from semantic failure, enabling the platform to route recovery appropriately. |
| **Convergence Loop** | The dev → test → fix → retest cycle within a single implementation workload. Testing is part of implementation, not a separate workload. |
| **Mechanical Failure** | An execution-oriented failure (timeout, dependency unavailable, transient error) where retry is a reasonable first response. |
| **Semantic Failure** | A meaning-oriented failure (output violates plan, acceptance mismatch, design gap) where retry will not help — correction requires strategic decision. |

---

## 3. Problem Statement

A long autonomous implementation run can appear productive while actually degrading over time. Without explicit controls, the squad may:

- Wander away from the approved objective without traceability.
- Silently change scope.
- Retry weak paths too long, burning time on failing approaches.
- Produce code without meaningful verification.
- Finish with incomplete or low-trust artifacts.

An 8-hour implementation run amplifies all of these risks. Additional compute capacity (e.g., DGX Spark) does not solve coordination, recovery, or artifact integrity problems.

**Specific infrastructure gaps in the current platform (v0.9.16):**

1. **No checkpoint/resume** — the executor has no mechanism to persist task completion state mid-run. If a run is interrupted, it must restart from task 0. The `RunStatus.PAUSED` state exists in the lifecycle model but the executor never transitions to it.
2. **No plan delta capture** — when a pulse check repair modifies the approach, there is no structured record of what changed and why.
3. **No task outcome classification** — `TaskResult.status` is a flat string (`SUCCEEDED`/`FAILED`). The platform cannot distinguish a mechanical timeout from a semantic plan violation, so it cannot route recovery appropriately.
4. **No correction protocol** — the existing pulse repair loop (SIP-0070) is bounded per-pulse and cannot modify the remaining task plan. There is no mechanism to `rewind` to a prior checkpoint or `patch` the task plan mid-run.
5. **No run contract** — the implementation run's objective and acceptance criteria live implicitly in the planning artifact and cycle request profile, not as a durable, platform-validated contract.

---

## 4. Design Principles

### 4.1 Duration-agnostic protocol

Checkpoint/resume, correction protocol, bounded retries, and the convergence loop must work identically for a 1-hour MacBook cycle and an 8-hour DGX Spark cycle. Duration amplifies problems; it does not create them. All protocol mechanics are developed and validated locally on short cycles before attempting long-duration runs.

### 4.2 Prefect owns attempts, SquadOps owns intent

Following the boundary established in `docs/ideas/IDEA-prefect-cycle-event-bus-boundary.md`:

- **Prefect** manages execution topology, retries, timeouts, cancellation, and durable flow state.
- **SquadOps** manages semantic interpretation, correction decisions, workload transitions, and recovery strategy.
- **Tasks** make outcomes legible by classifying results as mechanical or semantic failures.

The correction protocol is SquadOps orchestration logic. It does not push domain knowledge into Prefect, and it does not rebuild Prefect's execution mechanics.

### 4.3 Correction is protocol, not heroics

Correction follows a defined sequence (detect → RCA → decide → record → resume) rather than ad-hoc handler-driven fixes. Recovery is modeled as explicit task sequences, not hidden event handler magic.

### 4.4 Append-only plan evolution

Plan deltas are append-only artifacts. They layer corrections on top of the original plan with full traceability. The original plan is never mutated. An operator reviewing the run can reconstruct the full decision history.

### 4.5 Stop conditions are contractual

The run contract declares when to halt. The platform respects these limits rather than letting the squad "try harder." Exhausting bounded retries or timeboxes triggers escalation or abort, not silent continuation.

### 4.6 Implementation owns testing

The dev/test/fix convergence loop is a single workload. Testing becomes a separate workload only for release validation, compliance, or cross-system certification. This matches the existing `BUILD_TASK_STEPS` / `BUILDER_ASSEMBLY_TASK_STEPS` patterns where QA tasks are part of the implementation step sequence.

---

## 5. Goals

1. Establish **durable checkpoint and resume** as a non-negotiable platform capability — persist task completion state, produced artifacts, prior outputs, and plan delta history so a run can recover from interruptions without losing progress.
2. Define the **Run Contract** artifact schema — objective, acceptance criteria, non-goals, time budget, stop conditions, required wrap-up outputs.
3. Establish a **correction protocol** with explicit steps: detect → root cause analysis → decide → record plan delta → resume with traceability.
4. Introduce **structured task outcome classification** — distinguish mechanical failures (retryable) from semantic failures (needs correction) so the platform can route recovery appropriately.
5. Define **bounded execution limits**: max retries per task, max debug time per task, max consecutive failures before escalation, configurable via cycle request profile.
6. Define **implementation-specific pulse check suites** for plan divergence, repeated failures, scope creep, regression patterns, and lack of forward progress.
7. Emit **new lifecycle events** for checkpoint, resume, and correction actions — extend the SIP-0077 event taxonomy.

---

## 6. Non-Goals

- Defining the wrap-up workload protocol (separate SIP, order 5 on critical path).
- Full self-healing or autonomous adjustment based on prior run history (1.1+).
- Retrieval-before-debugging memory integration (1.1+).
- Scored memory and decay logic (1.1+).
- Role-specific dependency overlays in Docker images (recommended but independent).
- Redefining the Workload domain model (covered by SIP-0076).
- Prefect execution topology templates (Prefect already owns this; see §4.2).
- Automated correction path selection (Lead always makes the correction decision for v1.0).

---

## 7. Design

### 7.1 Run Contract Artifact

Each implementation run begins with a durable **Run Contract** stored as a run-level artifact of type `run_contract`. The contract is generated from the approved planning artifact and cycle request profile at run start, before any implementation tasks execute.

**Schema:**

```python
@dataclass(frozen=True)
class RunContract:
    """Durable execution contract for an implementation run."""

    objective: str                    # What the run must achieve
    acceptance_criteria: tuple[str, ...]  # Testable success conditions
    non_goals: tuple[str, ...]        # Explicit exclusions
    time_budget_seconds: int          # Total execution time envelope
    stop_conditions: tuple[str, ...]  # When to halt rather than continue
    required_artifacts: tuple[str, ...]  # What the run must produce (even on failure)
    plan_artifact_ref: str            # Artifact ID of the approved planning artifact
    source_gate_decision: str | None  # Gate that approved this run (if any)
```

**Placement:** `src/squadops/cycles/run_contract.py`

The contract is the reference point for all pulse checks, correction decisions, and wrap-up comparisons. It is stored via the artifact vault as `artifact_type = "run_contract"`.

### 7.2 Run Contract Generation

A new handler `GovernanceEstablishContractHandler` executes as the **first task** in an implementation run, before any dev/test tasks. It receives the approved planning artifact and emits a RunContract artifact.

**Task type:** `governance.establish_contract`

**Inputs:**
- `plan_artifact_refs` — approved planning artifact(s) from the preceding planning run
- `resolved_config` — cycle request profile (contains time budget, stop conditions)
- `prd` — original PRD (if available)

**Outputs:**
- `run_contract` artifact stored in vault
- `run_contract_ref` — artifact ID for downstream reference

This handler is Lead-owned. It extracts structure from the approved plan and materializes it as a platform-validated contract. If the planning artifact lacks sufficient structure for contract generation, the handler emits a failure with classification `NeedsReplan`.

### 7.3 Structured Task Outcome Classification

`TaskResult` gains an optional `outcome_class` field that classifies the result for routing:

```python
class TaskOutcome:
    """Structured outcome classification for task results.

    Follows the constants-class pattern (WorkloadType, ArtifactType, EventType).
    """

    SUCCESS = "success"                    # Task completed, output meets expectations
    RETRYABLE_FAILURE = "retryable_failure"  # Mechanical failure, retry may help
    SEMANTIC_FAILURE = "semantic_failure"    # Output is wrong/misaligned, retry won't help
    BLOCKED = "blocked"                     # Cannot proceed, dependency missing
    NEEDS_REPAIR = "needs_repair"           # Output partially valid, targeted fix needed
    NEEDS_REPLAN = "needs_replan"           # Fundamental approach is wrong
```

**Placement:** `src/squadops/cycles/task_outcome.py`

**Integration with TaskResult:**

```python
@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str              # SUCCEEDED / FAILED / SKIPPED (unchanged)
    outputs: dict | None
    error: str | None
    outcome_class: str | None = None  # New: TaskOutcome constant (optional, backward compat)
```

When `outcome_class` is `None` (backward compatibility), the executor treats `FAILED` as `RETRYABLE_FAILURE` for the first attempt and `SEMANTIC_FAILURE` after exhausting retries. When present, the executor uses the classification directly.

### 7.4 Checkpoint Model

Checkpoints are persisted at **task boundaries** — after each task completes successfully. A checkpoint captures:

```python
@dataclass(frozen=True)
class RunCheckpoint:
    """Durable snapshot of run execution state at a task boundary."""

    run_id: str
    checkpoint_index: int        # Monotonic, 0-based (= number of completed tasks)
    completed_task_ids: tuple[str, ...]
    prior_outputs: dict          # role → last output (same as executor's chain context)
    artifact_refs: tuple[str, ...]  # All artifact IDs produced so far
    plan_delta_refs: tuple[str, ...]  # All plan delta artifact IDs so far
    created_at: datetime
```

**Placement:** `src/squadops/cycles/checkpoint.py`

**Storage:** Checkpoints are stored via the existing `CycleRegistryPort`. A new method is added:

```python
# In CycleRegistryPort (abstract)
async def save_checkpoint(self, checkpoint: RunCheckpoint) -> None: ...
async def get_latest_checkpoint(self, run_id: str) -> RunCheckpoint | None: ...
```

Both `MemoryCycleRegistry` and `PostgresCycleRegistry` implement these methods. The Postgres adapter stores checkpoints in a new `run_checkpoints` table (see §7.12). The memory adapter stores them in a dict.

**Checkpoint frequency:** Every task boundary (after each successful task completion). This is the minimum resume granularity for v1.0.

### 7.5 Resume Protocol

When a run is resumed from a checkpoint:

1. **Trigger:** API route `POST /runs/{run_id}/resume` or CLI `squadops runs resume <project> <cycle_id> <run_id>`.
2. **State transition:** `PAUSED → RUNNING` (or `FAILED → RUNNING` for retry-from-checkpoint).
3. **Checkpoint load:** Executor loads `get_latest_checkpoint(run_id)`.
4. **Task plan regeneration:** `generate_task_plan()` produces the full task list. The executor skips tasks whose `task_id` appears in `checkpoint.completed_task_ids`.
5. **Context restoration:** `prior_outputs` and `artifact_refs` are restored from the checkpoint. The resumed task receives the same chain context as if the prior tasks had just completed.
6. **Event emission:** `RUN_RESUMED` event (already defined in EventType but currently never emitted).
7. **Plan delta injection:** If plan deltas were recorded before the pause, they are loaded and injected into the resumed task's inputs as `plan_delta_refs`.

**Artifact continuity:** All previously stored artifacts remain accessible. The resumed run does not re-execute completed tasks or re-produce existing artifacts.

**Resume reason:** The resume trigger records a `resume_reason` in the run's metadata, visible via API.

### 7.6 Correction Protocol

When a pulse check or task failure indicates drift or degradation, the correction protocol activates:

**Step 1 — Detect.** A pulse check identifies the problem (plan divergence, repeated failure, scope drift, regression). The detection signal is a `PULSE_BOUNDARY_DECIDED` event with decision `FAIL`.

**Step 2 — Root Cause Analysis.** A correction task sequence executes. The first task is `data.analyze_failure` — Data agent analyzes the failure evidence and classifies it using the failure taxonomy (§7.7).

**Step 3 — Decide.** Lead agent selects a correction path via `governance.correction_decision`:

| Path | Meaning | Effect |
|------|---------|--------|
| `continue` | Minor issue, proceeding as planned | Log plan delta, resume from current point |
| `patch` | Fix the immediate problem | Execute targeted repair tasks, resume from current point |
| `rewind` | Roll back to prior checkpoint | Load earlier checkpoint, resume with plan delta explaining the rewind |
| `abort` | Halt the implementation run | Transition to wrap-up with partial results |

**Step 4 — Record Plan Delta.** A `plan_delta` artifact is stored capturing:

```python
@dataclass(frozen=True)
class PlanDelta:
    """Append-only record of a plan modification during execution."""

    delta_id: str
    run_id: str
    correction_path: str          # continue | patch | rewind | abort
    trigger: str                  # What triggered the correction (pulse check ID, task failure, etc.)
    failure_classification: str   # From failure taxonomy (§7.7)
    analysis_summary: str         # RCA output from Data agent
    decision_rationale: str       # Lead agent's reasoning
    changes: tuple[str, ...]      # What changed in the approach
    affected_task_types: tuple[str, ...]  # Which remaining tasks are affected
    created_at: datetime
```

**Placement:** `src/squadops/cycles/plan_delta.py`

**Step 5 — Resume.** Execution continues from the current point (for `continue`/`patch`) or from a prior checkpoint (for `rewind`), with the plan delta injected into downstream task inputs.

### 7.7 Failure Taxonomy

Following the layered ownership model from the Prefect/Event Bus boundary IDEA:

| Category | Examples | First Owner | Retryable? |
|----------|----------|-------------|------------|
| **Execution** | Timeout, dependency unavailable, transient error, worker interruption | Prefect (mechanical retry) | Yes |
| **Work Product** | Failed schema validation, incomplete artifact, malformed output | Task/workload, then SquadOps | Maybe (once) |
| **Alignment** | Drift from plan, contract violation, acceptance mismatch | SquadOps correction protocol | No — needs correction |
| **Decision** | Conflicting evidence, insufficient context, ambiguous recovery | Escalation / operator | No — needs human |

```python
class FailureClassification:
    """Failure taxonomy for correction protocol RCA.

    Follows the constants-class pattern.
    """

    EXECUTION = "execution"          # Mechanical / infrastructure
    WORK_PRODUCT = "work_product"    # Output quality / completeness
    ALIGNMENT = "alignment"          # Plan drift / contract violation
    DECISION = "decision"            # Ambiguous / needs escalation
    MODEL_LIMITATION = "model_limitation"  # LLM capability gap (expected on smaller models)
```

**Placement:** `src/squadops/cycles/task_outcome.py` (alongside TaskOutcome)

### 7.8 Bounded Execution Limits

Configurable via cycle request profile `applied_defaults`:

| Limit | Key | Default | Behavior when exceeded |
|-------|-----|---------|----------------------|
| Max retries per task | `max_task_retries` | 2 | Task marked `FAILED` with `outcome_class = retryable_failure` exhausted |
| Max task duration | `max_task_seconds` | 600 | Task cancelled, marked `FAILED` with `outcome_class = retryable_failure` |
| Max consecutive failures | `max_consecutive_failures` | 3 | Correction protocol triggered (§7.6) |
| Max correction attempts per run | `max_correction_attempts` | 2 | Run aborted, transition to wrap-up |
| Run time budget | `time_budget_seconds` | 7200 | Run halted, transition to wrap-up |

These limits are stored in the Run Contract (§7.1) and enforced by the executor. The existing `generation_timeout` (SIP-0073) remains for LLM-level timeouts; `max_task_seconds` is the overall task envelope including dispatch and processing.

### 7.9 Implementation Task Steps

A new constant `IMPLEMENTATION_TASK_STEPS` replaces the current workload_type branching for `"implementation"`:

```python
IMPLEMENTATION_TASK_STEPS = [
    # Step 0: Establish run contract (Lead)
    TaskStep("governance.establish_contract", "lead"),
    # Step 1-N: Existing build steps (Dev → [Builder →] QA)
    # ... dynamically appended from BUILD_TASK_STEPS or BUILDER_ASSEMBLY_TASK_STEPS
]
```

The task plan generator prepends the contract establishment step, then appends the existing build task steps. This preserves the existing `BUILD_TASK_STEPS` / `BUILDER_ASSEMBLY_TASK_STEPS` selection logic (builder presence detection) unchanged.

**Correction task steps** are injected dynamically when the correction protocol triggers, not pre-planned:

```python
CORRECTION_TASK_STEPS = [
    TaskStep("data.analyze_failure", "data"),
    TaskStep("governance.correction_decision", "lead"),
]
```

After the correction decision, additional steps depend on the chosen path:
- `patch` → `development.repair` (dev) + `qa.validate_repair` (qa)
- `rewind` → checkpoint restore + re-execute from checkpoint
- `continue` → no additional tasks
- `abort` → no additional tasks (run ends)

### 7.10 Executor Integration

The `DistributedFlowExecutor._execute_sequential()` method gains:

1. **Checkpoint persistence** — after each successful task, call `save_checkpoint()`.
2. **Resume detection** — on run start, check `get_latest_checkpoint(run_id)`. If present, skip completed tasks and restore context.
3. **Outcome routing** — read `TaskResult.outcome_class` to determine retry vs correction:
   - `retryable_failure` → retry up to `max_task_retries`
   - `semantic_failure` / `needs_repair` / `needs_replan` → trigger correction protocol
   - `blocked` → pause run, emit `RUN_PAUSED`
4. **Consecutive failure tracking** — count consecutive failures; trigger correction at threshold.
5. **Time budget enforcement** — check elapsed time before each task; halt if budget exhausted.
6. **Correction injection** — when correction protocol produces a `patch` decision, inject repair tasks into the remaining task sequence.

**Key constraint:** The executor does NOT implement domain-aware recovery logic. It routes failures to the correction task sequence (§7.6), which uses LLM-powered agents (Data for RCA, Lead for decisions). The executor only enforces mechanical limits and manages state transitions.

### 7.11 Event Taxonomy Extensions

New events added to `EventType`:

```python
# --- Checkpoint (2) ---
CHECKPOINT_CREATED = "checkpoint.created"
CHECKPOINT_RESTORED = "checkpoint.restored"

# --- Correction (3) ---
CORRECTION_INITIATED = "correction.initiated"
CORRECTION_DECIDED = "correction.decided"
CORRECTION_COMPLETED = "correction.completed"
```

`RUN_RESUMED` is already defined in EventType (SIP-0077) but never emitted. This SIP activates it.

Total event count: 20 (existing) + 5 (new) + 1 (activated) = 25 emitted event types.

### 7.12 DDL Migration

New table for checkpoint persistence:

```sql
CREATE TABLE IF NOT EXISTS run_checkpoints (
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    checkpoint_index INTEGER NOT NULL,
    completed_task_ids JSONB NOT NULL DEFAULT '[]',
    prior_outputs   JSONB NOT NULL DEFAULT '{}',
    artifact_refs   JSONB NOT NULL DEFAULT '[]',
    plan_delta_refs JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, checkpoint_index)
);
```

No schema changes to existing tables. The Run model gains no new fields — checkpoint state is stored in the separate table and loaded on demand.

### 7.13 Cycle Request Profile Keys

New `_APPLIED_DEFAULTS_EXTRA_KEYS` entries:

```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    # ... existing keys ...
    "max_task_retries",
    "max_task_seconds",
    "max_consecutive_failures",
    "max_correction_attempts",
    "time_budget_seconds",
    "implementation_pulse_checks",
}
```

### 7.14 Implementation Pulse Check Suites

Two implementation-specific pulse check suites, configured in the implementation cycle request profile:

**Suite 1: `impl_progress`** (milestone, fires after each build task)
- `plan_alignment` — does the produced artifact address the planned objective?
- `acceptance_progress` — are acceptance criteria being met incrementally?
- `regression_check` — have previously passing verifications regressed?

**Suite 2: `impl_cadence`** (cadence, fires at cadence interval)
- `forward_progress` — has meaningful work been completed since last check?
- `scope_drift` — is work appearing that was not in the plan?
- `failure_pattern` — are the same failures recurring?

These suites use the existing pulse check framework (SIP-0070). The acceptance engine evaluates checks against task outputs and artifact contents.

### 7.15 API Extensions

**New route:** `POST /projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/resume`

Request body:
```json
{
    "resume_reason": "string (optional)"
}
```

Response: Updated run DTO with `status: "running"`.

**Preconditions:** Run must be in `PAUSED` or `FAILED` status. A checkpoint must exist for the run.

**New route:** `GET /projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/checkpoints`

Response: List of checkpoint summaries (index, completed task count, created_at).

**New CLI commands:**
```bash
squadops runs resume <project> <cycle_id> <run_id>         # Resume from checkpoint
squadops runs checkpoints <project> <cycle_id> <run_id>    # List checkpoints
```

### 7.16 Implementation Cycle Request Profile

A new cycle request profile `implementation` for implementation runs:

```yaml
name: implementation
description: Implementation workload with checkpoint/resume and correction protocol.
defaults:
  workload_sequence:
    - gate_name: progress_implement
      workload_type: implementation
  build_tasks: true
  max_task_retries: 2
  max_task_seconds: 600
  max_consecutive_failures: 3
  max_correction_attempts: 2
  time_budget_seconds: 7200
  implementation_pulse_checks:
    - suite_id: impl_progress
      binding_mode: milestone
      after_task_types:
        - development.
        - builder.
        - qa.
      checks:
        - id: plan_alignment
          description: "Produced artifact addresses planned objective"
        - id: acceptance_progress
          description: "Acceptance criteria being met incrementally"
        - id: regression_check
          description: "No regression in previously passing verifications"
    - suite_id: impl_cadence
      binding_mode: cadence
      checks:
        - id: forward_progress
          description: "Meaningful work completed since last check"
        - id: scope_drift
          description: "No unplanned work appearing"
        - id: failure_pattern
          description: "Same failures not recurring"
  cadence_policy:
    max_pulse_seconds: 600
    max_tasks_per_pulse: 3
```

---

## 8. Backwards Compatibility

### 8.1 TaskResult

`outcome_class` defaults to `None`. Existing handlers that do not set it continue to work — the executor falls back to retry-then-fail behavior, identical to current behavior. No existing handler changes required.

### 8.2 Executor

The checkpoint/resume path is additive. Runs without checkpoints (all existing runs) behave identically. The resume API rejects runs without checkpoints.

### 8.3 Cycle Request Profiles

All new keys (`max_task_retries`, etc.) have defaults. Existing profiles that do not specify them get default values. No existing profile changes required.

### 8.4 Event Bus

5 new EventType constants are additive. Existing bridge adapters (LangFuse, Prefect, Metrics) receive new events via the existing subscriber pattern. Unknown events are safely ignored by bridges that do not handle them.

### 8.5 Tests

All existing tests pass without modification. New tests cover checkpoint, resume, correction, and outcome classification.

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Checkpoint storage bloats for long runs | Disk/DB growth | Checkpoint pruning: keep only latest N checkpoints per run (default 5). Older checkpoints are GC'd. |
| Correction protocol adds latency to failure recovery | Slower failure handling | Correction tasks are bounded by same `max_task_seconds`. Total correction overhead is 2-4 tasks. |
| Structured outcomes require all handlers to classify | Adoption burden | `outcome_class` is optional. Handlers adopt incrementally. Executor has sensible fallback. |
| Rewind to prior checkpoint loses intermediate work | Lost progress | Rewind preserves all artifacts. Only execution state (prior_outputs chain) is rolled back. Artifacts produced between checkpoints remain stored. |
| Plan delta accumulation makes context too large | Token budget pressure | Plan deltas are summarized (not full artifacts) when injected into task inputs. Prompt guard (SIP-0073) truncates if needed. |

---

## 10. Rollout Plan

### Phase 1: Domain Models and Checkpoint Infrastructure

1. Define `RunContract`, `RunCheckpoint`, `PlanDelta`, `TaskOutcome`, `FailureClassification` frozen dataclasses.
2. Add `outcome_class` field to `TaskResult` (optional, default `None`).
3. Add `save_checkpoint()` / `get_latest_checkpoint()` to `CycleRegistryPort`.
4. Implement in `MemoryCycleRegistry` and `PostgresCycleRegistry`.
5. DDL migration for `run_checkpoints` table.
6. Add `CHECKPOINT_CREATED`, `CHECKPOINT_RESTORED`, `CORRECTION_INITIATED`, `CORRECTION_DECIDED`, `CORRECTION_COMPLETED` to `EventType`.

**Success gate:** All new models are frozen dataclasses. Checkpoint round-trip works in both registries. `run_new_arch_tests.sh` green.

### Phase 2: Executor Checkpoint and Resume

1. Add checkpoint persistence to `_execute_sequential()` — save after each successful task.
2. Add resume detection — load checkpoint on run start, skip completed tasks, restore context.
3. Add time budget enforcement — check elapsed time before each task.
4. Emit `CHECKPOINT_CREATED` and `RUN_RESUMED` events.
5. Wire `PAUSED → RUNNING` and `FAILED → RUNNING` transitions in executor.

**Success gate:** A run can be interrupted (cancel/crash), then resumed via API. Completed tasks are not re-executed. Artifacts are preserved. `run_new_arch_tests.sh` green.

### Phase 3: Correction Protocol and Outcome Routing

1. Implement `GovernanceEstablishContractHandler` — run contract generation.
2. Implement `DataAnalyzeFailureHandler` — failure RCA and classification.
3. Implement `GovernanceCorrectionDecisionHandler` — correction path selection.
4. Add outcome routing to executor — read `outcome_class`, route to retry vs correction.
5. Add consecutive failure tracking and correction triggering.
6. Add correction task injection — insert correction tasks into remaining sequence.
7. Add plan delta storage via artifact vault.
8. Emit `CORRECTION_INITIATED`, `CORRECTION_DECIDED`, `CORRECTION_COMPLETED` events.

**Success gate:** A semantic failure triggers the correction protocol. Lead selects a correction path. Plan delta is stored. Run resumes (or aborts) based on the decision. `run_new_arch_tests.sh` green.

### Phase 4: API, CLI, Profile, and Integration

1. Add `POST /runs/{run_id}/resume` API route.
2. Add `GET /runs/{run_id}/checkpoints` API route.
3. Add `squadops runs resume` and `squadops runs checkpoints` CLI commands.
4. Add `implementation` cycle request profile.
5. Add implementation pulse check suites.
6. Add cycle request profile keys to `_APPLIED_DEFAULTS_EXTRA_KEYS`.
7. Integration test: full implementation run with checkpoint, interrupt, resume, and correction.
8. Version bump.

**Success gate:** End-to-end implementation run completes with checkpoint/resume exercised. Correction path exercised (simulated failure). All artifacts produced. `run_new_arch_tests.sh` green.

---

## 11. File-Level Design

### New Files

| File | Purpose |
|------|---------|
| `src/squadops/cycles/run_contract.py` | RunContract frozen dataclass |
| `src/squadops/cycles/checkpoint.py` | RunCheckpoint frozen dataclass |
| `src/squadops/cycles/plan_delta.py` | PlanDelta frozen dataclass |
| `src/squadops/cycles/task_outcome.py` | TaskOutcome, FailureClassification constants |
| `src/squadops/capabilities/handlers/impl/establish_contract.py` | GovernanceEstablishContractHandler |
| `src/squadops/capabilities/handlers/impl/analyze_failure.py` | DataAnalyzeFailureHandler |
| `src/squadops/capabilities/handlers/impl/correction_decision.py` | GovernanceCorrectionDecisionHandler |
| `src/squadops/contracts/cycle_request_profiles/profiles/implementation.yaml` | Implementation profile |
| `infra/migrations/010_run_checkpoints.sql` | DDL for run_checkpoints table |
| `tests/unit/cycles/test_checkpoint.py` | Checkpoint model and registry tests |
| `tests/unit/cycles/test_run_contract.py` | RunContract model tests |
| `tests/unit/cycles/test_plan_delta.py` | PlanDelta model tests |
| `tests/unit/cycles/test_task_outcome.py` | TaskOutcome and FailureClassification tests |
| `tests/unit/capabilities/test_impl_handlers.py` | Implementation handler tests |
| `tests/unit/cycles/test_correction_protocol.py` | Correction protocol integration tests |

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/tasks/models.py` | Add `outcome_class: str \| None = None` to TaskResult |
| `src/squadops/events/types.py` | Add 5 new EventType constants |
| `src/squadops/ports/cycles/registry.py` | Add `save_checkpoint()`, `get_latest_checkpoint()` |
| `adapters/cycles/memory_cycle_registry.py` | Implement checkpoint methods |
| `adapters/cycles/postgres_cycle_registry.py` | Implement checkpoint methods |
| `adapters/cycles/distributed_flow_executor.py` | Checkpoint persistence, resume, outcome routing, correction injection, time budget |
| `src/squadops/cycles/task_plan.py` | Add `IMPLEMENTATION_TASK_STEPS`, `CORRECTION_TASK_STEPS` |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | Add new extra keys |
| `src/squadops/api/routes/runs.py` | Add resume and checkpoints routes |
| `src/squadops/cli/commands/runs.py` | Add resume and checkpoints commands |

---

## 12. Test Plan

| Suite | File | Tests | Purpose |
|-------|------|-------|---------|
| RunContract model | `tests/unit/cycles/test_run_contract.py` | ~8 | Frozen dataclass, field validation, serialization |
| RunCheckpoint model | `tests/unit/cycles/test_checkpoint.py` | ~12 | Frozen dataclass, monotonic index, round-trip in memory + postgres registries |
| PlanDelta model | `tests/unit/cycles/test_plan_delta.py` | ~8 | Frozen dataclass, append-only semantics, serialization |
| TaskOutcome constants | `tests/unit/cycles/test_task_outcome.py` | ~6 | All constants defined, no duplicates, FailureClassification coverage |
| Checkpoint registry | `tests/unit/cycles/test_checkpoint.py` | ~10 | save_checkpoint, get_latest_checkpoint, pruning, empty-state handling |
| Establish contract handler | `tests/unit/capabilities/test_impl_handlers.py` | ~8 | Contract generation from plan artifact, missing plan handling, output schema |
| Failure analysis handler | `tests/unit/capabilities/test_impl_handlers.py` | ~6 | RCA classification, evidence extraction, failure taxonomy mapping |
| Correction decision handler | `tests/unit/capabilities/test_impl_handlers.py` | ~8 | All 4 correction paths, plan delta generation, rationale capture |
| Executor checkpoint | `tests/unit/cycles/test_executor_checkpoint.py` | ~12 | Save after task, load on resume, skip completed, context restoration |
| Executor outcome routing | `tests/unit/cycles/test_executor_checkpoint.py` | ~10 | Retry for retryable, correction for semantic, consecutive failure threshold |
| Executor time budget | `tests/unit/cycles/test_executor_checkpoint.py` | ~4 | Budget enforcement, halt on exhaustion |
| Correction protocol | `tests/unit/cycles/test_correction_protocol.py` | ~12 | Full detect → RCA → decide → record → resume sequence for each path |
| API resume route | `tests/unit/api/test_run_resume.py` | ~8 | Resume from paused/failed, reject without checkpoint, reject from terminal state |
| CLI commands | `tests/unit/cli/test_runs_resume.py` | ~6 | Resume and checkpoints commands |
| Event emission | `tests/unit/events/test_impl_events.py` | ~8 | CHECKPOINT_CREATED, CHECKPOINT_RESTORED, CORRECTION_* emissions |
| Profile validation | `tests/unit/contracts/test_implementation_profile.py` | ~6 | Implementation profile loads, keys valid, pulse checks parse |
| **Total** | | **~130** | |

---

## 13. Key Design Decisions

### D1: Checkpoint at task boundaries, not sub-task

The minimum resume granularity is the completed task. Sub-task checkpointing (within a handler) is out of scope for v1.0. Task boundaries are the natural checkpoint because they are the unit of artifact production, event emission, and state transition. This resolves Open Question 4 from the original IDEA document.

### D2: Run Contract is a stored artifact, not a Run model field

The run contract is stored as an artifact of type `run_contract` via the existing artifact vault, not as fields on the Run dataclass. This avoids expanding the frozen Run model, keeps the contract inspectable via standard artifact APIs, and allows the contract to be referenced by plan deltas and wrap-up artifacts. This resolves Open Question 1 from the original proposal.

### D3: Plan deltas are strictly append-only

Plan deltas never mutate or supersede the original plan. Each delta is a separate artifact that layers corrections on top. An operator or wrap-up process reconstructs the full evolution by reading the original plan + all deltas in order. This makes the decision history fully auditable. This resolves Open Question 2.

### D4: Correction decisions always require Lead involvement

For v1.0, correction path selection (`continue`/`patch`/`rewind`/`abort`) is always made by the Lead agent via `governance.correction_decision`, not automated from pulse check signals. The platform provides evidence (RCA from Data agent) and the Lead decides. Automated correction is a 1.1 consideration. This resolves Open Question 3.

### D5: outcome_class is optional for backward compatibility

Existing handlers do not need to set `outcome_class`. The executor provides sensible defaults: first failure is treated as retryable, exhausted retries escalate to semantic failure. This allows incremental adoption — new implementation handlers set it, existing planning/build handlers do not.

### D6: Rewind preserves artifacts

When a `rewind` correction path is selected, execution state (prior_outputs chain, task index) rolls back to the target checkpoint, but all artifacts produced between the target checkpoint and the current point remain in the vault. This prevents data loss. The plan delta records which artifacts are "pre-rewind" for traceability.

### D7: Checkpoint pruning prevents storage bloat

Only the latest N checkpoints per run are retained (configurable, default 5). Older checkpoints are deleted when a new one is saved. For a 10-task implementation run, this means at most 5 checkpoints at any time. The latest checkpoint is always available for resume.

### D8: Correction tasks are injected dynamically, not pre-planned

The task plan generator does not include correction tasks in the initial plan. When the executor's correction protocol triggers, it dynamically injects `CORRECTION_TASK_STEPS` followed by path-specific tasks (e.g., repair tasks for `patch`). This keeps the happy-path plan clean and avoids speculative task generation.

### D9: Implementation step 0 is always contract establishment

The `governance.establish_contract` task executes before any dev/test tasks. If it fails (e.g., planning artifact insufficient), the run fails immediately rather than proceeding without a contract. This is the platform's last chance to reject an unprepared implementation run.

### D10: TaskFailed events remain observational

Following the Prefect/Event Bus boundary IDEA, `TASK_FAILED` events on the event bus remain observational (telemetry, evidence, threshold inputs). Task-level recovery routing happens in the executor via `outcome_class`, not in event handlers. This prevents the event bus from becoming a second orchestrator.

### D11: FAILED → RUNNING is a valid resume transition

In addition to `PAUSED → RUNNING`, the lifecycle state machine allows `FAILED → RUNNING` for retry-from-checkpoint. This supports the scenario where a run fails due to a transient issue, the operator investigates, and then resumes from the last checkpoint. A new lifecycle transition is added; existing terminal-state semantics for `COMPLETED` and `CANCELLED` are unchanged.

---

## 14. Acceptance Criteria

1. **Checkpoint round-trip** — a checkpoint saved via `save_checkpoint()` can be loaded via `get_latest_checkpoint()` with all fields intact, in both memory and Postgres registries.
2. **Resume from checkpoint** — a run interrupted mid-execution can be resumed. Completed tasks are not re-executed. `prior_outputs` and `artifact_refs` are restored from checkpoint.
3. **Artifact continuity** — all artifacts stored before interruption remain accessible after resume.
4. **Run Contract artifact** — `governance.establish_contract` produces a `run_contract` artifact stored in the vault, referenced by downstream tasks.
5. **Structured outcome routing** — a `TaskResult` with `outcome_class = "semantic_failure"` triggers the correction protocol, not a retry.
6. **Correction protocol full path** — detect → `data.analyze_failure` → `governance.correction_decision` → plan delta stored → execution resumes (or aborts) based on decision.
7. **All four correction paths** — `continue`, `patch`, `rewind`, `abort` are implemented and produce the expected behavior.
8. **Plan delta append-only** — multiple plan deltas can accumulate during a run. Each is a separate artifact. Original plan is never mutated.
9. **Bounded execution limits** — `max_task_retries`, `max_consecutive_failures`, `max_correction_attempts`, and `time_budget_seconds` are enforced by the executor.
10. **RUN_RESUMED event** — emitted when a run resumes from checkpoint.
11. **CHECKPOINT_CREATED event** — emitted after each successful checkpoint save.
12. **CORRECTION_* events** — `CORRECTION_INITIATED`, `CORRECTION_DECIDED`, `CORRECTION_COMPLETED` emitted at correct points.
13. **Resume API** — `POST /runs/{run_id}/resume` transitions run from `PAUSED`/`FAILED` to `RUNNING`, loading the latest checkpoint.
14. **Implementation profile** — `implementation.yaml` loads, validates, and produces correct `applied_defaults`.
15. **Backward compatibility** — existing handlers without `outcome_class` continue to work. Existing runs without checkpoints behave identically.
16. **Checkpoint pruning** — only the latest N checkpoints are retained per run.

---

## 15. Resolved Open Questions

**Q1: Should the run contract be a platform-native artifact type or a section within the planning artifact?**
Decision (D2): Separate artifact of type `run_contract`. This makes it independently inspectable, versionable, and referenceable by plan deltas and wrap-up.

**Q2: Should plan deltas support superseding prior plan sections?**
Decision (D3): No. Plan deltas are strictly append-only. The original plan plus all deltas forms the complete evolution history.

**Q3: Should correction path decisions be automated or require Lead involvement?**
Decision (D4): Always require Lead involvement for v1.0. Automated correction is a 1.1 consideration.

**Q4: What is the minimum resume boundary for v1.0?**
Decision (D1): Task boundary. Checkpoints are saved after each completed task.

**Q5: How should domain-aligned telemetry map to existing infrastructure?**
Resolved: The existing LangFuse trace/span model (trace = cycle, span = task) remains unchanged. New events (CHECKPOINT_*, CORRECTION_*) emit via the existing event bus and are handled by existing bridge adapters. No telemetry model changes needed.

---

## 16. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-long-run-readiness.md` — run contract, correction protocol, checkpoint/resume, role capability baselines, first DGX Spark validation run requirements.
- `docs/ideas/IDEA-prefect-cycle-event-bus-boundary.md` — layered ownership model, failure taxonomy, structured outcome contract, recovery as explicit workloads.

---

## Revision History

| Rev | Date | Changes |
|-----|------|---------|
| 1 | 2026-02-28 | Initial proposal: approach sketch, goals, open questions |
| 2 | 2026-03-04 | Acceptance-ready rewrite: terminology, design principles, 16 design sections, 11 design decisions, 4-phase rollout, file-level design, test plan (~130 tests), failure taxonomy, backwards compatibility, risks, resolved all 5 open questions |
