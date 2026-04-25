# SIP: Agent Runtime State — Modes, Duty Windows, Focus, and Activity

**Status:** Proposed (draft)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 1
**Targets:** v1.1
**Parent vision:** `sips/proposed/SIP-Agent-Runtime-Modes.md` (umbrella index)
**Sibling SIPs:**
- `SIP-Agent-Embodiment-Substrate.md` (v1.2 candidate, builds on this)
- `SIP-Duty-Durability-Temporal.md` (v1.3 candidate, builds on this)

---

## 1. Summary

This SIP introduces the **runtime-state foundation** for persistent SquadOps agents. It is the first of three SIPs that emerged from splitting the original umbrella proposal (`SIP-Agent-Runtime-Modes.md`).

It proposes the minimum runtime primitives needed to make persistent agents observable, schedulable, and recallable, without introducing embodiment or durable workflow concerns.

The four primitives:

1. **Mode** — current operating posture, exactly one of `duty | cycle | ambient`
2. **Assignment + Duty Window** — durable commitments and the time ranges in which they may claim the agent
3. **Focus Lease** — explicit ownership claim over the agent's primary attention
4. **Activity** — the concrete unit of work currently executing, with pause/resume/abort semantics

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

1. Preserve the cycle model as the canonical mechanism for bounded, acceptance-oriented work.
2. Introduce persistent runtime behavior without forcing all activity into cycles.
3. Support service-like operational responsibility through Duty mode with explicit windows.
4. Make current state, future commitments, and immediate action separately observable.
5. Allow interruption and recall through explicit policy rather than implicit prompt drift.
6. Keep the model small enough to ship in v1.1.

---

## 4. Non-Goals

This SIP does **not** propose:

- Embodiment abstractions (Mineflayer, Discord, browser) — see `SIP-Agent-Embodiment-Substrate.md`
- Location modeling — see `SIP-Agent-Embodiment-Substrate.md`
- Temporal or any external workflow durability layer — see `SIP-Duty-Durability-Temporal.md`
- Replacing the current cycle mechanism
- A fully autonomous "agent life" loop
- Direct human interaction as a peer mode (treated as cross-cutting; see §8)

---

## 5. Proposed Runtime Model

### 5.1 Top-Level Modes

An agent has exactly one **current mode** at a time:

- `duty` — on-duty, service-responsible, availability-constrained
- `cycle` — bounded, formal, assigned work with explicit completion semantics
- `ambient` — off-duty, low-priority, interruptible background presence

These modes are **mutually exclusive**. They imply different rules for interruptibility, accountability, scheduling, recall policy, and what commitments the agent is allowed to accept. They are operational postures, not task labels.

### 5.2 Mode definitions

**Duty.** The agent is responsible for a role or function requiring availability and policy-governed behavior. Examples: customer support, inventory watch, nightly research, monitoring/moderation.

**Cycle.** The agent is committed to bounded assigned work with acceptance criteria. Examples: building a web app, executing an experiment, producing an artifact, performing a validation pass. This remains the most structured form of execution in SquadOps.

**Ambient.** The agent is online, present, lightly available, and off-duty. Bounded, interruptible, low-resource. Not a loophole for uncontrolled autonomous drift — a low-priority interruptible background state.

---

## 6. Orthogonal Concepts: Mode vs Assignment vs Schedule vs Focus vs Activity

The most important architectural distinction: **mode is not the same as assignment or schedule.**

| Concept | Answers | Example |
|---------|---------|---------|
| **Mode** | What is the agent doing right now? | `ambient` |
| **Assignment** | What role or commitment is associated with the agent? | `nightly_research`, `support_duty` |
| **Schedule / Duty Window** | When is that assignment active or claimable? | `01:00–06:00 UTC` |
| **Focus** | What currently owns the agent's primary attention within its current mode? | `handling support case #184` |
| **Activity** | What concrete action is happening right now? | `summarize_findings`, `classify_ticket` |

This separation enables a coherent state like:

- current mode = `ambient`
- duty assignment = `nightly_research`
- duty window starts at `01:00`
- cycle eligible = `true until reserve threshold`

The agent can be ambient now, recruited into a short cycle if safe, and transition into Duty automatically when the window opens. That is operationally coherent and significantly safer than treating "free" and "committed" as vague prompt-level concepts.

---

## 7. Core Runtime Primitives

### 7.1 Agent Runtime State

A persistent agent should expose runtime state such as:

- `agent_id`
- `mode` — `duty | cycle | ambient`
- `runtime_status` — `online | idle | busy | paused | degraded | recovering | offline`
- `focus` — string label for primary concern within current mode
- `activity_id` — reference to current Activity, or null
- `interruptibility` — `none | low | medium | high`
- `last_heartbeat_at`
- `current_assignment_ref` — null in pure ambient

### 7.2 Assignment

A durable relationship between an agent and a future or potential responsibility.

Suggested fields:

- `assignment_id`
- `assignment_type` — `duty | reserve | cycle_eligibility`
- `assigned_role`
- `priority`
- `strictness` — `hard | soft`
- `active_window` — start, end, timezone
- `recall_policy` — `immediate | graceful | none`
- `allowed_off_window_modes`

An agent can hold an assignment without currently being in the corresponding mode.

### 7.3 Duty Window

Duty windows are explicit. Duty is not a permanent identity lock.

Suggested fields:

- `window_start`, `window_end`, `timezone`
- `strictness: hard | soft`
- `grace_before_start`, `grace_after_end`

**Hard duty window:** during the window, the agent is reserved for duty only.

**Soft duty window:** during the window, duty has priority, but short preemptible work may be allowed if the duty can reclaim focus.

### 7.4 Focus Lease

A focus lease is the runtime claim over an agent's primary attention. Conceptually analogous to the Kubernetes Lease pattern, but not literally implemented as one.

Suggested fields:

- `lease_id`
- `owner_type` — `duty | cycle | ambient`
- `owner_ref`
- `acquired_at`
- `expires_at` or `renewal_policy`
- `interruptibility`
- `recall_policy`

The lease is what prevents two owners from ambiguously claiming the same agent.

### 7.5 Activity

The concrete unit of work currently being performed.

Suggested fields:

- `activity_id`
- `activity_type`
- `mode` — which top-level mode this activity belongs to
- `goal`
- `priority`
- `can_pause`, `can_resume`, `can_abort`
- `completion_conditions`
- `evidence_requirements`

Activities make current work observable without digging into prompt history.

---

## 8. Direct Interaction Is Cross-Cutting

Direct human interaction is **not** a peer mode. It is a cross-cutting interaction path that may occur against an agent already in one of the three top-level modes.

- In **Ambient**, direct interaction usually interrupts easily.
- In **Duty**, direct interaction may be limited, deferred, or handled minimally.
- In **Cycle**, direct interaction may return status or require priority escalation.

This keeps the mode model small while preserving the reality that humans may speak to agents in any mode.

---

## 9. Cycle Preservation

This SIP preserves Cycle as the canonical bounded-work mechanism. Cycle execution semantics, planning workloads, acceptance criteria, gates, and artifacts are unchanged.

What changes: an agent may decline cycle recruitment if a hard duty window is approaching, or if a focus lease cannot be granted under current policy. That decision becomes **explainable** rather than implicit.

---

## 10. Data Model Sketch

```yaml
AgentRuntimeState:
  agent_id: string
  mode: duty | cycle | ambient
  runtime_status: online | idle | busy | paused | degraded | recovering | offline
  focus: string
  activity_id: string | null
  interruptibility: none | low | medium | high
  last_heartbeat_at: timestamp
  current_assignment_ref: string | null

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
  recall_policy: immediate | graceful | none
  allowed_off_window_modes:
    - ambient
    - cycle

FocusLease:
  lease_id: string
  owner_type: duty | cycle | ambient
  owner_ref: string
  acquired_at: timestamp
  renewal_policy: heartbeat | ttl | fixed_window
  interruptibility: none | low | medium | high
  recall_policy: immediate | graceful | none

Activity:
  activity_id: string
  mode: duty | cycle | ambient
  activity_type: string
  goal: string
  priority: integer
  can_pause: boolean
  can_resume: boolean
  can_abort: boolean
  completion_conditions: []
  evidence_requirements: []
```

Not final schema. Sufficient to prove the architecture.

---

## 11. Transition Semantics

Minimal transitions:

- `ambient -> cycle`
- `ambient -> duty`
- `cycle -> ambient`
- `cycle -> duty` (only if policy permits preemption)
- `duty -> ambient`
- `duty -> cycle` (generally only after duty window ends or if policy explicitly allows)

Rules:

- Mode transitions are evented and auditable
- Transitions carry reason codes
- Higher-priority transitions do not silently discard current activity state — interruptions explicitly pause, abort, or checkpoint the current activity
- A focus lease must be released or revoked before a new owner can acquire one

---

## 12. Persistence

Runtime state, assignments, and focus leases need a durable home. Recommended placement (to be confirmed during design review):

- **AgentRuntimeState, FocusLease** — Postgres (cycle registry already lives there; same connection pool)
- **Assignment** — Postgres
- **Activity** — Postgres for the durable record; in-memory for the live working set

Heartbeat already flows through `AgentHeartbeatReporter`; extending it to carry mode/focus is the cheapest path.

LanceDB (SIP-042) is **not** the right home — semantic memory is for retrieval, not transactional state.

---

## 13. Implementation Phases

### Phase 0 — Vocabulary freeze

- SIP approval
- Lock terminology for `mode`, `assignment`, `window`, `focus`, `activity`
- No code changes

### Phase 1 — Minimal runtime state

- Add `mode`, `runtime_status`, `focus`, `activity_id`, heartbeat fields to agent runtime
- Extend `AgentHeartbeatReporter` to carry the new fields
- Postgres migration for `agent_runtime_state` table

**Acceptance:** an operator can query an agent's current mode and current activity.

### Phase 2 — Assignments and duty windows

- Implement Assignment model and Postgres table
- Implement Duty Window with hard/soft strictness
- Add a transition scheduler (initially in-process, no Temporal)

**Acceptance:** an agent can be Ambient now and scheduled to enter Duty later. An upcoming hard duty window restricts cycle recruitment per policy.

### Phase 3 — Focus lease

- Implement FocusLease model with acquire/release/renew semantics
- Reasoned rejection when a conflicting owner attempts to claim focus

**Acceptance:** the framework can explain why an agent did or did not accept a cycle request.

### Phase 4 — Activity model

- Implement Activity object with pause/resume/abort
- Evidence requirement hooks
- Wire current cycle handlers to emit Activity records

**Acceptance:** current work is observable as an Activity, not hidden in prompt history.

---

## 14. Acceptance Criteria

The SIP is successful when:

1. **Runtime clarity** — the framework can always answer: what mode? what assignments? what activity? what may claim the agent next?
2. **Exclusivity** — an agent cannot be simultaneously in Duty, Cycle, and Ambient. Current mode is singular and explicit.
3. **Scheduling sanity** — cycle recruitment respects future duty windows and reservation policy.
4. **Recallability** — Ambient behavior can be recalled. Duty transitions can preempt Ambient. Policy governs whether Cycle can preempt Duty.
5. **Cycle preservation** — existing cycle architecture remains intact. No regressions in `run_regression_tests.sh`.
6. **Duty realism** — Duty supports explicit windows, hard and soft strictness, and service-like operational work without pretending it is a cycle.
7. **Incremental rollout** — Phases 1–4 ship and are useful even before embodiment or Temporal integration land.

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mode taxonomy expands over time | Stay with three top-level modes; resist additions |
| Direct interaction creeps in as a peer mode | Treat as cross-cutting; document explicitly |
| Duty becomes a permanent identity lock | Use assignment + window + current mode separation |
| Ambient becomes uncontrolled autonomy | Keep bounded, low-priority, interruptible; enforce in policy |
| Hidden attention contention | Focus lease as the single source of truth for ownership |
| State persistence collides with cycle registry | Reuse Postgres + connection pool; share migrations sequence |

---

## 16. Open Questions

1. Is `hard | soft` duty strictness sufficient for v1.1, or is a richer policy model needed?
2. Should cycle recruitment be blocked by a configurable pre-duty reserve buffer (e.g., no new cycle within 30 min of a duty window)?
3. Does the agent factory need new constructor parameters for runtime state, or should it be injected via the existing `PortsBundle`?
4. How should Postgres migrations be sequenced to avoid colliding with in-flight 1.0.x work on the Spark?
5. Should `runtime_status` be inferred from the current activity, or stored independently?

---

## 17. References

- Parent vision: `sips/proposed/SIP-Agent-Runtime-Modes.md`
- Original full proposal: commit `76a1f90` on main
- Related: SIP-0042 (LanceDB Semantic Memory), SIP-0061 (LangFuse Observability), SIP-0067 (Postgres Cycle Registry), SIP-0071 (Builder Role)
- W3C SCXML — https://www.w3.org/TR/scxml/
- Kubernetes Leases — https://kubernetes.io/docs/concepts/architecture/leases/
- BPMN 2.0.2 — https://www.omg.org/spec/BPMN/2.0.2/PDF
