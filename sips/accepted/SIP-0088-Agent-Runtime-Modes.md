---
title: Agent Runtime Modes
status: accepted
author: Jason Ladd
created_at: '2026-04-25T00:00:00Z'
sip_number: 88
updated_at: '2026-04-25T17:57:04.777541Z'
---
# SIP-0088: Agent Runtime Modes — Vision and Index

**Status:** Accepted (umbrella / vision)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 3 (incorporated review feedback on 2026-04-25; r2 split umbrella into three implementing SIPs)
**Original full proposal:** commit `76a1f90` on main

---

## Purpose of this document

This document is the **umbrella vision** for evolving SquadOps from a cycle-only execution framework into a runtime that supports persistent runtime state, scheduled operational responsibilities, and (eventually) embodied presence.

It does **not** propose implementation. The actionable proposals live in three sibling SIPs, each independently reviewable and shippable.

The original revision-1 draft was a single 1,100-line proposal. After design discussion it was split into three smaller SIPs so each scope (runtime taxonomy, embodiment, Temporal) can be reviewed and accepted independently. The original full content is preserved in git history at commit `76a1f90`.

---

## What this package introduces — and what it does not

This package introduces **persistent runtime state for agents** — the ability to observe, schedule, recall, and reason about an agent across cycles and duty windows.

It does **not** introduce always-on autonomous entities, unbounded "agent life" loops, or general-purpose self-direction. Persistence here means *durable state and explicit lifecycle*, not *uncapped autonomy*.

---

## The central insight

> **Current posture, future commitments, and immediate action must be modeled separately.**

- **RuntimeMode** is what the agent is doing now — exactly one of `duty | cycle | ambient`.
- **Assignment / schedule** is what may claim the agent later.
- **FocusLease / RuntimeActivity** is what currently owns its attention.

Without this separation, persistent agents become unobservable — schedules live in prompts, recall happens by vibes, and "free" vs. "committed" become guesses. With it, SquadOps gains a credible path to operational agents (Backspring support, monitoring, research) and embodied surfaces (Discord, browser, eventually Minecraft) without diluting the cycle model.

---

## Package-level invariant

The following invariant governs all three implementing SIPs:

> **RuntimeMode, Assignment, FocusLease, RuntimeActivity, Embodiment, and DutyDurability must remain separate concepts. No implementation may use one of these primitives as a hidden substitute for another.**

Concrete consequences:

- A duty assignment does not mean the agent is currently in Duty mode.
- A focus lease does not imply a specific embodiment.
- An embodiment attachment does not imply permission to act.
- A Temporal workflow does not own agent state.
- A RuntimeActivity does not define the top-level runtime mode.
- A RuntimeActivity does not replace cycle, task, workload, or handler execution.

---

## Conceptual boundary table

This table is canonical for the package. Every implementing SIP must respect it.

| Primitive | Owns | Does NOT own |
|-----------|------|--------------|
| **RuntimeMode** | Current top-level posture (duty/cycle/ambient) | Future commitments, external presence, work execution |
| **Assignment** | Future or potential responsibility | Current attention, current mode |
| **DutyWindow** | When duty may claim the agent | Work execution, focus arbitration |
| **FocusLease** | Primary attention ownership | Agent identity, schedule, embodiment lifecycle |
| **RuntimeActivity** | Observable record of current work | Execution engine semantics; replacement of cycle/task/workload/handler |
| **Embodiment** | External surface attachment, capabilities, location, health | Intent, priority, mode, scheduling decisions |
| **EmbodimentAdapter** | Translating *authorized* surface-specific action requests into platform calls | Goal decomposition, intent decisions, mode transitions |
| **DutyDurabilityPort** | Durable duty wake/recall mechanics | Agent semantics, runtime state |
| **Temporal adapter** | Timers, schedules, durable signals | Runtime state, cognition, embodiment, transition authority |

---

## The three top-level modes

| Mode | Meaning | Examples |
|------|---------|----------|
| **Duty** | On-duty, service-responsible, availability-constrained | Customer support, inventory watch, nightly research |
| **Cycle** | Bounded, formal, assigned work with explicit completion semantics | Build a feature, run an experiment, validate an artifact |
| **Ambient** | Off-duty, low-priority, interruptible background presence | Idling, lightweight observation, recallable presence |

These are mutually exclusive. An agent has exactly one mode at a time. **Direct human interaction is not a mode** — it is a cross-cutting interaction path that can occur in any mode (see policy table below).

---

## Direct interaction policy by mode

| Current mode | Default direct-interaction behavior |
|--------------|--------------------------------------|
| Ambient | May interrupt directly if budget permits |
| Duty | Answer, defer, or route per duty policy; should not silently abandon duty obligation |
| Cycle | Status-only by default; deeper engagement requires escalation |
| Offline / Degraded | Return last known state or "unavailable"; never fabricate |

This keeps "chat with the agent" from becoming a hidden fourth mode.

---

## What must not happen

Reviewer-driven guardrails. Implementations of the three follow-ons must not violate any of these:

- Cycle must not become a long-running service loop.
- Duty must not become a generic background task runner.
- Ambient must not become unsupervised autonomy. In particular, ambient must not perform irreversible external actions, spend material compute, or mutate external systems unless a focus lease is granted and a RuntimeActivity is started.
- Embodiment must not become a second agent identity.
- Temporal must not become the runtime brain.
- Minecraft, Discord, or any other surface concept must not appear in core.
- Direct human interaction must not become a fourth top-level mode.
- A RuntimeActivity must not replace cycle, task, workload, or handler execution semantics.

---

## Canonical terminology

Use these names in code, schemas, and design discussion. "Activity" is permitted as prose shorthand for RuntimeActivity but should never appear unqualified in schemas (collision with Temporal's `Activity`).

| Canonical name | Notes |
|----------------|-------|
| `RuntimeMode` | The enum: `duty`, `cycle`, `ambient` |
| `Assignment` | Durable commitment record |
| `DutyWindow` | Time range during which a duty may claim the agent |
| `FocusLease` | Attention ownership claim |
| `RuntimeActivity` | Observable current work record (NOT Temporal Activity) |
| `Embodiment` | External surface attachment record |
| `EmbodimentAdapter` | Adapter implementing surface-specific port |
| `DutyDurabilityPort` | Port for durable duty timer/signal mechanics |
| `DutyDurabilityRun` | Runtime correlation record between Assignment and external durability backend |

---

## The three implementing SIPs

### 1. `SIP-0089-Agent-Runtime-State.md` — v1.1 candidate

**Scope:** RuntimeMode, Assignment, DutyWindow, FocusLease, RuntimeActivity. Pure runtime-state primitives. No embodiment, no Temporal.

**Why first:** Everything else depends on these primitives. Once an agent has `mode`, `focus`, `current_runtime_activity`, `assignments`, and `focus_lease`, it is observable and schedulable. Embodiment and durable workflows attach to these primitives later.

### 2. `SIP-0090-Agent-Embodiment-Substrate.md` — v1.2 candidate

**Scope:** Embodiment abstraction (identity / runtime-surface separation), generic location, capability-aware RuntimeActivity scheduling, resource budgets, first proof point on Discord.

**Why second:** Once persistent agents exist, the next architectural question is "how do they act in external surfaces?" Discord is chosen as the first proof point because it is lighter to test than Minecraft. Minecraft becomes a future follow-on SIP (`SIP-Minecraft-Embodiment-Adapter.md`, not in this package).

### 3. `SIP-0091-Duty-Durability-via-Temporal.md` — v1.3 candidate

**Scope:** Temporal as a narrowly-scoped durability layer for Duty workflows only. Optional dependency. Proof point: a `nightly_research` duty surviving worker restarts.

**Why third:** Duty windows can be served by an in-process scheduler in v1.1. Temporal becomes valuable when production-grade durability matters — and the right time to add a second orchestrator is after the duty model has shape.

---

## Why three SIPs instead of one

The original umbrella proposal was good design but bad packaging. Reviewing it required signing off on:

- A new runtime taxonomy
- An embodiment abstraction
- A new optional orchestrator (Temporal)
- A virtual-world execution surface (Minecraft)

…all at once. Splitting bounds the blast radius:

- The runtime taxonomy can be approved without committing to Temporal.
- The embodiment substrate can be approved without committing to Minecraft.
- The Temporal adapter can be approved without rewriting agent semantics.
- If the embodiment substrate doesn't pan out, v1.1 still ships and is useful.

---

## Sequencing rules

- **v1.1 must land before v1.2 or v1.3.** Both follow-ons depend on the runtime-state primitives.
- **v1.2 and v1.3 are independent.** They can be reviewed and shipped in either order, or in parallel.
- **No version bump is implied by accepting these SIPs.** Acceptance is a design commitment. The actual `pyproject.toml` bump to 1.1 happens when the v1.1 implementation is feature-complete.
- **In-flight 1.0.x cycle hardening continues unaffected.** Nothing in these SIPs touches the cycle execution path until implementation lands behind feature flags.

---

## Architectural principles

These principles govern all three implementing SIPs:

1. **Keep top-level runtime postures small.** Three modes. Resist additions.
2. **Keep current mode singular.** No "kind of duty and kind of cycle."
3. **Keep assignments and schedules orthogonal to current mode.** Future commitments are not the same as current state.
4. **Treat direct interaction as cross-cutting.** Not a peer mode.
5. **Do not embed world semantics into core too early.** Core knows embodiment and location exist; adapters know the rest.
6. **Keep Cycle canonical for bounded work.** Even Minecraft builds respect cycle semantics.
7. **Use Duty for service-like persistence.** Don't stretch Cycle into a poor imitation of long-running operations.
8. **Prefer explicit recalls over implicit interruption.** Higher-priority claims produce explicit transitions, not prompt drift.
9. **FocusLease is the hard gate for attention.** No attention-owning RuntimeActivity may begin without a compatible lease.
10. **Embodiment never decides intent.** Adapters execute authorized actions; they do not interpret goals.
11. **Temporal makes time durable, not state.** Runtime state always lives in SquadOps.

---

## Package-level acceptance criteria

The package as a whole is successful when:

1. **RuntimeMode** remains singular and limited to `duty`, `cycle`, or `ambient`.
2. **Assignments** may be multiple; current mode may only be one.
3. **FocusLease** is required for primary attention ownership.
4. **RuntimeActivity** records current work but does not replace cycle, task, or workload semantics.
5. **Embodiment** exposes capabilities and health but does not own agent intent.
6. **Temporal** makes duty timing durable but does not own agent state or perform transitions directly.
7. **Direct human interaction** remains cross-cutting and never becomes a fourth mode.
8. All mode, focus, activity, and embodiment transitions emit **reason-coded events** (see canonical reason codes below).
9. Existing cycle execution remains unchanged unless explicitly gated by recruitment/focus policy.
10. Minecraft remains a follow-on adapter SIP, not part of core runtime state or the v1.2 embodiment substrate.

---

## Canonical reason codes

All three SIPs share these reason codes for events and rejection responses. Implementations may extend the set; they must not redefine these.

| Code | Meaning |
|------|---------|
| `duty_window_opened` | Duty window has begun; mode transition requested |
| `duty_window_closed` | Duty window has ended; release transition requested |
| `cycle_recruitment_accepted` | Agent agreed to join a cycle |
| `cycle_recruitment_rejected_upcoming_duty` | Cycle declined because a hard duty window is within the reserve buffer |
| `cycle_recruitment_rejected_focus_lease_conflict` | Cycle declined because focus lease cannot be acquired |
| `focus_lease_granted` | Lease acquired |
| `focus_lease_rejected` | Lease denied (carries owner ref + retry-after) |
| `focus_lease_queued` | Lease request queued behind current owner |
| `focus_lease_preempting` | Higher-priority owner displacing current owner |
| `recall_requested` | Higher-priority claim wants the agent's attention |
| `budget_exhausted` | A resource budget hit its ceiling |
| `embodiment_desynced` | External surface state diverged from local view |
| `operator_override` | Manual intervention forced a transition or decision |

---

## Canonical event names

All three SIPs share these event names. Implementations may extend; they must not redefine.

- `agent.mode.transition.requested` / `.completed` / `.rejected`
- `focus_lease.requested` / `.granted` / `.rejected` / `.queued` / `.preempted` / `.released`
- `runtime_activity.started` / `.paused` / `.resumed` / `.completed` / `.aborted`
- `assignment.window.opened` / `.closed`
- `embodiment.attach.requested` / `.attached` / `.desynced` / `.reconnecting` / `.detached`
- `duty_durability.window.scheduled` / `.signal.received` / `.workflow.failed`

---

## What this umbrella does NOT contain

The full architectural argument, data model sketches, transition tables, risk register, and open-questions list from the original proposal are **not** duplicated here. They have been distributed into the three implementing SIPs where they are actionable, and the original full text is preserved in git at commit `76a1f90`.

This document exists only to:

- Frame the central insight
- Establish the package invariant and conceptual boundary table
- Index the three implementing SIPs
- Document the sequencing and rationale for the split
- Preserve the architectural principles, terminology, reason codes, and event names that govern all three

For implementation detail, read the implementing SIPs.

---

## Future Considerations

This section captures known unresolved design questions that fall outside the scope of SIP-0089 / SIP-0090 / SIP-0091 but will need answers as real operational use cases arrive. They are documented here so the questions are not lost and so the implementing SIPs can be evaluated against them when concrete workloads expose the trade-offs.

### Composition of Duty work and Cycle work

The package commits to mutually exclusive top-level modes (Duty, Cycle, Ambient) and to FocusLease as the single attention owner. This handles the case of "an unrelated cycle wants this duty agent" cleanly: hard duty rejects, soft duty allows preemption with a graceful window.

It does **not** elegantly handle a case that real operational duty work is likely to surface:

> **Duty work that itself requires a coordinated squad cycle to make progress.**

Examples:

- **Customer support duty.** The on-duty Lead receives a ticket that needs Dev + QA triage to resolve. The duty work is *to handle the ticket*, but resolving the ticket requires squad coordination — exactly what cycles exist for.
- **Nightly research duty.** The on-duty Strat agent is producing a research synthesis. The synthesis genuinely needs Data's analysis to be complete. Strat is not "interrupted" by Data — the duty work *requires* collaboration with Data.
- **Inventory anomaly duty.** The on-duty Data agent detects an anomaly. Investigating it requires Lead + Strat to assess implications and decide on remediation.
- **Build pipeline watch duty.** The on-duty agent observes a CI failure overnight. Diagnosis and repair may need Dev + QA cooperation.

In all four cases the duty agent isn't *competing* with a cycle — the duty work is the *origin* of the cycle. The current package invariant doesn't tell us whether the duty agent participates in that cycle, gets temporarily replaced, stays out and consumes its output, or transitions between modes during the engagement.

Three candidate patterns have been identified during design discussion. None are committed; none are implementable until a concrete workload makes the trade-offs unambiguous.

#### Pattern B — Preempt-and-return (single-agent extension)

The duty agent stays *assigned* to the duty but its current mode flips Duty → Cycle for the cycle's duration. The underlying duty RuntimeActivity is paused (the activity model already supports `can_pause` / `can_resume`). When the cycle completes, mode flips back to Duty and the paused activity resumes.

This is mostly a generalization of soft-duty preemption semantics, applied to **self-spawned** cycles rather than external interruption. Architectural lift is small. The package invariants survive intact: at any instant the agent is in exactly one mode, and FocusLease has exactly one owner.

The weakness is that it does not solve the case where the duty *must be covered* during the cycle — if the duty's purpose is monitoring or availability, pausing it for a multi-hour cycle defeats the duty.

#### Pattern D — Backfill / assignment transfer (multi-agent coverage)

This mirrors human on-call rotations. When the on-duty agent must engage in cycle work that would otherwise pause the duty, the duty assignment temporarily transfers to a backfill-eligible agent. The original holder joins the cycle. When the cycle completes, policy decides whether the original resumes or the backfill finishes the rotation.

This is the most operationally realistic pattern but requires concepts the current package does not model:

- Assignment transferability (currently `Assignment` has a single `agent_id` owner)
- Backfill eligibility per assignment (`backfill_eligible_roles`, capability matching)
- Handoff event chain (`assignment.transferred`, `assignment.returned`, `assignment.coverage_assumed`)
- Decisions about state continuity — does the backfill inherit the original's in-flight RuntimeActivity, start fresh, or merge handoff context?
- Reverse-handoff policy when the original returns (or doesn't, if the cycle runs long)

Architectural lift is significant. This is not a v1.x extension — it is a substantive new capability that would warrant its own SIP.

#### Pattern E — Duty has dual nature (planned work + reserve availability)

The current package treats duty as monolithic: an agent is either on duty or not. Real operational duty often has two distinct components:

- **Planned work** — the duty's scheduled tasks (e.g., the nightly research synthesis itself)
- **Reserve availability** — interrupt-readiness for related cycle work or escalations

These could be modeled as separate policies on the same Assignment rather than as separate modes. The current `hard | soft` strictness collapses to a binary; richer expression might look like:

| Posture | Planned work | Interrupt readiness |
|---------|--------------|---------------------|
| **Hard duty** | Non-pausable | Not interruptible |
| **Soft duty** | Pausable | Cycle preempts within graceful window |
| **On-call duty** | Pausable | *Expected* to be interrupted; no graceful_window penalty for cycle joins |
| **Background duty** | Non-pausable | No interrupt readiness — duty runs to completion |

Same primitives, richer policy expression. Pattern E might be the *underlying primitive* that makes Pattern B and Pattern D cleaner to implement. Architectural lift is medium — extends Assignment policy fields without introducing new modes.

#### How this should be resolved

The right way to choose between B, D, and E (or combine them) is **not** to design speculatively now. The right way is to collect concrete duty workloads that Backspring actually wants the squad to perform, write a paragraph on each describing how the agent gets pulled into related cycle work, and let the pattern-counts drive the design.

Suggested seed workloads to evaluate:

1. **Customer support** — does the on-duty support agent escalate to a cycle, or does the cycle pull them in?
2. **Nightly research synthesis** — does the duty agent stay and spawn a cycle that excludes itself, or join?
3. **Inventory anomaly response** — does the on-duty Data agent escalate by triggering a cycle that pulls Lead/Strat in?
4. **Build pipeline watch** — does the on-duty agent attempt repair (cycle?) or page a backfill?
5. **Customer-facing incident response** — does the duty agent run point on a multi-agent investigation, or hand off?

Each will lean toward B, D, or E differently. Once 3–5 workloads are characterized, the dominant pattern will be visible. If B dominates, a small extension to soft-duty semantics is enough. If D dominates, a backfill SIP is warranted. If E dominates, the right move is to enrich Assignment policy fields and let B and D become emergent behaviors.

Until that exercise happens, the package's mutual-exclusivity invariant holds, and duty workloads in v1.1 / v1.2 / v1.3 must compose with cycle work via Pattern A from the original analysis: the duty handler may spawn a cycle that recruits *other* agents and consume the cycle's output, but the duty agent itself does not participate in the spawned cycle. This is the most conservative behavior and is implementable today without any SIP changes.

### Other deferred questions

Two smaller deferred questions worth noting:

- **Multi-active-embodiment per agent** — SIP-0090 v1.2 commits to single-active-embodiment. A future SIP could allow concurrent embodiments (e.g., one agent presenting in Discord and a browser session simultaneously). Deferred until a real workload requires it.
- **FocusLease queueing** — SIP-0089 D20 explicitly defers `queued` lease semantics to v1.2+. A future SIP would add the queue persistence storage, draining processor, and ordering tests required to make `queued` a real outcome rather than fake semantics.

These are smaller scope than the duty/cycle composition question and are flagged in the implementing SIPs themselves; they are listed here only for visibility.

---

## References

- `sips/accepted/SIP-0089-Agent-Runtime-State.md` — v1.1 candidate
- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` — v1.2 candidate
- `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` — v1.3 candidate
- Future follow-on: `SIP-Minecraft-Embodiment-Adapter.md` (not in this package)
- Original full proposal: commit `76a1f90` on main (`git show 76a1f90:sips/proposed/SIP-Agent-Runtime-Modes.md`)
