# SIP: Duty Durability via Temporal

**Status:** Proposed (draft)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 1
**Targets:** v1.3
**Depends on:** `SIP-Agent-Runtime-State.md` (v1.1) — must land first
**Parent vision:** `sips/proposed/SIP-Agent-Runtime-Modes.md` (umbrella index)
**Sibling:** `SIP-Agent-Embodiment-Substrate.md` (v1.2)

---

## 1. Summary

This SIP introduces **Temporal as a narrowly-scoped durability layer for Duty mode** — and only Duty mode.

Temporal handles what it is best at: durable timers, schedule-driven wake-ups, signal-driven interruption, and long-lived flows that survive worker failure. SquadOps continues to own everything else — agent identity, mode semantics, focus lease policy, activity model, embodiment.

The boundary is deliberate and enforceable:

> **SquadOps owns agent semantics. Temporal owns duty workflow durability.**

This SIP is intentionally the smallest of the three split SIPs. It adds one optional dependency, one workflow pattern, and one proof point. It does not become the agent runtime brain.

---

## 2. Problem Statement

Once duty windows exist (per `SIP-Agent-Runtime-State.md`), the next question is durability:

- A duty agent must wake up at `01:00` even if the worker was offline at midnight
- A duty workflow may wait minutes, hours, or days for an event
- A recall signal must reliably preempt an in-flight duty
- A duty must survive process restarts without losing its position

The v1.1 SIP proposes an in-process scheduler for duty windows. That works for development and basic ops, but it has well-known limits:

- Worker crashes lose pending transitions
- Long waits hold connections and memory
- Signal delivery becomes unreliable
- Retry semantics get reinvented per-duty

The challenge:

> How can SquadOps make Duty workflows durable without letting Temporal consume the rest of the runtime?

---

## 3. Why Temporal — and Why Only for Duty

### 3.1 Where Temporal fits

Temporal workflows are durable, support long waits, schedules, retries, and signal-driven interaction. Workflow Execution can run for extended periods, receive signals/queries/updates, and resume after failures. This maps cleanly to:

- Duty windows (durable timers)
- Event-driven duty wake-ups (signals)
- Recall and preemption (signals + cancellation)
- Periodic operational duty ticks (Schedules)
- Resumable long-lived duty flows (history replay)

References:
- https://docs.temporal.io/workflows
- https://docs.temporal.io/workflow-execution
- https://docs.temporal.io/encyclopedia/workflow-message-passing

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
| Current mode (duty/cycle/ambient) | SquadOps |
| Focus lease policy | SquadOps |
| Activity model | SquadOps |
| Embodiment lifecycle | SquadOps + adapters |
| **Duty workflow durability** | **Temporal** |
| **Duty timer / schedule wake-ups** | **Temporal** |
| **Recall signal delivery** | **Temporal** |
| **Long-running operational flows** | **Temporal** |
| Cycle execution | Prefect (unchanged) |
| Inter-agent comms | RabbitMQ (unchanged) |

Temporal does not replace Prefect. Prefect orchestrates bounded cycle execution. Temporal orchestrates open-ended duty durability. They coexist.

---

## 4. Design Intent

1. Make duty windows durable across worker restarts.
2. Make recall signals reliable.
3. Keep Temporal scoped to Duty workflows — not Ambient, not Cycle, not Activities, not Embodiment.
4. Keep SquadOps the semantic owner — Temporal is a backend, not a peer runtime.
5. Make Temporal opt-in. Without it, the v1.1 in-process scheduler still works.
6. Provide a clean port/adapter so Temporal can be swapped (or removed) without rewriting duty semantics.

---

## 5. Non-Goals

This SIP does **not** propose:

- Migrating cycle execution to Temporal
- Migrating agent comms to Temporal
- Embodiment events flowing through Temporal
- An "agent life" workflow that owns the agent for its lifetime
- Removing Prefect or RabbitMQ
- Making Temporal mandatory — it is an optional adapter

---

## 6. Proposed Architecture

### 6.1 Port

```python
# src/squadops/ports/duty_durability.py

class DutyDurabilityPort(ABC):
    async def schedule_duty_window(self, assignment_id, window_start, window_end) -> str: ...
    async def signal_recall(self, duty_run_id, reason) -> None: ...
    async def cancel_duty(self, duty_run_id) -> None: ...
    async def query_status(self, duty_run_id) -> DutyStatus: ...
```

### 6.2 Adapters

- `adapters/duty_durability/in_process/` — the v1.1 default; suitable for dev and small deployments
- `adapters/duty_durability/temporal/` — the new adapter; production-grade durability

Selection by config, same pattern as the cycle registry adapter (memory vs postgres).

### 6.3 What lives in a Temporal workflow

A duty workflow is **thin**. It does not contain agent logic. It only:

1. Waits for the duty window to open (durable timer)
2. Signals SquadOps to transition the agent into Duty mode
3. Waits for either window end, recall signal, or duty completion
4. Signals SquadOps to release the agent back to its prior mode

```
DutyWorkflow:
  await timer(window_start - now)
  signal squadops: enter_duty(assignment_id)
  await any of:
    - timer(window_end - now)
    - signal recall(reason)
    - signal duty_complete()
  signal squadops: release_duty(assignment_id, reason)
```

The actual duty work — answering support tickets, watching inventory, doing research — runs in SquadOps as Activities. Temporal just owns the *duration and interruption* of the duty.

### 6.4 What does NOT live in Temporal

- Activity execution (stays in SquadOps)
- Embodiment lifecycle (stays in SquadOps + adapters)
- Focus lease management (stays in SquadOps)
- Heartbeats and runtime status (stays in SquadOps)

---

## 7. Proof Point

One narrow proof point demonstrates the boundary:

**Duty:** `nightly_research`

- Window: `01:00–06:00 UTC` daily
- Wake-up: durable timer
- Activity during window: research synthesis using existing handler infrastructure
- Recall: signal-driven (e.g., a higher-priority cycle needs the agent)
- Completion: agent finishes early via `duty_complete` signal

**Acceptance for the proof point:**

- Stop the Temporal worker mid-window. Restart. Duty resumes correctly.
- Send recall signal. Agent transitions out of Duty cleanly within graceful_window seconds.
- Cancel the workflow. Agent releases focus lease and returns to Ambient.
- Run two consecutive nights. Both windows fire on schedule.

---

## 8. Implementation Phases

### Phase 1 — Port and in-process adapter

- Define `DutyDurabilityPort`
- Refactor v1.1 in-process scheduler behind the port
- Adapter selection via config

**Acceptance:** v1.1 behavior unchanged; Temporal not yet introduced.

### Phase 2 — Temporal adapter (basic)

- Add Temporal as optional dependency
- Implement Temporal adapter with durable timer + signal handling
- Workflow design as described in §6.3
- Local Temporal dev stack via docker-compose (optional service)

**Acceptance:** the `nightly_research` proof point passes the four acceptance tests in §7.

### Phase 3 — Schedules and recurrence

- Use Temporal Schedules for recurring duty windows
- Replace per-duty workflow spawning with schedule-triggered runs

**Acceptance:** duties can be defined as recurring without per-day workflow management.

### Phase 4 — Production hardening

- Retry policies for transient failures
- Graceful degradation if Temporal worker is down (fall back to in-process scheduler with degraded warning)
- Observability: link Temporal workflow IDs to SquadOps duty assignments in LangFuse traces

**Acceptance:** Temporal becomes the recommended duty-durability adapter for production.

---

## 9. Acceptance Criteria

The SIP is successful when:

1. **Boundary holds** — Temporal does not own agent identity, mode, focus, activity, or embodiment
2. **Optional dependency** — SquadOps runs without Temporal; Temporal is opt-in via adapter selection
3. **Durability proven** — duty workflows survive worker restarts mid-window
4. **Signals reliable** — recall signals deliver within configured graceful_window
5. **Schedules work** — recurring duties run reliably across multiple windows
6. **Coexistence** — Prefect (cycle execution) and Temporal (duty durability) operate in the same deployment without contention
7. **Graceful degradation** — if Temporal is unavailable, the in-process adapter still serves duty windows with a clear warning
8. **No regressions** — v1.1 and v1.2 behavior unaffected when Temporal adapter is selected

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Temporal scope creeps to own non-duty logic | Port interface is narrow; review every PR that adds Temporal-aware code outside the duty adapter |
| Workflow history bloats | Keep workflows thin (timer + signals only); offload work to SquadOps Activities |
| Determinism violations break replay | Workflow code touches only durable primitives; no LLM calls or agent logic inside the workflow |
| Operators add Temporal as a hard requirement | Keep in-process adapter as a first-class option; document selection clearly |
| Duplication with Prefect | Document boundary: Prefect = bounded cycle execution; Temporal = open-ended duty durability |
| Signal loss between Temporal and SquadOps | Idempotent transition handlers on the SquadOps side |

---

## 11. Open Questions

1. Should the Temporal adapter run in the same Python process as SquadOps, or as a separate worker container?
2. How are recall signals authenticated? (Temporal namespace per environment, or a shared signal token?)
3. What is the migration path for an existing in-process duty if the operator switches to the Temporal adapter mid-cycle?
4. Should LangFuse traces include Temporal workflow IDs as a span attribute, or stay separate?
5. Do we need a CLI command (`squadops duty status <assignment-id>`) that proxies to the durability adapter, or is querying the Temporal UI directly acceptable?
6. How does graceful_window interact with hard duty strictness — does a hard duty refuse recall signals during the window?

---

## 12. References

- Depends on: `sips/proposed/SIP-Agent-Runtime-State.md` (v1.1)
- Parent vision: `sips/proposed/SIP-Agent-Runtime-Modes.md`
- Original full proposal: commit `76a1f90` on main
- Temporal Workflows — https://docs.temporal.io/workflows
- Workflow Execution — https://docs.temporal.io/workflow-execution
- Signals/Queries/Updates — https://docs.temporal.io/encyclopedia/workflow-message-passing
- Schedules — https://docs.temporal.io/schedules
- Related: SIP-0066 (Distributed Cycle Execution Pipeline — Prefect coexistence), SIP-0061 (LangFuse — observability seam)
