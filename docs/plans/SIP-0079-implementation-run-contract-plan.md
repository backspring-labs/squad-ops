# Plan: SIP-0079 Implementation Run Contract & Correction Protocol

## Context

SIP-0079 defines the runtime protocol for the Implementation Workload — checkpoint/resume, structured task outcome classification, a correction protocol (detect → RCA → decide → record → resume), bounded execution limits, and a run contract artifact. This is the fourth SIP in the Spark-critical sequence (after SIP-0076, SIP-0077, SIP-0078) and must land before the first local validation milestone.

**Branch:** `feature/sip-0079-implementation-run-contract` (off main)
**SIP:** `sips/accepted/SIP-0079-Implementation-Run-Contract-Correction.md` (Rev 3)

---

## Runtime Contracts

These invariants govern implementation across all phases. Each is referenced by the step that enforces it.

**RC-1 (Task ID stability):** Deterministic task IDs for implementation runs must be stable across resume/regeneration as long as the run contract and workload path are unchanged. Correction-injected tasks use their own deterministic namespace (e.g., `corr-{run_id[:12]}-{correction_index:02d}-{task_type}`) but must not renumber or rename original planned task IDs.

**RC-2 (Rewind target):** In v1.0, `rewind` restores the **latest available successful checkpoint**. Arbitrary checkpoint selection is out of scope. Deeper/manual rewind selection may be added later.

**RC-3 (Correction-task checkpoints as resume anchors):** Successful correction-task checkpoints are valid resume anchors. Resume from latest checkpoint may therefore resume **after** successful correction tasks if the run failed later.

**RC-4 (completed_task_ids membership):** Only successfully completed tasks are added to `completed_task_ids`. Skipped tasks are not checkpointed and are not treated as completed resume anchors.

**RC-5 (BLOCKED counter isolation):** `BLOCKED` does **not** increment `consecutive_failures` or `correction_attempts`. It is an external dependency/governance pause, not a correction-triggering failure.

**RC-6 (NEEDS_REPLAN scope):** `NEEDS_REPLAN` is expected primarily from `governance.establish_contract`. If emitted by other tasks, it follows the generic semantic-failure → correction path unless explicitly overridden later.

**RC-7 (PlanDelta change entry shape):** Each entry in `PlanDelta.changes` is a structured string of the form `"{kind}: {target} — {description}"` (e.g., `"replace: development.build — switch from monolith to microservice scaffold"`). This keeps deltas interpretable for wrap-up and RCA without requiring a sub-dataclass in v1.0.

**RC-8 (Time budget includes correction):** Correction protocol tasks count against the same `time_budget_seconds` as the rest of the implementation run.

**RC-9 (Resume initiates execution):** `POST /runs/{run_id}/resume` is a control-plane action that authorizes and initiates continued execution through the normal executor dispatch path. It is not merely a status mutation — it triggers the executor to pick up the run from the latest checkpoint.

**RC-10 (Missing implementation_pulse_checks fallback):** If `implementation_pulse_checks` is absent from the profile/defaults, the executor uses existing default pulse behavior and does not fail configuration validation.

**RC-11 (Repair task failure recursion):** Failures in repair/validate-repair tasks may trigger another correction cycle, but still count against the same `max_correction_attempts`. No nested infinite correction path exists.

**RC-12 (Resume-after-correction verification):** The test plan must include a scenario where: run fails → correction executes successfully → later interruption occurs → resume restores from the post-correction checkpoint correctly.

---

## Phase 1: Domain Models and Checkpoint Infrastructure

### Commit 1a: TaskOutcome + FailureClassification constants

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cycles/task_outcome.py` | `TaskOutcome` constants class (6 values: SUCCESS, RETRYABLE_FAILURE, SEMANTIC_FAILURE, BLOCKED, NEEDS_REPAIR, NEEDS_REPLAN) + `FailureClassification` constants class (5 values: EXECUTION, WORK_PRODUCT, ALIGNMENT, DECISION, MODEL_LIMITATION) |

**Pattern reference:** `WorkloadType` / `ArtifactType` / `EventType` at `src/squadops/cycles/models.py:89-107` and `src/squadops/events/types.py:10-47` — constants class with string class variables, not enum.

**Tests:** `tests/unit/cycles/test_task_outcome.py` (~6)
- All TaskOutcome constants exist and are lowercase strings
- All FailureClassification constants exist and are lowercase strings
- No duplicate values within each class
- Both are constants classes (not enums)

### Commit 1b: RunContract, RunCheckpoint, PlanDelta frozen dataclasses

**New files:**

| File | Contents |
|------|----------|
| `src/squadops/cycles/run_contract.py` | `RunContract` frozen dataclass: objective, acceptance_criteria (tuple), non_goals (tuple), time_budget_seconds (int), stop_conditions (tuple), required_artifacts (tuple), plan_artifact_ref (str), source_gate_decision (str\|None). Includes `to_dict()` / `from_dict()`. |
| `src/squadops/cycles/checkpoint.py` | `RunCheckpoint` frozen dataclass: run_id, checkpoint_index (int), completed_task_ids (tuple), prior_outputs (dict), artifact_refs (tuple), plan_delta_refs (tuple), created_at (datetime). Includes `to_dict()` / `from_dict()`. **RC-4:** `completed_task_ids` contains only successfully completed tasks — never skipped or failed. |
| `src/squadops/cycles/plan_delta.py` | `PlanDelta` frozen dataclass: delta_id, run_id, correction_path, trigger, failure_classification, analysis_summary, decision_rationale, changes (tuple), affected_task_types (tuple), created_at (datetime). `__post_init__` validates non-empty required fields (failure_classification, analysis_summary, decision_rationale). Changes must be non-empty for `patch`/`rewind`. **RC-7:** Each change entry follows `"{kind}: {target} — {description}"` format. Includes `to_dict()` / `from_dict()`. |

**Pattern reference:** Frozen dataclasses at `src/squadops/cycles/models.py:209-338` — `@dataclass(frozen=True)`, tuple fields for immutable sequences, `dataclasses.replace()` for mutation.

**Tests:**

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/cycles/test_run_contract.py` | ~8 | Frozen immutability, to_dict/from_dict round-trip, optional source_gate_decision defaults to None, tuple fields are tuples not lists |
| `tests/unit/cycles/test_checkpoint.py` | ~6 | Frozen immutability, to_dict/from_dict round-trip with all field types (tuple, dict, datetime) |
| `tests/unit/cycles/test_plan_delta.py` | ~8 | Frozen immutability, to_dict/from_dict round-trip, validation rejects empty failure_classification/analysis_summary/decision_rationale, changes empty OK for continue/abort, changes required for patch/rewind |

### Commit 1c: outcome_class on TaskResult + EventType extensions

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/tasks/models.py:76-99` | Add `outcome_class: str \| None = None` after `execution_evidence` field on `TaskResult`. Backward compatible (defaults None). |
| `src/squadops/events/types.py` | Add 5 new constants after Artifact section: `CHECKPOINT_CREATED = "checkpoint.created"`, `CHECKPOINT_RESTORED = "checkpoint.restored"`, `CORRECTION_INITIATED = "correction.initiated"`, `CORRECTION_DECIDED = "correction.decided"`, `CORRECTION_COMPLETED = "correction.completed"`. Update docstring count from 20 to 25. Update `all()` docstring from 20 to 25. |

**Tests:**

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/tasks/test_task_result_outcome.py` | ~4 | TaskResult with outcome_class=None (backward compat), TaskResult with outcome_class set, from_dict/to_dict round-trip preserves outcome_class |
| `tests/unit/events/test_event_type_extensions.py` | ~5 | EventType.all() returns 25 items, all 5 new constants have correct string values, no duplicate values |

### Commit 1d: Checkpoint methods on CycleRegistryPort + both adapters + DDL + lifecycle transition

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/ports/cycles/cycle_registry.py` | Import `RunCheckpoint`. Add 3 abstract methods: `save_checkpoint(checkpoint: RunCheckpoint, max_keep: int = 5) -> None`, `get_latest_checkpoint(run_id: str) -> RunCheckpoint \| None`, `list_checkpoints(run_id: str) -> list[RunCheckpoint]`. |
| `adapters/cycles/memory_cycle_registry.py` | Add `self._checkpoints: dict[str, list[RunCheckpoint]] = {}` to `__init__`. Implement: `save_checkpoint` (append, prune to max_keep), `get_latest_checkpoint` (return last or None), `list_checkpoints` (return copy of list). |
| `adapters/cycles/postgres_cycle_registry.py` | Implement `save_checkpoint` (INSERT + DELETE for pruning), `get_latest_checkpoint` (SELECT ORDER BY DESC LIMIT 1, parse JSONB), `list_checkpoints` (SELECT ORDER BY ASC). |
| `src/squadops/cycles/lifecycle.py:25-34` | Add transition tuple: `("resume_from_failed", RunStatus.FAILED, RunStatus.RUNNING)`. Keep FAILED in TERMINAL_STATES — `validate_run_transition` uses `_VALID_TRANSITIONS`, not `TERMINAL_STATES`, for transition checks. |

**Note:** FK references `cycle_runs(run_id)` (not `runs(run_id)` — see `infra/migrations/001_cycle_registry.sql:30`).

**New file:**

| File | Contents |
|------|----------|
| `infra/migrations/005_run_checkpoints.sql` | `CREATE TABLE IF NOT EXISTS run_checkpoints (run_id TEXT NOT NULL REFERENCES cycle_runs(run_id), checkpoint_index INTEGER NOT NULL, completed_task_ids JSONB NOT NULL DEFAULT '[]', prior_outputs JSONB NOT NULL DEFAULT '{}', artifact_refs JSONB NOT NULL DEFAULT '[]', plan_delta_refs JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (run_id, checkpoint_index));` |

**Tests:**

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/cycles/test_checkpoint.py` (extend) | ~10 | MemoryCycleRegistry: save_checkpoint + get_latest_checkpoint round-trip, empty returns None, pruning (save 7 with max_keep=5, verify 5 remain), list_checkpoints returns all. PostgresCycleRegistry: contract tests with mock pool. |
| `tests/unit/cycles/test_lifecycle_resume.py` | ~4 | FAILED → RUNNING valid, PAUSED → RUNNING valid (regression), COMPLETED → RUNNING invalid, CANCELLED → RUNNING invalid |

**Success gate:** All models frozen with round-trip serialization. Checkpoint save/get works in both registries. FAILED → RUNNING transition valid. `run_new_arch_tests.sh` green.

---

## Phase 2: Executor Checkpoint and Resume

### Commit 2a: IMPLEMENTATION_TASK_STEPS + CORRECTION_TASK_STEPS + deterministic task IDs

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/task_plan.py` | Add `IMPLEMENTATION_TASK_STEPS` — prepend `("governance.establish_contract", "lead")` before build steps. Add `CORRECTION_TASK_STEPS = [("data.analyze_failure", "data"), ("governance.correction_decision", "lead")]`. Add `REPAIR_TASK_STEPS = [("development.repair", "dev"), ("qa.validate_repair", "qa")]`. In `generate_task_plan()`, add workload_type branching for `WorkloadType.IMPLEMENTATION`: prepend contract step, then existing build steps. **RC-1:** For implementation runs, generate deterministic task IDs: `f"task-{run_id[:12]}-{step_index:03d}-{task_type}"` instead of UUID. Correction-injected tasks use `f"corr-{run_id[:12]}-{correction_index:02d}-{task_type}"`. Neither renumbers original planned task IDs. |

**Tests:** `tests/unit/cycles/test_task_plan.py` (extend, ~8)
- IMPLEMENTATION_TASK_STEPS prepends governance.establish_contract before build steps
- CORRECTION_TASK_STEPS and REPAIR_TASK_STEPS constants defined correctly
- Deterministic task ID format for implementation runs
- Same inputs produce same task IDs across multiple generate_task_plan() calls (RC-1 stability invariant)
- Correction task IDs use separate namespace, don't collide with planned IDs (RC-1)
- Non-implementation runs still use UUID-based task IDs (backward compat)

### Commit 2b: CRP schema extra keys

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/contracts/cycle_request_profiles/schema.py:20-29` | Add to `_APPLIED_DEFAULTS_EXTRA_KEYS`: `"max_task_retries"`, `"max_task_seconds"`, `"max_consecutive_failures"`, `"max_correction_attempts"`, `"time_budget_seconds"`, `"implementation_pulse_checks"`. |

**Tests:** `tests/unit/contracts/test_schema.py` (extend, ~3)
- New keys accepted in extra keys set
- Unknown keys still rejected

### Commit 2c: Executor checkpoint persistence + resume detection + time budget + events

**Modified file:** `adapters/cycles/distributed_flow_executor.py`

**Changes to `_execute_sequential()`:**

1. **State tracking** (top of method): Add `completed_task_ids: list[str] = []`, `plan_delta_refs: list[str] = []`, `consecutive_failures: int = 0`, `correction_attempts: int = 0`, `task_attempt_counts: dict[str, int] = {}`.

2. **Resume detection** (before task loop): Load `get_latest_checkpoint(run_id)`. If checkpoint exists: populate `skip_task_ids` from `checkpoint.completed_task_ids`, restore `prior_outputs`, `all_artifact_refs`, `plan_delta_refs`, `completed_task_ids`. Emit `CHECKPOINT_RESTORED` event.

3. **Skip logic** (in task loop): `if envelope.task_id in skip_task_ids: continue`

4. **Checkpoint on success** (after successful task artifact collection): Build `RunCheckpoint`, call `save_checkpoint()`, emit `CHECKPOINT_CREATED` event. Only on success — failed/skipped tasks don't checkpoint.

5. **Time budget** (before each task dispatch): Read `time_budget_seconds` from `cycle.applied_defaults`. Track `run_start_time = time.monotonic()` at method top. Before dispatch: `if time_budget and (time.monotonic() - run_start_time) >= time_budget: raise _ExecutionError("Time budget exhausted")`. **RC-8:** Correction tasks consume the same budget — no separate clock.

**Changes to `execute_run()`:**

6. **RUN_RESUMED emission**: After `update_run_status(run_id, RunStatus.RUNNING)`, check if checkpoint exists. If so, emit `RUN_RESUMED` event with checkpoint_index.

**Tests:** `tests/unit/cycles/test_executor_checkpoint.py` (~20)
- Checkpoint saved after each successful task (mock registry, verify save_checkpoint called N times)
- Checkpoint NOT saved after failed task
- Resume: skip completed tasks (checkpoint with 2/5 tasks done, verify 3 dispatched)
- Resume: prior_outputs restored from checkpoint
- Resume: artifact_refs restored
- Resume: CHECKPOINT_RESTORED event emitted
- CHECKPOINT_CREATED event emitted after each save
- Time budget: halt when exhausted
- Time budget: no enforcement when not set
- RUN_RESUMED event emitted on resume

**Success gate:** Run can checkpoint and resume. Completed tasks skipped. Time budget enforced. `run_new_arch_tests.sh` green.

---

## Phase 3: Correction Protocol and Outcome Routing

### Commit 3a: Implementation handlers (establish_contract, analyze_failure, correction_decision)

**New files:**

| File | Contents |
|------|----------|
| `src/squadops/capabilities/handlers/impl/__init__.py` | Empty |
| `src/squadops/capabilities/handlers/impl/establish_contract.py` | `GovernanceEstablishContractHandler(_CycleTaskHandler)`: `_capability_id = "governance.establish_contract"`, `_role = "lead"`, `_artifact_name = "run_contract.json"`. Extracts plan artifact → LLM prompt → parse RunContract fields → store as `artifact_type = "run_contract"`. On parse failure: `HandlerResult(success=False)` with `outcome_class = TaskOutcome.NEEDS_REPLAN` in outputs. |
| `src/squadops/capabilities/handlers/impl/analyze_failure.py` | `DataAnalyzeFailureHandler(_CycleTaskHandler)`: `_capability_id = "data.analyze_failure"`, `_role = "data"`, `_artifact_name = "failure_analysis.md"`. Receives failure evidence → LLM classifies using FailureClassification taxonomy → returns classification + analysis_summary. |
| `src/squadops/capabilities/handlers/impl/correction_decision.py` | `GovernanceCorrectionDecisionHandler(_CycleTaskHandler)`: `_capability_id = "governance.correction_decision"`, `_role = "lead"`, `_artifact_name = "correction_decision.md"`. Presents 4 paths (continue/patch/rewind/abort) → LLM selects path + rationale → returns correction_path, decision_rationale, affected_task_types. |
| `src/squadops/capabilities/handlers/impl/repair_handlers.py` | `DevelopmentRepairHandler(_CycleTaskHandler)` with `_capability_id = "development.repair"`, `_role = "dev"`. `QAValidateRepairHandler(_CycleTaskHandler)` with `_capability_id = "qa.validate_repair"`, `_role = "qa"`. Thin subclasses using _CycleTaskHandler flow. |

**Pattern reference:** `_CycleTaskHandler` base class at `src/squadops/capabilities/handlers/cycle_tasks.py:36-120` — handlers inherit it, override `_capability_id`, `_role`, `_artifact_name`, and optionally `handle()`.

**Tests:** `tests/unit/capabilities/test_impl_handlers.py` (~22)
- GovernanceEstablishContractHandler: contract generated from plan artifact (mock LLM), missing plan returns NEEDS_REPLAN, output artifact is type "run_contract", fields extracted correctly
- DataAnalyzeFailureHandler: classification produced, evidence extracted, all FailureClassification categories mapped
- GovernanceCorrectionDecisionHandler: all 4 paths selectable, rationale captured, affected_task_types in outputs
- DevelopmentRepairHandler: repair output produced
- QAValidateRepairHandler: validation output produced

### Commit 3b: Outcome routing + consecutive failure tracking + correction injection

**Modified file:** `adapters/cycles/distributed_flow_executor.py`

Replace the current fail-fast block in `_execute_sequential()` with outcome routing:

1. **Outcome classification**: Read `result.outcome_class`. If None, apply D5 fallback table: first failure → RETRYABLE_FAILURE, exhausted `max_task_retries` → SEMANTIC_FAILURE.
2. **RETRYABLE_FAILURE**: Retry task (re-add to remaining sequence), increment `task_attempt_counts`.
3. **SEMANTIC_FAILURE / NEEDS_REPAIR / NEEDS_REPLAN**: Increment `consecutive_failures`. If from contract task (D9): immediate abort, no correction. **RC-6:** If `NEEDS_REPLAN` from non-contract task, follow generic semantic-failure → correction path. Otherwise: trigger correction protocol.
4. **BLOCKED**: Transition to `PAUSED`, emit `RUN_PAUSED`, raise `_PausedError`. **RC-5:** Does NOT increment `consecutive_failures` or `correction_attempts`.
5. **SUCCESS**: Reset `consecutive_failures = 0`, checkpoint (**RC-4:** add task_id to `completed_task_ids`), continue.
6. **Consecutive failure threshold**: When `consecutive_failures >= max_consecutive_failures` (default 3), trigger correction protocol.

**Correction protocol sequence** (when triggered):
1. Emit `CORRECTION_INITIATED` event.
2. Build correction task envelopes from `CORRECTION_TASK_STEPS` (deterministic IDs).
3. Inject failure evidence into correction task inputs.
4. Dispatch `data.analyze_failure` → `governance.correction_decision` sequentially.
5. Read correction_path from outputs. Emit `CORRECTION_DECIDED` event.
6. Path handling:
   - `continue`: Reset consecutive_failures, store plan delta, continue.
   - `patch`: Inject repair tasks, dispatch them, store plan delta.
   - `rewind`: Load latest checkpoint (**RC-2:** always latest, no arbitrary selection in v1.0), restore state, store plan delta, restart from checkpoint.
   - `abort`: Store plan delta, raise `_ExecutionError`.
7. Emit `CORRECTION_COMPLETED` event.
8. Increment `correction_attempts`. If `>= max_correction_attempts` (default 2): abort.

**RC-3:** Correction tasks checkpoint like normal tasks — successful correction-task checkpoints are valid resume anchors. **RC-11:** Repair task failures may trigger another correction cycle but count against the same `max_correction_attempts`.

**Plan delta storage**: Build `PlanDelta` from correction handler outputs, serialize as JSON artifact via `_store_artifact()` with `artifact_type = "plan_delta"`, append artifact ID to `plan_delta_refs`.

**Tests:**

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/cycles/test_outcome_routing.py` | ~12 | RETRYABLE → retry, SEMANTIC → correction, BLOCKED → pause (RC-5: no counter increment), SUCCESS → checkpoint (RC-4: added to completed_task_ids), NEEDS_REPAIR → correction, NEEDS_REPLAN from contract → immediate abort, NEEDS_REPLAN from other → correction (RC-6), SKIPPED → no checkpoint (RC-4: not in completed_task_ids), outcome_class=None fallback table behavior |
| `tests/unit/cycles/test_correction_protocol.py` | ~18 | Full correction → continue path, → patch path with repair tasks, → rewind path with checkpoint restore (RC-2: latest checkpoint only), → abort path. Consecutive failure threshold triggers correction. max_correction_attempts enforced (RC-11: repair failures count against same limit). Plan delta stored with RC-7 change entry format. Correction tasks checkpoint on success (RC-3: valid resume anchors). Resume-after-correction scenario (RC-12): run fails → correction succeeds → later interruption → resume from post-correction checkpoint. CORRECTION_INITIATED/DECIDED/COMPLETED events emitted at correct points. |

**Success gate:** Semantic failure triggers full correction protocol. All 4 paths work. Contract failure aborts immediately. Plan deltas stored. `run_new_arch_tests.sh` green.

---

## Phase 4: API, CLI, Profile, Bridge Updates, and Integration

### Commit 4a: Resume API route + checkpoints API route + DTOs

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/api/routes/cycles/dtos.py` | Add `ResumeRequest(BaseModel)` with optional `resume_reason: str \| None`. Add `CheckpointSummaryResponse(BaseModel)` with `checkpoint_index: int`, `completed_task_count: int`, `created_at: datetime`. |
| `src/squadops/api/routes/cycles/runs.py` | Add `POST /{run_id}/resume`: **RC-9:** This is a control-plane action that authorizes and initiates continued execution through the normal executor dispatch path (not merely a status mutation). Validates preconditions (PAUSED/FAILED status else 409, checkpoint exists else 422, cycle not terminal else 409), transitions to RUNNING, emits RUN_RESUMED, triggers executor to pick up the run from latest checkpoint. Add `GET /{run_id}/checkpoints`: returns list of CheckpointSummaryResponse via `list_checkpoints()`. |

**Preconditions (tightening #11):**
1. Status is PAUSED or FAILED → else 409 ILLEGAL_STATE_TRANSITION
2. Checkpoint exists → else 422 NO_CHECKPOINT
3. Parent cycle not COMPLETED/CANCELLED → else 409 ILLEGAL_STATE_TRANSITION

**Tests:** `tests/unit/api/test_run_resume.py` (~10)
- Resume from paused: 200
- Resume from failed: 200
- Resume from completed: 409
- Resume from cancelled: 409
- Resume from queued: 409
- Resume without checkpoint: 422
- Resume with terminal cycle: 409
- Resume emits RUN_RESUMED event
- Checkpoints: returns list of summaries
- Checkpoints: empty for run without checkpoints

### Commit 4b: CLI commands (resume, checkpoints)

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cli/commands/runs.py` | Add `resume` command: `POST /runs/{run_id}/resume` with optional `--reason` flag. Add `checkpoints` command: `GET /runs/{run_id}/checkpoints` with table output (index, completed tasks, created_at). |

**Pattern reference:** Existing run CLI commands at `src/squadops/cli/commands/runs.py:41-93` — config loading, API client setup, JSON vs table formatting.

**Tests:** `tests/unit/cli/test_runs_resume.py` (~6)
- Resume command POSTs to correct URL
- Resume with --reason flag
- Checkpoints command GETs correct URL
- Checkpoints table output format

### Commit 4c: Implementation cycle request profile

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/contracts/cycle_request_profiles/profiles/implementation.yaml` | Profile with defaults: `workload_sequence` (implementation workload + progress_implement gate), `build_tasks: true`, `max_task_retries: 2`, `max_task_seconds: 600`, `max_consecutive_failures: 3`, `max_correction_attempts: 2`, `time_budget_seconds: 7200`, `implementation_pulse_checks` (2 suites: impl_progress milestone, impl_cadence cadence), `cadence_policy`. |

**Tests:** `tests/unit/contracts/test_implementation_profile.py` (~7)
- Profile loads without error
- All bounded execution limit keys present with correct defaults
- Pulse check suites parse correctly
- Validates against CRP schema
- **RC-10:** Profile without `implementation_pulse_checks` loads without error (fallback to default pulse behavior)

### Commit 4d: Bridge updates for new events

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/events/bridges/metrics.py` | Add counters: `CORRECTION_INITIATED → corrections_initiated_total`, `CORRECTION_DECIDED → corrections_decided_total` (with `correction_path` label from payload). Add counters for `CHECKPOINT_CREATED → checkpoints_created_total`. |
| `src/squadops/events/bridges/prefect.py` | Ensure `RUN_RESUMED` maps to RUNNING state in `_RUN_STATE_MAP` (may already be handled by existing mapping). |

**Tests:** `tests/unit/events/test_impl_events.py` (~6)
- MetricsBridge handles CORRECTION_INITIATED counter
- MetricsBridge handles CORRECTION_DECIDED counter with correction_path label
- MetricsBridge handles CHECKPOINT_CREATED counter
- PrefectBridge handles RUN_RESUMED mapping

### Commit 4e: Version bump + SIP promotion

- Version bump to 0.9.17 via `scripts/maintainer/version_cli.py`
- Promote SIP-0079 to implemented via `scripts/maintainer/update_sip_status.py`

**Success gate:** Resume API works end-to-end. CLI commands functional. Implementation profile loads. Bridges handle new events. `run_new_arch_tests.sh` green. Full regression passes.

---

## Verification

1. `./scripts/dev/run_new_arch_tests.sh -v` — full regression green (test count increases by ~150)
2. `pytest tests/unit/cycles/ -v` — all checkpoint, correction, outcome tests pass
3. `pytest tests/unit/capabilities/ -v` — impl handler tests pass
4. `pytest tests/unit/api/ -v` — resume and checkpoints routes pass
5. `ruff check . && ruff format --check .` — clean
6. `grep -r "TaskOutcome\|RunCheckpoint\|PlanDelta\|FailureClassification" src/ adapters/` — verify usage is correct
7. Rebuild and deploy: `./scripts/dev/ops/rebuild_and_deploy.sh all` — all services healthy

---

## Test Summary

| Phase | New Tests | Cumulative |
|-------|-----------|------------|
| Phase 1 | ~47 | ~47 |
| Phase 2 | ~32 | ~79 |
| Phase 3 | ~52 | ~131 |
| Phase 4 | ~29 | ~160 |
