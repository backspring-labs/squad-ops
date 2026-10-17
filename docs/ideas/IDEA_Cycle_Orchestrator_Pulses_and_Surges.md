# IDEA: Cycle Orchestrator, Pulses, and Surges  
*(Aligned with CYCLE_PROTOCOL.md)*

> **Non-normative design history** (the owner's ruling Q33, 2026-10-17; committed with Project
> Lifecycle Management's revision 5, PR #2401). SIP-0070 and the code define the Cycle and Pulse that
> SquadOps runs, and they govern wherever this document differs:
> - **Pulse:** a bounded execution interval set by cadence limits (`max_pulse_seconds`,
>   `max_tasks_per_pulse`, overridable in a request profile's `defaults.cadence_policy`). The executor
>   closes it between dispatches and never preempts a task in flight, and guardrail checks run at its
>   boundary (`src/squadops/execution/pulse_boundary_runner.py`). This document's Pulse, a change in
>   coordination topology, is a different construct.
> - **Recovery:** the repair loop at a pulse boundary and the correction loop's decisions, its rewind
>   included (SIP-0086). This document makes the Pulse the only rewind boundary.
> - **Surge:** this document's term; the code has no Surge.
> - **`CYCLE_PROTOCOL.md`,** which this document treats as canonical, is not in the repository.
>
> Current Cycle and Pulse behavior is preserved. The portfolio records this document in its intake log
> (`sips/PORTFOLIO.md` §6).

## Intent

This IDEA refines and aligns the **Cycle Orchestrator / Pulse model** with the canonical definitions in `CYCLE_PROTOCOL.md`, while incorporating the newly clarified concept of a **Surge**.

The goal is to preserve:
- throughput and parallelism
- strong coordination semantics
- rewind and recovery guarantees
- observability and governance

…without reintroducing implicit synchronization barriers or human process metaphors.

This document **corrects earlier ambiguities**, clarifies boundaries between **Cycle, Pulse, Task, and Surge**, and introduces **surge tagging** as a first‑class observability and planning construct.

No code is included. This is an intent‑ and semantics‑level alignment document.

---

## Canonical Objects (Per CYCLE_PROTOCOL)

The following definitions are **authoritative and unchanged** in intent.

### Cycle
A **Cycle** is the top‑level governed execution container.

A cycle:
- has a single authoritative lifecycle
- owns rewind and recovery semantics
- contains pulses and tasks
- persists full execution history

A cycle answers:
> *“What is the system trying to accomplish, and what is its current execution truth?”*

---

### Task
A **Task** is the atomic unit of execution.

A task:
- is executed by an agent
- produces outcomes and artifacts
- may be long‑running
- may span pulses
- participates in dependency graphs

Tasks are the **throughput carriers** of the system.

---

## Refined Concepts

### Cycle Orchestrator (Aligned Replacement Term)

The **Cycle Orchestrator** is the authoritative coordination authority defined implicitly by `CYCLE_PROTOCOL.md`.

It is refined here for clarity, not re‑scoped.

> **The Cycle Orchestrator evaluates state transitions, governs coordination, determines runnable work, and emits pulses when coordination structure changes — without executing tasks itself.**

Key alignment points:
- Single authority (no distributed pulse emission)
- Owns pulse creation and lifecycle
- Owns pause, resume, rewind, and governance actions
- Agents and UI report or request, but never decide

---

## Pulse (Refined and Corrected)

### What a Pulse Is

A **Pulse** is a **coordination boundary**, not an execution boundary.

> **A Pulse represents a discrete change in coordination structure within a cycle.**

A pulse:
- has identity and ordering
- is logged and observable
- may activate or rewire tasks
- may evaluate or introduce gates
- is the **only legal rewind boundary**

### What a Pulse Is *Not*
A pulse is **not**:
- a phase
- a sprint
- a unit of work
- a time slice
- a requirement that all spawned tasks complete

This explicitly corrects earlier interpretations that risked turning pulses into performance bottlenecks.

---

## Pulse Emission Invariant (Aligned)

> **A pulse is emitted only when coordination topology changes — not when work merely progresses.**

This is consistent with:
- dependency graph mutation
- governance action
- convergence gate evaluation
- recovery or rewind conditions

Task completion alone **does not** imply pulse emission.

---

## Introducing the Surge (New, Orthogonal Concept)

### Definition

A **Surge** is a *logical grouping of related tasks* created in response to a pulse.

> **A Surge represents an intentional burst of related work, not a coordination boundary.**

This distinction is critical.

- Pulses change *structure*
- Surges group *activity*

A surge:
- is always associated with exactly one pulse (origin)
- may include tasks that run long after the pulse closes
- does **not** gate the cycle
- does **not** imply synchronization
- exists purely for planning, reasoning, and observability

---

## Why Surge Is Needed (Correction of Earlier Tension)

Earlier discussions implicitly overloaded **Pulse** with two roles:
1. coordination change
2. grouping related activities

This created conceptual strain.

**Surge cleanly separates those concerns.**

- Pulse = *why coordination changed*
- Surge = *what work was intentionally launched as a result*

---

## Surge Semantics

A surge:
- has a `surge_id`
- references its originating `pulse_id`
- contains a set of tasks (initial and possibly expanded)
- may overlap temporally with other surges
- may complete long after newer pulses exist

Surges are **non‑authoritative**. They do not drive state transitions.

---

## Observability & SOC Implications

### Task Marking / Color Coding

Tasks may be:
- tagged with `surge_id`
- visually color‑coded in the SOC
- filtered by surge origin
- viewed as a cohesive intent group

This enables:
- understanding *why* tasks exist
- reviewing execution quality per surge
- diagnosing thrash (many surges, low throughput)
- diagnosing under‑coordination (few surges, blocked tasks)

---

### Kanban View (Aligned)

- Columns represent **task lifecycle**
- Tasks flow independently
- Surge color or badge provides contextual grouping
- Pulses appear as:
  - timeline markers
  - annotations
  - coordination events

No swim‑lanes for pulses.
Optional swim‑lanes for surges (purely visual).

---

## Pulse vs Surge vs Task (Summary Table)

| Concept | Purpose | Authoritative | Throughput Impact |
|------|------|------|------|
| Cycle | Governed execution container | Yes | Indirect |
| Pulse | Coordination change | Yes | Indirect |
| Surge | Intentional work grouping | No | None |
| Task | Execution unit | Yes (locally) | Direct |

---

## Rewind Alignment

Rewind semantics remain **pulse‑scoped**, per `CYCLE_PROTOCOL.md`.

- Rewind targets a prior pulse
- All surges originating after that pulse are invalidated
- Task history is preserved, never erased
- New recovery pulses and surges may be created

Surges simplify rewind reasoning by making intent boundaries visible.

---

## Safety Invariants (Aligned + Extended)

1. Only the Cycle Orchestrator may emit pulses
2. Pulses are the only rewind boundaries
3. Surges never gate execution
4. Tasks may outlive their originating pulse
5. Task completion does not imply pulse emission
6. Pulse rate is a diagnostic signal, not a KPI
7. History is immutable; recovery is additive

---

## Final Framing (Locked)

> **The Cycle Orchestrator governs coordination.  
Pulses mark structural change.  
Surges express intent.  
Tasks deliver throughput.**

This separation preserves performance, clarity, and long‑term system integrity.

---

*End of IDEA (Aligned Edition).*