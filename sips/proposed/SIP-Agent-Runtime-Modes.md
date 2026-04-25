# SIP: Agent Runtime Modes — Vision and Index

**Status:** Proposed (umbrella / vision)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 2 (split into three implementing SIPs on 2026-04-25)
**Original full proposal:** commit `76a1f90` on main

---

## Purpose of this document

This document is the **umbrella vision** for evolving SquadOps from a cycle-only execution framework into a runtime that supports persistent, schedule-aware, and (eventually) embodied agents.

It does **not** propose implementation. The actionable proposals live in three sibling SIPs, each independently reviewable and shippable.

The original revision-1 draft was a single 1,100-line proposal. After design discussion it was split into three smaller SIPs so each scope (runtime taxonomy, embodiment, Temporal) can be reviewed and accepted independently. The original full content is preserved in git history at commit `76a1f90`.

---

## The central insight

> **Current posture, future commitments, and immediate action must be modeled separately.**

- **Mode** is what the agent is doing now — exactly one of `duty | cycle | ambient`.
- **Assignment / schedule** is what may claim the agent later.
- **Focus / activity** is what currently owns its attention.

Without this separation, persistent agents become unobservable — schedules live in prompts, recall happens by vibes, and "free" vs. "committed" become guesses. With it, SquadOps gains a credible path to operational agents (Backspring support, monitoring, research) and embodied surfaces (Discord, browser, eventually Minecraft) without diluting the cycle model.

---

## The three top-level modes

| Mode | Meaning | Examples |
|------|---------|----------|
| **Duty** | On-duty, service-responsible, availability-constrained | Customer support, inventory watch, nightly research |
| **Cycle** | Bounded, formal, assigned work with explicit completion semantics | Build a feature, run an experiment, validate an artifact |
| **Ambient** | Off-duty, low-priority, interruptible background presence | Idling, lightweight observation, recallable presence |

These are mutually exclusive. An agent has exactly one mode at a time. Direct human interaction is **not** a mode — it is a cross-cutting interaction path that can occur in any mode.

---

## The three implementing SIPs

### 1. `SIP-Agent-Runtime-State.md` — v1.1 candidate

**Scope:** Mode, assignment, duty window, focus lease, activity model. Pure runtime-state primitives. No embodiment, no Temporal.

**Why first:** Everything else depends on these primitives. Once an agent has `mode`, `focus`, `activity`, `assignments`, and `focus_lease`, it is observable and schedulable. Embodiment and durable workflows attach to these primitives later.

### 2. `SIP-Agent-Embodiment-Substrate.md` — v1.2 candidate

**Scope:** Embodiment abstraction (identity / runtime-surface separation), location as a generic concept, capability-aware Activity scheduling, resource budgets, first proof point on Discord.

**Why second:** Once persistent agents exist, the next architectural question is "how do they act in external surfaces?" Discord is chosen as the first proof point because it is lighter to test than Minecraft. Minecraft becomes a follow-on SIP once the substrate is proven.

### 3. `SIP-Duty-Durability-Temporal.md` — v1.3 candidate

**Scope:** Temporal as a narrowly-scoped durability layer for Duty workflows only. Optional dependency. Proof point: a `nightly_research` duty surviving worker restarts.

**Why third:** Duty windows can be served by an in-process scheduler in v1.1. Temporal becomes valuable when production-grade durability matters — and the right time to add a second orchestrator is after the duty model has shape.

---

## Why three SIPs instead of one

The original umbrella proposal was good design but bad packaging. Reviewing it required signing off on:

- A new runtime taxonomy
- An embodiment abstraction
- A new optional orchestrator (Temporal)
- A virtual-world execution surface (Minecraft)

…all at once. That made meaningful design review difficult — reviewers either had to accept the whole vision or push back on the whole thing.

Splitting into three lets each design review happen on its own merits:

- The runtime taxonomy can be approved and shipped without committing to Temporal.
- The embodiment substrate can be approved without committing to Minecraft.
- The Temporal adapter can be approved without rewriting agent semantics.

It also bounds the blast radius. If the embodiment substrate doesn't pan out as expected, v1.1 still ships and is useful. If Temporal turns out to be the wrong answer, v1.1 and v1.2 are unaffected.

---

## Sequencing rules

- **v1.1 must land before v1.2 or v1.3.** Both follow-ons depend on the runtime-state primitives.
- **v1.2 and v1.3 are independent.** They can be reviewed and shipped in either order, or in parallel.
- **No version bump is implied by accepting these SIPs.** Acceptance is a design commitment. The actual `pyproject.toml` bump to 1.1 happens when the v1.1 implementation is feature-complete.
- **In-flight 1.0.x cycle hardening continues unaffected.** Nothing in these SIPs touches the cycle execution path until implementation lands behind feature flags.

---

## Architectural principles (carried forward from the original proposal)

These principles should govern all three implementing SIPs:

1. **Keep top-level runtime postures small.** Three modes. Resist additions.
2. **Keep current mode singular.** No "kind of duty and kind of cycle."
3. **Keep assignments and schedules orthogonal to current mode.** Future commitments are not the same as current state.
4. **Treat direct interaction as cross-cutting.** Not a peer mode.
5. **Do not embed world semantics into core too early.** Core knows embodiment and location exist; adapters know the rest.
6. **Keep Cycle canonical for bounded work.** Even Minecraft builds respect cycle semantics.
7. **Use Duty for service-like persistence.** Don't stretch Cycle into a poor imitation of long-running operations.
8. **Prefer explicit recalls over implicit interruption.** Higher-priority claims produce explicit transitions, not prompt drift.

---

## What this umbrella does NOT contain

The full architectural argument, data model sketches, transition tables, risk register, and open-questions list from the original proposal are **not** duplicated here. They have been distributed into the three implementing SIPs where they are actionable, and the original full text is preserved in git at commit `76a1f90`.

This document exists only to:

- Frame the central insight
- Index the three implementing SIPs
- Document the sequencing and rationale for the split
- Preserve the architectural principles that govern all three

For implementation detail, read the implementing SIPs.

---

## References

- `sips/proposed/SIP-Agent-Runtime-State.md` — v1.1 candidate
- `sips/proposed/SIP-Agent-Embodiment-Substrate.md` — v1.2 candidate
- `sips/proposed/SIP-Duty-Durability-Temporal.md` — v1.3 candidate
- Original full proposal: commit `76a1f90` on main (`git show 76a1f90:sips/proposed/SIP-Agent-Runtime-Modes.md`)
