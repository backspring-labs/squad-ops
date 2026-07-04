---
title: Campaign Orchestration
status: proposed
author: jladd
created_at: '2026-07-04T00:00:00Z'
---
# SIP: Campaign Orchestration

## Status
Proposed

**Targets:** v1.6 (feature minor — this is the headline feature SIP that gates 1.6)
**Carved from:** `SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md` (the 2.0 vision anchor). This SIP is the **near-term, implementable mechanic** — the objective envelope + continuation policy — with no dependency on capability packs, Test Bay, or new agent roles. See `docs/plans/2-0-roadmap-reconciliation.md`.
**Supersedes:** the "Loop Policy" naming in `docs/ideas/SquadOps-Roadmap-Runtime-Loop-Capability-Backed-Agents.md`. The idea's continuance-decision vocabulary is adopted here as the Campaign continuation decision.
**Builds on:** SIP-0064 (Cycle/Run/TaskFlowPolicy + gates), SIP-0067 (Postgres cycle registry pattern), SIP-0070 (pulse checks / verification evidence), SIP-0083 (multi-run cycle orchestration), SIP-0089 (runtime state / cycle recruitment via the coordinator + FocusLease), SIP-0069 (Continuum console).

---

## 1. Summary

Introduce **Campaign** as a new orchestration level that sits **between Project and Cycle**: a durable objective envelope that coordinates a sequence of bounded Cycles toward a measurable outcome, and decides — from verification evidence and a declared policy — whether to launch another Cycle, repair, retry, fork, escalate, defer, or stop.

Campaign adds exactly two things the framework does not have today:

1. **Objective aggregation** — a durable record that ties multiple Cycles to one objective and accumulates their evidence and decisions.
2. **Automated re-cycle decision** — a pure, evidence-driven **continuation policy** that runs after each Cycle completes and yields the next action.

Everything else Campaign appears to need already exists and is **reused unchanged**: per-Cycle squads (each Cycle already snapshots its own `squad_profile_id`), intra-run iteration (SIP-0086 build convergence, SIP-0079 correction), multi-run-within-a-Cycle (SIP-0083), verification evidence (SIP-0070), operator gates (SIP-0064 `Gate`/`GateDecision`), and cycle recruitment (SIP-0089 coordinator/FocusLease, per-run `ambient→cycle` acquire/release). Campaign is a thin, high-value layer, not a new execution engine.

---

## 2. Motivation / Problem

The Cycle is intentionally **bounded** — one focused effort with a defined scope, squad profile, acceptance criteria, and deliverable. There is no first-class abstraction for an **objective that spans multiple Cycles**: build a feature, review the result, repair what failed, and continue until a measurable target is met.

Today an operator pursues a multi-Cycle objective by hand: create a Cycle, read the outcome, decide whether to create another, choose its request profile, and remember the thread connecting them. That thread is not durable, not observable, and not replayable. There is no record that says "these five Cycles pursued one objective, here is the evidence they accumulated, here is why each next Cycle was launched, and here is the final disposition."

The consequence is that SquadOps can execute bounded work well but cannot **carry an objective** across bounded work. That gap blocks the entire 2.0 self-improvement direction (nightly improvement Campaigns, Test Bay proving, capability promotion) — all of which are *specialized Campaigns*. Campaign Orchestration is the substrate they stand on, and it is independently useful for any human-directed multi-Cycle objective now.

---

## 3. Decision

Introduce a durable **Campaign** domain object and a deterministic **continuation policy**:

1. A **Campaign** references a Project, declares a measurable **objective** and a **CampaignPolicy**, and owns an ordered set of Cycles pursued under that objective. A `Cycle` gains an optional, nullable `campaign_id` — additive and backward-compatible; a Cycle created without a Campaign behaves exactly as today.
2. After each Cycle in a Campaign reaches a terminal state, a **pure continuation decision** is computed from `(objective, policy, accumulated evidence, latest cycle outcome)`, yielding one of a fixed set of outcomes (§7). The decision is recorded; if it launches a new Cycle, that Cycle is created through the **existing** cycle-create path with a policy-derived request profile.
3. A Campaign is **persisted** via a `CampaignRegistryPort` (memory + Postgres adapters), mirroring `CycleRegistryPort`.
4. A Campaign is **observable** in Continuum: objective, current Cycle, accumulated evidence, continuation decisions, and disposition.

The continuation decision follows the established SquadOps pattern of a **pure decision function enforced at a single choke point** (the reserve-buffer guard, the cycle-create preflight): no side effects inside the decision, side effects only at the boundary that acts on it.

---

## 4. Scope

- **In:** the Campaign domain model, `CampaignPolicy`, the `ContinuationDecision` vocabulary and pure decision function, the `CampaignRegistryPort` + adapters, the additive `Cycle.campaign_id` link, campaign lifecycle, the choke point that runs the decision after a Cycle terminates, and the Continuum Campaign surface.
- **In (reuse, not rebuild):** per-Cycle squad selection, cycle recruitment, intra-run/multi-run loops, verification evidence, operator gates — all consumed as-is.
- **Applies to** Campaigns created via the API/CLI and, later, on a schedule.

---

## 5. Non-Goals

Explicitly **not** in this SIP (they belong to the 2.0 Self-Improvement + Test Bay SIP or elsewhere):

- **Self-Improvement Campaign types, Test Bay, capability supply chain, staged-autonomy ladder, new agent roles, scorecards.** Campaign Orchestration is the neutral mechanic; those are specialized consumers of it.
- **Holding an agent across Cycles.** Each Cycle re-recruits through the existing coordinator/FocusLease path (`owner_ref = run_id`). Campaign never introduces a cross-Cycle lease or a longer-lived attention hold — that would touch SIP-0089 lease semantics, which we deliberately leave untouched (§8).
- **Making a Cycle unbounded.** Long-running objectives are handled by *coordinating multiple bounded Cycles*, never by relaxing a Cycle's acceptance boundary.
- **A new runtime mode.** Campaign is orchestration state, not agent posture. It does not join `ambient/cycle/duty`.
- **Replacing intra-cycle iteration.** SIP-0086/0079/0083 own within-Cycle continuance; Campaign sits strictly above them.
- **Autonomous promotion / self-modification.** Campaign can *escalate to an operator gate*; it grants no new authority.
- **Heavy artifact storage.** Campaign aggregates *references* to evidence (SIP-0064 `ArtifactRef`, verification records); a durable artifact store is Test Bay's concern (2.0).

---

## 6. Position in the Hierarchy

```
Project
  └── Campaign            ← NEW: objective envelope, coordinates N Cycles
        └── Cycle         bounded work (existing; gains optional campaign_id)
              └── Run     execution attempt (existing; SIP-0083 multi-run)
                    └── Task
```

Layered continuance — each layer already owns its band except the top one:

| Layer | Owns | SIP |
|---|---|---|
| Task/Run | one execution attempt | SIP-0064 |
| Intra-run loop | build convergence / correction within a run | SIP-0086 / SIP-0079 |
| Multi-run cycle | repeated runs within one bounded Cycle | SIP-0083 |
| **Campaign** | **continue/repair/retry/fork/escalate/defer/stop across Cycles toward an objective** | **this SIP** |

`CampaignPolicy` is a **sibling to `TaskFlowPolicy`** (`src/squadops/cycles/models.py`): both are frozen "declared orchestration intent" records, one scoped to runs-within-a-cycle, the other to cycles-within-a-campaign.

---

## 7. Continuation Decision

After a Cycle in a Campaign reaches a terminal state, the framework computes:

```
campaign_continuation_decision(
    objective:  CampaignObjective,
    policy:     CampaignPolicy,
    evidence:   CampaignEvidence,      # accumulated across prior Cycles
    latest:     CycleOutcome,          # verification/gate results of the just-finished Cycle
) -> ContinuationDecision              # pure; no side effects
```

### 7.1 Outcome vocabulary (adopted from the roadmap idea, §7.7)

| Outcome | Meaning | Reuses |
|---|---|---|
| `continue` | Launch the next Cycle with the current strategy | cycle-create |
| `repair` | Launch a correction-oriented Cycle for a failed verification | SIP-0079 framing at Cycle scope |
| `retry` | Re-run the same Cycle scope with bounded changes | cycle-create |
| `fork` | Launch an alternate approach as a sibling Cycle path | cycle-create |
| `escalate` | Request an operator decision before proceeding | SIP-0064 `Gate`/`GateDecision` |
| `defer` | Pause until an external condition or duty window | SIP-0089 duty windows |
| `stop_success` | Objective met per its measurement method | — |
| `stop_failure` | Objective unreachable under current policy limits | — |
| `summarize` | Emit the final Campaign report | — |

### 7.2 Decision inputs

The objective's **measurement method**, the latest Cycle's **verification/acceptance evidence** (SIP-0070 pulse checks + gate outcomes), accumulated evidence, and **policy limits** (max cycles, budget, time, required-evidence thresholds). No agent narrative alone may drive `stop_success` — it must point to verification evidence or an operator gate.

### 7.3 Decision output

`ContinuationDecision(outcome, rationale, evidence_refs, next_request_profile | None, decided_by, decided_at)`. When the outcome launches a Cycle, `next_request_profile` is the (policy-derived) cycle request profile handed to the **existing** cycle-create path. The decision is appended to the Campaign's decision history — the durable answer to "why was the next Cycle launched?"

---

## 8. Recruitment Invariant (the thing we must not break)

> **A Campaign launches Cycles; it never holds agents between them.**

Each Cycle recruits its squad exactly as today: the SIP-0089 coordinator grants a per-run `ambient→cycle` transition (`owner_ref = run_id`, `duty(2) > cycle(1) > ambient(0)` precedence, reserve-buffer guard), released when the run ends. Campaign sits entirely *above* recruitment — it decides *whether* and *with what request profile* to launch the next Cycle, then calls the ordinary path. There is no Campaign-scoped FocusLease, no cross-Cycle attention hold, no change to `runtime` lease semantics. This keeps the highest-risk part of the runtime untouched and is the reason Campaign is a bounded, low-risk feature.

---

## 9. Domain Model (shapes, non-binding on field names)

Frozen dataclasses in the SIP-0064 style, alongside `Cycle`/`Run`:

- **`Campaign`** — `campaign_id`, `project_id`, `created_at/by`, `objective`, `campaign_policy`, `cancelled`. Status is **derived** from its Cycles' states + its last continuation decision (mirroring `Cycle`'s derived-status pattern), not stored redundantly.
- **`CampaignObjective`** — `statement` (human-readable), `measurement_ref` (how success is judged — a verification/scorecard reference, may be null for operator-judged objectives), optional `target_type` (a neutral taxonomy hook the 2.0 self-improvement SIP extends; unused here).
- **`CampaignPolicy`** (sibling to `TaskFlowPolicy`) — `max_cycles`, `continuation_gates: tuple[Gate, ...]` (operator escalation points, reusing SIP-0064 `Gate`), optional `budget` and `stop_conditions`. Declared continuation intent.
- **`ContinuationDecision`** — as §7.3.
- **`CampaignEvidence`** — an accumulation of references (Cycle outcomes, `ArtifactRef`s, verification records) — *references, not heavy payloads*.

**Link:** `Cycle` gains `campaign_id: str | None = None` (additive, nullable). No behavior change for Campaign-less Cycles.

---

## 10. Persistence

`CampaignRegistryPort` (ABC in `ports/`) mirroring `CycleRegistryPort`: `create_campaign`, `get_campaign`, `list_for_project`, `attach_cycle`, `record_continuation_decision`, `append_evidence`. Memory + Postgres adapters, config-selected like the cycle registry. Mutators carry the `conn: Any = None` unit-of-work seam (D25). New migration in the Mac range (`1100–1199`; next free is `1150+`): a `campaigns` table + a nullable `campaign_id` column on `cycles` with an FK. Frozen-dataclass mutation via `dataclasses.replace()`.

---

## 11. Lifecycle

`draft → active → (paused | blocked) → completed` with terminal `completed` carrying a disposition (`success | failure | rejected | exhausted | escalated`). `cancelled=True` derives `CANCELLED` regardless of Cycle state, mirroring `Cycle.cancelled`. Transitions are driven by continuation decisions (`defer → paused`, `escalate → blocked pending gate`, `stop_* / summarize → completed`).

---

## 12. Continuum Surface (SIP-0069)

Continuum shows active/paused/blocked/completed Campaigns; a Campaign detail view exposes objective, current Cycle, accumulated evidence summary, the **continuation-decision history** (each with its rationale + evidence refs), and disposition. Operator actions map to existing gate decisions where a continuation `escalate` is pending. No new HTTP prefix — Campaign resources follow the `/api/v1/<resource>` lane (per the API conventions rule); read surfaces reuse the cycle read patterns.

---

## 13. Phasing (within the 1.6 arc)

- **Phase 1 — Model + registry + manual coordination.** `Campaign`/`CampaignObjective`/`CampaignPolicy` models, `CampaignRegistryPort` + adapters, the additive `Cycle.campaign_id`, create/attach via API+CLI, derived status. An operator can group Cycles under an objective and see the aggregate. *No auto-continuation yet.* (Migration-light, CI-able — mirrors how SIP-0090 Phase 1 proved the model before wiring.)
- **Phase 2 — Continuation policy.** `campaign_continuation_decision` pure function + the choke point that runs it when a Campaign's Cycle terminates, records the decision, and launches the next Cycle through the existing create path. This is the headline capability.
- **Phase 3 — Continuum surface.** The Campaign views + continuation-decision history + operator gate integration.

Acceptance of the SIP is **all three phases**, consistent with the SIP-0089/0090 precedent that a phase ≠ the whole SIP.

---

## 14. Acceptance Criteria

1. A Campaign can be created against a Project with a declared objective and policy, and persists across restart (Postgres adapter).
2. A Cycle can be created **with** a `campaign_id` and **without** one; the Campaign-less path is byte-for-byte unchanged in behavior.
3. After a Campaign's Cycle terminates, a `ContinuationDecision` is computed, **recorded with its rationale and evidence refs**, and — when the outcome launches a Cycle — the next Cycle is created through the ordinary cycle-create path with the policy-derived request profile.
4. **Recruitment invariant holds:** no Campaign-scoped lease exists; each launched Cycle recruits per-run through the SIP-0089 coordinator exactly as a standalone Cycle does (verified by asserting lease `owner_ref` is a `run_id`, never a `campaign_id`).
5. `stop_success` is never emitted on agent narrative alone — it requires verification evidence or an operator gate.
6. Policy limits are enforced: a Campaign cannot exceed `max_cycles` or its budget; exhaustion yields `stop_failure`/`exhausted`, not silent looping.
7. The continuation decision is **pure** — an architecture test asserts the decision function performs no persistence/dispatch (side effects live only at the choke point).
8. Continuum shows a Campaign's objective, current Cycle, decision history, and disposition.
9. A completed Campaign produces a final report answering: objective, what each Cycle changed, evidence, whether the objective was met, disposition.

---

## 15. Risks

- **Runaway continuation.** *Mitigation:* hard `max_cycles`/budget/time caps in policy (AC#6); `stop_failure` on exhaustion; the decision is pure and inspectable.
- **Scope creep into the 2.0 apparatus.** Self-Improvement/Test-Bay/capability pressure will want in. *Mitigation:* §5 non-goals are load-bearing; `target_type` is the single neutral extension hook, unused here.
- **Recruitment-semantics drift.** A "keep the squad warm across Cycles" optimization would breach §8. *Mitigation:* AC#4 architecture assertion; the invariant is stated as the SIP's central constraint.
- **Continuation-map vs verification drift.** The decision reads SIP-0070/gate evidence; if that evidence shape changes, the decision inputs must track it. *Mitigation:* consume verification through its existing contract, not a private copy.
- **Overlap with SIP-0083.** Multi-run-within-a-cycle already exists; a poorly-drawn boundary could duplicate it. *Mitigation:* §6 layering — Campaign only acts *after a Cycle terminates*, never on runs within a Cycle.

---

## 16. Relationships

- **Carved from** the Campaign/Self-Improvement/Test-Bay vision anchor; **enables** the 2.0 Self-Improvement SIP (a Self-Improvement Campaign is a specialized Campaign type).
- **Sibling** to `TaskFlowPolicy` (SIP-0064); **above** SIP-0086/0079/0083.
- **Consumes** SIP-0070 verification, SIP-0064 gates, SIP-0089 recruitment, SIP-0069 Continuum — all unchanged.
- **Precedent** for the pure-decision-at-a-choke-point shape: SIP-0089 §2.5 reserve-buffer guard, SIP-0095 cycle-create preflight.

---

## 17. Testing

- **Decision (unit):** each outcome from a crafted `(objective, policy, evidence, latest)`; exhaustion → `stop_failure`; `stop_success` requires verification evidence; purity (no I/O).
- **Registry (integration, real persistence):** create/attach/record round-trips; Campaign survives restart; `campaign_id` FK on cycles.
- **Backward-compat:** Campaign-less cycle-create is unchanged (existing cycle suite passes untouched).
- **Recruitment invariant:** a Campaign-launched Cycle produces a lease with `owner_ref = run_id` (never `campaign_id`).
- **E2E:** a 2-Cycle Campaign on a live stack — first Cycle completes, continuation decision launches the second, final report renders (per the live-cycle-validation rule).

---

## 18. Open Questions

1. Should `fork` create a sibling Campaign or a branched Cycle path within the same Campaign? (Leaning: branched Cycle path; a separate objective is a separate Campaign.)
2. Minimum `CampaignPolicy` for Phase 2 — is `max_cycles` + budget + a verification threshold enough, or is a small stop-condition DSL needed?
3. Does scheduled/nightly Campaign creation belong here (thin scheduler reuse of SIP-0089's poll) or in the 2.0 Self-Improvement SIP? (Leaning: the *scheduling mechanic* here if cheap; *nightly-improvement policy* in 2.0.)
4. How much evidence does the continuation decision need inline vs by reference to stay pure and cheap?

---

## Appendix A — Implementation Seams (non-normative)

- **Models** alongside `Cycle`/`Run` in `src/squadops/cycles/models.py` (or a new `campaigns/` package if the module grows).
- **Port** `src/squadops/ports/cycles/campaign_registry.py` mirroring `cycle_registry.py`; adapters under `adapters/persistence/` + memory, config-selected via the registry factory.
- **Choke point** where a Cycle transitions to terminal (the cycle lifecycle / dispatched-flow completion boundary): if the Cycle has a `campaign_id`, load the Campaign, compute `campaign_continuation_decision`, record it, and act on the outcome via the ordinary cycle-create service. Runs *after* #186's executor decomposition lands (cleaner completion boundary) — a soft sequencing note, not a hard dependency.
- **Decision** a pure module `campaigns/continuation.py` (mirrors `cycles/preflight.py`), importable by the service and tests without an import-hygiene violation.
- **CLI** `squadops campaigns create|show|list` mirroring `squadops cycles …`.
