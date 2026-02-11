# Cycle Execution Pipeline — Gap Analysis

**Date:** 2026-02-09
**Context:** E2E testing of `play_game` sample project
**Scope:** What exists, what's stubbed, what's missing between "API accepts cycle request" and "agents produce artifacts"

---

## Executive Summary

The cycle execution pipeline has solid infrastructure at both ends — the API/CLI layer (SIP-0064/0065) and the agent framework (BaseAgent, AgentOrchestrator, 5 roles) — but the middle layer that connects them is stubbed. Creating a cycle produces database records; agents sit idle on RabbitMQ. The flow executor, which should bridge these two worlds, logs intent and does nothing else.

The architecture is sound. Every port is defined, every adapter slot exists, the state machine is validated. This is a wiring job, not a redesign.

---

## Current State by Component

### Fully Implemented (no changes needed)

| Component | File | What It Does |
|-----------|------|--------------|
| **TaskEnvelope** | `src/squadops/tasks/models.py` | Frozen dataclass with task_id, agent_id, cycle_id, pulse_id, project_id, task_type, lineage fields (correlation/causation/trace/span), inputs, priority, timeout, metadata |
| **TaskResult** | `src/squadops/tasks/models.py` | Status (SUCCEEDED/FAILED/CANCELED), outputs dict, error, execution_evidence |
| **Run/Cycle models** | `src/squadops/cycles/models.py` | Frozen dataclasses. RunStatus: queued/running/paused/completed/failed/cancelled. CycleStatus derived from latest run. TaskFlowPolicy with mode + gates |
| **Lifecycle state machine** | `src/squadops/cycles/lifecycle.py` | `validate_run_transition()` enforces legal transitions. `derive_cycle_status()` computes cycle state from runs. `compute_config_hash()` for resolved config |
| **CycleRegistryPort** | `src/squadops/ports/cycles/cycle_registry.py` | Full ABC: create/get/list/cancel cycles, create/get/list/update_status/cancel runs, record_gate_decision (T11 single enforcement point) |
| **MemoryCycleRegistry** | `adapters/cycles/memory_cycle_registry.py` | All port methods implemented in-memory. State transitions validated, gate conflicts detected, frozen snapshots returned via `dataclasses.replace()` |
| **FlowExecutionPort** | `src/squadops/ports/cycles/flow_execution.py` | ABC with `execute_run(cycle, run, profile)` and `cancel_run(run_id)` |
| **ArtifactVaultPort** | `src/squadops/ports/cycles/artifact_vault.py` | ABC: store, retrieve, get_metadata, list_artifacts, set_baseline, get_baseline, list_baselines |
| **FilesystemArtifactVault** | `adapters/cycles/filesystem_artifact_vault.py` | Full implementation — stores files on disk with metadata JSON sidecars |
| **ProjectRegistryPort** | `src/squadops/ports/cycles/project_registry.py` | Read-only: list_projects, get_project |
| **ConfigProjectRegistry** | `adapters/cycles/config_project_registry.py` | Loads from `config/projects.yaml` |
| **SquadProfilePort** | `src/squadops/ports/cycles/squad_profile.py` | list/get/get_active/set_active/resolve_snapshot |
| **ConfigSquadProfile** | `adapters/cycles/config_squad_profile.py` | Loads from config YAML |
| **BaseAgent** | `src/squadops/agents/base.py` | Abstract `handle_task(envelope) -> TaskResult`. Lifecycle hooks: on_cycle_start/end, on_pulse_start/end, on_agent_start/stop. Full DI via PortsBundle |
| **AgentOrchestrator** | `src/squadops/orchestration/orchestrator.py` | `submit_task(envelope)` and `submit_batch(envelopes)` with routing by role. SIP-0061 LangFuse tracing. HandlerExecutor bridge. Agent registration |
| **HandlerExecutor** | `src/squadops/orchestration/handler_executor.py` | Executes tasks with timeout, wraps results |
| **API routes** | `src/squadops/api/routes/cycles/` | Full CRUD: projects, cycles, runs, gates, artifacts, profiles. Auth middleware (SIP-0062) |
| **CLI** | `src/squadops/cli/` | All commands: projects, cycles, runs, gates, artifacts, profiles, login/logout/whoami |
| **Factory** | `adapters/cycles/factory.py` | Provider-based creation for all 5 ports. Extensible for future adapters (postgres, prefect, etc.) |

### Stubbed (exists but doesn't do real work)

| Component | File | Current Behavior | What It Should Do |
|-----------|------|------------------|-------------------|
| **InProcessFlowExecutor** | `adapters/cycles/in_process_flow_executor.py` | `execute_run()` logs one line, adds run_id to a set. `cancel_run()` logs and removes from set. 46 lines total. | Interpret TaskFlowPolicy mode, construct TaskEnvelopes, dispatch to AgentOrchestrator, update run status, handle gate pauses, track artifacts |

### Missing (no code exists)

| Gap | Description |
|-----|-------------|
| **Route → FlowExecutor call** | `cycles.py:create_cycle()` creates Cycle + Run records but never calls `flow_executor.execute_run()`. The run stays `queued` forever. |
| **TaskEnvelope generation from PRD** | Nothing translates a cycle's PRD + config into concrete TaskEnvelope objects for agents. What tasks should Nat do? What should Neo build? This mapping doesn't exist. |
| **Gate pause/resume loop** | When TaskFlowPolicy has gates, the executor should pause (run status → `paused`), wait for gate decision via API, then resume. No implementation. |
| **Run status progression** | No code calls `registry.update_run_status()` during execution. Run status never moves from `queued`. |
| **Artifact collection from results** | TaskResult outputs are never inspected for artifacts. `artifact_vault.store()` is never called from the execution path. Run.artifact_refs stays empty. |
| **Agent lifecycle hook invocation** | BaseAgent's `on_cycle_start()`, `on_pulse_start()`, etc. are never called from the execution pipeline. |
| **Project CRUD** | ProjectRegistryPort is read-only. No `create_project()` method, no POST endpoint, no CLI command. Projects must be added to `config/projects.yaml` manually. |

---

## The Disconnected Pipeline

```
CLI / API                    Flow Executor              Orchestrator              Agents
─────────                    ─────────────              ────────────              ──────
squadops cycles create
        │
        ▼
POST /api/v1/.../cycles
        │
        ▼
Create Cycle + Run
(status = "queued")
        │
        ▼
Return response ◄─── STOP. Nothing calls flow_executor.execute_run()
                              │
                              ▼
                     [STUB: logs only]      AgentOrchestrator        BaseAgent
                                            .submit_task()           .handle_task()
                                            .submit_batch()          .on_cycle_start()
                                            .route_task()            .on_cycle_end()
                                                   │                       │
                                                   └───────────────────────┘
                                                   These work but nobody calls them
                                                   from the cycle execution path
```

---

## Detailed Gap Analysis

### Gap 1: Route Does Not Call Flow Executor

**File:** `src/squadops/api/routes/cycles/cycles.py` lines 28-111

After `create_cycle()` persists the Cycle and Run, it returns a response immediately. The `get_flow_executor()` DI getter exists in `deps.py` and is initialized at startup, but is never imported or called from the cycles route.

**What's needed:** After `create_run()` succeeds, spawn `flow_executor.execute_run(cycle, run, profile)`. This should be async (background task or queue-dispatched) so the API returns immediately with `status: "queued"` and the run progresses asynchronously.

### Gap 2: Flow Executor Is a Stub

**File:** `adapters/cycles/in_process_flow_executor.py` (46 lines)

```python
async def execute_run(self, cycle: Cycle, run: Run, profile: SquadProfile) -> None:
    logger.info("Flow executor: starting run %s for cycle %s...", run.run_id, cycle.cycle_id)
    self._active_runs.add(run.run_id)
```

The comment on line 4-6 states: *"For v0.9.3 this is a stub that logs intent. Full orchestrator integration will be wired when AgentOrchestrator is updated to accept Cycle/Run context."*

**What's needed:** A real implementation that:
1. Updates run status: queued → running
2. Interprets `cycle.task_flow_policy.mode`:
   - **sequential**: submit tasks one at a time, await each
   - **fan_out_fan_in**: submit all, await all
   - **fan_out_soft_gates**: submit groups, pause at gate boundaries
3. Constructs TaskEnvelope objects from cycle config + PRD
4. Dispatches to AgentOrchestrator
5. Collects TaskResults and stores artifacts
6. Updates run status: running → completed/failed
7. Handles gate pauses: running → paused → (await decision) → running

### Gap 3: No TaskEnvelope Generation from Cycle Config

This is the most conceptually significant gap. When a cycle is created for `play_game` with a PRD describing Tic-Tac-Toe, *something* must translate that into concrete tasks:

- Task for **Nat** (strategy): "Analyze PRD, produce architecture document"
- Task for **Neo** (dev): "Implement code per architecture"
- Task for **Eve** (QA): "Write and run tests"
- Task for **Data** (analytics): "Produce metrics report"
- Task for **Max** (lead): "Orchestrate and review"

Today, nothing does this translation. The TaskFlowPolicy defines *mode* (sequential/fan_out) and *gates* (pause points), but not *what tasks to run*.

**Options:**
- **Static task templates**: Each cycle type has a predefined task sequence (strategy → dev → qa → analytics → review)
- **PRD-driven task generation**: An LLM (Max as lead) reads the PRD and generates the task plan
- **PCR-declared tasks**: The PCR YAML explicitly lists task types and their ordering

### Gap 4: AgentOrchestrator Has No Cycle Context

`AgentOrchestrator.submit_task()` accepts only a `TaskEnvelope` — it doesn't know about cycles, runs, or gates. This means:

- It can't update `CycleRegistryPort` with progress
- It can't enforce cycle-level business rules
- It can't trigger gate pauses

**What's needed:** Either:
- Pass cycle context into the orchestrator (modify signatures)
- Or keep the orchestrator stateless and have the flow executor handle all cycle lifecycle concerns (orchestrator just executes tasks, flow executor manages the cycle state machine around it)

The second option is cleaner — it preserves the orchestrator's single responsibility and keeps cycle concerns in the flow executor.

### Gap 5: Agent Entrypoint Only Handles Chat Messages

**File:** `src/squadops/agents/entrypoint.py`

`AgentRunner._consume_tasks()` monitors the `{agent_id}_comms` queue and only handles `action="comms.chat"`. There's no handler for task envelope messages.

**What's needed:** For in-process execution (InProcessFlowExecutor), this may not matter — the flow executor calls the orchestrator directly, which calls agent.handle_task() in-process. For distributed execution (future), the entrypoint would need a task consumption handler.

### Gap 6: Memory-Only Cycle Registry

`MemoryCycleRegistry` stores everything in Python dicts. Server restart = all cycles lost.

**Impact for E2E testing:** Acceptable for now. The play_game test runs in a single session. PostgreSQL adapter is a 1.0 hardening concern, not a blocker for E2E validation.

### Gap 7: Project CRUD

`ProjectRegistryPort` has no `create_project()` method. Projects are config-seeded only (`config/projects.yaml`).

**Impact for E2E testing:** Already mitigated — `play_game` is registered in `config/projects.yaml`. Full CRUD is a 1.0 concern (covered by SIP-0094 proposal).

---

## Recommended Implementation Order

### Phase 1: Wire the Call Site (smallest change, proves the path)
- In `cycles.py:create_cycle()`, after persisting, spawn `flow_executor.execute_run()`
- Use FastAPI `BackgroundTasks` to run async without blocking the response

### Phase 2: Implement Flow Executor (core of the gap)
- Build the sequential execution path first (play_game uses sequential mode)
- Flow executor: update run status → build task list → submit to orchestrator → collect results → update run status
- Keep orchestrator signatures unchanged — flow executor wraps cycle lifecycle around it

### Phase 3: Task Generation Strategy
- Start simple: static task template for sequential mode (strategy → dev → qa → analytics → review)
- PRD content goes into `TaskEnvelope.inputs["prd"]`
- Each agent's `handle_task()` implementation uses the PRD to do its work

### Phase 4: Gate Decision Loop
- Flow executor pauses at gate boundaries (run status → paused)
- API gate decision endpoint already works (record_gate_decision in registry)
- Flow executor polls or uses asyncio.Event to resume

### Phase 5: Artifact Collection
- After each task completes, inspect TaskResult.outputs for artifact data
- Store via artifact_vault.store()
- Append artifact_refs to run record

### Phase 6: Project CRUD (if needed for 1.0)
- Add `create_project()` to ProjectRegistryPort
- Add POST endpoint and CLI command
- Can defer to SIP-0094

---

## Files That Need Changes

| File | Change | Phase |
|------|--------|-------|
| `src/squadops/api/routes/cycles/cycles.py` | Add flow_executor.execute_run() call after create_run() | 1 |
| `adapters/cycles/in_process_flow_executor.py` | Replace stub with real implementation | 2 |
| (new) task generation module | Static task templates or PRD-driven generation | 3 |
| `adapters/cycles/in_process_flow_executor.py` | Gate pause/resume loop | 4 |
| `adapters/cycles/in_process_flow_executor.py` | Artifact collection from TaskResult | 5 |
| `src/squadops/ports/cycles/project_registry.py` | Add create_project() (optional) | 6 |
| `src/squadops/api/routes/cycles/projects.py` | Add POST endpoint (optional) | 6 |
| `src/squadops/cli/commands/projects.py` | Add create command (optional) | 6 |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Memory-only registry loses data on restart | Low (E2E only) | Acceptable for testing; Postgres adapter for 1.0 |
| Static task templates are too rigid | Medium | Start static, evolve to PRD-driven generation |
| Gate polling is inefficient | Low | asyncio.Event or callback pattern; polling is fine for v1 |
| Agent handle_task() implementations may not exist for all task types | High | Need to verify each agent role has a working handler |
| In-process execution doesn't test RabbitMQ path | Medium | Validates core logic; distributed execution is a separate concern |

---

## Conclusion

The platform has ~90% of the infrastructure built. The remaining ~10% is the coordination logic in the flow executor that bridges the API layer to the agent framework. Phases 1-3 are the minimum viable path to see play_game execute end-to-end. Phases 4-5 complete the production-grade loop. Phase 6 is polish.
