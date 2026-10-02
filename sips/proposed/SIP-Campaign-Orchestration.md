---
sip_uid: '17883224960382348'
title: Campaign Orchestration
status: proposed
author: jladd
created_at: '2026-07-04T00:00:00Z'
---
# SIP: Campaign Orchestration

## Status

Proposed — **revision 2 (2026-10-01), for design review.** **Targets v2.0, the headline**
(`docs/plans/2-0-0-plan.md`, draft).

**What revision 2 changes.** Revision 1 (2026-07-04, retargeted 2026-08-03, 2026-08-07 and 2026-09-12)
specified a neutral mechanic: an objective envelope and a pure continuation policy over a series of
bounded cycles. It never said what a continuing cycle starts from, or who decides what it builds.
Revision 2 makes the campaign **evolve one app**, on three inputs:
- the owner's direction of 2026-09-28: the squad evolves the app's scope, and frontier models evolve the
  framework (`docs/plans/post-1-8-2-roadmap-reconciliation.md`);
- the owner's IDEA of 2026-10-01: the Nostromo crew supervises campaigns and optimizes the framework
  (`docs/ideas/nostromo-framework-optimization-crew.md`);
- the owner's rulings on that IDEA the same day (§3).

Kept from revision 1, updated where noted:
- the continuation decision as a pure function at one choke point;
- the evidence-integrity rules it inherits;
- the recruitment invariant;
- the domain model's frozen-dataclass shape;
- the registry port.

The placement history before 2026-09-12 is in the revision history at the end.

**Builds on:**
- SIP-0064: cycles, runs, gates.
- SIP-0067: the Postgres registry pattern.
- SIP-0083: multi-run cycles.
- SIP-0089: recruitment through the coordinator and FocusLease.
- SIP-0096: `CycleOutcome`, the evidence roll-up.
- SIP-0103: the authored interface manifest.
- SIP-0107: scoped code revision, which is the edit mechanism.
- SIP-0108: `CycleAssessment` and lineage.
- 1.9's completion boundary: `CycleCompletion`, `adapters/cycles/cycle_completion.py:20`, #1507.

**Carved from:** `SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md`, the 2.0 vision anchor,
whose squad-driven framework improvement has left 2.0 (the 09-28 direction).

---

## 1. Summary

A **Campaign** is an objective envelope over a sequence of bounded cycles that **evolves one app**. It
opens with a calibration cycle. Each later cycle starts from the previous accepted app plus a change
request, proposed by the squad's strategy role and ruled on by a supervisor at a checkpoint. An increment
is accepted only if every earlier increment still passes. A pure continuation policy decides, after each
cycle, whether the campaign continues, repairs, retries, escalates, waits or stops.

Campaign adds what the framework does not have:
1. **an app that carries across cycles**: the brownfield cycle and accumulated acceptance;
2. **scope that evolves under supervision**: the increment proposal and its checkpoint ruling;
3. **objective aggregation and the continuation decision**: revision 1's mechanic;
4. **a supervision interface**: one control surface, on the existing API lanes, for an external
   supervisor, today the Nostromo crew or the owner.

Everything else is reused: per-cycle squads and recruitment, the correction loop inside a run, the
verification roll-up, `CycleAssessment`, gates, deploy lineage. Campaign is a layer above the cycle. It
is not a new execution engine.

---

## 2. Motivation

SquadOps executes a bounded cycle well: one PRD, one squad, one tree built from nothing, one verdict. It
cannot **carry an app** across cycles.
- Every cycle is greenfield.
- No cycle starts from what the last one delivered.
- No record says which increments an app has received, why each was chosen, or whether the earlier ones
  still work.

The owner's 2.0 direction is a campaign of about ten hours in which the squad evolves group_run cycle by
cycle. Its value comes as much from what it teaches about the framework as from the app. A campaign that
cannot evolve an app can only re-run one objective. A campaign whose evolution nobody can inspect
teaches nothing.

---

## 3. The loops, and who owns what

| loop | cadence | owner | what it may do |
|---|---|---|---|
| **squad execution** | within a cycle | the squad (SquadOps) | plan, build, verify, repair, inside the cycle's bounds |
| **campaign** | at each checkpoint, between cycles | SquadOps's continuation policy, **ruled on by the supervisor** | continue, repair, retry, escalate, wait, stop. The next increment's **content** is proposed by the strategy role, and builds only with the supervisor's ruling |
| **framework optimization** | across cycles and campaigns | the outer loop: the owner and the Nostromo crew | observe, hypothesize, propose. **Change the framework only between campaigns, and only with the owner's approval** |

**The owner's rulings of 2026-10-01 that shape this SIP:**
1. **The strategy role proposes the next increment, on a short leash.** The supervisor rules on every
   proposal and watches how increments are proposed and implemented. Its recommendations for the
   feature-writing step are the outer loop's first standing subject (§9).
2. **The crew may run local inference on the Spark between squad cycles and between campaigns, never
   while the squad runs a cycle.** That is the crew operating model's §36 (`backspring-labs/nostromo`).
   This SIP specifies the SquadOps half of the handoff (§9.3).
3. **The continuation policy stays in SquadOps.** The supervisor holds the escalation queue and an
   abort. A campaign never depends on a supervisor's process being alive in order to stay safe: without
   a ruling, it waits.

---

## 4. Decision

1. A **Campaign** references a project, declares an **objective** with an **allowed change scope**, a
   **CampaignPolicy**, and a **supervisor**. It owns an ordered series of cycles. `Cycle` gains an
   optional `campaign_id`. A cycle without one behaves exactly as today.
2. Every campaign **opens with a calibration cycle** (§11). This is the fixed PRD, built from scratch, as
   the yardstick across framework changes.
3. Every later cycle is a **brownfield cycle** (§7). It starts from the previous **accepted tree** plus a
   **change request**, and edits through SIP-0107.
4. An increment is **accepted only under accumulated acceptance** (§8): its own criteria, plus every
   earlier increment's.
5. Between cycles, the **strategy role proposes** the next change request, and the **supervisor rules**
   on it (§9). No increment builds without a ruling.
6. After each cycle reaches `CycleCompletion`, a **pure continuation decision** (§10) yields the next
   action. It reads `CycleAssessment` and never derives a grade itself.
7. A Campaign is persisted (`CampaignRegistryPort`, memory and Postgres), observable through
   `/api/v1/campaigns` and the CLI, and audited (§13).
8. A campaign closes with a **write-once evidence package** and a **morning digest** (§14).

---

## 5. Scope and non-goals

**In:**
- the campaign object, the brownfield cycle, accumulated acceptance, the increment proposal and the
  checkpoint ruling;
- the continuation decision, the calibration cycle, the supervision interface;
- the evidence package and digest, the prior-cycle brief (#1692).

**Not in this SIP:**
- **The squad improving its own framework.** It is out of 2.0 (the 09-28 direction). The framework's
  improvement is the outer loop's, a process run by the owner and the crew.
- **Loosening the leash.** Auto-approval of proposals, in any tier, is not specified here. §9.4 records
  what a later decision would read.
- **`fork`,** meaning concurrent sibling cycles. It is deferred, so 2.0 opens no concurrent-recruitment
  window (§12).
- **Isolated replay for the supervisor** (SIP-0101 exposure). It is later than 2.0.0.
- **Holding agents across cycles** (§12), **unbounded cycles**, **a new runtime mode**.
- **Cross-cycle memory.** That is SIP-Cross-Cycle-Memory, ruled to 2.2. The campaign's continuity is
  explicit: the accepted tree, the ledger and the brief, not recall.
- **Capability-Backed Agents.**

---

## 6. Position in the hierarchy

```
Project
  └── Campaign            objective envelope: one app, evolved across cycles
        ├── calibration Cycle    the fixed PRD from scratch (§11)
        └── increment Cycles     brownfield: accepted tree + change request (§7)
              └── Run → Task     existing
```

| layer | owns | SIP |
|---|---|---|
| task, run | one execution attempt | SIP-0064 |
| intra-run loop | correction within a run | SIP-0086, SIP-0079 |
| multi-run cycle | repeated runs in one cycle | SIP-0083 |
| **campaign** | **the app across cycles: increments, acceptance, continuation** | **this SIP** |

---

## 7. The brownfield cycle (#1705)

### 7.1 The baseline

An increment cycle's baseline is the **accepted tree** of the campaign's last accepted increment:
- the persisted, verified tree, by its SIP-0107 §20 identity;
- never an operator-named tree inside a campaign;
- never a candidate tree that was not accepted.

### 7.2 The change request

A change request has four parts:
- a **PRD delta**;
- an **interface-manifest delta**;
- **acceptance criteria for the increment**;
- a statement of what the increment must not break.

The manifest delta is checked by the same gates as an authored manifest (SIP-0103), applied to the
manifest the delta produces. A delta that the gates refuse is a refused proposal, not a failed cycle.

### 7.3 Framing on a brownfield cycle

Framing runs only the tasks the delta needs. The baseline's accepted manifest and plan answer the rest.
Which tasks those are is design work for implementation, recorded here when it is built. The rule that
binds them: **a framing task that would re-author an accepted artifact from scratch is not run on a
brownfield cycle.**

### 7.4 What a failed increment leaves behind

Nothing. The baseline stays the accepted tree, byte for byte. A failed increment is recorded, its
candidate tree is kept as evidence, and the next cycle (a repair, a retry, or a new proposal) starts from
the same baseline. There is no partial merge.

---

## 8. Accumulated acceptance (#1707, #1796)

An increment is accepted only if:
- its own criteria pass under the cycle's normal verdict (SIP-0096, `CycleOutcome`);
- **every earlier increment's acceptance criteria still pass** on the candidate tree;
- **every route the accumulated manifest declares renders its view** in a browser (#1796).

Accumulated acceptance is re-executed on the candidate tree. It is never carried forward from an earlier
verdict. A criterion that cannot execute counts as `blocked_unverified`, never as a pass (SIP-0096).

### 8.1 An increment's new tests must fail on its baseline

Accumulated acceptance is only as strong as the tests it re-runs. In a campaign, every increment's
tests become guards for every later increment, so a test that cannot fail is a hollow guard for the
rest of the campaign. A brownfield cycle can check this, and a greenfield one cannot: the baseline is
the app without the increment.

- **Feature and fix increments:** the increment's **new** tests are run against the **baseline** tree.
  Each must **fail there as an assertion**. A test that dies on an import error or a missing module
  proves nothing. SIP-0104's Phase 2 assertion-shape classifier already makes that distinction. Each
  test must then pass on the candidate. A new test that passes on the baseline does not discriminate
  the increment, and the increment is not accepted until it is replaced or removed.
- **Refactor increments:** no new test is required. The existing guards must pass on both trees,
  which is what behaviour preservation means.
- **What this check is.** It is the campaign's form of demonstrated discrimination, from
  `SIP-Verification-Yield.md` (§7) and `SIP-Test-First-Verification.md` (Phase 1). It needs no
  contract-conforming stub, because the baseline does that job, and it costs one extra test run per
  increment.
- **Its result is recorded per test in the proposal ledger (§9.4).**

---

## 9. The increment proposal, on the short leash (#1706, #1708)

### 9.1 The proposal

At a checkpoint, the strategy role authors the next change request (§7.2) from:
- the objective and its allowed change scope;
- the accepted app: its manifest, its accumulated acceptance, its open failures;
- the campaign's evidence so far, including the prior-cycle brief (§14);
- any backlog the owner seeded.

Rails:
- **an out-of-scope proposal is refused, not trimmed**;
- a proposal its own author expects to break accumulated acceptance is not a candidate;
- the analyzer's findings and qa's failures reach the strategy role as backlog candidates. No other role
  proposes on its own.

The proposal is authored outside the continuation decision, which stays pure (§10).

### 9.2 The ruling

The supervisor rules on every proposal:
- **approve**, **amend** (the amended change request is what builds), or **reject**;
- every ruling carries a reason.

The supervisor may also:
- **escalate** to the owner;
- **pause** the campaign;
- **abort** it.

**No increment builds without a ruling.** A ruling not given within the checkpoint's declared bound
pauses the campaign (`awaiting_ruling`), and the digest says so. The campaign never proceeds unapproved,
and never waits without a bound being recorded (#1708).

The owner can rule through the same interface at any checkpoint, and is the supervisor when no crew is
assigned.

### 9.3 The checkpoint and the box

A checkpoint is the only time anything other than the squad may run inference on the box (ruling 2):
1. The cycle reaches `CycleCompletion`, and its participants are released (§12).
2. The campaign enters `at_checkpoint`. The continuation decision is recorded, and the proposal is
   published. **No squad inference runs from here until the next launch.**
3. The supervisor may now use the box. The crew's own guard (its operating model §36) reads, through
   SquadOps's API or CLI, that no run is in flight.
4. The supervisor posts its ruling.
5. **The next cycle launches only on a quiet box**: no model resident that the squad's deploy did not
   load. This check is the campaign launch's preflight. SquadOps reads its own state and the box's
   resident models, and never reads the crew's files. A launch refused by the quiet check is recorded,
   retried within a bound, then escalated.

### 9.4 The proposal ledger

One record per increment, written as it happens:
- the proposal and its inputs;
- the ruling, its reason, and who ruled;
- the cycle's outcome: verdict, correction rounds and their causes, framing re-rolls, criteria added, any
  earlier increment broken, and each new test's baseline result (§8.1);
- the supervisor's classification of what went wrong, if anything:
  - scope too large;
  - acceptance criteria not checkable;
  - a conflict with an earlier increment;
  - an ambiguous manifest delta;
  - a sound proposal implemented badly. That last one is **not** a feature-writing defect, and keeping
    it separate is the point.

The ledger is the evidence for two things:
- the outer loop's recommendations to the feature-writing step, which change the framework between
  campaigns, with the owner's approval;
- any later decision to loosen the leash, which this SIP does not make.

### 9.5 The no-progress rule

A campaign whose proposals stop producing accepted increments stops. The rule is declared in
`CampaignPolicy` (`max_unaccepted_increments`). Hitting it yields `stop_failure`, with the ledger as the
reason.

---

## 10. The continuation decision

After a campaign's cycle reaches `CycleCompletion`:

```
campaign_continuation_decision(
    objective:  CampaignObjective,
    policy:     CampaignPolicy,
    evidence:   CampaignEvidence,     # accumulated, by reference
    latest:     CycleAssessment,      # SIP-0108, over SIP-0096's CycleOutcome
) -> ContinuationDecision             # pure; no side effects
```

| outcome | meaning | next |
|---|---|---|
| `continue` | the increment was accepted; propose the next | §9: proposal, then ruling, then launch |
| `repair` | the increment failed a check it can repair | a repair cycle on the same baseline and the same change request, with the prior-cycle brief; the supervisor rules on it like a proposal |
| `retry` | the increment failed for a cause outside the work (infrastructure, a timeout the record attributes) | the same change request again; ruled on |
| `escalate` | the decision needs the owner | the supervisor's escalation queue |
| `wait` | an external condition: a ruling not yet given, a declared resume time | the campaign stays `at_checkpoint` or `paused`. This replaces revision 1's `defer`, whose duty-window borrow had no mechanism (rev 1 open question 5) |
| `stop_success` | the objective is met by its measurement | the evidence package and the digest |
| `stop_failure` | the policy's limits are reached (cycles, budget, time, the no-progress rule) | the evidence package and the digest |

**The integrity rules revision 1 set, kept:**
- `stop_success` requires a roll-up with `verdict = accepted`, or an owner's ruling. Never narrative.
- A `blocked_unverified` verdict yields only `repair` or `escalate`.

**Added by revision 2:**
- No outcome launches a cycle without a checkpoint ruling.
- The calibration cycle's verdict never drives continuation. It is the yardstick, not an increment (§11).

---

## 11. The calibration cycle (#1709)

Every campaign opens with **the same PRD built from scratch** on the campaign's deploy. That is today's
group_run cycle, under a fixed request profile.
- Its result is recorded as the campaign's **yardstick**, and is the outer loop's baseline: a framework
  change is read as helping or not on the calibration cycle before and after it, never on the increments,
  which differ by design.
- Its tree is also the campaign's first accepted baseline when it is accepted. A rejected calibration
  cycle stops the campaign before any increment (`stop_failure`, reason: calibration). A campaign does
  not evolve an app the framework could not build that night.

---

## 12. The recruitment invariant

> **A campaign launches cycles; it never holds agents between them.**

Each cycle recruits as today, through the SIP-0089 coordinator: per-run `ambient→cycle`,
`owner_ref = run_id`, released when the run ends. There is no campaign-scoped lease.
- **#288 is fixed** (1.3.1, 2026-07-08). Revision 1 named it a prerequisite, and it no longer is one.
- **The continuation choke point runs only after the ended cycle's participants are released.** At
  `CycleCompletion` the executor returns them `cycle→ambient`, and the decision sequences after that.
- With `fork` deferred (§5), no two cycles of one campaign ever recruit at once.

---

## 13. The supervision interface

One control surface, on the existing lanes:

| need | where |
|---|---|
| create, start, inspect, pause, resume, abort a campaign; post a checkpoint ruling; read the ledger | `/api/v1/campaigns` (`docs/architecture/api-route-lanes.md`) and `squadops campaigns …` |
| cancel a stalled run | the existing cancel path |
| identity | a supervisor role in Keycloak (SIP-0062), least privilege: campaign controls and reads, nothing else |
| audit | every control operation through `AuditPort`, with actor, role, target, reason, idempotency key, outcome |
| events | campaign decisions, rulings and checkpoints as cycle events (SIP-0077 taxonomy, with its parity tests). The API's reads are authoritative after a missed event |
| provenance | the deploy record (#1720) on every cycle; the accepted-tree identity per increment; the usage ledger per role and task |

**A ruling is idempotent by its key.** A repeated post of the same ruling is the same ruling, never a
second launch.

---

## 14. The evidence package, the digest, and the prior-cycle brief (#1710, #1692)

- **The evidence package** is write-once at campaign close. It holds:
  - the campaign record, the ledger, and every cycle's record and verdict;
  - the accumulated-acceptance results, the calibration reading, the deploy identity;
  - the audit trail;
  - **every failure, under the failure-attribution registry's vocabulary**
    (`src/squadops/cycles/failure_attribution.py`, SIP-0108 §4.2), with its campaign, cycle and
    increment. That way Cross-Cycle Memory (2.2) mines campaigns for recurrence without
    reconstructing it, and no parallel taxonomy is introduced.

  A reader who was not there, without the deploy that made it, can act on it.
- **The morning digest** is the owner-facing summary of the package: increments accepted, the ledger's
  rulings and classifications, campaign health, and the decisions requested.
- **The prior-cycle brief:** a repair or retry cycle is told what the cycle before it did, what failed,
  and what the analysis concluded. It is authored by the framework from that cycle's record, not
  recalled.

---

## 15. Domain model (shapes, not field names)

Frozen dataclasses beside `Cycle` and `Run`:
- **`Campaign`**:
  - id, project, created by and at, `objective`, `policy`, `supervisor`, `cancelled`;
  - status derived from its cycles, its last decision and its checkpoint state.
- **`CampaignObjective`**: statement, allowed change scope, measurement reference.
- **`CampaignPolicy`**:
  - `max_cycles`, budget, time;
  - `max_unaccepted_increments` (§9.5);
  - the checkpoint ruling bound;
  - the calibration request profile.
- **`ChangeRequest`**: PRD delta, manifest delta, acceptance criteria, must-not-break.
- **`CheckpointRuling`**: approve, amend or reject; the amended change request; the reason; who ruled;
  the idempotency key.
- **`LedgerEntry`** (§9.4).
- **`ContinuationDecision`**: outcome, rationale, evidence references, decided at.
- **`CampaignEvidence`**: references, not payloads.

---

## 16. Persistence

`CampaignRegistryPort`, beside `CycleRegistryPort`:
- the campaign, its cycles, its decisions, its rulings, its ledger;
- memory and Postgres adapters, selected by config;
- a migration for `campaigns` and the related tables, plus a nullable `campaign_id` on `cycles`.

Revision 1 named "the Mac range" of migration numbers. That convention is retired with the Mac lane, so
the next free number is used.

---

## 17. Lifecycle

```
draft → calibrating → at_checkpoint ⇄ running_increment
                         ↘ paused (awaiting_ruling | owner pause)
                         ↘ completed (success | failure | aborted | exhausted)
```

`cancelled` derives `CANCELLED`, as on `Cycle`. Every transition is a recorded event with its cause.

---

## 18. Phasing (2.0)

1. **The campaign object:** the model, registry, API and CLI, `Cycle.campaign_id`, the audit. No
   automation.
2. **The brownfield cycle and accumulated acceptance** (§7, §8), with the prior-cycle brief.
3. **The proposal, the ruling, the checkpoint handoff, the ledger** (§9), and the continuation decision
   (§10).
4. **The calibration cycle, the evidence package and the digest** (§11, §14).

Acceptance of the SIP's implementation is all four, the SIP-0089/0090 precedent that a phase is not the
whole SIP.

---

## 19. Acceptance criteria

1. A campaign is created with an objective, an allowed scope, a policy and a supervisor, and survives a
   restart (Postgres).
2. A cycle without a campaign is byte-for-byte unchanged in behaviour.
3. A campaign opens with its calibration cycle. A rejected calibration stops the campaign before any
   increment.
4. An increment cycle starts from the accepted tree's identity. A failed increment leaves that identity
   unchanged.
5. An increment is accepted only with every earlier increment's criteria re-executed and passing, and
   every declared route rendering its view.
5a. A feature or fix increment's new tests each fail on the baseline as an assertion and pass on the
    candidate. One that passes on the baseline blocks acceptance (§8.1).
6. **No increment builds without a recorded ruling.** A ruling not given within its bound pauses the
   campaign, and the record says so.
7. **The next launch refuses a box that is not quiet,** and the refusal is recorded.
8. Every control operation has an audit record with actor, reason and idempotency key. A repeated ruling
   launches nothing new.
9. The continuation decision is pure. An architecture test asserts it does no persistence or dispatch.
   `stop_success` needs an accepted roll-up or an owner's ruling.
10. Every cycle of a campaign holds its own lease, with `owner_ref` set to its run, asserted positively.
11. The evidence package is complete at close: the ledger, every verdict, the calibration reading, the
    deploy identity and the audit. The digest is rendered from it.
12. A two-increment campaign on a live stack: the calibration cycle, two increments proposed, ruled on
    and accepted, the second with the first's criteria still passing.

---

## 20. Risks

- **The leash becomes a bottleneck.** A supervisor slow to rule stalls the campaign. *Mitigation:* the
  ruling bound, `awaiting_ruling` in the digest, and the owner as fallback. Stalling is the safe failure.
- **Feature-writing defects hide behind implementation defects.** *Mitigation:* the ledger's
  classification keeps "a sound proposal implemented badly" apart (§9.4).
- **The box handoff races.** A crew model is still resident when a cycle launches. *Mitigation:* the
  quiet-box preflight is SquadOps's own check, not the crew's word (§9.3).
- **Accumulated acceptance grows slow.** Every increment re-executes every earlier criterion.
  *Mitigation:* measure it per increment in the ledger. A ten-hour campaign of a few increments is the
  scale 2.0 claims.
- **A brownfield framing re-authors the app.** *Mitigation:* §7.3's rule, and the delta gates.
- **Runaway continuation.** *Mitigation:* the policy's caps and the no-progress rule. Every launch is
  ruled on.
- **Scope creep into the 2.0 vision anchor.** *Mitigation:* §5's non-goals.

---

## 21. Relationships

- **Consumes, unchanged:**
  - `CycleCompletion` (1.9);
  - `CycleAssessment` (SIP-0108);
  - `CycleOutcome` (SIP-0096);
  - SIP-0107 (the edit mechanism);
  - SIP-0103's gates (on the delta);
  - SIP-0089 recruitment;
  - the cancel path;
  - deploy lineage (#1720).
- **Enables** the outer loop's process (#1711) and the crew's supervision (the IDEA).
- **Precedent** for the pure decision at one choke point: SIP-0089's reserve-buffer guard, and the
  cycle-create preflight.

---

## 22. Testing

- **Decision (unit):** each outcome from a crafted input; the integrity rules; purity.
- **Registry (integration):** round-trips; survival across restart; the foreign key.
- **The brownfield baseline (unit, plus a replay):** a failed increment leaves the accepted identity
  byte-identical.
- **Accumulated acceptance (wiring):** entering at `CycleCompletion` with a stored two-increment
  record, the earlier criteria reach the verdict.
- **The baseline check (replay):** a stored increment's real suite, run on its real baseline. A test
  that fails only by import error is not credited as discriminating.
- **The ruling gate (wiring):** no launch without a ruling; a repeated ruling launches nothing new; a
  ruling not given pauses the campaign.
- **The quiet-box preflight:** a resident foreign model refuses the launch.
- **E2E:** acceptance criterion 12 on a live stack.

---

## 23. Open questions

1. **Which framing tasks run on a brownfield cycle** (§7.3). This is answered during implementation and
   recorded here.
2. **The manifest delta's form:** a patch to the YAML, or a typed delta the gates read.
3. **The ruling bound's default,** and whether it differs between the crew and the owner.
4. **How the quiet-box check identifies the squad's models,** from the deploy record (#1720) or from the
   squad profile.

---

## Revision history

- **Revision 2 (2026-10-01):** rewritten to the 09-28 direction, the owner's IDEA, and the owner's
  rulings on it. Added:
  - the brownfield cycle, accumulated acceptance, the increment proposal on the short leash, the checkpoint
    and box handoff, the proposal ledger, the calibration cycle, the supervision interface, the evidence
    package, the digest and the prior-cycle brief (#1705–#1710, #1692, #1796);
  - `wait` replaces `defer`; `fork` is deferred; #288 is recorded as fixed;
  - an increment's new tests must fail on its baseline (§8.1), and the evidence package records
    failures under the attribution registry's vocabulary (§14). Both were added after the owner's
    review of the Verification Yield and Cross-Cycle Memory proposals the same day;
  - the continuation decision reads `CycleAssessment` at `CycleCompletion`.
- **Revision 1 (2026-07-04):** the neutral mechanic. Placement history:
  - targeted v1.6;
  - retargeted to v1.8 on 2026-08-03 (`docs/plans/post-1-4-roadmap-reconciliation.md`);
  - billed as a co-headliner of v1.8 on 2026-08-07, with the scorecard's grade definitions landing first
    (`docs/plans/post-1-5-roadmap-reconciliation.md`);
  - retargeted to v2.0, the headline, on 2026-09-12 (`docs/plans/1-8-0-plan.md` §8 decision 1).

  It superseded the "Loop Policy" naming in
  `docs/ideas/SquadOps-Roadmap-Runtime-Loop-Capability-Backed-Agents.md`.

---

## Appendix A — Implementation seams (non-normative)

- **Models** in a `campaigns/` package beside `cycles/`.
- **Port:** `src/squadops/ports/cycles/campaign_registry.py`; adapters under `adapters/persistence/`.
- **The choke point:** where a cycle reaches `CycleCompletion`. If the cycle has a `campaign_id`, the
  campaign is loaded, the decision computed and recorded, and the checkpoint entered.
- **The decision:** a pure module, `campaigns/continuation.py`.
- **The proposal:** a task of the strategy role, run at the checkpoint, outside the continuation decision.
- **The quiet-box preflight:** beside the cycle-create preflight.
- **CLI:** `squadops campaigns create|show|list|rule|pause|resume|abort`.
