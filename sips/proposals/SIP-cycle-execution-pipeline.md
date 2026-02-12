# SIP-00XX: Cycle Execution Pipeline Wiring (API → Flow Executor → Orchestrator → Agents → Artifacts)

**Status:** Proposed  
**Created:** 2026-02-10  
**Owner:** SquadOps Core  
**Target Release:** v0.9.4 (or next minor after v0.9.3)  
**Related:** SIP-0061 (tracing), SIP-0062 (auth), SIP-0064/0065 (API/CLI cycles layer)

---

## 1. Intent

Implement the missing “middle layer” of the cycle execution pipeline: after a cycle + run are created via API/CLI, a flow executor must execute the run by generating `TaskEnvelope`s, dispatching them through `AgentOrchestrator`, handling gates, updating run status, invoking agent lifecycle hooks, and collecting/storing artifacts via `ArtifactVaultPort`.

This SIP is a wiring + coordination implementation. The existing ports/adapters, state machine validation, and agent orchestration are treated as the stable foundation.

---

## 2. Problem Statement

Cycle creation currently persists `Cycle` and `Run` records but does not start execution. Runs remain in `queued` indefinitely, and agents remain idle. The `InProcessFlowExecutor` exists but is stubbed and does not perform execution, status progression, gate pauses/resumes, artifact collection, or lifecycle hook invocation.

---

## 3. Goals

1. **Route → FlowExecutor wiring:** Creating a cycle/run triggers execution asynchronously without blocking API responses.
2. **Run status progression:** `queued → running → (paused) → running → completed/failed/cancelled` is driven by the executor and validated by the lifecycle state machine.
3. **Task generation (v1):** Provide a static, spec’d baseline mapping from PRD + config to a task plan that yields `TaskEnvelope`s for the 5 standard roles.
4. **Gate loop:** Support `TaskFlowPolicy` gates that pause execution at defined boundaries until a decision is recorded and the run resumes.
5. **Artifacts:** Persist artifacts emitted by tasks into the `ArtifactVaultPort`, and attach `artifact_refs` to the run.
6. **Agent lifecycle hooks:** Invoke `on_cycle_start/end` and `on_pulse_start/end` around task execution boundaries (in-process path).
7. **E2E validation:** `play_game` runs end-to-end and produces stored artifacts.

---

## 4. Non-Goals

- Distributed task consumption over RabbitMQ (agent entrypoint changes for task envelopes) — tracked separately.
- Postgres-backed `CycleRegistryPort` adapter — 1.0 hardening concern.
- Full project CRUD (create/update projects via API/CLI) — tracked separately (e.g., SIP-0094).
- “Perfect” PRD-to-task decomposition via LLM planning — initial implementation is static templates; evolvable later.

---

## 5. Proposed Design

### 5.1 Key Principle: Keep Orchestrator Stateless About Cycle Lifecycle

`AgentOrchestrator` remains responsible for routing and executing tasks; the **flow executor** owns cycle/run lifecycle concerns:
- status transitions
- gates / pause-resume
- artifact handling
- lifecycle hook boundaries

This preserves single responsibility and avoids signature churn across orchestration code.

### 5.2 Constructor Injection (No Hidden Globals)

`InProcessFlowExecutor` MUST receive its dependencies via constructor injection:

- `CycleRegistryPort` — for run status updates and gate decision reads
- `ArtifactVaultPort` — for storing task artifacts
- `AgentOrchestrator` — for dispatching tasks to agents

No hidden globals or service locators. Dependencies are provided by the runtime bootstrap:

- `adapters/cycles/factory.py`: `create_flow_executor()` accepts the registry, vault, and orchestrator and passes them to the constructor.
- `src/squadops/api/runtime/main.py`: instantiates the concrete adapters and passes them into the factory at startup.
- `src/squadops/api/runtime/deps.py`: exposes getters for the executor (already exists) and orchestrator (new, if needed).

### 5.3 Execution Flow Overview

1. API creates `Cycle` + `Run` via `CycleRegistryPort`.
2. API schedules `flow_executor.execute_run(cycle, run, profile)` as a background task.
3. Flow executor:
   - updates run status to `running`
   - generates a task plan and constructs `TaskEnvelope`s
   - executes per `TaskFlowPolicy.mode`
   - pauses at gates (optional)
   - stores artifacts after each task (and/or at fan-in)
   - updates run status to terminal outcome

### 5.4 Task Generation (Static Template v1)

Introduce a small "task planning" module that emits a deterministic plan for the standard 5-role squad. The baseline sequence with pinned `task_type` values (used by `AgentOrchestrator.route_task()` for role dispatch):

| Step | Agent | task_type | Work |
|------|-------|-----------|------|
| 1 | Nat (strategy) | `strategy.analyze_prd` | Analyze PRD; produce architecture/plan artifact |
| 2 | Neo (dev) | `development.implement` | Implement per plan; produce code artifact(s) |
| 3 | Eve (QA) | `qa.validate` | Write/run tests; produce test report artifact |
| 4 | Data (analytics) | `analytics.report` | Produce metrics/report artifact |
| 5 | Max (lead) | `governance.review` | Review/summarize; produce run summary artifact |

**Task inputs:**

- `inputs["prd"]` — original PRD content (all tasks)
- `inputs["resolved_config"]` — resolved cycle config (all tasks)
- `metadata["config_hash"]` — config hash for traceability (all tasks)

**Task chaining (sequential mode):**

In sequential mode, the executor accumulates outputs from completed tasks and injects them into downstream envelopes:

- `inputs["prior_outputs"]` — dict keyed by role, containing upstream `TaskResult.outputs` (e.g., `{"strategy": <Nat outputs>, "development": <Neo outputs>}`)
- `inputs["artifact_refs"]` — list of artifact refs emitted by prior steps

**Size rule:** large payloads (code files, reports) MUST be stored as artifacts; chain refs, not raw blobs. `prior_outputs` should contain summaries and structured metadata, not full file contents.

**Extensibility:** Future SIPs may replace or augment this with PRD-driven planning or PCR-declared tasks without changing the flow executor control loop.

### 5.5 TaskFlowPolicy Modes

Minimum spec'd behaviors:

- **sequential**
  - submit one task; await completion; persist status and artifacts; proceed
- **fan_out_fan_in**
  - submit a batch; await all; persist artifacts; proceed
- **fan_out_soft_gates**
  - submit a group; await group; pause at gate boundary; resume after decision

Modes are interpreted by the flow executor; `AgentOrchestrator` remains unaware of the policy.

### 5.6 Error Handling

Mode-level failure semantics:

- **sequential:** fail-fast. First task failure transitions the run to `failed`; remaining tasks are skipped.
- **fan_out_fan_in:** await all tasks. Run transitions to `failed` if any task failed.
- **fan_out_soft_gates:** same as fan_out for the group. If any task in the group failed, run transitions to `failed` before reaching the gate.

This aligns with the existing `AgentOrchestrator.submit_batch()` behavior (fail-fast with remaining tasks marked SKIPPED).

Hook failures are recorded as execution evidence but do not mask task failures.

### 5.7 Gate Pause / Resume

When a gate boundary is reached, executor transitions run status to `paused`. Resume behavior:

- **v1 (acceptable):** poll `CycleRegistryPort.recorded_gate_decisions` (or equivalent read method) until a decision exists for the gate and run is still active.
- **v1.1 (preferred):** in-process `asyncio.Event` per gate decision to avoid polling (optional).

On resume, executor transitions run status back to `running` and continues.

**Gate rejection:** A `rejected` gate decision transitions the run to `failed`. Retries (re-running the group before the gate) are out of scope for this SIP.

### 5.8 Artifact Collection

Spec:

- A task may return `TaskResult.outputs` containing:
  - `artifacts`: list of `{name, bytes|path, media_type, metadata}` (or similar), OR
  - role-specific structured outputs that the flow executor converts into artifact(s)
- Flow executor stores artifacts via `ArtifactVaultPort.store()` and appends the returned refs to `run.artifact_refs`.
- Minimal metadata includes: cycle_id, run_id, task_id, agent_id/role, created_at, and lineage fields (correlation/trace/span).

### 5.9 Lifecycle Hook Invocation

In-process execution invokes:
- `on_cycle_start()` once per run start (per agent participating, or per orchestrator-managed lifecycle)
- `on_pulse_start()` / `on_pulse_end()` around each pulse boundary (v1 can treat "pulse" as a single sequence step or a group boundary)
- `on_cycle_end()` at run completion (success/failure/cancel)

Hook invocation is best-effort and must not mask task failures; failures in hooks are logged and attached as execution evidence.

---

## 6. Implementation Plan

### Phase 1 — Wire Call Site (API → FlowExecutor)
- Update `src/squadops/api/routes/cycles/cycles.py` to invoke `execute_run()` after successful `create_run()`.
- Use FastAPI `BackgroundTasks` (or equivalent) to ensure non-blocking behavior.
- Ensure request returns immediately with `queued`, and the background executor drives progression.

### Phase 2 — Replace `InProcessFlowExecutor` Stub With Real Execution
- Implement `execute_run(cycle, run, profile)`:
  - status transitions via `CycleRegistryPort.update_run_status()`
  - active-run tracking + cancellation checks
  - policy mode interpretation + orchestrator submission
- Implement `cancel_run(run_id)`:
  - mark cancellation intent and transition run to `cancelled` if safe
  - prevent further task dispatch

### Phase 3 — Add Task Planning Module (Static Templates)
- Create a module (e.g., `src/squadops/cycles/task_plan.py`) that:
  - accepts `(cycle, run, profile)` and returns an ordered plan of task specs
  - constructs `TaskEnvelope`s for each step
- Add unit tests ensuring deterministic plan generation for `play_game`.

### Phase 4 — Gates
- Implement gate boundaries in sequential and fan-out modes.
- Pause/resume loop wired to existing gate decision endpoints and registry logic.

### Phase 5 — Artifacts + Evidence
- Implement artifact storage integration with `FilesystemArtifactVault`.
- Attach artifact refs to the run record.
- Add execution evidence summarizing task outcomes, timing, and gate decisions.

### Phase 6 — E2E Tests
- Add/extend E2E tests for:
  - cycle creation triggers background execution
  - run transitions to terminal state
  - artifacts exist in vault and are listable via API/CLI
  - gate pause/resume works for at least one sample policy

---

## 7. Acceptance Criteria

1. Creating a cycle via CLI or API triggers execution without manual steps.
2. A run progresses from `queued` to `running` and reaches a terminal status within expected time (for `play_game`).
3. At least one artifact per role is stored and retrievable via API/CLI.
4. Gate policy pauses the run (`paused`) and resumes to completion after a decision is recorded.
5. Lifecycle hooks are invoked (validated via logs and/or execution evidence).
6. All transitions pass `validate_run_transition()`; invalid transitions are not introduced.

---

## 8. Risks & Mitigations

- **Static templates too rigid:** keep plan module isolated; ensure a future planner can replace the generator without changing executor control loop.
- **Polling gates inefficient:** acceptable for v1; optionally add `asyncio.Event` in v1.1.
- **Agent task handlers incomplete:** introduce a minimal “no-op with artifact” handler per role for sample projects to guarantee E2E execution while role implementations mature.

---

## 9. Rollout / Backward Compatibility

- Default behavior: execution is started automatically on cycle creation.
- A feature flag may be introduced to disable auto-execution for debugging (optional). If introduced, it must default to enabled in dev/test environments.

---

## 10. Test Plan

- Unit tests:
  - task plan generation is deterministic
  - status transitions are legal
  - artifact storage metadata contains required linkage fields
- Integration tests:
  - API create-cycle spawns background execution
  - CLI observability: `runs get`, `artifacts list`, `gates set`
- E2E:
  - `play_game` completes and produces artifacts
  - gate sample completes with pause/resume

---

## 11. Appendix — Proposed File Touches (Non-Exhaustive)

- `src/squadops/api/routes/cycles/cycles.py` (wire execute_run in background)
- `src/squadops/api/runtime/main.py` (pass ports + orchestrator into factory at startup)
- `src/squadops/api/runtime/deps.py` (orchestrator getter, if needed)
- `adapters/cycles/in_process_flow_executor.py` (core implementation)
- `adapters/cycles/factory.py` (accept registry, vault, orchestrator in create_flow_executor)
- `src/squadops/cycles/task_plan.py` (new; static templates)
- `src/squadops/cycles/__init__.py` (exports as needed)
- `tests/…` (unit/integration/e2e coverage)

