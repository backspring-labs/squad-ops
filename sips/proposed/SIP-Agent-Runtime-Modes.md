# SIP: Agent Runtime Modes, Duty Windows, and Durable Operational Orchestration

**Status:** Proposed (draft)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 1
**Scope:** SquadOps runtime model evolution
**Related concepts:** Persistent agents, embodied agents, Duty mode, Ambient mode, Cycle execution, virtual world embodiment, Temporal duty orchestration

---

## 1. Summary

This SIP proposes a deliberately small but extensible runtime model for persistent SquadOps agents that may:

- participate in formal **cycle** work,
- hold scheduled or ongoing **duty** responsibilities,
- remain online in low-priority **ambient** presence,
- later support embodied execution surfaces such as Minecraft, Decentraland, or other virtual worlds,
- and eventually support real Backspring operational functions such as support, monitoring, inventory, and research.

The core recommendation is to **avoid exploding SquadOps into a fully generalized "always-on autonomous life simulation"** and instead introduce a compact set of runtime primitives that preserve architectural discipline.

The top-level runtime model should begin with **three mutually exclusive modes**:

- **Duty** — on-duty, service-responsible, availability-constrained operation
- **Cycle** — bounded, formal, assigned work with explicit completion semantics
- **Ambient** — off-duty, low-priority, interruptible background presence

These modes should be treated as the agent's **current operating posture**, while **assignment**, **schedule**, **eligibility**, **focus**, and **activity** remain separate but related concepts.

This separation is critical. It allows an agent to be:

- currently in **Ambient**,
- scheduled to enter **Duty** at 1:00 AM,
- and still eligible for short **Cycle** recruitment until that duty window begins.

That distinction gives SquadOps a clean path toward persistent operations without breaking the existing cycle loop or introducing vague autonomous behavior that cannot be scheduled, recalled, or reasoned about.

---

## 2. Problem Statement

SquadOps is hardening around a cycle-oriented execution model. That is the right foundation. But the broader vision requires agents that are more than one-shot task executors:

- agents may remain online for the life of their container,
- agents may exist within a spatial environment,
- agents may need to remember where they are and what they are doing,
- agents may need to be interruptible and recallable,
- agents may need to hold operational responsibilities during scheduled windows,
- and agents may eventually support business operations that do not cleanly map to a fixed run or workload.

Examples include:

- building a structure in Minecraft as a formal cycle workload,
- exploring Minecraft or remaining socially present in a world during low-priority time,
- serving customer support during a duty window,
- performing inventory watch or nightly research,
- supporting a real operating business where agents cannot be simultaneously "on duty," "free roaming," and "committed to a long build cycle."

If SquadOps responds to this need by simply bolting Mineflayer onto the current agent abstraction, or by allowing a persistent agent to improvise across multiple contexts without explicit runtime discipline, the framework will drift toward hidden state, unclear ownership, poor interruptibility, and unreliable operational semantics.

The challenge is therefore:

> How can SquadOps introduce persistent, embodied, schedule-aware agent behavior without undermining the simplicity and reliability of the current cycle-oriented architecture?

---

## 3. Design Intent

This SIP is intended to achieve the following:

1. **Preserve the cycle model** as the canonical mechanism for bounded, acceptance-oriented work.
2. **Introduce persistent runtime behavior** without forcing all agent activity into cycles.
3. **Support service-like operational responsibility** through a Duty concept with explicit duty windows.
4. **Support embodied or spatial presence** without making virtual-world logic the center of the framework.
5. **Allow interruption, recall, and scheduling** through explicit runtime policy rather than prompt magic.
6. **Create a durable base for future Backspring operational use cases** such as support, monitoring, research, and inventory.
7. **Keep the model small enough to implement safely.**

This SIP is intentionally conservative. It does **not** aim to define a full cognition architecture, social simulation layer, or universal autonomy engine.

---

## 4. Non-Goals

This SIP does **not** propose:

- fully autonomous free-roaming agents with unconstrained self-direction,
- an "always multitasking" agent that can deeply converse, build, and perform duty work simultaneously,
- replacing the current cycle mechanism,
- treating embodiment platforms such as Minecraft as the new source of truth for agent state,
- or using Temporal or any other orchestration engine as the entire agent runtime brain.

This is a runtime discipline proposal, not a general AGI fantasy paper.

---

## 5. Proposed Runtime Model

### 5.1 Top-Level Modes

An agent should have exactly one **current mode** at a time:

- `duty`
- `cycle`
- `ambient`

These are **mutually exclusive top-level modes**.

### 5.2 Why these are modes, not just focus flavors

These three categories are not merely different tasks. They imply different rules for:

- interruptibility,
- accountability,
- scheduling,
- reporting,
- resource use,
- recall policy,
- and what kinds of commitments the agent is allowed to accept.

That makes them operational postures, not just task labels.

### 5.3 The modes in plain English

#### Duty

**Duty** means the agent is **on duty**.

It is responsible for a role or function that requires availability, responsiveness, and policy-governed behavior.

Examples:

- customer support
- inventory watch
- nightly research
- monitoring/moderation
- event-driven operational observation

Duty implies the agent cannot casually wander off into a virtual world or commit to a long blocking cycle task if that would undermine the duty obligation.

#### Cycle

**Cycle** means the agent is committed to **bounded assigned work**.

Examples:

- building a web app,
- executing an experiment,
- producing an artifact,
- performing a validation pass,
- or building a defined structure in Minecraft as part of a formal workload.

Cycle work should continue to be the most structured and acceptance-oriented form of execution in SquadOps.

#### Ambient

**Ambient** means the agent is online, present, lightly available, and **off duty**.

Examples:

- exploring Minecraft,
- remaining in a home base,
- patrolling a small area,
- performing light observation,
- casual low-resource social presence,
- idling with purpose.

Ambient is not "do whatever forever." It is simply the low-priority, interruptible background state for agents that are online but not currently assigned to serious work.

---

## 6. Orthogonal Concepts: Mode vs Assignment vs Schedule vs Focus vs Activity

One of the most important architectural distinctions in this proposal is that **mode is not the same thing as assignment or schedule**.

### 6.1 Current mode

Current mode answers:

> What is the agent doing right now?

Examples:

- ambient
- cycle
- duty

### 6.2 Assignment

Assignment answers:

> What role or commitment has been associated with the agent?

Examples:

- assigned to nightly research
- assigned to support duty
- eligible for cycle recruitment
- reserved for monitoring window

An agent can be assigned to a duty without currently being in Duty mode.

### 6.3 Schedule / duty window

Schedule answers:

> When is that assignment active or claimable?

Examples:

- support duty active 9 AM–5 PM
- nightly research active 1 AM–6 AM
- reserve window begins at 10 PM

### 6.4 Focus

Focus answers:

> What currently owns the agent's primary attention within its current mode?

Examples:

- duty focus: queue watch
- duty focus: handling support case #184
- cycle focus: implementation task A7
- ambient focus: explore nearby biome

### 6.5 Activity

Activity answers:

> What concrete action is happening right now?

Examples:

- move_to(x,y,z)
- summarize_findings
- classify_ticket
- place_block
- answer_status_ping

### 6.6 Why this distinction matters

This gives SquadOps the ability to model a clean and realistic case such as:

- current mode = `ambient`
- duty assignment = `nightly_research`
- duty window starts at `01:00`
- cycle eligible = `true until reserve threshold`

That means the agent can be ambient now, recruited into a short cycle task if safe, and later transition into Duty mode automatically when the window opens.

That is operationally coherent and significantly safer than treating "free" and "committed" as vague prompt-level concepts.

---

## 7. Core Runtime Primitives

The following primitives are the minimum recommended scaffolding.

### 7.1 Agent Runtime State

A persistent agent should expose runtime state such as:

- `agent_id`
- `mode`
- `focus`
- `activity_id`
- `runtime_status`
- `interruptibility`
- `last_heartbeat_at`
- `current_assignment_ref`
- `resource_budget_ref`
- `location_ref`

### 7.2 Assignment

An assignment represents a durable relationship between an agent and a future or potential responsibility.

Examples:

- support duty assignment
- nightly research assignment
- cycle eligibility window
- reserve window

Suggested fields:

- `assignment_id`
- `assignment_type`
- `assigned_role`
- `active_window`
- `strictness`
- `priority`
- `recall_policy`
- `allowed_off_window_modes`

### 7.3 Duty Window

Duty windows should be explicit. A duty is not a permanent identity lock.

Suggested fields:

- `window_start`
- `window_end`
- `timezone`
- `strictness: hard | soft`
- `grace_before_start`
- `grace_after_end`

#### Hard duty window

During the window, the agent is reserved for duty only.

#### Soft duty window

During the window, duty has priority, but short, preemptible work may be allowed if the duty can reclaim focus.

### 7.4 Focus Lease

A focus lease is the runtime claim over an agent's primary attention.

This is a conceptual and implementation pattern, not necessarily a direct copy of Kubernetes Lease objects. But the analogy is useful: leases exist to coordinate ownership and availability in distributed systems.

Suggested fields:

- `lease_id`
- `owner_type` (`duty`, `cycle`, `ambient`)
- `owner_ref`
- `acquired_at`
- `expires_at` or `renewal_policy`
- `interruptibility`
- `recall_policy`

### 7.5 Activity

Activities represent the concrete unit of work currently being performed.

Suggested fields:

- `activity_id`
- `activity_type`
- `mode`
- `goal`
- `priority`
- `requires_embodiment`
- `can_pause`
- `can_resume`
- `can_abort`
- `completion_conditions`
- `evidence_requirements`

### 7.6 Embodiment

An agent identity should be separated from its embodiment.

The agent is the durable actor. The embodiment is the runtime surface through which it acts in a world or system.

Examples of embodiments:

- Mineflayer avatar in Minecraft
- Decentraland/Sandbox avatar
- Discord presence
- CLI session
- browser automation context

Suggested fields:

- `embodiment_id`
- `embodiment_type`
- `platform`
- `attachment_state`
- `health`
- `capability_set`
- `location_ref`

### 7.7 Location

Location should be generic at the core.

Suggested fields:

- `location_type`
- `location_system`
- `location_ref`
- `updated_at`

The core only needs to know that location exists and matters. World-specific detail can stay in adapters.

### 7.8 Resource Budget

The goal is not to simulate a human body. The goal is to prevent irresponsible scheduling.

Suggested coarse-grained budget dimensions:

- attention budget
- compute/token budget
- action budget
- concurrency allowance
- uptime / fatigue threshold

The first release can keep this extremely simple.

---

## 8. Direct Interaction Is Not a Top-Level Mode

A useful simplification from the discussion is that **direct human interaction should not be modeled as a separate peer mode**.

Instead, direct interaction should be treated as a **cross-cutting interaction path** that may occur against an agent already in one of the three top-level modes.

That means:

- in **Ambient**, direct interaction usually interrupts easily,
- in **Duty**, direct interaction may be limited, deferred, or handled minimally,
- in **Cycle**, direct interaction may return status or require priority escalation.

This keeps the mode model small while still preserving the reality that humans may speak to agents in any mode.

---

## 9. Cycle Participation with Non-Code Execution Surfaces

A key insight from the discussion is that a cycle does **not** need to mean only software-building work.

A cycle can target any execution surface, including:

- code repositories,
- documents,
- data systems,
- and virtual worlds such as Minecraft.

The clean framing is:

> The cycle does not "happen inside Minecraft."
> The cycle orchestrates tasks whose execution surface is Minecraft.

This means SquadOps can support a cycle workload such as:

- build a shelter near spawn,
- gather wood,
- craft planks,
- place torches,
- verify a structure footprint,
- and produce evidence of completion.

The existing cycle philosophy remains intact if Minecraft world actions are represented as:

- task work,
- observable state changes,
- acceptance-checked outcomes,
- and run artifacts.

That is an important extension point for future embodied execution.

---

## 10. Ambient as a First-Class Low-Priority Runtime Posture

Ambient should remain intentionally narrow.

It exists so that a persistent agent can be:

- online,
- embodied,
- recallable,
- lightly interactive,
- and not currently holding a serious obligation.

Ambient should be:

- highly interruptible,
- low-resource,
- bounded by policy,
- and explicitly lower priority than Duty and Cycle.

Ambient is not a loophole for uncontrolled autonomous drift.

Recommended constraints:

- bounded exploration radius,
- bounded budget,
- bounded allowed actions,
- immediate recall support,
- and no long blocking commitments.

---

## 11. Duty as Scheduled Operational Responsibility

Duty is the most important new concept in this proposal.

### 11.1 Why Duty matters

Many future Backspring uses are not well expressed as a fixed cycle:

- customer support
- inventory watch
- nightly research
- moderation / queue watch
- event-driven monitoring

These are better modeled as **operational responsibilities** that may run during windows, wait on events, and require recallable focus.

### 11.2 Duty is not permanent lock-in

A duty should be understood as:

- an assignment,
- with a schedule or active window,
- that may claim the agent into Duty mode during that window,
- and release the agent back to Ambient or Cycle outside that window.

This is a critical design refinement. It allows the framework to support realistic staffing-like behavior without freezing agents into static identities.

### 11.3 Duty strictness

Recommended first-cut policy:

- **hard duty** — during the window, no cycle participation, no ambient exploration beyond minimal local idle behavior
- **soft duty** — during the window, duty has priority, but preemptible short work may be allowed if duty can reclaim the agent

### 11.4 Duty and "off duty"

The "off duty" framing is operationally correct and should be preserved in the conceptual model:

- if an agent is in Duty mode, it is **on duty**,
- if an agent is in Ambient or Cycle, it is effectively **off duty** for that period,
- but assignments and schedules may still already exist in the background.

That is intuitive and useful.

---

## 12. Temporal as the Best Initial Seam for Duty Mode

This discussion surfaced a particularly strong architectural seam:

> Temporal should be considered primarily for **Duty orchestration**, not as the agent's full runtime brain.

### 12.1 Why Temporal fits Duty

Temporal workflows are durable and support long waits, retries, schedules, and signal-driven interaction. Workflows can run for extended periods, receive messages, and resume after failures. This is especially well-aligned to service-like operational duties that must wait on timers or events rather than constantly execute hot loops. See Temporal Workflow and Workflow Execution documentation, especially the discussion of durable execution, signals/queries/updates, and schedules:

- https://docs.temporal.io/workflows
- https://docs.temporal.io/workflow-execution
- https://docs.temporal.io/encyclopedia/workflow-message-passing

That makes Temporal a strong fit for:

- duty windows,
- durable waiting,
- event wake-ups,
- recall and preemption signals,
- periodic operational duty ticks,
- and resumable long-lived duty flows.

### 12.2 Why Temporal should not own the whole agent runtime

Temporal also records event history and expects deterministic workflow behavior. A single workflow execution has practical limits on throughput and size, even though the platform scales to huge numbers of executions overall. That makes it a poor first choice for:

- every tiny Minecraft movement,
- continuous embodiment telemetry,
- an immortal all-purpose "agent life workflow,"
- or free-form cognition loops.

### 12.3 Recommended boundary

The clean boundary is:

- **SquadOps owns agent semantics**: identity, current mode, focus rules, policy, activity model, embodiment model.
- **Temporal optionally owns duty durability**: windows, timers, durable waiting, wake-on-event logic, retry semantics, recall signals, and long-lived duty flows.

That boundary keeps Temporal where it is strongest and keeps SquadOps in control of the agent runtime model.

---

## 13. Industry and Standards Alignment

This proposal does not need to copy any external standard exactly, but it should align with a few proven ideas.

### 13.1 BPMN for bounded, explicit workflow semantics

BPMN 2.0.2 remains one of the most durable standards for modeling bounded workflows, process events, tasks, and execution-oriented process structures. It is relevant here not because SquadOps should become BPMN, but because BPMN reinforces the idea that formal work should have:

- explicit start and end conditions,
- defined tasks,
- event handling,
- structured control flow,
- and execution semantics.

That maps well to **Cycle** and parts of **Duty** orchestration.

Reference:

- OMG BPMN 2.0.2 specification: https://www.omg.org/spec/BPMN/2.0.2/PDF

### 13.2 State-machine semantics for mutually exclusive operating postures

The proposal to treat `duty | cycle | ambient` as mutually exclusive top-level modes is strongly consistent with the general state-machine approach used in UML state machines and W3C SCXML. These standards distinguish current state from transitions, events, and nested execution concerns.

This supports the notion that:

- current mode should be singular,
- transitions should be explicit,
- and nested detail should live under the current mode rather than creating endless peer categories.

References:

- W3C SCXML Recommendation: https://www.w3.org/TR/scxml/
- OMG UML overview: https://www.omg.org/spec/UML/2.5.1/About-UML

### 13.3 Prefect for bounded flow/task state and orchestration history

Prefect's model of flows, tasks, and explicit state histories reinforces the value of:

- bounded runs,
- tracked execution state,
- retries, schedules, and timeouts,
- and distinguishing the state lifecycle of a run from the business meaning of the work.

This aligns strongly with the continuing role of **Cycle** in SquadOps.

References:

- Prefect flows: https://docs.prefect.io/v3/concepts/flows
- Prefect states: https://docs.prefect.io/v3/concepts/states

### 13.4 Kubernetes Lease pattern for coordination and ownership claims

Kubernetes Lease objects provide a widely used example of how distributed systems represent:

- shared resource coordination,
- leader election,
- heartbeats,
- and lightweight ownership/availability tracking.

This does **not** mean SquadOps should literally use Kubernetes Lease objects for focus. But it is a strong precedent for introducing a **focus lease / ownership claim** concept rather than allowing multiple ambiguous owners to contend for the same agent attention.

Reference:

- Kubernetes Leases: https://kubernetes.io/docs/concepts/architecture/leases/

### 13.5 Temporal for durable, event-driven, long-running operational flows

Temporal's workflow model reinforces the idea that some responsibilities are better represented as durable, event-aware, long-lived orchestrations that can survive failures and react to timers and signals.

That aligns most naturally to **Duty mode**, especially scheduled or event-driven duties.

References:

- Temporal Workflows: https://docs.temporal.io/workflows
- Workflow Execution: https://docs.temporal.io/workflow-execution
- Signals / Queries / Updates: https://docs.temporal.io/encyclopedia/workflow-message-passing

---

## 14. Recommended Architectural Principles

### 14.1 Keep top-level runtime postures small

Do not create a large taxonomy of near-overlapping modes.

Start with:

- Duty
- Cycle
- Ambient

### 14.2 Keep current mode singular

An agent should not be "kind of duty and kind of cycle and a little ambient."

Current posture must be singular for the runtime to be understandable.

### 14.3 Keep assignments and schedules orthogonal

An agent may have future commitments while still being Ambient now.

### 14.4 Treat direct interaction as a cross-cutting path

Do not make "direct" a peer mode.

### 14.5 Do not embed world semantics into core too early

Core should know that embodiment and location exist, not every detail of every world.

### 14.6 Keep Cycle canonical for bounded work

Even Minecraft build tasks should still respect the cycle philosophy:

- defined goal,
- bounded workload,
- acceptance criteria,
- evidence,
- wrap-up.

### 14.7 Use Duty for service-like persistence

Do not stretch Cycle until it becomes a poor imitation of long-running operations.

### 14.8 Prefer explicit recalls over implicit interruption

A higher-priority claim should produce an explicit mode transition or focus transition, not mysterious prompt drift.

---

## 15. Proposed Data Model Sketch

```yaml
AgentRuntimeState:
  agent_id: string
  mode: duty | cycle | ambient
  runtime_status: online | idle | busy | paused | degraded | recovering | offline
  focus: string
  activity_id: string | null
  interruptibility: none | low | medium | high
  last_heartbeat_at: timestamp
  embodiment_id: string | null
  location_ref: string | null
  resource_budget_ref: string | null

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
  requires_embodiment: boolean
  can_pause: boolean
  can_resume: boolean
  can_abort: boolean
  completion_conditions: []
  evidence_requirements: []

Embodiment:
  embodiment_id: string
  embodiment_type: minecraft | discord | browser | cli | other
  platform: string
  attachment_state: unattached | attaching | attached | desynced | reconnecting | detached
  health: healthy | degraded | failed
  location_ref: string | null
```

This is intentionally not final schema. It is simply sufficient to prove the architecture.

---

## 16. Transition Semantics

A minimal transition model should include at least:

- `ambient -> cycle`
- `ambient -> duty`
- `cycle -> ambient`
- `cycle -> duty` (only if policy permits preemption or explicit interruption)
- `duty -> ambient`
- `duty -> cycle` (generally only after duty window ends or if policy explicitly allows it)

Additional conditions:

- mode transitions should be evented and auditable,
- transitions should carry reason codes,
- higher-priority transitions should not silently discard current activity state,
- and interruptions should either pause, abort, or checkpoint the current activity explicitly.

---

## 17. Implementation Path

### Phase 0 — Document and agree on the runtime taxonomy

Deliverables:

- SIP approval
- vocabulary freeze for `mode`, `assignment`, `window`, `focus`, `activity`, `embodiment`
- no code changes yet

### Phase 1 — Add minimal runtime state to agents

Implement:

- current mode
- runtime status
- heartbeat
- focus field
- current activity id

Acceptance:

- an operator can see an agent's current mode and current activity
- runtime does not require embodiment support yet

### Phase 2 — Add assignments and duty windows

Implement:

- assignment model
- duty window model
- hard vs soft duty flag
- transition scheduler hooks

Acceptance:

- an agent can be Ambient now but scheduled to enter Duty later
- an upcoming duty window can restrict cycle recruitment according to policy

### Phase 3 — Add focus lease / ownership claim

Implement:

- explicit primary owner of agent attention
- lease acquisition / release / renew semantics
- reasoned rejection when a conflicting owner attempts to claim focus

Acceptance:

- the framework can explain why an agent did or did not accept a cycle request
- duty, cycle, and ambient cannot all claim the same agent simultaneously

### Phase 4 — Add activity model

Implement:

- current activity object
- pause/resume/abort semantics
- evidence requirement hooks

Acceptance:

- current work is observable as an activity, not hidden in prompt history

### Phase 5 — Add embodiment abstraction

Implement:

- embodiment attachment state
- embodiment health
- location reference

Acceptance:

- the framework can represent a Mineflayer-backed embodiment without making Minecraft core knowledge part of the domain

### Phase 6 — Add one minimal embodied proof point

Recommended proof point:

- Minecraft embodiment that can:
  - connect,
  - move to a location,
  - report position,
  - gather a small material target,
  - place a simple marker structure.

Acceptance:

- a cycle can target Minecraft as an execution surface with acceptance checks
- ambient exploration can be interrupted and recalled

### Phase 7 — Add optional Duty durability using Temporal

Recommended proof point:

- one `nightly_research` duty
- one duty window
- one timer-based wake-up
- one event-based wake-up
- one recall signal
- one handoff back into SquadOps activity execution

Acceptance:

- the duty survives worker interruption,
- duty window transitions occur reliably,
- recall behavior is explicit,
- and SquadOps remains semantic owner of mode and activity.

---

## 18. Acceptance Criteria

This SIP should only be considered successful if the following become true.

### 18.1 Runtime clarity

- The framework can always answer:
  - what mode is the agent in now?
  - what assignment(s) does it have?
  - what is its current activity?
  - what may claim it next?

### 18.2 Exclusivity

- An agent cannot be simultaneously in Duty, Cycle, and Ambient.
- Current mode is singular and explicit.

### 18.3 Scheduling sanity

- An agent can be Ambient now and scheduled for future Duty.
- Cycle recruitment respects future duty windows and reservation policy.

### 18.4 Recallability

- Ambient behavior can be recalled.
- Duty transitions can preempt Ambient.
- Policy governs whether Cycle can preempt or interrupt Duty.

### 18.5 Cycle preservation

- Existing cycle architecture remains intact.
- Non-code execution surfaces such as Minecraft can participate without changing the fundamental cycle semantics.

### 18.6 Duty realism

- Duty supports explicit windows.
- Hard and soft duty behavior are representable.
- Duty can model service-like operational work without pretending it is just a cycle.

### 18.7 Embodiment safety

- Embodied activity is represented through adapters and activities, not hidden inside agent prompt context.
- Location and embodiment health are observable.

### 18.8 Incremental rollout

- The first implementation can stop after mode + assignment + focus + activity and still be useful.
- Embodiment and Temporal are optional later layers, not prerequisites for the entire model.

---

## 19. Risks and Failure Modes

### 19.1 Too many top-level modes

Risk:
The runtime becomes a taxonomy soup.

Mitigation:
Stay with three top-level modes for now.

### 19.2 Making direct interaction a peer mode

Risk:
The mode model gets muddy and repetitive.

Mitigation:
Treat direct interaction as cross-cutting.

### 19.3 Treating Duty as permanent identity lock

Risk:
Agents become unusably rigid.

Mitigation:
Use assignment + duty window + current mode.

### 19.4 Treating Ambient as unrestricted autonomy

Risk:
Framework loses control and predictability.

Mitigation:
Keep ambient bounded, low-priority, and recallable.

### 19.5 Letting Minecraft or embodiment drive the domain model

Risk:
Core becomes contaminated by adapter-specific concerns.

Mitigation:
Separate identity from embodiment and keep location generic.

### 19.6 Overusing Temporal

Risk:
A second orchestration system swallows the runtime.

Mitigation:
Use Temporal narrowly for Duty durability first.

### 19.7 Hidden attention contention

Risk:
Agent "kind of" accepts multiple serious responsibilities at once.

Mitigation:
Introduce explicit focus ownership / lease semantics.

---

## 20. Open Questions

1. Should `hard | soft` duty strictness be enough for v1, or is a richer policy model needed later?
2. Should cycle recruitment be blocked by a configurable pre-duty reserve buffer?
3. Does Ambient need geographic bounds from day one for embodied agents?
4. Should a duty window transition be implemented inside SquadOps first, or only once Temporal is introduced?
5. What evidence model is required for world-state acceptance checks in Minecraft workloads?
6. Does the current agent factory need new runtime traits to support persistent mode/state fields?
7. How should budget exhaustion change mode eligibility or cause forced transitions?

---

## 21. Recommendation

Proceed with this SIP in a staged way.

Do **not** begin by building a rich virtual-world agent.
Do **not** begin by making Temporal the whole system.
Do **not** begin by exploding the taxonomy.

Instead:

1. freeze the three top-level modes,
2. separate current mode from assignments and schedules,
3. add focus and activity visibility,
4. add duty windows,
5. preserve cycles as the bounded-work canonical path,
6. then add one embodied proof point,
7. then add one narrow Temporal duty proof point.

That path gives SquadOps a disciplined runway toward persistent operational agents, embodied worlds, and future Backspring business support without wrecking the current framework with a half-baked runtime model.

---

## 22. Proposed Working Definitions

For ease of future reference:

### Mode
The agent's current operating posture.
Exactly one of: `duty | cycle | ambient`.

### Duty
On-duty, service-responsible mode with availability expectations.

### Cycle
Bounded, formal assigned work with explicit completion semantics.

### Ambient
Off-duty, low-priority, interruptible background presence.

### Assignment
A scheduled or durable commitment associated with the agent.

### Duty Window
The time range during which a duty assignment may or must claim the agent.

### Focus
The current primary concern owning the agent's attention inside its mode.

### Activity
The concrete action or unit of work currently being executed.

### Embodiment
A runtime surface through which the agent acts in a world or system.

### Recall
A policy-driven interruption or reassignment request that changes or reclaims the agent's current focus or mode.

---

## 23. Closing View

The most important idea in this document is not Minecraft, not Temporal, and not even Duty itself.

It is this:

> **Current posture, future commitments, and immediate action must be modeled separately.**

In other words:

- **mode** is what the agent is doing now,
- **assignment/schedule** is what may claim it later,
- **focus/activity** is what currently owns its attention.

That separation is what gives SquadOps a credible path to persistent, embodied, operational agents without collapsing the framework into ambiguity.
