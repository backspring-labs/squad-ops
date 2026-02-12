# SIP-0066: Cycle Execution Pipeline Wiring — Implementation Plan

## Context

SIP-0066 (accepted) wires the missing middle layer between the API/CLI (SIP-0064/0065) and the agent framework (`BaseAgent`, `AgentOrchestrator`, handlers). Currently, `squadops cycles create play_game` persists records and returns immediately; the run stays `queued` forever. The `InProcessFlowExecutor` logs one line and does nothing else.

This plan implements SIP-0066 across 8 phases: cycle task handlers → bootstrap/DI → route wiring → task plan → executor core → gates → artifacts → tests.

SIP spec: `sips/accepted/SIP-0066-Cycle-Execution-Pipeline-Wiring.md`
Depends on: SIP-0064 (Cycle Execution API), SIP-0065 (CLI)

---

## Key Discoveries from Exploration

1. **Handler mismatch** — The 5 pinned `task_type` values (`strategy.analyze_prd`, `development.implement`, `qa.validate`, `data.report`, `governance.review`) do NOT match any existing registered `capability_id`s. Existing handlers use different names (`governance.task_analysis`, `development.code_generation`, etc.) for skill-based execution. We need 5 new cycle-specific handlers.

2. **AgentOrchestrator not instantiated** — `main.py` initializes cycle ports but never creates an `AgentOrchestrator`. Bootstrap requires: `HandlerRegistry` (via `create_handler_registry()`), `SkillRegistry` (empty is fine), and `PortsBundle` (frozen dataclass needing 7 concrete port implementations + optional llm_observability).

3. **PortsBundle requires 7 ports** — `PortsBundle(llm, memory, prompt_service, queue, metrics, events, filesystem)`. Cycle task handlers don't use any of these, but the dataclass can't be constructed without them. Need NoOp stubs.

4. **`submit_task()` routes by task_type prefix** — `AgentOrchestrator.DEFAULT_ROUTING` maps `"data."` → `"data"` role (confirming `data.report` is correct, not `analytics.report`). The routing is: `governance.` → lead, `development.` → dev, `qa.` → qa, `data.` → data, `strategy.` → strat.

5. **`submit_task()` calls `HandlerExecutor.execute()`** which resolves handler from `HandlerRegistry` by `capability_id == task_type`. If handler not found → `HandlerNotFoundError`. This is why Phase 1 (handler registration) is a hard prerequisite.

6. **`FlowExecutionPort.execute_run()` currently takes `(cycle, run, profile)`** — SIP-0066 changes this to `(cycle_id, run_id, profile_id)` for staleness protection. This is a breaking interface change affecting the ABC, adapter, and all call sites.

7. **`CycleRegistryPort` has no `append_artifact_refs()`** — Need to add this abstract method + implement in `MemoryCycleRegistry`.

8. **`ExecutionContext.create()` requires `agent_id`, `role_id`, `task_id`, `cycle_id`, `ports`, `skill_registry`** — The `HandlerExecutor` constructs this internally. The orchestrator's `submit_task()` delegates to `self._executor.execute(envelope, timeout)`.

9. **`HandlerResult` requires `_evidence: HandlerEvidence`** — Cycle task handlers must produce evidence via `HandlerEvidence.create()`. Cannot return `HandlerResult(success=True, outputs={})` without evidence.

10. **`run_new_arch_tests.sh` runs 912+ tests** — Full regression suite. Must pass after all phases.

11. **`TaskResult.status` is a string** — Values: `"SUCCEEDED"`, `"FAILED"`, `"CANCELED"`. The executor checks `result.status != "SUCCEEDED"` for fail-fast. Confirmed from `src/squadops/tasks/models.py:TaskResult`.

12. **`ArtifactVaultPort.store(artifact: ArtifactRef, content: bytes) -> ArtifactRef`** — Confirmed from `src/squadops/ports/cycles/artifact_vault.py`. Takes an `ArtifactRef` + raw bytes, returns `ArtifactRef` with `vault_uri` populated. The `_store_artifact` helper must encode string content to bytes before calling.

---

## Decisions (binding for implementation)

**D1) Stub handlers, not stub agents.** Cycle task handlers are `CapabilityHandler` subclasses, not `BaseAgent` subclasses. They don't touch the incomplete agent shims in `execution/squad/`.

**D2) `data.report` not `analytics.report`.** Matches existing `"data."` routing prefix in `AgentOrchestrator.DEFAULT_ROUTING`.

**D3) NoOp PortsBundle as a reusable module with safe-by-default behavior.** Create `adapters/noop/ports.py` with NoOp implementations for all 7 required ports and a `create_noop_ports_bundle()` factory. Behavior split:
- **Safe do-nothing** for fire-and-forget / ambient calls: `MetricsPort`, `EventPort`, `QueuePort` (return empty, log nothing, no-op). The orchestrator/executor pipeline may emit metrics or events implicitly — these must not explode.
- **Hard-fail (`NotImplementedError`)** for intentional calls that should never happen in cycle task handlers: `LLMPort` (completion), `MemoryPort` (read/write), `PromptService` (fetch), `FileSystemPort` (read/write). If these fire, something is wrong and we want to know immediately.
Reusable by both `main.py` bootstrap and tests.

**D4) Empty SkillRegistry.** Cycle task handlers return structured data directly — they don't invoke skills via `context.execute_skill()`. An empty `SkillRegistry()` is sufficient.

**D5) Polling for gate decisions (v1).** `asyncio.sleep(interval)` + `registry.get_run()` to check for decisions. Acceptable for v1; future SIP can add `asyncio.Event` signaling.

**D6) TaskEnvelope.inputs for chaining.** `prior_outputs` and `artifact_refs` injected via `dataclasses.replace()` on the frozen envelope's inputs dict.

**D7) Phases 1–3 ship together.** Route wiring without handler registration and orchestrator bootstrap would invoke a stub executor / hit missing deps at runtime. These phases must land in the same PR or be feature-flagged together.

**D8) Breaking port signature change.** `FlowExecutionPort.execute_run(cycle_id, run_id, profile_id)` replaces `execute_run(cycle, run, profile)`. Executor loads authoritative state from registry to avoid stale objects.

**D9) Cancellation is registry-driven.** `cancel_run()` calls `self._cycle_registry.cancel_run(run_id)` to persist intent, AND adds `run_id` to a local `self._cancelled: set[str]` for fast in-process checking. The execute loop checks both local set (fast path) and registry state (authoritative) before each dispatch and between gate polls. Registry is source of truth; local set is an optimization for the common single-process case.

**D10) Inject `SquadProfilePort` into executor.** The executor needs to load the profile by `profile_id`. Add `squad_profile: SquadProfilePort` to `InProcessFlowExecutor` constructor, factory wiring, and runtime bootstrap. This resolves Open Question #2 definitively.

**D11) Gate boundary timing is post-gate.** `after_task_types` means: execute the task, THEN check if the just-completed `task_type` appears in any gate's `after_task_types`. If yes, pause. This aligns with the field name and prevents pausing before the work that precedes the gate.

**D12) Constructor deps are required, not Optional.** `InProcessFlowExecutor` requires all injected deps (`cycle_registry`, `artifact_vault`, `orchestrator`, `squad_profile`). No silent fallback — if deps are missing, construction fails fast at startup. D7 guarantees they're always available.

---

## Phase 1: Cycle Task Handlers

Create 5 handlers subclassing `CapabilityHandler`, one per role. These are minimal no-op stubs that return placeholder content — future SIPs replace with LLM-driven implementations.

### 1.1 New file: `src/squadops/capabilities/handlers/cycle_tasks.py`

| Handler Class | `capability_id` | Role | Purpose |
|---------------|-----------------|------|---------|
| `StrategyAnalyzeHandler` | `strategy.analyze_prd` | strat | Accept PRD; return architecture/plan summary |
| `DevelopmentImplementHandler` | `development.implement` | dev | Accept PRD + prior_outputs; return code summary |
| `QAValidateHandler` | `qa.validate` | qa | Accept PRD + prior_outputs; return test report |
| `DataReportHandler` | `data.report` | data | Accept PRD + prior_outputs; return metrics |
| `GovernanceReviewHandler` | `governance.review` | lead | Accept PRD + prior_outputs; return review |

Each handler:
- `validate_inputs()`: requires `prd` key in inputs (returns `["'prd' is required"]` if missing)
- `handle()`: creates `HandlerEvidence.create(handler_name, capability_id, duration_ms)`, returns `HandlerResult(success=True, outputs={...}, _evidence=evidence)` with role-specific structured output:
  ```python
  outputs = {
      "summary": f"[{role}] Stub analysis of PRD...",
      "role": role,
      "artifacts": [
          {"name": f"{role}_output.md", "content": "...", "media_type": "text/markdown"}
      ],
  }
  ```
- Pattern follows `governance.py` `TaskAnalysisHandler` but WITHOUT skill execution (no `context.execute_skill()`)

### 1.2 Modify: `src/squadops/bootstrap/handlers.py`

Add imports and 5 entries to `HANDLER_CONFIGS`:
```python
from squadops.capabilities.handlers.cycle_tasks import (
    StrategyAnalyzeHandler,
    DevelopmentImplementHandler,
    QAValidateHandler,
    DataReportHandler,
    GovernanceReviewHandler,
)

# In HANDLER_CONFIGS list:
(StrategyAnalyzeHandler, ("strat",)),
(DevelopmentImplementHandler, ("dev",)),
(QAValidateHandler, ("qa",)),
(DataReportHandler, ("data",)),
(GovernanceReviewHandler, ("lead",)),
```

---

## Phase 2: Bootstrap/DI Wiring

### 2.1 New file: `adapters/noop/ports.py` — NoOp Ports for PortsBundle

Create a reusable module with NoOp implementations for all 7 required ports. Each NoOp class subclasses the corresponding port ABC and implements all abstract methods. Behavior per D3:
- **Safe do-nothing** (return empty/None, no side effects): `NoOpMetricsPort`, `NoOpEventPort`, `NoOpQueuePort`
- **Hard-fail** (`raise NotImplementedError`): `NoOpLLMPort`, `NoOpMemoryPort`, `NoOpPromptService`, `NoOpFileSystemPort`

Exports a factory:
```python
def create_noop_ports_bundle() -> PortsBundle:
    """Create PortsBundle with NoOp stubs for orchestrator bootstrap.

    Cycle task handlers don't use skills or external ports.
    These stubs exist only to satisfy the PortsBundle dataclass.
    """
    return PortsBundle(
        llm=NoOpLLMPort(),
        memory=NoOpMemoryPort(),
        prompt_service=NoOpPromptService(),
        queue=NoOpQueuePort(),
        metrics=NoOpMetricsPort(),
        events=NoOpEventPort(),
        filesystem=NoOpFileSystemPort(),
    )
```

**Pre-implementation step:** Survey all 7 port ABCs for their abstract method signatures to ensure each NoOp satisfies them. Check for existing NoOp adapters first (e.g., `NoOpLLMObservabilityAdapter` exists per CLAUDE.md).

### 2.2 Modify: `src/squadops/api/runtime/main.py` — Bootstrap orchestrator

In `startup_event()`, after cycle ports are initialized, add:

```python
# Bootstrap AgentOrchestrator for cycle execution
from squadops.bootstrap.handlers import create_handler_registry
from squadops.agents.skills.registry import SkillRegistry
from squadops.orchestration.orchestrator import AgentOrchestrator
from adapters.noop.ports import create_noop_ports_bundle

handler_registry = create_handler_registry()
skill_registry = SkillRegistry()
ports_bundle = create_noop_ports_bundle()

orchestrator = AgentOrchestrator(
    handler_registry=handler_registry,
    skill_registry=skill_registry,
    ports=ports_bundle,
)

# Re-create flow executor with injected dependencies
flow_executor = create_flow_executor(
    "in_process",
    cycle_registry=cycle_registry,
    artifact_vault=artifact_vault,
    orchestrator=orchestrator,
    squad_profile=squad_profile,
)
set_cycle_ports(flow_executor=flow_executor)
```

Where `cycle_registry`, `artifact_vault`, and `squad_profile` are the already-created instances from the existing initialization block. Requires refactoring the existing init block to capture those variables before `set_cycle_ports()`.

### 2.3 Modify: `adapters/cycles/factory.py` — Accept DI params

```python
def create_flow_executor(
    provider: str = "in_process",
    *,
    cycle_registry: CycleRegistryPort | None = None,
    artifact_vault: ArtifactVaultPort | None = None,
    orchestrator: AgentOrchestrator | None = None,
    squad_profile: SquadProfilePort | None = None,
    **kwargs,
) -> FlowExecutionPort:
    if provider == "in_process":
        from adapters.cycles.in_process_flow_executor import InProcessFlowExecutor
        return InProcessFlowExecutor(
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            orchestrator=orchestrator,
            squad_profile=squad_profile,
        )
    raise ValueError(...)
```

### 2.4 Modify: `src/squadops/ports/cycles/cycle_registry.py` — Add `append_artifact_refs`

```python
@abstractmethod
async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run:
    """Append artifact references to a run record.

    Raises:
        RunNotFoundError: If the run_id is not found.
    """
```

### 2.5 Modify: `adapters/cycles/memory_cycle_registry.py` — Implement `append_artifact_refs`

De-duplicating implementation for safety:
```python
async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run:
    if run_id not in self._runs:
        raise RunNotFoundError(f"Run not found: {run_id}")
    data = self._runs[run_id]
    existing = list(data.get("artifact_refs", []))
    existing_set = set(existing)
    for aid in artifact_ids:
        if aid not in existing_set:
            existing.append(aid)
            existing_set.add(aid)
    data["artifact_refs"] = existing
    return self._to_run(data)
```

---

## Phase 3: Route Wiring + Port Signature Change

### 3.1 Modify: `src/squadops/ports/cycles/flow_execution.py` — Breaking signature change

```python
class FlowExecutionPort(ABC):
    @abstractmethod
    async def execute_run(
        self, cycle_id: str, run_id: str, profile_id: str | None = None
    ) -> None:
        """Execute a run by loading authoritative state from registry."""

    @abstractmethod
    async def cancel_run(self, run_id: str) -> None:
        """Cancel an in-progress run execution."""
```

### 3.2 Search & update all implementers/mocks (breaking change checklist)

Before proceeding, run: `grep -rn 'execute_run(' src/ adapters/ tests/` and update every hit:
- `adapters/cycles/in_process_flow_executor.py` — adapter implementation
- `tests/unit/cycles/test_adapters.py` — any executor tests
- `tests/unit/cycles/test_integration.py` — integration test mocks
- Any other test that mocks `FlowExecutionPort.execute_run`

This is the most common place where regressions slip through on signature changes.

### 3.3 Modify: `adapters/cycles/in_process_flow_executor.py` — Match new signature

Update to accept new signature (full implementation in Phase 5):
```python
async def execute_run(
    self, cycle_id: str, run_id: str, profile_id: str | None = None
) -> None:
    ...
```

### 3.4 Modify: `src/squadops/api/routes/cycles/cycles.py` — Background task wiring

The existing `create_cycle()` route already resolves the profile via `profile_port.resolve_snapshot(body.squad_profile_id)` and has the `profile` object in scope (see `cycles.py:44`). The `profile_id` is `body.squad_profile_id` (from `CycleCreateRequest`).

```python
from fastapi import BackgroundTasks

@router.post("")
async def create_cycle(
    project_id: str, body: CycleCreateRequest, background_tasks: BackgroundTasks
):
    # ... existing persist logic (unchanged) ...
    # `profile` already resolved above via profile_port.resolve_snapshot(body.squad_profile_id)

    # Wire execute_run as background task
    from squadops.api.runtime.deps import get_flow_executor
    flow_executor = get_flow_executor()
    background_tasks.add_task(
        flow_executor.execute_run,
        cycle.cycle_id,
        run.run_id,
        body.squad_profile_id,  # from CycleCreateRequest, same ID used to resolve profile above
    )

    return CycleCreateResponse(...)
```

API still returns immediately with `status: "queued"`. The background task drives `queued → running → completed/failed`.

---

## Phase 4: Task Plan Generator

### 4.1 New file: `src/squadops/cycles/task_plan.py`

```python
def generate_task_plan(
    cycle: Cycle, run: Run, profile: SquadProfile
) -> list[TaskEnvelope]:
```

Produces the deterministic 5-step plan per SIP-0066 §5.4:

**Steps:**
1. Construct one `TaskEnvelope` per step using pinned task_types
2. All envelopes share `cycle_id`, `project_id`, `correlation_id`, `trace_id` (generated once per plan)
3. Each gets unique `task_id` (uuid), `pulse_id` (uuid), `span_id` (uuid)
4. `causation_id` chains: step N's `task_id` becomes step N+1's `causation_id`
5. `inputs` contains:
   - `prd`: `cycle.prd_ref` — **this is a PRD ref (identifier/path), not hydrated content.** Handlers treat it as an opaque identifier for v1. Future SIP can hydrate content from vault/filesystem. Do not add content-loading logic in this implementation.
   - `resolved_config`: `{**cycle.applied_defaults, **cycle.execution_overrides}`
   - `config_hash`: `run.resolved_config_hash`
6. `agent_id` resolved from `profile.agents` by matching `role` to the step's expected role
7. `metadata` includes `step_index` (0-4) and `role` for traceability

**Task type → role mapping (pinned):**
```python
CYCLE_TASK_STEPS = [
    ("strategy.analyze_prd", "strat"),
    ("development.implement", "dev"),
    ("qa.validate", "qa"),
    ("data.report", "data"),
    ("governance.review", "lead"),
]
```

**Reuse:** `TaskEnvelope` from `src/squadops/tasks/models.py`, uuid generation for IDs.

---

## Phase 5: Flow Executor Core (sequential + chaining + fail-fast + cancellation)

Gate logic is NOT in this phase — it is added in Phase 6.

### 5.1 Replace: `adapters/cycles/in_process_flow_executor.py`

#### Constructor (D12: all deps required)

```python
class InProcessFlowExecutor(FlowExecutionPort):
    def __init__(
        self,
        cycle_registry: CycleRegistryPort,
        artifact_vault: ArtifactVaultPort,
        orchestrator: AgentOrchestrator,
        squad_profile: SquadProfilePort,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._orchestrator = orchestrator
        self._squad_profile = squad_profile
        self._cancelled: set[str] = set()
```

#### `execute_run(cycle_id, run_id, profile_id)` flow

```
1. Load cycle from registry: cycle = await self._cycle_registry.get_cycle(cycle_id)
2. Load run from registry: run = await self._cycle_registry.get_run(run_id)
3. Load profile: profile, _ = await self._squad_profile.resolve_snapshot(profile_id)
4. registry.update_run_status(run_id, RUNNING)
5. plan = generate_task_plan(cycle, run, profile)
6. Match on cycle.task_flow_policy.mode:
   - sequential → _execute_sequential(plan, run_id, cycle)
   - fan_out_fan_in → _execute_fan_out(plan, run_id, cycle)
   - fan_out_soft_gates → _execute_gated(plan, run_id, cycle)
7. On success: registry.update_run_status(run_id, COMPLETED)
8. On _ExecutionError: registry.update_run_status(run_id, FAILED)
9. On _CancellationError: registry.update_run_status(run_id, CANCELLED)
10. All wrapped in try/except — any unhandled exception → FAILED + log
```

#### Sequential execution (primary path for `play_game`)

```python
async def _is_cancelled(self, run_id: str) -> bool:
    """D9: check local fast-path set AND registry state (source of truth)."""
    if run_id in self._cancelled:
        return True
    run = await self._cycle_registry.get_run(run_id)
    if run.status == RunStatus.CANCELLED.value:
        self._cancelled.add(run_id)  # cache for fast path
        return True
    return False

prior_outputs = {}
all_artifact_refs = []
for i, envelope in enumerate(plan):
    # Check cancellation (D9: registry-driven + local fast path)
    if await self._is_cancelled(run_id):
        raise _CancellationError(run_id)
    # Inject chain context via dataclasses.replace (D6)
    enriched = dataclasses.replace(envelope, inputs={
        **envelope.inputs,
        "prior_outputs": prior_outputs,
        "artifact_refs": list(all_artifact_refs),
    })
    # Dispatch
    result = await self._orchestrator.submit_task(enriched)
    if result.status != "SUCCEEDED":  # Discovery #11: string comparison
        raise _ExecutionError(f"Task {envelope.task_id} failed: {result.error}")
    # Collect artifacts — only new refs for this step (Tightening #1)
    new_refs = []
    for art in (result.outputs or {}).get("artifacts", []):
        ref = await self._store_artifact(art, cycle, run_id, envelope)
        new_refs.append(ref.artifact_id)
        all_artifact_refs.append(ref.artifact_id)
    # Persist only this step's new refs (avoids duplicate explosion)
    if new_refs:
        await self._cycle_registry.append_artifact_refs(run_id, tuple(new_refs))
    # Chain outputs by role_id (strat/dev/qa/data/lead — NOT agent name, NOT task_type)
    role = envelope.metadata.get("role", "unknown")
    prior_outputs[role] = {
        k: v for k, v in (result.outputs or {}).items() if k != "artifacts"
    }
```

**Chaining key convention:** `prior_outputs` is keyed by `role_id` (`strat`, `dev`, `qa`, `data`, `lead`). Downstream consumers access prior outputs as `inputs["prior_outputs"]["strat"]`, etc. This is stable and predictable regardless of agent naming.

#### `cancel_run(run_id)` — Registry-driven cancellation (D9)

```python
async def cancel_run(self, run_id: str) -> None:
    self._cancelled.add(run_id)
    await self._cycle_registry.cancel_run(run_id)
```

#### `_store_artifact()` helper (Discovery #12: confirmed store API)

**Pre-implementation verification:** Before coding this helper, construct one minimal `ArtifactRef(...)` in a REPL or throwaway test to confirm all field names match the real dataclass (`artifact_id`, `project_id`, `artifact_type`, `filename`, `content_hash`, `size_bytes`, `media_type`, `created_at`, `cycle_id`, `run_id`, `metadata`). Field name mismatches cause runtime `TypeError`s that are easy to miss until integration.

```python
async def _store_artifact(self, art_dict, cycle, run_id, envelope) -> ArtifactRef:
    content = art_dict.get("content", "").encode("utf-8")
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        artifact_type=art_dict.get("type", "document"),
        filename=art_dict["name"],
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=art_dict.get("media_type", "text/markdown"),
        created_at=datetime.now(UTC),
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        metadata={"task_id": envelope.task_id, "role": envelope.metadata.get("role")},
    )
    return await self._artifact_vault.store(ref, content)
```

---

## Phase 6: Gates (Pause/Resume + Reject)

Wraps the Phase 5 dispatch loop with post-task gate pause/resume behavior.

#### Gate boundary check is POST-TASK (D11)

After each successful task completion in the sequential loop, check if the just-completed `task_type` matches any gate's `after_task_types`. If yes, pause.

```python
# In sequential loop, AFTER dispatch + artifact collection + output chaining:
if self._is_gate_boundary(cycle, envelope.task_type):
    await self._handle_gate(run_id, cycle, envelope.task_type)
```

#### `_is_gate_boundary()` — Check if completed task_type triggers a gate

```python
def _is_gate_boundary(self, cycle: Cycle, task_type: str) -> bool:
    for gate in cycle.task_flow_policy.gates:
        if task_type in gate.after_task_types:
            return True
    return False
```

#### `_handle_gate()` — Pause, poll, resume or reject

**Data model confirmation:** Gate decision field names verified against `src/squadops/cycles/models.py`:
- `Run.gate_decisions` — `tuple[GateDecision, ...]`
- `GateDecision.gate_name` — `str` (matches gate `name` in `TaskFlowPolicy.gates`)
- `GateDecision.decision` — `str` (values: `"approved"`, `"rejected"`)
- `GateDecision.notes` — `str | None`

```python
async def _handle_gate(self, run_id, cycle, task_type):
    gate_names = [
        g.name for g in cycle.task_flow_policy.gates
        if task_type in g.after_task_types
    ]
    await self._cycle_registry.update_run_status(run_id, RunStatus.PAUSED)

    poll_interval = 2.0  # seconds
    while True:
        # D9: check cancellation between polls (same helper as dispatch loop)
        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)
        run = await self._cycle_registry.get_run(run_id)
        for gate_name in gate_names:
            for decision in run.gate_decisions:
                if decision.gate_name == gate_name:
                    if decision.decision == "approved":
                        await self._cycle_registry.update_run_status(
                            run_id, RunStatus.RUNNING
                        )
                        return  # Resume
                    elif decision.decision == "rejected":
                        raise _ExecutionError(
                            f"Gate {gate_name!r} rejected: {decision.notes}"
                        )
        await asyncio.sleep(poll_interval)
```

---

## Phase 7: Artifacts + Execution Evidence

Artifact handling is integrated into Phase 5's sequential execution loop. This phase covers verification and cleanup:

1. **Artifact metadata fields** — Each `ArtifactRef` includes: `cycle_id`, `run_id`, `task_id` (in metadata), `role` (in metadata), `created_at`
2. **Incremental persistence** — `append_artifact_refs()` called with only new refs per step (Tightening #1), not the growing list
3. **Content hashing** — SHA-256 of content bytes for dedup/verification
4. **Execution evidence** — Captured by `HandlerEvidence` in each handler's `handle()` method (Phase 1). The flow executor doesn't need separate evidence tracking — it relies on `TaskResult.execution_evidence` from the orchestrator pipeline.
5. **Interface verification** — Before implementing `_store_artifact`, confirm `ArtifactVaultPort.store(artifact: ArtifactRef, content: bytes) -> ArtifactRef` matches expectations (Discovery #12: confirmed).

---

## Phase 8: Tests

### 8.1 New: `tests/unit/capabilities/test_cycle_task_handlers.py` (~18 tests)

- Each of the 5 handlers: validates `prd` required, returns `HandlerResult(success=True)`
- Each handler: outputs contain `summary`, `role`, `artifacts` list
- Each handler: `capability_id` matches expected pinned value
- Each handler: `name` property returns non-empty string
- Validation: missing `prd` → error list contains `"'prd' is required"`
- **Tightening #11:** Prefer testing handlers via `HandlerExecutor` if the construction harness is straightforward. If `HandlerExecutor` requires too much setup, use `ExecutionContext.create()` directly but match the real invocation path as closely as possible. Check existing handler tests for the canonical pattern before writing.

### 8.2 New: `tests/unit/cycles/test_task_plan.py` (~15 tests)

- Deterministic: same inputs → same task_types in same order
- 5 envelopes produced, correct task_types in order
- Lineage: all share `correlation_id`/`trace_id`, each has unique `task_id`
- Causation chaining: step N+1's `causation_id` == step N's `task_id`
- Inputs: each envelope has `prd`, `resolved_config`, `config_hash`
- Agent resolution: `agent_id` matches profile agent for role
- Metadata: each has `step_index` and `role`

### 8.3 New: `tests/unit/cycles/test_flow_executor.py` (~28 tests)

Test with mocked `CycleRegistryPort`, `ArtifactVaultPort`, `SquadProfilePort`, and `AgentOrchestrator`:

- **Sequential happy path:** 5 tasks execute in order, run transitions queued→running→completed
- **Sequential fail-fast:** first failure → run=failed, remaining tasks skipped
- **Cancel:** `cancel_run()` stops further dispatch, run → cancelled
- **Artifact storage:** artifacts from task results stored via vault, refs appended to run
- **No duplicate refs:** each step appends only its own new refs, not the cumulative list
- **Prior outputs chaining:** downstream tasks receive upstream outputs in `inputs["prior_outputs"]`
- **Gate pause/resume (post-task):** run pauses AFTER completing the gate-triggering task, resumes on `approved`
- **Gate rejection:** `rejected` decision → run=failed
- **Cancel during gate poll:** cancellation while paused → run=cancelled
- **Constructor validation:** missing required deps → TypeError at construction (D12)
- **Port signature:** `execute_run(cycle_id, run_id, profile_id)` accepted (not old signature)
- **Tightening #12: Handler not found regression test:** submit_task with unknown `task_type` → `HandlerNotFoundError`, confirming pinned task_types don't silently regress

### 8.4 Modify: `tests/unit/cycles/test_adapters.py` (~3 tests)

- `append_artifact_refs`: appends to existing refs
- `append_artifact_refs`: run not found → `RunNotFoundError`
- `append_artifact_refs`: returns updated `Run` with new refs
- `append_artifact_refs`: de-duplicates when same ID appended twice

### 8.5 Regression

Full suite must pass:
```bash
./scripts/dev/run_new_arch_tests.sh -v
```

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/capabilities/handlers/cycle_tasks.py` | **NEW** — 5 cycle task handlers | 1 |
| `src/squadops/bootstrap/handlers.py` | **MODIFY** — register 5 new handlers | 1 |
| `adapters/noop/ports.py` | **NEW** — NoOp port implementations + `create_noop_ports_bundle()` | 2 |
| `src/squadops/api/runtime/main.py` | **MODIFY** — bootstrap orchestrator + rewire executor with all deps | 2 |
| `adapters/cycles/factory.py` | **MODIFY** — accept DI params incl. `squad_profile` for flow executor | 2 |
| `src/squadops/ports/cycles/cycle_registry.py` | **MODIFY** — add `append_artifact_refs` | 2 |
| `adapters/cycles/memory_cycle_registry.py` | **MODIFY** — implement `append_artifact_refs` (with de-dupe) | 2 |
| `src/squadops/ports/cycles/flow_execution.py` | **MODIFY** — breaking signature: `execute_run(cycle_id, run_id, profile_id)` | 3 |
| `src/squadops/api/routes/cycles/cycles.py` | **MODIFY** — `BackgroundTasks` wiring | 3 |
| `adapters/cycles/in_process_flow_executor.py` | **REPLACE** — full implementation (constructor, sequential, gates, artifacts) | 3→5→6 |
| `src/squadops/cycles/task_plan.py` | **NEW** — static task plan generator | 4 |
| `tests/unit/capabilities/test_cycle_task_handlers.py` | **NEW** — ~18 tests | 8 |
| `tests/unit/cycles/test_task_plan.py` | **NEW** — ~15 tests | 8 |
| `tests/unit/cycles/test_flow_executor.py` | **NEW** — ~28 tests | 8 |
| `tests/unit/cycles/test_adapters.py` | **MODIFY** — +4 tests | 8 |

---

## Implementation Order

Phases 1–3 MUST ship together (D7) — they must land in the same PR or be feature-flagged together. Otherwise Phase 3 will call a non-functional executor.

```
Phase 1 (handlers) → Phase 2 (bootstrap/DI) → Phase 3 (route + port signature)
         ↓                                            ↓
    [all three ship together as one atomic unit]
                                                      ↓
                                                Phase 4 (task plan)
                                                      ↓
                                                Phase 5 (executor: sequential + chaining + fail-fast + cancel)
                                                      ↓
                                                Phase 6 (gates: post-task pause/resume/reject)
                                                      ↓
                                                Phase 7 (artifacts: verification + cleanup)
                                                      ↓
                                                Phase 8 (tests: written alongside each phase)
```

---

## Verification

```bash
# Phase-by-phase unit tests
pytest tests/unit/capabilities/test_cycle_task_handlers.py -v
pytest tests/unit/cycles/test_task_plan.py -v
pytest tests/unit/cycles/test_flow_executor.py -v
pytest tests/unit/cycles/test_adapters.py -v

# Full regression suite
./scripts/dev/run_new_arch_tests.sh -v

# Manual E2E (requires docker-compose services running)
squadops cycles create play_game --profile examples/play_game/pcr.yaml
squadops runs list play_game <cycle_id>     # should show running → completed
squadops artifacts list --cycle <cycle_id>  # should show 5 artifacts
squadops gates set <cycle_id> quality-review --approve  # if gate reached
```

---

## Resolved Questions

All three open questions from rev 1 are now resolved:

1. **NoOp port implementations** → D3: Create `adapters/noop/ports.py` as a reusable module. Survey all 7 port ABCs for method signatures during Phase 2 implementation.

2. **SquadProfilePort access from executor** → D10: Inject `SquadProfilePort` into `InProcessFlowExecutor` constructor. Factory and bootstrap wiring updated accordingly.

3. **Gate boundary timing** → D11: Post-gate. Execute the task, THEN check if `task_type` appears in any gate's `after_task_types`. Aligns with field name semantics.
