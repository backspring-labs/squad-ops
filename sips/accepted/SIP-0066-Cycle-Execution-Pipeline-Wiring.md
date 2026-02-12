---
title: Cycle Execution Pipeline Wiring
status: accepted
author: Jason Ladd
created_at: '2026-02-11T00:00:00Z'
sip_number: 66
updated_at: '2026-02-11T20:15:58.939262Z'
---
# SIP-00XX: Cycle Execution Pipeline (API → Flow Executor → Orchestrator → Agents → Artifacts)

**Status:** Proposed
**Created:** 2026-02-11
**Owner:** SquadOps Core
**Target Release:** v0.9.4 (or next minor after v0.9.3)
**Related:** SIP-0064/0065 (Cycles API/CLI), SIP-0061 (Tracing), SIP-0062 (Auth)

---

## 1. Intent

Implement the missing “middle layer” that turns a created `Cycle` + `Run` into actual execution: generate `TaskEnvelope`s, dispatch them through `AgentOrchestrator`, manage run status transitions, handle gates (pause/resume + rejection), invoke lifecycle hooks, chain task outputs forward, and persist artifacts via `ArtifactVaultPort`.

This is primarily **wiring + coordination**; the existing ports/adapters/state machine/orchestrator remain the foundation.

---

## 2. Problem Statement

Creating a cycle currently persists records and returns `RunStatus=queued`, but nothing starts execution. The `InProcessFlowExecutor` exists but is a stub and does not:
- progress run status beyond `queued`
- construct and dispatch `TaskEnvelope`s
- handle gates
- collect artifacts
- invoke lifecycle hooks
- chain outputs between tasks

Agents are functional, but remain idle because no execution path calls them.

---

## 3. Goals

1. **Auto-execution:** After cycle/run creation via API/CLI, execution starts asynchronously (non-blocking to request).
2. **Status progression:** Run transitions are driven by executor and validated:  
   `queued → running → (paused) → running → completed/failed/cancelled`
3. **Task plan v1:** Deterministic task plan for the standard 5-role squad (static template).
4. **Task chaining:** Downstream tasks receive upstream outputs/refs (Nat → Neo → Eve → Data → Max).
5. **Gate loop:** Pause/resume at policy-defined gates; rejection is defined and deterministic.
6. **Artifacts:** Persist per-task artifacts and attach artifact refs to the run.
7. **Lifecycle hooks:** Invoke `on_cycle_start/end` and `on_pulse_start/end` around task boundaries (in-process).
8. **E2E:** `play_game` runs end-to-end and produces stored artifacts.

---

## 4. Non-Goals

- Distributed execution via RabbitMQ task envelope consumption in agent entrypoint (separate SIP).
- Postgres-backed `CycleRegistryPort` adapter (1.0 hardening).
- Project CRUD (`create_project`) + POST routes/CLI (separate SIP; config-seeded projects acceptable for v0.9.x).
- LLM-driven task planning or PCR-declared task graphs (future enhancement; v1 is static templates).

---

## 5. Proposed Design

### 5.1 Principle: Orchestrator stays stateless about cycle lifecycle

`AgentOrchestrator` remains responsible for routing/executing tasks. The **flow executor** owns:
- run status transitions
- failure semantics
- gates (pause/resume/reject)
- task chaining and context accumulation
- artifact persistence
- lifecycle hook boundaries

### 5.2 Dependency injection (required)

`InProcessFlowExecutor` MUST be constructed with explicit dependencies (no globals):

- `cycle_registry: CycleRegistryPort`
- `artifact_vault: ArtifactVaultPort`
- `orchestrator: AgentOrchestrator`

**Wiring changes are in-scope:**
- `adapters/cycles/factory.py` builds `InProcessFlowExecutor(cycle_registry, artifact_vault, orchestrator, ...)`
- `src/squadops/api/runtime/main.py` instantiates concrete ports/adapters and passes them into the factory
- `src/squadops/api/runtime/deps.py` exposes the flow executor/orchestrator via DI getters

### 5.3 Execution contract (breaking interface change)

**Breaking change:** The `FlowExecutionPort` ABC signature changes from `execute_run(cycle, run, profile)` (passing domain objects) to loading by ID:

- `execute_run(cycle_id: str, run_id: str, profile_id: str | None) -> None`

Executor loads `Cycle` and `Run` from `cycle_registry` at start and before each major step to avoid stale state.

This requires updating:
- `src/squadops/ports/cycles/flow_execution.py` (ABC definition)
- `adapters/cycles/in_process_flow_executor.py` (implementation)
- All tests that mock or implement `FlowExecutionPort`

### 5.4 Task plan v1 (static templates)

Introduce `task_plan.py` that emits a deterministic sequence for the standard 5 roles.

**Pinned `task_type` values (spec’d):**
- `strategy.analyze_prd` → Nat
- `development.implement` → Neo
- `qa.validate` → Eve
- `data.report` → Data
- `governance.review` → Max

**Base envelope inputs (present for every task):**
- `inputs["prd"]`: PRD content or PRD ref
- `inputs["resolved_config"]`: resolved config snapshot or ref
- `inputs["config_hash"]`: stable hash for traceability

### 5.5 Task chaining (sequential + fan-in)

Executor maintains an accumulated context:

- `prior_outputs`: role-keyed map of `TaskResult.outputs` (bounded; prefer refs)
- `artifact_refs`: list of artifact refs persisted so far (preferred for larger content)

For each downstream task, executor injects:

```python
TaskEnvelope.inputs = {
  "prd": <original PRD or ref>,
  "resolved_config": <resolved config or ref>,
  "config_hash": <hash>,
  "prior_outputs": { "strategy": <...>, "development": <...>, ... },
  "artifact_refs": [<refs so far>],
}
```

Large payloads MUST be stored as artifacts and chained by ref (not raw blobs).

### 5.6 Policy modes

Executor interprets `TaskFlowPolicy.mode`:

- **sequential**: submit one task; await; persist artifacts; update accumulated context
- **fan_out_fan_in**: submit a batch; await all; persist artifacts; update accumulated context; proceed to fan-in task(s) if any
- **fan_out_soft_gates**: submit a group; await; persist artifacts; pause at gate boundary; resume after decision

### 5.7 Gates

At a gate boundary, executor transitions run to `paused`, then waits for a recorded decision.

- v1 implementation MAY poll registry (acceptable).
- v1.1 MAY use an in-process signal (`asyncio.Event`) (optional).

**Gate rejection behavior (v1):** rejected decision transitions the run to `failed` (no retries in this SIP).

### 5.8 Failure semantics

Deterministic behavior per mode:

- **sequential:** fail-fast. First failure → run `failed`; remaining tasks skipped.
- **fan_out_fan_in:** await all; run `failed` if any task failed.
- **fan_out_soft_gates:** group failure fails the run before gate.

Hook invocation is best-effort; hook failures are recorded in execution evidence but do not mask task failures.

**Cancellation:** Cancellation is cooperative: `cancel_run()` records intent; the execute loop checks intent before each dispatch and between gate polls. If set, remaining tasks are skipped and the run transitions to `cancelled`.

### 5.9 Artifacts

After each task completion:

1. Inspect `TaskResult.outputs` for artifact payloads (bytes/path) OR structured outputs that should be materialized as artifacts.
2. Store via `artifact_vault.store()`.
3. Append returned refs to `run.artifact_refs` via `cycle_registry.append_artifact_refs(run_id, artifact_ids)`.

**Required artifact metadata fields:**
- `cycle_id`, `run_id`, `task_id`, `agent_id/role`, `task_type`, `step_index`, `created_at`
- lineage/correlation fields when available

### 5.10 Lifecycle hooks

In-process execution invokes:
- `on_cycle_start()` once at the beginning (for participating agents or via orchestrator-managed lifecycle)
- `on_pulse_start()` / `on_pulse_end()` around each step/group boundary (v1: treat each task as a pulse boundary or treat groups as pulses)
- `on_cycle_end()` at terminal state

---

## 6. Implementation Plan

**Note:** Phases 1–3 MUST ship together; otherwise `create_cycle` will invoke a stub executor and/or hit missing dependencies at runtime.

### Phase 1 — Cycle task handlers (pinned capability_ids)
- Create 5 new handlers whose `capability_id` matches the pinned `task_type` values from §5.4:
  - `strategy.analyze_prd`, `development.implement`, `qa.validate`, `data.report`, `governance.review`
- New file: `src/squadops/capabilities/handlers/cycle_tasks.py`
- Register all 5 in `src/squadops/bootstrap/handlers.py` via `HANDLER_CONFIGS`
- Each handler is a minimal no-op stub: validates `prd` input, returns `HandlerResult(success=True, outputs={summary, artifacts, role})`
- Without this phase, `HandlerRegistry` cannot resolve pinned task_types and every task FAILS immediately.

### Phase 2 — Bootstrap/DI wiring (ports → factory → orchestrator → executor)
- Update `adapters/cycles/factory.py` to build executor with constructor injection.
- Update `api/runtime/main.py` to instantiate concrete adapters and bootstrap `AgentOrchestrator`:
  - Create `HandlerRegistry` via `bootstrap/handlers.py` `create_handler_registry()` (includes Phase 1 handlers)
  - Create `SkillRegistry` (empty — no-op handlers don't invoke skills)
  - Create `PortsBundle` with NoOp adapters for all required ports (LLM, memory, etc.) — cycle task handlers don't use these ports, but the dataclass requires concrete values
  - Instantiate `AgentOrchestrator(handler_registry, skill_registry, ports)`
  - Pass orchestrator + cycle_registry + artifact_vault into `create_flow_executor()`
- Update `api/runtime/deps.py` to expose executor/orchestrator via DI getters.
- Add `append_artifact_refs(run_id, artifact_ids)` to `CycleRegistryPort` ABC and implement in `MemoryCycleRegistry`.

### Phase 3 — Route wiring (API → executor)
- In `src/squadops/api/routes/cycles/cycles.py:create_cycle()`, after `create_run()`:
  - enqueue `execute_run(cycle_id, run_id, profile_id)` as a background task
  - API returns immediately with `status=queued`
- Update `FlowExecutionPort` ABC signature: `execute_run(cycle_id, run_id, profile_id)` (breaking change per §5.3)
- Update `InProcessFlowExecutor` stub to match new signature

### Phase 4 — Task plan v1 (static templates + pinned task_types)
- Implement `src/squadops/cycles/task_plan.py`.
- Create envelopes with pinned `task_type` values and base inputs.

### Phase 5 — Implement `InProcessFlowExecutor.execute_run`
- Load `cycle` + `run` from registry.
- Transition `queued → running`.
- Execute per `TaskFlowPolicy.mode` with failure semantics (§5.8).
- Implement task chaining: accumulated context (`prior_outputs`, `artifact_refs`) injected into downstream envelopes.
- Persist terminal status (`completed/failed/cancelled`) via registry updates.

### Phase 6 — Gates (pause/resume + reject)
- Implement pause/resume loop.
- Rejection → run `failed`.

### Phase 7 — Artifacts + execution evidence
- Store artifacts in vault; attach refs to run via `append_artifact_refs()`.
- Record execution evidence (timings, outcomes, gate decisions, chained refs).

### Phase 8 — Tests
- Unit: task_plan deterministic; status transition legality; artifact metadata fields present; cycle task handler validation.
- Integration: create_cycle triggers background execution; run reaches terminal state.
- E2E: `play_game` produces artifacts and demonstrates chaining; gate path includes pause/resume + reject→failed.

---

## 7. Acceptance Criteria

1. Creating a cycle via API/CLI starts execution automatically (no manual kick).
2. Run transitions: `queued → running → terminal` (or `paused` at gates) with validated transitions.
3. `play_game` completes and produces at least one artifact per role.
4. Task chaining is verifiable: Neo’s envelope inputs include Nat’s outputs/refs; downstream steps receive prior refs.
5. Gate pause/resume works; reject transitions run to `failed`.
6. Failure semantics match §5.8 across all supported modes.

---

## 8. Risks & Mitigations

- **Handlers missing for pinned task_types:** add minimal per-role no-op handlers that emit a small artifact for E2E until role handlers mature.
- **Chained payload sizes:** enforce “store large outputs as artifacts; chain refs.”
- **Polling gates:** acceptable for v1; optimize later with signals/events.
- **MemoryCycleRegistry volatility:** acceptable for v0.9.x E2E; Postgres adapter planned for 1.0.

---

## 9. File Touches (non-exhaustive)

- `src/squadops/capabilities/handlers/cycle_tasks.py` **(new)** — 5 cycle task handlers
- `src/squadops/bootstrap/handlers.py` **(modify)** — register cycle task handlers
- `src/squadops/ports/cycles/flow_execution.py` **(modify)** — breaking signature change: `execute_run(cycle_id, run_id, profile_id)`
- `src/squadops/ports/cycles/cycle_registry.py` **(modify)** — add `append_artifact_refs()` abstract method
- `adapters/cycles/memory_cycle_registry.py` **(modify)** — implement `append_artifact_refs()`
- `adapters/cycles/in_process_flow_executor.py` **(replace)** — full implementation
- `adapters/cycles/factory.py` **(modify)** — inject ports into executor
- `src/squadops/cycles/task_plan.py` **(new)** — static task plan generator
- `src/squadops/api/runtime/main.py` **(modify)** — bootstrap orchestrator (HandlerRegistry + SkillRegistry + NoOp PortsBundle) and rewire executor
- `src/squadops/api/runtime/deps.py` **(modify)** — DI providers/getters
- `src/squadops/api/routes/cycles/cycles.py` **(modify)** — wire execute_run background task
- `tests/...` (unit/integration/e2e)

