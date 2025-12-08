---
sip_uid: 01KBTWMSCW472RT7T72DYNXKT2
sip_number: 49
title: Agent Lifecycle & Health Check Integration
status: implemented
author: Jason Ladd
approver: null
created_at: '2025-12-06T22:31:20Z'
updated_at: '2025-12-07T19:47:42.152052Z'
original_filename: SIP-AGENT-LIFE-CYCLE.md
---
# SIP-AGENT-LIFE-CYCLE — Agent Lifecycle & Health Check Integration

**Status:** Proposed  
**Target Version:** 0.8.x  
**Author:** Framework Committee  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data  

---

# 1. Purpose and Intent

This SIP defines the **canonical Agent Life Cycle** for all SquadOps agents.  
It establishes a strict and minimal finite state model that governs **agent behavior**, independent from network reachability or health check availability.

The lifecycle exists to:

- Provide predictable agent behavior for task routing, concurrency, and governance.
- Enable SOC to distinguish between **network status** and **lifecycle state**.
- Support consistent logging, task management, and WarmBoot evaluation.
- Avoid implementation drift and ensure all agents share the same FSM semantics.
- Cleanly integrate with `/health/agents` and the Health Check UI.

This SIP specifies **what** must exist — not how individual agent containers implement it.

---

# 2. Background

Earlier drafts conflated a lifecycle state of "OFFLINE" with network reachability.  
This prevented the Health Check service and SOC from distinguishing between:

1. **Status (Network Reachability)**  
   - Can the agent be reached?  
   - Reports: `online` or `offline`

2. **Lifecycle (Agent FSM Behavior)**  
   - What is the agent *doing*?  
   - Reports: `STARTING`, `READY`, `WORKING`, `BLOCKED`, `CRASHED`, `STOPPING`

Merging these concepts introduced ambiguity in failure analysis, WarmBoot scoring, and SOC visualization.  
This SIP corrects the model and restores clarity.

---

# 3. Problem Statements

This SIP resolves the following issues:

1. **Status and lifecycle were conflated**, reducing observability fidelity.  
2. **FSM contained an "OFFLINE" state**, conflicting with network health checks.  
3. **SOC could not distinguish unreachable vs. unready agents.**  
4. **Agents lacked a canonical, enforced FSM**, causing inconsistent behavior across roles.  
5. **Testing and concurrency protocols could not reliably detect BLOCKED vs. CRASHED** states.

---

# 4. Scope

## 4.1 Included

- Canonical lifecycle definition  
- Allowed transitions  
- Separation of **Status** and **Lifecycle**  
- Requirements for health check responses  
- Requirements for SOC display behavior  
- Required logging and traceability fields  

## 4.2 Not Included

- Implementation details (libraries, FSM engines, hooks)  
- Role-specific lifecycle variations  
- Behavioral tuning or reasoning model differences  

---

# 5. Design Overview

All agents share an identical minimal FSM:

```text
STARTING → READY → WORKING → READY
WORKING  → BLOCKED → WORKING
WORKING  → CRASHED → STOPPING → (no lifecycle; status=offline)
READY    → STOPPING → (no lifecycle; status=offline)
```

Lifecycle and network Status are now **independent**, with the following rules:

- **Status:**  
  - `online` or `offline`  
  - Determined by `/health/agents` liveness probe  
  - Not part of the lifecycle

- **Lifecycle:**  
  One of:
  ```text
  STARTING
  READY
  WORKING
  BLOCKED
  CRASHED
  STOPPING
  ```
  Or **UNKNOWN** if Status is `offline`.

This separation aligns with Kubernetes "live vs. ready" semantics and modern distributed system design.

---

# 6. Functional Requirements

## 6.1 Status Field (Network Reachability)

Agents must expose a `status` field in `/health/agents` returning:

```json
"status": "online" | "offline"
```

Rules:

- Status is **binary**.
- If no response is received within timeout → `offline`.
- If status = `offline`, lifecycle state MUST be omitted or set to `null`.

---

## 6.2 Lifecycle Field (FSM)

Agents must expose a `lifecycle` field in `/health/agents` returning one of:

```json
"lifecycle": "STARTING" | "READY" | "WORKING" | "BLOCKED" | "CRASHED" | "STOPPING"
```

Rules:

- Lifecycle is reported **only when status=online**.
- Lifecycle values must follow the canonical transitions defined in this SIP.
- Illegal transitions must be prevented and logged.

---

## 6.3 Canonical Lifecycle Definitions

### STARTING
Agent is booting and not yet ready.

**Requirements**

- Connections to infra (DB, queues, Task API) are being established.
- Workspace prep MAY be initiated but is not guaranteed complete.
- Health check: `status=online`, `lifecycle=STARTING`.

---

### READY
Agent is fully operational and may accept tasks.

**Requirements**

- All core dependencies verified.
- Agent is eligible for task routing from Max.
- Concurrency Protocol: **Available**.
- Health check: `status=online`, `lifecycle=READY`.

---

### WORKING
Agent is executing a task.

**Requirements**

- Task context is bound (agent_id, task_id, cycle_id).
- Task Logging has recorded a start event.
- Concurrency Protocol:
  - Active–Blocking or Active–Non-Blocking (implementation detail).
- Health check: `status=online`, `lifecycle=WORKING`.

---

### BLOCKED
Agent is paused waiting for external input per the Concurrency Protocol.

**Examples**

- Waiting on another agent's output.
- Awaiting data fetch completion.
- Awaiting human approval.

**Requirements**

- A human- or machine-readable `blocked_reason` SHOULD be maintained in logs.
- Concurrency Protocol: **Blocked – External Input Needed**.
- Health check: `status=online`, `lifecycle=BLOCKED`.

---

### CRASHED
Agent encountered an unrecoverable internal error.

**Requirements**

- The current task is considered failed.
- A crash record MUST be written to logs with stack trace where possible.
- Health check: `status=online`, `lifecycle=CRASHED` for a short window, until STOPPING begins.

---

### STOPPING
Agent is performing graceful teardown and will soon report `offline`.

**Requirements**

- In-flight tasks are either:
  - Marked as failed, or
  - Handed off according to Task Management SIPs.
- Logs and telemetry are flushed.
- Health check: `status=online`, `lifecycle=STOPPING` until the process exits, then `offline` with no lifecycle.

---

## 6.4 Allowed Transitions

| From     | To        | Meaning                         |
|----------|-----------|---------------------------------|
| STARTING | READY     | Initialization complete         |
| READY    | WORKING   | Task assigned                   |
| WORKING  | READY     | Task completed                  |
| WORKING  | BLOCKED   | Waiting on external input       |
| BLOCKED  | WORKING   | External input resolved         |
| WORKING  | CRASHED   | Fatal error while working       |
| BLOCKED  | CRASHED   | Fatal error while blocked       |
| READY    | STOPPING  | Shutdown sequence initiated     |
| CRASHED  | STOPPING  | Fatal cleanup / teardown        |

**Status Coupling Rules**

- While in any lifecycle state: `status` MUST be `online`.
- After STOPPING completes, the process exits and:
  - Health check: `status=offline`, `lifecycle=null`.

---

## 6.5 Logging Requirements

Every lifecycle transition MUST be logged to the Cycle Data Store with:

- `agent_id`
- `previous_state`
- `new_state`
- `timestamp`
- `cycle_id` (if applicable)
- `task_id` (if applicable)
- Optional: `reason` (especially for BLOCKED and CRASHED)

These logs support:

- WarmBoot analysis.
- RCA (root cause analysis).
- SOC audit trails.
- Regression testing of lifecycle behavior.

---

## 6.6 SOC Visualization Requirements

The SquadOps Console (SOC) MUST:

- Display **Status** and **Lifecycle** as separate columns.
- Represent:

  - `status=online` in green (e.g., ✅ online).
  - `status=offline` in muted red/grey (e.g., ❌ offline).
  - `lifecycle` values using a consistent palette (e.g., READY green, WORKING blue, BLOCKED yellow, CRASHED red, STOPPING grey/blue, STARTING grey/blue).

- When `status=offline`:
  - Lifecycle column MUST render `—` or be empty.

Example table row:

```text
Agent  Role   Status      Lifecycle  Version  TPS  Memories
Neo    dev    ✅ online   READY      0.6.5    0    60
Max    lead   ✅ online   WORKING    0.6.5    0    41
Eve    qa     ❌ offline  —          0.6.5    0    2
```

---

# 7. Non-Functional Requirements

- Lifecycle reporting MUST complete within < 250ms per agent.
- Logging MUST be durable and ordered for each agent.
- Lifecycle states MUST be resilient to short, transient outages.
- Backward compatibility:
  - Older agents MAY omit `lifecycle` (null), but MUST still report `status`.
  - SOC should handle null lifecycle gracefully.

---

# 8. API Surface

## 8.1 `/health/agents` Response (Updated)

The Health Check service MUST return an array of agent status objects:

```json
[
  {
    "agent": "Neo",
    "role": "dev",
    "status": "online",
    "lifecycle": "READY",
    "version": "0.6.5",
    "tps": 0,
    "memories": 60
  },
  {
    "agent": "Max",
    "role": "lead",
    "status": "online",
    "lifecycle": "WORKING",
    "version": "0.6.5",
    "tps": 0,
    "memories": 41
  },
  {
    "agent": "Eve",
    "role": "qa",
    "status": "offline",
    "lifecycle": null,
    "version": "0.6.5",
    "tps": 0,
    "memories": 2
  }
]
```

### API Rules

- `status` is always present and is either `online` or `offline`.
- `lifecycle` MUST be one of the defined lifecycle states or `null`.
- When `status=offline`, `lifecycle` MUST be `null`.

---

# 9. Implementation Considerations

- Agents MAY implement the FSM via:
  - A minimal state variable plus guard checks, or
  - A lightweight FSM library.
- A crash SHOULD trigger:
  - Lifecycle: `CRASHED` → `STOPPING` → process exit.
  - Status: transitions from `online` to `offline` once the process is unreachable.
- The Health Check service MUST:
  - Poll agents on a fixed cadence.
  - Degrade `status` to `offline` on timeout or connection failure.
- Lifecycle state MUST be stored in-process and exposed via a lightweight endpoint the Health Check service can query.

---

# 10. Executive Summary — What Must Be Built

- A unified FSM shared by all agents with states:
  - `STARTING`, `READY`, `WORKING`, `BLOCKED`, `CRASHED`, `STOPPING`.
- Strict separation of **Status** (`online`/`offline`) and **Lifecycle**.
- Updated `/health/agents` API to include both fields.
- Logging of all lifecycle transitions to the Cycle Data Store.
- SOC updates to render Status and Lifecycle independently.
- Enforcement of allowed transitions and illegal transition logging.

---

# 11. Definition of Done

- [ ] All agents implement the canonical lifecycle states.  
- [ ] All agents expose `status` and `lifecycle` to the Health Check service.  
- [ ] `/health/agents` returns data in the specified JSON structure.  
- [ ] SOC displays separate Status and Lifecycle columns.  
- [ ] Offline agents show `status=offline` and `lifecycle=null`.  
- [ ] CRASHED → STOPPING → offline flow works for all agents.  
- [ ] All lifecycle transitions are logged with agent_id, cycle_id, and task_id where applicable.  
- [ ] WarmBoot runs can reconstruct lifecycle sequences from logs.

---

# 12. Appendix

*(None for this version.)*


