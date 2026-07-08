# Roadmap Idea: SquadOps Runtime Maturity → Loop Policy → Capability-Backed Agents

**Status:** Idea / Roadmap Note  
**Date:** 2026-07-01  
**Owner:** Backspring Labs / SquadOps  
**Related:** Runtime Modes, Duty Assignment, Cycle Loop Policy, Capability Pack Plugins, Skill-Mediated Tool Use, Iris/Glyph Design Capability Reference Pack

---

## 1. Executive Summary

This roadmap captures the proposed sequencing for SquadOps after the current 1.1 hardening work.

The central idea:

> **SquadOps 1.x should mature the execution/runtime substrate before SquadOps 2.0 introduces capability-backed, memory-aware, tool-governed specialist agents.**

The Capability Pack Plugin SIP and Skill-Mediated Tool Use amendment feel like a true **2.0 target**. They change the meaning of what a SquadOps agent is: from primarily a prompt-defined role with handlers into a capability-backed specialist operating from resources, memory, tools/skills, working sets, and evidence.

Before that 2.0 shift, SquadOps should first finish:

1. **1.1 hardening** — make the existing cycle/runtime/artifact foundation reliable.
2. **1.2 runtime/presence maturity** — complete richer runtime posture and/or embodiment substrate work.
3. **1.3 duty durability / duty roster assignment** — make persistent operational responsibility visible, schedulable, recallable, and durable.
4. **Late 1.x loop policy** — add verification-guided continuance across runs/cycles.
5. **2.0 capability-backed agents** — introduce capability pack plugins, working sets, scoped memory, artifact workspaces, and skill-mediated tool use.

This sequencing keeps each conceptual layer clean:

| Layer | Question answered |
|---|---|
| Runtime hardening | Can SquadOps reliably execute and observe bounded work? |
| Duty/runtime assignment | Can agents hold operational responsibilities without blurring modes? |
| Loop policy | Can SquadOps continue improving toward a goal using evidence and verification? |
| Capability-backed agents | Can agents become reusable, memory-aware, tool-governed specialists? |

---

## 2. Roadmap Thesis

The roadmap should preserve this distinction:

> **1.x is about execution maturity. 2.0 is about agent expertise maturity.**

### 1.x execution maturity

1.x should focus on making SquadOps reliable, observable, schedulable, and capable of bounded iterative improvement.

This includes:

- reliable cycle execution,
- clearer runtime modes,
- duty assignments,
- runtime state visibility,
- focus and activity tracking,
- duty durability,
- artifact quality,
- verification,
- loop/continuance policy.

### 2.0 agent expertise maturity

2.0 should focus on making agents truly capability-backed specialists.

This includes:

- Capability Pack Plugins,
- Capability Binding Contracts,
- Skill-Mediated Tool Use,
- Working Set Assembly,
- Squad Artifact Workspaces,
- scoped memory,
- evidence ledgers,
- reusable design/architecture/QA/security/domain capability packs,
- Iris/Glyph as the first design reference capability binding.

---

## 3. Proposed Release Sequence

```text
1.1 — Runtime and cycle hardening
1.2 — Embodiment substrate / richer runtime presence
1.3 — Duty durability, duty roster assignment, runtime console maturity
1.x — Loop Policy for iterative cycle/run continuance
2.0 — Capability Pack Plugins, working sets, scoped memory, skill-mediated tool use
```

This keeps the 2.0 SIP from landing before the runtime substrate is mature enough to support it.

---

## 4. Phase 1: SquadOps 1.1 — Runtime and Cycle Hardening

### 4.1 Intent

1.1 should make the current platform dependable.

The goal is not to add large new abstractions. The goal is to stabilize the foundation that later runtime, loop, and capability systems depend on.

### 4.2 Focus areas

1. Cycle execution reliability
2. Task/run status correctness
3. Artifact persistence and lineage
4. Telemetry and evidence quality
5. Acceptance checks and validation
6. Agent status/runtime-state consistency
7. Existing handler behavior
8. Regression coverage
9. CLI/API/operator visibility
10. Hardening around failure states

### 4.3 What 1.1 should avoid

1.1 should avoid pulling in:

- Capability Pack Plugins,
- Iris/Glyph design capability runtime,
- full skill-mediated tool governance,
- scoped memory promotion flows,
- long-running autonomous loops,
- broad new tool surfaces.

### 4.4 Guiding sentence

> **1.1 should make the existing machine trustworthy before adding more intelligence to it.**

---

## 5. Phase 2: SquadOps 1.2 — Embodiment Substrate / Richer Runtime Presence

### 5.1 Intent

1.2 should mature the idea that agents can have runtime presence in external surfaces without confusing that presence with agent identity or agent intent.

This may include embodiment substrate work, Discord presence, richer runtime surface attachments, and clearer observability of where/how an agent is available.

### 5.2 Key boundary

The runtime should preserve the distinction between:

| Concept | Meaning |
|---|---|
| Agent identity | Durable agent identity and role |
| RuntimeMode | Current posture: duty, cycle, ambient |
| Embodiment | External surface attachment |
| Capability | Work the agent can perform |
| Assignment | Commitment or responsibility |
| RuntimeActivity | Observable current unit of work |

### 5.3 Why this comes before loop policy

Loop policy will be cleaner if runtime state and embodiment boundaries are already settled.

Without this, loops may accidentally become:

- hidden ambient autonomy,
- duty substitutes,
- background execution hacks,
- surface-specific agents.

### 5.4 Guiding sentence

> **1.2 should make agent presence observable without letting presence become intent.**

---

## 6. Phase 3: SquadOps 1.3 — Duty Durability, Duty Roster Assignment, and Runtime Console Maturity

### 6.1 Intent

1.3 should complete the operational responsibility layer.

Duty should become a first-class, visible, schedulable, recallable, durable responsibility model — not a vague prompt instruction and not a hidden loop.

### 6.2 Focus areas

1. Duty assignment records
2. Duty windows
3. Duty roster binding
4. Recall policy
5. Reserve windows
6. FocusLease integration
7. RuntimeActivity visibility for duty work
8. Duty continuity and handoff
9. Durable wake/recall mechanics
10. Continuum console surfaces for runtime/duty visibility

### 6.3 Duty is not loop policy

Duty answers:

> What operational responsibility does this agent hold, and when may it claim attention?

Loop policy answers:

> Given verification/evidence, should work continue, repair, retry, fork, escalate, or stop?

Those must remain separate.

### 6.4 Duty is not capability binding

Duty may activate an agent/capability binding later, but duty itself is not the capability.

Example:

- Joi may hold a Spanish coaching duty assignment.
- The actual teaching/review capability may be activated during that duty window.
- The duty assignment is the commitment.
- The capability is the type of work.
- The skill/tool surface is what the capability may use.

### 6.5 Guiding sentence

> **1.3 should make persistent responsibility explicit, durable, and observable without turning Duty into a generic background loop.**

---

## 7. Phase 4: Late 1.x — Loop Policy for Iterative Cycle/Run Continuance

### 7.1 Intent

After 1.2/1.3 and hardening, SquadOps should add a late 1.x enhancement SIP for **Loop Policy**.

This should come before the 2.0 capability-pack architecture because loop policy is still part of execution maturity.

The loop answers:

> How does SquadOps continue improving toward a goal across runs and/or cycles using verification, acceptance evidence, and continuance policy?

### 7.2 Proposed SIP title ideas

Possible titles:

- **SIP: Loop Policy for Iterative Cycle Continuance**
- **SIP: Cycle Loop Policy and Verification-Guided Continuance**
- **SIP: Verification-Guided Loop Policy for Runs and Cycles**
- **SIP: Loop Policy for Goal-Oriented Cycle Improvement**

The important word is **Policy**.

The loop should not sound like a new top-level runtime mode.

### 7.3 Core invariant

> **Loop is a continuance policy around bounded work. It does not replace Cycle, Duty, Run, Task, FocusLease, or RuntimeActivity.**

### 7.4 Conceptual model

```text
Goal / Request
  ↓
Cycle
  ↓
Run(s)
  ↓
Verification / Acceptance Evidence
  ↓
Loop Policy Decision
  ↓
continue | repair | retry | fork | escalate | stop | summarize
```

### 7.5 What a loop owns

A Loop Policy may own:

- continuance rules,
- stop conditions,
- retry limits,
- repair activation criteria,
- verification thresholds,
- escalation rules,
- run/cycle summary logic,
- evidence review rules,
- improvement target tracking,
- decision history.

### 7.6 What a loop does not own

A Loop Policy must not own:

- agent identity,
- agent runtime mode,
- duty assignment,
- embodiment,
- FocusLease authority,
- task execution semantics,
- handler behavior,
- memory promotion,
- external tool authority,
- product scope.

### 7.7 Loop decision outcomes

Initial decision outcomes could include:

| Outcome | Meaning |
|---|---|
| `continue` | Proceed with another run/cycle using current strategy |
| `repair` | Activate correction path based on failed verification |
| `retry` | Repeat a failed or incomplete step with bounded changes |
| `fork` | Create an alternate path/approach |
| `escalate` | Ask operator/lead/higher-capability agent for decision |
| `stop_success` | Goal satisfied |
| `stop_failure` | Goal cannot be met under current constraints |
| `summarize` | Produce final state and recommendations |
| `defer` | Pause until external condition, input, or duty window |

### 7.8 Loop inputs

Loop policy should evaluate:

- goal/request,
- run outputs,
- artifact evidence,
- verification results,
- acceptance checks,
- QA findings,
- build/test status,
- operator gates,
- failure reasons,
- budget usage,
- time limits,
- prior loop decisions,
- open questions/blockers.

### 7.9 Loop outputs

Loop policy should produce:

- loop decision,
- rationale,
- evidence considered,
- next requested action,
- modified request/run profile if needed,
- repair instructions,
- stop summary,
- candidate lessons,
- artifact lineage references.

### 7.10 Loop and runs

The earlier conceptual direction still holds:

- A **run** is execution.
- A **task run** can execute a deterministic flow.
- A **cycle run** can coordinate squad work.
- A **loop policy** decides whether to continue improving toward a goal.
- Design, research, build, QA, and repair runs may have different bounded contexts and deliverable types.
- Verification and continuance logic should use those deliverable types.

### 7.11 Why loop belongs before 2.0

Loop policy should land before capability-backed agents because it creates the execution evidence that 2.0 agents will later use.

Loop policy can generate:

- run outcome classifications,
- verification summaries,
- failure reasons,
- repair decisions,
- artifact lineage,
- acceptance traces,
- candidate lessons,
- evidence ledgers.

Then 2.0 can give agents richer expertise and memory to improve how they participate in loops.

### 7.12 What loop should avoid

The loop SIP should avoid:

- becoming a hidden autonomous agent life loop,
- competing with Duty,
- competing with Cycle,
- becoming a scheduler,
- becoming a background task runner,
- creating unbounded autonomy,
- replacing acceptance criteria,
- making memory automatically durable,
- giving agents new tool authority by implication.

### 7.13 Guiding sentence

> **Loop Policy lets SquadOps improve bounded work across runs using evidence, without turning Cycle into Duty or Duty into autonomy.**

---

## 8. Phase 5: SquadOps 2.0 — Capability-Backed Specialist Agents

### 8.1 Intent

SquadOps 2.0 should introduce the major architectural advancement captured in the Capability Pack Plugin SIP and Skill-Mediated Tool Use amendment.

2.0 answers:

> How do SquadOps agents become reusable, memory-aware, tool-governed specialists with real subject matter expertise?

### 8.2 Core 2.0 platform primitives

2.0 should introduce or complete:

1. Capability Pack Plugins
2. Capability Binding Contracts
3. Agent Capability Bindings
4. Capability-Skill Contracts
5. Skill-Mediated Tool Use
6. Working Set Assembly
7. Squad Artifact Workspaces
8. Scoped Memory
9. Memory Promotion
10. Evidence Ledgers
11. Resource Modules
12. Design Capability Reference Pack
13. Optional Iris/Glyph roster bindings
14. Hybrid adoption for hardwired agents such as Neo

### 8.3 Core principle

> **Agents are identities. Plugins publish capabilities and binding contracts. Rosters bind agents to capabilities. Assignments activate those bindings. Working sets supply context. Capabilities activate skills. Skills operate tools through ports/adapters and produce evidence.**

### 8.4 Why this is a 2.0-level change

This changes the meaning of an agent.

Before:

> role prompt + model + handler

After:

> agent identity + role charter + bound capabilities + scoped memory + tool permissions + working set + artifact responsibilities + evaluation rubric

That is not just another feature. It is the next architecture tier.

### 8.5 Design reference pack

The first reference plugin should be the Design Capability Pack.

It should demonstrate:

- reusable capability pack plugin structure,
- capability binding contracts,
- modular resource modules,
- design-system application,
- design-system stewardship,
- working set assembly,
- workspace artifacts,
- evidence,
- memory candidates,
- Iris/Glyph reference roster bindings.

### 8.6 Iris and Glyph split

Reference roster expression:

| Agent | Responsibility |
|---|---|
| Iris | Applies relevant design systems to requirements; produces UX/design plans, critiques, acceptance criteria, and gap reports |
| Glyph | Stewards and evolves design systems; evaluates gap reports and proposes reusable design-system additions/changes |

Important boundary:

> The Design Capability Plugin does not own Iris or Glyph. It publishes design capabilities. The roster binds Iris and Glyph to those capabilities.

### 8.7 Skill-mediated tool use

2.0 should also clarify the hierarchy:

| Layer | Meaning |
|---|---|
| Tool | Underlying instrument/service/API/app/adapter |
| Skill | Defined, governed use of a specific tool |
| Capability | Domain-level ability that composes skills, resources, memory, templates, rubrics, and judgment |
| Assignment | Runtime activation of agent/capability in context |
| Agent | Durable identity/actor bound to capabilities |

Core rule:

> **Capabilities do not use raw tools directly. Capabilities activate approved skills. Skills operate tools through ports/adapters and produce evidence.**

### 8.8 Why loop policy should already exist by 2.0

Capability-backed agents will be more valuable if there is already a loop policy substrate they can participate in.

Examples:

- Iris improves UX plans across loop iterations.
- Glyph evolves design-system guidance based on repeated gaps.
- Neo uses architecture memory and ADR resources to improve repair decisions.
- Eve feeds verification results into loop policy.
- Max coordinates continuance/escalation decisions.
- Bob executes build/repair skills under capability-specific tool permissions.

Without loop policy, 2.0 agents may become smarter but still lack a mature execution continuance model.

### 8.9 Guiding sentence

> **2.0 should make SquadOps a runtime for composing capable agents from reusable, governed capability packs.**

---

## 9. Roadmap Dependency Map

```text
1.1 Hardening
  ↓
Reliable cycle/run/task/artifact substrate
  ↓
1.2 Runtime presence / embodiment substrate
  ↓
Clear separation of identity, runtime mode, surface presence
  ↓
1.3 Duty durability and roster assignment
  ↓
Persistent responsibility becomes schedulable, recallable, visible
  ↓
Late 1.x Loop Policy
  ↓
Evidence-guided continuance across runs/cycles
  ↓
2.0 Capability-Backed Agents
  ↓
Reusable capability packs, working sets, scoped memory, skill-mediated tools
```

---

## 10. Suggested SIP Packaging

### 10.1 Keep the 2.0 SIP as an umbrella / architecture target

The Capability Pack Plugin SIP is broad. It should probably remain a 2.0 architecture target or umbrella SIP.

It may later split into implementation SIPs:

1. Capability Pack Plugin Substrate
2. Capability Binding Contracts
3. Working Set Assembly
4. Evidence Ledger
5. Squad Artifact Workspace
6. Scoped Memory Promotion
7. Skill-Mediated Tool Use
8. Design Capability Reference Pack
9. Iris/Glyph Optional Roster Bindings
10. Neo Hybrid Capability Adoption

### 10.2 Add a late 1.x Loop Policy SIP before 2.0

The Loop Policy SIP should be more bounded.

It should define:

- loop policy,
- loop state,
- continuance decisions,
- verification inputs,
- stop/repair/retry/fork/escalate outcomes,
- run/cycle relationship,
- evidence output,
- constraints against autonomy,
- relationship to Duty/Cycle/RuntimeActivity/FocusLease.

### 10.3 Keep duty work separate

Duty durability and roster assignment should remain separate from loop policy.

Duty is operational responsibility.

Loop is continuance policy.

Capability pack 2.0 is agent expertise and tool/memory/resource governance.

---

## 11. Concept Boundary Table

| Concept | Release area | Owns | Does not own |
|---|---|---|---|
| RuntimeMode | 1.1/1.2 | Current posture: duty/cycle/ambient | Future assignment, capability, loop policy |
| Assignment | 1.1/1.3 | Commitment/responsibility | Current focus or capability definition |
| Duty | 1.3 | Persistent service responsibility | Iterative continuance policy |
| Cycle | 1.x | Bounded formal work | Long-running duty/autonomy |
| Run | 1.x | Execution attempt | Goal continuance policy |
| Loop Policy | late 1.x | Continue/repair/retry/fork/escalate/stop decisions | Runtime mode, duty assignment, agent identity |
| Capability | 2.0 | Domain-level ability | Agent identity, raw tool authority |
| Skill | 2.0 | Governed use of a tool | Domain-level outcome |
| Tool | 2.0 | Instrument/API/service/adapter | Intent or policy |
| Working Set | 2.0 | Prepared execution context | Durable memory authority |
| Memory | 2.0 | Scoped learned context | Canonical resource authority |
| Artifact Workspace | 2.0 | Shared work state | RuntimeActivity replacement |

---

## 12. Strategic Narrative

The roadmap story is clean:

### 1.1

> Make the machine reliable.

### 1.2

> Make agent presence observable.

### 1.3

> Make operational responsibility durable and schedulable.

### Late 1.x

> Make improvement across runs evidence-guided.

### 2.0

> Make agents capability-backed specialists.

This is a strong architecture progression because each stage creates a platform layer the next stage can rely on.

---

## 13. Recommended Next Moves

### Immediate

Finish 1.1 hardening without pulling in the 2.0 concepts.

### Next

Complete runtime/duty roster assignment and Continuum visibility.

### Then

Draft the late 1.x Loop Policy SIP.

Suggested title:

> **SIP: Loop Policy for Verification-Guided Cycle Continuance**

Core invariant:

> **Loop is a continuance policy around bounded work. It does not replace Cycle, Duty, Run, Task, FocusLease, or RuntimeActivity.**

### Later

Keep the Capability Pack Plugin SIP and Skill-Mediated Tool Use amendment as the 2.0 architecture target.

---

## 14. Final Roadmap Principle

> **Do not give agents more autonomy before the runtime can observe, schedule, verify, and govern them.**

The right order is:

1. harden execution,
2. mature runtime and duty,
3. add loop continuance,
4. then make agents capability-backed, memory-aware, and tool-governed.

This preserves SquadOps' architectural discipline while giving it a clear path toward much more capable specialist agents.
