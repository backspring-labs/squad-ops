# SIP-PREFECT-PULSE-CONTEXT — Prefect Integration and Pulse Context Framework (0.8.x)

## Status
**Draft** — Unnumbered (awaiting maintainer acceptance)  
**Target Version:** 0.8.x  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data  

---

# 1. Purpose and Intent

This SIP defines how SquadOps:

- Integrates **Prefect** as an optional **execution backend** for task orchestration, and  
- Introduces a formal **Pulse Context** abstraction between Agent Context and Cycle Context.

The intent is to:

- Replace ad hoc, SQL-centric task execution logic with a pluggable **Task Adapter** that can call Prefect without changing existing HTTP APIs or data models.
- Define Pulse Context as the **unit of coordinated work** across multiple tasks and agents inside a Cycle.
- Ensure that future enhancements—such as layered prompting and richer Pulse semantics—can be implemented **without redesigning the Prefect integration**.

This SIP specifies **what must exist and how components interact**, not the internal implementation details of Prefect itself.

---

# 2. Background

In 0.7.x, SquadOps:

- Executes tasks directly via SQL-backed models and inline Python orchestration.
- Has a defined **Cycle Data Store** SIP but only an informal notion of “pulses” as groups of tasks.
- Has no formal separation between:
  - The **execution engine** (how tasks are scheduled and run), and
  - The **governance and context model** (Cycle / Pulse / Agent context).

This leads to:

- Limited observability and retry semantics for long-running multi-task flows.
- Difficulty swapping orchestration engines or running on different infrastructure.
- Ambiguity around how a “pulse” should be represented and persisted.

Prefect provides a robust orchestration engine, but it must be integrated in a way that:

- Preserves **SquadOps DB and APIs as the golden source of truth**.
- Keeps **Pulse Context** a first-class SquadOps concept, not something owned by Prefect.
- Avoids entangling LLM prompt construction with the execution backend.

---

# 3. Problem Statements

This SIP addresses the following problems:

1. **Execution engine is tightly coupled to SQL and inline code.**  
   There is no clean abstraction for plugging in an external orchestrator such as Prefect.

2. **Pulses lack a formal, shared context model.**  
   Agents conceptually operate in “pulses,” but there is no explicit PulseContext schema or storage convention.

3. **Orchestration and context are entangled conceptually.**  
   Without clear separation:
   - Execution backends risk absorbing context or prompt-construction responsibilities.
   - Future changes to Pulse semantics could force redesigns of the orchestration layer.

4. **Runtime APIs must remain stable.**  
   Existing FastAPI endpoints and task/flow models should not change shape just because Prefect is introduced.

This SIP defines a design that cleanly separates **execution** from **context and prompting**, so that Prefect can be integrated now and Pulse Context can be expanded later without reworking the adapter.

---

# 4. Scope

## 4.1 Included

- Definition of a **Prefect-based Task Adapter** (`PrefectTasksAdapter`) that implements the existing Task Adapter interface.
- Definition of **Pulse Context** as a SquadOps-owned abstraction between Agent and Cycle Context.
- Integration points between:
  - Prefect flows/runs, and
  - SquadOps Cycles, Pulses, Tasks, and the Cycle Data Store.
- Requirements on:
  - File locations,
  - Adapter behavior,
  - Backend selection,
  - Data flow.

## 4.2 Not Included

- Detailed design of layered prompting or prompt templates across Project → Cycle → Pulse → Task → Agent.  
  (This is reserved for a dedicated Pulse Prompting SIP.)
- Changes to the public FastAPI contract beyond what is strictly required to surface Prefect-run state via existing models.
- Any reliance on Prefect-specific features that would make it impossible to support a different orchestration engine in the future.

---

# 5. Design Overview

This SIP introduces two cooperating pieces:

1. **PrefectTasksAdapter (Execution Backend)**  
   - Lives at `agents/tasks/prefect_adapter.py`.  
   - Implements the existing `TaskAdapterBase` interface.  
   - Translates SquadOps Task/Flow concepts into Prefect flows and tasks.  
   - Writes all execution state back into SquadOps models and DB.  
   - Does **not** perform any LLM prompt construction or Pulse semantics.

2. **Pulse Context (Context Layer)**  
   - Lives at `agents/context/pulse_context.py`.  
   - Represents the shared context for a **pulse**: a cluster of related tasks and agents within a Cycle.  
   - Is persisted under the **Cycle Data Store** hierarchy:
     `cycle_data/{cycle_id}/pulses/{pulse_id}/`.  
   - Is injected into agent invocations and capabilities by the runtime/context builder, not by Prefect.

Execution and context are deliberately separated:

- Prefect is a **stateless orchestrator from SquadOps’ perspective**: it runs what it is told, and reports back state.
- Pulse Context is a **SquadOps-native concept** used to coordinate multi-agent work; it may be used for layered prompting later, but that logic remains in the runtime and context builder layers, not in the adapter.

---

# 6. Functional Requirements

## 6.1 Task Adapter Abstraction

- A base interface `TaskAdapterBase` MUST exist and remain the canonical abstraction for orchestration backends.
- The scheduler/executor layer MUST only communicate with backends through this interface.
- Existing SQL-backed implementations (e.g., `SqlTasksAdapter`) MUST remain available.

### 6.1.1 PrefectTasksAdapter

A new implementation `PrefectTasksAdapter` MUST be added:

- Location: `agents/tasks/prefect_adapter.py`.
- Inherits from `TaskAdapterBase`.
- Implements, at minimum, the following methods (names illustrative, exact signatures as defined by the existing adapter interface):

  - `create_task(task_create: TaskCreate) -> Task`
  - `update_task_state(task_id: str, state: TaskState) -> Task`
  - `add_artifact(task_id: str, artifact: TaskArtifact) -> None`
  - `add_dependency(task_id: str, depends_on: list[str]) -> None`
  - `list_tasks_for_pid(pid: str) -> list[Task]`
  - `list_tasks_for_cycle_id(cycle_id: str) -> list[Task]`
  - `get_task_status(task_id: str) -> TaskStatus`
  - `update_task_status(task_id: str, status: TaskStatusUpdate) -> TaskStatus`
  - `get_task_summary(task_id: str) -> TaskSummary`

  - Flow-level methods (if defined in the base interface), e.g.:
    - `create_flow(ecid: str, metadata: FlowMetadata) -> FlowRun`
    - `get_flow(flow_id: str) -> FlowRun`
    - `list_flows(ecid: str) -> list[FlowRun]`
    - `update_flow(flow_id: str, updates: FlowUpdate) -> FlowRun`

- `PrefectTasksAdapter` MUST be treated as an **internal detail**. No external HTTP or CLI surface may refer to it directly.

### 6.1.2 Backend Selection

- A runtime configuration (e.g., environment variable `TASKS_BACKEND`) MUST control which adapter implementation is used:
  - `"sql"` → SQL-backed adapter.
  - `"prefect"` → `PrefectTasksAdapter`.
- The scheduler/executor code MUST obtain an adapter instance via a **registry/factory**, not through direct imports of a specific implementation.
- Existing FastAPI endpoints MUST continue to:
  - Use the existing Task/Flow models.
  - Make no assumptions about the underlying backend.

---

## 6.2 Prefect as Execution Backend Only

To avoid coupling execution with context or prompting, the following requirements apply:

- `PrefectTasksAdapter` MUST NOT:
  - Construct LLM prompts.
  - Perform dynamic prompt injection.
  - Read or write Agent Context or Pulse Context directly.
- Instead, it MUST:
  - Accept opaque identifiers such as `cycle_id` (ECID), `pulse_id`, and `agent_id` as part of the `TaskCreate` and Flow metadata.
  - Use these IDs only for logging, traceability, and writing back execution state and artifacts into the SquadOps DB and Cycle Data Store.

The **source of truth** for:

- Task definitions,  
- Task state,  
- Flow/ECID metadata, and  
- Pulse membership  

MUST remain the SquadOps models and DB.  
Prefect’s own internal state is considered an **implementation detail** and MUST NOT become the primary API surface.

---

## 6.3 State Mapping and Persistence

### 6.3.1 State Mapping

- A mapping MUST be defined between Prefect states and SquadOps `TaskState` values, e.g.:

  ```python
  PREFECT_TO_SQUADOPS_STATE = {
      "PENDING": "PENDING",
      "RUNNING": "RUNNING",
      "COMPLETED": "SUCCEEDED",
      "FAILED": "FAILED",
      "CANCELLED": "CANCELLED",
      # etc., as needed.
  }
  ```

- The inverse mapping (`SQUADOPS_TO_PREFECT_STATE`) MAY be used for control operations (e.g., cancellation), where applicable.

### 6.3.2 Persistence

- When a Prefect flow or task run is created, the adapter MUST:
  - Store the Prefect run ID in the corresponding SquadOps Task/Flow record.
  - Persist any relevant runtime metadata into the existing Task/Flow models (e.g., start/end times, state, error messages).
- The adapter MUST NOT bypass the Task/Flow models to read or write state directly from Prefect’s internal database for external consumption.
- `/tasks/*` and any `/flows/*` or `/cycles/*` endpoints MUST continue to read from SquadOps DB models, which are kept in sync via the adapter.

---

## 6.4 Pulse Context

### 6.4.1 Definition

A **Pulse** is a coherent unit of work inside a Cycle, typically:

- A group of related tasks,
- Often involving multiple agents, and
- Aligned to a short-term objective (e.g., “Implement Prefect adapter interface,” “Run WarmBoot calibration,” etc.).

**Pulse Context** is the shared context object that describes this unit of work.

### 6.4.2 PulseContext Schema (Conceptual)

A `PulseContext` structure MUST, at minimum, support the following fields (names indicative):

- `pulse_id: str` — unique within a given Cycle.
- `cycle_id: str` — the ECID / Cycle identifier.
- `name: str` — human-readable label.
- `description: str` — short description of the pulse objective.
- `agents_involved: list[str]` — agent IDs or roles participating in this pulse.
- `task_ids: list[str]` — task identifiers associated with this pulse.
- `artifacts: dict[str, Any]` — references to artifacts produced/consumed within the pulse (paths, IDs, etc.).
- `constraints: dict[str, Any]` — optional constraints, e.g., time bounds, guards, or resource limits.
- `acceptance_criteria: dict[str, Any]` — optional criteria describing when the pulse is “done”.
- `metadata: dict[str, Any]` — free-form metadata for future extensions.
- `created_at`, `updated_at` timestamps.

The concrete data model MAY be implemented as:

- A Python class (`PulseContext`),
- A Pydantic model,
- Or a typed dictionary,

As long as these fields are representable in the Cycle Data Store and usable by the runtime.

### 6.4.3 Storage in Cycle Data Store

- Pulse Context MUST be persisted under the Cycle Data Store hierarchy as:

  ```text
  cycle_data/{cycle_id}/pulses/{pulse_id}/pulse_context.json
  ```

- Additional pulse-scoped artifacts MAY be stored alongside, e.g.:

  ```text
  cycle_data/{cycle_id}/pulses/{pulse_id}/artifacts/*
  ```

- The Cycle Data Store remains the canonical location for Pulse Context and its artifacts.

### 6.4.4 Runtime Integration

- A module `agents/context/pulse_context.py` MUST provide functions and/or a class to:
  - Create a new `PulseContext`.
  - Load an existing `PulseContext` from the Cycle Data Store.
  - Update and persist changes to `PulseContext`.
- The runtime/context builder MUST:
  - Attach the relevant `PulseContext` to agent invocations that participate in that pulse.
  - Pass PulseContext (or a derived, compact representation) into capability methods as a structured object, not as arbitrary appended prompt text.

### 6.4.5 Separation from Prompt Construction

- This SIP does **not** define how prompt templates are built for LLM calls.
- However, it explicitly requires that:
  - `PrefectTasksAdapter` does not construct prompts.
  - Pulse Context is **not owned by Prefect** and is not required for Prefect integration.
  - Future work on layered prompting can rely on `PulseContext` and the Cycle Data Store without requiring changes to the Prefect adapter.

---

# 7. Non-Functional Requirements

- **Backward Compatibility:**  
  - Existing HTTP APIs and Task/Flow models MUST remain compatible.  
  - Switching between `sql` and `prefect` backends must not require client changes.

- **Swappability:**  
  - Prefect integration MUST be isolated such that a different backend (or returning to SQL-only) can be implemented by adding another Task Adapter without rewriting orchestration logic.

- **Performance:**  
  - Task and flow orchestration with Prefect MUST introduce no more than a reasonable constant overhead relative to direct SQL execution, considering network and scheduling costs.

- **Observability:**  
  - Prefect run IDs, states, and timing information MUST be visible via existing Task/Flow views, either directly or through mapped fields.

- **Resilience:**  
  - Failures in Prefect MUST be surfaced cleanly through SquadOps Task/Flow state (e.g., FAILED) with accessible error messages in Task/Flow metadata or artifacts.

---

# 8. Implementation Considerations

- Adapter implementation SHOULD:
  - Use Prefect’s official client APIs.
  - Abstract Prefect-specific details behind helper functions to ease future backend substitution.
- Error handling SHOULD:
  - Map Prefect exceptions to well-defined SquadOps error codes or messages.
  - Avoid leaking Prefect-specific stack traces beyond Task/Flow metadata.
- The runtime configuration for backend selection SHOULD:
  - Default to the existing SQL adapter when configuration is absent.
  - Be overrideable per environment (e.g., local vs staging vs production).

---

# 9. API and Data Contracts

- No new public HTTP endpoints are required.  
- Existing endpoints that list or query tasks/flows MUST:

  - Continue to accept the same parameters.
  - Continue to return the same models.
  - Internally rely on the Task Adapter (SQL or Prefect) to resolve state.

- Task and Flow models MAY gain fields to store Prefect run metadata (e.g., `prefect_flow_run_id`, `prefect_task_run_id`), but these SHOULD be treated as optional implementation details rather than required inputs from clients.

---

# 10. Executive Summary — What Must Be Built

1. **PrefectTasksAdapter implementation**
   - Located at `agents/tasks/prefect_adapter.py`.
   - Implements `TaskAdapterBase`.
   - Uses Prefect flows and tasks to execute SquadOps tasks.
   - Maps Prefect state ↔ SquadOps TaskState.
   - Writes all state back into Task/Flow models.

2. **Backend selection mechanism**
   - Registry/factory to choose between SQL and Prefect adapters based on configuration.
   - No change to external HTTP contracts.

3. **Pulse Context module**
   - Located at `agents/context/pulse_context.py`.
   - Defines `PulseContext` structure and read/write helpers.
   - Persists PulseContext under `cycle_data/{cycle_id}/pulses/{pulse_id}/`.

4. **Runtime integration hooks**
   - Orchestration layer uses Task Adapter abstraction only.
   - Runtime/context builder loads PulseContext and passes it into agent capabilities where appropriate.

5. **Separation of concerns**
   - Prefect remains a pure execution backend.
   - Pulse Context and future layered prompting remain under SquadOps runtime and context management.

---

# 11. Definition of Done

- [ ] `PrefectTasksAdapter` implemented and wired into the Task Adapter registry.  
- [ ] Backend selection via configuration is functioning (`sql` vs `prefect`).  
- [ ] All existing Task/Flow HTTP endpoints operate unchanged with both backends.  
- [ ] Prefect flow/task runs are created and linked to Task/Flow records with run IDs.  
- [ ] Task/Flow state is correctly mapped from Prefect states and stored in SquadOps DB.  
- [ ] `PulseContext` module exists and can create/load/update Pulse Context in the Cycle Data Store.  
- [ ] At least one end-to-end Cycle using Prefect and Pulse Context has been executed successfully.  
- [ ] Switching off Prefect (back to SQL-only) requires configuration change only, with no code changes to clients.

---

# 12. Appendix

*(None for this version.)*
