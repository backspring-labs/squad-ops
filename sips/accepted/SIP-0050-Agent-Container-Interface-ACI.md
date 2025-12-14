---
sip_uid: 01KC6VW361J91NZR3C27074XDE
sip_number: 50
title: Agent Container Interface (ACI) – Clean Specification
status: accepted
author: Unknown
approver: null
created_at: '2025-12-09T14:30:00Z'
updated_at: '2025-12-12T00:00:00.000000Z'
original_filename: SIP-AGENT-CONTAINER-INTERFACE.md
---
# SIP-AGENT-CONTAINER-INTERFACE  
## Agent Container Interface (ACI) – Clean Specification

## 1. Summary
This SIP defines the **Agent Container Interface (ACI)**: the contract between the **SquadOps runtime** and a **single agent container**. It specifies how containers:
- Receive and execute **tasks**
- Report **results and errors**
- Maintain and expose **lifecycle state**
- Emit **heartbeats** for health and crash detection
- Support **observability and lineage** through structured events and lifecycle hooks

This SIP intentionally **avoids implementation details** (language, framework, transport). It focuses solely on the behavioral contract.

---

## 2. Motivation
SquadOps requires consistent, predictable behavior across agents. Without a shared interface:
- Observability breaks
- Health detection becomes unreliable
- Containers behave inconsistently across environments
- Scaling to multi-agent and multi-host setups becomes fragile

ACI gives SquadOps a **stable boundary** between runtime and containers so agents can evolve independently without breaking orchestration.

### 2.1 Roadmap Alignment
ACI establishes the baseline contract for SquadOps evolution:
- **0.8.x**: ACI baseline with heartbeats, lifecycle, and task handling used by Prefect-based flows, Cycle Data Store, and Health Dashboard
- **0.8B (Prompt/Memory SIP)**: Builds on ACI by defining how prompts and memory are constructed inside tasks, without changing ACI
- **0.9.x (LangFuse, Keycloak, SOC)**: Leverages ACI for reliable telemetry, traceability, and SOC visualizations
- **1.0**: ACI is assumed stable and mandatory for all production-ready agents, with full Continuum observability support

---

## 3. Scope and Non-Goals

### 3.1 In Scope
- What containers must **accept**, **produce**, and **expose**
- How the runtime **assigns work** and **reads state**
- Heartbeat-driven health detection
- Integration with the **Agent Lifecycle SIP**
- Conceptual definition of a **Task Envelope**
- **Observability and lineage** support through lifecycle hooks and structured events
- Mandatory lineage fields for traceability and causal chain reconstruction

### 3.2 Out of Scope
- Any specific code structure, function signatures, or transport APIs
- Chat protocol design (treated as a task for now)
- Background workers (covered by a future SIP)
- Ping/pong (deferred)
- Scaling, autoscaling, or distributed container scheduling
- Detailed Continuum-specific observability requirements (see `ACI_CONTINUUM_ADDENDUM.md` for comprehensive Continuum integration guidance)

---

## 4. Related Documents
- **SIP-AGENT-LIFE-CYCLE**  
- **SIP_CYCLE_DATA_STORE**  
- **Health Dashboard Spec**
- **ACI_CONTINUUM_ADDENDUM.md** (for detailed Continuum observability requirements and Continuum-specific integration guidance)

ACI must be consistent with these.

---

## 5. Core Concepts

### 5.1 Agent Container
A standalone process hosting one logical agent. It:
- Receives tasks
- Executes them
- Returns results
- Maintains lifecycle state
- Emits heartbeats

### 5.2 Runtime
The SquadOps orchestration layer that:
- Assigns tasks
- Tracks task progress
- Reads lifecycle + health
- Updates UI surfaces (Health Dashboard, SOC)

### 5.3 Lifecycle State
Lifecycle is defined in the separate lifecycle SIP:  
`OFFLINE, STARTING, READY, WORKING, BLOCKED, CRASHED, STOPPING`

ACI defines **how this state is exposed**, not what the states mean.

### 5.4 Lineage Fields
For observability, traceability, and causal chain reconstruction, ACI requires the following lineage identifiers:

- **`project_id`**: Identifies the project context
- **`cycle_id`**: Identifies the execution cycle
- **`pulse_id`**: Identifies the pulse within a cycle
- **`task_id`**: Identifies the specific task (nullable until task creation)
- **`agent_id`**: Identifies the agent container
- **`correlation_id`**: Stable identifier across cycle/pulse/task lineage for correlation
- **`causation_id`**: Immediate parent event/message/decision that caused this event
- **`trace_id`**: Distributed tracing identifier (if tracing enabled)
- **`span_id`**: Current span identifier (if applicable)

These fields must be generated or propagated consistently. If an ID is not yet available (e.g., `task_id` before task creation), ACI must generate a placeholder or explicitly mark it as `null` and update it at the earliest valid point. Silent omission is not permitted.

### 5.5 Lifecycle Hooks
ACI defines lifecycle hooks as interception points where containers can emit structured events. These hooks are required even if initial implementations are no-ops. See Section 8.4 for details.

---

## 6. Responsibilities

### 6.1 Agent Container Responsibilities
The container **MUST**:
- Accept task envelopes
- Execute tasks
- Return results or errors
- Maintain its lifecycle state
- Emit heartbeats with lifecycle
- Survive task-level failures without crashing
- Propagate lineage fields (project_id, cycle_id, pulse_id, task_id, agent_id, correlation_id, causation_id, trace_id, span_id) through all lifecycle events
- Emit structured events at lifecycle hooks (see Section 8.4)

The container **MAY**:
- Execute multiple tasks concurrently using **internal background workers**, provided:
  - Each `task_id` receives a terminal result
  - Heartbeats + lifecycle accurately reflect whether new work can be accepted

### 6.2 Runtime Responsibilities
The runtime **MUST**:
- Deliver tasks only to containers in a valid accepting state
- Record task output in the Cycle Data Store
- Monitor heartbeats to determine health
- Update UI surfaces

---

## 7. Task Handling Contract

### 7.1 Task Envelope (Conceptual)
Each task sent to a container includes:
- `task_id`
- `agent_id`
- `cycle_id`, `pulse_id`
- `project_id` (for lineage and Continuum compatibility)
- `task_type`
- `inputs` (JSON-compatible)
- Optional: `priority`, `timeout`, `metadata`
- **Lineage fields** (mandatory for observability):
  - `correlation_id` (stable across cycle/pulse/task lineage)
  - `causation_id` (immediate parent event/message/decision)
  - `trace_id` (if tracing enabled)
  - `span_id` (current span, if applicable)

### 7.2 Execution Semantics
Upon receiving a task, the container:
1. Checks lifecycle and readiness
2. Executes the task
3. Returns:
   - `task_id`
   - `status` (SUCCEEDED / FAILED / CANCELED)
   - `outputs` or `error`

### 7.3 Task Cancellation (Optional)
If supported, containers may honor cancellation requests. Otherwise they must clearly document their behavior.

---

## 8. Lifecycle Integration

### 8.1 Required Lifecycle Exposure
Containers must surface their lifecycle state via:
- Heartbeats
- Any implementation-specific status endpoint or message

### 8.2 Error vs CRASHED
- A task failure is **not** a container crash
- A fatal container error results in lifecycle=**CRASHED**
- If the process stops, the runtime infers OFFLINE via stale heartbeats

### 8.3 Failure Modes and Risks

#### Failure Modes
- **Missing or Stale Heartbeats**  
  - Risk: Agent appears healthy when it is not.  
  - Mitigation: Runtime marks agents as not reachable after a heartbeat grace period.

- **Misreported Lifecycle State**  
  - Risk: Runtime assigns work to agents that are not actually READY.  
  - Mitigation: Tests must verify lifecycle transitions; logs should reflect transitions clearly.

- **Mismatched `task_id` in Results**  
  - Risk: Task results are misattributed.  
  - Mitigation: Runtime must reject or flag mismatched task IDs.

- **Containers That Crash on Task Errors**  
  - Risk: One bad input brings down the entire agent.  
  - Mitigation: Strong separation of task-level errors vs container-level failures in both design and tests.

- **Missing Lineage Fields**  
  - Risk: Cannot reconstruct causal chains or correlate events across the system.  
  - Mitigation: ACI requires all lineage fields to be present or explicitly null; silent omission is not permitted.

#### Risks
- **Partial Adoption Risk**  
  - If only some agents implement ACI correctly, behavior across the squad may be inconsistent.

- **Overfitting to a Single Transport**  
  - Risk of accidentally binding ACI to HTTP-only or queue-only semantics. ACI must remain transport-agnostic.

- **Test Coverage Gaps**  
  - If ACI is not backed by integration tests, regressions may go unnoticed until late. All test categories in Section 12 must pass.

### 8.4 Lifecycle Hooks
ACI requires containers to expose lifecycle hooks **even if initial implementations are no-ops**. These hooks provide guaranteed interception points for instrumentation and observability.

#### Required Hooks
- **Agent Lifecycle**:
  - `on_agent_start`
  - `on_agent_stop`
- **Cycle Lifecycle**:
  - `on_cycle_start`
  - `on_cycle_end`
- **Pulse Lifecycle**:
  - `on_pulse_start`
  - `on_pulse_end`
- **Task Lifecycle**:
  - `on_task_created`
  - `on_task_start`
  - `on_task_complete`
  - `on_task_failed`
- **Failure & Exception**:
  - `on_failure`
  - `on_exception`

#### Hook Context Structure
Each hook must receive a **context object** containing the required lineage fields (see Section 5.4):
- `project_id`, `cycle_id`, `pulse_id`, `task_id` (nullable until available)
- `agent_id`
- `correlation_id`, `causation_id`
- `trace_id`, `span_id` (if tracing enabled)

#### Implementation Notes
- Hooks may be no-ops in initial implementations but must be callable
- Hook execution must be **asynchronous and non-blocking** to avoid impacting task execution
- For detailed Continuum-specific requirements, see `ACI_CONTINUUM_ADDENDUM.md`

---

## 9. Heartbeats and Health

### 9.1 Heartbeat Requirements
Heartbeats include:
- `agent_id`
- `container_id`
- `lifecycle_state`
- `timestamp`
- Optional metrics

### 9.2 Health Dashboard Use
The dashboard shows lifecycle + reachability.  
Stale heartbeats result in **not reachable** state.

---

## 10. Logging & Traceability (Light Guidance)
Containers **should**:
- Include task_id, agent_id, and cycle_id in logs
- Log lifecycle transitions
- Include correlation_id where provided

### 10.1 Observability & Lineage
ACI requires containers to support observability through structured events and lineage tracking.

#### Structured Event Emission
At each lifecycle hook (see Section 8.4), containers must be capable of emitting a **structured event** with:
- `event_type` (e.g., `task_started`, `pulse_failed`)
- `timestamp`
- Full lineage identity set (all fields from Section 5.4)
- Optional metadata payload

Events must be suitable for:
- SOC Ledger ingestion
- Trace/log correlation
- Causal graph reconstruction

Event emission must be **asynchronous and non-blocking** to avoid impacting task execution.

#### Causation Rules
ACI enforces the following causation guarantees:
1. Every emitted event must reference a valid `causation_id`, except:
   - Root events (e.g., project initialization)
2. Task creation events must list the triggering message or decision as their cause
3. Failure events must reference:
   - The task, pulse, or agent lifecycle event that directly caused the failure

This ensures causal chains are reconstructable even when traces fragment.

#### Tracing Alignment
ACI must allow (but not require) integration with distributed tracing:
- Lifecycle hooks may start or attach to spans
- Spans should align naturally with:
  - Task execution
  - Tool invocation
  - LLM reasoning calls (delegated downstream)

ACI must **not hard-code** a tracing vendor or SDK, but must:
- Pass trace context through hooks and message envelopes
- Preserve trace continuity where possible

#### Continuum View Compatibility
ACI-emitted events must support aggregation into authoritative views:
- **Project**: cycle start/end events, correlation_id
- **Cycle**: pulse boundaries, objective metadata
- **Pulse**: trace scoping, failure density
- **Task**: task lifecycle events, retries, outcomes

No ACI design decision may obscure these aggregations.

#### Non-Functional Requirements
- **Backward Compatibility**: Existing agents must run under ACI without logic changes
- **Low Overhead**: Instrumentation hooks must not materially slow execution
- **Fail-Safe**: Loss of observability backends must not break execution
- **Determinism**: Lineage fields must be stable and reproducible for a given run

For detailed Continuum-specific requirements, see `ACI_CONTINUUM_ADDENDUM.md`.

---

## 11. Rollout Phasing

### Phase 1 (0.8.x)
- Implement ACI as defined
- Heartbeats + lifecycle
- Runtime assignment rules
- Lifecycle hooks (may be no-ops initially, but must be callable)
- Basic lineage field propagation

### Phase 2 (0.9.x+)
- Background-workers SIP
- Chat protocol SIP
- Optional ping/pong diagnostics
- Full Continuum observability integration (see `ACI_CONTINUUM_ADDENDUM.md`)
- LangFuse, Keycloak, and SOC integration leveraging ACI observability

### Migration Strategy
Existing agents should:
- Add Task Envelope handling at their input boundary
- Expose lifecycle state through heartbeats
- Distinguish task-level errors from container-level crashes
- Add lifecycle hooks (can start as no-ops)
- Propagate lineage fields through all events

Migration can be incremental:
- Start with heartbeats + lifecycle exposure
- Then unify Task Envelope handling and task result correlation
- Finally add lifecycle hooks and structured event emission

### Metrics & Success Criteria
ACI is considered successfully adopted when:
- **All agents used in production**:
  - Expose lifecycle_state via heartbeats
  - Accept Task Envelopes and return results with matching `task_id`
  - Propagate lineage fields in all lifecycle events
- **Health Dashboard**:
  - Reflects accurate lifecycle and reachability for each agent
- **Regression Tests**:
  - ACI test suites run in CI and pass consistently
- **Incidents** related to:
  - "Unknown agent state" or
  - "Tasks lost / misattributed" or
  - "Cannot reconstruct causal chains"
  are significantly reduced or eliminated

---

## 12. Testing & Validation Requirements

A container is **ACI-compliant** only if it passes the following categories of tests:

### 12.1 Lifecycle Tests
- STARTING → READY transition confirmed via heartbeats
- READY → WORKING → READY during task execution
- BLOCKED state represented correctly
- STOPPING/ OFFLINE transitions occur on shutdown
- CRASHED inferred from fatal errors or heartbeat loss

### 12.2 Task Contract Tests
- Container accepts a valid envelope
- Returns result with matching `task_id`
- Rejects unsupported `task_type` with clear reason
- Differentiates task-level errors vs container-level failures
- Optional: Proper handling of cancellation requests

### 12.3 Heartbeat & Health Tests
- Heartbeats emitted at expected interval
- Lifecycle embedded correctly
- Stale heartbeat → runtime marks agent as not reachable
- Crash simulation results in appropriate detection

### 12.4 Runtime/Container Boundary Tests
- Runtime does NOT assign tasks to non-READY containers
- Runtime resumes task assignment when container returns to READY
- Full end-to-end cycle:
  - Create cycle
  - Create task
  - Route to container
  - Observe result
  - Persist outputs

### 12.5 Concurrency Tests (if enabled)
- Multiple internal workers execute tasks concurrently
- No lost tasks
- Each `task_id` terminates with SUCCEEDED/FAILED/CANCELED
- Lifecycle state still reflects acceptance capacity

### 12.6 Observability & Lineage Tests
- Lineage fields (project_id, cycle_id, pulse_id, task_id, agent_id, correlation_id, causation_id, trace_id, span_id) are present in all lifecycle events
- Causation chains are reconstructable: every event (except root events) references a valid causation_id
- Trace context propagation works: trace_id and span_id are preserved through task execution
- Events are structured and suitable for SOC Ledger ingestion
- Lifecycle hooks are callable and receive context with required lineage fields
- Failure events reference the correct causation (task, pulse, or agent lifecycle event that caused the failure)
- Events are emitted asynchronously and do not block task execution

---

This specification finalizes the ACI required for SquadOps 0.8.x and provides the test suite needed to validate it before 1.0.

