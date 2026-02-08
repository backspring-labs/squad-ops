# IDEA: Cycle & Pulse Execution Model  
## FSM-Based Execution Semantics for SquadOps

**Status:** IDEA – Conceptual Foundation  
**Scope:** Architecture & Execution Semantics  
**Binding:** Non-normative (informs future SIPs)

---

## 1. Problem Statement

As SquadOps evolves beyond simple task execution into a **benchmarkable, inspectable, and educational agent coordination framework**, it requires a clear and explicit execution model that can answer:

- Where is a cycle right now?
- What is actively happening?
- What is blocked, and why?
- How do we visualize execution without leaking orchestration internals?
- How do we measure performance, utilization, and coordination meaningfully?

Early designs risked conflating:
- lifecycle phases
- execution windows
- coordination constructs

This IDEA establishes a **clean separation of concerns** between:

- **Cycle Phases**
- **Pulses**
- **Gates**
- **Task Flow Policies**

---

## 2. Design Principles

1. **Explicit state machines beat implicit flags**
2. **Macro lifecycle ≠ micro execution**
3. **Visualization drives architectural clarity**
4. **Execution semantics must be API-visible**
5. **Orchestration engines are implementation details**

---

## 3. Cycle Phases (Macro Lifecycle)

### Definition

**Cycle Phases** represent the **structural lifecycle** of a cycle.

They answer:

> *Where is this cycle in its overall lifecycle?*

### Characteristics

- Global
- Invariant across projects
- Non-repeatable
- FSM-backed
- Terminal-aware

### Canonical Cycle Phases

These phases form the **Cycle FSM**:

1. `CREATED`  
   Cycle record exists; nothing executed.

2. `READY` *(optional but useful)*  
   Intent resolved and validated; ready to start.

3. `RUNNING`  
   Execution is active (pulses may run or block).

4. `PAUSED`  
   Explicit pause (human or system-level).

5. `WRAP_UP`  
   Execution complete; summary artifacts being produced.

6. `SCORING`  
   Scorecard and metrics generation (if enabled).

7. `COMPLETED`  
   Terminal success.

8. `FAILED`  
   Terminal failure.

### Key Constraint

> **Pulses do not advance cycle phases.**  
> Phase transitions are driven by lifecycle events, not task completion.

---

## 4. Pulses (Micro Execution Windows)

### Definition

A **Pulse** is a **bounded execution window inside the RUNNING phase** that groups related work for coordination, observability, and benchmarking.

They answer:

> *What chunk of work is happening right now?*

### Characteristics

- Exist only during `RUNNING`
- Optional
- Repeatable
- Runtime constructs
- Can overlap or sequence
- May produce artifacts
- May block on gates

### What Pulses Are *Not*

- Not lifecycle phases
- Not permanent structure
- Not wrap-up or scoring containers
- Not orchestration DAGs

---

## 5. Pulse State Machine (Pulse FSM)

Pulses have their **own lightweight FSM**, separate from the Cycle FSM.

### Pulse States

- `PLANNED`
- `RUNNING`
- `BLOCKED`
- `COMPLETED`
- `FAILED`
- `SKIPPED` *(optional)*

### Relationship to Cycle FSM

- Cycle remains `RUNNING` while pulses are `RUNNING` or `BLOCKED`
- Cycle transitions to `WRAP_UP` only after execution pulses complete
- Pulse failure may or may not fail the cycle (policy-driven)

---

## 6. Gates (Blocking Conditions)

### Definition

A **Gate** is a named condition that blocks progress **inside a pulse**.

### Gate States

- `OPEN`
- `WAITING`
- `RELEASED`
- `FAILED`

### Key Distinction

- **Cycle PAUSED** → explicit lifecycle pause  
- **Pulse BLOCKED** → waiting on a gate

### Example: Planning Pause

- Cycle Phase: `RUNNING`
- Pulse State: `BLOCKED`
- Gate: `PLAN_APPROVAL = WAITING`

This avoids polluting the cycle FSM with execution details.

---

## 7. Task Flow Policy (Coordination Shape)

### Definition

The **Task Flow Policy** describes the *shape of coordination* **inside a pulse**.

### Examples

- `sequential`
- `fan_out_fan_in`
- `fan_out_soft_gates`

### Responsibilities

- Declares coordination intent
- Is persisted for observability
- Does **not** expose orchestration engine internals

Prefect (or any runtime) owns the concrete DAG.

---

## 8. Why This Separation Matters

This model enables:

- Clear SOC visualization
- Deterministic benchmarking
- Accurate utilization metrics
- Meaningful blocked-time analysis
- Model vs coordination performance attribution
- Clean API contracts
- Long-term extensibility

It prevents:

- Status-string ambiguity
- Implicit execution behavior
- UI-driven architecture
- Runtime coupling
- Conceptual drift

---

## 9. Visualization Implications (Non-UI)

This execution model naturally supports:

- **Cycle timeline views** (phases)
- **Pulse execution views** (current work)
- **Gate indicators** (blocking reasons)
- **Agent activity overlays**
- **Benchmark comparisons across runs**

Without introducing new abstractions later.

---

## 10. Relationship to Benchmark Example Apps

- **hello_squad**  
  Minimal pulses, no gates, straight-through execution.

- **run_crysis**  
  Multiple pulses, explicit planning gate, per-agent capability stress.

- **group_run**  
  Many pulses, soft gates, coordination and handoff stress.

Same execution model. Different stressors.

---

## 11. Why This Is an IDEA (Not a SIP Yet)

This document:

- establishes vocabulary
- locks conceptual boundaries
- informs future SIPs (API, SOC, scoring)

It deliberately avoids:

- endpoint definitions
- persistence schemas
- UI commitments
- version binding

Those belong in subsequent SIPs.
