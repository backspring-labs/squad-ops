---
title: Duty Durability via Temporal
status: accepted
author: Jason Ladd
created_at: '2026-04-25T00:00:00Z'
sip_number: 91
updated_at: '2026-04-25T17:57:14.005001Z'
---
# SIP-0091: Duty Durability via Temporal

**Status:** Accepted
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 2 (incorporated review feedback on 2026-04-25)
**Targets:** v1.3
**Depends on:** `sips/accepted/SIP-0089-Agent-Runtime-State.md` (v1.1) — must land first
**Parent vision:** `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (umbrella index)
**Sibling:** `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2)

---

## 1. Summary

This SIP introduces **Temporal as a narrowly-scoped durability layer for Duty mode** — and only Duty mode.

Temporal handles what it is best at: durable timers, schedule-driven wake-ups, signal-driven interruption, and long-lived flows that survive worker failure. SquadOps continues to own everything else — agent identity, mode semantics, focus lease policy, RuntimeActivity model, embodiment.

The boundary is deliberate and enforceable:

> **SquadOps owns agent semantics. Temporal owns duty workflow durability. Temporal does not transition agent state directly — it requests transitions through SquadOps.**

This SIP is intentionally the smallest of the three split SIPs. It adds one optional dependency, one workflow pattern, and one proof point. It does not become the agent runtime brain.

---

## 2. Problem Statement

Once duty windows exist (per `SIP-0089-Agent-Runtime-State.md`), the next question is durability:

- A duty agent must wake up at `01:00` even if the worker was offline at midnight
- A duty workflow may wait minutes, hours, or days for an event
- A recall signal must reliably preempt an in-flight duty
- A duty must survive process restarts without losing its position

The v1.1 SIP proposes an in-process scheduler. That works for development and basic ops, but has well-known limits:

- Worker crashes lose pending transitions
- Long waits hold connections and memory
- Signal delivery becomes unreliable
- Retry semantics get reinvented per-duty

The challenge:

> How can SquadOps make Duty workflows durable without letting Temporal consume the rest of the runtime?

---

## 3. Why Temporal — and Why Only for Duty

### 3.1 Where Temporal fits

Temporal workflows are durable, support long waits, schedules, retries, and signal-driven interaction. This maps cleanly to:

- DutyWindow timing (durable timers)
- Event-driven duty wake-ups (signals)
- Recall and preemption requests (signals + cancellation)
- Periodic operational duty ticks (Schedules)
- Resumable long-lived duty flows (history replay)

References:
- https://docs.temporal.io/workflows
- https://docs.temporal.io/workflow-execution
- https://docs.temporal.io/encyclopedia/workflow-message-passing
- https://docs.temporal.io/schedules

### 3.2 Where Temporal does NOT fit

Temporal records event history and expects deterministic workflow behavior. Practical limits per workflow execution make it a poor fit for:

- Every Minecraft movement or embodiment event
- Continuous embodiment telemetry
- An "agent life workflow" running forever
- Free-form cognition loops or per-token decisions

If we let Temporal own the entire agent runtime, history bloat, determinism constraints, and workflow size limits will dominate the architecture.

### 3.3 The boundary

| Concern | Owner |
|---------|-------|
| Agent identity | SquadOps |
| Current RuntimeMode | SquadOps |
| FocusLease arbitration | SquadOps |
| RuntimeActivity model | SquadOps |
| Embodiment lifecycle | SquadOps + adapters |
| **Duty workflow durability** | **Temporal** |
| **DutyWindow timer wake-ups** | **Temporal** |
| **Recall signal delivery** | **Temporal** |
| **Long-running operational flows (timer + signal scaffolding)** | **Temporal** |
| Cycle execution | Prefect (unchanged) |
| Inter-agent comms | RabbitMQ (unchanged) |

Temporal does not replace Prefect. Prefect orchestrates bounded cycle execution. Temporal orchestrates open-ended duty durability. They coexist.

---

## 4. Design Intent

1. Make DutyWindows durable across worker restarts.
2. Make recall signals reliable.
3. Keep Temporal scoped to Duty workflows — not Ambient, not Cycle, not RuntimeActivities, not Embodiment.
4. Keep SquadOps the semantic owner — Temporal is a backend, not a peer runtime.
5. **Temporal requests transitions; SquadOps performs them.** Temporal never mutates agent state directly.
6. Make Temporal opt-in. Without it, the v1.1 in-process scheduler still works.
7. Provide a clean port/adapter so Temporal can be swapped (or removed) without rewriting duty semantics.

---

## 5. Non-Goals

This SIP does **not** propose:

- Migrating cycle execution to Temporal
- Migrating agent comms to Temporal
- Embodiment events flowing through Temporal
- An "agent life" workflow that owns the agent for its lifetime
- Removing Prefect or RabbitMQ
- Making Temporal mandatory — it is an optional adapter
- Letting Temporal be the source of truth for Assignment records

---

## 6. Proposed Architecture

### 6.1 Port

```python
# src/squadops/ports/duty_durability.py

class DutyDurabilityPort(ABC):
    async def register_duty_window(
        self,
        assignment_id: str,
        window_start: datetime,
        window_end: datetime,
        idempotency_key: str,
    ) -> DutyDurabilityRunRef: ...

    async def request_recall(
        self,
        duty_run_id: str,
        reason_code: str,
        idempotency_key: str,
    ) -> None: ...

    async def cancel_duty_window(
        self,
        duty_run_id: str,
        reason_code: str,
        idempotency_key: str,
    ) -> None: ...

    async def get_duty_run_status(self, duty_run_id: str) -> DutyDurabilityRun: ...
```

Method names are deliberately semantic, not Temporal-shaped. `request_recall` may be implemented as a Temporal signal in the Temporal adapter, but the port name does not assume that.

### 6.2 Adapters

- `adapters/duty_durability/in_process/` — the v1.1 default; suitable for dev and small deployments
- `adapters/duty_durability/temporal/` — the new adapter; production-grade durability

Selection by config, same pattern as the cycle registry adapter (memory vs postgres).

### 6.3 DutyDurabilityRun correlation record

A SquadOps-side record links the SquadOps Assignment to whatever the durability backend uses. It is the queryable handle for CLI/UI without coupling directly to Temporal.

```yaml
DutyDurabilityRun:
  duty_run_id: string                       # SquadOps-issued
  assignment_id: string                     # FK to Assignment
  adapter_kind: in_process | temporal
  external_workflow_id: string | null       # Temporal workflow ID, if applicable
  external_run_id: string | null            # Temporal run ID, if applicable
  window_start: timestamp
  window_end: timestamp
  durability_status: scheduled | active | recalled | completed | failed | cancelled
  last_event_at: timestamp
  last_reason_code: string
```

The **Assignment** remains the source of truth for what a duty *is*. The DutyDurabilityRun records how a *specific window* of that assignment is being made durable.

### 6.4 What lives in a Temporal workflow

A duty workflow is **thin**. It does not contain agent logic. It only:

1. Waits for the duty window to open (durable timer)
2. **Requests** SquadOps to enter Duty mode (durable activity that calls SquadOps API)
3. Waits for either window end, recall signal, or duty completion
4. **Requests** SquadOps to release Duty mode

```
DutyWorkflow:
  await timer(window_start - now)
  request_to_squadops: enter_duty(assignment_id, idempotency_key)   # SquadOps decides if/how
  await any of:
    - timer(window_end - now)
    - signal recall(reason_code)
    - signal duty_complete()
  request_to_squadops: release_duty(assignment_id, reason_code, idempotency_key)
```

The actual duty work — answering support tickets, watching inventory, doing research — runs in SquadOps as RuntimeActivities. Temporal owns only the *duration and interruption* of the duty.

### 6.5 What does NOT live in Temporal

- RuntimeActivity execution (stays in SquadOps)
- Embodiment lifecycle (stays in SquadOps + adapters)
- FocusLease management (stays in SquadOps)
- Heartbeats and runtime status (stays in SquadOps)
- Assignment records (stays in SquadOps Postgres)
- LLM calls or any agent cognition (must never enter the workflow — would break determinism)

---

## 7. Idempotency Requirements (mandatory)

Temporal replay and external transition calls require idempotency. Every Temporal-originated request into SquadOps must be safe to replay.

### 7.1 Idempotency keys

Every request from a Temporal workflow into SquadOps must carry an idempotency key constructed from:

- Workflow ID
- Run ID
- Assignment ID
- Transition type (`enter_duty`, `release_duty`, `recall`, `cancel`)
- Scheduled window start (timestamp)

Format: `{workflow_id}:{run_id}:{assignment_id}:{transition_type}:{window_start_iso}`

### 7.2 Server-side handler requirements

SquadOps transition handlers receiving these requests must be **idempotent**:

- Replayed or duplicated requests must not double-acquire FocusLeases
- Replayed or duplicated requests must not double-release FocusLeases
- Replayed or duplicated requests must not create duplicate RuntimeActivities
- Replayed requests must return the original response (recorded result), not re-execute the side effect

Implementation: an `idempotency_log` table indexed by key, recording the first-seen result.

This is **not optional**. Without it, a Temporal worker restart can double-execute duty transitions.

---

## 8. Failure Behaviors

### 8.1 SquadOps unavailable

If a Temporal workflow wakes at `window_start` but SquadOps API is unreachable:

- Temporal retries the transition request using a configured retry policy (exponential backoff, max attempts)
- The DutyDurabilityRun status becomes `transition_pending` with a `last_reason_code` indicating the failure mode
- The agent is **not** considered in Duty mode until SquadOps records the transition successfully
- If retries exhaust, missed-window policy (§8.2) applies

### 8.2 Missed-window policy

When a duty window is missed (worker downtime, repeated failure, late wake), the Assignment's `missed_window_policy` governs behavior:

| Policy | Behavior |
|--------|----------|
| `skip` | Mark window as missed; wait for next scheduled window. Emit `duty_window_missed` event. |
| `start_late_within_grace` | Start the duty if `now ≤ window_end - graceful_window`. Otherwise skip. |
| `require_operator_review` | Mark window as `awaiting_review`. Block until `operator_override` is supplied. |

Default if unspecified: `start_late_within_grace`.

### 8.3 Production fallback rule (critical safety)

Silent fallback from Temporal → in-process scheduling is **forbidden in production** for any Assignment registered with the Temporal adapter. This prevents the foot-gun of double duty execution if the in-process scheduler also fires the same window.

| Mode | Fallback behavior |
|------|------------------|
| `dev` | Automatic fallback allowed; emit warning |
| `prod` | Fallback requires explicit `operator_override` setting per Assignment; otherwise the system surfaces the unavailability and refuses to schedule |

The mode is read from the SquadOps configuration (`SQUADOPS__DEPLOYMENT__MODE` or equivalent).

---

## 9. What Temporal Worker Restart Actually Resumes

A precise statement to avoid overstating Temporal's guarantees:

> Restarting the Temporal worker resumes the **workflow's timer and signal state**, including pending timers, recorded signals, and the workflow's position in its execution. It does **not** automatically resume any in-flight duty *work* unless the SquadOps RuntimeActivity model also supports checkpointing for that work.

In other words: Temporal makes the *scheduling* survive. Whether the *work* survives depends on the RuntimeActivity having `can_resume` semantics and durable checkpoints, which is a SquadOps responsibility.

---

## 10. Authentication and Authorization Posture

Temporal signals and workflow requests must be authenticated. This is not an open question for production.

- Recall signals must originate from authenticated SquadOps services, not arbitrary callers reaching Temporal directly.
- External user intent (e.g., an operator triggering a recall) enters through the SquadOps API or CLI. SquadOps authorizes the action and then calls `DutyDurabilityPort.request_recall()`.
- Temporal namespaces and task queues must be **environment-scoped** (e.g., `squadops-prod-duty`, `squadops-staging-duty`). Cross-namespace signal injection is prohibited.
- Temporal workflows calling SquadOps must use a service account with limited scope (only the duty-transition endpoints).

---

## 11. Temporal Schedules vs Assignment

Temporal Schedules are a **durability mechanism for recurring wake-ups**. They are not the canonical record of what duties exist.

- The **SquadOps Assignment** remains the source of truth for what a duty *is*: role, window, strictness, recall policy, missed-window policy.
- A **Temporal Schedule** creates or triggers workflow runs for individual DutyWindows of that Assignment.
- If an Assignment is deleted in SquadOps, the corresponding Temporal Schedule must be cancelled.
- If a Temporal Schedule is removed manually, SquadOps must detect this on next reconciliation and either re-register or surface the discrepancy.

A reconciliation loop in the Temporal adapter compares Assignment state with Schedule state and surfaces drift.

---

## 12. Proof Point

One narrow proof point demonstrates the boundary:

**Duty:** `nightly_research`

- Window: `01:00–06:00 UTC` daily
- Wake-up: durable Temporal Schedule
- RuntimeActivity during window: research synthesis using existing handler infrastructure
- Recall: signal-driven (e.g., a higher-priority cycle needs the agent)
- Completion: agent finishes early via `duty_complete` signal
- Missed-window policy: `start_late_within_grace`

### Acceptance for the proof point

- Stop the Temporal worker mid-window. Restart. The **workflow** resumes and the duty correctly remains in `active` durability status. RuntimeActivity resumes per its own `can_resume` semantics.
- Send a recall signal. SquadOps receives the recall request, authorizes it, and transitions the agent out of Duty cleanly within `graceful_window` seconds. Idempotency holds: replayed signal does not double-recall.
- Cancel the workflow. SquadOps releases the FocusLease and returns the agent to Ambient.
- Run two consecutive nights. Both windows fire on schedule with distinct DutyDurabilityRun records.
- Take SquadOps API down at `window_start`. Temporal retries. When SquadOps returns, transition completes; no duplicate transition occurs.

---

## 13. Implementation Phases

### Phase 1 — Port and in-process adapter

- Define `DutyDurabilityPort`
- Implement `DutyDurabilityRun` record + Postgres table
- Refactor v1.1 in-process scheduler behind the port
- Adapter selection via config
- Idempotency log table

**Acceptance:** v1.1 behavior unchanged; Temporal not yet introduced. Idempotent transition handlers in place and tested against replay.

### Phase 2 — Temporal adapter (basic)

- Add Temporal as optional dependency
- Implement Temporal adapter with durable timer + signal handling
- Workflow design as described in §6.4
- Local Temporal dev stack via docker-compose (optional service)
- Authentication posture per §10

**Acceptance:** the `nightly_research` proof point passes the §12 acceptance, including the idempotency and unavailable-API tests.

### Phase 3 — Schedules and recurrence

- Use Temporal Schedules for recurring DutyWindows
- Reconciliation loop comparing Assignments to Schedules
- Replace per-duty workflow spawning with schedule-triggered runs

**Acceptance:** duties can be defined as recurring without per-day workflow management. Drift between Assignment and Schedule is surfaced.

### Phase 4 — Production hardening

- Retry policies for transient failures
- Production fallback rule per §8.3 (refuse silent fallback in prod)
- Observability: link Temporal workflow IDs to SquadOps duty Assignments in LangFuse traces via DutyDurabilityRun

**Acceptance:** Temporal becomes the recommended duty-durability adapter for production.

---

## 14. Acceptance Criteria

The SIP is successful when:

1. **Boundary holds** — Temporal does not own agent identity, mode, FocusLease, RuntimeActivity, or embodiment
2. **Temporal requests, SquadOps decides** — workflows never mutate agent state directly
3. **Idempotency** — every Temporal-originated request carries an idempotency key; handlers are replay-safe
4. **Optional dependency** — SquadOps runs without Temporal; Temporal is opt-in via adapter selection
5. **Durability proven** — duty workflow timer/signal state survives worker restarts mid-window
6. **Signals reliable** — recall signals deliver within `graceful_window`
7. **Schedules work** — recurring duties run reliably across multiple windows; drift is surfaced
8. **Coexistence** — Prefect (cycle execution) and Temporal (duty durability) operate in the same deployment without contention
9. **Production safety** — no silent fallback to in-process in production; missed-window policy explicit
10. **Auth posture enforced** — recall signals only from authenticated SquadOps services; namespaces environment-scoped
11. **No regressions** — v1.1 and v1.2 behavior unaffected when Temporal adapter is selected

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Temporal scope creeps to own non-duty logic | Port interface is narrow; review every PR that adds Temporal-aware code outside the duty adapter |
| Workflow history bloats | Keep workflows thin (timer + signal requests only); offload work to SquadOps RuntimeActivities |
| Determinism violations break replay | Workflow code touches only durable primitives; no LLM calls or agent logic inside the workflow |
| Operators add Temporal as a hard requirement | Keep in-process adapter as a first-class option; document selection clearly |
| Duplication with Prefect | Document boundary: Prefect = bounded cycle execution; Temporal = open-ended duty durability |
| Signal loss between Temporal and SquadOps | Idempotent transition handlers + retry policy in §8.1 |
| **Silent fallback causes double execution** | Production fallback rule §8.3 — refuse silent fallback in prod |
| Workflow "resumes work" expectation | Precise wording in §9 — Temporal resumes scheduling, not RuntimeActivity work |
| Recall signals from arbitrary callers | Auth posture §10 — only authenticated SquadOps services |
| Assignment vs Schedule drift | Reconciliation loop §11 |

---

## 16. Open Questions

1. Should the Temporal adapter run in the same Python process as SquadOps, or as a separate worker container?
2. How should LangFuse traces link to Temporal workflow IDs? Span attribute on the SquadOps side referencing `external_workflow_id`?
3. What CLI surface should expose duty status — `squadops duty status <assignment-id>` proxying to `DutyDurabilityPort.get_duty_run_status()`, or just direct Temporal UI access?
4. How does `graceful_window` interact with hard duty strictness — does a hard duty refuse recall signals during the window, or honor them with extended grace?
5. Should the idempotency log have a TTL (e.g., 30 days) to bound storage, or persist indefinitely for audit?

---

## 17. References

- Depends on: `sips/accepted/SIP-0089-Agent-Runtime-State.md` (v1.1)
- Parent vision: `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (canonical reason codes, event names, package invariant)
- Original full proposal: commit `76a1f90` on main
- Temporal Workflows — https://docs.temporal.io/workflows
- Workflow Execution — https://docs.temporal.io/workflow-execution
- Signals/Queries/Updates — https://docs.temporal.io/encyclopedia/workflow-message-passing
- Schedules — https://docs.temporal.io/schedules
- Related: SIP-0066 (Distributed Cycle Execution Pipeline — Prefect coexistence), SIP-0061 (LangFuse — observability seam)
