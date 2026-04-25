---
title: Agent Runtime State
status: accepted
author: Jason Ladd
created_at: '2026-04-25T00:00:00Z'
sip_number: 89
updated_at: '2026-04-25T17:57:13.678325Z'
---
# SIP-0089: Agent Runtime State — Modes, Duty Windows, Focus, and RuntimeActivity

**Status:** Accepted
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 2 (incorporated review feedback on 2026-04-25)
**Targets:** v1.1
**Parent vision:** `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (umbrella index)
**Sibling SIPs:**
- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2 candidate, builds on this)
- `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3 candidate, builds on this)

---

## 1. Summary

This SIP introduces the **runtime-state foundation** for persistent SquadOps agents. It is the first of three SIPs that emerged from splitting the original umbrella proposal (`SIP-0088-Agent-Runtime-Modes.md`).

It proposes the minimum runtime primitives needed to make persistent agents observable, schedulable, and recallable, without introducing embodiment or durable workflow concerns.

**This SIP introduces a runtime coordination layer around existing execution paths.** It does not redefine how cycles are planned, executed, validated, or accepted. Cycle, workload, task, and handler semantics are unchanged — they continue to do the work. The new primitives observe and arbitrate; they do not execute.

The five primitives:

1. **RuntimeMode** — current operating posture, exactly one of `duty | cycle | ambient`
2. **Assignment + DutyWindow** — durable commitments and the time ranges in which they may claim the agent
3. **FocusLease** — explicit ownership claim over the agent's primary attention
4. **RuntimeActivity** — observable runtime record of current work (the canonical name; `Activity` is reserved for Temporal's distinct concept)
5. **Runtime status** — agent health/availability, distinct from work posture

This SIP **does not** propose embodiment, location, virtual worlds, or Temporal integration. Those are deferred to the sibling SIPs.

---

## 2. Problem Statement

SquadOps is hardening around a cycle-oriented execution model. That works for bounded acceptance-oriented work. But the framework cannot currently express:

- an agent that is online but not assigned to a cycle,
- an agent that holds a scheduled operational responsibility (e.g. nightly research, support duty),
- an agent that is "free" right now but reserved for a duty window starting in two hours,
- the difference between *what* an agent is doing now and *what* may claim it next.

Without explicit runtime state, these conditions live in prompt history or in the absence of an active cycle, which makes scheduling and recall unreasoned and unobservable.

The challenge:

> How can SquadOps introduce persistent, schedule-aware agent behavior without undermining the simplicity of the current cycle-oriented architecture?

---

## 3. Design Intent

1. Preserve the cycle model as the canonical mechanism for bounded, acceptance-oriented work. **Cycle execution paths are not modified by this SIP.**
2. Introduce persistent runtime *state* — not autonomous behavior — without forcing all activity into cycles.
3. Support service-like operational responsibility through Duty mode with explicit windows.
4. Make current state, future commitments, and immediate action separately observable.
5. Allow interruption and recall through explicit policy rather than implicit prompt drift.
6. Establish FocusLease as the **hard gate** for primary attention.
7. Keep the model small enough to ship in v1.1.

---

## 4. Non-Goals

This SIP does **not** propose:

- Embodiment abstractions (Mineflayer, Discord, browser) — see `SIP-0090-Agent-Embodiment-Substrate.md`
- Location modeling — see `SIP-0090-Agent-Embodiment-Substrate.md`
- Temporal or any external workflow durability layer — see `SIP-0091-Duty-Durability-via-Temporal.md`
- Replacing the current cycle mechanism
- Replacing or competing with the existing task/workload/handler execution model
- A fully autonomous "agent life" loop
- Direct human interaction as a peer mode (treated as cross-cutting; see §8)

---

## 5. Proposed Runtime Model

### 5.1 Top-Level Modes

An agent has exactly one **current RuntimeMode** at a time:

- `duty` — on-duty, service-responsible, availability-constrained
- `cycle` — bounded, formal, assigned work with explicit completion semantics
- `ambient` — off-duty, low-priority, interruptible background presence

These modes are **mutually exclusive**. They imply different rules for interruptibility, accountability, scheduling, recall policy, and what commitments the agent is allowed to accept. They are operational postures, not task labels.

### 5.2 Mode definitions

**Duty.** The agent is responsible for a role or function requiring availability and policy-governed behavior. Examples: customer support, inventory watch, nightly research, monitoring/moderation.

**Cycle.** The agent is committed to bounded assigned work with acceptance criteria. Examples: building a web app, executing an experiment, producing an artifact, performing a validation pass. This remains the most structured form of execution in SquadOps.

**Ambient.** The agent is online, present, lightly available, and off-duty. Bounded, interruptible, low-resource. **Ambient may observe, idle, respond lightly, or prepare context. Ambient may NOT perform irreversible external actions, spend material compute, or mutate external systems unless a FocusLease is granted and a RuntimeActivity is started.** This becomes critical once embodiment exists in v1.2.

---

## 6. Orthogonal Concepts: Mode vs Assignment vs Schedule vs Focus vs Activity

The most important architectural distinction: **mode is not the same as assignment or schedule.**

| Concept | Answers | Example |
|---------|---------|---------|
| **RuntimeMode** | What is the agent doing right now? | `ambient` |
| **Assignment** | What role or commitment is associated with the agent? | `nightly_research`, `support_duty` |
| **DutyWindow** | When is that assignment active or claimable? | `01:00–06:00 UTC` |
| **Focus** (held via FocusLease) | What currently owns the agent's primary attention within its current mode? | `handling support case #184` |
| **RuntimeActivity** | What concrete unit of work is currently observable? | `summarize_findings`, `classify_ticket` |

This separation enables a coherent state like:

- current mode = `ambient`
- duty assignment = `nightly_research`
- duty window starts at `01:00`
- cycle eligible = `true` until reserve buffer begins

The agent can be ambient now, recruited into a short cycle if safe, and transition into Duty automatically when the window opens.

---

## 7. RuntimeActivity vs Existing Execution Concepts

This is the most-asked question on first reading. The mapping:

| Concept | Role | Owner |
|---------|------|-------|
| **Cycle** | Bounded unit of formal work with acceptance | Existing cycle subsystem (unchanged) |
| **Workload** | DAG or grouped execution structure within a cycle | Existing workload runner (unchanged) |
| **Task** | Planned capability-level execution unit | Existing task model (unchanged) |
| **Handler** | Implementation path that performs task work | Existing handler registry (unchanged) |
| **RuntimeActivity** | Runtime-visible observation/control record for what an agent is currently doing | **New, this SIP** |

**A RuntimeActivity is not a new execution engine primitive.** It is the runtime-visible representation of current work, whether that work is being performed by a cycle task, a duty handler, an ambient observation, or (in v1.2) an embodied action.

Concretely:

- A single cycle task may create one or more RuntimeActivity records over its lifetime
- A RuntimeActivity may reference a cycle, workload, task, duty assignment, or embodiment action depending on context
- Existing execution mechanisms emit and update RuntimeActivity records; they are not replaced by them

Implementation pattern: handlers and workload runners gain a thin observability hook that opens, updates, and closes a RuntimeActivity record. Execution itself stays where it is.

---

## 8. Direct Interaction Is Cross-Cutting

Direct human interaction is **not** a peer mode. It is a cross-cutting interaction path that may occur against an agent already in one of the three top-level modes. See the policy table in the umbrella SIP.

This keeps the mode model small while preserving the reality that humans may speak to agents in any mode.

---

## 9. Cycle Preservation

This SIP preserves Cycle as the canonical bounded-work mechanism. Cycle execution semantics, planning workloads, acceptance criteria, gates, and artifacts are unchanged.

What changes: an agent may decline cycle recruitment if a hard duty window is approaching (within the reserve buffer; see §11.4) or if a focus lease cannot be granted under current policy. That decision becomes **explainable** rather than implicit, via the canonical reason codes in the umbrella.

---

## 10. Core Runtime Primitives

### 10.1 Agent Runtime State

```yaml
AgentRuntimeState:
  agent_id: string
  mode: duty | cycle | ambient
  runtime_status: online | degraded | recovering | offline   # health only — see 10.5
  focus: string                                              # short label for primary concern
  current_runtime_activity_id: string | null
  interruptibility: none | low | medium | high               # current posture
  last_heartbeat_at: timestamp
  current_assignment_ref: string | null                      # the ACTIVE assignment, if any
```

### 10.2 Assignment

```yaml
Assignment:
  assignment_id: string
  assignment_type: duty | reserve | cycle_eligibility
  assigned_role: string
  priority: integer
  strictness: hard | soft
  active_window:
    start: timestamp
    end: timestamp
    timezone: string
  reserve_before_window: duration   # see 11.4 — first-class policy in v1.1
  reserve_after_window: duration
  recall_policy: immediate | graceful | none
  graceful_window: duration
  allowed_off_window_modes:
    - ambient
    - cycle
```

**Assignment cardinality:** an agent may hold **multiple Assignments** but exactly **one current RuntimeMode** and at most **one primary FocusLease**. Conflicts among assignments are resolved by scheduling policy *before* a focus claim is attempted. `current_assignment_ref` names the currently active assignment, not the only one held.

### 10.3 DutyWindow

DutyWindows are explicit. Duty is not a permanent identity lock. Window fields live inside the Assignment (`active_window`, `reserve_before_window`, `reserve_after_window`, `graceful_window`).

### 10.4 FocusLease

```yaml
FocusLease:
  lease_id: string
  owner_type: duty | cycle | ambient
  owner_ref: string
  acquired_at: timestamp
  expires_at: timestamp | null
  renewal_policy: heartbeat | ttl | fixed_window
  interruptibility: none | low | medium | high
  recall_policy: immediate | graceful | none
```

**Invariant:** No RuntimeActivity that requires primary attention may begin unless the agent holds a compatible FocusLease.

Permitted exceptions to the FocusLease requirement:

- Passive heartbeat
- Status query
- Low-cost ambient observation (only if policy explicitly allows a shared/low-priority lease)
- Embodied actions in v1.2 may require either the primary FocusLease or a future EmbodimentLease (deferred decision)

### 10.5 Runtime status

`runtime_status` describes **agent runtime health and availability only**. It does not encode work posture.

- `online` — healthy, reachable, heartbeating
- `degraded` — reachable but impaired (e.g., LLM provider failover, partial connectivity)
- `recovering` — attempting to return to `online` after a failure
- `offline` — unreachable

Whether the agent is "idle" or "busy" is **derived** from FocusLease + RuntimeActivity, not stored in `runtime_status`. Whether the agent is "paused" is a **RuntimeActivity** state, not a runtime-status state.

### 10.6 RuntimeActivity

```yaml
RuntimeActivity:
  runtime_activity_id: string
  mode: duty | cycle | ambient                  # which top-level mode this belongs to
  activity_type: string
  goal: string
  priority: integer
  state: pending | running | paused | completed | aborted | failed
  source_ref:                                   # what created this activity
    kind: cycle_task | workload | duty_handler | ambient_observation | embodied_action
    ref: string                                 # opaque; the source subsystem interprets
  can_pause: boolean
  can_resume: boolean
  can_abort: boolean
  completion_conditions: []
  evidence_requirements: []
```

RuntimeActivities make current work observable without digging into prompt history. They do not perform work; existing handlers and workloads do, while emitting RuntimeActivity records.

---

## 11. Transition Semantics

### 11.1 Allowed transitions

- `ambient → cycle`
- `ambient → duty`
- `cycle → ambient`
- `cycle → duty` (only if policy permits preemption)
- `duty → ambient`
- `duty → cycle` (generally only after duty window ends or if policy explicitly allows)

### 11.2 Required preconditions for any mode transition

Every mode transition must:

1. Carry a **reason code** from the canonical set in the umbrella SIP
2. Resolve a **FocusLease decision** (acquired, released, or transferred)
3. Resolve a **RuntimeActivity decision** (paused, resumed, aborted, completed, or none)
4. Pass a **policy evaluation** (priority, interruptibility, reserve buffer, graceful window)
5. Emit a **runtime event** from the canonical event set in the umbrella SIP

Invalid transitions must be rejected with an explainable reason code; they must not silently no-op.

### 11.3 Specific transition constraints

- **Ambient → Cycle:** requires cycle recruitment policy approval and FocusLease acquisition.
- **Cycle → Duty:** requires duty priority to exceed cycle interruptibility policy AND current RuntimeActivity to be `can_pause` or `can_abort`.
- **Duty → Cycle:** requires DutyWindow end OR explicit policy allowance with FocusLease re-arbitration.
- **Offline → Duty:** **not permitted directly.** Runtime must first reach `online` or `recovering` status.
- **Any → Any with destructive RuntimeActivity loss:** rejected unless explicit `operator_override` reason code is provided.

### 11.4 Pre-duty reserve buffer (first-class v1.1 policy)

Cycle recruitment must respect a configurable **reserve buffer** before a hard duty window. Without this, a long cycle can be accepted minutes before a hard duty window opens and immediately create a conflict.

- `reserve_before_window: duration` — declared on the Assignment
- During the buffer, cycle recruitment is rejected with reason `cycle_recruitment_rejected_upcoming_duty`
- Soft duties may permit recruitment during the buffer if the cycle's `can_pause` is true and the cycle accepts the duty's `recall_policy`

Default if unspecified: 15 minutes for hard duties, 0 minutes for soft duties.

### 11.5 FocusLease conflict outcomes

A FocusLease request resolves to exactly one of:

| Outcome | Meaning | Required response fields |
|---------|---------|--------------------------|
| `granted` | Lease acquired | `lease_id`, `expires_at`, reason code |
| `rejected` | Lease denied; current owner holds | `current_owner_ref`, reason code, optional `retry_after` |
| `queued` | Lease will be granted when current owner releases | `queue_position`, `current_owner_ref`, reason code |
| `preempting` | Higher-priority owner displacing current owner | `current_owner_ref`, `preemption_grace`, reason code |

All outcomes emit a `focus_lease.*` event from the canonical event set.

---

## 12. Hard vs Soft Duty (Operational Semantics)

### Hard duty

- **Blocks** new cycle recruitment during the DutyWindow AND reserve buffer
- **May preempt** ambient work
- **May preempt** cycle work only if the cycle accepted that interruptibility policy at recruitment time
- Direct interaction during the window is `defer-or-route`, not `interrupt`

### Soft duty

- **Allows** preemptible work during the window
- Reclaims focus per `recall_policy` and `graceful_window`
- **Should not accept** new work that cannot pause or checkpoint within the graceful window
- Direct interaction is `answer` by default

---

## 13. Persistence

Runtime state, assignments, and focus leases need a durable home. Recommended placement (to be confirmed during design review):

- **AgentRuntimeState, FocusLease, Assignment, RuntimeActivity** — Postgres (cycle registry already lives there; same connection pool)
- **Live RuntimeActivity working set** — in-memory cache; Postgres for durable record

Heartbeat already flows through `AgentHeartbeatReporter`; extending it to carry mode/focus is the cheapest path.

LanceDB (SIP-042) is **not** the right home — semantic memory is for retrieval, not transactional state.

---

## 14. Implementation Phases

### Phase 0 — Vocabulary freeze

- SIP approval
- Lock terminology per the umbrella's canonical names
- No code changes

### Phase 1 — Minimal runtime state

- Add `mode`, `runtime_status`, `focus`, `current_runtime_activity_id`, heartbeat fields to agent runtime
- Extend `AgentHeartbeatReporter` to carry the new fields
- Postgres migration for `agent_runtime_state` table

**Acceptance:** an operator can query an agent's current mode and current RuntimeActivity.

### Phase 2 — Assignments and duty windows

- Implement Assignment model and Postgres table (including `reserve_before_window`)
- Implement DutyWindow with hard/soft strictness
- Add a transition scheduler (in-process; no Temporal)
- Implement reserve-buffer policy in cycle recruitment

**Acceptance:** an agent can be Ambient now and scheduled to enter Duty later. An upcoming hard duty window restricts cycle recruitment per the reserve buffer.

### Phase 3 — Focus lease

- Implement FocusLease model with acquire/release/renew semantics
- All four outcome types (granted/rejected/queued/preempting) with reason codes
- Reasoned rejection when a conflicting owner attempts to claim focus

**Acceptance:** the framework can explain why an agent did or did not accept a cycle request. Lease conflict outcomes are observable via events.

### Phase 4 — RuntimeActivity model

- Implement RuntimeActivity object with pause/resume/abort
- Evidence requirement hooks
- Wire current cycle handlers and workload runners to emit RuntimeActivity records

**Acceptance:** current work is observable as a RuntimeActivity, not hidden in prompt history. No regression in cycle execution.

---

## 15. Acceptance Criteria

The SIP is successful when:

1. **Runtime clarity** — the framework can always answer: what mode? what assignments? what RuntimeActivity? what may claim the agent next?
2. **Exclusivity** — an agent cannot be simultaneously in Duty, Cycle, and Ambient. Current mode is singular and explicit.
3. **Scheduling sanity** — cycle recruitment respects future duty windows AND the reserve buffer.
4. **Recallability** — Ambient behavior can be recalled. Duty transitions can preempt Ambient. Policy governs whether Cycle can preempt Duty.
5. **Cycle preservation** — existing cycle architecture remains intact. No regressions in `run_regression_tests.sh`.
6. **Duty realism** — Duty supports explicit windows, hard and soft strictness with operational semantics in §12, and service-like operational work.
7. **Lease as gate** — no attention-owning RuntimeActivity begins without a compatible FocusLease.
8. **Explainability** — every transition and lease decision carries a reason code from the canonical set.
9. **Incremental rollout** — Phases 1–4 ship and are useful even before embodiment or Temporal integration land.

---

## 16. Canonical Example: Nightly Research Duty

End-to-end walkthrough exercising the v1.1 model:

| Time | State | Event |
|------|-------|-------|
| 00:30 UTC | mode=`ambient`, assignment=`nightly_research` (window 01:00–06:00, hard, reserve_before=15m) | — |
| 00:45 UTC | Reserve buffer begins | A cycle request arrives. Recruitment rejected with `cycle_recruitment_rejected_upcoming_duty`; event emitted. |
| 01:00 UTC | Scheduler requests `ambient → duty` | Transition validated: reason=`duty_window_opened`, FocusLease acquired by `nightly_research`, RuntimeActivity `research_scan` started. |
| 03:15 UTC | Human asks for status | Direct interaction handled cross-cutting per duty policy (`answer`); mode unchanged; no transition. |
| 04:30 UTC | Embodied action attempt (v1.2 hypothetical) | Requires capability-aware lease check; in v1.1 scope: not applicable. |
| 06:00 UTC | DutyWindow ends | RuntimeActivity completes; FocusLease released; reason=`duty_window_closed`; transition `duty → ambient`; event emitted. |

Every step produces a queryable event with a reason code. Nothing is implicit.

---

## 17. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mode taxonomy expands over time | Stay with three top-level modes; resist additions |
| Direct interaction creeps in as a peer mode | Treat as cross-cutting; document explicitly in umbrella |
| Duty becomes a permanent identity lock | Use Assignment + DutyWindow + current mode separation |
| Ambient becomes uncontrolled autonomy | Hard rule in §5.2 forbidding irreversible action without lease+activity |
| Hidden attention contention | FocusLease is the single source of truth for ownership |
| RuntimeActivity becomes a parallel execution model | §7 mapping table; reviewers must reject any PR that makes RuntimeActivity *do* work |
| State persistence collides with cycle registry | Reuse Postgres + connection pool; share migrations sequence |
| Activity name collision with Temporal Activity | Canonical name `RuntimeActivity` everywhere in code/schema |

---

## 18. Open Questions

1. Is `hard | soft` duty strictness sufficient for v1.1, or is a richer policy model needed?
2. Should the agent factory accept new constructor parameters for runtime state, or should it be injected via the existing `PortsBundle`?
3. How should Postgres migrations be sequenced to avoid colliding with in-flight 1.0.x work on the Spark?
4. Should embodied actions in v1.2 require the primary FocusLease, or a separate EmbodimentLease? (Decision deferred to v1.2 SIP.)
5. Should `current_runtime_activity_id` allow multiple concurrent activities, or strictly one? (Recommend strict-one for v1.1; multi-activity is a future expansion.)

---

## 19. References

- Parent vision: `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (canonical reason codes, event names, terminology)
- Original full proposal: commit `76a1f90` on main
- Related: SIP-0042 (LanceDB Semantic Memory), SIP-0061 (LangFuse Observability), SIP-0067 (Postgres Cycle Registry), SIP-0071 (Builder Role)
- W3C SCXML — https://www.w3.org/TR/scxml/
- Kubernetes Leases — https://kubernetes.io/docs/concepts/architecture/leases/
- BPMN 2.0.2 — https://www.omg.org/spec/BPMN/2.0.2/PDF
