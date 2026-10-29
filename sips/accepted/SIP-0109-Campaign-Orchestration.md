---
sip_uid: '17883224960382348'
title: Campaign Orchestration
status: accepted
author: jladd
created_at: '2026-07-04T00:00:00Z'
sip_number: 109
updated_at: '2026-10-01T22:03:31.055983Z'
---
# SIP-0109: Campaign Orchestration

## Status

Accepted — **revision 6 (2026-10-01).** Accepted on 2026-10-01 on the owner's ruling, after the crew's
design review approved revision 6 for implementation (Ripley, on #1798, at `78ab4c73`). **Targets v2.0,
the headline** (`docs/plans/2-0-0-plan.md`, adopted the same day).

**The rule this SIP establishes** (from the crew's design review, adopted):

> A campaign is a **persisted, resumable state machine** in which:
> - **the strategy role alone authors change requests;**
> - **the supervisor rules without becoming the author;**
> - **every launch is derived exactly once from durable evidence and a recorded ruling.**

**What revision 6 changes.** The crew's fourth review (Ripley, on #1798) confirmed revision 5 resolved all
seven of its prior findings, and named one final state-machine contradiction: escalation both bypassed
and obeyed the pausing guard. Revision 6 sets one precedence:
- terminal outcome, then escalation, then the pausing guard, then the autonomous launch or abandonment;
- `escalate` is unguarded, and the guard applies only to guardable actions;
- an owner's ruling is not re-guarded (§10, criterion 12g).

**What revision 5 changed.** The crew's third review (Ripley, on #1798) found revision 4 close, and named
bounded corrections, all made here:
- **frozen criteria execute under their own content-addressed verifier bundles** through a named
  candidate-verifier overlay, the fourth tree (§7.4, §8.1);
- **only cycle-launch actions create launch intents;** escalate, stop and abandonment are control
  transitions (§10);
- **the failure producer takes the cycle's outcome,** `failure_events(outcome, evidence)`, with the
  order of writes in the completion transaction defined (§14);
- **repair exhaustion is deterministic:** rejected-and-exhausted abandons and proposes;
  unverified-and-exhausted escalates (§10a).

**What revision 4 changed.** The crew's re-review of revision 3 (Ripley, on #1798) found five seams that
would break implementation. Revision 4 closes them:
- **a paused decision resumes its recorded pending action**, with no recomputation (§10);
- **repair and retry cycles have an exact contract** (§10a);
- **launches go through an outbox**, with idempotent cycle creation (§12b);
- **failure records come from one named producer and one write point** (§14);
- **each criterion owns its verifier bundle**, so freezing one never couples it to another (§8.1).

**What revision 3 changed.** Revision 2 made the campaign evolve one app, under a supervisor's leash.
The crew's design review of it on #1798 (Ripley, 2026-10-01) found that it left the architecture to be
established during implementation. Revision 3 decides it:
- **The proposal runs as the first run of the increment cycle,** recruited like any run, and the
  supervisor's ruling is a **cycle gate** after it, using the gate decisions that already exist (§9).
- **The continuation decision is an ordered table** with predicates and precedence (§10).
- **Each increment carries a typed change request** (§7.2), and evaluation uses **three trees**, with a
  normative seam table (§7.4, §8.4).
- **A transactional control log is the authority** for every control operation. Security audit is a
  projection of it (§13).
- **Evidence is append-time records plus a close-time projection** (§14).
- **The open questions are answered** (§23).
- **The implementation order is dependency-ordered** (§18).

Kept from revision 2:
- the brownfield cycle and accumulated acceptance;
- the strategy role's proposal on a short leash;
- the box lease;
- the limits, the calibration cycle and the brownfield reference scenario;
- the evidence package and digest.

The revision history at the end has the earlier placements.

**Builds on:**
- SIP-0064: cycles, runs, gates, `GateDecisionValue`.
- SIP-0067: the Postgres registry pattern.
- SIP-0083: multi-run cycles.
- SIP-0089: recruitment through the coordinator and FocusLease.
- SIP-0096: `CycleOutcome`, the evidence roll-up.
- SIP-0103: the authored interface manifest, its gates, and #811's revision loop.
- SIP-0107: scoped code revision, which is the edit mechanism.
- SIP-0108: `CycleAssessment`, and the failure-attribution registry.
- 1.9's completion boundary: `CycleCompletion`, `adapters/cycles/cycle_completion.py:20`, #1507.

---

## Delivery ledger (current as of 2026-10-28)

Kept by the rule in CLAUDE.md ("SIP System"): one row per part, updated in the PR that ships or re-places it, read at each release cut. Built from the read-only SIP-portfolio audit of 2026-10-04; `sips/PORTFOLIO.md` indexes it.

| part | status | where |
|---|---|---|
| §18 steps 1–8 (control log through recovery diagnostics) | **shipped** | **v2.0.0**; the counted set read PASS (§24at) |
| package renderings: the size bound and the digest's what-shipped and proposals sections | **shipped** | v2.0.0 (#1998) |
| package renderings: the app's evolution with screenshots | **shipped** | the v2.0.0 release package: campaign 2 at each of its four accepted trees (#1710, with #2000's capture fix) |
| package renderings: the squad's first pass | **dropped** (the owner chose to drop it at the v2.0.0 cut, 2026-10-04; the digest and package carry the close) | #1710, closed |
| the outer-loop runbook's second half | **shipped** | v2.0.0 (#1997, closed #1711) |
| criterion files freeze rules the approved request never stated (the set's P9) | **shipped** (§24ax, §24ay): the rule reaches every author of an increment's tests, and unsupported behaviour is returned as a proposal | 2.1.0, PRs #2012 and #2019, issue #1884 |
| a proposal's PRD delta can state more than its manifest delta carries | **shipped** (§24aw: the request says so; no rail) | 2.1.0, #2014 |
| rows 10–11 reachable live (environment attribution) | **shipped** (§24bg, §24bh): the rows read the attribution, are asked before rows 8–9, and the box's and the queue's refusals record an infrastructure ending | 2.1.0, PRs #2080 and #2102, issues #1824 and #2101 |
| proposal tasks re-run on re-attach (random ids) | **shipped**: every workload's task ids are deterministic | 2.1.0, PR #2033, issue #1934 |
| a restart leaves the interrupted run's Prefect flow runs open (the re-attach, §24am) | **shipped**: a dead process's flow runs are ended when the run re-attaches and when it ends | 2.1.0, PR #2033, issue #2007 |
| the stack's frozen conventions told to the proposer (Next.js; the rest) | **shipped** (§24av) | 2.1.0, #2013 |
| the rails accept an empty manifest delta | **shipped** (§24au) | 2.1.0, #2011 |
| the prior-cycle brief's remainder | **shipped** (§24bf) | 2.1.0, PR #2071, issue #1692 |
| the supervisor creates and manages campaigns (revises §24al) | **shipped** (§24az) | 2.1.0, PR #2047, issue #1940 |
| a campaign records its definition file's hash | **shipped** | 2.1.0, PR #2050, issue #1954 |
| supervisor instruments (the lease proof, the binding replay, the loaded checks, the watcher) | **shipped** | 2.1.0, PR #2025, issue #1956 |
| per-increment scorecard in the digest (§24bb) | **shipped** | 2.1.0, PR #2027, issue #1960 |
| increment replay (any increment of any campaign, outside it) | **shipped** | 2.1.0, PR #2026, issue #1959 |
| the plan-review tier at the plan gate, declared by `plan_gate` (§24bj) | **shipped**; activation held until 2.2's measurement window closes | 2.2.0, PR #2146 |
| the escalation queue: its store, the bound's expiry and the parked cycle (§24bk) | **shipped** | 2.2.0, PR #2147 |
| the escalation queue's late answer, its digest lists and its CLI (§24bl) | **shipped** | 2.2.0, PR #2148 |
| the late answer corrected (§24bm): one answer per decision, carried into a tier campaign's next manifest only for the same question, and an open or uncarried question escalates | **shipped** | 2.2.0, PR #2189, issue #2188 |
| the tier's activation, after 2.2's measurement window closes, and its live reading in the cut's campaign shakeout (the 2.2 plan, steps 10–11) | **shipped** | 2.2.0, issue #1708: activated in the cut's shakeout `cmp_3c22edb866c2`, which decided all 3 of its plan gates `system:plan_review_tier` (the cut pre-registration's P3, §10, PR #2219). The tier diagnostic's calibration escalated on an open question, and the delegate's answer resolved it inside the bound. The timeout half (expiry, the parked cycle, the continuation) is read in unit tests only; its live reading is the next row |
| the timeout half, read live: the expiry, the parked increment, row 15, the no-progress stop and the late answer, on a diagnostic campaign whose increments ask a question (the `increment_design_asks` seed fault) | **shipped:** 2.3.0, PR #2307, issue #2279. Read live on `dep_c627c2873c3c`, 2026-10-14: every pre-registered reading held, after the reading found #2290, #2301 and #2303 (fixed by #2293, #2302 and #2304) | the 2.3 plan, phase 8, R3's deploy |
| a park's abandonment counted at its own decision, so a run of parks stops at `max_unaccepted_increments` (§24bp) | **shipped** | 2.3.0, PR #2295, issue #2294 |
| an increment rejected only for criteria the accepted application already meets is abandoned for a new proposal told which, not repaired (§24bq, row 16) | **shipped** | 2.3.0, PR #2319, issue #2315 |
| a successor's brief carries the increment's evaluation (frozen breaks, unmet criteria, routes not held, blocked judgements), not only its cycle's checks (§24br, rows 12, 13 and 16) | **shipped** | 2.3.0, PR #2375, issue #2318 |
| a late answer on a closed campaign re-materializes its stored digest, and an agent's late answer is recorded as an agent's | **shipped** | 2.3.1, PR #2389, issue #2305 |
| accepted increments' `prd_delta` text to the proposer | **shipped** with SIP-0113 §4.5 (SIP-0113 §10u, §10v): the accepted PRD folded by section, read through the promotion's own lookup, shown in its own asset | 2.4.0, PRs #2687 and #2688, issue #2677 |
| escalating a launch the cycle-create preflight refuses | **shipped** (§24ba) | 2.1.0, PR #2052, issue #1971 |
| re-hearing an ended cycle between restarts | **shipped**: the campaign sweep re-hears on its interval, and a cycle is heard by one hearer at a time | 2.1.0, PR #2038, issue #1972 (§24as) |
| a Next.js render profile (a route-declaring Next.js increment is always `blocked_unverified`) | **shipped** (§24bd) | 2.1.0, PR #2059, issue #1973 |
| an increment that needs packaging changed | **unplaced, deliberately** (§24as): re-placed on evidence | §24y |
| whether an increment's build skips the builder tail | **dropped as a question** (§24as): answered when a campaign raises it | §24ab |
| the quiet-box check reading GPU compute processes | **unplaced, deliberately** (§24as): until the owner grants the runtime-api the GPU (a `docker-compose.yml` change) | §24l, §24ai, §24an |
| the acquire race window; re-attach with the process up; a task re-asked after an agent restart | **dropped**: not built, by design (recorded) | §24ai, §24am, §24ao |
| §24b–§24i, marked "implementer's reading, not yet ruled" | **shipped**, ratified as written (§24as) | v2.0.0 |
| a return carries its classification, or `unclassified` with why (the 2.2 plan's D2) | **shipped** (§24bi) | 2.2.0, PR #2132 |
| proposal-run retries bound failed proposal cycles in a row, and the failure past them pauses (§24bn) | **shipped** | 2.3.0, PR #2245, issue #2231 |
| a campaign declares its stack, and every cycle it launches carries it (§24bs) | **shipped** | 2.4.0, PR #2446, issue #2443 |
| a fresh proposal is shown each proposal its campaign never approved, with the ruling's reason (§24bu) | **shipped** | 2.4.0, PR #2598, issue #2593 |
| a Campaign on a repository-backed Project, point 1: calibration as a record, not a cycle (§24bv point 1, §24cc) | **shipped** | 2.5.0, PR #2738 |
| a Campaign on a repository-backed Project, point 2: the accepted tree is a campaign branch, an increment promoted onto it from its own capture (§24bv point 2, §24cd, §24ce) | **shipped** | 2.5.0, PR #2740 |
| a Campaign on a repository-backed Project, point 2's launcher handoff: the head read at drain and handed to cycle creation, and a repository-backed increment's intent binding no tree (§24cd point 1; SIP-0112 H.9) | **shipped** | 2.5.0, PR #2763 |
| a Campaign on a repository-backed Project, point 3's regression baseline: an increment on a head compared with the verification that made it, the record's commit with its inherited baseline; with §24ci (a)'s pytest exception-class reader and the product-runner discrimination rule (§24bv point 3, §24ci (a); SIP-0112 H.10) | **shipped** | 2.5.0, PR #2764 |
| a Campaign on a repository-backed Project, point 5: the proposal's input read at the head, the change request on a product with each criterion's test placed under the product's runners, the scope's reading there, the continuation's change request, and the creation rules (§24bv point 5, §24cj; SIP-0112 H.4, H.11) | **shipped** | 2.5.0, PR #2771 |
| a Campaign on a repository-backed Project, point 6: acceptance on the product's runner, runtime-side in the sandbox at the increment's delivery, each overlay a revision of its tree, in place of `qa.evaluate_increment`, which a branch increment's plan no longer carries (§24cd point 6, §24cl; its criterion files are §24cj's placed ones; SIP-0112 H.11's drop) | **shipped**, except route rendering on a product (§24cl item 6, §24co's row) | 2.5.0, PR #2774 |
| a Campaign on a repository-backed Project, point 4: upstream moving. The branch is rebased onto the commit and revision its Project reconciled, its head verified by the product's checks, a pending repair or retry superseded as `upstream_moved` (D10), the conflict and regression escalations, and the ref's follow (§24bv point 4, §24cd points 2–5, §24cm) | **shipped**, with §24cd point 5's frozen bundles at the rebase run by #2774's `frozen_on_runner` (§24cm item 11) | 2.5.0, PR #2770 |
| a Campaign on a repository-backed Project, the supervisor's review-request push: the campaign branch pushed as `squadops/<campaign>` with the supervisor's own token, leased on the last push and refused over a branch someone else moved (§24ci (b), §24cn) | **shipped** | 2.5.0, PR #2772 |
| a Campaign on a repository-backed Project, point 3's route rendering on a product: the profile's client routes rendered on the candidate, started in the sandbox from contract 7's start, read by the evaluator image's Chromium and judged by their views' root anchors (§24bv point 3, §24cl item 6, §24co; SIP-0102 §11k) | **shipped** | 2.5.0, PR #2777 |
| a page criterion on a repository-backed change request names its view's anchor (required on a page the change adds, refused on one the profile judges), and a route the request adds is judged by it, so it can hold; an added page whose path needs a seed is refused, and a dev repair keeps the anchors (§24co item 11's remainder, §24cp items 1–5) | **shipped** | 2.5.0, PR #2780, closes #2779 |
| a seed for a page a repository-backed change request adds whose path has a parameter, so it can be read instead of refused (§24cp item 5) | **unplaced**, deliberately: for the supervisor to place | #2781 |
| the anchors of pages earlier increments added, carried into a repository-backed proposal's input, so the rails and the renderer check an added page's anchor against them (§24cp, not built) | **unplaced**, deliberately: for the supervisor to place | #2783 |
| a Campaign on a repository-backed Project, read live: a repository-backed Campaign's increments judged at delivery and promoted onto its branch end to end, on a product made from a blueprint (`z_shelfnote`, IR-7) and one with its own layout (`z_continuum`), as the 2.5 plan's Track A demonstrations (§24bv, §24cl, §24co) | **placed** | 2.5.0, #2619 |
| a vitest test-id reader, so a vitest-only criterion can be read as discriminating (§24ci (a)) | **shipped**: from vitest's default reporter, as the product's own command prints it (SIP-0112 H.10) | 2.5.0, PR #2764, closes #2757 |
| a Campaign cycle held on its instruction bindings escalates as `binding_hold`, released by re-supply and never parked (§24bw; SIP-0110 §A.3.6) | **shipped** | 2.4.0, PR #2628 (#2178's Campaign half) |

**What closes this SIP:** Its 2.1.0 rows closing, #1710's remainder ruled, and #1708's remainder shipped in 2.2.0 or ruled out of scope. §24at, the consolidated status at the v2.0.0 cut, replaces the 2.0 plan's §5a as the permanent record. Promotion follows at the sweep after the last placed row closes.

## 1. Summary

A **Campaign** is an objective envelope over a sequence of bounded cycles that **evolves one app**. It
opens with a calibration cycle. Each later cycle is an **increment cycle**:
- its first run is the strategy role's **proposal**, a typed change request against the accepted app;
- a **gate** follows, where the supervisor approves, returns it for revision, or rejects it;
- an approved proposal is framed as a delta, built and verified;
- the increment is accepted only if every earlier increment still passes.

After each cycle, a pure, ordered continuation decision chooses what comes next. Every control
operation is written first to a transactional control log, so the campaign survives a restart with no
lost ruling and no duplicate launch.

---

## 2. Motivation

SquadOps executes a bounded cycle well: one PRD, one squad, one tree built from nothing, one verdict. It
cannot **carry an app** across cycles. No cycle starts from what the last one delivered, and no record
says which increments an app has received, why each was chosen, or whether the earlier ones still work.
The owner's 2.0 direction is a campaign of about ten hours in which the squad evolves group_run cycle by
cycle (`docs/plans/post-1-8-2-roadmap-reconciliation.md`).

---

## 3. The loops, and who owns what

| loop | cadence | owner | what it may do |
|---|---|---|---|
| **squad execution** | within a cycle | the squad (SquadOps) | plan, build, verify, repair, inside the cycle's bounds |
| **campaign** | per cycle | SquadOps's continuation decision; **every increment ruled on at its gate by the supervisor** | continue, repair, retry, escalate, pause, stop. Increment content is authored only by the strategy role |
| **framework optimization** | across campaigns | the outer loop: the owner and the Nostromo crew | observe, hypothesize, propose. **Change the framework only between campaigns, and only with the owner's approval** |

**The owner's rulings of 2026-10-01:**
1. **The strategy role proposes on a short leash:** the supervisor rules on every proposal, and watches
   how increments are proposed and implemented.
2. **The crew may run inference on the Spark between squad cycles and between campaigns, never while
   the squad runs one** (the crew operating model's §36, `backspring-labs/nostromo`).
3. **The continuation policy stays in SquadOps.** The supervisor holds escalation and abort.
4. **The proposal runs as the first run of the increment cycle, with the ruling a gate after it.**
   **A control log is the authority for control operations. The change request is typed.** (Ruled on the
   crew's review, the same day.)

---

## 4. Decision

1. A **Campaign** references a project, and declares an **objective** with an **allowed change scope**,
   a **CampaignPolicy**, and a **supervisor**. `Cycle` gains a nullable `campaign_id` and a `kind`
   (`calibration | increment | repair | retry`).
2. Every campaign **opens with a calibration cycle** (§11).
3. Every later cycle is an **increment cycle** (§7.3) running workloads in this order:
   - `proposal`;
   - the gate `increment_ruling`;
   - `framing`, delta-scoped;
   - the gate `progress_plan_review`;
   - `implementation`.

   Repair and retry cycles reuse an approved change request and its baseline (§10).
4. The **change request is typed** (§7.2), and evaluation runs on **the evaluator trees**: accepted,
   candidate, the baseline-evaluator overlay, and the candidate-verifier overlay (§7.4).
5. An increment is accepted only under **accumulated acceptance**, with **executable carried
   criteria** and **one discriminating test per new criterion** (§8).
6. After every campaign cycle reaches `CycleCompletion`, an **ordered, pure continuation decision**
   yields the next action (§10).
7. **One owner of the Spark at a time** (§9.3). Every launch is gated on it, and on a quiet box.
8. **A transactional control log is the authority** for every control operation. Security audit and
   events are projections of it (§13).
9. **Evidence is append-time and immutable;** the package is a close-time projection (§14).

---

## 5. Scope and non-goals

**In:** everything §4 lists.

**Not in this SIP:**
- the squad improving its own framework, which is the outer loop's (the 09-28 direction);
- loosening the leash: no auto-approval tier in 2.0;
- `fork`, meaning concurrent sibling cycles (§12);
- isolated replay for the supervisor (SIP-0101 exposure);
- holding agents across cycles, unbounded cycles, a new runtime mode;
- Cross-Cycle Memory (v2.2; its revision 3 is #1805);
- Capability-Backed Agents.

---

## 6. Position in the hierarchy

```
Project
  └── Campaign                        objective envelope: one app, evolved across cycles
        ├── calibration Cycle         the fixed PRD from scratch (§11)
        └── increment Cycle           (§7.3)
              ├── Run: proposal       strategy.propose_increment → typed change request
              ├── Gate: increment_ruling     the supervisor's ruling (§9.2)
              ├── Run: framing        delta-scoped
              ├── Gate: progress_plan_review
              └── Run: implementation
```

| layer | owns | SIP |
|---|---|---|
| task, run | one execution attempt | SIP-0064 |
| intra-run loop | correction within a run | SIP-0086, SIP-0079 |
| multi-run cycle | runs and gates within one cycle | SIP-0083, SIP-0064 |
| **campaign** | **the app across cycles: increments, acceptance, continuation, the box** | **this SIP** |

---

## 7. The increment cycle (#1705)

### 7.1 The baseline

An increment cycle's baseline is the **accepted tree** of the campaign's last accepted increment, or of
the calibration cycle for the first. It is identified by its SIP-0107 §20 verified identity and is
**immutable**: no evaluator, repair or later cycle writes to it. Promotion to a new accepted tree is a
single transition (§12a).

### 7.2 The typed change request

The proposal's output, and the only authored input to the rest of the cycle:

| field | type | read by |
|---|---|---|
| `proposal_id`, `version`, `content_hash` | identity | the gate's binding (§9.2), the control log |
| `baseline_tree` | the accepted tree's identity | the gate's binding, the evaluators |
| `kind` | `feature \| fix \| refactor` | §8.2 (refactors add no discriminating tests) |
| `prd_delta` | added, modified or retired requirement sections, each with an id | delta framing (§7.3) |
| `manifest_delta` | typed operations: `add`, `modify` or `remove` on entities (fields with types), endpoints (method, path, request, response, success status, errors), client routes (path, view, test ids), error codes | the manifest gates, applied to the manifest the delta produces; the footprint |
| `criteria` | each with an id, a statement, its **public surface** (an endpoint, or a client route) and the observable it asserts | §8.2, §8.1 |
| `must_not_break` | earlier criteria ids this increment must keep passing (by default, all of them) | §8.1 |
| `retires` | earlier criteria ids the increment retires, each with a reason. A scope change, so the supervisor rules on it explicitly | §8.1 |
| `replaces_verifiers` | earlier criteria whose frozen verifier bundle this increment replaces, each with a reason. A scope change, ruled explicitly; the old bundle is retired | §8.1 |
| `footprint` | the files the delta may touch, derived by the stack's scaffold map from `manifest_delta`, never authored | the plan validator (§7.3), SIP-0107 write grants |

A change request whose `manifest_delta` the SIP-0103 gates refuse never reaches the gate. It is a
proposal-run failure, and the run's own retry applies (§9.1).

### 7.3 The increment cycle's workloads

| workload | tasks | skipped from a greenfield framing, and why |
|---|---|---|
| `proposal` | `strategy.propose_increment` (new `TaskType`) | — |
| gate `increment_ruling` | the supervisor (§9.2) | — |
| `framing` | `development.design_plan`, `qa.define_test_strategy`, `governance.prepare_plan_authoring_brief`, the plan proposers, `governance.merge_plan`, `governance.review_plan`. Each is scoped to the change request: design and plan cover only the footprint, and the test strategy covers only the new criteria | `data.research_context` and `strategy.frame_objective`, because the approved change request is the framed objective. `development.author_manifest`, because the manifest is the baseline's, plus the typed delta, re-checked by the manifest gates |
| gate `progress_plan_review` | as today | — |
| `implementation` | as today, editing through SIP-0107 within the footprint's write grants | — |

**The plan validator refuses a task whose writes fall outside the footprint.** No framing task
re-authors an accepted artifact.

### 7.4 The evaluator trees

| tree | content | identity | who writes it |
|---|---|---|---|
| **accepted** | the last accepted increment's tree | SIP-0107 §20 verified identity | promotion only (§12a) |
| **candidate** | the accepted tree plus this increment's applied patches | workspace revision id (#734) | the increment's implementation and correction runs |
| **baseline-evaluator overlay** | the accepted tree's **product code**, plus the candidate's test files, test configuration and test-only dependencies. **Never the candidate's product code** | the accepted identity plus a hash of the overlaid test set | built per evaluation; never persisted as a tree |
| **candidate-verifier overlay** | the candidate's **product code**, plus **one frozen criterion's verifier bundle** (§8.1): its test, its fixture snapshot, its configuration and its test-only dependencies. **Never the candidate's own test files** | the candidate identity plus the bundle's content address | built per frozen criterion, per evaluation; never persisted |

**Test identity.** A test is identified by its file path and its name, as the stack's runner reports
them. Against the accepted tree's test ids, each candidate test is `new`, `modified` (same id, changed
body) or `renamed` (same body hash, new id). A test file the candidate deletes is a `retires` entry, or a
must-not-break violation.

### 7.5 What a failed increment leaves behind

Nothing on the accepted tree. The candidate tree is kept as evidence. The next cycle (repair, retry or a
new proposal) starts from the same accepted identity, and there is no partial merge.

---

## 8. Acceptance

### 8.1 Accumulated acceptance, with executable carried criteria (#1707)

**Each criterion pins an immutable, content-addressed verifier bundle.** At acceptance, the bundle is
frozen as:
- **its own test file,** `<the stack's test dir>/criteria/<criterion_id>.test.<ext>`, which the scaffold
  emits as a fill slot (SIP-0104);
- **a snapshot of the fixtures and helpers it requires,** resolved from its imports at freeze time;
- **its test configuration and test-only dependency lock.**

The bundle's identity is the hash of that content. Storage deduplicates by content, so bundles that share
a fixture share its bytes, but **no bundle reads another's**.

**Accumulated acceptance executes the candidate's product code under each frozen bundle,** through the
**candidate-verifier overlay** (§7.4), by the bundle's frozen invocation. It never runs the candidate's
own copies of the test files.
- **Each criterion is bound only to its own bundle.** A fixture added or changed for a later criterion
  enters only that criterion's bundle, so no other criterion's identity moves.
- **Frozen bundle files are outside every later increment's footprint.** A change request may replace
  a criterion's bundle only through **`replaces_verifiers`**, an explicit ruled entry like `retires`.
  The old bundle is retired and the new one frozen. A candidate write to a frozen bundle's files
  without it is refused by the plan validator.
- **A missing or unreadable bundle is `blocked_unverified`,** never a pass (SIP-0096).

### 8.2 Baseline discrimination: one test per new criterion

For a `feature` or `fix` increment, each criterion it adds needs **at least one test, in its
criterion-owned file (§8.1), that fails on the baseline-evaluator overlay for the intended reason, and
passes on the candidate.** Other new tests,
preservation tests among them, may pass on both.
- **"For the intended reason" means an assertion failure on the criterion's public surface:** a status,
  a response body, a rendered element. On the overlay, a missing endpoint answering 404 or 405 is
  behavioural, and so is a missing view rendering without its declared test ids.
- **These are not behavioural evidence:** a collection or import error, a missing module, an
  unavailable fixture, a failed setup. New behaviour is tested through the running app's public surface,
  never by importing a module that exists only in the candidate. SIP-0104's Phase 2 assertion-shape
  classifier draws the line.
- **A criterion without a discriminating test is not met.** Refactor increments add no criteria; their
  guards are the frozen criteria (§8.1).
- **What this check is:** the campaign's form of demonstrated discrimination
  (`SIP-Verification-Yield.md` §7; `SIP-Test-First-Verification.md` Phase 1). The baseline does the job
  that Test-First Verification's contract-conforming stub does for a greenfield cycle.

### 8.3 Every declared route renders (#1796)

Every client route in the accumulated manifest renders its view's declared test ids in a browser, on
the candidate tree.

### 8.4 The evaluator seam table (normative)

| evaluator | tree it sees | authoritative input | outcome when input is missing | durable output | on restart |
|---|---|---|---|---|---|
| manifest gates on the delta | the baseline's manifest plus `manifest_delta` | the change request | the proposal run fails, and its retry applies | the gate result on the proposal run | the proposal run re-runs |
| emission typed checks | the role's container: candidate workspace plus its emission | the plan, the manifest | `blocked_unverified` | typed-check evaluation artifacts | as today |
| correction verifier | candidate workspace plus the failed task's artifacts plus the patch | the failure evidence | `blocked_unverified` | the patch verification | as today |
| baseline discrimination (§8.2) | the baseline-evaluator overlay | the change request's criteria; the candidate's test ids | the criterion is not met | a per-criterion, per-test result keyed by (increment, test id, overlay identity) | recomputed: the overlay is derived, and the result is idempotent by key |
| accumulated acceptance (§8.1) | **the candidate-verifier overlay**, one per frozen criterion | the frozen bundle and its invocation | `blocked_unverified` (a missing or unreadable bundle included) | a per-criterion result keyed by (increment, criterion id, candidate identity, bundle address) | recomputed, idempotent by key |
| route rendering (§8.3) | the candidate tree, booted | the accumulated manifest's routes | `blocked_unverified` | a per-route result | recomputed |
| promotion (§12a) | none: reads the results above | every result recorded and passing | no promotion | the new accepted identity, in one control-log transition | idempotent: the transition is keyed by (campaign, increment, candidate identity) |
| failure records (§14) | the cycle's outcome and evidence | `failure_events(outcome, evidence)`, the one producer | an `unaskable` record naming the input | one record per event, then the attribution computed from them, in one completion transaction | keyed by (cycle, event index); re-writing is a no-op |
| the launcher (§12b) | the launch intents | a pending intent | nothing launches | the cycle, with `source_launch_id` | re-drains; idempotent by `source_launch_id` |
| quiet-box check (§9.3) | the box: engines and GPU processes | the active deploy record (#1720) | not quiet: the launch is refused | a launch-blocked record | re-evaluated at the next attempt |
| continuation decision (§10) | none: pure | the cycle's `CycleAssessment`, the campaign record, policy counters | not computed until the cycle is terminal | the decision row, in the control log | keyed by cycle id; recomputing returns the recorded decision |

---

## 9. The proposal, the ruling, and the box

### 9.1 The proposal run (#1706)

The `proposal` workload is a run like any other:
- **One task:** `strategy.propose_increment`, the strategy role.
- **Recruited by the SIP-0089 coordinator** at the run's start (`owner_ref = proposal run id`), and
  released at its end. The campaign holds no agent (§12).
- **A request profile of its own** (`campaign-proposal`), with its own token budget.
- **Inputs, persisted as the run's inputs:**
  - the objective and its allowed scope;
  - the accepted tree's identity, manifest and frozen criteria;
  - the campaign's ledger;
  - the prior-cycle brief (§14);
  - the owner's backlog;
  - on a revision, the supervisor's note.
- **Output:** the typed change request (§7.2), persisted as the run's artifact, with its content hash.
- **Failure:** the run's ordinary retry (the run fails and is re-dispatched, up to the policy's proposal
  retry count). Then the cycle ends `proposal_failed`, which the continuation decision reads (§10).
- **Restart:** the run's ordinary recovery. It is a run.

**Rails:**
- an out-of-scope proposal (a `manifest_delta` or `footprint` outside the allowed scope) is refused by
  the run's validator, not trimmed;
- the analyzer's findings and qa's failures reach the strategy role as backlog;
- no other role proposes.

### 9.2 The increment gate and its ruling (#1801)

After the proposal run, the cycle stops at the gate `increment_ruling`. The supervisor rules through the
existing gate decision path. The values are the existing `GateDecisionValue`s
(`src/squadops/cycles/models.py:57-63`):

| ruling | `GateDecisionValue` | what follows |
|---|---|---|
| approve | `approved` | the `framing` workload runs |
| request revision | `returned_for_revision` | a new `proposal` run in the same cycle, with the supervisor's note (the #811 revision loop's shape); the new version is ruled on afresh |
| reject | `rejected` | the cycle ends `rejected_at_gate`; no build |
| — | `approved_with_refinements` | **not legal on this gate.** Refining would make the supervisor an author |

- **Every ruling binds** to the proposal's `proposal_id`, `version` and `content_hash`, and to
  `baseline_tree`. A ruling whose binding does not match the gate's current proposal and the campaign's
  accepted identity is **refused as stale**, and recorded.
- **Every ruling carries a reason and an idempotency key.** Using the same key with the same payload
  returns the recorded ruling. Using the same key with a different payload is **refused as a conflict.**
- **The bound.** A gate not ruled within the policy's ruling bound pauses the campaign
  (`awaiting_ruling`, §9.5). The defaults are **30 minutes for the crew** and **12 hours for the
  owner**, each declared in `CampaignPolicy`. The campaign never proceeds unapproved.
- **The owner rules through the same path,** and is the supervisor when no crew is assigned.

### 9.3 The box lease (#1802)

SquadOps records **one owner of the Spark at a time**: the squad or the supervisor.
- **The lease passes to the supervisor when the gate opens:** the proposal run has ended and no run of
  the cycle is in flight. It returns to the squad when the supervisor releases it, its models unloaded,
  or when it expires.
- **Every cycle launch and every run start on the box** (campaign, CLI or driver) refuses while the
  supervisor holds the lease.
- **Every launch also requires a quiet box.** The identity source is the **active deploy record**
  (#1720): its serving engines and their models. The check reads each declared engine's loaded-model
  listing, and the GPU's compute processes. The box is quiet when every loaded model is in the deploy
  record and every GPU compute process belongs to a declared engine. An engine that cannot be read
  counts as not quiet: the check fails closed.
- **A refused launch** puts the campaign in `launch_blocked`, with the refusal recorded. It is
  re-attempted at the policy's interval up to its count, and then escalates. Resumption is automatic
  when the check passes within the count; after escalation, only the owner resumes.
- **An expired lease** reverts to the squad only when the box is quiet. Otherwise the campaign escalates.
- SquadOps reads its own lease and the box. It never reads the crew's files.

### 9.4 The proposal ledger

One record per proposal version, appended as it happens (§14):
- the change request;
- the ruling, its reason, who ruled, and its binding;
- the cycle's outcome: verdict, correction rounds and their causes, framing re-rolls, each new
  criterion's discriminating-test result, and any frozen criterion broken;
- the supervisor's classification of what went wrong:
  - scope too large;
  - criteria not checkable;
  - a conflict with an earlier increment;
  - an ambiguous manifest delta;
  - **a sound proposal implemented badly**, which is not a feature-writing defect.

### 9.5 Limits (#1800)

| limit (`CampaignPolicy`) | when reached | resumes on |
|---|---|---|
| total cycles | `stop_failure` (exhausted) | — |
| elapsed time | pause | the owner |
| budget (tokens) | pause | the owner |
| repair cycles on one increment | the increment is abandoned; it counts as unaccepted | — |
| retry cycles on one increment | escalate | the owner |
| proposal-run retries (failed proposal cycles in a row, §24bn) | pause | the owner |
| revisions of one proposal | the proposal counts as rejected | — |
| rejected proposals in a row | pause | the owner |
| unaccepted increments (`max_unaccepted_increments`, the no-progress rule) | `stop_failure` | — |
| the ruling bound | pause (`awaiting_ruling`) | a ruling, or the owner |
| launch-blocked attempts | escalate | the owner |

**A pause caused by a limit resumes only on the owner's recorded word.** The supervisor rules on gates,
and cannot lift a limit.

---

## 10. The continuation decision (#1800)

**Promotion comes first.** An accepted increment is promoted in its own transition when its cycle
reaches `CycleCompletion` (§12a), before the decision runs. The decision then reads the new accepted
identity, and a pause never holds a promotion.

The decision is **pure** and runs **once per campaign cycle**, keyed by cycle id. It has three ordered
steps, and its full result is written in one control-log transition:

```
campaign_continuation_decision(campaign, cycle, latest) -> ContinuationDecision
    # campaign: objective, policy, counters, flags, accepted identity
    # cycle:    kind, terminal state, gate outcome
    # latest:   CycleAssessment (verdict; attribution.primary)
ContinuationDecision = (terminal | pending_action, guard)
```

**Step 1, terminal outcomes. The first match ends the campaign:**

| # | predicate | outcome |
|---|---|---|
| 1 | the campaign is aborted | `stop` (aborted) |
| 2 | `cycle.kind = calibration` and `latest.verdict ≠ accepted` | `stop_failure` (calibration) |
| 3 | `latest.verdict = accepted`, and the objective's measurement is met with this increment counted | `stop_success` |
| 4 | a stopping limit is reached (total cycles, no-progress) | `stop_failure` (that limit) |

**Step 2, the pending action. When no terminal outcome fired, the first match is the next action:**

| # | predicate | `pending_action` |
|---|---|---|
| 5 | `cycle.kind = calibration` (accepted) | `propose` |
| 6 | the cycle ended `rejected_at_gate` or `proposal_failed` | `propose` |
| 7 | `latest.verdict = accepted` | `propose` |
| 8 | `latest.verdict = blocked_unverified` and repair cycles remain for the increment | `repair` |
| 9 | `latest.verdict = blocked_unverified` | `escalate` |
| 10 | `latest.verdict = rejected`, `latest.attribution.primary = environment_or_infrastructure_failure`, and retry cycles remain | `retry` |
| 11 | `latest.verdict = rejected` and `latest.attribution.primary = environment_or_infrastructure_failure` (no retry cycles remain) | `escalate` |
| 12 | `latest.verdict = rejected` and repair cycles remain for the increment | `repair` |
| 13 | `latest.verdict = rejected` | `abandon_and_propose` (counts as unaccepted) |
| 14 | otherwise | `escalate` |

**Step 3, the guard. It applies only to guardable actions.** The pending actions are of two kinds:
- **guardable,** the actions the campaign would execute on its own: the cycle-launch actions
  (`propose`, `repair`, `retry`) and `abandon_and_propose`;
- **unguarded:** `escalate`.

For a guardable action: if a pausing limit is reached (elapsed time, budget, rejected proposals in a
row), `guard = paused (that limit)`; otherwise `guard = proceed`. **`escalate` has no guard.**

**The precedence, end to end:** terminal outcome (step 1), then escalation, then the pausing guard, then
the autonomous launch or abandonment. **Escalation wins over a simultaneous pausing limit**, so the owner
receives one ruling to make, never a pause holding an escalation.

**Execution. Control transitions are** `escalate`, `stop`, and the abandonment half of
`abandon_and_propose`.

**Only a cycle-launch action creates a launch intent** (§12b). The transition writes the pending action
and the guard together:
- **A launch action under `proceed`** becomes a launch intent in the same transaction.
- **`abandon_and_propose` under `proceed`** atomically records the abandonment, updates the unaccepted
  count, and writes the `propose` intent, in one transaction.
- **`escalate`** is unguarded. It moves the campaign directly to `escalated`, with no intent, and waits
  for the owner's recorded ruling. The ruling names the next action (propose, abandon, repair, retry,
  or stop), which executes at once, launch actions through an intent. **The pausing guard does not
  re-apply to an owner's ruling.** The ruling is the owner's word, and the owner's word is also what
  lifts a limit-caused pause.
- **Any guardable action under `paused`** is **held**, with no intent. **The owner's resume executes
  that same recorded action** by the same rules: a launch action becomes an intent in the resume's
  transition, and `abandon_and_propose` records its abandonment and its intent together. It never
  recomputes the decision.

**The rules that bind it:**
- **Success first** (row 3 before row 4).
- **`blocked_unverified` never yields `propose` from an unverified increment, and never
  `stop_success`.**
- **`stop_success` needs `latest.verdict = accepted`.**
- **No outcome launches directly.** Launches go only through launch intents (§12b).
- **No `wait` outcome.** A pending ruling is an open gate in the next cycle.

### 10a. Repair and retry cycles

A repair or retry **reuses exactly** the bound change request, its ruling, its baseline and its
footprint. **Any change of scope, baseline or content requires a new proposal run and ruling,** which
means a new increment cycle. The baseline cannot move between an increment's cycles: nothing is
promoted while an increment is unresolved.

| | `repair` | `retry` |
|---|---|---|
| **when** | the increment failed a check it can repair | the increment failed for a cause outside the work |
| **workloads** | `implementation` only, correction-focused, under the failed cycle's approved plan | `framing` (delta-scoped), the gate `progress_plan_review`, `implementation` |
| **the ruling** | the gate `increment_ruling` is **not run**. The bound ruling is reused by reference, and its binding re-checked: the same `proposal_id`, `version`, `content_hash` and `baseline_tree`. A mismatch refuses the cycle | the same |
| **the starting tree** | **the failed cycle's candidate content**, by its identity, re-applied onto the accepted tree | **the accepted tree**: a fresh candidate |
| **the footprint** | the bound change request's. A repair needing writes outside it is refused by the plan validator, and the repair cycle fails | the same |
| **the prior-cycle brief** | enters the implementation's correction context (#1692) | recorded, and shown to framing |
| **when the limit is reached** | **rejected and exhausted:** the increment is abandoned and a fresh proposal follows (row 13). **Unverified and exhausted:** the campaign escalates (row 9), and only the owner's recorded ruling selects the next action | the campaign escalates (row 11), and the owner's ruling selects the next action |
| **what else forces a fresh proposal** | any needed change of scope, baseline or content | the same |

---

## 11. The calibration cycle (#1709)

Every campaign opens with **the same PRD built from scratch** on the campaign's deploy, under a fixed
request profile. It is the **yardstick for greenfield behaviour**, and only rows 2 and 5 of §10 read its
verdict. It exercises no proposal, delta or accumulated acceptance; §11a is their yardstick.

### 11a. The brownfield reference scenario (#1804)

- **A fixed baseline:** a stored, accepted group_run tree.
- **A fixed typed change request.** Both are pinned by hash.
- **One increment cycle builds the fixed change request** (no gate: the request is pre-approved and
  recorded as such). Its record reports delta framing, scoped repair, accumulated acceptance and
  baseline discrimination separately.
- **The strategy role also runs a proposal** against the same baseline and objective. That proposal is
  recorded and **rated by the supervisor, not built**.

It runs in the fast lane between campaigns, and in a release's counted set.

---

## 12. The recruitment invariant

> **A campaign launches cycles; it never holds agents between them.**

Every run, the proposal run included, recruits through the SIP-0089 coordinator (per-run
`ambient→cycle`, `owner_ref = run_id`) and releases at its end. There is no campaign-scoped agent lease.
The box lease (§9.3) governs the hardware, not agents.
- **#288 is fixed** (1.3.1).
- **The continuation decision runs only after the ended cycle's participants are released.**
- **With `fork` deferred,** no two cycles of one campaign recruit at once.

### 12a. Recovery (#1803)

**Every control operation is a control-log transition** (§13): written in the same transaction as the
state change, and keyed. On restart, the campaign's state is the log's last committed transition.
Nothing is reconstructed from logs.

**Restart, by state:**

| state at restart | what resumes |
|---|---|
| calibrating, or running an increment (a run in flight) | the run's ordinary recovery; the campaign waits on the cycle |
| proposing | the proposal run's ordinary recovery |
| awaiting ruling (gate open) | the gate is open again; the lease's holder and expiry are as recorded |
| launch blocked | the next quiet-box attempt at the recorded interval |
| paused, or escalated | nothing, until the owner's recorded word |
| promotion in progress | promotion is one transition: either committed (the new identity) or not (the old) |
| a decision recorded with `guard = paused` | nothing launches; the held pending action waits for the owner's resume (§10) |
| a launch intent not yet `launched` | the launcher re-drains it; creation is idempotent by `source_launch_id` (§12b) |
| completed | nothing |

**The required outcomes, each verified by a fault-injected diagnostic:**

| event | required outcome |
|---|---|
| a restart in any state above | the table's resumption; **no ruling lost**, because a ruling is committed before it is acknowledged |
| a duplicate completion event for one cycle | **one** continuation decision, keyed by cycle id; never two cycles created |
| a crash on either side of cycle creation | **exactly one** cycle per launch intent (§12b) |
| a pause, then a resume | the recorded pending action executes once; nothing is recomputed (§10) |
| a repeated ruling | the recorded ruling; nothing new happens |
| a conflicting idempotency key | refused and recorded |
| interruption during accumulated acceptance or promotion | **no partial promotion**: the accepted identity changes only in the promotion transition, after every result is recorded |
| an abort | terminal: the running cycle is cancelled by the existing path; **no continuation follows**, whatever arrives after |
| a timeout or launch-blocked state | resumable exactly as §9.2 and §9.3 say |

### 12b. Exactly-once launch: the launch intent

The campaign's state lives behind `CampaignRegistryPort`. A launched cycle is created through
`CycleRegistryPort.create_cycle(cycle)` (`src/squadops/ports/cycles/cycle_registry.py:29`), which has no
transaction argument and no idempotency source. A crash between the two writes could lose a launch, or
duplicate it. So launches cross that boundary through an **outbox**:
- **The decision's transition** (or a resume's, or an escalation ruling's) writes a **launch intent**
  in the same transaction as its control-log row: `launch_id` (derived from the decision id, unique),
  the cycle to create, and its `kind` and inputs.
- **A launcher** drains pending intents and creates each cycle with `source_launch_id = launch_id`.
  `cycles.source_launch_id` is a new nullable column with a **uniqueness constraint**. **Cycle creation
  is idempotent by it**: `CycleRegistryPort` gains `create_cycle_for_launch(cycle, launch_id)`, which
  returns the existing cycle when one carries that id.
- **The launcher then marks the intent `launched`,** with the cycle id, in a control-log transition.
- **On restart**, the launcher re-drains every intent that is not `launched`. The uniqueness constraint
  makes a re-drain create nothing twice.
- **Fault tests inject a crash on both sides of the boundary:**
  - after the intent commits, before the cycle is created;
  - after the cycle is created, before the intent is marked;
  - two launchers draining the same intent.

  Each must end with exactly one cycle per intent.

---

## 13. The supervision interface and the control log (#1799, #1801)

**The control log is the authority.** It is one append-only table in the campaign registry. Each row
holds:
- operation, actor, actor role, reason, target;
- idempotency key, binding, outcome;
- prior state and next state;
- committed at.

It is **written in the same transaction as the state change it records.** A control operation is
acknowledged only after its row commits.

**Projections, not authorities:**
- **Security audit:** each row is projected to `AuditPort`. That port is fail-open by contract
  (`src/squadops/ports/audit.py:16-17`), which is acceptable because the control log, not the
  projection, carries completeness. `AuditEvent`'s missing fields (role, reason, idempotency key) travel
  in its metadata.
- **Events:** campaign transitions as cycle events (SIP-0077 taxonomy, with its parity tests). The API's
  reads of the control log are authoritative after a missed event.

**The surface:**

| need | where |
|---|---|
| create, inspect, pause, resume, abort; read the ledger and the control log | `/api/v1/campaigns` and `squadops campaigns …` |
| rule at the increment gate | the existing gate decision path, with the binding and the idempotency key |
| acquire and release the box lease | `/api/v1/campaigns/{id}/lease` |
| identity | a supervisor role in Keycloak (SIP-0062): campaign controls and reads only |

---

## 14. Evidence (#1710, #1692)

**Append-time records, immutable once written:**
- the control log (§13);
- the proposal ledger (§9.4);
- each cycle's records and assessment;
- each evaluator's durable output (§8.4);
- **one failure record per failure, from one producer.** Today `CycleEvidence`
  (`src/squadops/cycles/cycle_assessment.py:180`) carries no failure events: `_completed()` and
  `_failed_run()` (`cycle_assessment.py:620`, `:654`) build `FailureEvent`s transiently while composing
  the terminal attribution.
  - **The producer:** those constructions are extracted into **one deterministic function**,
    `failure_events(outcome, evidence) -> tuple[FailureEvent, ...]`. It takes the cycle's
    `CycleOutcome` because the completed-cycle events come from `outcome.failed` and
    `outcome.unverified` (`cycle_assessment.py:618-640`), which are not fields of `CycleEvidence`. The
    terminal run is the one `assess()` selects.
  - **One completion transaction, in this order:**
    1. derive the events and the `unaskable` records, and persist them, each with its `FailureEvent`,
       its class by `compose()` (`src/squadops/cycles/failure_attribution.py:446`), the registry
       version, and the campaign, cycle, increment and event index;
    2. compute the assessment's attribution **from that exact persisted set**, and persist the
       assessment.
  - **Campaign evidence reads the persisted records. No consumer re-derives the events.**
  - **An input the attribution could not read** (`AttributionReading.unrecorded`) is persisted as a
    record in state `unaskable`, naming the input. It is never silently absent.
  Cross-Cycle Memory (v2.2, #1805) mines these records for recurrence, with no parallel taxonomy.

**The close-time package** is a **projection** of those records: materialized at close, idempotently,
from the records alone. A crash during close re-runs the projection. A reader without the producing
deploy can act on it.

**The morning digest** is rendered from the package.

**The prior-cycle brief:** a repair or retry cycle's proposal-free first input. It is authored by the
framework from the prior cycle's records, never recalled.

---

## 15. Domain model (shapes)

Frozen dataclasses beside `Cycle` and `Run`:
- `Campaign`;
- `CampaignObjective` (statement, allowed scope, measurement);
- `CampaignPolicy`, holding §9.5's limits, the ruling bounds, the lease expiry, the launch-blocked
  interval and count, the calibration profile and the proposal profile;
- `ChangeRequest`, typed as §7.2;
- `IncrementRuling`, the gate decision plus its binding, reason and idempotency key;
- `BoxLease`;
- `ControlLogEntry`;
- `LedgerEntry`;
- `FrozenCriterion`;
- `FailureRecord`;
- `ContinuationDecision`: a terminal outcome, or a pending action with its guard (§10);
- `LaunchIntent`: `launch_id`, the cycle to create, its state (`pending | launched`) and its cycle id;
- `VerifierBundle`: content-addressed. The criterion's own test file, its fixture snapshot, its
  configuration and dependency lock, and its invocation (§8.1).

---

## 16. Persistence

`CampaignRegistryPort`, beside `CycleRegistryPort`, with memory and Postgres adapters. Tables:
- `campaigns`;
- `campaign_control_log`;
- `campaign_ledger`;
- `campaign_frozen_criteria`;
- `campaign_box_lease`;
- `campaign_launch_intents`;
- `campaign_verifier_bundles`, content-addressed;
- `cycles.campaign_id` and `cycles.kind`, both nullable, and `cycles.source_launch_id`, nullable and
  **unique**.

`cycle_failure_records` belong to the cycle, not the campaign: every cycle writes them at completion
(§14), with campaign ids when the cycle has them.

The next free migration number is used.

---

## 17. Lifecycle

```
draft → calibrating → at_proposal → awaiting_ruling ─approve→ building → evaluating ─┬→ promoting → at_proposal
                          ↑     ←returned_for_revision─┘                              ├→ repairing / retrying
                          └─────────── rejected_at_gate / proposal_failed ─────────────┘
any state → launch_blocked → (quiet) resumes | (count exhausted) escalated
any state → paused (limit | owner) → owner resumes
any state → escalated → owner resumes or stops
any state → completed (success | failure | aborted | exhausted)
```

Every transition is a control-log row with its cause. A `paused` campaign holds the decision's pending
action, and its resume executes that action. `cancelled` derives `CANCELLED`, as on `Cycle`.

---

## 18. Implementation order (dependency-ordered)

| step | delivers | what it proves before the next starts |
|---|---|---|
| 1 | the domain model, the transactional control log, and the launch outbox with idempotent cycle creation (#1799) | a control operation commits atomically with its state change; an idempotency conflict is refused; a restart reads state from the log; a crash on either side of cycle creation leaves exactly one cycle |
| 1a | `failure_events(outcome, evidence)` extracted as the one producer; the events persisted, then attribution computed from them, in one completion transaction (#1710) | behaviour-neutral: backfilling every stored cycle's records with `failure_events(outcome, evidence)` and recomputing its attribution from them leaves it unchanged |
| 2 | the proposal run and the typed change request (#1706) | the run recruits and releases like any run; out-of-scope proposals are refused; the delta passes the manifest gates or the run fails |
| 3 | the evaluator trees, and content-addressed verifier bundles (#1806) | the accepted tree is immutable; the baseline overlay holds no candidate product code; the candidate-verifier overlay holds no candidate test files; adding a criterion changes no other criterion's bundle |
| 4 | accumulated acceptance and baseline discrimination (#1707, #1796) | frozen criteria execute on the candidate; a criterion without a discriminating test is not met; an import error is not discrimination |
| 5 | the increment gate, the binding, the box lease, the continuation decision with its held pending action, and repair and retry cycles (#1801, #1802, #1800, #1705) | stale and conflicting rulings are refused; every launch path honours the lease; each row is reachable with precedence as written; a pause and resume executes the held action once; repair and retry reuse exactly the bound request |
| 6 | the audit and event projections | each control-log row projects; a failed projection loses no control record |
| 7 | the calibration cycle, the reference scenario, the evidence package and digest (#1709, #1804, #1710) | the package materializes from records alone, idempotently |
| 8 | the recovery diagnostics (#1803) | every row of §12a holds under its injected fault |
| then | the shakeout campaign, the pre-registration, the counted set (the plan's §6) | — |

---

## 19. Acceptance criteria

**Compatibility, as named observable assertions** for a cycle without a campaign:
- its workload sequence is its profile's, with no `proposal` workload and no `increment_ruling` gate;
- its records, assessment and evidence are unchanged;
- its API responses gain only the nullable `campaign_id` and `kind`;
- **the one deliberate change:** its launch is refused while a supervisor holds the box lease, or the
  box is not quiet.

**The campaign:**
1. Survives a restart in every state of §12a's table, resuming as the table says.
2. Opens with its calibration cycle. A rejected calibration stops it before any increment.
3. **Only the strategy role authors a change request.** A ruling of `approved_with_refinements` on the
   increment gate is refused, and no API writes a change request but the proposal run.
4. **An out-of-scope proposal is refused** by the proposal run's validator.
5. **No increment builds without a ruling bound to its current proposal version and accepted
   identity.** A stale ruling is refused; a conflicting idempotency key is refused; a repeated ruling
   changes nothing.
6. Each criterion a feature or fix adds has a test that fails on the overlay for the intended reason
   and passes on the candidate. A criterion without one is not met. An import or setup failure is not
   discrimination.
7. **Frozen criteria execute on the candidate.** A changed frozen test file without a `retires` entry
   blocks acceptance.
8. **The accepted identity is immutable,** and changes only by the promotion transition. An interrupted
   promotion leaves the previous identity.
9. **Every launch path honours the box lease and the quiet-box check.** A launch-blocked campaign
   resumes when the box is quiet, and escalates after its count.
10. Each limit of §9.5 takes its action. A limit-caused pause resumes only on the owner's word.
11. **The no-progress rule stops a campaign** whose proposals stop producing accepted increments.
12. Each row of §10's three steps is reached by a crafted input, with the precedence as written. The
    function is pure, which an architecture test asserts.
12a. **Pause and resume:** for an accepted increment, a rejected increment, a `proposal_failed` cycle, a
     `repair` and a `retry`, a pausing limit holds the pending action, and the owner's resume executes
     that same action exactly once, with no recomputation.
12b. **Repair and retry** reuse exactly the bound change request, ruling, baseline and footprint, start
     from the trees §10a names, and refuse a cycle whose binding no longer matches.
12c. **Exactly-once launch:** with a crash injected on each side of cycle creation, and with two
     launchers, each launch intent yields exactly one cycle.
12d. **Failure records:** one producer, `failure_events(outcome, evidence)`, and one completion
     transaction that persists the events before computing the attribution from them. Backfilled
     against every stored cycle, the recomputed attribution equals the stored one, and an unreadable
     input is an `unaskable` record.
12e. **Verifier bundles:** a frozen criterion executes the candidate's product code under its own bundle.
     Adding a criterion that needs a changed fixture leaves the earlier criterion's bundle unchanged. A
     write to a frozen bundle's files without `replaces_verifiers` is refused, and a missing bundle is
     `blocked_unverified`.
12f. **Only launch actions create intents:** `escalate` and `stop` never do, and `abandon_and_propose`
     records the abandonment and its intent in one transaction, both under `proceed` and on resume.
12g. **Escalation wins over a simultaneous pausing limit:** a cycle whose pending action is `escalate`
     while a pausing limit is reached ends in `escalated`, never `paused`, and the owner makes one ruling.
     That ruling's action executes without the pausing guard re-applying.
13. **The evidence package is usable without the producing deploy:** materialized from records alone,
    and re-materialized identically after a crash at close.
14. The reference scenario reports each brownfield mechanism separately, with the proposal rated.
15. A two-increment campaign on a live stack.

---

## 20. Risks

- **The leash becomes a bottleneck.** *Mitigation:* the ruling bounds, the pause, the owner as fallback.
  Stalling is the safe failure.
- **The overlay misjudges discrimination.** A test depends on candidate product code through a helper.
  *Mitigation:* the overlay excludes candidate product code by construction; an import of it is
  classified as non-behavioural, not as a pass.
- **Frozen criteria become brittle** as the app evolves. *Mitigation:* `retires`, ruled explicitly; the
  ledger records every retirement.
- **The control log is a hot path.** *Mitigation:* one row per control operation, not per task.
- **A brownfield framing re-authors the app.** *Mitigation:* §7.3's skipped tasks, and the footprint
  enforced by the plan validator.

---

## 21. Relationships

- **Consumes, unchanged:**
  - `CycleCompletion`;
  - `CycleAssessment` and the attribution registry;
  - `GateDecisionValue` and the gate decision path;
  - SIP-0107;
  - SIP-0103's gates;
  - SIP-0089 recruitment;
  - the cancel path;
  - deploy records (#1720).
- **Enables** the outer loop (#1711) and the crew's supervision.

---

## 22. Testing

- **The continuation table:** one crafted input per row; overlapping inputs resolve by precedence;
  purity.
- **The control log:** atomic commit with the state; conflicts refused; restart from the log.
- **The gate:** stale, conflicting and repeated rulings; `approved_with_refinements` refused.
- **The trees:** overlay contents; test identity across new, modified and renamed tests; accepted-tree
  immutability.
- **Wiring, entering at `CycleCompletion` with stored two-increment records:** frozen criteria reach
  the verdict.
- **The lease and the quiet box:** each launch path; fail-closed on an unreadable engine; expiry.
- **Recovery:** one fault-injected diagnostic per row of §12a's required outcomes, the launch boundary
  included (§12b).
- **Pause and resume:** the five cases of criterion 12a.
- **The failure producer:** recomputation from the persisted records against every stored cycle's
  attribution.
- **E2E:** criterion 15 on a live stack.

---

## 23. Open questions

**Answered in revision 3:**
1. Which framing tasks run on a brownfield cycle: §7.3.
2. The delta's form: typed, §7.2.
3. The ruling bound's defaults: 30 minutes for the crew and 12 hours for the owner, declared in
   `CampaignPolicy` (§9.2).
4. The quiet-box identity source: the active deploy record's engines and models, failing closed
   (§9.3).

**Remaining, none architectural:** the limits' default values, set at the pre-registration from the
shakeout.

---

## 24. Post-acceptance amendments

### 24a. §14's failure records, as built (2026-10-02, #1813; ruled by the owner)

Step 1a's second part (#1710) persists a cycle's failure records at its ending. It settled four
points §14 left open, or stated otherwise. **The owner ruled all four as recommended, on
2026-10-02.**

1. **The persisted events are part of `CycleEvidence`** (`persisted_failure_events`), not a new argument
   to `assess()`.
   - **What changed:** §14 says the attribution is computed "from that exact persisted set" and does
     not say how the set reaches the assessment. It reaches it as evidence.
   - **The evidence:** `assess()` is pinned to `(outcome, evidence, *, assessor)` by
     `test_assess_reads_two_arguments_and_a_declared_assessor`, because the evidence identity must
     vouch for everything the assessment reads (SIP-0108 §4.1(a)).
   - **The identity rule:** the field is omitted from the identity's canonical form when it is `None`.
     Every identity already recorded, in the benchmark registry and in the verification-set records,
     is therefore unchanged. A test pins one computed before the field existed.
2. **The assessment itself is not persisted at completion.**
   - **What changed:** §14 step 2 says "persist the assessment". The events are persisted, and the
     assessment is computed on read from them, deterministically.
   - **Why:** a stored assessment would be a second copy that can disagree with the code that reads it.
   - **Where the frozen copy goes:** the place it matters, the campaign's close-time evidence package
     (step 7, §14's "close-time package").
3. **Records are append-only sets, one per ending,** and the latest set is the cycle's. A resumed run
   (`resume_from_failed`) ends a cycle again, and a write-once-per-cycle rule would refuse the second
   ending. A set with no records means "recorded, no failures". No set means "never recorded", and
   such a cycle's attribution is derived by the producer, as before 1a.
4. **The backfill of stored cycles (criterion 12d) runs once, after the records are deployed, with a
   backup taken first.** It writes to the live registry, so it waits for the deploy. It uses the same
   producer whose neutrality was proven against all 629 stored cycles on 2026-10-01
   (`scripts/dev/attribution_snapshot.py`, #1811).


### 24b. §10's continuation decision, as built (2026-10-02, #1800; implementer's reading, not yet ruled)

`squadops.campaigns.continuation.campaign_continuation_decision` implements §10's three steps and
fourteen rows as written. Building it settled four points §10 leaves to the implementer, and
found one gap. **None of these has been ruled.** Each is the narrowest reading of the text, and is
proposed in the PR that builds the decision.

1. **The counters are read with the ending cycle counted,** and the caller supplies them.
   - **The no-progress count also counts the abandonment row 13 would make.** Otherwise the
     decision whose own abandonment reaches `max_unaccepted_increments` would return
     `abandon_and_propose`, and the campaign would launch one more proposal before stopping.
   - **The evidence:** row 4 is step 1, and abandonment is decided in step 2. Read literally, the
     count of the abandonment arrives only at the next decision.
     `test_the_precedence_is_as_written[abandonment-counts]` pins the reading.
2. **Whether the objective's measurement is met is an input** (`objective_met`), read with this
   increment counted.
   - **Why:** `CampaignObjective.measurement` is free text (§15), and no evaluator of it exists.
   - **What is still owed:** the reference scenario (#1804) gives the first measurement a reader.
3. **Row 3 does not fire for a calibration cycle.** A calibration cycle carries no increment, so
   "with this increment counted" cannot hold for it.
4. **`max_rejected_proposals_in_row` and `max_unaccepted_increments` must be at least 1.** The
   decision reads a limit as reached at its value. At 0, the campaign would pause or stop on its
   first decision.
5. **The gap: rows 10–11 are not reachable today.**
   - **A rejected completion** reads `unattributed`, because its failed checks carry no locus.
   - **An infrastructure failure** ends its run `failed`, with no verdict, and row 14 escalates it.
   - **So a campaign never retries on its own.** The rows are built as written and tested with a
     constructed assessment. Fixing the reading is #1824.


### 24c. §9.2's increment gate, as built (2026-10-02, #1801; implementer's reading, not yet ruled)

1. **The proposal is submitted to the campaign when the gate opens.**
   - **What changed:** §9.2 says a ruling binds to "the gate's current proposal", and does not say
     how the campaign learns which proposal that is. A new control operation, `submit`, records
     it. The workload gate writes it on reaching `increment_ruling`. The row pins the proposal
     (its binding, cycle and run) on the campaign row and moves an `at_proposal` campaign to
     `awaiting_ruling`.
   - **Keying:** the row is keyed by the run, so re-entering the gate after a restart replays it.
   - **A holding campaign** (paused, escalated or launch-blocked) records the proposal in place.
     Its resume returns it to `awaiting_ruling`.
   - **The ruling's binding is checked against that pinned proposal and the accepted tree, inside
     the transaction that records the ruling.** A ruling on any other run's gate is stale too.
2. **The increment gate is never passed through.** #807 approves a gate whose design declares no
   open question. An increment cycle carries its baseline's manifest, which declares none, so the
   increment would have been approved with nobody ruling. The gate is exempt from that path.
3. **The ruling's row comes before the gate decision.** On the existing gate route, for this gate
   alone:
   - the caller needs `campaigns:supervise`;
   - the binding, a reason (`notes`) and an idempotency key are required, and a waiver is refused;
   - the `rule` row is written first, and a refused ruling records no gate decision;
   - a replayed ruling records the gate decision only if the first attempt never did.

   Every other gate still needs `cycles:write`, and refuses a binding.


### 24d. §9.2's revision request, as built (2026-10-02, #1801; implementer's reading, not yet ruled)

1. **A returned proposal is revised in a new proposal run of the same cycle,** in #811's shape:
   - the returned run is superseded (cancelled);
   - the new run's `campaign_proposal` block carries the next version, the supervisor's note word
     for word, and the change request it revises;
   - the strategy role is shown all three, and its new version is submitted and ruled on afresh.
2. **The budget is the campaign's `max_proposal_revisions`,** carried on the block as
   `max_revisions` by the launch, and required there.
   - **Revisions made so far** are counted as the cycle's superseded proposal runs, read from the
     registry, so a restart counts the same.
   - **When the budget is spent,** the sequence stops (`revision_unavailable`). The proposal counts
     as rejected (§9.5) and the cycle ends at the gate.
3. **The revised block travels as a forwarding override,** as #811's framing revision does. A
   restart while the revision run is in flight re-enters with the cycle's own block. That
   recovery belongs to step 8 (§12a, #1803).


### 24e. Starting a campaign and launching its cycles, as built (2026-10-02, #1709, #1799; implementer's reading, not yet ruled)

1. **A `start` operation.**
   - **What changed:** §13's surface names create, pause, resume and abort, and §17 draws
     `draft → calibrating`, but no operation made that move. `start` does it. It needs
     `campaigns:control` (the owner's, per the 10-02 role ruling), acts on a draft only, and
     writes the calibration cycle's launch intent in its own row.
   - **Migration 1650** adds it to the operation list.
2. **The policy names the squad** (`squad_profile`, required). Every launch is run by a squad, and
   §15's policy named only the request profiles.
3. **A launch is created by the cycle-create path itself.**
   - **What changed:** the create route's body became `prepare_cycle`. The route and a campaign's
     launch both build, preflight and persist a cycle through it.
   - **The intent carries the whole cycle-create request,** built from the policy when the deciding
     row is written, so a re-drain creates the cycle the decision named.
4. **The first run.**
   - **When drains run:** after every row that writes an intent, and once at startup.
   - **What each drain reconciles:** every live campaign's launched intents. A launched cycle
     without a run gets its first one, and a queued first run the process has not started is
     started.
   - **So a crash** between the mark and the run, or between the run and its start, is repaired
     by the next drain, and no cycle gets a second first run.
5. **Not built: escalating a launch the preflight refuses.** Such a launch stays pending and is
   logged. Escalating the campaign on it is recovery (§12a, #1803).


### 24f. The completion hook, as built, and what it does not do yet (2026-10-02, #1800, #1709; implementer's reading, not yet ruled)

At a campaign cycle's completion boundary (`CycleCompletion`), `squadops.campaigns.progress`:
- reads the ending;
- promotes an accepted calibration's tree;
- derives the counters;
- writes the continuation decision in one row keyed by the cycle, with its intent under `proceed`.

As built:

1. **The accepted tree is the files the cycle delivered,** by the one rule every reader shares
   (#1832), identified by their hash.
2. **Only a calibration is promoted here.**
   - **Why:** an increment's promotion waits for §8's acceptance (step 4's decisions) to be wired
     into its completion.
   - **The alternative refused:** promoting on the cycle verdict alone would skip the frozen
     criteria and the discrimination check.
3. **A cycle that stopped resumable (paused, or not terminal, #1754) is not decided.** A decision
   already recorded for the cycle is returned on re-entry, never recomputed, even if the clock has
   since crossed a limit.
4. **A launched cycle's end first moves the campaign to `evaluating`** (§17), then decides.
5. **The counters are derived from the campaign's records:**
   - launches give the cycles, and the cycles' usage gives the tokens;
   - the START row gives the elapsed time;
   - the earlier decision rows give the rejected proposals in a row and the unaccepted increments;
   - repair and retry cycles count since the increment cycle they serve.
6. **Not built, and named, not hidden:**
   - **`objective_met` is always false.** The measurement has no reader yet (§24b), so a campaign
     ends by exhaustion, failure, escalation or abort, not in success.
   - **`repair` and `retry` escalate** with the reason that their cycles (§10a) are not built yet
     (#1705).
   - **A held action under a pausing limit is recorded on the row,** but the owner's resume does
     not yet execute it.
   - **An increment cycle runs the proposal profile alone.** The increment gate needs a workload
     after it (the sequence loop ends on its last workload before that workload's gate), and delta
     framing (§7.3) is not built. So a `propose` decision launches a proposal run that ends with no
     verdict, and §10 row 14 escalates it to the owner with the proposal stored.


### 24g. The owner's word, as built (2026-10-02, #1800; implementer's reading, not yet ruled)

1. **The held action is executed by the owner's `resume`** (§10, §19 criterion 12a).
   - **What the resume reads:** the latest applied row into `paused`. When that row is a decision
     whose guard paused it, the resume executes that row's action exactly as recorded: a launch
     action writes its intent in the resume's own row, and an abandonment is recorded with it.
   - **The executing row:** it carries `{"action": …, "executes": "held"}`.
   - **Anything else refuses:** a second resume finds the campaign no longer paused and is refused
     as stale. A resume naming a different action is refused.
   - **This supersedes §24f's** "not yet executed by the owner's resume".
2. **An escalation is ruled through the same `resume`,** which must name the action (`propose`,
   `abandon_and_propose`, `repair` or `retry`). There is no separate ruling route; stopping is
   `abort`. The row carries `"executes": "ruling"`.
3. **An abandonment counts as unaccepted wherever it was executed:** by a decision under
   `proceed`, or by the owner's word.
4. **`repair` and `retry` are refused as unbuilt** (#1705). They are refused, not pretended.
5. **A policy's request profiles must exist when the campaign is created** (422 otherwise). A
   profile that cannot be loaded at a later launch escalates the campaign with that reason; it
   never leaves the decision unwritten.


### 24h. The evidence package, as built (2026-10-02, #1710; implementer's reading, not yet ruled)

1. **The package** is a JSON projection of the campaign's records:
   - the campaign itself;
   - its control log (every decision, with the ending and verdict it read);
   - its launches;
   - per launched cycle, the `CycleAssessment`, the latest persisted failure-record set, and the
     decision that followed it.

   **Identity:** the hash of its canonical form.
2. **It is stored in the vault** (`campaign_evidence`), beside a **morning digest** in Markdown
   rendered from the package alone:
   - what was accepted;
   - each cycle's kind, ending, verdict, decision and attribution;
   - what the owner is asked to rule.
3. **When it is materialized:** by a terminal decision, by an abort, and on request
   (`POST …/package`, `campaigns:control`).
   - **Idempotent by identity:** the same records store nothing new.
   - **The close still commits** if the materialization fails, which is logged loudly.
   - **Reading the digest:** `GET …/package` (`campaigns:read`) or `squadops campaigns digest`.
4. **A cycle whose assessment cannot be read is in the package with the reason,** never left out.
5. **Not yet in it:**
   - the per-round revision forms and stored prompts #1710 lists;
   - the log lines the readouts read;
   - a size bound.

   The package holds what the records hold today. Those additions follow the readouts that
   produce them.


### 24i. The proposal ledger, read from the control log (2026-10-02; implementer's reading, not yet ruled)

**What changed:** §16 lists a `campaign_ledger` table. The ledger is built as a **projection of the
control log** instead.

**Why:** every part of a ledger entry is already a control-log row:
- the version as submitted (`submit`);
- its ruling, reason and author (`rule`);
- its cycle's outcome (`decide`, attached to the last version that cycle carried);
- the supervisor's classification.

A second table would be a second record that can disagree with the authority.

**As built:**
- **The classification is a new record-only operation, `classify`** (migration 1660), taking one
  of §9.4's five readings. It needs `campaigns:supervise`, so the supervisor classifies.
- **It is accepted after the campaign has ended,** since the ledger is read the morning after. A
  version never submitted to the gate cannot be classified.
- **Reading it:** `GET …/ledger`, or `squadops campaigns ledger` and `squadops campaigns classify`.


### 24j. The increment cycle's seams, as built (2026-10-02, #1705; implementer's reading, decided under the 2.0 charter)

§7.3 says what an increment cycle runs. The seams that carry it reuse existing machinery, and are
being built in the order the design note on #1705 sets out:

- **a. The candidate manifest binds the increment's framing.**
  - **At the increment gate's approval:** the approved change request, whose stored hash is checked,
    has its manifest delta applied to the accepted manifest. The candidate manifest and the contract
    derived from it (#779) are stored as the proposal run's promoted artifacts.
  - **At every later advance:** the forwarding builder hands them over as `plan_artifact_refs` and
    `contract_ref`. Framing runs in bind mode and authors no manifest.
    - **Every workload, not just the next one.** They are read from the approved proposal run, so
      they reach the implementation as well as the framing, as a seed from cycle creation reaches
      every workload.
    - **Why "every" (#1705 b):** a three-workload increment showed the gap. Forwarding is rebuilt
      from the cycle and the run that just finished, so the implementation would have run
      unscaffolded, in author mode and without the accepted tree.
- **c1. The implementation starts from the accepted tree.**
  - **How the run finds it:** the increment's launch names the accepted cycle
    (`campaign_proposal.accepted_cycle_id`).
  - **What is seeded:** that cycle's delivered files (#1833's rule), beside the candidate manifest's
    skeleton.
  - **Why the accepted code wins:** the files are produced content, so the workspace's rule (#881)
    hands every existing file its accepted implementation, and only what the increment adds stays
    a stub.
- **b, the `campaign-increment` profile:** built, under §24k.
- **d, framing scoped to the change.** Its two parts:
  - **The footprint, taught and enforced (#1843).**
    - **Taught:** the plan authors are shown the footprint (`request.plan_increment_footprint_appendix`).
    - **Enforced:** the plan gate refuses a task whose `expected_artifacts` fall outside it, through
      `validate_increment_footprint`, the gate the framing re-roll keys on.
    - **Where the footprint comes from:** it is derived from the accepted manifest and the
      candidate, exactly as the change request's footprint was.
  - **The change request is the framed objective (#1705).** It is forwarded with the seed, from
    durable state.
    - **Skipped:** an increment's framing does not run `data.research_context` or
      `strategy.frame_objective`. A framing that would also author a manifest is refused.
    - **Shown:** every stage after them is shown the document verbatim
      (`request.increment_framing_section`), the brief included. The proposers get the brief's
      frame and the footprint, not the document.
    - **Checked:** the framing run's provisioning loads the change request and checks its stored
      hash.
    - **Required:** an increment framed without it is refused, and a change request given to any
      other run is refused.
- **c2, the ownership narrowed to the footprint**, as defense in depth.
  - **What it does:** an increment's bound scaffold record carries its footprint, derived as the
    plan gate's is.
    - The dev and builder grants become the fill slots inside the footprint.
    - A write to an accepted slot outside it is another producer's surface: it is dropped with
      evidence, and the next attempt is told why.
  - **Where it holds:** at task storage and on every repair emission, the two places the record is
    built.
  - **The difference from the design note:** the other slots are not frozen.
    - **Why not:** the bound record's frozen bytes are the scaffold's stubs, so freezing them would
      restore a stub over the accepted code.
    - **What protects the accepted content instead:** the dropped emission leaves the seeded
      accepted file in place (#1842).
- **Still to build:**
  - **e, the increment's acceptance at its completion** (#1839's `evaluate_increment`) and its
    promotion.

### 24k. The increment profile, and the gate's name (2026-10-02, #1705 step b; decided under the 2.0 charter)

- **What changed: the gate is named `progress_increment_ruling`.** Wherever this SIP says
  `increment_ruling`, the gate's name is `progress_increment_ruling`.
  - **The evidence:** SIP-0076 (implemented) expresses a gate's role by its name. A gate referenced
    from a `workload_sequence` must start with `progress_` or `promote_`, and the profile schema
    refuses any other name at load. `campaign-increment.yaml` was refused on its first load.
  - **Why `progress_`:** the ruling decides whether the next workload, framing, begins. That is
    SIP-0076's progression role. A third prefix would be a new variant of a canon with one
    validator, which is the drift CLAUDE.md asks to conform rather than extend.
  - **What it touched:** the gate's name is single-sourced (`campaigns.gate.INCREMENT_RULING_GATE`),
    so the change is that constant, the profiles' YAML, and test literals. No increment gate had
    been reached on any deploy, so no stored row carries the old name.
- **The profile:** `campaign-increment` runs proposal → `progress_increment_ruling` → framing →
  `progress_plan_review` → implementation. Its defaults are `validated-fullstack`'s, plus the
  proposal's `proposal_max_attempts`.
- **The ruling gate declares no `after_task_types`.**
  - **Why it is declared at all:** the registry refuses a decision on a gate the cycle's policy does
    not name.
  - **Why it has no task boundary:** a task boundary pauses a run mid-flight (`_handle_gate`),
    which here would wait for a ruling on a proposal the workload gate has not yet submitted to the
    campaign. The first draft of the profile had this defect.
- **A campaign's proposal profile must reach the ruling, checked at creation** (§24g item 5
  extended). `increment_sequence_refusal` requires that:
  - the sequence opens with the proposal workload, gated by the ruling;
  - a workload follows that gate;
  - the gate is declared, with no task boundary.

  `campaign-proposal`, the proposal workload alone, is refused as a campaign's proposal profile. It
  stays for proving a proposal against a deploy outside a campaign.
- **§24f's "an increment cycle runs the proposal profile alone" no longer holds.** An approved
  increment now frames and implements. Until step e is built:
  - its completion is assessed as any cycle is, with the stack's acceptance rather than
    `evaluate_increment`;
  - an accepted increment is not promoted, so row 7's next proposal is still made against the
    calibration's accepted tree.

  `max_cycles` bounds this; step e closes it.


### 24l. The box lease and the quiet-box check, as built so far (2026-10-02, #1802; decided under the 2.0 charter)

- **The decisions are pure** (`campaigns/box.py`, held by `test_pure_decisions_do_no_io.py`).
  - **`BoxLease`:** the squad's lease or the supervisor's. A supervisor's lease must carry an expiry.
  - **`box_quietness`:** the box is quiet only when every engine was read and every resident model
    is one the active deploy record declares. Models match by name, and by digest where both sides
    report one, so a tag re-pulled under a declared name is another model.
  - **`launch_verdict`:** a live supervisor lease refuses first. An expired one no longer holds the
    box, but the launch still needs a quiet box.
- **The reads** (`campaigns/box_reading.py`).
  - **The declared models** come from the active deploy record (#1720).
  - **Each engine's resident models** come through a new LLM-port capability, `loaded_models`
    (`list_loaded_models`): Ollama's `/api/ps`; vLLM and Atlas's `/v1/models`, since they hold the
    weights they were launched with.
  - **An engine that cannot report is unreadable, never empty.** The port raises rather than
    answering `[]`, and the reader records the failure as that engine's reading.
- **What differs from §9.3: the check is model-only.** §9.3 also reads the GPU's compute processes.
  - **Why:** the runtime-api container has no GPU device and no `nvidia-smi`
    (`DeviceRequests: null`).
  - **What it needs:** granting the service the NVIDIA `utility` capability is a
    `docker-compose.yml` change, the owner's to make.
  - **Why not fail closed meanwhile:** failing closed on an unreadable GPU listing would refuse
    every launch on this box.
- **Two of the draft's questions (#1829), decided:**
  - **A run start inside a cycle while the supervisor holds the lease waits, not fails.** It polls
    the lease, with the ruling bound as its ceiling, so an approval is not turned into a dead
    increment.
  - **A refused launch outside a campaign** (the CLI, the set driver) is a 409 that names the
    refusal and its reasons, plus a security-audit event. A campaign's own refusal is its
    control-log row (`launch_blocked`).
- **Still to build:** the lease's persistence and its API (`/api/v1/campaigns/{id}/lease`,
  `campaigns:supervise`); enforcement at the cycle-create preflight, at the launcher (re-attempted
  at the policy's interval, escalating after its count), and at run starts.
### 24m. Criterion-owned test files, as built (2026-10-02, #1705 e, part 0; decided under the 2.0 charter)

§8.1 places each criterion's test in its own file, `<the stack's test dir>/criteria/<criterion_id>.test.<ext>`,
"which the scaffold emits as a fill slot (SIP-0104)".

- **What differs: the qa plan writes the file, not the scaffold.**
  - **Why:** only `nextjs_ts` has a SIP-0104 verification-scaffold emitter. The campaign's reference
    stack, `fullstack_fastapi_react`, has none, so there is no shell for the file to be a slot of.
  - **What the plan does instead:** a qa task names the file in its `expected_artifacts`.
    `validate_increment_criterion_files` refuses a plan that leaves a new criterion's file unwritten,
    at the plan gate the framing re-roll keys on.
  - **Taught before enforced:** the plan authors are shown each criterion's file
    (`request.plan_increment_criteria_appendix`).
  - **A file only a dev task names does not count:** the qa role writes the test that proves the
    criterion.
- **Where the file lives is the stack's declaration** (`ScaffoldStack.criterion_test_files`, by surface
  kind), held inside the stack's qa namespace by the inventory test.
  - **`fullstack_fastapi_react`:** `backend/tests/criteria/test_<id>.py` for an endpoint;
    `frontend/src/__tests__/criteria/<id>.test.jsx` for a client route. pytest collects only
    `test_*.py`, so the §8.1 pattern is adapted to each runner's convention.
  - **`nextjs_ts`:** `__tests__/criteria/<id>.test.ts` and `.test.tsx`.
  - **The id is kept to letters, digits and `_`,** so the file is a valid module on every runner.
- **A new criterion may not reuse an id an earlier increment froze** (`reused_criterion`, a new
  proposal refusal). A criterion pins its bundle by id for the rest of the campaign, so a reused id
  would share the frozen file and its bundle.


### 24n. The increment's evaluation, as built (2026-10-02, #1705 e, part 1; decided under the 2.0 charter)

**What differs from the #1705 design note:** the design note put the runner in the sandbox. The
evaluation is a deterministic qa task instead, `qa.evaluate_increment`, the last task of an
increment's implementation run.
- **Why not the sandbox:** its typed operations run only the backend suite and report an exit code
  and an output tail. §8.2 reads per-test results.
- **Why the qa container:** the qa role's container already runs both stacks' runners and parses
  their reports (`test_runner.run_suite`, now the one dispatch on the test framework, which
  `run_build_validation` wraps).
- **The reading is posted on #1705** (issuecomment-5957403977).

**What it is handed** (the registry's `increment_evaluation` tasks):
- **At plan time:**
  - the increment's id;
  - each new criterion's own file (§24m);
  - the routes the candidate manifest declares, with their test ids.

  The implementation run is handed the approved change request for this. It goes to the
  evaluation alone, not to the build tasks.
- **At dispatch:**
  - the accepted tree: the run's seeded artifacts from the accepted cycle its launch names (#1842);
  - the candidate: the acceptance workspace.

  Without both trees nothing is judged, because an empty baseline would read every new test as
  discriminating.

**What it writes:** the `increment_evaluation` artifact. It carries the verdict, every
per-criterion and per-route result keyed as §8.4 says, and each newly frozen bundle whole, for a
promotion to store.

**What it does not do yet:**
- **No route is rendered (§8.3).** Every declared route arrives unrendered and is
  `blocked_unverified`, so an increment that declares a route is `blocked_unverified`, never
  promoted, and never wrongly accepted.
- **No frozen bundles are run (§8.1).** They arrive with promotion (part 2). The first increment
  after calibration has none.
- **The completion hook does not read the artifact yet** (part 2).


### 24o. An increment's promotion, and the criteria it freezes, as built (2026-10-02, #1705 e, part 2; decided under the 2.0 charter)

- **The decision reads the increment's own acceptance (§8.4).**
  - **What it reads:** the completion hook reads the implementation run's `increment_evaluation`
    artifact (§24n). `EndedCycle` carries its verdict.
  - **How the two verdicts combine** (`cycle_verdict`):
    - if either the cycle's verdict or the increment's is `rejected`, the increment is rejected;
    - only when both are `accepted` is the increment accepted;
    - anything else is `blocked_unverified`.
  - **A missing evaluation:** an increment that reached its assessment with none is
    `blocked_unverified`, never accepted unjudged.
- **An accepted increment is promoted as a calibration is** (§12a): its delivered tree becomes the
  campaign's accepted tree, in a PROMOTE row keyed by the cycle and that identity.
- **Its new criteria are frozen with it** (§8.1).
  - **What is stored:** each new criterion's bundle, as a `verifier_bundle` artifact (files,
    invocation, address, test path). A replayed promotion finds the bundle by address and reuses it.
  - **Where they are named:** in the PROMOTE row's `frozen_criteria`. The control log is the record.
- **Every later increment's launch pins the criteria frozen so far** in its `campaign_proposal`
  block.
  - **`prior_criteria`:** the ids the proposal may not reuse (`reused_criterion`, §24m).
  - **`frozen_criteria`:** each criterion's test path, bundle artifact and address.
  - **How the evaluation uses them:** at dispatch it is handed the pinned bundles and runs each on the
    candidate. A bundle that is missing, unreadable, or no longer hashes to its pinned address is
    never run, and is `blocked_unverified` (SIP-0096).
- **Not built:**
  - **retirement:** `retires` and `replaces_verifiers` do not yet remove a frozen criterion;
  - **route rendering:** every increment that declares a route stays `blocked_unverified` until
    rendering is read (§8.3, part 3). It is repaired by row 8 and never promoted.


### 24p. Route rendering, as built (2026-10-02, #1705 e, part 3; decided under the 2.0 charter)

§8.3: every declared route renders. The evaluation (§24n) reads it in the qa container, not in the
sandbox as the #1705 step e reading recommended.
- **Why not the sandbox:** runtime-api does not reach the SIP-0102 sandbox service.
  - Its provider is `noop`, and no sandbox client is wired into runtime-api or the agents.
  - Reaching it needs the service's address and token in runtime-api's environment, which is a
    `docker-compose.yml` change.
- **Why the qa container:** it already boots the backend for behavioural probes (#822). Its role
  declares its own system packages, so the browser is one line there (`chromium`), and no other
  role's image grows.

**How a page is read** (`handlers/route_rendering.py`):
1. **The candidate is stood up.** The backend is booted by the stack's probe profile, on the port
   the scaffold's dev proxy targets. The frontend is served by its own dev server after an install.
   Both are named by the stack's `render_profile` (FastAPI+React: `vite_dev_proxy`).
2. **A parameterized route is brought into being first** (`route_seeds`). Its collection's create
   request is sent, with the body the create probe sends (`create_request_body`, now the one
   synthesis), and the created id fills the route's parameter.
3. **Each page is read** by headless Chromium (`--dump-dom`), and the `data-testid` values it
   rendered are judged against the route's declared test ids.

**Anything unread is `blocked_unverified`, never passed.** That covers:
- no render profile for the stack;
- an app that does not install or boot;
- a route with no seed, or a seed the app refuses;
- a page the browser could not read.

`nextjs_ts` declares no render profile yet, so its routes are blocked.

**What differs from §8.3's text: a route renders when its view's root anchor does**, not every
declared test id. The root anchor is the first declared id, stamped on the view's container (#659).
- **The evidence:** the first live reading, of roll 4's delivered app (`cyc_2296ec2e5121`, accepted
  21/21), in the qa image. All three pages rendered their root anchor.
  - `/`, read with an empty list, did not show its row anchors (`runs-list`, `run-row`, …).
  - `/runs/new` did not show `create-run-error`.
- **Why that rules out the literal reading:** a view's anchors include states that exclude each
  other — a list's rows and its empty state, a form and its error. One reading of a correct page
  never shows them all, so "every declared id" fails a correct app.
- **What happens to the others:** the anchors a reading did not show are recorded on the route's
  result (`not_shown`), not judged. Each state's anchors are exercised by the qa suites, which put
  the page into that state.

**The same live check found a leak** in the first cut of the renderer, which this fixes. Stopping
`npx` left the dev server it started still serving and writing into the workspace being removed.
Each server now runs in a session of its own and its whole process group is stopped. No process
outlived the second reading.

### 24q. The brownfield reference scenario, as built (2026-10-02, #1804; decided under the 2.0 charter)

- **The inputs** (`examples/03_group_run/reference_scenario.yaml`), each pinned by hash:
  - **The baseline:** `cyc_7a4b7a6fbf0e`. Its delivered tree is reconstructed from the vault by the one
    delivered-tree rule (#1833).
  - **Its manifest.**
  - **The fixed change request:** the PRD's capacity limit, as the validation plan's §4 defines it.
  - **The two seeds derived from them:** the stored change request and the candidate manifest.
  - **Drift is refused:** a launch whose input moved from its pin is refused. A different baseline or
    request is a different measurement, never the yardstick. Pins are written once and never
    overwritten.
- **How it is built:** the seeds are made through the proposal's own rails and the approved gate's
  derivation (`campaigns/reference.py`), exactly as a campaign's increment gate stores them.
- **How it is launched:** one cycle on `campaign-reference` (framing → plan review → implementation; no
  proposal, no ruling: the request is pre-approved and recorded as such).
  - **It carries the same `campaign_proposal` block** a campaign's increment launch writes, and its
    seeds in `plan_artifact_refs` and `contract_ref`.
  - **So every increment seam treats it as an increment, with no campaign:** bind-mode framing on the
    candidate, the change request shown, the footprint taught and enforced, the evaluation.
  - **The accepted tree is now keyed on the block** (`accepted_cycle_of`), as every other seam
    already was, rather than on the campaign's cycle kind.
- **The launcher:** `scripts/dev/launch_reference_increment.py` (`--dry-run`, `--write-pins`).
- **Not built yet:**
  - **the proposal half:** a proposal against the same baseline, recorded and rated, not built;
  - **the per-mechanism report:** each brownfield mechanism reported separately, read from the
    record (the evaluation artifact, §24n).

### 24r. Frozen verifiers protected, and retirement, as built (2026-10-02, §19 items 7 and 12e; decided under the 2.0 charter)

- **No plan writes an earlier criterion's frozen test file** (`validate_increment_frozen_files`).
  - **What is protected:** the launch pins the frozen criteria with their test paths (§24o). Each is
    protected unless the approved change request retires it or replaces its verifier.
  - **How:** refused at the plan gate the framing re-roll keys on, and taught first
    (`request.plan_increment_frozen_appendix`).
- **A candidate that rewrote a frozen verifier is not accepted on it.**
  - **The bundle still runs as frozen:** the candidate's copy is never what is judged.
  - **The criterion is blocked:** if the candidate's copy of the test file differs from its bundle
    without a `retires` entry, the criterion is `blocked_unverified`, and so is the increment (§19
    item 7).
- **Retirement:**
  - **Dropped from the run:** a criterion the change request retires, or whose verifier it replaces,
    is dropped from the evaluation's frozen set.
  - **Recorded at promotion:** the promotion records it (`retired_criteria` on the PROMOTE row), and
    the frozen set every later launch pins leaves it out.
- **Not built: re-freezing a replaced verifier.** `replaces_verifiers` is treated as retirement, so the
  replacement's new bundle is not frozen. A change that replaces a verifier leaves that behaviour
  unfrozen until a later criterion covers it. *(Built since: §24x.)*

### 24s. Retry cycles, as built (2026-10-02, §10a, §19 item 12b in part; decided under the 2.0 charter)

- **What launches a retry:** a `retry` decision (§10 row 10), or the owner's resume of a held one.
- **How it is launched** (`launch_requests.bound_launch`): with the policy's proposal profile, with its
  `proposal` workload removed, so its stack is the campaign's and no proposal is run or ruled. It
  carries:
  - the increment's own `campaign_proposal` block;
  - the approved seeds: the candidate manifest, the change request and the contract. They are read
    from the increment's approved proposal run, or from the failed retry's own launch.

  So every increment seam reads it as the increment it continues: bind-mode framing on the
  candidate, the footprint, the accepted tree as the starting tree, the evaluation.
- **The binding is re-checked before anything launches.** The increment's baseline must still be the
  accepted tree, and an applied ruling approving that proposal version must be on record. Otherwise
  the decision escalates and names the mismatch. Any change of scope, baseline or content needs a new
  proposal and ruling.
- **The campaign moves to `retrying`.** When the retry ends it is `evaluating` again, and it is decided
  like an increment.
- **Retries and repairs are judged like an increment:** by their own evaluation (§8.4), and promoted
  when accepted.
- **Not built:**
  - **repair cycles:** implementation only, under the failed cycle's plan, from the failed candidate's
    content, with the prior-cycle brief in the correction context;
  - **a retry's prior-cycle brief shown to framing.**

  A `repair` decision still escalates as unbuilt.

### 24t. Repair cycles, as built (2026-10-02, §10a, §19 item 12b; decided under the 2.0 charter)

- **What launches a repair:** a `repair` decision (§10 row 12), or the owner's resume of a held one.
  It is launched by the same `bound_launch` as a retry (§24s), with the same binding re-check. A
  `repair` decision no longer escalates as unbuilt, which §24s recorded.
- **It runs the build alone.** Each bound kind keeps only its own workloads of the policy's proposal
  profile (`BOUND_WORKLOADS`): a retry keeps `framing` and `implementation`, a repair keeps
  `implementation`. A profile that does not hold them refuses the launch, and the decision escalates
  and names the reason.
- **Under the failed cycle's approved plan.** The launch forwards the implementation plan the failed
  cycle built under, beside the increment's seeds:
  - its framing's promoted plan;
  - or, for a repair of a repair, the plan that repair was launched with.

  The implementation run loads it from the forwarded refs, as it loads any approved plan. A cycle
  with no plan on record cannot be repaired, and the decision escalates (`unbuilt`).
- **From the failed candidate.** The block names the cycle it repairs (`repair_of`). The run's
  starting tree (`starting_tree_refs`) is the accepted tree's delivered files with the failed
  cycle's delivered files composed over them, so a file both hold is the failed cycle's.
- **A retry after a repair does not inherit the repair's plan.** The seeds a bound launch carries
  forward are filtered to the seed types (the candidate manifest and the change request). A seed
  that cannot be read is left out and logged, never a crash.
- **Not built: the prior-cycle brief** that §10a's table puts in a repair's correction context. It
  is #1692's, and until it lands a repair is told nothing of the cycle it repairs beyond its files.

### 24u. The prior-cycle brief, as built (2026-10-02, #1692, §10a, §14; decided under the 2.0 charter)

This builds what §24s and §24t recorded as not built: the brief a retry and a repair are shown.

- **What it is** (`campaigns/prior_cycle.py`): the failed cycle's own record, carried to the cycle
  that recovers from it. No model writes any of it (§14: authored by the framework from the prior
  cycle's records). It holds:
  - the assessment's typed indicators: the verdict, the failed checks, what went unverified and
    why, criteria coverage, correction movements and refunded rounds;
  - the cause the attribution names;
  - **why each failed check failed:** the reason its run's stored verification summary recorded
    (`failed_detail`, #500).
    - The latest run's reason is used.
    - Only checks the assessment counts as failed are included.
    - Each reason is shown verbatim in a fence, up to 1500 characters, and says where it was cut.
    - A check its producer disputed (SIP-0096 §17a) is marked as disputed.
- **An indicator the assessment could not ask is shown as `not recorded (<reason>)`,** never
  omitted, so an absence is not read as "nothing failed". A check with no stored reason is listed
  without one, and none is invented.
- **How it travels:**
  - A retry or repair launch carries it on its `campaign_proposal` block (`prior_cycle`). It is read
    from the decided cycle's assessment and its runs' summaries: at the decision, or for an owner's
    resume, at the resume.
  - It is an aid, so a record that cannot be read leaves the brief out, with a warning. It never
    blocks the launch, the owner's included.
  - The continuation decision never reads it.
- **Who is handed it is the context-assembly registry's declaration** (`prior_cycle_brief`), as it
  is for a framing re-roll's rejection (#669). The flagged authors are:
  - framing's: the technical design, the test strategy, the plan authoring brief and the three
    proposers;
  - the implementation's: the developer, the qa test author and the builder.

  No other task gets it: not the merger, nor the evaluation. Each flagged author shows it through
  one managed asset (`request.prior_cycle_brief_appendix`). `qa.define_test_strategy` moves out of
  `DECLARED_NO_CONTEXT`, since it now has a declared input.
- **What differs from §10a's table:**
  - **A repair shows it to the implementation's authors, not to its correction context.** A repair
    re-runs the approved plan over the failed candidate, so those authors are the ones correcting
    the failed cycle. The correction rounds inside the repair read their own cycle's failures, which
    are newer than the brief.
  - **A retry shows it to framing, as §10a says, and to its implementation's authors too.** They
    build the same increment again, and the checks that failed will judge them.
- **Not built, of what #1692 lists:**
  - **The proposal run's brief** (§7's inputs). A fresh proposal after an abandoned increment (row
    13) is not yet handed the brief of the cycle that ended it.
  - **The correction chain's own record:** what each round tried, and the patches it refused.
    The brief carries the round counts, not their content.
  - **The recurrence measure:** whether a failure class recurs within the campaign after the brief
    is shown.

### 24v. A cycle that ended with no decision, re-heard at startup (2026-10-02, §12a, #1803; decided under the 2.0 charter)

**§12a's restart table lacked a row for a launched cycle that ended with no decision recorded.**
That happens when the completion hook failed, or when the process stopped between the cycle's end
and its decision.
- **Its row said:** "calibrating, or running an increment: the campaign waits on the cycle". The
  cycle had already ended, so the campaign waited forever.
- **The evidence:** the first live campaign shakeout (`cmp_a34deb3d7372`).
  - Its calibration ended accepted.
  - The hook promoted it, then crashed before deciding (#1857).
  - Nothing heard the cycle again. The hook's own docstring promised a re-entry that did not exist.
  - The campaign was aborted.

**As built:**
- **The ending is recorded before the campaign is told.** `CycleCompletion.end` appends the cycle's
  ending (`RecordedEnd`: the last run and the stop reason; migration `1670_cycle_ends.sql`) beside
  its failure records. The table is append-only, and the latest ending is the cycle's.
- **At startup, after the launcher's drain, every launched cycle of a live campaign is re-heard**
  (`CampaignProgress.rehear_ended`, from `main._resume_campaigns`), from its recorded ending.
  - A cycle with no recorded ending is in flight, or ended before endings were recorded, and is
    left alone.
  - A paused ending is not decided, as at the hook.
  - A decision already recorded for the cycle is returned unchanged, so re-hearing changes nothing.
- **Re-hearing runs after the drain, never inside it,** because a decision launches through the
  drain, which holds its lock.

**What differs from re-reading the cycle:** the stop reason is never reconstructed from the runs. A
gate rejection and a failed run can leave the same run statuses. §12a says nothing is reconstructed
from logs, and the recorded ending is the record.

**Not built:**
- **A re-hear between restarts.** A hook that fails while the process stays up leaves its campaign
  until the next restart. *Built in 2.1.0 (#1972): the campaign sweep re-hears every launched
  cycle on its 60-second interval, through the same idempotent path, and a cycle the hook is still
  hearing is not heard alongside it.*
- **The fault-injected diagnostic** §12a requires for this row.
- **Any recovery for a cycle that ended before this record existed.** It is left alone. The
  shakeout's campaign was aborted for that reason.

### 24w. The abandoned increment's brief, shown to the next proposal (2026-10-02, §7, row 13, #1692; decided under the 2.0 charter)

This builds the first of §24u's not-built items. §7 lists the prior-cycle brief among the proposal
run's inputs.

- **When:** an `abandon_and_propose`, whether by the decision (§10 row 13: rejected, no repair left)
  or by the owner's word.
- **What is carried:** the new increment's launch carries the abandoned cycle's brief, read as §24u
  reads it, fail-soft.
- **Who sees it:** the proposal shows it through its own asset
  (`request.proposal_abandoned_increment`).
  - The asset says the abandoned change is not in the application.
  - It says the same change proposed again will be judged by the same checks.
  - It asks for a smaller or changed proposal, or a different one.
- **It has its own key, `abandoned_increment`, never `prior_cycle`.** The registry hands
  `prior_cycle` to every author of the cycle as "this increment was attempted before" (§24u). The new
  increment is a different change, so its framing and build authors are not told that. Only the
  proposal reads `abandoned_increment`.
- **A `propose` that replaces nothing carries none.**

### 24x. A replaced verifier, frozen anew (2026-10-02, §8.1, §24r's not-built; decided under the 2.0 charter)

§8.1: a change request replaces a criterion's bundle through `replaces_verifiers`, and "the old bundle
is retired and the new one frozen." §24r built the retirement. This builds the freeze.

- **Where the replacement is:** at the test file the launch pinned for that criterion. The new
  verifier is written where the old one was, and the plan gate already lets the plan write it
  (§24r).
  - The evaluation is handed each replaced criterion with that path
    (`increment_replaced_criteria`, from `replaced_criterion_files`).
  - A replacement of a criterion the launch did not pin names no file, and is none.
- **How it is judged:** its new bundle is frozen from the candidate's copy of that file, and run on
  the candidate as a frozen criterion is.
  - It must hold. A replacement that fails on the candidate is `broken`, and the increment is not
    accepted.
  - A replacement the candidate does not carry is `blocked_unverified`.
  - Nothing discriminates it: it guards behaviour the campaign already accepted, changed by a ruled
    scope.
- **How it is frozen:** the new bundle is in the evaluation's `new_bundles`, so the promotion freezes
  it.
  - The same PROMOTE row retires the old one (`retired_criteria`).
  - The frozen-set fold applies a row's retirements before its freezes, so the criterion stays
    frozen, under its new bundle, for every later launch.
  - The evaluation records which criteria were replaced (`replaced`).


### 24y. What an increment's plan authors are offered (2026-10-02, §7.3, #1868; decided under the 2.0 charter)

**The evidence:** shakeout 2's increment (`cyc_b5043d62d2f0`). Its first framing was refused at the
plan gate for doing what it was taught.
- The footprint said "plan tasks **only** for these files", and listed `backend/models.py` and
  `backend/errors.py`. The manifest delta changes them, so the scaffold regenerates them, and the
  frozen rule forbids any task to claim them.
- It was offered a builder task, whose `assembly_notes.md` no increment's footprint holds.

**As built:**
- **The footprint is shown in two parts.**
  - The files the plan's tasks write.
  - The files the scaffold regenerates from the approved manifest
    (`request.plan_increment_regenerated_appendix`), which no task claims.
  - The split is the contract's `frozen_files`, the set the gate refuses a claim on, so what the
    authors are taught and what the gate enforces cannot disagree.
- **An increment's plan has no builder task: `builder.assemble` is not offered.** A builder's
  artifacts are packaging. An increment's footprint is derived from its manifest delta and test
  namespace, and never holds packaging; the accepted tree's packaging is its starting tree.
  - **An increment that does need packaging changed** (a new dependency, say) needs the footprint
    to reach packaging files first. That is not built.


### 24z. An increment's frozen files are its candidate's (2026-10-02, §7.3, §24t, #1876; decided under the 2.0 charter)

**The evidence:** the reference increment (`cyc_d4438834b2c3`) passed framing and built. Its
implementation then failed `plan_defect`, because every test of criterion C1 died with
`AttributeError: 'RunCreate' object has no attribute 'capacity'`.
- The routes were written against the candidate manifest, whose `RunCreate` declares `capacity`.
- The workspace held the **accepted baseline's** scaffold-frozen `backend/models.py`.
- The accepted tree is seeded after the skeleton, last-writer-wins (#881), so its copy of every
  frozen file overrode the one the candidate manifest regenerated. No repair can rewrite a frozen
  file.

**As built:**
- **What the accepted tree supplies:** an increment's starting tree takes its produced files from
  the accepted tree (the fill slots, the tests), and for a repair from the failed candidate
  (§24t). **Never a scaffold-frozen file.** Those are the candidate skeleton's (`frozen_paths`:
  the skeleton's files less its fill slots).
- **What the evaluation's baseline reads:** the accepted cycle's delivered files, whole, from that
  cycle (`accepted_tree_contents`), not from the run's seed. The baseline overlay needs the
  baseline's own frozen files.

**Found with it** (#1877, not a design change): the scaffold typed every request field `str`, so
the candidate's `RunCreate.capacity` refused the integer its criterion sends. Request fields now
take their entity's declared type.

### 24aa. The reference scenario's per-mechanism report, as built (2026-10-02, §11a, §24q's not-built; decided under the 2.0 charter)

`scripts/dev/reference_report.py --cycle <id>`. The derivation is `reference.mechanism_report`; the
script only fetches. It reads one reference increment's record through the runtime API and
reports each brownfield mechanism separately, read from the record only.
- **Delta framing:** each framing attempt and its gate. A refusal is shown with its notes whole: the
  gate joins its reasons with `; `, a reason can carry one itself, and the record cannot be split
  back into them.
- **Scoped repair:** the correction movements and refunded rounds, from the cycle's assessment, and
  the cause its attribution names. If no implementation ran, the report says so.
- **Accumulated acceptance, baseline discrimination and route rendering:** each read from the
  evaluation artifact (§24n). If there is none, the report says the increment was never judged.
- **The verdict:** the increment's and the cycle's.

**The assessment's three states are kept** (#1445): a value; `none` when asked and there were none;
`not recorded (reason)` otherwise. An absence is never read as either of the first two. The
prior-cycle brief (§24u) had dropped `asked_none` indicators, and now shows them as `none`.

**Its fixtures are live records:** shakeout 2's refused increment, and the reference increment's
failed build (`cyc_d4438834b2c3`, with its assessment).

**Not built:**
- **the proposal half** (the owner's ruling is asked on #1804);
- **validation on an evaluated increment's record.** None has completed yet: the reference build
  failed on #1876/#1877. *(Validated since, on the completed reference `cyc_257539e64218`: routes
  held, criteria `not_run` on #1880.)*


### 24ab. The builder still assembles an increment's build (2026-10-02, §24y, #439; decided under the 2.0 charter)

§24y says an increment's plan has no builder task, and none is offered. The build still runs one.
- **Where it comes from:** #439's workload-invariant tail appends `builder.assemble`, and `qa.test`
  after it, to every implementation run whose squad has a builder, whatever the plan holds.
  Assembly and verification are workload-owned, so a plan cannot drop them.
- **The evidence:** the accepted reference increment `cyc_7c503f5e0fdf`.
  - Its plan had no builder task, and its build ran `builder.assemble`.
  - The increment was accepted, and its footprint held.
- **Why it is harmless:** the builder's packaging outputs (`Dockerfile`, `.dockerignore`, …) are in
  the candidate skeleton's frozen set, so scaffold enforcement restores them, and its notes are a
  document. So the tail changes no accepted file.
- **Not decided:** whether an increment's build should skip the tail's assembly. It costs one
  builder task per increment, and nothing measured so far says it does harm.


### 24ac. An increment's accepted tree is the whole app (2026-10-03, §12a, §24f, #1887; decided under the 2.0 charter)

§24f said the accepted tree is the files the cycle delivered. For a calibration, that is the app.
For an increment it is not.

**The evidence:** shakeout 3 (`cmp_3cd057058851`) promoted its first increment (`cyc_df019ef84ca4`).
Its second increment then spent five correction rounds on a list view that its correction decision
called "a stub". The calibration had implemented that view, and the first increment never touched
it.
- An increment's run is seeded with the tree it builds on, but those seeds stay the accepted
  cycle's artifacts.
- So the increment's own artifacts are only its change and its skeleton's stubs.
- The promotion read those, so its tree and identity were partial. The next increment was seeded
  from them, and so was its evaluation's baseline.

**As built:**
- **A promotion composes the whole tree** (`compose_accepted_tree`): the tree the cycle was built on
  (its accepted cycle's), overlaid with what it delivered, by #881's rule across cycles.
  - Produced content wins over what it replaces.
  - A scaffold-seeded file never shadows produced content, so a stub for a slot the increment did
    not touch keeps the accepted implementation.
  - Among seeded versions the latest wins: the frozen file the candidate regenerated (#1876).
  - A calibration builds on nothing.
- **The promotion records that tree** as an artifact (`accepted_tree`, `path → artifact id`) and
  names it on the PROMOTE row (`tree_ref`). The identity is the composed tree's.
- **Every reader of an accepted tree reads the record:** the next increment's seed and its
  evaluation's baseline. A cycle promoted before the record existed, or never promoted (a reference
  baseline), keeps the delivered-files reading.

**Not repaired:** shakeout 3's increment 1 was promoted before this fix, so its recorded identity is
the partial tree. The campaign's later increments are judged against that partial record.

### 24ad. A question the accepted cycle's gate answered is not asked again (2026-10-03, §7.3, §12a, #1885; decided under the 2.0 charter)

An increment frames the accepted manifest plus its approved delta (§7.3). The manifest's open
questions (`unresolved: true` decisions, SIP-0103 §5c.10) are what its plan gate stops for. The
answer to one is recorded only in the approving gate decision's notes. The accepted manifest kept the
question open.

**The evidence:** shakeout 3's calibration was asked `datetime-format` and answered at 22:14 ET.
Increment 1's candidate asked it again, and its plan gate stopped for a human at 23:03 ET. Shakeout
4's calibration was asked `run-list-ordering`, answered at 01:41 ET; replayed on the stored records,
increment 1's candidate (the accepted manifest plus `prop_567c4915dbc0`'s delta) still carries it. An
unattended campaign would stop at every increment's gate for a question already ruled.

**As built:** carried forward at the proposal, from the record.
- **The proposal launch** reads the accepted manifest, then the accepted cycle's answer: the latest
  approval on one of its framing runs that a principal made and that has notes
  (`CampaignProgress._question_answer`).
- **Each open question is resolved by it** (`resolve_answered_questions`). The decision's `choice` is
  the gate's notes. Its `warrant` names the cycle, the actor and the time, and keeps the question
  that was asked.
- The resolved manifest is the proposal's baseline, so the candidate carries the answer. The
  increment's gate then passes as `system:no_open_questions`. When that increment is accepted, its
  manifest already holds the answer, so later increments inherit it with nothing to resolve.

**What does not count as an answer:**
- A machine pass-through answered nothing.
- An approval with blank notes stated nothing. Its question stays open and is asked again, rather
  than a ruling being invented.

**Not chosen:**
- **Rewriting the accepted manifest at promotion.** It would be a new write on a completed cycle, for
  what one read at the proposal already gives.
- **A campaign-level register of ruled questions.** It would be a second home for a decision the
  manifest already models.

Decisions sit outside the manifest's structural projection, so no contract binding or skeleton
moves.

### 24ae. The ruling bound, as built (2026-10-03, §9.2, §9.5, §19 criterion 10, #1801; decided under the 2.0 charter)

`crew_ruling_bound_s` and `owner_ruling_bound_s` were declared in `CampaignPolicy` and read
nowhere, so an unruled gate waited forever with nothing recorded. §9.2 says a gate not ruled
within the bound "pauses the campaign (`awaiting_ruling`)". §9.5's row says the pause resumes on
"a ruling, or the owner".

**As built:**
- **A sweep in the runtime API** runs every 60 seconds (`main._sweep_campaigns` →
  `CampaignProgress.sweep_ruling_bounds`) over every campaign in `awaiting_ruling`
  (`CampaignRegistryPort.campaigns_in_state`).
- **The gate's clock starts when it opens:** the latest applied row that moved the campaign into
  `awaiting_ruling` (`gate_opened_at`). That is a submission, or a resume that returns a held
  proposal to the gate. A revision's new version opens it afresh.
- **Each seat's bound, once passed, is one row:** `ruling_overdue` with `seat` `crew` or `owner`,
  keyed by the seat, the proposal run and the version, so it is written once
  (`ruling_overdue_transitions`, pure).
  - The row keeps the campaign `awaiting_ruling` (`expected_state` and `next_state` both
    `awaiting_ruling`). That state is the bound's pause, and nothing launches from it.
  - A row that races a ruling is refused as stale and recorded. It never lands on a gate
    already ruled.
- **Nothing rules on the gate.** A ruling still resolves it, from the crew's supervisor or the
  owner, before or after either bound. The campaign never proceeds unapproved.
- **The owner's morning digest** asks for the ruling while the gate waits, and names each bound
  it has passed. The digest is the row's reader.
- **Migration 1680** adds `ruling_overdue` to the control log's operation list.

**Not built, as my draft on #1801 proposed (comment of 2026-10-02):**
- **An owner-only gate after the crew's bound.** §9.5's row says a ruling resumes the gate, so a
  late crew ruling is accepted.
- **Moving to `paused` at the owner's bound.** `awaiting_ruling` is the pause §9.5 names. A
  `paused` state would let a crew ruling lift what §9.5 calls a limit-caused pause.
- **The box lease's return at the crew's bound** (§9.3) waits for the lease's persistence, which
  §24l records as still to build. The sweep is where it will be read.

**The sweep's next tenants:** re-hearing an ended cycle between restarts (§24v's not-built) and
the launch-blocked retries (§9.3). Each needs its own concurrency reading against the live
completion hook before it joins.

### 24af. The reference scenario's proposal half, as built (2026-10-03, §11a, §24q's not-built, #1804; decided under the 2.0 charter)

§11a: "The strategy role also runs a proposal against the same baseline and objective. That
proposal is recorded and **rated by the supervisor, not built**." The build half shipped as §24q,
and the report as §24aa. This half was drafted on #1804 and held for a ruling it did not need.

**The snag it answers:** the sequence loop ends before its last workload's gate (§24f), so a
proposal-only cycle cannot reach a gate to be ruled at.

**As built:**
- **The proposal runs on `campaign-proposal`:** the proposal workload alone, with no gate. It is
  the profile the first live proposals ran on.
  - It is launched by `launch_reference_increment.py --proposal`, through
    `reference_proposal_request`.
  - It carries the build half's pinned baseline and objective under its own id
    (`ref_rated_proposal`).
  - Nothing is seeded: no candidate manifest, contract or change request. The cycle ends with its
    change request stored, and nothing builds.
- **The rating is a typed record, not a ruling** (`campaigns/proposal_rating.py`). A ruling decides
  what happens next, nothing does here, and this cycle has no accepted identity to bind one to.
  - **Its verdict** uses the ruling's three outcomes, as what the supervisor would have ruled:
    `would_approve`, `would_return` or `would_reject`.
  - **It carries a reason**, and three ratings from 1 to 3, each with a note: `scope_fit`,
    `criteria_discriminability` and `footprint_size`.
  - **It is bound to the stored change request's `content_hash`.** A rating of any other document
    is refused, as a stale ruling is.
- **`POST /api/v1/projects/{p}/cycles/{c}/proposal-rating`** (`campaigns:supervise`) stores the
  rating beside the change request, as a `proposal_rating` artifact.
  - It refuses a campaign's cycle, since a campaign's proposals are ruled at the increment gate.
  - It also refuses a cycle that stored no change request, and an incomplete rating, naming every
    reason at once.
  - **The CLI verb** is `squadops cycles rate <project> <cycle> --rating-file …`.
- **The per-mechanism report** takes `--proposal-cycle` and shows the proposal beside the build
  half's mechanisms (`rated_proposal`): its criteria, its footprint, and the rating of exactly that
  version. A rating of another version is named as such, and never shown as this one's.

**Not built:** a dummy workload after a gate so that the proposal could be ruled. That cycle would
pretend it might build, and its ruling would arm a gate that launches nothing.

### 24ag. An accepted repair proposes from the manifest it ran against (2026-10-03, §10a, §24ad, #1902; decided under the 2.0 charter)

**The evidence:** shakeout 4's repair cycle (`cyc_eaae3dec8d09`) was accepted and promoted, and the
next proposal escalated at control-log seq 14: "the accepted cycle stored no interface manifest".
§10a's repair reuses the increment's approved seeds through its launch's `plan_artifact_refs` and
stores none of its own. The proposal read only the accepted cycle's own artifacts.

**As built:**
- **The accepted manifest is the one the cycle ran against** (`_accepted_manifest`): one it stored
  (a calibration's authored manifest, an increment's approved seed), else the seed its launch
  carried.
- **§24ad's answer follows the repair to the cycle that framed it.** A repair runs no framing, so it
  has no gate of its own. The answer is read at the framing gate of the cycle it repaired
  (`repair_of`), following repairs of repairs, bounded. The decision's `warrant` names the cycle
  whose gate answered, not the repair that was accepted. A retry runs framing again, so it reads
  its own gate.

**Why it passed CI:** the progress tests' fake vault handed every stored artifact to every cycle, so
any accepted cycle "stored" the calibration's manifest. The new test answers by cycle, as the live
vault does.

### 24ah. The objective's measurement has a reader, so row 3 can stop a campaign in success (2026-10-03, §10 row 3, §15, §24b's not-built; decided under the 2.0 charter)

§24b recorded that `objective_met` was always false. `CampaignObjective.measurement` is free text and
nothing read it, so row 3 could never fire, and a campaign ended by exhaustion, failure, escalation
or abort, never in success.

**The evidence:** shakeout 4 (`cmp_be852b0f08f0`) accepted its second increment at control-log seq
19, with every frozen criterion held, which was its measurement ("two accepted increments"). It then
ended on row 4 (total cycles), outcome `exhausted`. The 2.0 plan's set is two campaigns of three
increments each (decision 3). Without a reader, each would propose increments past its objective until
`max_cycles` stopped it, and it would read exhausted.

**As built:**
- **`CampaignObjective.target_accepted_increments`:** the measurement's one machine reading, the
  accepted increments that meet it. It is required of every new campaign (the create route refuses
  it missing). A campaign stored before the field existed reads `None` and has no reader, as before.
- **Row 3's `objective_met`** holds when the campaign's accepted increments, this one counted, reach
  the target. The count is the applied PROMOTE rows of its increment, repair and retry cycles, each
  cycle once, read after this cycle's own promotion commits. The calibration's promotion is the
  accepted baseline, not an increment.
- **The measurement's text stays the human statement;** the digest prints the target beside it.

Row 3 is checked before row 4, so a campaign whose last allowed cycle meets the target ends in
success, not exhaustion.

### 24ai. The box lease, enforced (2026-10-03, §9.3, §19 item 9, §24l's still-to-build, #1802; decided under the 2.0 charter)

§24l built the lease's decisions and the quiet-box reads, and nothing called them. Its still-to-build
list was the lease's persistence and API, and enforcement at the cycle-create preflight, the launcher
and run starts.

**The evidence:** the crew's review of the 2.0 pre-registration draft (#1908, 2026-10-03,
changes requested). The draft counts "no launch beside a crew model" among the set's safety
guarantees, and on main that guarantee rested on operator discipline, with nothing in the control
log to read it from.

**As built:**
- **The lease is stored** (migration 1690, `box_lease`): one row, seeded as the squad's, so every
  change takes its row lock. A supervisor's lease, and only one, carries an expiry.
  - Each change is a control-log row (`lease_acquire`, `lease_release`), committed with the lease by
    `CampaignRegistryPort.change_box_lease` and never by `transition`. Each row is projected to the
    security audit like every other row.
  - Its rules are pure (`box.lease_refusal`, `box.leased`):
    - **acquire** only at the campaign's increment gate (`gate_not_open`), only while no run is in
      flight on the box (`run_in_flight`), and only when no other supervisor holds it (`box_held`);
      the same holder renews;
    - **release** only by the holder of a live lease (`not_lease_holder`). An expired lease holds
      nothing.
- **The API:** `GET`/`POST /api/v1/campaigns/{id}/lease` and `POST …/lease/release`, under
  `campaigns:supervise` (read under `campaigns:read`). An acquire past the policy's `lease_expiry_s`
  is refused (422).
  - The CLI: `squadops campaigns lease show|acquire|release`.
- **One reader of the box,** `BoxReader`: the lease, the active deploy record's declared models, and
  the configured engine's resident models. Every launch path asks it.
- **Enforcement at the three points:**
  - **The cycle-create route** refuses with a 409 (`BOX_REFUSED`, naming the refusal and its reasons)
    and a security-audit event (`cycle.launch_refused`). This covers the CLI and the set driver.
  - **The launcher** launches nothing for a campaign in a holding state. An intent the box refuses
    moves its campaign to `launch_blocked` with a `launch_blocked` row (the attempt, the refusal, the
    reasons, the state it was launched from), and the intent stays pending.
    - The campaign sweep re-attempts it every `launch_blocked_interval_s`: allowed, a
      `launch_unblocked` row returns the campaign to that state and the held intent launches;
      refused at the `launch_blocked_attempts`th attempt, the campaign escalates.
    - The owner's resume of that escalation names no action: it returns the campaign to
      `launch_blocked`, re-attempted at once and counted afresh (an action would write a second
      intent beside the pending one).
  - **A run start** waits, queued, while the supervisor holds the box, reading the lease every 15 s,
    and starts once it is released or expires (§24l's "waits, not fails"). Its ceiling is the
    holding campaign's `owner_ruling_bound_s`; a lease renewed past it fails the run unstarted, with
    the reason.

**Not built, and why:**
- **The check stays model-only (§24l).** The GPU's compute processes are not read until the
  runtime-api is granted the device, which is a `docker-compose.yml` change and the owner's. The
  guarantee is therefore "no launch beside an undeclared resident model", and the pre-registration
  says so.
- **The acquire reads the runs in flight before its transaction.** A run whose start read a free
  lease, and that marks itself running between that read and the acquire's commit, is not seen.
  The window is a run's lease read to its `running` write. Closing it would put the run start under
  the lease's row lock, a change to every run's start for a race that needs a run and a supervisor
  to land in the same instant. Recorded, not built.

**Deployed proof:** the pre-registration's precondition 4 (#1908), read on the deploy that carries
this, and appended here.

- **The quiet-box half, rebuild 16** (2026-10-03, 14:38–14:39 UTC, `cmp_969baa78fd39`). With
  `llama3.1:8b` resident, a CLI create was refused (409 `box_not_quiet`, audit
  `cycle.launch_refused`). The campaign's launch went `launch_blocked`, then escalated. After the
  unload and a resume, the sweep launched it 15 s later.
- **The live-lease half, rebuild 18** (`5f46d946`, shakeout 6's first increment gate, 2026-10-03,
  22:05–22:09 UTC, `cmp_58d4e3b0a5d3`). 5 of 5 steps passed:
  1. a 120 s lease: a create refused, `supervisor_holds_the_box`;
  2. the lease expired with `llama3.1:8b` resident: a create refused, `box_not_quiet`;
  3. re-acquired, and the ruling approved while held: the framing run stayed queued
     (`run_start_waiting_for_box … refusal=supervisor_holds_the_box`);
  4. released with the model still resident: the framing run stayed queued, and a create was
     refused, `box_not_quiet` (§24an);
  5. the model unloaded: `run_start_box_free … waited_s=120`, and the framing run started 3.6 s
     later.

  Each refused create was audited (`cycle.launch_refused`, `denied`). The step log is
  `var/campaigns/cmp_58d4e3b0a5d3/proofs/1802-live-lease-proof.log`; the records are on #1908.
- **Not shown live: a campaign launch under a live lease.** It cannot arise: an acquire needs the
  increment gate open and no run in flight, and a campaign launches only when a cycle ends.

### 24aj. A plan gate waiting on a design question is bounded too (2026-10-03, §9.2, §9.5, §24ae, #1708; ruled by the owner)

§24ae bounded the increment gate and nothing else. A framing whose plan asks a design question
stops its cycle at `progress_plan_review` until someone answers. That wait had no bound and left no
record, so a campaign could sit on it unseen. #1708's "no gate waits without bound" was unmet for the
2.0 set. The owner ruled this built before the loop's exit shakeout (2.0 plan rev 9, §5a.5).

**As built:**
- **The same sweep, the same row.** Every interval, `CampaignProgress.sweep_ruling_bounds` also
  reads each campaign in `calibrating`, `building`, `repairing` or `retrying`.
  - **Which gate is waiting** (`gate.waiting_gate`): its newest launched cycle is waiting when the
    newest run completed, that run's workload names a gate, and the gate holds no decision. The run
    is read by its number, not its position, so a re-rolled framing reads correctly.
  - **The rows** (`gate.plan_gate_overdue_transitions`, pure): each seat whose bound has passed since
    the gate opened (the run's `finished_at`) gets one `ruling_overdue` row. It is keyed by the seat,
    the run and the gate, and its binding names the gate and the cycle.
  - **The increment gate is left to §24ae's rows.**
- **The row keeps the campaign where it is,** and nothing answers the gate. The supervisor's or the
  owner's answer still resolves it, before or after either bound (the runbook's §4).
- **The digest asks for the answer** while the overdue rows are the campaign's latest word, naming
  the gate, the run and each bound passed. Once the campaign moves on, the ask goes.

**Not built, by the same decisions as §24ae:** an owner-only answer after the crew's bound, and a
move to `paused`. In 2.0 every gate stays the supervisor's or the owner's (the plan's decision 4).
The auto-decision tier and the escalation queue are placed in 2.2.0.

### 24ak. What died with the logs is kept: the revision forms, and the log windows (2026-10-03, §14, §24h's not-yet, #1710; ruled by the owner)

§24h's package lacked the per-round revision forms and the log lines the readouts read. Both lived
only in the containers' logs, and a rebuild destroys those. Shakeout 5's cycles show the loss:
archived after rebuild 16, every container's window is empty. The owner ruled this capture built
before the loop's exit shakeout (2.0 plan rev 9, §5a.5).

**As built:**
- **The revision forms are the run's record.** A task's outputs now carry every form it took:
  - a repair's `revision_form`, as before;
  - each self-evaluation pass's (`self_eval_revision_forms`);
  - a qa re-take's (`qa_retake_revision_form`), on both the accepted and the refused branch.

  The task dispatcher reads each reply through `run_loop_summary.revision_forms_of`, keeping the
  run's forms beside its usage. Finalization persists them on the run's loop summary
  (`revision_forms`; a row written before reads `None`). They never move an assessment's identity:
  they are the run's record, not evidence the assessment reads.
- **The package carries them.** Each cycle lists its runs' forms from their persisted summaries
  (`PACKAGE_VERSION` 2).
- **The log windows are kept on the Spark** (the triage tier of #1710's two tiers).
  `scripts/dev/campaign_log_archive.py <campaign> --follow` runs beside a campaign. It writes each
  cycle's window per container under the main checkout's `var/campaigns/<campaign>/logs/`: from the
  first run's start to the last run's end, with a margin.
  - A manifest names each file's window and sha256.
  - It marks a window **lost** when its container is newer than the cycle's first run, so an empty
    file never reads as a quiet cycle.
  - An ended cycle is archived once.

**Not built:** the package's size bound, the app's evolution with screenshots, and the squad's first
pass. All three are after the set, rendered from durable records (plan rev 9, §5a.4).

### 24al. One supervisor, whoever holds the seat (2026-10-03, §9.2, §9.5, §24ae, §24aj; ruled by the owner)

**The ruling.** The owner, 2026-10-03: "consider me or the crew as requiring the same need to
supervise. it shouldn't impact squad ops design." The supervisor's seat is one seat. Whether the
owner or the crew holds it is the record's actor on each ruling, not a distinction in SquadOps.

**What changed.**
- **One ruling bound.** `CampaignPolicy.crew_ruling_bound_s` and `owner_ruling_bound_s`, a crew
  first and the owner as fallback, become `ruling_bound_s`, the supervisor's.
  - The increment gate's (§24ae) and the plan gate's (§24aj) overdue rows are each written once,
    when that bound passes. Their binding carries the bound, not a seat.
  - The digest says "past its ruling bound".
- **Stored campaigns read as written.** A policy stored with the two seat bounds is read through
  `CampaignPolicy.from_stored`, its supervisor's bound being the first of them (the crew's). A
  terminal row needs no migration, and its control-log rows keep the seats they were written with.
- **A run start's ceiling (§24ai)** was "the holding campaign's owner ruling bound". It becomes one
  full lease, `lease_expiry_s`: a supervisor renewing past it fails the run unstarted. The ceiling
  no longer names a seat.

**What did not change.** The owner's own powers are authority, not supervision: creating a
campaign, the owner's word on a pause or an escalation, an abort (`campaigns:control`). They keep
their scope. A supervisor rules through `campaigns:supervise`, whoever it is.

**Consequence for the 2.0 set.** Who supervises is no longer a SquadOps decision. The 2.0 plan's
decision 2 (who supervises) and decision 6 (the crew's network path) are the supervisor's
concerns, not the framework's. The set claims supervision through the interface, and each
ruling records its actor.

### 24am. A restart takes up the campaign cycle it died inside (2026-10-03, §12a, §19 item 1, #1922; decided under the 2.0 charter)

**What §12a says, and what was built.** "awaiting ruling: the gate is open again"; "running an
increment: the run's ordinary recovery". As built, a cycle's sequence moved only through the
executor's in-process loop: its gate's poll and its run's execution. Both died with the process.
- A decision recorded after a restart was never acted on.
- A run in flight stayed `running`.
- The startup sweep said so ("approval alone will not resume it: approve, then squadops runs
  retry").

So every restart mid-cycle needed `runs retry` or `runs resume`, operator steps outside the
campaign's interface. Found by reading the code before #1803's restart diagnostic, which would
have found it after the exit shakeout and cost another shakeout round.

**As built:**
- **At startup** (`main._resume_campaigns`, after the drain and the re-hearing),
  `CampaignLaunchService.reattach` takes up each live campaign's launched cycle whose ending is not
  recorded. It reads the cycle's newest run:
  - **`running`:** resumed from its checkpoint, as `runs resume` does;
  - **`completed`:** re-entered at its gate, or at the cycle's end;
  - **failed, cancelled or paused:** left alone. The re-hearing or the owner acts on it.
- **`execute_cycle(…, reentry=True)`** is an adapter-internal keyword, like `execute_run`'s
  `forwarding_overrides`, and only the re-attach passes it.
  - A completed run at entry is not run again: the loop takes it from its gate.
  - The first gate of a re-entry reads a decision already recorded on it: no second system
    approval, and no re-submitted proposal. A gate still undecided is polled again: the gate is open
    again.
- **Only at startup, and only campaign cycles.** A later drain would find successor runs the
  process is already executing. A cycle no campaign launched stays operator-owned, as the startup
  sweep treats it.

**Not built:** a re-attach while the process stays up. A cycle stops inside a live process only
by the process failing, and the restart is what this answers. The proof live is #1803's restart
diagnostic, on the registered deploy.

### 24an. A run start refuses what a launch refuses (2026-10-03, §9.3, §24ai, #1928; ruled by the owner)

**What §9.3 said, and what it left open.** "Every cycle launch and every run start on the box refuses
while the supervisor holds the lease. Every launch also requires a quiet box." A run start read only
the lease (§24ai). The lease returns to the squad when the supervisor releases it or when it expires,
and a release did not require the models unloaded. So a crew model left resident was run beside by
the cycle's next run. At an increment gate that run is the framing run the ruling just approved: the
supervisor's own seam. The crew's blocking review of the 2.0 pre-registration (#1908) asked for this
case, "an expired lease with a crew model resident", to be refused testably rather than by operator
discipline. Found re-reading that review against the code. The owner chose option 1 of #1928's three:
the run start, not the release.

**As built:**
- **A run start waits on the launch's own verdict** (`launch_verdict`, read through the box reader):
  the supervisor's lease first, then the quiet box. `RunAdmission.await_box` reads the box reader's
  verdict, so one rule decides a launch and a run start, and the start refuses what the launch
  refuses.
- **A wait, not a failure** (§24l's rule, kept). The run stays queued and reads the box every 15 s.
  It starts once a launch would be allowed: the lease given back, and the crew's model unloaded.
- **Its ceiling is one full lease** (`lease_expiry_s`) of the campaign whose box it waits on: the
  holding campaign while the lease is held, else the run's own. Past it the run fails unstarted,
  with the verdict's reasons.
- **A run outside every campaign is refused at once** on a box that is not quiet. It has no lease to
  wait out, and its launch is refused the same way (the create route's 409).
- **Wiring:** the executor takes a `box_verdict` port. The composition root binds it late to the box
  reader, as it binds the launch drain.

**Not built:**
- **A release that refuses while the box is not quiet** (#1928's option 2). The run start's wait
  already covers a release and an expiry alike, so it would add a second mechanism for half the
  cases.
- **The quiet box stays model-only** (§24ai): the GPU's compute processes are still not read, and a
  crew session using a model the deploy declares reads as quiet. The pre-registration states both.

**Proven live (rebuild 18, 2026-10-03, 22:08:41–22:09:46 UTC):** with the lease released and
`llama3.1:8b` still resident, the framing run the ruling had approved stayed queued for 65 s, and
started 3.6 s after the unload (§24ai's deployed proof, step 4).

**Read before building:** nothing on the deploy loads an undeclared model mid-cycle. No embedding
model is installed, and no agent has logged an embedding call. Every campaign launch since #1802, each
made right after a cycle ended, passed the quiet check. So a squad run waits only on what the
check exists to refuse.

### 24ao. A restart leaves its runs, and a task asked again is answered (2026-10-03, §12a, §24am, #1929; placed in 2.0 by the owner)

**What #1803's restart diagnostic showed on rebuild 17.** §24am's re-attach took each interrupted run
up again, and every restart passed. The records showed two costs behind the passes:
- **A graceful stop was handled as a run failure.** The shutdown closed the pool, then failed every
  pending reply wait. The run read either as its own failure and wrote `failed`, which was lost only
  because the pool was already closed. Reaching an open pool, that write would record a restart as a
  failed run. The re-attach takes up only `running` and `completed`, so it would skip the run, and
  the campaign would spend a retry on a restart.
- **The re-attach dispatched the in-flight task a second time.** The agent was still working on the
  original. It takes one message at a time, so the copy arrived after the original had finished and
  replied, and the agent ran it in full. One framing task was sent three times, and the copies ran
  while the run's real next task shared the GPU (`cmp_e39d5b9c24c6`).

**As built:**
- **The executor is told first.** Shutdown calls `begin_shutdown()` before anything closes. A run
  interrupted from then on is left exactly as it was. Its failure is raised as a cancellation, so
  the cycle loop records no ending, and neither the release nor the finalization runs. The startup
  reaper frees the run's leases, and the re-attach ends the run.
- **A task a restarted runtime asks for again is answered.** Every dispatch carries the dispatcher's
  boot id. An agent keeps, for its last 16 finished tasks, the reply it sent and the boot it
  answered. The same task id from a different boot is answered with that reply, and the asker's boot
  is recorded. The same id from the same boot is that runtime's retry: `dispatch_with_retry` re-sends
  the identical envelope, and it runs fresh. A replayed failure is still the receiving runtime's to
  retry.

**Not built:** an agent restarted since holds no replies, and runs the task, as before. A task whose
original reply reached no one and whose agent has since restarted is run again: the cost before
this change, now only in that case.
- **Amended the same day: a proposal task is not recognised** (#1934, found on rebuild 18's
  `restart-at:at_proposal`). The replay keys on the task id, and only framing and implementation
  runs have deterministic ids (`task-{run}-{index}-{type}`, #811). A proposal run's ids are
  random, so its re-dispatched task is a new id, and the agent runs it again. The cost is time
  only: the original's reply is dropped as unknown, and the copy's reply answers the new wait.
  Deterministic ids for every workload are placed in 2.1.0.

### 24ap. A proposal is told what each frozen criterion asserts (2026-10-03, §7.3, §8.1, §9.1, #1938; found in the exit shakeout)

**What was built, and what it hid.** A promotion froze each new criterion as its id, test path and
verifier bundle (§8.1). The next proposal's launch carried those records, but the proposal prompt
rendered only the ids (`- `T3``), with no statement and no accepted increment's feature text. The
strategy role was told "do not break T3" and never told that T3 was the date sort.

**Found in shakeout 6** (`cmp_58d4e3b0a5d3`, rebuild 18):
- Increment 2 froze T3, "GET /runs returns runs sorted by datetime in ascending lexical order".
- Increment 3's first proposal asserted the same thing as T4.
- The supervisor returned it for revision (§9.4: a conflict with an earlier increment). Its
  version 2 proposed Tier 1 item 3.

In the counted set every increment after the first proposes against this context, and repeated
duplicates spend revisions and rejections until an increment is abandoned. That cost would be the
framework's context, not the squad's judgement.

**As built:**
- **The promotion freezes what a criterion asserts.** Each frozen record carries the criterion's
  `statement` and `surface` from the approved change request. The request is found through the
  increment's seed (`increment_seed`, which now names `change_request_ref`), the way every later
  workload finds it: the approved proposal run's promoted request. No seed or no stored request
  freezes ids only, on every attempt.
- **Amended the same day: the lookup is a function of stored data alone** (#1943, found from the
  crew's review of #1908). As first built, a read that failed degraded the record to ids only and
  let the promotion commit. A promotion's binding is part of the PROMOTE transition's replay identity
  (`transition_request_hash`). So a degraded attempt followed by a restart and a complete replay, or
  the reverse, was one key with two bindings. It was refused, and the campaign never decided. A
  failed read now fails the promotion attempt, as every other read in `_promote` does, and the
  re-hearing retries it.
- **Read against shakeout 6's real records first.** The first build read the request from the
  cycle's `plan_artifact_refs`. The live cycle row carries none, because the refs ride each run's
  forwarding, so it would have frozen ids only, and it passed a unit test that put the refs on the
  cycle. On increment 2's records the corrected read freezes T3's statement.
- **The proposal renders it.** Each frozen criterion shows as
  `- `T3`: <statement> (on `<surface>`)`. The request template says that each is something the
  application already does, and that restating one adds nothing a test can fail on before the
  change. A record frozen before this change renders by its id.

**Not built:** the accepted increments' `prd_delta` text. The criteria carry what a test checks,
which is what a duplicate needs to be seen. The feature prose beside them is a 2.4 question, for
when the squad authors its own backlog.

**The deploy it lands on (the owner's ruling, 2026-10-03):** rebuild 19 differs from rebuild 18 only
by this change. #1803's recovery diagnostics, 12/12 on rebuild 18, stand for it: no restart,
re-attach, kill or abort path changed. The exit shakeout re-runs on rebuild 19.

### 24aq. The proposer is told the rule a new criterion is judged by (2026-10-04, §8.2, §9.1, #1946; found in the exit shakeouts)

**What was enforced, and never said.** §8.2 requires every new criterion's test to fail on the
accepted tree and pass on the candidate. The increment's evaluation enforces it as discrimination, and
the supervisor's policy enforces it at the gate (#1908 §3a, "an observable a test could not check").
The proposal prompt stated it only for frozen criteria (§24ap).

**Seen live: two of the 2.0 shakeouts' three first proposals** carried a criterion the accepted app
already met, each the default case of the feature it added:
- shakeout 7's T2, "the second join to a capacity-2 run succeeds";
- shakeout 8's T3, "a run without capacity takes a tenth join".

Both were returned, and each version 2 dropped the criterion. A gate that polices a rule the author was
never given is a missing derivation. In the counted set it would also have measured a prompt gap as
the strategy role's proposal quality.

**As built:** the request template (v4) states the rule, shown with the shape that missed: a criterion
the accepted application already meets cannot be proven. "A run created without a capacity still
accepts a tenth join" is the example of what is not a criterion, and "a third join to a run with
capacity 2 is refused" the example of what is.

**The deploy it lands on:** a prompt asset in the agent images, so it needs a rebuild. Its only overlap
with a recovery diagnostic is the proposal run's content in `restart-at:at_proposal`, and that leg
re-runs on the new deploy. Shakeout 8 was stopped for it, and shakeout 9 is the exit run.

### 24ar. The proposer is told what an optional field left out comes back as (2026-10-04, §7.3, §8.2, §9.1, #1948; found in the exit shakeout, decided under the 2.0 charter)

**What the stack decides, and the proposal never saw.** The FastAPI stack's skeleton freezes every
optional entity field without a default as `<type> | None = None` (#1125), so a response returns a
field the request left out as `null`. The builder does not choose it. The proposal sees the manifest,
which says only `required: false`, and nothing it is shown says null rather than absent.

**Seen live: shakeout 9's first proposal** (`prop_58e5e58c3558` v1, rebuild 21). T1 asserted that a run
created without a capacity "returns a body with no capacity key". The delta defined `capacity`
exactly as the accepted `distance`, so a correct build returns `"capacity": null` and fails its own
criterion. The supervisor returned it (#1908 §3a, criteria not checkable), and version 2 asserted
`capacity: null`. This is §24aq's shape again: a rule enforced on the author that the author was never
given. Here the rule is the stack's frozen serialization.

**As built:**
- **The fact is the stack's, declared as data.** `ScaffoldStack.unset_optional_response` holds the
  JSON value its frozen models return: FastAPI `null`. A test builds the entity from the generated
  `backend/models.py` and holds the declaration to the bytes.
- **A stack that declares nothing tells the proposal nothing**, rather than another stack's
  convention. The Next.js stack freezes `field?: type`, which points to absent. It declares nothing
  until that is read from a real emission.
- **The prose is a request template of its own** (`request.proposal_unset_optional`), shown with the
  observable that failed and the one that is checkable. The proposal request is template v5.

**The deploy it lands on:** a prompt asset and the stack table in the agent images, so it needs a
rebuild. Its only overlap with a recovery diagnostic is the proposal run's content
(`restart-at:at_proposal`, and `abort-in-flight` where it lands in a proposal run). Both re-run on the
new deploy. Shakeout 9 does not satisfy the exit rule, and shakeout 10 is the exit run.

### 24as. §24b–§24i ratified; the eight unplaced items placed or ruled; the 2.2/2.4 sequence (2026-10-04)

**What changed.**
- **§24b–§24i, each marked "implementer's reading, not yet ruled", are ratified as written.** CLAUDE.md requires an amendment to name who ruled it, and these named no one until now.
- **The items unplaced at the 2026-10-04 audit:**
  - escalating a launch the cycle-create preflight refuses (§24e item 5): **#1971, 2.1.0**;
  - re-hearing an ended cycle between restarts (§24v): **#1972, 2.1.0**;
  - a Next.js render profile (§24p): **#1973, 2.1.0**, with #1950 and #1962;
  - an increment that needs packaging changed (§24y): **unplaced, deliberately**, re-placed on evidence;
  - whether an increment's build skips the builder tail (§24ab): **dropped as a question**, answered when a campaign raises it;
  - the quiet-box check reading GPU compute processes (§24l, §24ai, §24an): **unplaced, deliberately**, until the owner grants the runtime-api the GPU.
- **Downstream placements the same ruling made:**
  - 2.2 changes one squad behaviour, memory, beside #1708's auto tier and escalation queue;
  - the other judgement steps (#557, #949, #950) follow `SIP-Outcome-Evaluation`'s scenarios (2.4 or later);
  - `SIP-Outcome-Evaluation`'s feature half heads 2.4, and its §4.7 lands as an amendment to this SIP's §10 row 3;
  - the squad-authored backlog is 2.6.

**Evidence.** The read-only SIP-portfolio audit of 2026-10-04; this SIP's delivery ledger.

**Who ruled it.** the owner's rulings of 2026-10-04 on the SIP-portfolio audit (`sips/PORTFOLIO.md`): "yes, move them to 3.x including capability-backed agents. I accept all your other recommendations to keep SIPs current, reflecting what gets delivered, and where the work is targeted". The ratification of §24b–§24i, and the place-or-drop choice for each unplaced item, are the supervisor's readings of "I accept all your other recommendations"; the owner was told both when they were recorded.

---

## Revision history

- **Revision 6 (2026-10-01, late evening):** the crew's fourth review, which found revision 5 resolved its
  prior findings and named one contradiction: escalation both bypassed and obeyed the pausing guard.
  Revision 6 makes escalation unguarded, applies the guard only to guardable actions, and fixes the
  precedence (§10, criterion 12g).
- **Revision 5 (2026-10-01, late evening):** the crew's third review (Ripley, on #1798), which found
  revision 4 close and named bounded corrections, made here:
  - content-addressed verifier bundles, executed through the candidate-verifier overlay (§7.4, §8.1);
  - launch actions separated from control transitions (§10);
  - the outcome-aware failure producer, with its completion order (§14);
  - deterministic repair exhaustion (§10a).
- **Revision 4 (2026-10-01, late evening):** the crew's re-review of revision 3 (Ripley, on #1798),
  which confirmed revision 3 closed its seven blockers and named five more seams. Revision 4 closes them:
  - the held pending action and its resume (§10);
  - the repair and retry contract (§10a);
  - the launch outbox and idempotent cycle creation (§12b);
  - the single failure producer and its write point (§14);
  - criterion-owned verifier bundles and the fixture set (§8.1).
- **Revision 3 (2026-10-01, evening):** the crew's design review of revision 2 on #1798 (Ripley), with
  the owner's rulings on it:
  - the proposal as the increment cycle's first run, and the ruling as its gate (§9);
  - the ordered continuation table, with `wait` removed (§10);
  - the typed change request and the three trees, with the seam table (§7, §8.4);
  - the transactional control log as the authority (§13);
  - append-time evidence with a close-time projection, and per-failure records from `compose()` (§14);
  - restart by state (§12a);
  - the open questions answered (§23);
  - the dependency-ordered implementation (§18);
  - acceptance criteria with fail cases and named compatibility assertions (§19).
- **Revision 2 (2026-10-01):** the campaign evolves one app, from:
  - the owner's direction of 2026-09-28;
  - the owner's IDEA (`docs/ideas/nostromo-framework-optimization-crew.md`) and the rulings on it;
  - the Verification Yield review;
  - an external review of the plan.
- **Revision 1 (2026-07-04):** the neutral mechanic: an objective envelope and a pure continuation
  policy. Placements:
  - targeted v1.6;
  - retargeted to v1.8 on 2026-08-03;
  - billed as a co-headliner of v1.8 on 2026-08-07;
  - retargeted to v2.0, the headline, on 2026-09-12 (`docs/plans/1-8-0-plan.md` §8 decision 1).

---

## Appendix A — Implementation seams (non-normative)

- Models and the pure decision in a `campaigns/` package beside `cycles/`.
- The port at `src/squadops/ports/cycles/campaign_registry.py`; adapters under `adapters/persistence/`.
- The continuation choke point where a cycle reaches `CycleCompletion`, when the cycle has a
  `campaign_id`.
- `TaskType.STRATEGY_PROPOSE_INCREMENT`, the `proposal` workload type, and the `increment_ruling`
  gate, declared by a campaign increment profile.
- The quiet-box check and the lease gate beside the cycle-create preflight, and at the run dispatch.
- CLI: `squadops campaigns create|show|list|log|pause|resume|abort|lease`; rulings through
  `squadops runs gate`.

### 24at. Consolidated status at the v2.0.0 cut (2026-10-04)

**What changed.** This is the permanent record of where SIP-0109 stands at its first release. It
replaces the 2.0 plan's §5a, which the cut supersedes.

**Shipped in v2.0.0:**
- §18's eight steps, as §24a–§24ar record them: the campaign object and control log; the continuation
  decision; the increment proposal and its gate; the brownfield increment cycle; accumulated
  acceptance; repair, retry and the prior-cycle brief; recovery and its diagnostics; the box lease;
  the evidence package and digest; the reference scenario;
- after the set, the runbook's second half (#1997) and the digest's renderings (#1998).

**Measured** (`docs/plans/2-0-0-preregistration.md` §10, rebuild 22 `b09883c9`): two pre-registered
campaigns, each a calibration and three accepted increments. Both completed by row 3 with every
earlier frozen criterion passing on each later increment. Every safety guarantee held, both packages
were complete, and there was no owner action.
- P1, P2, P3, P6 and P7 held; P4, P5 and P8 were not exercised.
- **P9 is falsified:** two criterion files frozen at promotion add rules no approved request stated.
  The supervisor cannot see a criterion file at the gate, because it is authored after approval (§9.2).
  #1884 carries it to 2.1.0.
- §10's rows reached live: 3, 4, 8 and 9 in the shakeouts (the 2.0 plan §5a.1's #1800 row), and 5
  and 7 in the set. Rows 10–11 stay unreachable (#1824).

**Open, each placed in the ledger above:**
- **2.1.0:** #1824, #1884, #1934, #1950, #1961, #1962, #1995, the prior-cycle brief's remainder
  (#1692), #1940 (revises §24al), #1954, #1956, #1959, #1960, #1971, #1972, #1973;
- **#1710's remainder:** closed at the cut. The evolution screenshots are in the 2.0.0 release package,
  and the squad's first pass is **dropped**: the owner chose to drop it at the cut, so the digest and
  package carry a campaign's close;
- **2.2.0:** #1708's auto-decision tier and escalation queue (outside this SIP's scope, §5).

**Status: stays `accepted`.** CLAUDE.md's cut step 5: a phased SIP with open children stays accepted,
with the gap named. The gap is the 2.1.0 rows above.

**Evidence.** The pre-registration's §10 readings; the control logs of `cmp_c4b81554bd59` and
`cmp_97a4a15f360f`; the ledger above.

**Who ruled it.** The supervisor, as the owner's delegate under the 2.0 standing authority, read the
set by the pre-registration's frame. The cut itself (the tag, the Release and the records upload) is
the owner's consolidated approval.

### 24au. The rails refuse a behaviour change with nothing to build (2026-10-05, §7.2, §9.1, #1961)

**What changed.**
- **A new rail.** A `feature` or `fix` whose derived footprint holds no product file is refused,
  as `nothing_to_build`. Such a footprint holds only the qa test namespace's patterns, which an
  empty `manifest_delta` derives. The refusal returns to the proposer inside its task, as every rail
  does (§9.1). A `refactor` is unaffected.
- **The proposal request says what the manifest is** (template v6). The accepted manifest is what the
  application does: everything it declares is built, and a change is what `manifest_delta` adds or
  modifies.

**What it does not do.** A behaviour change inside an existing declaration (say, a declared error the
code misses) cannot be proposed, because the accepted manifest is accepted behaviour. The issue's
option 2 would admit the fill-slot files a criterion's surface names. It is not built: it widens what
a build may touch on the criteria's say-so, and would need its own argument.

**Evidence.**
- **The case:** the 2.0 set's campaign 1, increment 2, `prop_5fb2d8136c36` v1 (`kind: feature`,
  `manifest_delta: []`). Its footprint was the qa namespace alone. It passed every rail, and the
  supervisor returned it for another reason: capacity was already declared, so already built.
- **The replay:** every stored change request carrying a stored proposal context, 40 of them, went
  through the new rails. 39 accept with their stored footprint unchanged. The one refused is that v1,
  which was never approved.
- **The 7 other stored requests** are the reference scenario's seeded request. Its footprint holds
  four product files.

**Who ruled it.** The owner's approval of the 2.1 plan (§7 item 1, 2026-10-04), which takes the
issue's recommended option 1.

### 24av. The proposer is told every convention its stack's frozen code decides (2026-10-05, §7.3, §8.2, §9.1, #1962, #1950)

**What changed.** §24ar told the proposer one convention, FastAPI's `null` for an optional field left
out. That declaration is generalized and replaced:
- **One mechanism:** `frozen_conventions_for(stack)` returns `FrozenConvention`s, each a kind and the
  values its asset renders. `ScaffoldStack.unset_optional_response` and
  `request.proposal_unset_optional` are gone. The prose is one asset per kind,
  `request.proposal_convention_<kind>`, under `request.proposal_frozen_conventions`. The proposal
  request is template v7.
- **FastAPI declares four:** an optional field left out comes back as `null`; a required request
  string is trimmed, and refused with `validation_error` when blank (#593); a declared
  `success_status` is pinned in the route decorator (pf-39); and every contract error comes back as
  the frozen envelope.
- **Next.js declares two:** the value an optional field left out comes back as is **not fixed**
  (#1950), and the frozen error envelope.
- **No fact gets a second author.** The pinned status derives from `skeleton_pins_success_status`, and
  the envelope from `error_seam`. The other kinds are the stack's own `frozen_conventions`.

**Evidence.**
- **The second instance:** the 2.0 set's campaign 1, increment 2, v2 proposed name trimming (T3, T4)
  that the frozen `NonBlankStr` already did. It was returned `criteria_not_checkable`.
- **#1950's read** (the issue's comment of 2026-10-05). The Next.js scaffold freezes no response
  construction. Of the 225 distinct stored `POST /runs` handlers, 187 leave the field out, 17 return
  `null`, 17 return `""` and 4 never handle it, and all three representations occur in runs that
  completed.
- **Each convention is held to the generated bytes in both directions:** declared exactly where the
  stack's tree shows it (`TestFrozenConventionsHoldOnTheBytes`).

**Who ruled it.** The owner's approval of the 2.1 plan (§7 item 2, 2026-10-04).

### 24aw. The proposer is told a PRD delta states only what the request delivers (2026-10-05, §9.1, #1995)

**What changed.** The proposal request (template v8) says that `prd_delta` states only what the
`manifest_delta`, criteria and footprint carry. Its example is the stored case below. **No rail is
added.**

**Why no rail.** The disagreement lives in prose. A deterministic predicate needs a typed link from
each PRD delta item to the manifest entries and criteria that carry it, which is a change to the change
request's schema (§9): a design change, not a 2.1 fix. Through 2.1 the supervisor reads every PRD delta
(#1908 §3a). The typed link is recorded on #1708, because the auto tier (2.2) is when nobody reads them.

**Evidence.** The 2.0 set's campaign 2, increment 1, `prop_450986544201` v1. Its PRD delta stated
"show capacity status in run detail". Its manifest delta changed no client route, no criterion named
the detail view, and its footprint held no view source. The supervisor returned it
(`ambiguous_manifest_delta`), and v2 narrowed the text.

**Who ruled it.** The owner's approval of the 2.1 plan (§7 item 3, 2026-10-04), which decides
template-only.
### 24ax. Every author of an increment's tests is held to the owner's rule (2026-10-05, §8.1, §8.2, #1884, part 1 of 2)

**The rule (the owner's, recorded on PR #2010 and in the 2.1 plan's §5 ruling 13):** "a QA author
may add tests only for behavior already required by frozen criteria or another explicitly accepted
artifact. Unsupported desirable behavior must be returned as a proposal, not encoded in a test that
gates or repairs the current run. Test-file placement does not alter the rule."

**What changed (part 1: the rule reaches every author).**
- **One asset, `request.increment_test_scope_appendix`,** states the rule, with campaign 1 T1's tie
  order as the example, and lists the criteria the increment is held to. #1886's narrower section
  left `request.plan_increment_criteria_appendix` (v3), so the rule has one author.
- **One key, `increment_test_scope`:** the approved criteria (id, statement, observable) and the
  frozen criteria's statements, composed by `increment_test_scope` from the change request and the
  launch's pins. It is present for every increment, a `refactor` with no criteria included.
- **Its readers:**
  - the plan authors, through a new `INCREMENT_SURFACES` entry (the dev and qa proposers, and the
    merger's sole-author fallback);
  - `qa.test`, by a new context-contract property, `increment_test_scope`;
  - `qa.test_repair`, by `REPAIR_PRESENCE_KEYS`, because the correction loop builds a repair's
    envelope and forwards nothing else. It renders through `request.cycle_repair_task` v12. A dev
    repair of the same failure is not shown it: the rule is the QA author's.

**Part 2** is the proposal outlet: `proposed_behaviours.yaml`, stored and never run, shown to the next
proposal (the 2.1 plan, §7 item 4).

**Evidence.**
- **The set read P9 falsified:** campaign 1 T1's tie order and campaign 2 T4's non-mutation were
  frozen with their criteria.
- **#1886's rule never reached the author who wrote them.** It rendered only to plan authors, and
  only when the change had criteria. An implementation run's `qa.test` was handed nothing of the
  change request (`_increment_inputs` returned `{}`).
- **Mutation:** each of the four seams (the repair forwarding, the contract property, the planning
  surface, the repair template variable) fails its test when removed.

**Who ruled it.** The owner, on PR #2010 (2026-10-05): the rule, its application to both the
planning and `qa.test` paths, and its acceptance criteria. The supervisor built it to the plan's §7
item 4.

### 24ay. Behaviour a qa author would test but nothing accepted requires is returned as a proposal (2026-10-05, §8.1, §9.1, #1884, part 2 of 2)

**The rule's other half** (the owner's, §24ax): "Unsupported desirable behavior must be returned as a
proposal, not encoded in a test that gates or repairs the current run."

**What changed: the proposal outlet.**
- **Who may emit it.** Only `qa.test` in an increment's implementation run, told how by
  `request.qa_test_proposed_behaviours_appendix`, which renders beside the rule. `qa.test_repair` is
  not given it. A block in a repair's emission is kept out of its artifacts and named in its evidence
  (`proposed_behaviours_ignored`).
- **The contract:** one fenced `proposed_behaviours.yaml` block with a top-level list of 1 to 10
  entries, each with exactly `behaviour`, `why`, `surface_kind` (`endpoint` or `client_route`) and
  `surface`, none blank. `squadops.campaigns.proposed_behaviours` parses it.
- **Where it goes.**
  - Extracted as type `qa_proposed_behaviours`, never `test`, so the suite never runs it and the stub
    check never reads it.
  - **Malformed:** a validation row that a self-evaluation pass returns to the author. If the block
    is still malformed when the passes run out, it alone is dropped, the evidence says why, and the
    row goes, so the verdict is the tests'.
  - **Valid:** stored once, normalized.
- **Never in a tree.** Three readers exclude it: the delivered tree's allow-list already did; the
  correction runner's retest deny-list and `failed_task_artifacts`, which forwards a failed task's
  files to its repair and the verifier's overlay, now name it. The last one is a reader the plan's
  seam table did not list.
- **The next proposal.** `_propose_launch` reads the entries stored on the accepted cycle and, for a
  proposal replacing an abandoned increment, on that one. They go into the launch block as
  `qa_proposed_behaviours`, deduplicated, at most ten. The read is a function of stored data alone
  (#1943's rule): a failed read fails the launch attempt and is logged, and no degraded launch is
  written. `request.proposal_qa_proposed_behaviours` renders them for the proposer (template v9).

**Evidence.** Each of seven seams fails its test when removed:
- the retest deny-list;
- `failed_task_artifacts`;
- the extraction typing;
- the row's removal after the passes;
- the repair's exclusion;
- the launch read;
- the proposal render.

**Who ruled it.** The owner, on PR #2010 (2026-10-05), and the 2.1 plan's §7 item 4, which specifies
the contract.

### 24az. The supervisor creates and manages a campaign; escalations and limit pauses stay the owner's (2026-10-05, §13, §24al, #1940; the owner's scope request)

**What §24al said.** "The owner's own powers are authority, not supervision: creating a campaign,
the owner's word on a pause or an escalation, an abort (`campaigns:control`). They keep their
scope." Only `admin` held that scope, so the owner launched every campaign.

**What changed.** A new scope, `campaigns:manage`, held by `admin` and `campaign-supervisor`:
- **it covers:** create, start, abort, materializing the package, and resuming a pause the
  supervisor made;
- **`campaigns:control` stays the owner's alone,** and the resume route requires it when the
  campaign is escalated, paused by a limit (§9.5: such a pause "resumes only on the owner's
  recorded word", unchanged), or paused by the owner;
- **which one is read from the row that held the campaign** (`owner_held`, `campaigns/progress.py`),
  never from the request. A supervisor asking for an owner's resume is refused 403
  (`OWNER_AUTHORITY_REQUIRED`) before anything is written. A resume in any other state is nobody's
  hold, and is refused as stale and recorded, whoever asks (§12a, unchanged);
- **every row still carries the token's actor and role,** so a supervisor's create, start or
  abort reads as the supervisor's.

**One reading the issue left open, decided here.** A pause the *owner* made is the owner's hold,
and the supervisor does not lift it. The issue's words were "resume a campaign the supervisor
paused"; the reverse reading would let the supervisor undo the owner's brake.

**Evidence.** Route tests through the real authorization adapter, each failing on main:
- the supervisor creates, starts (through the real launch service), pauses, resumes its own pause,
  aborts and materializes a package, and each row names it;
- the supervisor resuming an escalation, a limit's pause or the owner's pause is refused 403 with
  nothing written, and the owner's resume of the same campaign then proceeds;
- the read-only seats still steer nothing.

**Who ruled it.** The owner, 2026-10-03: "I think I need the campaign supervisor granted the
ability to create and manage campaigns", "keep escalations with me", and "keep limit pauses with
me". Kept in 2.1 as its one feature exception, bounded to these operations (the 2.1 plan, §5
rulings 2 and 13).

### 24ba. A launch the cycle-create path refuses escalates to the owner (2026-10-05, §12a, §24e item 5, #1971; placed by the owner's portfolio rulings, Q17)

**What §24e item 5 said.** "Not built: escalating a launch the preflight refuses. Such a launch
stays pending and is logged." Every later drain refused it again, logged and unasked, so an
unattended campaign stalled with nothing asking the owner. A refused intent also raised out of
the launcher's drain, so the pending intents queued behind it in the same drain waited too.

**What changed.**
- **What counts as a refusal:** what the cycle-create path refuses as a client error, its 4xx
  (`cycle_error_envelope`): a preflight block (SIP-0095), a project or profile that does not
  exist, a request it cannot validate. The launch service raises `LaunchRefused` for these. Any
  other failure is a fault: it propagates, the intent stays pending, and the next drain repeats
  it, as before.
- **A new operation, `launch_refused`** (migration 1695): the campaign moves to `escalated` with
  the intent still pending. The row's binding names the launch, the state it was written from and
  the refusal, cut to 500 characters. It is keyed by the launch and its refusal count, so a drain
  that dies before the row commits replays it, and a refusal after the owner's resume is a new row.
- **The owner's word:** a resume without an action returns the campaign to the state the launch
  was written from and drains at once. The launch goes ahead if what refused it is fixed, and
  escalates again if not. A resume naming an action is refused (422): it would write a second
  launch beside the pending one. Abort is unchanged.
- **The digest asks the right question** for each kind of launch escalation: a refused launch
  names its refusal, and a blocked one its attempts. Both say to resume without an action. It had
  told the owner to name an action and quoted "§10 row None" for a blocked launch's escalation,
  a gap found here and fixed with it.

**Evidence.** Entered at the start route with the real launch service: the preflight refuses,
the campaign escalates with one `launch_refused` row and the intent pending, a second drain asks
nothing again, a resume naming an action is refused, and once the refusal is lifted the owner's
resume launches the cycle. A transient fault leaves the campaign unescalated. Each test fails with
the launcher's or the digest's change reverted.

**Who ruled it.** The owner, on the SIP-portfolio audit (2026-10-04, queue Q17), placing #1971 in
2.1. The rule that a resume of a launch escalation names no action follows §9.3's for a blocked
launch (#1802).

### 24bb. The digest scores each increment, from the package alone (2026-10-05, §14, #1960)

**What changed.** The morning digest gains a **Per increment** table, computed by
`squadops.campaigns.scorecard` from the package's records and nothing else, so the same arithmetic
reads a replay and its original (#1959). For each increment launch, with any repair or retry cycles
it launched before the next increment:
- elapsed time (from the launch to the last decision), split into executing (the cycles' run wall
  clock) and waiting (the rest);
- tokens, by task-type family, and the qa share (verification's cost, SIP-Verification-Yield §17);
- LLM calls, correction rounds, proposal rounds with each ruling, repair and retry cycles, criteria
  added, and the outcome (accepted, abandoned, rejected or open).

It is reporting only: no verdict, decision or prompt reads it. It is computed when the digest renders
and is not stored in the package, which keeps only records.

**Not split yet, and why.**
- **The cause of a wait** (ruling, gate, box) needs per-run starts and the box's persisted `waited_s`,
  and neither is in the package.
- **Test-file churn and test-check correction rounds** need the vault and the correction ledger.

**Evidence.** The 2.0 set's campaign 2 package reads as its record says: three increments accepted,
the first on its second version (v1 returned, v2 approved), with waiting of 2 to 4 minutes per
increment.

**Who ruled it.** The owner's adoption of the 2.1 plan (§2.0, the crew's enablers), and the folding of
Verification Yield's cost measures into this table (2026-10-04).

### 24bc. A rewind the model's limits chose is a patch (2026-10-05, §10, §10a, #1757; ruled by the owner)

**The question #1723 left.** The same classification and equivalent evidence had chosen `patch`
once and ended the run twice. A `rewind` is implemented as run death, so for an unattended run it
discarded every correction attempt the run had left, and the campaign then had to read a failed
cycle where a repair was still possible.

**What changed.** A third anchor in the deterministic correction policy
(`correction_policy.py`), beside #994's and pf-45's: a `rewind` on a `model_limitation`
classification, with the repair slot unspent, resolves to `patch`. A run that still ends is
absorbed at cycle level by the campaign's repair and retry rows (§10a), as before.
`execution`, `alignment`, `decision` and `contract_compliance` rewinds stand.

**The override is now durable.** It rode only the `CORRECTION_DECIDED` event and the log, so the
measurement below had to infer "an anchor fired" from the artifact that followed. Every override
is now recorded on the run's loop summary (`path_overrides`: the task, the round, the proposed
path, the path taken, the anchor), which the run persists at finalization. A summary written
before this reads `None`, not "no overrides".

**Evidence.** The deploy's 737 stored correction decisions, read on 2026-10-05 (posted on #1757):
all 7 model-limitation rewinds ended their run, each with repair budget left, and 25 of the 30
model-limitation rounds that resolved to `patch` went on to complete. Entered at `execute_run`, a
model-limitation analysis and a rewind decision now take the patch path, and the run's summary
carries the override. Both tests fail with the anchor reverted.

**Who ruled it.** The owner, on the 2.1 plan (§5 ruling 4, 2026-10-04): "run death is not the
meaning of `rewind` for an unattended run", the stored decisions read first. The
contentless-builder diagnostic follows: it now reaches its failure through the patch path every
time.

### 24bd. A Next.js increment's pages are read, and a page written as the API writes it is seeded (2026-10-05, §8.3, §24p, #1973; the owner's portfolio rulings, Q17)

**What §24p left.** Route rendering needs a stack's `render_profile`, and `nextjs_ts` declared
none, so every declared route of a Next.js increment read `blocked_unverified`. A route-declaring
Next.js increment could never be promoted.

**What changed.**
- **A render profile for an app that serves its own pages** (`next_start`). The app is stood up by
  the stack's probe profile, prepared first within the probe profile's own limit (`npm install`
  and `next build`, #827), then started with `next start`. Pages are read from that port, and no
  frontend is started beside it. `render_routes` now takes the probe profile itself, so its
  preparation, boot and readiness path come from one source.
- **A page's parameter is read either way a manifest writes it**: `:run_id`, or `{run_id}` as the
  API writes it. Both the Next.js manifests and the React roll manifests write `{run_id}`, so on
  main such a page was never seeded and was read at its literal path. **On both stacks.**
- **A page's collection is matched under the API's base path** when the manifest writes its
  endpoints there (`/api/runs` for `/runs/{run_id}`, as Next.js's do). The seed posts to the
  endpoint as written.

**Evidence.** The delivered tree of `cyc_025e085a22b1` (the 2.0.0 Next.js regression, accepted
2026-10-03) was rendered in the qa container with this code, and judged by `route_rendering`:
- `/` and `/runs/new` held;
- `/runs/{run_id}` held after its seed (`POST /api/runs`, 201).

Before the base-path and parameter changes, the detail page read `blocked_unverified`. Unit tests
cover both stacks' real manifests (React roll 4 and that Next.js regression), the build-then-serve
order, and a build that fails.

**Who ruled it.** The owner, on the SIP-portfolio audit (2026-10-04, queue Q17), placing #1973 in
2.1 with #1950 and #1962.

### 24be. A page's collection is found where the manifest wrote it, under base_path or under a prefix in each path (2026-10-06, §8.3, §24bd)

**What §24bd left.** §24bd matched a page's collection at the path itself (`/runs`) or under the
API's `base_path`. Next.js manifests write their API a second way: `base_path` empty and `/api`
written into each endpoint path. 2.1 rebuild 2's Next.js regression (`cyc_d94c3742bb88`) did,
as rebuild 1's did. Its detail page had no seed, was never read, and the boot audit (#1796) failed
on it: `route-render /runs/{run_id}: not read (blocked_unverified)`. A campaign's increment
evaluation reads seeds the same way, so a Next.js increment of that shape could never be promoted.

**What changed.** When neither match exists, the collection is the one create endpoint whose
path is the collection under leading segments (`/api/runs` for `/runs/{run_id}`). When none is,
or more than one is, the page stays unseeded and reads `blocked_unverified`, never guessed.

**Evidence.** The boot audit was replayed through the same invocation on the roll's delivered app.
On main it failed as above. With this change it passed, and all three declared routes rendered their
views, the detail page seeded at `POST /api/runs`. The roll's stored manifest is a test fixture beside
§24bd's two. Reverting the match fails that case, and accepting an ambiguous match fails the
ambiguity case.

**Who ruled.** Found by rebuild 2's regression pair (#2084); a gap in §24bd's own rule ("a page written as
the API writes it is seeded"), fixed to that rule.
### 24bf. The prior-cycle brief's remainder: the correction chain round by round, and whether what it showed recurred (2026-10-05, §10a, §14, #1692; placed in 2.1.0 by the owner's ruling of 2026-10-03)

**What §24u left not built:** two of #1692's items after the proposal run's brief shipped.
- **The correction chain's own record.** "What each round tried, and the patches it refused. The
  brief carries the round counts, not their content." A recovery cycle could learn that three
  rounds ran. It could not learn that a repair of `backend/routes.py` had already been tried and
  refused, so it was free to try it again.
- **The recurrence measure.** "Whether a failure class recurs within the campaign after the brief
  is shown."

**As built:**
- **The rounds** (`campaigns/prior_cycle.correction_rounds`) come from each run's loop summary
  (SIP-0108 §4.1), never a narrative. Each round carries the task that failed (its type) and the
  checks that failed it. Each repair of that round says whether it was kept, what it edited, and,
  when refused, the reason its form recorded. The round also says how the task moved afterwards.
  Repairs join their round by the index their task id carries
  (`adapters/cycles/correction_ids.py`, before and after #1697's sequence). The brief adds
  `correction_rounds`, and `correction_ended` (the chain's termination reason) when the chain
  was terminated. A row written before rounds were recorded shows none, never a guess.
- **The campaign reads them** where it builds the brief (`_prior_cycle_brief`): the failed
  cycle's runs, each run's stored loop summary.
- **Rendered** through the same managed asset, `request.prior_cycle_brief_appendix` (v2):
  "What each correction round tried", one line per round. The asset adds: "A repair that was
  tried and did not clear its check is a direction already taken."
- **The recurrence measure** (`campaigns/scorecard.brief_recurrence`) is per recovery cycle
  shown a brief. Of the checks the brief listed as failed, it records which failed again
  (`recurred`) and which did not (`cleared`). It is `unread` when the recovery cycle's own failed
  checks were not observed: an absence is never read as cleared. The digest's scorecard shows it
  under the per-increment table. It is reporting only: no decision reads it.

**Not yet read on real data.** No stored campaign has launched a repair or retry with a brief: the
2.0 set's two campaigns had none. The measure first reads on the 2.1 line's campaigns. The round
record was rendered from stored loop summaries (`run_33a98e71a7c8`, `run_a1e8f6dab695`, rows
whose chains ended `plan_defect`), so its text is the text a successor would be shown.

**Who ruled it.** The owner placed #1692 in 2.1.0 (2026-10-03, the 2.0 plan rev 9, §5a.5). Its
items are the issue's own list. This builds the two §24u recorded as not built.
### 24bg. The retry rows read the attribution, and an ending outside the work is declared (2026-10-05, §10 rows 10–11, #1824; ruled by the owner)

**What §10 wrote, and why it never fired.** Rows 10 and 11 read `latest.verdict = rejected` with
`attribution.primary = environment_or_infrastructure_failure`. No cycle produced that reading:
- a run that fails on infrastructure reaches no verification summary, so its verdict is
  unaskable, not `rejected`;
- nothing declared such an ending. It was recorded as `other` and read `unattributed`.

Of the 156 stored failed cycles read through `cycles assess` (2026-10-03, comment on #1824), none
read the environment class. So every failure outside the work escalated to the owner (row 14).

**What changed.**
- **Rows 10 and 11 read the attribution, not the verdict:** a cycle that is not accepted, not
  `blocked_unverified`, and whose primary attribution is `environment_or_infrastructure_failure`
  is retried while retries remain, and escalated after. This includes a failed run with no
  verdict. `blocked_unverified` keeps rows 8 and 9, ahead of it.
- **The ending is declared where it is unambiguous** (SIP-0108 §10q): the box refusing a run past
  its admission bound (`RunAdmission.await_box`), and the queue refusing a dispatch (a
  `QueueError`, now declared on the queue port). Both record the terminal kind
  `infrastructure_failed`, which reads `environment_or_infrastructure_failure`.
- **A task timeout is not declared one.** The model may still have been working (#995: a
  timeout read as a dropped generation pointed everyone at the wrong layer), and a retry would hide
  a defect in the work. It stays `other`, so it escalates, as before.

**Evidence.** `tests/unit/campaigns/test_retry_on_infrastructure.py` enters at the admission wait
and the executor's terminal mapping, and reads the run's stored summary through the real
assessment into the decision: row 10, then row 11 with the retry spent. A task timeout and an
unexpected error stay `other`. Each of the five changes was reverted in turn, and a test failed
for each.

**Who ruled it.** The owner, 2026-10-05, on the recommendation in #1824: option 1 (the rows read
the attribution) with the producer, since option 1 alone would still never fire.

### 24bh. The retry rows are asked before the blocked rows (2026-10-06, §10 rows 8–11, #2101; ruled by the owner)

**What §24bg wrote, and what the live path did.** §24bg kept rows 8 and 9 ahead of rows 10 and 11,
on the premise that "a run that fails on infrastructure reaches no verification summary, so its
verdict is unaskable". The live path disproved the premise. Finalization records a verification
summary for every run that reaches it (`run_completion.py`, `record_run_verification_summary`). A
failed run that verified nothing aggregates to `blocked_unverified` (SIP-0096, #388).

So on the final deploy's diagnostic (`cmp_a17471e90130`, 2026-10-06), the increment's framing run was
refused by a box held past one lease, and three readings followed:
- it ended `infrastructure_failed`;
- the cycle's attribution read `environment_or_infrastructure_failure`;
- its verdict read `blocked_unverified`.

Row 8 fired first. Its repair had no approved implementation plan to work under, so it built nothing
and the campaign escalated. #2080's wiring test had modelled the refused run with no verification
summary, a shape the live path never produces.

**What changed.** Rows 10 and 11 are asked before rows 8 and 9. A cycle whose primary attribution is
`environment_or_infrastructure_failure` is retried while retries remain, and escalated after,
whatever its verdict, unless it was accepted. Without that attribution, `blocked_unverified` keeps
rows 8 and 9. The rows keep their numbers, which the control log records. Only the order in which
they are asked changes.

**Not changed:** a calibration cycle that is not accepted still ends the campaign (row 2), whatever
its attribution. A calibration refused by the box therefore ends its campaign in failure rather
than retrying. That is left as it is, and named here so that it is a decision, not a gap.

**Evidence.**
- `tests/unit/campaigns/test_retry_on_infrastructure.py` enters at the admission wait and the
  terminal mapping. It takes the verification summary that finalization's own aggregation
  (`RunCompletion._aggregate_verification`) records for a failed run, and reads both stored
  summaries through the real assessment into the decision: row 10, then row 11 with the retry spent.
- With the old order restored, four tests fail: the wiring test, the direct precedence case, and the
  two continuation-table rows for `blocked_unverified` with the environment attribution.
- The diagnostic's own reading is the live evidence: `box-held-past-the-lease` FAIL on
  `cmp_a17471e90130`, with "the continuation was row 8 (repair), not row 10 (retry)".

**Who ruled it.** The owner, 2026-10-06, on the recommendation that followed the diagnostic's failure
(reorder the rows, abort the diagnostic, rebuild with the fix alone, re-run): "go with the recommended
sequence".

### 24bi. A return names what went wrong, or says that nothing fits and why (2026-10-08, §9.2, §9.4; the 2.2 plan's D2, adopted by the owner 2026-10-07)

**What §9.4 wrote, and what the record held.** §9.4 has the supervisor classify what went wrong with
each returned or rejected proposal, and the tooling records it as a separate `classify` row,
accepted at any time, even after the campaign ends. Nothing tied the class to the ruling. Of the six
historical returns, three carry their class only in the ruling's prose. The runbook told the
supervisor to name the nearest class when none fitted, which forces a novel defect into a wrong class.
SIP-0110 observes each returned proposal by its class (§0.4), so a return without one is observed as
`unclassified` with nothing to say why, and the repeat report cannot read it.

**What changed.** A ruling at the increment gate that returns a proposal (request revision, or reject)
carries its classification:
- one of §9.4's five classes; or
- `unclassified`, with a rationale saying why none fits. A novel defect stays returnable without
  being forced into a class.

A return with neither is refused with a 422, before any row is written. So is a rationale beside a
class (a class's reason is the ruling's own notes), an unknown class, and a class on an approval,
which has nothing wrong to name. The class rides the ruling's own `rule` row (`classification`,
`classification_rationale` in its binding), in the transaction that records the ruling. The CLI takes
`--classification` and `--classification-rationale` on `squadops runs gate … progress_increment_ruling`.

**Not changed:**
- the five classes;
- the `classify` route, which still records a later reading of a version. SIP-0110's projection reads
  the ruling's class together with any later reading, so a later reading can class an `unclassified`
  return;
- an approval's ruling.

**Evidence.**
- `tests/unit/api/test_increment_gate_route.py`, entered at the gate route: a return or rejection with
  no class, `unclassified` without a rationale, an unknown class, and a class on an approval are each
  a 422 that writes no `rule` row and no gate decision. A classed return, an `unclassified` one with
  its rationale, and an approval each record exactly that on the `rule` row.
- `tests/unit/memory/test_observations.py`: the observed class is the ruling's, joined by any later
  reading; an `unclassified` return keeps its rationale; a ruling from before the rail stays
  `unclassified` with "no classification of this version was recorded".
- `tests/unit/cli/test_commands_runs.py`: the flags reach the request, and another gate refuses them.

**Who ruled it.** The owner, 2026-10-07, adopting the 2.2 plan with D1–D15 as written. D2: "a
`ProposalClassification` class or an explicit `unclassified` with rationale; a return with neither is
refused (a SIP-0109 rail and amendment)".

### 24bj. The plan-review tier and the escalation queue (2026-10-08, §9.2, §9.5, §10, §24ad, §24ae, §24aj, #1708; the policy ruled by the owner)

#1708 asked for three things: a declared policy that decides an unattended cycle's review gate inside
the objective's scope, with the decider recorded; an escalation that queues instead of holding the
box; and no gate that waits without bound. §24aj bounded the wait with a record, and nothing more. The
2.2 plan (§2.2) placed the rest here, and the owner ruled the policy on 2026-10-08.

**The ruling.** The owner, 2026-10-08, accepted the four recommendations put to them ("yes to 1 and 2,
go ahead"):
1. **The tier may approve, and nothing else.** A rejection, a return or an answer to a question is
   never the tier's. Anything it cannot approve escalates.
2. **An approval needs every condition below.** Any one missing escalates.
3. **An escalation waits the campaign's `ruling_bound_s`.** When the bound passes, the increment is
   parked, unaccepted. The campaign continues with independent work, or ends with its completed and
   unresolved work kept apart.
4. **An answer that comes after the campaign closed** is recorded against its escalation and read at
   the next campaign's admission. It never reopens a closed campaign.

**What the tier adds, read against today.** A design-bearing plan gate already passes on its own when
its manifest asks no question (`system:no_open_questions`, #807, `adapters/cycles/workload_gate.py:263`),
after plan validation and the manifest's schema and winnability gates. A plan gate stops for a person
only when the design asks a question, as `cmp_dae2cd6b0e3c`'s calibration asked its runs-list ordering.
So **the tier approves nothing the pass-through would not.** It grants no new authority. What it adds:
- **two conditions the pass-through never checked:** the plan stays inside the objective's scope, and
  the framing ran once. In a tier campaign, a plan that fails either escalates where a supervised
  campaign passes it unread;
- **the escalation queue and its bound,** so a question nobody answers parks its increment instead of
  holding the campaign.

**The policy (normative).**
- **Its gate:** `progress_plan_review` on a campaign's cycles (calibration, increment, repair, retry).
  The increment gate stays the supervisor's (§9.2). Approving a proposal would need checks that do not
  exist yet (the 2.2 plan §2.2: unsupported added scope, omitted obligations, already-satisfied
  criteria, and others).
- **Its conditions, all required:**
  1. plan validation passed at this gate (the existing rails, `framing_gate_check`);
  2. the manifest's schema and winnability gates passed;
  3. no unresolved question remains once §24ad's answers are applied;
  4. **the plan's footprint is inside the objective's `allowed_scope`.** The footprint is the union of
     its tasks' `expected_artifacts`. An increment, repair or retry is held to it. **A calibration is
     not:** it builds the baseline the scope is read against, and its plan names the builder's own
     `assembly_notes.md` at the root. Both of this line's calibrations do (`cyc_41679341d038`,
     `cyc_17cd76a351a0`), and all three of its increments were inside scope;
  5. the cycle's framing ran once. A re-rolled framing (`workload_gate.py:201`, under
     `max_framing_rerolls`) escalates, because plan validation already refused one of its plans.
- **The decider is recorded:** `decided_by = system:plan_review_tier`. The decision's notes name each
  condition and what it read, so the row says why, not only who.
- **Declared, never defaulted.** `CampaignPolicy.plan_gate` is `supervised` or `tier`. A definition
  that does not declare it is refused at creation, as every other policy field is. A campaign stored
  before this reads `supervised` (`CampaignPolicy.from_stored`). **`supervised` is today's behaviour,
  unchanged:** the pass-through, §24ae's and §24aj's overdue rows, and a wait that only a ruling ends.
- **Pure:** the tier reads the gate's evidence and the campaign's record, never mutable memory
  (SIP-0110 §7, §0.8).

**Its activation is held until the measurement window closes** (the 2.2 plan's D3). 2.2 builds the
tier, and no campaign declares `tier` before the window closes. The window's experiment manifest
records each campaign's `plan_gate`. Two reasons:
- authority comes from a declared policy, and that is read in a shakeout before it is relied on;
- **the tier changes what memory observes.** A plan the tier approves is never observed as a rejection,
  and a parked one is not observed at all (below).

The cut's campaign shakeout declares `tier`. It is read for one thing: every case the policy does not
cover escalated.

**The escalation (normative).**
- **Opened** when a tier campaign's plan gate is not approved by the tier. It is one row, keyed by its
  identity: the campaign, the cycle, the run, the gate, the proposal and its version (none for a
  calibration), the accepted baseline's identity, and the plan's (its manifest's and its
  implementation plan's content hashes). Opening is idempotent: a row with the same identity is the
  same escalation. It carries the conditions that failed, the open questions verbatim, and its opening
  time.
- **Its states:** `pending`, then exactly one of:
  - `resolved`: a principal decided the gate before the bound, whatever the decision. An approval with
    blank notes on a question answers nothing (§24ad), so the escalation stays `pending`;
  - `expired`: the bound passed with it pending;
  - `cancelled`: the campaign was aborted or stopped while it was pending;
  - `superseded`: the gate it was opened for is no longer the one waiting, for example after a
    supervisor's return re-framed the cycle.

  Each transition is compare-and-set from `pending` and is recorded with its actor and time. A
  transition that loses a race is refused and recorded, as §24ae's rows are.
- **While one is pending, the campaign holds at that gate.** Any other increment would start from the
  same accepted baseline as the pending one, so nothing else launches. The hold lasts at most
  `ruling_bound_s`, the same bound a ruling waits.
- **The expiry is one transition,** written by §24ae's sweep: the escalation is `expired`, the run is
  cancelled with the reason `escalation_expired`, and the cycle ends **parked**.

**A parked cycle (normative).**
- **The continuation decision** gets one row, asked before row 6: the cycle was parked.
  - **An increment, repair or retry:** `abandon_and_propose`, counting as unaccepted. A run of parks is
    bounded by `max_unaccepted_increments`, the no-progress rule (§9.5).
  - **A calibration:** row 2 applies (`stop_failure`, calibration). There is no baseline to build on.
- **Silence is never approval, and never a rejection.** A parked plan is not counted among the rejected
  proposals in a row, and memory does not observe it as a rejected plan (SIP-0110 revision 6).
- **It is not regenerated in a loop.** The next proposal is shown the parked increment's brief through
  §24w's channel, with the escalation and its open questions. A re-proposal that escalates again is
  parked again and counts again, so the no-progress rule ends the loop.
- **Completed and unresolved, kept apart.** The campaign's close record and its digest list the
  accepted increments, and separately every escalation pending or expired at the close, with its
  questions. A campaign that ends because every increment it could build needed the owner ends
  `stop_failure` (no-progress), with that list. The outcome vocabulary does not change.

**The late answer (normative).** An answer to an expired escalation is recorded against it, with its
actor, its time and its notes. The escalation stays `expired`, with the answer beside it.
- It never resumes a parked cycle, and never reopens a closed campaign.
- It is read as an authoritative answer to the same question, by §24ad's mechanism, with a warrant that
  names the escalation:
  - by a running campaign at its next proposal launch;
  - by the next campaign for the same project, at its admission, which applies it to its calibration's
    questions.
- A stale answer never authorizes a changed plan. It answers a question by its id, and a changed plan
  that asks the same question is answered by it, as §24ad answers a question already ruled.

**The digest** asks for each pending escalation, lists each expired one as unresolved and answerable,
and shows each late answer recorded. It reads the store, so a restart loses nothing.

**Not changed:**
- **the campaign-level `escalated` state** (§10 rows 9, 11 and 14, the retry limit, the launch limit).
  It waits on the owner's word, as §10 says. It is not this queue;
- the supervisor's rulings at either gate, in either mode;
- the increment gate.

**Not built:**
- **an automatic rejection or answer.** The ruling keeps them with a person;
- **proposal auto-approval,** until its checks exist (the 2.2 plan §2.2);
- **an escalation that notifies anyone.** The digest is its reader, as it is the overdue rows' (§24ae).

### 24bk. The escalation queue, as built, and one correction to §24bj (2026-10-08, §10, §24ae, §24aj, §24bj, #1708; implementer's reading, ratified by the owner 2026-10-09)

**The correction.** §24bj says an approval with blank notes on a question "answers nothing (§24ad),
so the escalation stays `pending`". That cannot hold. A person's approval decides the gate, and the
cycle goes on to its build. A pending escalation would then expire at the bound and park a cycle that
had already moved on. **As built:** any decision a person records on the gate resolves its escalation.
A blank-noted approval still answers no question: §24ad leaves the question open, and it is asked
again at the next gate. Found while building the sweep; the test is
`test_a_person_deciding_the_gate_resolves_it_and_the_run_goes_on`.

**As built:**
- **The queue is the campaign's control log.** Two record-only operations (migration 1750):
  - `escalation_opened`, keyed by the escalation's identity (`escalation.EscalationIdentity`): the
    campaign, cycle, run, gate, proposal and version, the accepted baseline, and the content hash of
    the manifest and plan the tier read;
  - `escalation_closed`, whose binding names its state. **Every ending of one escalation shares one
    key,** so a second ending is refused as a conflicting key, recorded, and never applied. That is
    the compare-and-set: an escalation ends exactly once.

  Both are records, so the campaign holds in the state it was in, as §24bj says.
- **The gate opens it** (`WorkloadGate._open_escalation`) when the tier cannot approve, then waits for
  a person. A restart that re-enters the gate finds the escalation standing and writes nothing, so its
  bound runs from its first opening.
- **The sweep ends it** (`CampaignProgress._sweep_escalations`, every interval, beside §24ae's and
  §24aj's rows), reading each pending escalation against its run:
  - a person decided its gate: `resolved`, with the decider as the row's actor;
  - its run no longer waits, and nobody decided it: `superseded`;
  - it still waits, and `ruling_bound_s` has passed since it opened: `expired`.
- **An expiry parks the cycle.** The sweep cancels the run (the `supersede` edge, `COMPLETED →
  CANCELLED`, a framing run waiting at its gate having already completed). The gate's poll sees the
  cancellation, and the cycle ends `RUN_CANCELLED`. A person's decision that lands between the sweep's
  read and the cancel wins: the run goes on, and the expiry stands in the record beside it.
- **The `parked` ending** (`CycleEnding.PARKED`) is read from the record: the cycle's last run is the
  one an expiry named, and it was cancelled (`escalation.parked_run`). An operator's cancel with no
  expiry naming the run is not a park.
- **§10 row 15**, asked before row 6: a parked increment, repair or retry is `abandon_and_propose`,
  counting as unaccepted. Row 15 is numbered after row 14 so that recorded rows keep their numbers. A
  parked calibration never reaches it: it was not accepted, so row 2 ends the campaign.
- **`cancelled` is read, not written.** An escalation still pending when its campaign completed reads
  `cancelled`. The campaign's own terminal row is its record, and no sweep reads completed campaigns.
- **§24aj's overdue row is not written for an escalated gate.** It shares the bound with the expiry and
  says the gate still waits, which the expiry contradicts.

**Still to build** (#1708): the late answer and its reading through §24ad, the digest's lists, and the
CLI that answers an expired escalation.

**Evidence.**
- `tests/unit/campaigns/test_plan_gate_escalations.py` enters at `CampaignProgress.sweep_ruling_bounds`
  over memory campaign and cycle registries:
  - an expiry is written once, cancels the run and parks it, with no overdue row beside it;
  - before the bound, nothing moves;
  - a person's decision resolves the escalation and leaves the run alone;
  - a run that stopped waiting supersedes it;
  - a second ending is refused;
  - an escalation pending at the campaign's end reads `cancelled`.

  Without the overdue-row skip, the expiry test fails. Without the park, the expiry test fails.
- `tests/unit/cycles/test_plan_review_tier_wiring.py` enters at `WorkloadGate.decide`. The tier's
  failure opens one escalation naming its conditions and questions, and a re-entry opens no second
  one: that test found the re-entry writing a refused row on every restart, which is why the gate
  reads the log first.
- `tests/unit/campaigns/test_continuation.py`: row 15 for a parked increment and a parked repair, row
  2 for a parked calibration, and row 4 for a run of parks.

**Who ruled it.** The queue is §24bj's, ruled by the owner on 2026-10-08. The correction, and the
readings above that §24bj left open (row 15's number, `cancelled` read rather than written, the
overdue row's skip), were the implementer's, for the owner's reading. **The owner ratified them as written on 2026-10-09**,
accepting the readiness packet's recommendation ("I am good with all other recommendations to proceed on the plan"),
after the owner's reviewer had recommended accepting the correction (§24bm). They are now the owner's ruling.

### 24bl. The late answer, and where a later gate reads it (2026-10-08, §24ad, §24bj, §24bk, #1708; implementer's reading of the owner's ruling 4, for the owner)

> **Superseded in part by §24bm (2026-10-09).** The owner did not ratify this reading. A late answer no longer
> clears a question at the gate by its decision id: it answers each decision by id, it is carried into a tier
> campaign's next manifest only for the same question, and the gate escalates any question the plan does not carry.

§24bj's ruling 4: an answer that comes after the campaign closed is recorded against its escalation and
read at the next campaign's admission, and it never reopens a closed campaign. §24bj said it is read
through §24ad's mechanism, by a running campaign at its next proposal launch and by the next campaign
at its admission.

**As built:**
- **The record.** `escalation_answered` (migration 1760) is a record-only control-log row, so it is
  accepted on a completed campaign. It is keyed by its escalation: one answer per escalation.
  - It is taken only by an `expired` or `cancelled` escalation. A pending one is answered at its gate,
    and a resolved or superseded one has nothing left to answer.
  - Blank text states nothing (§24ad), and is refused.
  - The same answer again replays. A different one is refused with the answer already held, so no
    later gate reads two answers for one escalation.
  - It never resumes the parked cycle or reopens the campaign.

  `POST /api/v1/campaigns/{id}/escalations/{escalation_id}/answer` (`campaigns:supervise`), and
  `squadops campaigns answer <campaign> <escalation> --answer "…" --reason "…"`.
- **Its key: the decision's id.** An escalation now records its open decisions as `(id, question)`
  (`open_decisions`, beside `open_questions`, which now reads from it). An author's decision id
  recurs across framings of one project: both of this line's calibrations named `list-ordering`.
- **Where it is read: every later plan gate of a tier campaign in the same project.** The tier reads
  the design's open decisions against the late answers on record in the project's campaigns
  (`escalation.recorded_answers`; the latest answer for an id wins). A decision an answer covers is
  answered, and the tier's notes name the answer and the escalation it was recorded against. The rest
  stay open, and only they are recorded on any escalation the gate opens. This reading covers both of
  §24bj's cases:
  - the next campaign's calibration: its first plan gate is where its admission meets the question;
  - a running campaign's next gate.

**Where this differs from §24bj's wording, and why:**
- **Read at the gate, not at the proposal launch.** §24ad's channel resolves the accepted manifest's
  questions at a proposal launch. A calibration has no accepted manifest: its questions arise in the
  manifest its framing writes. So the one place that sees the question in both cases is the gate.
  **The answer does not enter the manifest's decision as its `choice`.** The build of the cycle whose
  gate it answered runs on the plan as authored, as an answer given at the gate does today.
- **Tier campaigns only.** A supervised campaign keeps today's behaviour (§24bj). Reading late answers
  there would let #807's pass-through approve with notes saying the design asked nothing, which would
  be false.

**The digest** has an Escalations section listing every escalation and how it ended, with its late
answer, kept apart from what was accepted. Its asks are:
- a pending escalation, to answer at the gate before the bound parks it;
- an expired or cancelled one with no answer, with the command that answers it late.

**Evidence.**
- `tests/unit/cycles/test_plan_review_tier_wiring.py`, entered at `WorkloadGate.decide` with V4 roll
  2's authored manifest (decision `expansion-gating`):
  - a late answer recorded against an earlier campaign's expired escalation answers the same decision,
    so the tier approves and opens no escalation, its notes naming the answer;
  - with the carry removed, the test fails;
  - an escalation the gate opens records the decision's id with its question.
- `tests/unit/api/test_campaign_routes.py`:
  - an answer is recorded once, a retry replays, and a different answer is a 422;
  - an answer after the campaign ended is recorded, and the campaign stays completed;
  - pending, resolved, blank and unknown are each a 422 that records nothing.
- `tests/unit/campaigns/test_plan_gate_escalations.py`: the digest asks at the gate while the
  escalation is pending, then asks for a late answer once it has expired, then shows the answer and drops the ask.
- `tests/unit/cli/test_commands_campaigns.py`: `answer` posts to the escalation's own route, and
  `escalations` lists each one's state, conditions and questions.

**Who ruled it.** The record is the owner's ruling 4 of 2026-10-08. Reading it at the gate, by decision
id, in tier campaigns only, is the implementer's reading, for the owner.

### 24bm. A late answer reaches a plan only by being carried, and only to the same question (2026-10-09, §24ad, §24bj, §24bl, #2188; ruled by the owner)

**What changed.** §24bl let a later plan gate clear an open question with any late answer on record whose decision id
matched, and recorded one free-text answer for every decision its escalation listed. The answer never became the
current manifest's choice, so the tier approved a plan that did not carry it. Now:
- **A late answer names each decision it answers, by its id** (`answers: {decision_id: answer}`). It may name only
  decisions the escalation recorded, and one text never stands for several questions. Each answer is kept with the
  question it answered. `POST /api/v1/campaigns/{id}/escalations/{escalation_id}/answer` takes `answers`, and
  `squadops campaigns answer … --answer DECISION_ID=ANSWER`, once per decision.
- **It is carried at a tier campaign's proposal launch, as §24ad's answer is.** An open decision in the baseline
  manifest is resolved by a late answer on record only when both the decision id and the question match.
  Case, spacing and trailing punctuation are set aside; an author's ids recur across a project's framings, so a shared
  id alone is not the same question. The decision's `choice` becomes the answer, and its `warrant` names the
  escalation (`late answer recorded against esc_…`).
- **The gate no longer clears anything by id.**
  - An open question in the manifest it reads is open, and escalates.
  - A decision that cites a late answer is answered only while its `choice` is still the answer that escalation
    recorded for it. Otherwise it escalates, naming the mismatch.
  - So a historical "descending" never authorizes an ascending plan because both are called `list-ordering`.
- **Unchanged:** supervised campaigns carry nothing (§24bl's tier-only rule), a calibration's question is answered at
  its gate (it has no baseline to carry into), and the late answer stays a record that reopens nothing.

**Evidence.**
- **Read at rebuild 9 (`a84e085f`):**
  - the tier removed open decisions by id against late answers from every campaign of the project
    (`adapters/cycles/workload_gate.py`);
  - `escalation.recorded_answers` recorded the one answer under each of the escalation's decision ids;
  - nothing wrote the answer into the manifest.
- **The tests:**
  - `tests/unit/cycles/test_plan_review_tier_wiring.py`, entered at `WorkloadGate.decide` on V4 roll 2's authored
    manifest. A late answer on record leaves the open question open and escalates; with the gate's old clearing
    restored, the test fails. A plan carrying the answer it cites is approved, its notes naming the carry. One whose
    choice was changed escalates;
  - `tests/unit/campaigns/test_progress.py`, entered at `CycleCompletion.end` on shakeout 4's calibration manifest. A
    tier campaign's increment baseline carries the late answer for the same question. It carries nothing for another
    question under the same id, and nothing in a supervised campaign;
  - `tests/unit/campaigns/test_late_answers.py`: question matching; the latest answer per decision; the carry check;
    a manifest with nothing to resolve unchanged, byte for byte;
  - the route and CLI tests: an answer naming a decision the escalation did not ask is a 422.
- **No live effect, and no data migration.** The tier is inactive until after 2.2's window (the 2.2 plan's D3), and the
  live store holds no late answer.

**Who ruled it.** The owner's review of the 2.2 shakeout (2026-10-09, point 9): "Do not ratify §24bl unchanged …
Require compatible question/context, explicit coverage of each answered question, and evidence that the current plan
carries the answer; otherwise continue escalating … Keep the automatic tier disabled through the window and correct
this behavior before activating it." In the same review the owner's reviewer recommended accepting §24bk's bookkeeping
correction, which stays the owner's ruling.

### 24bn. Proposal-run retries bound failed proposals in a row, and the failure past them pauses (2026-10-11, §9.5, §10 row 6, #2231; ruled by the owner)

**What §9.5 wrote, and what main did.** §9.5's row read "proposal-run retries | the cycle ends
`proposal_failed`", which describes a retry of a failed proposal run *inside* its cycle. That retry
was never built. The cycle ended `proposal_failed` on its first failed run, and
`max_proposal_run_retries` was declared, required and validated, but read nowhere. Row 6 proposed
again after every failure, so nothing but `max_cycles` bounded failures in a row. Rejected proposals in
a row pause the campaign (`max_rejected_proposals_in_row`), but a failed proposal run is not a rejection.

The 2.2.1 diagnostic (`cmp_bf5daecdf444`, uncounted) showed it live. Its rails refuse every proposal
by design. Four proposal cycles failed in a row, each decided row 6 `propose` with guard `proceed`,
and the campaign ended `exhausted` at `max_cycles: 5`. Its plan had predicted it would close "after one
retry (`max_proposal_run_retries`)". The plan's §6 records that misreading, and #2231 was filed.

**What changed.**
- **The in-cycle retry is not built.** A proposal refused after its revision budget is almost always
  refused again, and each attempt costs about 20 minutes of box time.
- **`max_proposal_run_retries` keeps its name and gets a meaning.** It is the number of failed
  proposal cycles the campaign retries in a row. Row 6 is the retry: the next proposal cycle.
- **The failure past the retries pauses.** The pending launch is held, `paused_by:
  failed_proposals_in_row`, and the campaign resumes only on the owner's recorded word, as
  §9.5 says of every limit's pause. With `max_proposal_run_retries: 1`, the first failure is
  retried and a second failure in a row pauses.
- **The count** (`failed_proposals_in_row`) is read the way rejected proposals in a row are read.
  It is the ending cycle, then the earlier decisions' rows, back to the first that ended otherwise.
  A rejection, a built increment or a parked one breaks the run.
- **The precedence is unchanged.** Rows 1–4 are still asked first, so a failure decided once
  `max_cycles` or the no-progress rule is reached ends the campaign rather than pausing it. The two
  in-a-row limits are asked after the elapsed-time and budget limits.

**Evidence.**
- `tests/unit/campaigns/test_progress.py::test_the_failure_past_the_proposal_retries_pauses_the_campaign`
  enters at the completion hook (`CycleCompletion.end`) with two failed proposal runs. The first is
  decided row 6 `proceed`; the second is decided row 6, `paused_by: failed_proposals_in_row`, and the
  campaign is `paused`.
- `test_failed_proposals_in_a_row_are_read_back_until_another_ending` covers the count: a run of
  failures, and a rejection or a build breaking it.
- `tests/unit/campaigns/test_continuation.py` adds two precedence cases: the retried failure, and
  the failure past the retries.
- With the pause removed, the wiring test and the second precedence case fail. With it asked one
  failure early (`>=`), the wiring test and the first case fail.

**Who ruled it.** The owner, 2026-10-11: "approve your #2231 recommendations". The recommendation was
to build no in-cycle retry, to give `max_proposal_run_retries` this meaning, to pause past it as
rejected proposals in a row do, and to amend §9.5 accordingly. It is recorded on #2231.

### 24bo. The rails refuse an undefined manifest key, and a criterion no build may meet (2026-10-13, §7.2, #2205; implementer's reading, for the owner)

**What changed.** §7.2's rails derived the footprint from the manifest the delta produces, but two things passed
unseen. The 2.2 window's campaign 4 proposal `prop_5af48f5f739c` v1 had both, and only the supervisor's reading of
its footprint caught them:
- **An undefined key.** The proposer put each error's message under `messages:` in three endpoint definitions.
  `InterfaceManifest.from_dict` reads only the keys it knows and dropped it without a word, so the footprint was
  derived without it. Now the rails refuse it as `undefined_key`, naming each key as written (an entity field's as
  `fields[<name>].<key>`) and listing the keys that element does declare. The table of declared keys
  (`scaffold.MANIFEST_ELEMENT_KEYS`) sits beside the parsers, and a test holds it to them.
- **A criterion no build may meet.** Its three criteria named endpoints served by `backend/routes.py`, which the
  delta left unchanged, so the footprint excluded it, and every write there would have been dropped
  (`write_authorization`) or refused at the plan gate. Now an endpoint criterion whose serving file is outside the
  footprint is refused as `surface_outside_footprint`, naming the criterion and the file. The serving file is the
  contract's own `endpoint_owners`, the relation every repair aims by.
  - A client-route criterion is not checked this way. A view's behaviour can be served by the endpoints it calls, so a
    view outside the footprint does not show the criterion unbuildable.
  - Neither rail adds to `nothing_to_build`, which already names the cause when a delta changes no product file.

**The third gap, ruled.** #2205's third gap was whether the manifest can declare an error's message text, and without
it a message-only change had no buildable delta. The owner ruled on 2026-10-14 that the error contract carries it
(SIP-0103's amendment of that date). So a change to an error's wording is a `modify` of its `error_code`, and the
footprint holds the frozen error module the scaffold regenerates. `surface_outside_footprint` therefore doesn't refuse
an endpoint criterion when the endpoint declares a code whose contract the delta changes, because the regenerated
module builds that change outside the serving file.

**The evidence:** the proposal's stored document and the accepted manifest it was proposed against
(`tests/fixtures/campaigns/`). Through the rails they now draw three `undefined_key` refusals (`messages`, each by its
endpoint) and three `surface_outside_footprint` refusals (T1–T3, each served by `backend/routes.py`). The reference
change request, whose delta does change `backend/routes.py`, still passes. The same proposal with its messages declared
on the codes passes the rails, with `backend/errors.py` in its footprint.

### 24bp. A park's abandonment counts at its own decision, as a rejection's does (2026-10-13, §9.5, §10 rows 4, 13 and 15, §24bj, #2294; implementer's correction, for the owner)

**What main did.** Row 4 stops a campaign when the unaccepted increments plus the abandonment this decision would make
reach `max_unaccepted_increments`. That second term covered row 13 only, a rejected increment with no repair left. It was
added so the decision whose own abandonment reaches the limit stops, rather than proposing once more. Row 15 (§24bj, §24bk)
came later: a parked increment, repair or retry is abandoned and proposes again, "counting as unaccepted". Its own
abandonment was counted only after its decision. So under a limit of 2, two rejected increments stopped the campaign at
the second, while two parked increments didn't: the second park proposed a third increment, and the stop came after the
third park. The continuation test pinned the late stop.

**What changed.** A parked increment, repair or retry counts its abandonment at its own decision, as row 13's does.
Two parks in a row stop a campaign whose limit is 2, as two rejections do. A parked calibration is unaffected, because row
2 ends the campaign before row 4 is asked. §24bj's "a run of parks is bounded by `max_unaccepted_increments`" now holds as
written.

**Evidence.**
- `tests/unit/campaigns/test_continuation.py::test_parks_in_a_row_stop_at_the_limit_through_the_counters_the_decision_reads`
  derives the counters with `derive_counters` from a log holding the earlier parks' row-15 decisions, as
  `CycleCompletion.end` derives them, then decides the next park. The first park proposes again; the second stops at row
  4 (`stop_failure`, no progress).
- The row table's no-progress case for a park is now one earlier park, for an increment and for a retry.
- With the old count restored, three of these cases fail.
- Found pre-registering #2279's live reading, whose no-progress stop depends on how many parks reach it.

**Who ruled it.** Proposed by the implementer, as a correction that makes row 15 match §24bj's text and row 13's precedent.
The owner rules it with the merge.

### 24bq. A rejection only for criteria already met is abandoned for a new proposal, not repaired (2026-10-14, §8.2, §10 rows 4, 12, 13 and 16, §24w, #2315; ruled by the owner)

**What main did.** Row 12 sent every rejected increment with a repair cycle left to a repair. A repair rebuilds the
candidate. But a new criterion that is unmet with `no_baseline_failure` (§8.2) is unmet because its test passes on the
accepted tree, and no rebuild of the candidate changes the baseline run. When those criteria were the whole of the
rejection, the repair was spent before the outcome it could not change. Row 13 then abandoned the increment, and its
brief (§24w) carried the cycle's own checks, which had passed, so the next proposal was not told why.

**The evidence.** #2205's after arm (`cmp_fd71a56a9142`, 2026-10-14, on TensorFold):
- the first proposal's T1–T4 discriminated;
- its T5 and T6 (the run view shows the server's message) were `no_baseline_failure`, because the accepted view
  already showed it;
- row 12 launched a repair (`cyc_bfa3287a2f65`, 5 min), which rewrote every criterion's test and got the same split;
- row 13 abandoned the increment, and a second proposal, with endpoint criteria only, was accepted.

The readings are on #2205 and the issue is #2315.

**What changed.**
- **Row 16, asked before row 12:** the cycle's own verification accepted and its increment's evaluation rejected it, and
  every unmet new criterion is `no_baseline_failure`. Nothing is blocked, every frozen criterion held, and every route
  rendered. The action is `abandon_and_propose`, whether repair cycles remain or not.
  - It counts as unaccepted at its own decision, as rows 13 and 15 do (§24bp), so row 4's no-progress stop reads it.
  - A rejection with any other unmet reason, or a build that also failed its own checks, keeps row 12. A repair can
    fix those.
- **§24w's brief** for an abandonment (rows 13 and 16) names the criteria the evaluation found already met, each with
  its statement and surface from the approved change request. They are shown as "Already met by the accepted
  application, before this change". Read from stored records (the last run's evaluation and the request), as #1943
  requires of a launch.

**Evidence.**
- `tests/unit/campaigns/test_continuation.py::test_a_rejection_only_for_already_met_criteria_is_abandoned_for_a_new_proposal`
  covers four cases:
  - row 16 with repairs left;
  - row 16 with repairs spent;
  - row 12 when the build's own checks also failed;
  - row 4 when the abandonment reaches the limit.
- `tests/unit/campaigns/test_progress.py::test_an_increment_rejected_only_for_criteria_already_met_goes_to_a_new_proposal_told_which`
  enters at the completion hook with the request on the approved proposal run (#1938's live shape):
  - row 16, and the next proposal's `abandoned_increment.already_met` carries C1's statement and surface;
  - with a second criterion that fails on the candidate, row 12.
- `test_a_rejection_is_already_met_only_when_nothing_else_stands_in_it` checks five evaluations that must not count as
  already met only: none, blocked, a frozen criterion broken, a route missing, and accepted.
- Three mutations are caught:
  - row 16 never firing;
  - a broken frozen criterion ignored;
  - the brief left without the criteria.

**Who ruled it.** The owner, 2026-10-14 ("yes"), on the recommendation put on #2315: skip the repair, and tell the
next proposal which criteria the accepted application already meets.

### 24br. A successor's brief carries the increment's evaluation, not only its cycle's checks (2026-10-16, §8, §10a, §24w, §24bq, §10 rows 12, 13 and 16, #2318; implementer's correction, for the owner)

**What main did.** A repair (row 12), a retry, and the next proposal after an abandonment (rows 13 and 16) are handed the
failed cycle's brief (§24w, #1692). It was built from the cycle's own assessment: its checks, its attribution and its
correction rounds. The decision that launched the successor read something else, the increment's own evaluation (§8,
`increment_verdict`). The evaluation can reject a build whose own checks all passed: a frozen criterion broken, a new
criterion unmet, a declared route that didn't render, or a judgement blocked. Then the brief told the successor the
cycle passed. §24bq added one part, the criteria already met, to an abandonment's brief only.

**The evidence.** The 2.3 cut's shakeout (`cmp_27dba15dea9a`, on `dep_d8f35563107c`, 2026-10-16):
- increment 2 (`prop_6663003f2974`, a seed endpoint, `cyc_019ad1db5c02`) passed every check of its own, 23 of 23
  criteria. Its evaluation rejected it: frozen T2 broke at `test_guard_ordering_capacity_before_duplicate`, because the
  build rewrote `backend/routes.py` and moved the duplicate check ahead of the capacity check;
- row 12 launched a repair (`cyc_cb0461c0a639`). Its brief read `verdict: accepted, failed_checks: [], primary_cause:
  None`, and named neither T2 nor the test;
- the repair passed its own checks, T2 broke at the same test again, and row 13 abandoned the increment.

**What changed.**
- **Every brief built from an increment-kind cycle carries its evaluation's findings** when the evaluation rejected it.
  That covers increments, repairs and retries, for the repair, the retry and the next proposal alike:
  - each frozen criterion that didn't hold, with its failing tests;
  - each new criterion left unmet, with its reason;
  - each route that didn't render, with the test ids it was missing;
  - anything the evaluation blocked.
- **Each criterion is named with its statement and surface:** the frozen ones as their promotions froze them (carried on
  the bound proposal), the new ones from the approved change request.
- **It's read from stored records,** the last run's `increment_evaluation.json`, as §24bq's criteria are (#1943).
- **The brief's lines show the findings after the cycle's checks,** headed "The increment's own evaluation rejected it,
  whatever the checks above say". A criterion already listed as met (§24bq) isn't repeated.
- **Unchanged:**
  - the decision and its rows;
  - the brief's cycle-check indicators, which still say what the build's checks read;
  - its integrity rule: typed records only, never a narrative.

**Not in it.** A repair's own correction loop still doesn't run the frozen criteria. They run at the evaluation (§8.1),
so a repair is now told what broke but can't verify its fix before the evaluation does.

**Evidence.**
- `tests/unit/campaigns/test_progress.py::test_an_increment_its_evaluation_rejected_tells_its_successor_why` enters at
  the completion hook on the shakeout's case: a build whose checks accepted, whose evaluation broke frozen T2. For the
  repair (row 12) and for the next proposal (row 13), the brief carries T2 with its statement, surface and failing
  test, and its lines show it.
- `tests/unit/campaigns/test_prior_cycle.py` checks:
  - an accepted or absent evaluation adds nothing;
  - every part of a rejection is shown;
  - a criterion already met isn't repeated.
- Four mutations are caught:
  - the brief never reading the evaluation;
  - frozen breaks dropped;
  - the lines never shown;
  - an accepted evaluation reported.

**Who ruled it.** Not the owner yet. The supervisor placed it in 2.3 under the owner's delegation of 2026-10-15 ("Yes I
gave you authority!"), as the cut shakeout's seam finding: the cut's pre-registration (§3) fixes a finding and re-runs
the shakeout. It's for the owner's review.

### 24bs. A campaign declares its stack, and every cycle it launches carries it (2026-10-18, §7.3, §10a, §11, §12b, §15, #2443; implementer's correction, for the owner)

**What main did.** Every launch built its cycle-create request from a profile name alone. The calibration
used `policy.calibration_profile`, and the increment and every bound cycle used `policy.proposal_profile`
(`src/squadops/campaigns/launch_requests.py`). None of them passed a stack. Every campaign profile pins
`fullstack_fastapi_react`, and so does `validated-fullstack`, which every definition under
`examples/03_group_run/campaigns/` calibrates on. `CampaignPolicy` had no stack. So a campaign could run on
one stack only, and no test or deploy ever ran a campaign on `nextjs_ts`. Other Next.js pieces shipped in
2.1 (§24av, §24bd, §24m's criterion paths), which made the stack look supported. The launch was the piece
that was missing.

**The evidence.** The 2.4 plan's D3 rules its measurement window as four campaigns, two per stack (SIP-0113
§6). Preparing #316's design review found that no Next.js campaign could launch (#2443).

**What changed.**
- **`CampaignPolicy.stack`,** optional on `CampaignCreateRequest`. Every launch carries it to
  `cycle_request_body()` as `user_values`: `build_profile` and `development_profile` together, the pair #832
  keeps in agreement. They reach the cycle as `execution_overrides`, hashed into its config hash as any
  override is. That's how every Next.js verification set already runs `validated-fullstack`.
- **Undeclared, it is the campaign profiles' own stack.** That's what a cycle with no stack override runs.
  It is declared absence, not a default this SIP invents. **Unlike `plan_gate` (§24bj) it is not required:**
  requiring it would refuse every pinned definition, which §24bj already does for the 19 written before it.
  This one would refuse all 34, including the pinned ones the crew re-runs.
- **A stack a campaign can't run on is refused at creation** (422): one with no scaffold, or one that declares
  nowhere for a criterion's test file (§8.1, `hosts_campaign_increments` in `squadops.stacks.scaffold`). An
  empty string is refused too, never read as undeclared.
- **Stored rows and replays are unchanged.** A policy stored without a stack reads as `None`. The stack enters
  a creation's replay hash only when declared, so every stored creation's retry still replays, as §24bj's
  plan gate does.
- **Unchanged:** the profiles, the decisions and their rows, and every existing campaign's requests.

**What it does not do.** It does not show that a Next.js campaign succeeds. That has never run. The window's
Next.js campaigns are preceded by uncounted Next.js shakeout campaigns, and whatever they find is a seam
finding of its own.

**Who ruled it.** Not the owner yet. The supervisor built it under the 2.4 grant (the plan's D11), as the
prerequisite of D3's ruled window. It's for the owner's review. It is a contract 2 field (SIP-0112 §8.2), so it
carries the MacBook lane's review (G4).

### 24bt. Campaign creation names a held-out scenario suite, kept in Outcome Evaluation's record (2026-10-18, §15, §16; SIP-0113 §4.7 phase 1, #2413; implementer's record, for the owner)

**What changed.** `CampaignCreateRequest` gains an optional `scenario_suite`: the digest of a held-out
scenario suite the owner approved (SIP-0113 §4.1, the 2.4 plan's D2).
- **The check comes first.** It runs before the campaign is created: a suite nothing holds, or a draft,
  is refused with 422 and its own code, `SUITE_NOT_FOUND` or `SUITE_NOT_APPROVED`, and creates no
  campaign.
- **The pin comes after, in SIP-0113's own record** (`campaign_scenario_suites`, migration 1900), keyed by
  the campaign the creation returned.
  - A replayed creation replays its pin, and a retry that names another suite is refused with 409
    `SUITE_ALREADY_PINNED`.
  - **A campaign takes a new pin only while it is a draft.** The suite isn't in the creation's replay hash,
    so a retry under the same key could otherwise attach a suite to a campaign created without one, after
    it had started. Past its draft, it is refused with 409 `SUITE_PIN_PAST_DRAFT`. A retry while it is still
    a draft recovers a pin the first creation failed to write.
  - **The creation is projected before the pin**, so a refused pin still leaves the created campaign
    projected.
- **An unknown field is refused** (contract 2): `CampaignCreateRequest` forbids extra fields, so a
  misspelled `scenario_suit` doesn't create a campaign with no suite. Its nested `objective` and `policy`
  still ignore unknown keys: five historical shakeout definitions carry two retired policy keys.
- **This SIP's state is unchanged.** It is not on `CampaignPolicy`, it doesn't enter the creation's replay
  hash, and no decision, row or launch of this SIP reads it.
- **Phase 2's `scenario_suite`, `scenario_target` and `quality_baseline` on `CampaignObjective`** (SIP-0113
  §4.7) remain that phase's, with their own amendment if it is built.

**The evidence.** SIP-0113 §4.7 places the phase-1 pin at Campaign creation, and SIP-0112 §8.2's contract
2 has each lane add its own typed fields there and repurpose none. #2413 builds it, with its wiring test at
`POST /api/v1/campaigns` (`tests/unit/api/test_campaign_scenario_suite.py`).

**Who ruled it.** The owner accepted SIP-0113 with this placement (2026-10-17). The supervisor built it
under the 2.4 grant (D11). It is a contract 2 field, so it carries the MacBook lane's review (G4). The
draft rule, the projection order, the kept codes and the forbidden extras answer that review.

### 24bu. A fresh proposal is shown each proposal its campaign never approved, with the ruling's reason (2026-10-21, §9.1, §9.2, §9.5, §10 rows 6, 7, 13 and 16, #2593; implementer's correction, for the owner)

**What main did.** A revision is shown the supervisor's note and the version it revises (§9.2). A rejection ends its
cycle instead (§9.5, `rejected_at_gate`), and row 6 launches a fresh proposal, built from the PRD, the accepted
manifest, the objective and the frozen criteria. It carried no earlier ruling, so a rejection's reason reached the
control log and the ledger, and never the squad.

**The evidence.** The 2.4 measurement window's campaign 4 (`cmp_263d1e49aca8`, on `dep_19dfa94c0a0a`, 2026-10-21):
- the proposer offered PRD Expansion Tier 2's per-participant leave button in four of its five proposals, with Tier 1
  incomplete;
- each was rejected on the window's priority-order condition, with the reason in its notes, and
  `max_rejected_proposals_in_row` paused the campaign twice. The supervisor aborted it at the second pause;
- the repeat is consistent with the gap, not proof of it: the PRD's own "only if Tier 1 is complete" was in front of
  every proposal.

**What changed.**
- **Every fresh proposal's launch** (`_propose_launch`, rows 6, 7, 13 and 16) **carries `unapproved_proposals`:** each
  proposal the campaign ruled on and never approved, by its last applied ruling, the ten most recent, in ruling order.
  That covers a rejection, and a return whose revisions were spent. A proposal approved at any version is left out.
- **Each entry carries:**
  - the ruling's reason and its §24bi classification;
  - what it proposed, its PRD sections and criteria, read from its proposal run's own change request (the document the
    ruling bound to);
  - whether it was ruled on the application the new proposal builds on, or on an earlier one. A change rejected for
    priority may be built later, under another proposal.
- **It's its own key,** read by the proposal alone, as row 13's `abandoned_increment` is (§24w). The proposal renders it
  through `request.proposal_unapproved_proposals`, which tells the model to judge each reason against the manifest it is
  shown, not the application it was ruled on.
- **A read that fails raises,** and the re-hearing retries the launch, the launch's rule for its inputs (#1943's shape).
- **Unchanged:** the ruling rule, the rows and their counters, and what a revision is shown. The issue's alternative,
  returning a priority-order failure for revision so its note reaches the squad, changes the ruling rule, which is the
  owner's.

**The design choice.** #2593 left open whether the squad should see the supervisor's reasons, or only what was
rejected. It sees the reasons, because a revision already does (§9.2), and the reason is what the proposer couldn't see.
So a ruling's notes are now prompt content: they must stand alone, in the PRD's and the application's terms, and they
never carry a held-out value. Campaign 4's notes cited the window's pre-registration, which the squad can't read.

**Evidence.**
- `tests/unit/campaigns/test_progress.py::test_a_rejected_proposals_reason_reaches_the_fresh_proposal_after_it` enters
  at the completion hook as a rejected proposal's cycle ends. Row 6's launch carries the reason, the classification and
  the ruled run's own request, not a newer decoy under the cycle's other run.
- `test_a_ruled_request_whose_read_fails_launches_nothing_and_the_rehearing_shows_it`: a failed read launches nothing,
  and the re-hearing launches with the entry.
- `tests/unit/capabilities/test_strategy_propose_increment.py::test_a_fresh_proposal_is_shown_each_proposal_the_campaign_never_approved`
  renders the section through the real handler.
- Rendered on campaign 4's own records: 4 entries, a section of about 1,500 tokens on a prompt of about 7,400.

**Who ruled it.** Not the owner yet. The supervisor built it under the owner's 2.4 grant of 2026-10-19, as a defect the
window's campaign 4 found. It's for the owner's review.

### 24bv. A Campaign on a repository-backed Project: calibration as a record, increments on a campaign branch, proposals from the product's tree (2026-10-21, §7, §8, §9.1, §10 rows 2, 4 and 5, §11, §12a; SIP-0112 H.4; #2619; designed, not built: placed in 2.5)

**What was found.** A Campaign on a repository-backed Project, external or greenfield, runs its calibration cycle and
never launches an increment (#2619, the Spark lane, 2026-10-21). The increment profiles pin a template stack that a
source-backed cycle refuses, and a proposal needs an interface manifest such a product doesn't have. The calibration
launch also carries no PRD or plan, so it fails at provisioning (IR-2's live run). This SIP was written for a
product SquadOps builds from its PRD in its own vault. The only Campaigns run so far are on such sample applications,
and nothing below changes them.

**The owner's direction, 2026-10-21** (through the MacBook lane, on #2619): "it seems we need a way to derive the stack
and recipe and call out any gaps preventing squad ops from working on it", and then "go with 2.5". SIP-0112 H.4 states
what such a Project is (its derived development profile and its capability gaps). This amendment states how a
Campaign runs on one. Each part names the section it amends.

**A repository-backed Project** is one with a source (SIP-0112 E.4.1): an imported product, or a greenfield one after
its initialization (H.1). Everything below applies to it and to nothing else.

#### 1. Calibration is a record, not a cycle (§11, §10 rows 2, 4 and 5)

- **`campaigns start` writes a calibration record in place of launching a calibration cycle.** The record holds the
  Project's state as it stands at the start:
  - the reconciled commit;
  - the Development Configuration revision;
  - the inherited baseline captured at both;
  - the derived profile's gaps.
- **The start is refused (409) when it can't write one, naming why, and nothing is written.** It's refused when:
  - the Project isn't READY;
  - a sync recorded relevant drift it hasn't reconciled (SIP-0112 H.2);
  - no inherited baseline is captured at that commit and revision;
  - a blocking gap stands (H.4), including a baseline in which no check ran.

  This is the start's own precondition. Nothing has been launched, so nothing escalates.
- **The rows:**
  - row 2 never fires for a record, since a start that would have failed it is refused;
  - row 5 reads the record as an accepted calibration and proposes;
  - the record counts toward no limit of row 4's, and none of step 3's guards;
  - the elapsed time runs from the start, as today.
- **The definition says so:**
  - `calibration_profile: inherited_baseline` is required for a repository-backed Project and refused for any other;
  - `policy.stack` must be unset (§24bs), since the derived profile is the product's recipe;
  - `proposal_profile` names the stack-less source-backed increment profile that H.4's point 3 adds.

  Each refusal comes at creation (422), naming the field.
- **What the calibration no longer is:** the yardstick for greenfield behaviour (§11). A repository-backed Campaign
  has no greenfield yardstick, and its package says so. Its increments are compared with the tree before them, and
  with Outcome Evaluation's reading of the record's commit (SIP-0113 §10l).

#### 2. The accepted tree is a campaign branch (§7.1, §12a)

- **The accepted tree is the head of the campaign's branch** in the managed clone (`squadops/campaign/<campaign_id>`).
  It starts at the record's commit. It's identified by its commit and by the commit's tree identity (contract 4), and
  it's immutable as today: it moves only by promotion, or by the rebase in point 4.
- **Promotion (§12a) moves the branch head to the increment's captured commit**, in the same keyed transition.
  - The capture's parent is the head (`source_delivery`), so the branch holds the accepted increments in order.
  - The Campaign's one review request is updated after it (SIP-0112 H.4).
- **A failed increment leaves the branch where it was** (§7.5). Its candidate commit, if one was captured, is kept as
  evidence off the branch.

#### 3. What an increment pins and is compared against (§7.1, §8)

- **Its source context pins the branch head.**
  - It pins the head commit, not the Project's `development_baseline_commit`.
  - It pins the Project's configuration revision.
  - Its instruction sources bind at that commit (SIP-0110 §5ad), so it reads `CLAUDE.md` as the previous increment
    left it.
- **Its regression baseline is the previous accepted increment's verification,** or, for the first, the record's
  inherited baseline. The product's checks, read under no-introduced-regression (SIP-0112 FR-20, and its findings
  readers once #2609 ships), compare the candidate with the tree it was built on, never with upstream.
- **Accumulated acceptance and discrimination (§8.1, §8.2), on the product's own runner:**
  - **A criterion's verifier bundle** is a test file placed where the product's runner discovers tests, under the
    derived profile's test layout. It's frozen with the test-support files the profile names, and run by the
    product's test command scoped to that file.
    - A runner the profile can't scope to one file is a disclosed gap.
    - Then the frozen criteria run as the whole suite, and each is read by its test id: pytest's node id, through
      #2609's reader.
  - **The baseline-evaluator overlay** is the accepted tree's product files plus the candidate's test files, as the
    profile classes them.
    - A product whose test files the profile can't class is a blocking gap for `feature` and `fix` increments, named
      at configure time. Without it, no criterion could be shown to discriminate (§8.2).
  - **Route rendering (§8.3)** applies only where the profile names client routes: a greenfield product following a
    blueprint, from its approved manifest. Elsewhere it's recorded as not applicable.
- **The emission, correction and route seams in §8.4's table** see the candidate on the branch head, as today. Each
  row's "outcome when input is missing" is unchanged.

#### 4. When upstream moves (SIP-0112 H.2)

- **Before each fresh launch, the launcher compares the branch's base with upstream,** read by the Project's latest
  sync.
  - **Relevant drift:** the Project is reconciled first (validate, configure, baseline at the new commit, as today).
    The launcher then rebases the branch onto the reconciled commit, re-verifies the rebased head by the product's
    checks, and records `branch_rebased` in the control log: the base and head before and after, and the
    verification.
  - That verification is the next increment's regression baseline.
- **A rebase that conflicts, or a rebased head whose checks regress against upstream's baseline, refuses the launch.**
  The Campaign escalates (`CAMPAIGN_BRANCH_CONFLICT`, `REBASED_HEAD_REGRESSED`), and nothing is resolved by itself.
- **Drift that isn't relevant holds nothing,** as for a standalone cycle. The review request carries any conflict it
  makes.
- **When the owner merges the review request,** the next sync attributes those increments as integrated (H.2's
  attribution). The branch's base becomes the merge commit, with no rebase.
- **A rebase between a failed increment and its repair** leaves the repair nothing to continue, since its candidate
  was built on the old head. **Proposed, for the owner's review:** the increment is abandoned as `upstream_moved`,
  counted toward no `max_unaccepted_increments` (the squad's work didn't fail), and row 6's fresh proposal follows on
  the rebased head.

#### 5. The proposal's input (§7.2, §9.1)

- **In place of "the accepted tree's identity, manifest and frozen criteria"**, a repository-backed proposal is given:
  - the branch head;
  - the bounded tree view at it: the file map and the instruction files, framing's `source_repository` view;
  - the derived profile, with its disclosed gaps;
  - the frozen criteria;
  - the previous increment's verification: its checks and, once #2609 ships, its findings;
  - the requirements source, bound at the head.

  A greenfield product's approved manifest (H.1) is given beside them. Rows 6, 7, 13 and 16's inputs (§24w, §24br,
  §24bu) are unchanged.
- **The requirements source.** An imported Project has no `prd_path`, and a calibration record carries none. So a
  repository-backed Campaign's objective names one:
  - `objective.requirements`, required at creation;
  - either a `repo:file:<path>@current` reference, bound at each increment's head as §5ad binds an instruction's (a
    PRD that an increment or upstream changed is read as it now stands), or a stored artifact's id.
- **The change request (§7.2), on such a Project:**
  - **`manifest_delta`** is absent, and refused if present.
  - **`footprint`** is authored by the proposer as path globs, since no scaffold map derives it. It must lie inside
    the objective's `allowed_scope`, and the plan validator enforces it as today.
  - **Each criterion's public surface** is one the derived profile names: an endpoint the start declaration serves, a
    command-line entry point, or a package's public interface. The observable is asserted there, never by importing
    a module that exists only in the candidate (§8.2's rule).
  - **`prd_delta`** is against the requirements source.

**What stays.**
- A sample application's Campaigns, the counted pair (SIP-0112 IR-10), and every row's predicate.
- The launch intent (§12b), the ruling (§9.2), the plan gate (§24bj) and the intervention ledger.
- Standalone source-backed cycles.

**Not decided here, for 2.5's design review:**
- whether the review request stays a draft until the Campaign ends;
- a per-increment review request beside the Campaign's (H.4 names it as a later addition);
- how a frozen bundle snapshots fixtures for runners other than pytest and vitest.

**Evidence.**
- #2619's three refusals, at the lines it cites.
- IR-2's calibration failing at provisioning (`cyc_95c8659ae6c5`, `docs/plans/2-4-0-demonstrations-readout.md`).
- The Spark lane's IR-3 run on `z_continuum` (#2179, issuecomment-6326878563), which reached two calibration launches
  and could go no further.
- The stacking gap: a source-backed run seeds from `development_baseline_commit` (`execution/source_checkout.py:62`),
  and its accepted change is captured as one commit on it (`execution/source_delivery.py:279`, `:314`).

**Who ruled.** The owner ruled the direction and the placement in 2.5, on 2026-10-21. The supervisor (the Spark lane)
wrote this, as H.4's boundary assigns it. The proposals in points 1 and 4 (refusing the start; `upstream_moved` not
counted) and the requirements source in point 5 are the supervisor's, for the owner's review and the MacBook lane's
G4.

### 24bw. A Campaign cycle held on its instruction bindings escalates as its own kind, released by re-supply and never parked (2026-10-21, §10 rows 10, 11, 14 and 15, §24bj, §24bk, §24bp; SIP-0110 §A.3.6, #2178; the supervisor's design, for the owner)

**What it's for.** SIP-0110 §A.3.6's hold (#2178, the MacBook lane's) replaces §5m's failed run. A run whose task
instructions can't be bound, at provisioning or at a re-dispatch, is held, not failed. It's released when the binding
is complete:
- the store answered;
- a §5w intervention revised, narrowed or withdrawn the instruction;
- or a §5v re-binding replaced the revision.

A standalone cycle holds until it's released or cancelled. A Campaign's cycle needs the owner to see it, and an end,
which is this SIP's. The MacBook lane asked whether a held plan gate's path fits.

**It fits in part.** The queue, the bound and where it's seen fit. Its answer and its expiry don't. So a binding hold
is its own escalation kind, `binding_hold`, in the same queue.

**What it shares with a plan gate's escalation (§24bk):**
- **The control log is the queue.** An `escalation_opened` row is keyed by the hold's identity, and one
  `escalation_closed` row is its only ending, compare-and-set as today.
- **The bound is the Campaign's `ruling_bound_s`,** read by the same sweep.
- **It's listed where a plan gate's is:** `campaigns escalations`, the digest and the package. The owner sees a held
  cycle where a held gate shows.

**What is its own:**
- **The identity** is the campaign, cycle, run and held task, plus the unresolved records, each as its id and revision.
  A different set of unresolved records is a different hold.
- **The opening row's binding** names each unresolved record, the reason it couldn't be bound, and its kind, as the
  composer sets it (never parsed from the reason). The hold's cause class is `store` if any record's is, since nothing
  else can be judged then, and `input` otherwise:
  - **`store`:** the memory store didn't answer;
  - **`input`:** a required reference that couldn't be bound at the cycle's commit, or an instruction withdrawn or
    narrowed so nothing is left to bind.
- **It's released, not answered.**
  - The executor records the release on the run (`release_binding_hold(run_id, hold_id, released_at, cause)`, the
    cycle registry's compare-and-set). The sweep reads it and closes the escalation `resolved`, with the release's
    cause as its binding. So the executor writes a release and the sweep ends an escalation, each the only writer of
    its own.
  - `campaigns answer` on a `binding_hold` is refused (422): "released by re-supply, not by an answer".
  - §24bl's late answer and §24bm's carrying never read one.
- **Its expiry is by cause, and never a park.** A plan gate's expiry parks the cycle, and row 15 reads a park as
  `abandon_and_propose`, counted as unaccepted (§24bp). A binding hold says nothing about the squad's work. So when
  `ruling_bound_s` passes with the run still held, the sweep closes the escalation `expired`. It then records the
  release as `expired` through the same compare-and-set, and only if that lands does it cancel the run
  (`binding_hold_expired`). A re-supply that landed since the sweep read the run wins: the run goes on, and the expiry
  stands in the record beside it, as a plan gate's late decision does (§24bk). The cycle then ends by the hold's cause
  class:
  - **`store`:** `CycleEnding.HELD_STORE`. Rows 10 and 11 apply: a retry while retries remain, then escalate.
    Nothing is counted toward `max_unaccepted_increments`;
  - **`input`:** `CycleEnding.HELD_INPUT`, read by **row 17** (new, numbered after row 16 so recorded rows keep their
    numbers): `escalate`, naming the unresolved records, with nothing counted. The owner's re-binding or withdrawal,
    then a resume, continues it.
  - **A held calibration** that expires is still row 2: it wasn't accepted. Its rows name the hold.
  - **Neither ending has a verdict** (`cycle_verdict` gives none to an unassessed ending), so a cancelled run's vacuous
    `accepted` (#2303's shape) promotes nothing.

  `CycleEnding.PARKED` stays a plan gate's alone, read from a plan-gate expiry only (`escalation.parked_run`), so row 15
  never reads a binding hold.
- **Superseded and cancelled read as today:** a run no longer held with no release recorded (an operator's cancel) is
  `superseded`, and a hold still open when its Campaign completed reads `cancelled`.

**The executor's one call on the Campaign side,** `campaigns.binding_hold.open_binding_hold(campaigns, cycle, run_id,
hold, now)`, comes after it records the hold on the run. It writes the opening row for a Campaign cycle, and nothing for
a standalone one. A restart that re-enters the hold finds it standing and writes nothing, so its bound runs from its
first opening, as a gate's does.

**The kinds, as listed:** `plan_review` (a row written before kinds existed reads as one) and `binding_hold`, with its
cause class, on `GET /api/v1/campaigns/{id}/escalations` and in `campaigns escalations`. A hold's unresolved records
stand where a plan gate's failed conditions do.

**Seams it uses, never duplicates:**
- **One binder.** A held Campaign cycle's re-supply fills its missing bindings through the launcher's `_fill_binding`
  (`api/campaign_launch.py`, `cycle_bindings.missing_from`), at the cycle's own commit (SIP-0110 §5ad).
- **The box lease.** A held run keeps the Campaign's lease, and the hold renews it as a waiting gate does. Otherwise a
  `lease_expiry_s` below the bound would fail the run on renewal (§24ai's ceiling, one full lease since §24al).

**What stays:** every row's predicate, the plan gate's escalation and its park, the late answer, and the standalone
cycle's hold, which is SIP-0110's and has no escalation.

**Evidence.** `tests/unit/campaigns/test_binding_hold_escalations.py` enters at `open_binding_hold`, at the sweep
(`CampaignProgress.sweep_ruling_bounds`) and at the hearing (`cycle_ended`), with the run's hold record and the
registry's release stood in for until #2178's run side lands. Its cases:
- for each cause class, the bound respected, then expired, released, cancelled, and read by row 10 or row 17;
- the park never read, and nothing promoted on a vacuous `accepted`;
- a re-supply or re-binding closing `resolved`, and a cancel closing `superseded`, with the run left alone;
- a re-supply that lands before the sweep's release winning;
- a restart writing one row, and a standalone cycle writing none;
- the answer refused.

**Who ruled.** Proposed by the supervisor (the Spark lane) on #2178 (issuecomment-6327598642), and the MacBook lane
agreed to the split and the hold record the same day. Not yet the owner's: it's for the owner's review.

### 24bx. The deploy declares its agents' own models, and an instrument that holds the box names a model no deploy declares (2026-10-22, §9.3, §24an, #2676; implementer's correction, for the owner)

**What was wrong.** §24an read before building that nothing on the deploy loads an undeclared model mid-cycle. Chat
does. Joi, the deploy's chat agent, is in no squad profile and answers on its instance's model, `llama3.1:8b`. The
deploy record (#1720) declared only the squad profiles' models. So after any chat turn the box read Joi's model as
foreign, and every launch was refused `box_not_quiet` until the engine unloaded it, five minutes by Ollama's default.
SIP-0110 makes chat the way a note is saved and an instruction confirmed, so a chat before a launch is its normal path.

**Evidence.** #2183's acceptance run on the Mac (`dep_33612d484ee7`). T5's chat turns, then T13's cycle create, refused:
"engine ollama has llama3.1:8b (46e0c10c039e) loaded, which the deploy record does not declare". Unloading the model
cleared it, and the same create went through.

**What changed:**
- **The record declares the model of each enabled agent instance whose service the deploy runs** (`instance_models`,
  from the configured agent instances file), as well as the profiles'. A deploy whose instances file is missing is
  refused, unrecorded.
- **The two instruments that hold the box name their model.** The 2.0 lease proof and blocked legs used `llama3.1:8b` as
  the model no deploy declares, and it's Joi's, declared now.
  - `campaign_lease_proof.py --stand-in-model` is required.
  - `campaign_recovery_diagnostics.py --foreign-model` is required for `restart-queued-successor` and
    `box-held-past-the-lease`.
  - A model the active record declares is refused before any step or injection.
  - The records those runs left stand, since the model was undeclared then.

**What stays.** The rule: every engine read, every loaded model declared, and none serving (SIP-0111 §5.5). A model a
person loads by hand is still undeclared and still refuses a launch. A chat request being served still makes the engine
busy.

**Who ruled.** The MacBook lane's correction, under the owner's 2.4 delegation. The instruments are the Spark lane's, and
its review is asked on the PR. For the owner's review.

### 24by. A change request may name the goals it means to move, and only its proposer and the supervisor see them (2026-10-22, §7.2, §9.1, §9.2; SIP-0113 §4.5, §10t ruling 4, #2677; the supervisor's design, for the owner)

**What changed.** §7.2's change request gains one authored field, `moves_goals`: the ids of the goals the proposal means
to move, from the scenario goals SIP-0113 §4.5 shows the proposal run (§10t step 1). After the build, the ledger reads
each named goal against the increment's own evaluation (§10t step 5).

| field | type | read by |
|---|---|---|
| `moves_goals` | goal ids, each one the proposal run was shown | the rails (§9.1), the supervisor (§9.2), the ledger (SIP-0113 §4.5) |

- **The rails refuse an id the proposal wasn't shown,** as `unknown_goal`, with every other refusal. Naming a goal that
  already passes is not refused (§10t ruling 5).
- **An empty list is left out of the stored document and out of `content_hash`.** So every request ruled on before this
  field existed keeps its hash and loads as it was ruled. A non-empty list is in the hash, so the ruling binds the goals
  the supervisor saw.
- **Framing is shown the request without the field** (`role_view`, at `increment_change_request`). No framing or build
  role learns which held-out goal its work is aimed at. The build roles were never shown the document, only what it
  derives.

**Evidence.**
- Every change request stored on the Spark's vault (117) loads, stores back byte for byte and is unchanged by the role
  view. So do the three stored in `tests/fixtures/campaigns/`.
- The rails' tests: `tests/unit/campaigns/test_change_request.py`. The handler, entered at `handle()` with the evidence
  on its inputs: `tests/unit/capabilities/test_strategy_propose_increment.py`. The framing, entered at
  `RunProvisioning.prepare`: `tests/unit/cycles/test_proposal_evidence_wiring.py`.

**What stays.** Every other field, rail and refusal. The proposal's prompt doesn't yet tell the model the field exists;
that comes with the evidence it names (§10t step 4).

**Who ruled.** The supervisor's design (SIP-0113 §10t ruling 4), under the owner's 2.4 delegation and D4's ruling of
2026-10-22. For the owner's review.

### 24bz. A campaign's proposal is shown its accepted tree's outcomes, and a request that repeats a goal is refused (2026-10-22, §9.1, §7.2, §24by; SIP-0113 §4.5, §10t rulings 2 and 7, #2677; the supervisor's design, for the owner)

**What changed.** §9.1's proposal run is shown three more parts of its context, beside the PRD. Each is read by
SIP-0113's reader from the campaign's own records, and each renders only when it holds something:
- **the PRD as the accepted increments left it:** their `prd_delta` sections, folded by id in promotion order;
- **the campaign's goals:** each goal of its pinned suite with its result on the accepted tree (`failed`, `not
  verified`, `passed`, the gaps first), and how to name the ones the change aims at in `moves_goals` (§24by);
- **the quality moves:** each measure against the first accepted build.

A proposal outside a campaign, or one with nothing to show, renders as before and is never told of `moves_goals`.

**One more rail, `goal_text_copied`.** A PRD section, or a criterion's statement or observable, that repeats a shown
goal's statement word for word is refused by the goal's id and where, never by its text. Every framing and build role
reads those fields, and the goal is the evaluator's (SIP-0113 §10t ruling 7). The goals asset tells the model to write
them in the change's own words.

**Evidence.** `request.strategy_propose_increment` v15 rendered through the real handler on a live proposal's stored
inputs (`run_970b65eddddc`, `cmp_263d1e49aca8`), with the reader's evidence for the tree it proposed on. Without the
evidence it reproduces the stored prompt exactly. With it, the request adds the three sections and 25 goal lines, from
6,809 to 8,058 estimated tokens. The handler and rails tests: `tests/unit/capabilities/test_strategy_propose_increment.py`
and `tests/unit/campaigns/test_change_request.py`.

**Who ruled.** The supervisor's design (SIP-0113 §10t), under the owner's 2.4 delegation and D4's ruling of 2026-10-22.
For the owner's review.

### 24ca. A repair or a retry carries the increment's own keys and its lineage, never a copy of the failed cycle's block (2026-10-23, §10a, §24u; #2578 part 1, after #2558 and #2576; implementer's correction, for the owner)

**What was wrong.** A continuation's `campaign_proposal` block was the failed cycle's block, copied whole, with
`repair_of` and `prior_cycle` then deleted. #2558 and #2576 were both keys of one cycle carried into the next that
way. Any key added later rode along by default, and so did the keys only a proposal reads: `abandoned_increment`,
`qa_proposed_behaviours`, `unapproved_proposals`, a revision's note. A continuation runs no proposal.

**What changed.** The block is built from `CONTINUED_KEYS` (`launch_requests.py`) and the launch's own lineage.
- `CONTINUED_KEYS` holds the binding and what every increment seam reads of it, as the increment's launch wrote them:
  `proposal_id`, `version`, `baseline_tree`, `accepted_cycle_id`, `baseline_manifest`, `objective`, `prior_criteria`,
  `frozen_criteria` and `max_revisions`.
- The lineage is `continues`, `repair_of` for a repair, and the brief of the cycle it continues, `prior_cycle`.

**Evidence.** Every campaign cycle the Spark has stored carries the nine keys. A test plants proposal-only keys and an
invented later lineage key in a failed increment's block, and finds the retry carries none of them. Copying the block
again fails it, and #2558's test.

**What stays.** #2578's other parts (an `increment_id` on each cycle, Prefect tags, a per-increment view in the
ledger) await a ruling.

### 24cb. A cycle stopped at its plan gate built nothing: no verdict, row 2 for a calibration, row 18 for an increment (2026-10-23, §8.4, §10 rows 2, 4, 6 and 8, §24bj, §24bp; #2704, after #2303; implementer's correction, for the owner)

**What was wrong.** `cycle_ending` gave a non-assessed ending only to a proposal run, a park or a binding hold. A
framing run stopped at its plan gate read `assessed`. That covers the plan check's rejection with no re-roll left, a
person's rejection, a revision none could run, a decision the gate doesn't know, and a gate that failed. #2303 made
`cycle_verdict` give no verdict to a cycle that never reached its build, but only for an ending other than `assessed`.
So the framing run's summary, which reads `accepted` with nothing executed, was taken as the cycle's verdict.
- **A calibration** was promoted as accepted, with an empty tree as the campaign's baseline, and row 5 proposed an
  increment against it.
- **An increment** whose approved change's plan was refused had no increment evaluation, so it read
  `blocked_unverified`. Row 8 then repaired a candidate that was never built, and spent the increment's repair.

**What changed.**
- **A new ending, `stopped_at_plan_gate`.** A framing run stopped at its gate for any of those five reasons ends the
  cycle this way. Like every ending other than `assessed`, it has no verdict, and the outcome evaluation (SIP-0113
  §4.1) doesn't run on it.
- **A calibration** with it ends the campaign on row 2: `stop_failure`, cause `calibration`.
- **An increment, repair or retry** with it is **row 18**, asked before row 6, as row 15 is: `abandon_and_propose`.
  - It counts toward `max_unaccepted_increments` at its own decision, as a park's abandonment does (§24bp). So the
    plan stop that reaches the limit ends the campaign on row 4 instead of proposing once more.
  - It spends nothing of `max_repair_cycles_per_increment`. No repair or retry is launched, since nothing was built
    to repair. The next cycle is a fresh proposal.
- **A proposal run stopped by a decision the increment gate doesn't know** is `proposal_failed`, as a gate that failed
  already was (#2213). The plan check never judges a proposal run (`PLAN_JUDGED_WORKLOADS`), so no proposal stops on
  `plan_rejected`.

**Evidence.** Live on the Mac, deploy `dep_c412e3a206f8`, #2183's campaign `cmp_889af0a98b6d` on lite-14b:
- Calibration `cyc_a807ab739918`'s three plans were auto-rejected at `progress_plan_review`. Twice two tasks declared
  `backend/routes.py`; once a regex check named a source file.
- The control log then recorded `promote` with "its 0 delivered files" and identity `e3b0c44298fc…`
  (`FileTree.of({}).identity`), then `decide` with row 5, `ending: assessed` and `verdict: accepted`. Increment
  `cyc_6ee156954613` launched on it. The campaign was aborted.

Tests enter at the completion hook (`CycleCompletion.end`):
- A calibration whose framing run stops for the plan check, a rejection or a failed gate ends the campaign on row 2,
  promoted nothing, and was never evaluated.
- An increment whose plan stops is abandoned on row 18, with a fresh proposal launched and no repair. With
  `max_unaccepted_increments` at 1 it ends on row 4.
- Reverting `cycle_ending` fails 10 of the tests. Leaving the abandonment uncounted fails the limit test. Dropping row
  18 fails 3.

**What stays, deliberately.** A framing run that ended `run_failed`, or `run_cancelled` without being parked, stopped on
its own run, not at its gate. It stays `assessed` on purpose, so its assessment decides it, attribution included. A
failure outside the work still routes to a retry on rows 10 and 11, which a no-verdict ending would skip. This
correction changes only the stops at a gate. Nobody has seen a failed framing run's assessment read `accepted`, and
this correction doesn't change that path.

### 24cc. A calibration record is what the first accepted tree names, and unclassed test files refuse a Campaign's start (2026-10-24, §7.1, §10 rows 2, 4 and 5, §12a, §15, §16, §24bv points 1 and 3; SIP-0112 H.6, H.7; #2619; the supervisor's design, for the owner)

**Why.** §24bv point 1 makes a repository-backed Project's calibration a record, not a cycle. Building it showed
that two parts of the accepted design no longer describe what runs:
- §7.1 has the first increment's baseline be "the accepted tree … of the calibration cycle", and §15's accepted
  tree named its cycle. After a record, there is no such cycle.
- §24bv point 3 has unclassed test files block only `feature` and `fix` increments, "named at configure time".
  SIP-0112 H.6 makes the gap a stop for a Campaign's start, and H.7 names it at baseline capture.

**What changed.**
1. **The accepted tree names its cycle or its calibration record: exactly one of the two** (§7.1, §15, §16).
   - `AcceptedTree` carries its identity and exactly one of `cycle_id` and `calibration_record_id`. The dataclass
     refuses neither and both.
   - Migration 1697 adds `campaigns.accepted_calibration_record_id`, and replaces 1630's both-or-neither CHECK with
     one that holds the identity and exactly one of the two together.
   - A record's identity is its commit's tree identity (contract 4), read from the mapping its baseline capture
     recorded.
   - A cycle's promotion hashes as it did before (`transition_request_hash` leaves the new field out when it's
     empty), so a promotion committed before the upgrade still replays after it.
2. **Every reader of the accepted tree's cycle reads a record, or refuses it by name.** None passes an empty cycle
   on.
   - The proposal launch (`_propose_launch`) returns the record as unbuilt, so the campaign escalates naming §24bv
     point 5.
   - `increment_launch` raises for a tree that names no cycle. So `campaign_proposal.accepted_cycle_id` is never
     written empty, and the seams downstream (`accepted_cycle_of`, the proposal's evidence, the evaluated tree) only
     ever read a cycle.
   - The latest decided cycle, read by the owner's word, is none after a record's decision. Its target is the
     record's id, never looked up as a cycle.
   - The campaign's read (`AcceptedTreeDTO`) carries whichever one it names.
   - The record's promotion and decision rows name the record, never a cycle. Each package reader is fixed to
     match:
     - the digest's accepted list names the record, its commit and its tree;
     - "no partial promotion" holds for a record's promotion when it names its commit, since its tree is the
       managed clone's and has no vault reference;
     - the proposal ledger reads a record's decision as deciding no proposal;
     - the proposal evidence reads no cycle evaluation for it (SIP-0113 §10l's reading of the record's commit isn't
       built).
3. **The record lives in the start's own control-log row** (§12a, §16). The start row's binding holds it whole
   (`calibration-record/v1`), so the start and its record commit together, and no table is added. It holds:
   - the Project's baseline commit and configuration revision (as `pin_source_context` reads them);
   - the commit's tree identity;
   - the inherited baseline at both, by a digest of its checks and each check's result;
   - the disclosed gaps of the derived profile at the Project's pin. It's read as `prepare_cycle` reads a Cycle's
     (SIP-0112 H.8): `get_derived_profile(project_id, at=(commit, revision))`, never the latest capture's.
4. **The record's own path, in a cycle's order** (§10: promotion first; §12a).
   - `promote`, keyed by the record and its identity, names the record and its commit. Nothing goes to the vault
     and nothing is frozen.
   - Then `decide`, keyed by the record. Its ending is `calibration_recorded` and its verdict `accepted`.
   - The start route runs both after the memory pin. A restart, or a failed hearing, between any two of the three
     rows is re-heard at startup and on the sweep's interval (`rehear_calibration_records`, beside `rehear_ended`).
     The keys make a second hearing write nothing.
5. **Rows 2, 4 and 5, as built** (`calibration_record_decision`).
   - Row 5 proposes.
   - Row 2 can't fire, since a start that would fail it is refused.
   - No limit of row 4 and no guard of step 3 counts the record: it's no cycle, spends no tokens and is no
     unaccepted increment.
   - The guard still reads the elapsed time from the start.
6. **The refusal: 409 `CALIBRATION_REFUSED`, with its cause in the details.** The causes:
   - `project_not_ready`, including a Project with no validated commit or no configuration revision;
   - `drift_unreconciled`, read by SIP-0112 H.2's `unreconciled`;
   - `no_baseline`, at that commit and revision, or with no tree recorded at the commit;
   - `no_profile`: none is recorded at the pin (contract 8). A profile derived at another commit or revision is
     never read in its place, so there's no separate stale cause;
   - `blocking_gap`, naming each gap's id and what closes it. Every blocking gap refuses the start (H.6), not only
     those that stop `work`.

   **No refusal is reached twice.** The start creates no cycle, so `prepare_cycle`'s own blocking-gap refusal
   (H.8's 409 `PROJECT_STATE_CONFLICT`) is never reached for it, nor is the plan gates' validator. H.8
   leaves refusing a Campaign's start to this point.

   **Nothing is written, not even a refused row.** Like the start refused for a request profile that doesn't
   exist (422), it's refused before it reaches the control log, so §12a's "refused and recorded" doesn't apply.
7. **Point 3, matched to H.6.** Unclassed test files refuse the Campaign's start: the derived profile's blocking
   `test_files_unclassed`, which H.6 makes a stop for `campaigns`. That's stronger than point 3's "a blocking gap for
   `feature` and `fix` increments". The gap is named at baseline capture, where H.7 derives the profile, not at
   configure time.

**Where it stops, by design.** Row 5's proposal input on a repository-backed Project is §24bv point 5, the MacBook
lane's. Until it lands, the record's decision escalates with that reason, and the owner's resume answers it the same
way (422). Not in this amendment:
- the creation rules (`calibration_profile`, `policy.stack`, `proposal_profile`);
- the campaign branch and promotion onto it (point 2);
- the increment's pin (contract 1).

**Evidence.** The tests enter at `POST /api/v1/campaigns/{id}/start`
(`tests/unit/api/test_campaign_calibration_record.py`):
- **The wiring.** It runs on the shared fixture's Tally, with its baseline really captured: the managed clone and
  the workspace store are real, and the checks run as local processes. The record names the capture's commit,
  revision and checks, and Tally's two disclosed gaps. Its tree is the fixture's own recorded tree identity. No
  cycle or intent is created. Row 5 proposes and escalates on point 5.
- **Each refusal cause, 11 cases.** Each one leaves the control log at its creation row, and creates no cycle.
- **A restart before the promotion, and one between the promotion and the decision.** Each is heard once at
  `main._resume_campaigns`, and a second startup writes nothing.
- **The abort's package.** It names the record, and "no partial promotion" holds.
- **The owner's word and the ledger** after the record's decision escalated. The resume names point 5 (422), and
  the ledger reads.
- **A sample application's start** still launches its calibration cycle.

`tests/unit/campaigns/test_calibration_record.py` holds three things: the decision with every limit at its floor,
the exactly-one tree, and a cycle's promotion hash, which is the one `origin/main` computes. The Postgres test
reads a record's tree back after a restart and refuses a row naming both.

Fifteen mutants, each caught by these tests:
- the route never taking the record path;
- the record counted toward the budget, or the elapsed time not read;
- `test_files_unclassed` not a stop, drift not read, or a profile of another commit read in place of the pin's;
- the tree identity not read from the mapping;
- no re-hearing at startup;
- the new field in a cycle's promotion hash;
- the latest decided cycle, the digest, "no partial promotion" or the ledger reading a record as a cycle;
- `increment_launch` accepting a record's tree, or a tree naming both.

**Who ruled.** The supervisor (the Spark lane), implementing §24bv, for the owner's review. The choice in point 1 (a
tree names its cycle or its record, rather than the record wearing a cycle's id) is the supervisor's design call,
recorded as risk 2 of the 2.5 build plan for §24bv.

### 24cd. §24bv points 2–4 as they will be built: the head is read at launch, a rebase supersedes what it makes stale, and acceptance runs where the product's toolchain is (2026-10-24, §7.1, §8.2, §8.4, §12a, §12b, §24bv; #2619; the supervisor's design, for the owner, with the MacBook lane's G4 on the contract points)

**What was found.** A read of the code against §24bv, before building it, found seven places where §24bv's text can't be built as written, or leaves the build a choice. Each is settled below. The seams are on main at `daf63168`, and each is named.

**1. The head is read at launch, and handed to the cycle as a typed field (§12b, §24bv point 3).**
- **What's wrong today:** a launch intent fixes its `baseline_tree` when its decision is written (`campaigns/launch_requests.py:100`), and a ruling is refused once the accepted tree moves past it (`campaigns/lifecycle.py:245-251`). Under §24bv point 4 the branch can move at drain time, by a rebase, so every intent written before it would go stale.
- **Built:** a repository-backed increment's intent binds no tree. The launcher reads the campaign branch's head at drain (`campaign_branch.head(campaign_id)`) and hands it to cycle creation as a `CampaignHead(commit, tree_identity, previous_verification_ref)`.
  - `prepare_cycle` pins the increment there, through the MacBook lane's additive `ProjectSourceContext.pinned_commit` and `pinned_from` (contract 1's increment pin). `development_baseline_commit` keeps meaning the Project's baseline, so H.2's drift gate still keys on it.
  - A repository-backed increment without a head is refused, never defaulted.
- **A sample application's intents** are unchanged: they bind their tree as today.

**2. A rebase supersedes what it makes stale, in its own transition (§12b, §24bv point 4, D10).**
- `BRANCH_REBASED` is a control-log transition, and moves the accepted tree's base and head. In the same transaction, a pending repair or retry built on the old head is marked `superseded` (a new intent state). Its increment is abandoned as `upstream_moved`, and row 6's fresh-proposal intent is written.
- **D10's exemption:** `upstream_moved` counts toward no `max_unaccepted_increments`. Cycles, tokens and time keep their limits.
- **A Git ref can't join a database transaction.** The control row commits first, and the branch's ref then follows it by compare-and-swap. At startup, a ref that disagrees with the latest row is moved to it, so the row is the authority and the ref its projection. This replaces point 2's "in the same keyed transition" for the ref.

**3. The launcher never reconciles a Project (§24bv point 4, SIP-0112 H.2).**
- It rebases only onto a commit the Project has already reconciled (validated, configured and baselined, as today, by whoever reconciles).
- A relevant drift not yet reconciled refuses the launch as H.2's gate does (`api/routes/cycles/cycles.py:469-483`): it escalates with the intent pending.
- **A blocking gap at launch:** SIP-0112 H.8 refuses a Cycle whose known work meets a blocking gap, in `prepare_cycle` (`ProjectStateConflictError`, 409). A Campaign meets one only when a reconciliation in mid-Campaign records a profile with one. The launcher escalates on that refusal with the intent pending, as it does for H.2's gate.
- **Which profile an increment reads:** the derived profile at the Project's pin (`development_baseline_commit` and its configuration revision), not at `pinned_commit`. So every increment of a Campaign reads the same profile between reconciliations.

**4. The owner's merge is a rebase that ends at the merge commit (§24bv point 4).** When the owner merges the review request, the next sync reports upstream at the merge commit, and the Project is reconciled there. The launcher's pre-launch comparison then rebases the branch onto it. The branch's increments are already in it, so the rebased head is the merge commit itself. No separate trigger exists or is needed, and H.2's attribution reads the increments as integrated.

**5. The rebase's verification runs the frozen criteria too (§24bv point 4, §8.1).** It runs the product's checks and every frozen criterion's bundle on the rebased head. So a break upstream caused is found at the rebase (`REBASED_HEAD_REGRESSED`), never blamed on the next increment.

**6. Acceptance on the product's runner runs in the sandbox, runtime-side (§8.4, §24bv point 3).**
- §8.4 puts the increment evaluator in its role's container. A repository-backed product's toolchain exists only in the sandbox, where its declared commands run (SIP-0102 X-3a).
- So its accumulated acceptance and discrimination run there, through the runtime, with each overlay built as a revision of the tree.
- The plan drops `qa.evaluate_increment` for a source-backed increment, keyed on the cycle's source context. That is the MacBook lane's recipe change, and it lands with or after this build, never before.
- §8.4's other rows, and a sample application's evaluator, are unchanged.

**7. For the owner: two questions this doesn't settle.**
- **"For the intended reason" (§8.2) on a product's own runner.**
  - pytest's findings reader keys only failed and errored test ids (`sandbox/findings.py:154-179`), so a criterion failing on the baseline by an `ImportError` reads the same as one failing behaviourally. vitest has no test-id reader at all (H.7's disclosed `no_test_id_reader`).
  - **Proposed:** a pytest reader that carries each failure's exception class, built with this, so §8.2's rule holds on pytest. On a runner with no such reader, a criterion's discrimination is unread, and it isn't accepted as discriminating. That holds the rule rather than weakening it, and may leave a vitest-only criterion unacceptable until a reader exists.
  - **Yours to rule:** keep that, or accept a whole-file reading as a disclosed limitation.
- **The Campaign's review request** (§24bv point 2, H.4).
  - Today a review request is the owner's act, one per run (`projects/contribution.py:81-152`). Pushes are never forced (`ports/projects/source_repository.py:79`), and a branch name is one segment (`adapters/tools/git_source.py:54`).
  - A Campaign's single review request needs an automatic push on the deploy's credentials, and a forced one after a rebase.
  - **Yours to rule:** whether it is automatic, and when, and on whose credentials. A contribution's push uses the owner's token for that act only, so an automatic push is a credentials ruling as well as a timing one. Until then the branch lives in the managed clone, and nothing is pushed.

**What stays:** §24bv's points 1 and 5, every row's predicate, and a sample application's Campaigns.

**Evidence:**
- the seams named above;
- the MacBook lane's answers on the pin, the recipe and `create_campaign` (2026-10-24, cross-lane);
- the Plan read of 2026-10-24, kept with the supervisor's build plan.

**Who ruled.** The supervisor (the Spark lane), implementing §24bv under the owner's direction of 2026-10-21 and the overnight grant of 2026-10-24. Points 1 to 6 are the build's. Point 7's two questions are the owner's. Points 1 and 6 meet the MacBook lane's contract 1 and recipe. The MacBook lane approved both (G4 on PR #2733, 2026-10-24) and added point 3's last two items.

### 24ce. An increment is promoted onto its campaign branch from its own capture, and a capture the branch can't take escalates (2026-10-24, §7.1, §7.5, §12a, §24bv point 2, §24cd points 1 and 2; #2619; the supervisor's design, for the owner)

**Why.** §24bv point 2 makes a repository-backed Project's accepted tree the head of a campaign
branch, and §24cd point 2 has the control row commit first with the ref following it. Building
it forced five things neither says.

**What changed.**
1. **A capture the branch can't take is refused, and the campaign escalates** (§24bv point 2,
   §12a).
   - §24bv says the capture's parent is the head, but not what happens when it isn't. The
     promotion is refused, and nothing is written: no PROMOTE row, and the accepted tree and the
     ref stay where they were.
   - It's refused when the capture was built on a commit other than the head, the run captured
     nothing, the run recorded no source verification, the campaign has no head, or the runtime
     has no managed clone wired.
   - The decision row still follows, and names the refusal (`promotion_refused`). A decision
     under `proceed` launches nothing on the tree the increment would have replaced: the
     campaign escalates, with the refusal as its reason (`unbuilt`). A terminal decision still
     completes the campaign.
   - Until contract 1's increment pin lands (§24cd point 1), every increment is pinned at the
     Project's baseline. So the first accepted increment after the record is promoted, and a
     second accepted increment is refused this way, never stacked over the first.
2. **The head is read from the row and its log** (§24cd point 1).
   - `head(campaign, log)` returns `CampaignHead(commit, tree_identity,
     previous_verification_ref)`. §24cd named `head(campaign_id)`, but the verification isn't
     part of the accepted tree: it is on the PROMOTE row that made the head.
   - A tree that names no commit raises `NoCampaignHead`, never a default.
   - Nothing reads the ref for the head.
3. **What a promotion on the branch records.**
   - `AcceptedTree` carries `commit` beside its identity: the record's commit, or the
     increment's captured one. Migration 1698 adds `campaigns.accepted_commit`, held by a CHECK
     to a commit id beside an identity. A sample application's tree names none, and the request
     hash leaves an empty commit out, so every promotion committed before the upgrade replays.
   - The increment's PROMOTE row names `commit`, `parent_commit` and `verification_ref` (the
     run's source verification), and no `tree_ref`: nothing is composed from the vault or stored
     there. Its new criteria are frozen as any increment's are (§8.1).
   - "No partial promotion" (§12a) reads a promotion naming its commit as whole. The digest
     names the commit.
   - The capture is read from contract 3's mappings: the run's delivery workspace's CAPTURED
     mapping, with its parent read from the same workspace's SEEDED mapping. The contribution
     reads it through the same function.
   - The path is chosen by the cycle: a source-backed increment, repair or retry. A calibration
     cycle and every sample application's cycle keep the vault's path.
4. **A restart between the row and the ref.**
   - A re-hearing of the cycle (§24v) finds its capture already the head, and replays the same
     promotion. It writes no second row, and isn't refused as built elsewhere.
   - The follow is one compare-and-swap, from the commit the row replaced. A ref already at the
     head is a replay's. Any other refusal or failure is logged and never raised.
   - The re-sync runs at startup, before the drain, and on the sweep's interval (§24cd says at
     startup), so a follow that failed while the process stayed up is caught within a sweep.
     It reads the ref before the row, so a promotion committing in between is never undone.
5. **The record's promotion creates the branch** at the record's commit (`expected = None`).
   A replayed record promotion finds it made.

**Where it stops, by design.**
- The launcher doesn't hand `CampaignHead` to cycle creation yet. That waits for the MacBook
  lane's `ProjectSourceContext.pinned_commit` and `pinned_from` (§24cd point 1, contract 1).
- The regression baseline from `previous_verification_ref` (§24bv point 3), acceptance on the
  product's runner (§24cd point 6), the rebase (point 4) and the review request (§24cd point 7)
  are later builds. Nothing is pushed.

**Evidence.**
- The wiring test enters at `CampaignProgress.cycle_ended` after a real
  `deliver_source_change` over the shared fixture's managed clone
  (`tests/unit/campaigns/test_campaign_branch.py`). The accepted tree is the capture's commit
  and the commit's own tree, read back from Git. The ref is at the capture, and the package
  holds "no partial promotion".
- The same file holds:
  - a second increment pinned at the Project's baseline, refused and escalated;
  - a failed increment, whose capture stays at its own ref;
  - a follow that failed, moved at `main._resume_campaigns`;
  - a stop between the row and the ref, promoted once and decided once at startup.
- `tests/unit/tools/test_git_source.py` holds the compare-and-swap refusing a stale expected
  commit and a create over an existing branch. The Postgres test reads the commit back after a
  restart, and refuses a malformed one or one with no tree.
- `tests/unit/campaigns/test_progress.py` holds a sample application's promotions with the
  branch wired, unchanged.
- Thirteen mutants, twelve caught. The thirteenth was a second compare-and-swap in the follow
  that no reachable path exercised, and it was removed (item 4).

**Who ruled.** The supervisor (the Spark lane), implementing §24bv and §24cd under the owner's
direction of 2026-10-21 and the overnight grant of 2026-10-24, for the owner's review. Item 1's
escalation is the supervisor's design call.

### 24cf. A campaign cycle names its increment, and its flow runs say which increment and which kind (2026-10-24, §10a, §12b, §16, §24ca; #2578 parts 2 and 3; the supervisor's design, the MacBook lane's G4 on part 2)

**What changed.**
- **`increment_id` on each cycle.** It is the increment's proposal id, on `Cycle`, on contract 2's cycle record (the cycle DTO) and in an indexed `cycle_registry.increment_id` column (migration 1699).
  - **The campaign's launcher sets it,** and nothing else does. It reads it from the launch's own `campaign_proposal` block (`launch_requests.increment_id_of`) and hands it to `prepare_cycle` as a keyword, as it hands `campaign_id` and `kind`.
  - **A repair or retry** carries its increment's id, through part 1's allow-list (§24ca), never from its predecessor's row.
  - **A re-proposal** carries a new one. A calibration, and a cycle no campaign launched, carry none.
  - `CycleCreateRequest` gains nothing, so a standalone create can't name an increment.
- **A launch whose block names no proposal is refused,** escalating the campaign (`LaunchRefused`), never defaulted to empty. No re-drain can supply what the intent lacks.
- **The control log stays the source of truth.** The column is its projection, and a test holds every launched cycle's `increment_id` equal to the proposal id its own launch names.
- **Prefect tags `increment:<id>` and `kind:<kind>`** join the flow run's tags, for operators only. Nothing reads a tag to decide.

**What stays.** Part 4, the per-increment view the ledger lists, is its own PR. There is still no writable increments table.

**Evidence.**
- **The wiring:** a test enters at `CampaignLaunchService.drain()`, over calibration, increment and repair intents written by `calibration_launch`, `increment_launch` and `bound_launch`. It finds the calibration empty and the increment and its repair naming one proposal.
- **The refusal:** a test finds an intent without a proposal escalating the campaign with no cycle created.
- **Persistence:** the Postgres round trip holds the column.
- **The tags:** the executor's flow-run tag test holds the new tags.

**Who ruled.** The owner placed parts 2–4 in 2.5 ("3–5 yes", 2026-10-23). The MacBook lane approved part 2's design on #2578 (issuecomment-6381040179): set by the launcher, read from the continuation's own binding, a projection with its test, and independent of contract 1's `pinned_commit`. The supervisor (the Spark lane) built it.

### 24cg. The ledger lists each version's cycles, and the last one's end is the version's outcome (2026-10-24, §9.4, §10a, §24ca, §24cf; #2578 part 4; implementer's correction, for the owner)

**What was wrong.**
- The ledger (§9.4) gave each proposal version the decision of the cycle that carried it, and only that cycle's.
- An increment spans its cycle, then any repair or retry of it, so the ledger showed a repaired version with the row that decided its first try, and never attached the repair's own end.
- The 2.4 window's campaign 1 shows this: sorting's first try appears as row 12 (repair), and the repair's abandonment (row 13) isn't attached.

**Built:**
- **Each ledger entry lists the cycles that carried its version** (`cycles`), in launch order. Each shows its id, its kind (`increment`, then `repair` or `retry`) and, once decided, the deciding row's fields. The entry's `outcome` is its last cycle's decision.
- **A repair or retry is attached by its own launch's binding,** the proposal and version `CONTINUED_KEYS` carry into its block (§24ca), read from the launch outbox. It is never attached by cycle order.
  - So campaigns run before #2578 part 2's `increment_id` read correctly too: their launches always carried the binding.
  - A continuation whose binding names a version never submitted is listed under none.
- **The CLI's `campaigns ledger`** shows each version's cycles beside its ruling.
- **There is still no writable increments table** (#2578's part 4): this view is derived from the log and the outbox.

**Evidence.** The ledger route's tests, entered at `GET /api/v1/campaigns/{id}/ledger`:
- a repair launched by the owner's resume (`bound_launch`) is listed under the version it continues, first with no row and then with its own deciding row, which becomes the version's outcome;
- a continuation of another proposal is listed under none.

Two mutations are each caught: the route not reading the outbox, and attaching by order.

**Who ruled.** The owner placed #2578 parts 2–4 in 2.5 ("3–5 yes", 2026-10-23). The supervisor (the Spark lane) built this part.

### 24ch. An increment's scope governs its product files, and the qa test namespace is the framework's (2026-10-28, §7.2, §9.1, §9.2 condition 4, §24bj; #2743; the owner's ruling)

**What was wrong.**
- The footprint (§7.2) is derived, never authored: each product file whose expansion the delta changes, plus the stack's qa test namespace as `<dir>**` patterns, which `derive_footprint_from` appends whatever the delta.
- §9.1's rail held the whole footprint to the objective's `allowed_scope`, those patterns included. §9.2's condition 4 held every file a plan names to it, the criterion tests included.
- So a narrow scope refused every increment. Campaign `cmp_b79783b2…` (2.4.0, `fullstack_fastapi_react`) was scoped to `backend/routes.py` and `backend/tests/test_runs.py`, for a backend-only fix to the runs list's order. Its proposal was refused `out_of_scope` on `backend/tests/**`, `frontend/src/__tests__/**` and `frontend/src/tests/**`, which no scope entry naming a file can cover, and the campaign closed `exhausted`.
- Narrowing the patterns to the scope would not have been enough. The framework writes an endpoint criterion's test at `backend/tests/criteria/test_{criterion}.py`, which the same scope also leaves out.

**The ruling** (the owner, 2026-10-28, "go with option 1"):
- **The objective's scope governs the change's product files.**
- **The stack's qa test namespace is the framework's.** The scope does not read it, and the verdict names it.
- **Rejected:** letting the scope narrow the namespace, refused with the criterion-test path named. It would have kept the owner's control of where tests go, but it still refused the reproduction.

**Built:**
- **One reading for both checks.** `outside_allowed_scope` takes the stack, and leaves out every path in its qa test namespace (`qa_namespace_paths`, by `is_qa_test_path_for_stack`). That covers the footprint's `<dir>**` patterns and any test file a plan names there. §9.1's rail and §9.2's condition 4 call it, so the two still cannot disagree.
- **An unknown stack has no namespace,** so every path stays the scope's. The plan-review tier reads the stack from the run's manifest (`manifest_stack`), and with no manifest it already escalates on condition 3.
- **What the reader sees:**
  - a refusal for a product file outside the scope names the namespace as the framework's;
  - the tier's reading lists the plan's files in the namespace beside its product files;
  - an accepted request's footprint still names the patterns the build may write.
- **The write grants are unchanged.** The qa namespace was already granted to the test author by its own declaration, not by the scope (`write_authorization.py`).
- **The cost:** an objective can no longer say where tests may go. A scope of test files alone admits no product change, and its refusal says so.

**Evidence:**
- **The issue's reproduction,** entered at `validate_proposal` on the 1.9 baseline: `GET /runs` given a declared order, under the scope of the route file and one test file. It is accepted, with footprint `backend/routes.py` plus the three namespace patterns. On the code before this change it is refused exactly as #2743 reports.
- **The same delta under a scope of the test file alone** is refused, naming `backend/routes.py` and the namespace.
- **At the gate,** entered at `WorkloadGate.decide`: a tier campaign scoped to `backend/routes.py`, whose plan names `backend/tests/criteria/test_c1.py`, is approved by the tier. Its notes name the test file as the framework's.
- **Six mutations are each caught:**
  - the namespace not left out;
  - every path left out;
  - the gate passing no stack;
  - `manifest_stack` reading none;
  - the tier dropping the stack;
  - the refusal no longer naming the namespace.

**Who ruled.** The owner (option 1, 2026-10-28), on the supervisor's analysis in #2743. The supervisor (the Spark lane) built it.

### 24ci. §24cd point 7 ruled: discrimination on a product's runner needs a test-id reader, and the supervisor pushes the Campaign's review request (2026-10-28, §8.2, §24bv point 2, §24cd point 7; SIP-0112 H.4, H.7; #2619, #2757; the owner's ruling)

**What was open.** §24cd point 7 left the owner two questions about a Campaign on a repository-backed Project. The supervisor recommended an answer to each, and the owner took both, changing who pushes: "Go with your recommendations but for you to push not me".

**(a) "For the intended reason" (§8.2) on a product's own runner: the rule holds.**
- **A runner with a test-id reader:** pytest's reader is extended, with §24bv point 3's build (#2619), to carry each failure's exception class beside its test id. A criterion that fails on the baseline only by an `ImportError`, or by any setup failure, then doesn't read as discriminating, as on the sample applications' stacks.
- **A runner without one:** the criterion's discrimination is unread, and it isn't accepted as discriminating. vitest is such a runner today (H.7's disclosed `no_test_id_reader`).
- **Rejected:** a whole-file reading, disclosed as a limitation. It would count a test file that fails to import on the baseline as discriminating, which is the failure #2602 removed on Next.js pages.
- **The cost:** a Campaign whose criteria run only under vitest accepts no criterion until a vitest reader exists. That reader is #2757, placed in 2.5 before `z_shelfnote`'s demonstration, since that Project tests its frontend with vitest (SIP-0112's H.4 reading of its configuration).

**(b) The Campaign's review request: the supervisor pushes it, at the Campaign's close or on request.**
- **No automatic push from the deploy.** That would need a token with write access stored in the deploy for it (`projects.review_request_tokens`), and nothing is stored for it.
- **Who and how:** the supervisor runs the push, as an operator's act, through the contribution path (`squadops projects contribute`, `projects/contribution.py`), passing the token with the request as that command does today (`--token-from-gh`, the box's `gh` login). The owner reviews and merges the review request, and §24cd point 4 reads that merge.
- **When:** at the Campaign's close, or mid-Campaign when the owner asks for it.
- **After a rebase (§24cd point 2):** the push to the Campaign's review branch is forced with a lease on the ref the control log last recorded, so a branch someone else moved is refused, never overwritten. This widens `source_repository.py:79`'s "never forced" for this branch only, and the build says so.
- **Until it is built:** the branch lives in the managed clone, and nothing is pushed.

**Evidence:** §24cd point 7's reading of `sandbox/findings.py:154-179`, `projects/contribution.py:81-152` and `ports/projects/source_repository.py:79`; the token reading of `contribution.py`'s `_open_review_request`, which refuses a request with no token for the Project and names both sources.

**Who ruled.** The owner (2026-10-28), on the supervisor's recommendations. The supervisor (the Spark lane) builds both with #2619.

### 24cj. §24bv point 5 as built: a repository-backed proposal reads the product at its head, and each criterion's test is placed under the product's runners (2026-10-28, §7.2, §9.1, §10a, §24bv point 5, §24cc, §24ch; SIP-0112 H.4, H.6, H.11; #2619; the supervisor's design and ruling under the owner's delegation, for the owner)

**Why.** §24bv point 5 says what a repository-backed proposal is given and how its change request reads. Until this,
the calibration record's row 5 escalated as unbuilt (§24cc), and H.11 left point 5 two more things: where a criterion's
test file goes with no stack, and a repair or retry with no manifest to seed. Building it found four places where the
text can't be built as written, or leaves a choice:
- **Ten seams decided "is this an increment?" by the launch's manifest** (`increment_baseline`), which a
  repository-backed increment has none of. Each would read it as no increment, and its framing would design the
  product anew.
- **Where a criterion's test goes:** `scaffold.criterion_test_path` raises with no stack.
- **What scope reads on a product:** §24ch made a stack's qa test namespace the framework's. A product has no stack,
  and it has tests of its own.
- **When the input is bound:** §24cd point 1's intent binds no tree, so nothing about the head is known at the
  decision.

**What changed.**
1. **One marker: the block's `basis`** (`IncrementBasis`, `campaigns/change_request.py:89`; read by
   `increment_basis`, `increment_tree.py:156`). `increment_launch` writes `basis: campaign_branch` for a campaign whose
   accepted tree names a commit, the calibration record's or an increment's on the branch (`launch_requests.py:148`).
   A block that names none and carries a manifest reads `manifest`, so every block written before this reads as it
   did. An unknown basis is refused. The seams ask `is_increment` or the basis, and read the manifest only where the
   basis has one: the change request's framing, the seed, the frozen files, the test scope, the planning steps, the
   builder offer, the framing gate, the proposal gate's seed and the proposal's evidence.
2. **The launch** (`progress.py:1842`, `_propose_on_branch`). A repository-backed proposal launches with no manifest
   and no accepted cycle. It reads none of a sample application's manifest inputs (§24ad's answer, the seed fault,
   §24bm's late answer), and keeps rows 6, 7, 13 and 16's: the frozen criteria, the abandoned brief, what qa proposed,
   each proposal never approved. Its objective carries `objective.requirements`. This changes §24cc point 2:
   `increment_launch` now raises only for a sample application's tree that names no cycle, and for a manifest given
   to a branch's.
3. **The input is composed at the proposal's run, at the head its cycle pins** (`execution/product_proposal.py`,
   in `RunProvisioning.prepare`), as SIP-0113's evidence is. It reaches the task that authors the change request
   (`TaskType.authors_change_request`) as `product_proposal`:
   - the head's commit and tree;
   - the derived profile at the Project's pin (§24cd point 3): its languages, public surfaces and file classes, each
     runner with its criterion placement, and its disclosed gaps;
   - the previous increment's verification, or the record's inherited baseline for the first. It's read by
     `source_delivery.regression_baseline`, the one delivery compares the candidate with, with up to 20 finding keys
     per check;
   - the requirements source, read at the head (`repo:file:<path>@current` bound as `repo:file:<path>@<head>`), or
     a stored artifact;
   - a greenfield product's approved manifest (H.1), beside them.

   A read that fails raises, so the run fails and the campaign proposes again under §24bn's bound.
   - **Narrowed: the tree view is the map and the instruction files.** §24bv names "framing's `source_repository`
     view". Its appendix also tells a build task how to emit files, which a proposer doesn't. The checks are shown
     with their results instead, as the previous verification.
   - **Not shown: outcome evidence** (SIP-0113 §4.5). Nothing evaluates a head yet (§10l).
4. **The change request on a product** (`_validate_product_proposal`, `change_request.py:788`). It takes four
   additive fields. Each is stored only when it isn't its default, so every request stored before keeps its document
   and its hash:
   - `basis`;
   - `footprint`, authored as path globs, and hashed, so a footprint widened after the ruling is refused when loaded;
   - a criterion's optional `paths`, the product paths it exercises;
   - the derived `criterion_files`, hashed with the footprint (the outside review's P2, below).

   `SurfaceKind` adds `command` and `package`. The rails are:
   - a `manifest_delta` is refused (`manifest_delta_on_product`);
   - a `feature` or `fix` with no footprint is refused (`nothing_to_build`);
   - a footprint outside `allowed_scope` is refused;
   - a criterion's surface must be one the profile names: an endpoint needs an HTTP base, a page a UI base, and a
     command or package must be declared, or a subcommand or name under one;
   - a criterion's `paths` must lie in the footprint;
   - each criterion is placed, or refused (`unplaceable_criterion`);
   - the placed files are appended to the footprint;
   - the criteria, goal and retirement rails are unchanged.
5. **Placement** (`campaigns/criterion_placement.py`). The runner is the first, in the profile's order, whose
   `covers` holds every path the criterion exercises: its `paths`, or the footprint's product files.
   - **The file** goes under the runner's first root, named by its `file_pattern`, with `criterion_<id>` for the
     first `*`.
   - **A second `*` is the extension,** the one the runner's own test files take most. Tally's is
     `checks/check_criterion_<id>.py`, and a vitest frontend's `<root>/criterion_<id>.test.jsx`.
   - **Refused, named:**
     - a runner with no one-file argv, or one a `runner_not_scopable` gap names (a later covering runner may host
       it);
     - a pattern naming no single file;
     - an extension no test file gives;
     - a placed path that is a product file already.

   The placement is stored with the request, and every reader after the proposal reads it:
   `increment_criterion_files` (`increment_tree.py:327`), the plan authors, the framing gate and the evaluation's
   inputs.
6. **The scope on a product: the supervisor's ruling, under the owner's delegation of 2026-10-28 ("use your best
   judgement on all other items").** Only the criterion test files the framework places are the framework's.
   - Every other file, the product's own tests included, is the product's, and stays inside `allowed_scope`.
   - Editing an existing test needs it in scope, as editing any product file does.
   - `outside_allowed_scope` takes the placed files (`placed`), so the proposal's rails and the plan-review tier
     (§24bj) read one rule, as §24ch requires.
   - **The reading rejected:** exempting the profile's `files.test` classes. It would let a change rewrite a
     product's tests outside the owner's scope. That is the control §24ch kept for product files, and a product's
     tests are its own.
7. **The continuation carries its change request** (`increment_seed`, `increment_tree.py:233`). A repository-backed
   increment's seed is its approved change request alone: no candidate manifest and no contract. So its repair and
   its retry carry it, as `plan_artifact_refs`, and `CONTINUED_KEYS` carries `basis`. The proposal gate's seed
   (`WorkloadGate._seed_increment`) only promotes the run's artifacts. `bound_at_head` still refuses a continuation
   whose tree isn't the head.
8. **The plan authors are taught before the gate enforces it** (#686). A product's increment has no contract, and its
   indexes used to reach plan authors only in bind mode. `inject_contract_inputs` now gives them its footprint,
   criterion files, frozen files and test scope without one (`task_plan.py:949`). The framing gate holds the plan to
   the stored footprint and the placed files.
9. **Creation** (`repository_backed.creation_refusal`, called at `POST /api/v1/campaigns`, 422, naming the field):
   - a repository-backed Campaign must name `objective.requirements`;
   - its increments must seed no skeleton, by `seeds_skeleton` over the proposal profile under the policy's stack.
     That refuses `policy.stack`, or a stacked profile such as `campaign-increment`, as §24bv point 1 asks;
   - a sample application's Campaign may not name a requirements source;
   - a requirements source at a fixed revision, or in another family, is refused, since an increment that edits the
     PRD would then never be shown it;
   - a Project the registry doesn't hold is left to the start (§24cc).

**Not built here, and where it is:**
- **§24cd point 6's evaluator, and the `qa.evaluate_increment` drop** (#2619). Until point 6 lands, a repository-backed
  increment's implementation still plans `qa.evaluate_increment`, with its placed criterion files as inputs.
- **The plan-review tier on a product.** It reads the placed files, but escalates on condition 3, since a product has
  no manifest to read questions from. So a product's increment under `plan_gate: tier` is ruled by the supervisor at
  its plan gate.
- **Point 1's `calibration_profile: inherited_baseline` rule.** No such profile exists, and a repository-backed start
  writes its record whatever the profile names.
- **Point 4's rebase and the review-request push** are separate builds.

**Evidence.**
- **The wiring, entered at the live callers:**
  - `test_campaign_calibration_record.py`: `POST /api/v1/campaigns/{id}/start` on Tally's real clone. Row 5 launches,
    through the drain and `prepare_cycle`, a cycle pinned at the record's commit. Its block names `campaign_branch`
    and the record's tree, carries the requirements source, and has no manifest or accepted cycle.
  - `test_product_proposal.py`: `RunProvisioning.prepare` on Tally's real clone. At the record's commit, the proposal
    task alone is given the recorded profile's placement, its two disclosed gaps, the inherited baseline's checks and
    `README.md` read at the head. On a head committed past the record, with its verification, it is given that head,
    that verification and the README as the head has it. A greenfield product is given its approved manifest. A
    requirements file the head lacks, an artifact not stored, and no profile at the pin each fail the run, named.
  - `test_strategy_propose_product_increment.py`: `handle()` with the real assets. The prompt shows the head, surfaces,
    placement, gaps, checks, requirements and tree, and not the manifest prompt. The stored request carries its basis,
    footprint and placed file, and a manifest delta is returned for revision.
  - `test_product_increment_seams.py`: `CampaignProgress._bound_seeds` (the continuation carries the change request
    once approved), `generate_task_plan` (the indexes without a contract), the framing gate (a file outside the
    footprint and an unplanned criterion refused), and `with_proposal_evidence`.
  - `test_campaign_repository_creation.py`: `POST /api/v1/campaigns`, each refusal and the accepted creation.
- **The rails and the placement:** `test_product_change_request.py` and `test_criterion_placement.py`. These cover
  Tally's recorded profile, an invented pytest-and-vitest product, each refusal, the stored hash holding the authored
  footprint, and §24cj's scope reading at the rails and at the tier (`test_plan_review_tier.py`).
- **Eighteen mutants, each caught** (eight more for the review, below):
  - the basis read from the manifest's presence;
  - the seed needing a manifest;
  - placed files left out of the footprint;
  - the footprint unhashed;
  - the product's tests exempt from scope;
  - the tier reading placed files against scope;
  - the input never composed;
  - the requirements read at the Project's baseline;
  - any command accepted;
  - a guessed extension;
  - an unscopable runner hosting;
  - creation not reading the Project;
  - the launch with no basis;
  - the continuation dropping it;
  - no indexes without a contract;
  - the framing gate reading no footprint;
  - the evidence step refusing a branch increment;
  - the product sent the manifest's template.

**The outside review (SIP-0112 H.12) on PR #2771: request changes, two findings, both fixed in that PR.**
- **P1: two criteria could share one test file.** A test file is named by its criterion's id kept to letters, digits
  and `_`, so `T-1` and `T_1` name one file. Placement checked a placed path against the product's files only, never
  against the other criteria's. Now:
  - the rule is single-sourced (`scaffold.criterion_module_name`);
  - on both bases, the rails refuse an id named twice (`duplicate_criterion`), and ids whose files would be one file,
    a frozen criterion's included (`criterion_file_collision`);
  - on a product, the placed paths are checked unique across the request whatever placed them.

  This also fixes the same collision on a sample application, which predates point 5.
- **P2: the stored placement wasn't integrity-checked.** `criterion_files` was left out of the hash, and the loader
  didn't revalidate it.
  - **Chosen: the placement is bound into the hash, and checked whole on every load** (`placement_inconsistency`).
    Each criterion is placed exactly once, at a path of its own, in the footprint, and named for it.
  - **Why this, not revalidation against the pinned profile:** every reader after the ruling is pure and holds no
    profile: the framing, the plan authors, the framing gate and the evaluation's inputs. And the placement is part
    of what the supervisor approves, the file the build writes and the evaluation freezes.
  - **What it does on a failure:** a placement changed after the ruling fails the hash, and an inconsistent one is
    refused by name, at `load_stored_change_request`. So it fails closed in the framing's provisioning, and the
    framing gate now refuses a branch plan whose request can't be read (`_unreadable_branch_request`) rather than
    skip its rules.
  - **What it doesn't cover:** the hash is no signature. A writer that also recomputes the hash isn't caught, as for
    any field of the request. A placement edited in the vault, though, is caught.
- **Evidence:** `test_product_change_request.py` covers:
  - two ids naming one file, one id twice, and an id naming a frozen criterion's file, on both bases;
  - a malformed placement putting two criteria at one path;
  - a stored placement renamed, moved, dropped, doubled, left out of the footprint, or placed for another criterion;
  - one moved where only the hash can tell;
  - a sample application's request carrying a placement.

  `test_product_increment_seams.py` covers a tampered placement refused at `approved_change_request` and at the
  framing gate.
- **Eight more mutants, each caught:** no identity check; a duplicate let through; a frozen criterion's file not read;
  placed paths not checked unique; the placement unhashed; the placement never checked; a file not held to its
  criterion's name; the gate failing open.

**Who ruled.** The owner placed point 5 in 2.5 (2026-10-21), ruled D10's requirements source (2026-10-24), and moved
the MacBook lane's point 5 to the Spark lane (2026-10-28). The supervisor (the Spark lane) designed and built it. Item
6's scope reading is the supervisor's judgement under the owner's delegation of 2026-10-28. Items 3 and 4 change the
change request's schema, a shared contract, so they take the outside review SIP-0112 H.12 provides before the merge.

### 24cl. §24cd point 6 as built: a repository-backed increment is judged at its delivery, on the product's runner in the sandbox, in place of `qa.evaluate_increment` (2026-10-28, §8.1–§8.4, §24bv point 3, §24cd points 5 and 6, §24ci (a), §24cj; SIP-0112 H.6, H.10, H.11; #2619; the supervisor's build, for the owner)

**Why.** §24cd point 6 moves a repository-backed increment's acceptance into the sandbox, runtime-side, because the
product's toolchain exists only there. It builds each overlay as a revision of the tree, and drops
`qa.evaluate_increment` for such an increment. §24bv point 3 says what the bundle and the overlays are on a product. Until
this, a product's increment still planned `qa.evaluate_increment` (§24cj, "Not built here"). That task runs in the qa
role's container, which holds no product toolchain. And `discrimination_on_runner` and `held_on_runner` (#2764) had no
live caller. Each item below says what the build settled where the text leaves a choice. One part
isn't built: route rendering on a product (item 6), a release-level gap. Item 13 is the outside review's first
finding (SIP-0112 H.12), fixed here.

**What was built, and each choice the text left.**
1. **When: at delivery, after the capture** (`DispatchedFlowExecutor._deliver_source_change`, which calls
   `execution.product_acceptance.evaluate_product_increment`). Point 6 says where the evaluation runs, not when.
   Delivery is where both trees are in hand: the head the run was built on and the squad's changes to it. A candidate
   the product's checks reject fails its run first, as before, and isn't judged. That matches a sample application's
   run that fails before its last task. A framing or proposal run delivers nothing, so it's never judged.
2. **One evaluator for each increment** (rule 3: a property, not a type compare). `IncrementBasis.evaluated_at_delivery`
   holds for `campaign_branch`. The plan asks it and plans no `qa.evaluate_increment` (`task_plan._increment_evaluation`),
   and delivery asks the same property to judge. So a sample application's increment keeps its task, and a standalone
   source-backed cycle, which is no increment, is never judged.
3. **The inputs are the ones the plan hands `qa.evaluate_increment`** (`increment_evaluation_inputs`). They come from
   the same approved change request: the increment's id, each new criterion's placed file (§24cj item 5), the frozen
   criteria its launch pinned with their stored bundles, and what it retires or replaces. The profile is read at the
   Project's pin (§24cd point 3). The configuration is read at the revision the cycle pinned.
4. **Each overlay is a revision of its tree, in a workspace of its own** (`runner_acceptance.RunnerAcceptance`). The
   tree is seeded as the head's checkout (`git_checkout`), with the squad's changes patched on for the candidate
   (`agent_patch`). The overlay is then cut on it (`acceptance_assembly`). So an overlay's parent revision is the tree it
   overlays.
   - The candidate's revision must be the one delivery verified, or nothing is judged (`CandidateNotDelivered`).
   - **Nothing runs on a revision other than its overlay** (item 13). Each revision cut on the way (the checkout, the
     candidate, the overlay) must be the one its content names (`compute_revision_id`, with the executable bits a patch
     keeps). A seed or a patch that cut another, or a patch that wasn't applied, stops the run before its command:
     the run is unexecuted, with why. A command that reports another revision than the overlay's is no result either.
   - **The choice:** one workspace per overlay, not one per tree with overlays patched in turn. A store's patch needs
     the live tree to match its base, and a deleted file loses its executable bit, so a chain of overlays would make
     each revision depend on the order of the ones before it.
   - Each workspace is released before it is seeded (an earlier attempt's, after a restart) and after its run.
5. **The product's test files and a criterion's bundle** (`ProductTestSurface`, `freeze_product_bundle`).
   - **A test file** is one contract 8's `files.test` or `files.test_support` classes, matched on the whole path, or a
     criterion file the framework placed. Every other tracked file is the product's.
   - **The overlays are `evaluator_trees`' own** (§7.4). The baseline-evaluator overlay is the head's product files plus
     the bundle. The candidate-verifier overlay is the candidate's product files plus the bundle. Neither holds the
     tree's own test files, so a candidate's conftest can't change how a frozen criterion runs.
   - **A bundle** is the placed test file and the test files it imports, as on a stack, plus the support files of the
     runner that holds it (§24bv point 3).
   - **The choice: a Python test file's package markers.** The `__init__.py` of each directory above it, where the tree
     has one and it is a test file, goes in the bundle. §8.1 freezes "the fixtures and helpers it requires, resolved from
     its imports". Without its markers, a test under a package directory imports as a top-level module, and the product
     may not be on its path.
   - **Its invocation** is the runner's one-file argv, with the file named in it as H.6's `{path}` or `{name}`.
6. **Route rendering on a product isn't built: a release-level gap** (the outside review's second finding, SIP-0112
   H.12). §24bv point 3 has routes rendered where the profile names client routes: a greenfield product made from a
   blueprint. Nothing here can render them, since the sample stacks' renderer stands the app up in the qa container
   from the stack's own probe profile. So each route the profile names is `blocked_unverified`, never passed by
   omission (SIP-0096), and the increment is blocked with it. A profile that names none has no routes, and they are not
   applicable.
   - **The cost:** every increment on a blueprint product blocks, so 2.5 can't claim a Campaign on one is accepted
     until the renderer exists. `z_shelfnote` is such a product: its profile carries its manifest's routes (H.7).
   - **Where it is:** the supervisor schedules the renderer separately, with #2414's remainder (the declared start at
     the cycle-end hook), since both stand the product up from contract 7's start declaration. It is not built in this
     PR, and its row stays placed on #2619.
7. **Which runner, which argv, which reader** (H.6's ownership rule).
   - A new criterion's file is run by the runner that holds it (`DerivedProfile.runner_for`), and read by that runner's
     test-id reader.
   - A frozen bundle runs by its own frozen invocation (§8.1: "by the bundle's frozen invocation"), even after a
     reconciliation changes the runner's argv. It is read by the reader of the runner that holds its file now. Where
     no runner holds it, or the runner has no reader, it is read by its exit status, and item 13 says what that can
     show.
   - **A runner with no test-id reader isn't run for a new criterion** (§24ci (a)). Its criterion is unread and blocks,
     and its bundle is still frozen.
   - Each argv runs as the configuration's checks run, in their working directory, after their install and build
     steps (H.6).
8. **The record is the `increment_evaluation` document a sample application's evaluation writes**
   (`acceptance_run.evaluation_document`). It is stored on the implementation run, so each reader takes it unchanged:
   - the completion's verdict, and §24bq's already-met reading (`progress.increment_verdict`, `already_met`,
     `rejected_only_as_already_met`);
   - the promotion, which freezes `new_bundles` (`_freeze_bundles`), and the next launch's pin;
   - a successor's brief (§24br, `prior_cycle`);
   - the reference report (`reference.py`, `scripts/dev/reference_report.py`).

   Two keys are added for this evaluator alone, and no reader reads them: `evaluated_on: product_runner`, and `runs`.
   `runs` holds each run's criterion, side, overlay identity, sandbox revision, argv, reader, exit status and reading:
   §8.4's keys.
9. **A difference this leaves, named.** A criterion test that can't be collected on the baseline makes pytest exit 2.
   An example is a module-level import of a module only the candidate has. pytest's reader can't read exit 2, so
   `discrimination_on_runner` reads the criterion as not run, and it blocks. A sample stack reads the same file as
   `only_setup_failures`, and the criterion is unmet with its reason. Neither counts it as discriminating, which is
   §8.2's rule. But a blocked increment is told only "not run", where the sample stack's repair is told why. Changing
   it is a change to `discrimination_on_runner`, #2764's decision, and this doesn't make it. It is the supervisor's to
   rule.
10. **The rebase's frozen bundles** (§24cd point 5; #2770 records them as `frozen_criteria_unrun` "until point 6").
    `runner_acceptance.frozen_on_runner` is the frozen half alone, and its signature is held stable for the call. It
    runs on any tree, with no candidate changes. The supervisor wires it after #2770 and #2774 merge. The call needs:
    - `runs`: a `RunnerAcceptance` with the runtime's sandbox, the derived profile at the reconciled pin, a
      `RunnerSetup.of(configuration.commands)` for the reconciled revision, a workspace prefix of the rebase's own, and
      no `verified_candidate_revision`, since the tree carries no changes;
    - `subject_id`: the rebase's key, which each result is keyed by;
    - `tree`: a `SandboxTree` of the rebased head from the managed clone (`repository.tree_at`: its files and
      executable bits);
    - `frozen`: the campaign's frozen pins (`frozen_criteria(log)`), their bundles read as a launch's are
      (`frozen_bundle_contents`), rebuilt by `frozen_criteria_from`;
    - `surface`: `ProductTestSurface.of(profile, <the pins' test paths>)`.

    A result that isn't `held` refuses the rebase as `REBASED_HEAD_REGRESSED`, a blocked one included, since item 13's
    blocked result is a head nothing showed holds. It isn't wired here.
11. **What refuses, and fails the run** (`ProductAcceptanceRefused`, `CandidateNotDelivered`): no derived profile at
    the pin, no sandbox, no approved change request, or a candidate other than the verified one. A run that can't be
    judged fails, as a `qa.evaluate_increment` that can't be judged fails its task. Nothing is accepted unjudged.
12. **The cost.** Each overlay seeds the whole tree and runs the configuration's install and build steps before its
    one file: two runs for each new criterion with a reader, and one for each frozen criterion. A product whose install
    is slow pays it on every run.
13. **A frozen criterion holds only on evidence that its tests ran and passed** (the outside review's first finding,
    SIP-0112 H.12; SIP-0096: "only executed-and-passed credits"). Before this, a run that failed nothing could read
    `held` with no test run:
    - a runner with no test-id reader read exit 0 as held, and unittest's discovery exits 0 when every test was skipped;
    - a reader's reading that counted no failure read as held when its tests were skipped, since a skip is collected;
    - and a run could be made on the unpatched tree when an overlay's patch wasn't applied (item 4).

    **What changed** (`acceptance.held_on_runner` and `acceptance.discrimination_on_runner`, #2764's, changed here):
    - **With no test-id reader,** exit 0 is `blocked_unverified`, never held. A non-zero exit is still broken: the
      frozen test ran against the candidate's code and didn't pass. That is §24ci (a)'s rule for discrimination,
      applied to holding. It narrows H.6's `per_test_reading` ("each criterion is read by its own test file's result")
      for a frozen criterion: a whole file's pass is no evidence that a test ran. One cost: unittest exits 5 when a
      file holds no test, and that reads broken, not blocked. Neither reads held.
    - **With one,** a frozen criterion holds only when every test it collected passed. A test that was skipped, or
      expected to fail, blocks it, naming how many.
    - **On discrimination's candidate side,** a run that skipped a test reads as not run, since the skipped test may
      be the one that failed on the baseline.
    - **The evidence:** each reading of a test runner now carries `passed`, the tests that ran and passed by the
      runner's own summary (`squadops.sandbox.findings`, pytest's counts line and vitest's `Tests` line). Like a class
      (H.10), it changes no key and no readable rule, so no reader's version. A reading stored before it has none, and
      reads back unchanged.
    - **What a reading with no pass count reads:** not run, and blocked. So the sandbox service is rebuilt with the
      runtime API, or every criterion blocks until it is.

**Not built here, and where it is:**
- route rendering on a product (item 6): a release-level gap, which the supervisor schedules with #2414's remainder,
  on #2619;
- the rebase's call (item 10): the supervisor wires it after #2770 and #2774 merge;
- §24ci (b)'s review-request push: #2772.

**Evidence.**
- **The wiring, entered at the live callers:**
  - `tests/unit/campaigns/test_product_runner_acceptance_wiring.py` enters at the executor's end of plan
    (`_execute_sequential`, which delivers). It runs over the shared fixture's Tally, with a real managed clone and a
    real sandbox service, whose one stand-in runs X-3a's disposable copy as local processes:
    - a branch increment is delivered, captured and judged, and its document is stored on its run. Tally's unittest
      names no test, so its new criterion blocks, and its frozen criterion's exit 0 blocks too (item 13);
    - a change that keeps every check of Tally's but breaks the frozen criterion is rejected;
    - no profile at the pin fails the run;
    - a standalone source-backed cycle is never judged;
    - `generate_task_plan` plans `qa.evaluate_increment` for a sample application's increment and not for a branch's;
    - `CampaignProgress.cycle_ended` promotes onto the campaign branch from a product document, freezing its bundle at
      the placed file with an address the next pin holds.
  - `tests/unit/campaigns/test_runner_acceptance_sandbox.py` runs real pytest in the real sandbox service, on an
    invented product. Its backend reads each run's whole output with the declared reader. It covers:
    - discrimination, and each reason it isn't met;
    - item 9's collection error;
    - no reader;
    - nothing to run;
    - a frozen bundle kept, undone, skipped by a candidate's conftest, or its file rewritten;
    - the frozen invocation after the profile changes;
    - the rebase's half;
    - the verified-candidate refusal;
    - a sandbox that runs nothing;
    - routes;
    - the placeholders and the package markers;
    - a vitest runner under a package, read from recorded vitest 2.1.9 output, since this box has no vitest;
    - item 13, each on a real run: a skipped verifier file, an expected failure, zero tests collected, a no-reader
      runner that skipped every test, and a criterion its candidate skips;
    - item 4's refusals: an overlay patch not applied, a patch that cut another revision, and a command that passed
      on another revision.
  - `tests/unit/campaigns/test_runner_acceptance.py` holds `held_on_runner`'s table, and
    `tests/unit/sandbox/test_findings_readers.py` the pass count from real pytest and vitest output.
- **Mutants, after the review:** twenty-seven, the first build's seventeen again and ten on item 13's and item 4's seams, and all twenty-seven caught. The ten: a no-reader exit 0 read as held; a skipped frozen test read as held; a reading with no pass count read as all passed; a candidate's skip read as a pass; the reader counting a skip as passed; the pass count never stored; a seed, a patch, or an unapplied patch of another revision run on; and a run on another revision credited. The seed's mutant survived the first pass, since a patch after it caught the stray file, and a tree that is already its own overlay now catches it. The first build's seventeen were:
  - the overlay keeping the tree's test files;
  - the baseline run on the candidate;
  - a no-reader runner run and read whole;
  - a frozen bundle run by the current argv;
  - no package markers;
  - no support files;
  - the verified-candidate check dropped;
  - a rewritten frozen file not blocked;
  - routes never judged;
  - a frozen bundle read whole;
  - the product's tests read as product files;
  - the plan keeping, or dropping everywhere, `qa.evaluate_increment`;
  - delivery never judging, or judging every source-backed cycle;
  - the document stored off its run;
  - the pinned frozen criteria never read.
- **The loaded checks** `2619-product-acceptance`, `2774-review` (the runtime) and `2774-review-sandbox` (the
  sandbox service) (`scripts/dev/loaded_checks.yaml`), each run on the source.

**Who ruled.** The supervisor (the Spark lane) built §24cd point 6 under the owner's direction of 2026-10-21 and the
2.5 grants, with the owner's delegation of 2026-10-28 (§24cj item 6). Items 1 to 12 are the supervisor's choices, for
the owner's review. Item 6 leaves the routes unbuilt and the increments blocked. Item 9 names a difference for the
supervisor to rule. Item 8 adds two keys to the `increment_evaluation` document, which other readers depend on, so it
takes the outside review SIP-0112 H.12 provides before the merge. That review (the outside reviewer's, relayed by
the owner, 2026-10-28) requested changes. Its two findings are items 13 and 6: item 13 is fixed here, and item 6 is
named as the release-level gap it called it. Item 13 also changes #2764's `held_on_runner` and
`discrimination_on_runner`, and adds `passed` to H.5's readings, additively.

### 24cm. §24bv point 4 as built: the base is a commit and a revision, the reconciled commit needs no verification, and the frozen bundles wait on point 6 (2026-10-28, §8.1, §12b, §17, §24bv point 4, §24cd points 2–5; #2619; the supervisor's build, for the owner, with the MacBook lane's G4 on the port)

**What was built.** §24cd points 2–5, before each launch (`squadops.campaigns.branch_rebase`, called by the launcher as `before_launch`):
- the Project's own gates run at its pin first (`reconciled_at_pin`: READY, H.2's drift, the inherited baseline, H.8's blocking gap), so the launcher never reconciles;
- the branch's commits are replayed onto the pin in the managed clone (`SourceRepositoryPort.rebase`);
- the rebased head is verified by the product's checks against upstream's inherited baseline;
- one `BRANCH_REBASED` row moves the accepted tree and supersedes a pending repair or retry;
- the ref follows by compare-and-swap, and the existing startup and sweep re-sync moves a ref a stop left behind.

**Where the build differs from §24bv and §24cd's text:**
1. **The base is a commit and a Development Configuration revision.** §24bv compares the branch's base with upstream's commit. But the head's verification is read only at the revision it ran at (`previous_verification_baseline` refuses another, FR-20). So a Project re-configured at the same commit would refuse every later increment. The launcher rebases when either differs. A revision-only rebase moves no commit and re-verifies the head at the new revision.
2. **A rebased head that is the reconciled commit itself runs no verification.** That happens after the owner's merge (§24cd point 4), or when the Project reconciles before any increment is accepted. That commit's regression baseline is the inherited one, captured at reconciliation. The row names `verification: inherited_baseline` and no `verification_ref`. `require_campaign_head` already accepts a head at the Project's baseline commit with none. This answers the second half of #2761's G4 note 2.
3. **Where the rebase's verification is kept.** It is a `source-verification/v1` document in the vault beside the Project. Its `cycle_id` and `run_id` are null, since no run made it, and its `rebase` block names the campaign, the base and head before, and the commits replayed and dropped. `head()` reads `verification_ref` from a `BRANCH_REBASED` row as it reads a PROMOTE row's, so the next increment's delivery compares with it (§24bv point 3). This answers the first half of the G4 note.
4. **An unverified rebased head escalates as `REBASED_HEAD_REGRESSED` too.** That is a head no check executed and passed on. It can't be a regression baseline, which must be accepted. The refusal gives the verification's own summary, which says which it was, and its vault id.
5. **How the refusals escalate.** Each is the launch's refusal (`LAUNCH_REFUSED`, the campaign escalated with the intent pending, #1971), named by its code: `CAMPAIGN_BRANCH_CONFLICT` with the commit and the paths, or `REBASED_HEAD_REGRESSED`. Drift and a blocking gap use the cycle-create path's own gates, so their codes are that path's (`STALE_SOURCE_PRECONDITION`, `PROJECT_STATE_CONFLICT`). Nothing is rebased, and nothing superseded, before a refusal.
6. **The supersession's state and its proposal.**
   - The row moves the campaign from `repairing` or `retrying` to `at_proposal`, an edge §17 didn't draw. It is added to the lifecycle.
   - When row 6's proposal can't be built, the row escalates the campaign instead, naming why (`unbuilt`), as a decision does. Since #2771 built §24bv point 5, that is a proposal whose inputs can't be read (a profile, a manifest, a request it refuses), named by its reason.
   - The supersession reads the intent under the campaign's lock. One launched or superseded meanwhile refuses the rebase as `stale_state`.
7. **No limit is checked at the rebase.** The fresh proposal replaces the launch the repair would have been, one for one. The next decision counts its cycle, its tokens and the elapsed time. Tests hold that five rebases in a row still reach `max_cycles`, the budget and the elapsed time, and count toward no `max_unaccepted_increments` (D10).
8. **The mechanism.**
   - Each commit is merged onto what was replayed before it, with its parent as the base (`git merge-tree --write-tree`). No working tree is touched, and only objects are written.
   - A result with no change is dropped, as a rebase drops a change upstream holds.
   - Each new commit keeps the original's author, message and committer date. So the same rebase writes the same commits, and a replay after a restart is a replay.
   - The port's new `rebase` is a change to SIP-0112's source-repository port, for the MacBook lane's G4.
9. **SIP-0109's migration range is full.** `1600–1699` is used to `1699`. Its later migrations take `2000–2099`, starting with `2000_campaign_branch_rebased.sql`.
10. **The clone's other refusals are sorted by who can get past them** (the second review, SIP-0112 H.12, P2 on #2770). A conflict wasn't the only refusal the clone's rebase can make. Each refusal now names its reason, and the launcher sorts on it (`NEEDS_THE_OPERATOR`):
    - **the operator's, escalated with the intent pending:**
      - `CAMPAIGN_BRANCH_UNREBASEABLE` for a merge on the branch (`not_linear`, refused before anything is replayed), a base not in its history, or an id that isn't a commit;
      - `CAMPAIGN_BRANCH_UNAVAILABLE` for a clone that is gone (`not_cloned`) or a commit it lacks (`commit_missing`);
      - `REBASED_HEAD_UNVERIFIABLE` for a runtime with no sandbox to check the head in;
    - **an infrastructure fault:** anything else (a timeout, git failing to run). Nothing is written, the campaign stays where it was with its intent pending, and the launch is repeated. The sweep now drains on its interval (`main._sweep_campaigns`). Before, a launch that faulted waited for the next row that wrote an intent, which a waiting campaign never writes.
11. **The frozen criteria run at every rebase, on the product's runner, and fail closed** (§24cd point 5's second half; the third review, SIP-0112 H.12, P1 on #2770).
    - **The call.** `BranchRebase` takes `frozen_on_runner`, given a `FrozenAtRebase`: the rebase's own key as its subject, the Campaign, the Project and its pin, the rebased head's tree with its executable bits, and the frozen pins. The runtime builds it (`main._branch_rebase`) with `ProductRunnerFrozen`, which calls #2774's `runner_acceptance.frozen_on_runner` exactly as §24cl item 10 states:
      - a `RunnerAcceptance` over the runtime's sandbox, with the derived profile at the reconciled pin, `RunnerSetup.of` the reconciled revision's commands, a workspace prefix of the rebase's own, and no verified candidate revision;
      - the rebase key as the subject;
      - the rebased head from the managed clone;
      - the pins' bundles, read as a launch reads them (`frozen_bundle_contents`) and rebuilt by `frozen_criteria_from`;
      - the surface, `ProductTestSurface.of` the profile and the pins' test paths.
    - **The readings.** It runs on every rebase, the reconciled commit's included. A criterion whose reading isn't `held`, a blocked one included, or that the runner didn't read, refuses the rebase as `REBASED_HEAD_REGRESSED`, naming each with its reading. The row names the criteria that held (`frozen_criteria_held`), and the digest says so.
    - **Fail closed.** Frozen criteria with no runner, no sandbox to run them in, or no derived profile at the pin refuse the rebase as `REBASED_HEAD_UNVERIFIABLE`, naming every criterion left unread. A rebase never passes with its frozen criteria unread.
    - **This replaces** the round-one build's "frozen criteria named unrun, and the rebase passes" (`frozen_criteria_unrun`). That build was the round-three review's P1.

**Evidence.**
- **The wiring.** The tests enter at `CampaignLaunchService.drain()` with `before_launch` wired as `main` wires it (`tests/unit/campaigns/test_branch_rebase.py`). They run over the shared fixture's Tally, with a real managed clone, a real sandbox service and a real delivery and baseline capture, and upstream moves by a commit to the fixture's own repository:
  - a README change upstream rebases the branch, and the increment then launched is pinned at the rebased head. A real delivery on it compares with the rebase's verification;
  - a pending repair is superseded, and the fresh proposal launches in the same drain. With the real proposal path, it escalates naming §24bv point 5;
  - a conflicting change, and an upstream check that the rebased head fails, each escalate with the intent pending, and nothing moves;
  - no baseline at the pin, drift after reconciliation, and a blocking gap each refuse before any rebase;
  - the owner's merge, and a reconciliation before any acceptance, rebase to the reconciled commit with no verification;
  - a revision-only reconciliation re-verifies the head where it stands;
  - upstream moving twice rebases from where the first rebase left the branch;
  - a follow that failed is moved at `main._resume_campaigns`;
  - a merge on the branch, a base not in its history, a commit the clone lacks and a lost clone each escalate by name with the intent pending, and a timeout writes nothing and is repeated by the sweep's drain;
  - the frozen criteria, run for real with `ProductRunnerFrozen`: one held under a pytest runner that reads tests by id, one broken under Tally's unittest by upstream's README change, and one whose bundle was never stored (blocked). Only the held one passes, and with it alone the row names it held;
  - fail closed: no runner, no profile at the pin and no sandbox each refuse as unverifiable, naming the criterion left unread;
  - the runtime's own wiring, `main._branch_rebase`, drained with a criterion upstream breaks;
  - what the runner is given (the rebase key, the Campaign, the pin, the rebased head), with a stub in its place.
- **The clone's rebase** is tested against real repositories (`tests/unit/tools/test_git_source.py`): replay keeping each change and its author, determinism, a merge and a squash rebasing to upstream, a conflict named by commit and path, and the edges.
- **The Postgres registry** holds the supersession and the new CHECK values in one transaction (`tests/integration/cycles/test_postgres_campaign_registry_integration.py`), run by CI's integration job.
- **Mutations:** twenty, one on each seam; all twenty caught. `branch_base` ignoring a rebase survived the first run, since the rebase's idempotency key masked it, and a test of upstream moving twice now catches it. The second review's fixes added ten more, all caught, on the refusal table, the sweep's drain, the linearity check, the missing-commit check and the frozen seam. The third review's fix added eight more. Seven were caught: failing open with no runner or an unrunnable one, a blocked or unread reading accepted, the base's tree run in place of the rebased head's, the bundles never read from the vault, and the runtime wiring no runner. One survived, the surface leaving the pins' test paths out. It is equivalent here: the bundle's own files win at their paths in the overlay, and a single-file invocation collects no other test file.

**Who ruled.** The supervisor (the Spark lane), building §24cd points 2–5 under the owner's direction of 2026-10-21 and the 2.5 grants. Items 1, 2, 4 to 7, 10 and 11 are the supervisor's calls, for the owner's review. Item 10 answers the outside second review's P2, and item 11 its third review's P1 (SIP-0112 H.12). Item 8's port change is for the MacBook lane's G4.

### 24cn. §24ci (b) as built: the supervisor's push, leased on the last push, with its own token and its own route (2026-10-28, §13, §24bv point 2, §24ci (b), §24cm; #2619; the supervisor's build, for the owner, with the MacBook lane's G4 on the port)

**What was built.** §24ci (b)'s rule, as an operator's act that only the supervisor or the owner can make:
- `squadops campaigns push-review <campaign> --token-from-gh` calls `POST /api/v1/campaigns/{id}/review-pushes`, which takes `campaigns:manage`;
- the push pushes the campaign branch's head to the product as `squadops/<campaign>`, through the contribution path (`squadops.projects.contribution.push_campaign_review`);
- the first push opens the review request against the Project's base branch. Later pushes move the branch that request follows;
- each push is a `review_pushed` row, a record accepted on a completed Campaign: the branch, the commit, the lease, whether it rewrote the branch, and the request's address.

**Where the build differs from §24ci (b)'s text:**
1. **Its own command and route, on the contribution path's code.** §24ci (b) names `squadops projects contribute`. That command contributes one run's capture and records it in the Project's contributions. A Campaign's push is a different act, of a branch, recorded in the Campaign's control log. So it has its own command and route, beside the Campaign's other operator acts (the `/api/v1` resource lane, `docs/architecture/api-route-lanes.md`). It shares the contribution path's code: `_review_target`'s checks (a token, a forge, a base that is a branch) and the same forge call. It writes no Project contribution row.
2. **Every push after the first is leased, not only a rebase's.** The lease is the commit the last `review_pushed` row recorded. A push that only adds increments fast-forwards under it. A push after a rebase rewrites under it. Either way, a branch someone else moved is refused (`409 REVIEW_BRANCH_MOVED`), never overwritten. `forced` records whether the push rewrote: the lease isn't an ancestor of the head.
3. **The first push is never forced.** With no recorded push there is no lease, so a branch the product already holds with other history is refused.
4. **The token comes with the request, and only with it.** A run's contribution falls back to a token the deploy names (`projects.review_request_tokens`). A Campaign's push has no such fallback, since §24ci (b) says nothing is stored for it. The request's `token` is required, and the CLI refuses without `--token-from-gh`. It is used in memory for the push and the forge call, never written to a row, a response or a log.
5. **What it refuses before anything leaves** (`409 REVIEW_PUSH_REFUSED`):
   - a sample application's Campaign;
   - a Project that doesn't contribute by `review_request`;
   - a branch at its base, which holds nothing upstream lacks;
   - a branch whose ref is behind its row. The startup and sweep re-sync moves the ref (§24cd point 2), and the push is retried after.
6. **A retry is a replay.** A request whose idempotency key is recorded is answered with that push, even after the head has moved. A request for the head last pushed is answered with that push, and nothing is pushed. A push whose row never committed is pushed again, which the product reads as up to date, and then recorded.
   - **A crash after the forge opened the request** (the second review, SIP-0112 H.12, P1 on #2772): the retry finds no push recorded, so it calls the forge again. The port returns an open request of the same head against the same base, in the same repository, rather than opening another (`ReviewRequestPort.open_review_request`). So the retry recovers the request, and its row records the recovered address. GitHub's adapter looks it up by `owner:head`, `base` and `state=open`, and a test holds the lookup to those three.
   - **Retries that arrive together** are serialized per Campaign in the runtime process, and each reads the control log inside the lock. The second is answered with the first's row, with no push and no forge call. A second runtime process would need the lock in the registry. The runtime API runs as one.
   - **What stays the owner's:** a crash after the push, followed by a rebase before the retry, leaves the product's branch at a commit no row names. The retry's lease (none, or an older commit) is refused, and the branch is never overwritten. The owner reads the branch and decides.
7. **The port's widening is its own method.** `SourceRepositoryPort.push_campaign_branch` pushes only `refs/squadops/campaign/<campaign>` to `refs/heads/squadops/<campaign>`, and refuses any other branch or campaign id (`ref_refused`). `push_capture` stays never forced, and its documentation names the one exception. This is a change to SIP-0112's source-repository port, for the MacBook lane's G4.

**Not built, by the ruling:** an automatic push, and a token stored in the deploy for it.

**Evidence.**
- **The wiring:** the tests enter at the route (`tests/unit/api/test_campaign_review_push.py`), over `test_branch_rebase`'s world: a real managed clone, real deliveries, a real rebase, and the fixture's own repository as the product:
  - the first push opens the request, and the push after a rebase is forced under the first's lease;
  - three pushes across two rebases are each leased on the one before;
  - a branch someone else moved is refused and left as they left it;
  - a retried key is answered with its own push, after the head moved;
  - each refusal is made with nothing pushed or opened;
  - a completed Campaign is pushed at its close;
  - the invented token is in no row, response or log.
- **The clone's push** is tested against a real repository (`tests/unit/tools/test_git_source.py`): the lease rewriting, the retry that is up to date, a moved branch refused, a first push not forced, only a Campaign's own branch, and the token in the environment alone.
- **The CLI** sends the caller's own token, prints none, and sends nothing without `--token-from-gh` (`tests/unit/cli/test_commands_campaigns.py`).
- **The Postgres registry** records `review_pushed` on a completed Campaign (migration `2001`), run by CI's integration job.
- **Mutations:** thirteen, all caught. Two survived the first run: the lease taken from the first push, and a retried key pushing again. Each has a test now. The second review's fixes added five more, all caught, on the lock, the log read inside it, and the forge's recovery. One (the recorded address ignored, so every push asks the forge) survived the first run, and the wiring test now holds the forge to one call.
- **The second review's fault injection:** the registry fails on the push's row after the forge opened the request, and the retry, by the same key or a new one, recovers the request and records it, with one request opened. Two retries at once, by one key or two, make one push and one forge call (`tests/unit/api/test_campaign_review_push.py`).

**Who ruled.** The owner ruled the push (§24ci (b), 2026-10-28). The supervisor (the Spark lane) built it. Items 1 to 6 are the supervisor's calls, for the owner's review. Item 6's recovery answers the outside second review's P1 (SIP-0112 H.12). Item 7's port change is for the MacBook lane's G4.
### 24co. Route rendering on a product, as built: the profile's client routes are rendered on the candidate, started in the sandbox from the product's declared start (2026-10-28, §8.3, §8.4, §24bv point 3, §24cl items 6 and 8; SIP-0112 contract 7, H.7; SIP-0102 §11e, §11k; SIP-0113 §4.1; #2619; the supervisor's build, for the owner)

**Why.** §24cl item 6 left each route a blueprint product's profile names `blocked_unverified`, and the outside
review called that a release-level gap: every increment on `z_shelfnote` blocks. §24cl item 6 scheduled the renderer
with #2414's remainder, since both stand the product up from contract 7's start. This builds the renderer. Each item
says what the build settled where the text leaves a choice, and the rule each reading comes from.

**What was built, and each choice the text left.**
1. **When, and on which tree: at delivery, beside the criteria** (`execution.product_acceptance`, §24cl item 1). The
   tree is the candidate delivery verified: the head's checkout with the squad's changes. Its revision is checked
   against the one delivery cut, or nothing is read (`CandidateNotDelivered`, §24cl item 4's rule).
2. **Who renders: a renderer the runtime root builds over the sandbox's scenario runner**
   (`scenarios.declared_routes.DeclaredStartRoutes`, handed to the executor as `route_renderer`). The choice: the
   executor never names the runner. It builds squad task envelopes, and two guards keep every squad-side package from
   importing the held-out scenarios' package (`test_held_out_scenarios_stay_out_of_the_squads_reach`,
   `test_proposal_evidence_stays_on_its_task`; SIP-0113 §4.1, IR-4). So the executor reads a
   `campaigns.product_routes.RouteRenderer`, and only the root names the scenarios' class. The factory requires
   `route_renderer` (#1987's rule). `None` reads every route `blocked_unverified`, naming why.
3. **How the product starts: by the scenario runner's one start path** (X-3b, SIP-0102 §11e; #2414's "one start path,
   never a flag-gated second one"). The start is read by `scenarios.runner.configured_start`, from the Development
   Configuration at the revision the cycle pinned. That function is also what the cycle-end hook reads (#2414's
   remainder), so the two can never start a product differently. The copy is disposable and discarded (contract 3).
   No scenario runs, and no suite is read.
4. **How a page is read: by the evaluator image's own Chromium, with the qa role's flags.** It runs as the container's
   entrypoint (`ContainerSpec.entrypoint`, `sandbox.environment.EVALUATOR_BROWSER`), with
   `route_rendering.DUMP_DOM_FLAGS`, the flags a sample application's pages are read with. It runs on the app network,
   with caps dropped and no new privileges, and with nothing of the app's environment.
   - **Where:** at the app's IP, since a UI server may refuse a name it doesn't know (the driver's precedent), and
     under the declared `ui_base`. SIP-0113 §4.1: "browser pages: a path from its declared UI base".
   - **The choice: not the image's driver.** A request kind in `driver.mjs` would change the image's sources, so its
     tag would move (`test_evaluator_image.py`) and every quality series on `-7` would end. The image, its tag,
     `browser.mjs` and the Chromium pin are unchanged.
5. **What counts as rendered: the sample application's rule** (§8.3, #659, `acceptance.route_rendering`). A route
   renders when its view's root anchor is among the test ids the page's elements carry. The root anchor is the first
   test id the approved manifest gives the route, the manifest the profile's routes were read from (H.7). A page read
   without it is broken, and the increment is rejected. That includes a route the app no longer serves, whose page is
   its 404 or another view's.
   - **The choice: the ids are read from the elements' attributes** (`route_rendering.view_anchors`), not with the qa
     role's pattern, which also counts a `data-testid="…"` in a script's text or a text node. Read live on the
     evaluator image (below), the pattern found 4 distinct ids on a page whose elements carried 2. The qa reading is
     unchanged here. It's filed as #2776, since changing it changes what a sample application's increment is judged
     on.
6. **Seeds and catch-alls, as a sample application's.** A parameterized route's page is brought into being by its seed
   (`increment_tree.route_seeds`, §8.3, #2398). The seed is sent to the app's own address with the path as the manifest
   writes it (SIP-0113 §10n ruling 8). A catch-all is read at `/__squadops_unmatched__` (#2754, #2755).
7. **What blocks every route, naming why.** Never passed (SIP-0096). Each reason is contract 7's (SIP-0112 §8.2.1) or
   SIP-0113 §4.1's:
   - **no start declaration:** "no declaration: every scenario is `blocked_unverified`, reason 'no start declaration'".
     The profile's `no_start_declaration` gap stays as H.7 derives it, disclosed. It isn't relaxed;
   - **a declaration contract 7 refuses** (`declared_start`'s schema check): "no start declaration", with why;
   - **a declared evaluation secret: "secret not available"** (contract 7; Q40). Nothing is resolved before the
     owner's approval record (#2421, placed in 2.6), so a start that declares a secret isn't started without it;
   - **readiness `command`: "no runner"** (§4.1). The runner checks `http` and `tcp`;
   - **no runner, or one unreachable: "no runner"** (§4.1);
   - **a start or readiness failure: "start failed"**, with the runner's detail (contract 7);
   - **no readable approved manifest:** no route's anchor is known.
8. **What blocks one route, naming why:**
   - **a view that declares no anchor.** Nothing on its page could show its view rendered. This is stricter than a
     sample application's rule, which holds such a route on any page read. It's named here and not changed for them,
     with #2776;
   - **a page the browser didn't read:** no `ui_base`, no app network, the image absent, the browser's container not
     run, a non-zero exit, or nothing dumped;
   - **a parameterized route nothing brings into being:** no seed, or a seed the app refused (#2398's reading).
9. **The record.** The `increment_evaluation` document's `routes` entries are a sample application's, with one
   addition: `detail`, on a blocked route whose reader says why. It's written only when set, so a sample application's
   document is unchanged. The `blocked` lines carry the reason ("route /add: not rendered: start failed: …"), and so
   do the campaign's and a successor's brief (§24br). One key is added for this evaluator alone, beside §24cl item 8's
   two:
   - `renderings`: what was started (the tree's identity, the configuration revision, whether it started, and why
     not);
   - and for each route its anchor, the path it was read at, the ids the page showed and why a blocked one wasn't
     read. No reader reads it.
10. **The wire** (SIP-0102 §11k). `POST /api/v1/evaluations` takes `routes`, and answers each one's reading. A service
    that predates it ignores the field and answers none, so each route reads unread and blocks, never passes. Both
    sides deploy together (SIP-0113 §10p ruling 7).
11. **The expected set: the pinned routes and the routes the change request adds** (the outside review of PR #2777,
    P2, 2026-10-28). Before this item, only the profile's routes were judged. A route the increment added fell
    outside the checks, so a broken new page couldn't affect acceptance.
    - **The pinned routes** are the profile's, with their anchors and seeds from the approved manifest (H.7), as
      items 5 and 6 read them. They stay in the set whatever the request names, so a route the candidate drops still
      reads broken.
    - **The added routes** are the surfaces of the approved change request's `client_route` criteria (§7.2's
      surface kinds; §24bv point 5: "an endpoint the start declaration serves", whose page counterpart point 5's
      rails check against the declared `ui_base`). Each is one the profile doesn't pin, taken once. A route the
      request names and the profile pins is judged once, by its pinned anchor.
    - **Where they come from, read against the code first.** A product's change request carries no `manifest_delta`
      (§24bv point 5: "**`manifest_delta`** is absent, and refused if present"), and its schema has no anchor field. A
      `client_route` criterion names a path, a statement and a free-text `observable`. Its footprint names files,
      not routes. So the criteria's surfaces are the only record of the routes an increment adds.
    - **What an added route reads: blocked, whatever its page shows.** Nothing names its view's root anchor, and §8.3's
      evidence that a route rendered is that anchor on its page (item 5). So it is `blocked_unverified`, "the change
      request adds it, and names no anchor of its view". It's still rendered, so its record shows what the page
      carried. An increment that adds a route can't be accepted with it, which is fail-closed (SIP-0096).
    - **The choice: an anchor isn't read from the criterion's free-text `observable`.** A `data-testid` a proposer
      wrote in prose is an unstructured claim, and parsing it would make the observable's wording a contract nobody
      declared. A typed anchor on a `client_route` criterion would change the change request's schema and the
      proposer's prompt (§7.2), which belongs in a design of its own. It's filed as #2779. Until then, every product
      increment that adds a page blocks on that page.
    - **The record:** each route in `renderings` names its `source`, `approved_manifest` or `change_request`.
    - **A product with no blueprint** pins no route, and still has the routes its request adds judged. Before this
      item it had none.
12. **Inert markup is no evidence a view rendered** (the outside review of PR #2777 at `8c09cd4f`, P2, 2026-10-28).
    - **What was found:** `view_anchors` counted the `data-testid` of every element in Chromium's dump, including
      elements inside a `<template>`, whose content is an inert fragment never connected to the document.
      - A fallback page for a missing route could carry an unused template stamped with the route's anchor, and the
        route would read held.
      - Read live on the evaluator image (`-7`), the dump keeps both a template's content and a `<noscript>`'s
        (Chromium runs with scripting on, so the latter is never rendered).
      - On a fallback page whose rendered element was `not-found`, `view_anchors` now finds `not-found` alone. The qa
        role's pattern finds all four ids in the dump, including one in a template and one in a noscript.
    - **What changed:** nothing inside a `<template>` or a `<noscript>` counts, however deep
      (`route_rendering.INERT_ELEMENTS`).
      - An inert element that never closes leaves everything after it inert. So does `<template/>`, which HTML parses
        as an open element. Either way the page can only lose anchors and read broken, never gain one (fail-closed).
      - A page that renders the view reads as before, since its view is connected.
    - **The choice: the dumped DOM, filtered, not a query of the live one.** A live query (an element connected to the
      document, at the route's URL) runs through the image's driver. That would change `driver.mjs`, so the image's
      tag would move and every quality series on `-7` would end (item 4).
      - In a dump, the only content not connected to the document is a template's, and a `<noscript>` is the one
        element a scripted page carries without rendering.
      - **What stays unread:** a connected element that's hidden, whether by `hidden`, `display: none` or being off
        screen, still counts. Visibility isn't part of §8.3's rule as written, and judging it needs the live page.
    - **Where the anchor must be: the root anchor, by its id, not a position the reading checks.**
      - SIP-0105 §17 makes "the first `testids` entry of a route … `data-testid` on the stub's container". §24p rules
        that "a route renders when its view's root anchor does … The root anchor is the first declared id, stamped on
        the view's container (#659)".
      - So the contract requires the root anchor, the first declared id, and not any of the view's other anchors.
        `acceptance.route_rendering` enforces that for a sample application's route and a product's alike: it marks
        only that id missing.
      - It defines the root anchor as an id stamped on the container. It doesn't make the container's position in
        the DOM something a reading must verify. So the reading takes a rendered element carrying the id as the
        container, and nothing here changes the sample-application reading on that point.
    - **The sample applications:** the qa role still reads with its pattern, which counts a template's and a
      `<noscript>`'s content as well as a script's text. Changing that changes counted evidence, so it's added to #2776
      and not changed here.
13. **The evidence that the intended view rendered** (the outside review of PR #2777 at `c1cfe48a`, P2, 2026-10-28).
    - **The rule:** a route renders when *the requested route's own root anchor is carried by a connected, not inert,
      not-hidden-in-markup element, in the page the browser rendered at that route*. A successful browser exit adds
      nothing: exit 0 with an empty dump is unread, and exit 0 with no qualifying anchor is broken.
    - **Hidden in markup, fail-closed** (`route_rendering.hidden_in_markup`). An anchor doesn't count when its element,
      or any ancestor, has:
      - the `hidden` attribute, whatever its value (`until-found` included);
      - `aria-hidden="true"`;
      - an inline `style` declaring `display: none`, `visibility: hidden` or `collapse`, or `content-visibility:
        hidden`, `!important` or not.
      These are treated like item 12's inert markup. A descendant that re-shows itself (`visibility: visible` under a
      hidden ancestor) still doesn't count: fail-closed.
    - **How:** the open elements are now read as a stack. Chromium's serializer writes every non-void element's end
      tag, so the stack is the document's tree. An end tag that opened nothing is ignored, so a stray one can't end a
      hidden region early. An unclosed hidden or inert element leaves the rest of the page uncounted.
    - **Fallbacks and redirects.** A client route on a single-page app answers 200 with `index.html` for any path. So
      an HTTP status says nothing about a client route, and `--dump-dom` shows neither the status nor whether the
      navigation stayed on the route. Read live on the `-7` image: a script that sends `/settings` to `/` leaves
      home's DOM in the dump.
      - What the dump does show is which view rendered. A fallback or a redirect renders another view, whose root
        anchor isn't the requested one, so the root-anchor rule reads it broken.
      - That holds only while no two routes share a root anchor. PR #2780 makes them unique at the rails (SIP-0109
        §24cp). The renderer refuses it here too: two routes in the expected set whose views share a root anchor are
        both `blocked_unverified`, "its view's root anchor is also <the other>'s", since neither page can be told
        from the other's (fail-closed).
    - **Not judged here, named:** hiding by a stylesheet rule (a class, a media query, a parent's rule) can't be seen
      in a dump. Judging it, with the final URL and the status, needs the live DOM through the evaluator's driver.
      That moves the image's tag and ends the `-7` series (item 4). It's filed for the next evaluator tag as #2782.
    - **The sample applications:** the qa role's pattern counts a hidden element's anchor too. That's #2776's change to
      counted evidence, and it isn't changed here.

**The cost.** One more start of the product for each increment whose expected set isn't empty: its install, build and
start. And one Chromium container for each route.

**Not built here:**
- the qa role's reading of a sample application's pages from their elements (#2776);
- an approved secret resolved for the start (#2421, 2.6);
- an anchor a change request names for a route it adds, so an added route can hold (item 11; #2779).
- a visibility reading from the live DOM, with the final URL and the status, for hiding by a stylesheet rule (item 13;
  #2782, the next evaluator tag).

**Evidence.**
- **The wiring, entered at the live caller:** `test_product_runner_acceptance_wiring.py` enters at the executor's end
  of plan (`_execute_sequential`, which delivers), on the shared fixture's Tally. Tally is given a blueprint's routes, a
  `ui_base` and no secret, and its routes are rendered by the root's renderer over the real `ContainerScenarioRunner`.
  The browser's container is the fake's. It covers:
  - the candidate delivery verified, started by its declared start, with both routes held and the evidence on the
    stored document;
  - a route the candidate no longer serves, which rejects the increment;
  - a start that fails, which blocks both routes, naming why.
- **The renderer:** `test_product_routes.py`, over the real runner. It covers each item 7 and 8 reason, the catch-all,
  the seed, the unseeded route, a route with no anchor, a page whose root anchor is missing, and the unverified
  candidate.
- **The runner:** `test_scenario_runner_routes.py`. It covers:
  - the browser's argv, posture and address;
  - the seed's address;
  - the `ui_base` path;
  - a script's text not counted;
  - each unread reason;
  - the routes read after the quality reading and the scenarios;
  - the wire round trip, including an older service's answer.
- **The rest:** `test_http_surface.py` carries the routes through the client and the service. The adapter tests cover
  `--entrypoint`, the image tests `EVALUATOR_BROWSER`, and the route-rendering tests `view_anchors` and the one set of
  flags.
- **Read live on the Spark (2026-10-28).** The worktree's runner and renderer ran over the real `DockerAdapter`, the
  `-7` evaluator image's Chromium (`--entrypoint /usr/bin/chromium`, caps dropped, no new privileges) and an invented
  one-page product, served by `python:3.12-slim` on a throwaway network:
  - of 4 routes, 3 held with their anchors seen, `*` read at the unmatched path;
  - the one the app doesn't serve read broken: `settings-view` missing, `not-found` seen;
  - the page whose script names two other views showed only its own two ids;
  - the copy was removed, and nothing was left running.
- **Item 11's evidence** (the outside review's P2):
  - `test_product_routes.py`: an added route blocked whether its page renders, is broken or reads nothing; the pinned
    routes still judged beside it; an increment with an added route blocked; one that drops a pinned route rejected;
    a product with no blueprint judging its added route;
  - the wiring test at the executor's end of plan: a change request whose criterion is on `/totals`, a page the
    candidate serves broken, and the increment not accepted, with the pinned routes still held.
- **Item 12's evidence** (the outside review's P2 at `8c09cd4f`):
  - `test_route_rendering.py`: no anchor counted inside a template (nested ones too) or a noscript, the elements after
    one still counted, and an unclosed or self-closed template inert to the end;
  - `test_product_routes.py`: a fallback page carrying the route's anchor only in a template, or only in a noscript,
    reads broken;
  - the wiring test at the executor's end of plan: a fallback page with `/`'s anchor only in a template rejects the
    increment, and its record shows only `not-found-view` seen;
  - read live on the `-7` image's Chromium, the dump of such a page: as item 12 says.
- **Item 13's evidence** (the outside review's P2 at `c1cfe48a`):
  - `test_route_rendering.py`: no anchor counted under each hiding attribute or inline declaration, on an element or
    its ancestor; `aria-hidden="false"` and a style that hides nothing still counted; a hidden void element, a stray end
    tag inside a hidden region, and an unclosed hidden element;
  - `test_product_routes.py`: a redirect that renders home, a fallback that renders another view, and an anchor hidden
    by its attribute, an ancestor's inline style or an `aria-hidden` ancestor, each read broken, never held; and two
    routes sharing a root anchor, both blocked;
  - the wiring test at the executor's end of plan: `/`'s anchor only under an inline `display:none`, beside a
    visible fallback, rejects the increment;
  - read live on the `-7` image's Chromium (2026-10-28): the dump of a page whose anchors are hidden by `hidden=""`
    and by an inline `display: none` reads `not-found` alone, and a redirect's dump reads home's anchor alone.
- **Mutants:** forty-seven, all caught: items 1 to 10's twenty-seven, five on item 11, five on item 12 and ten on item
  13:
  - the hidden attribute, `aria-hidden`, an inline style, `display: none`, `visibility: hidden` and
    `content-visibility: hidden` each ignored;
  - `!important` read as part of the value;
  - an ancestor's hiding not inherited;
  - a stray end tag ending a hidden region;
  - a hidden void element counted;
  - a shared root anchor not refused.

  Item 12's
  are a template's content read, a noscript's content read, an inert element never closed, a nested template
  closing the outer one, and a self-closed template read as opening nothing. Item 11's are:
  - the requested routes ignored;
  - an added route held on any page read;
  - the pinned routes dropped when one is added;
  - delivery handing the renderer no requested routes;
  - the record's source lost.
- **The loaded checks** `2619-product-routes` and `2777-review` (the runtime) and `2619-product-routes-sandbox` and
  `2777-review-inert` and `2777-review-hidden` (the sandbox service, which reads the pages)
  (`scripts/dev/loaded_checks.yaml`), each run on the source.

**Who ruled.** The supervisor (the Spark lane) built §24bv point 3's rendering under the owner's direction of
2026-10-21 and the 2.5 grants. Items 1 to 13 are the supervisor's choices, for the owner's review. Items 11 to 13
answer the outside review's findings on PR #2777 (each a P2, relayed by the owner, 2026-10-28). Item 13's direction was
the supervisor's, and its unjudged case is named in it (#2782). Item 12's direction was the supervisor's too,
and its choice not to read an anchor from prose is named in it. Item 9 adds a key
to the `increment_evaluation` document, and item 3 adds a reader of contract 7, so it takes the outside review SIP-0112
H.12 provides before the merge.

### 24cp. A page criterion on a repository-backed change request names its view's anchor, and a route the request adds is judged by it (2026-10-28, §7.2, §8.3, §9.1, §24bv point 5, §24cj, §24co items 5 and 11; #2779; the implementer's design under the supervisor's placement, for the owner)

**Why.** §24co item 11 put the routes a change request's `client_route` criteria name into the routes judged at
acceptance, and left each one `blocked_unverified`, whatever its page showed: a product's request carries no
`manifest_delta` (§24bv point 5), so nothing named the view's root anchor that §8.3's judgement reads. That fails
closed, but it means every product increment that adds a page blocks on that page, and none can be accepted. The
supervisor placed #2779 in 2.5 (2026-10-28) so `z_shelfnote`'s demonstration can accept an increment that adds a
page. §24co item 11 had already ruled out reading an anchor from the criterion's free-text `observable`, so the
anchor is a typed field.

**What changed.**
1. **The schema (§7.2, on a campaign branch).** A `client_route` criterion may carry `anchor`: the `data-testid` its
   page's view renders on its root element, read as a manifest's route reads its first test id (#659)
   (`Criterion.anchor`, `campaigns/change_request.py:164`).
   - **It's authored content, and hashed.** An anchor changed after the ruling fails the hash on load, as a widened
     footprint does (§24cj). The ruling's binding (§9.2) is the hash, so it binds the anchor too.
   - **It's stored only when set,** as a criterion's `paths` is (`_authored_fields`). A request that names none keeps
     its document and its hash. The test pins the hash `origin/main` computes for such a request.
   - **The parse refuses it, as `malformed`, naming why** (`_anchor`, `change_request.py:385`):
     - on a sample application's request: its views are anchored by its manifest delta's `testids`;
     - on a criterion that isn't a page (`endpoint`, `command`, `package`): there's no view;
     - when it isn't a `data-testid` value. That's a letter, then letters, digits, `-` or `_`, at most 64 characters
       (`_ANCHOR`, `:382`). Nothing in it needs quoting in an attribute or a selector, so the page's reading and
       the criterion's test name one element.

     The load runs the same parse, so a stored request is held to the same checks.
2. **The rails (`_anchor_refusals`, `change_request.py:1028`, run by `_validate_product_proposal` at `:979`).** A
   page "the change adds" is one whose route the profile's `client_routes` doesn't name. Those are the routes
   acceptance pins (§24co item 11), read here as `ProductContext.judged_routes` (`:781`).
   - **Required on a page the change adds (`anchor_required`).** The choice was required, not optional:
     - an added page with no anchor can only block at acceptance (§24co item 11), so a request that names none
       is an increment the campaign can't accept with its own page;
     - refused at the rails, it goes back to the proposer with the reason, while it can still be revised;
     - left optional, it would cost a build and a delivery to learn the same thing.

     The reading rejected was optional, blocking at acceptance as before. A request stored before this item, which
     names none, still loads and still blocks, as `NO_ANCHOR_REQUESTED`.
   - **Refused on a page the profile already judges (`anchor_on_judged_route`).** That page is judged by its approved
     manifest's anchor (§24co item 5) whatever the request names, so a second anchor would be one nothing reads.
     - **The reading rejected:** the request's anchor replacing the pinned one. A change could then rewrite an
       existing page to show only the id its own proposal named, and the pin would hold nothing.
   - **One anchor per added page (`anchors_disagree`).** A view has one root element.
   - **A page on a product with no UI base** is refused by its surface alone (`unknown_surface`), and isn't also
     asked for an anchor.
   - **Where the judged routes come from.** The proposal's input carries them now: `profile_view` adds the profile's
     `client_routes` (`execution/product_proposal.py:159`), and `product_context` reads them
     (`planning/proposal.py:142`). An input composed before this item names none, so every page criterion there
     reads as adding its page. That's stricter, never looser.
3. **The renderer (§24co item 11, superseded for a request that names an anchor).**
   - `requested_routes` gives each route the criteria assert on with the anchor they name, or `""`
     (`campaigns/product_routes.py:48`). The first anchor named for a route is taken.
   - The `RouteRenderer` protocol's `requested_routes` is now that mapping.
   - `DeclaredStartRoutes.render` judges an added route by its requested anchor (`scenarios/declared_routes.py:153`),
     exactly as a pinned route is judged (`acceptance.route_rendering`):
     - *held* when the anchor is among the page's elements' test ids;
     - *broken* when the page was read without it, which rejects the increment;
     - *blocked* when the page wasn't read, with the reader's reason.
   - With no anchor named, it's blocked as `NO_ANCHOR_REQUESTED`, as before.
   - A pinned route is judged by its manifest's anchor, whatever the request names.
   - The `renderings` record names the requested anchor on the added route's entry.
4. **Who is told, each through a managed asset (#448).** Each is rendered only when the request names an anchor, so a
   sample application's prompts, and every increment's that names none, are unchanged.
   - **The proposer** (`request.strategy_propose_product_increment`, version 2): the example gains a page criterion
     with its anchor, and a paragraph says what an anchor is, that the build renders it on the view's root
     element, that acceptance reads the page for it, and where a criterion names none.
     - Its profile section (`request.proposal_product_profile`, version 2) lists the pages acceptance already reads
       (`request.proposal_judged_routes`), when the profile names any.
   - **The plan authors** (the dev and qa proposers and the sole-author merger): `increment_views_index`
     (`cycles/task_plan.py:767`), through `request.increment_views_appendix` in `INCREMENT_SURFACES`
     (`handlers/_plan_authoring.py:95`).
   - **The suite's author** (`qa.test`): the test scope's `views` (`campaigns/increment_tree.py:611`, from
     `page_views`, `:651`), rendered by `increment_test_scope_section`. A qa repair inherits it through
     `REPAIR_PRESENCE_KEYS`' `increment_test_scope`.
   - **The view's author** (`development.develop`): `increment_views` (`task_plan.py:870`), declared by
     `ContextAssemblyContract.increment_views` (`context_assembly.py:163`, set at `:307`). It's rendered in the
     focused prompt (version 8) and the monolithic one (version 3) by `increment_views_section`
     (`handlers/increment_test_scope.py:66`).
   - **Narrowed: the framing section isn't changed.** `request.increment_framing_section` is every increment's, a
     sample application's included. A framing stage sees the anchor in the change request it's shown, and the plan
     authors are shown the views appendix.

5. **The outside review (SIP-0112 H.12) of PR #2780 at `7c19e900`, relayed by the owner: changes requested, two
   P2s, both fixed in that PR.**
   - **P2 1: an added route with a parameter could never be verified.**
     - **Why:** a route the request adds gets an anchor but no seed. Seeds come from the approved manifest's creates,
       which only a pinned route has (§24co item 6). So `literal_path` returns nothing, and the route blocks forever,
       as this item's first text said under "not built".
     - **The choice, the supervisor's for 2.5: refuse it at the rails, not seed it.** A page criterion on an added
       route whose path needs a seed is refused as `added_route_unseedable`, naming a fixed path the proposer can
       use instead (`_unseedable`, called from `_anchor_refusals`). "Needs a seed" means a segment that:
       - is a parameter as the renderer reads one (`:x` or `{x}`, `increment_tree.route_param`);
       - is bracketed (`[x]`, a Next.js dynamic segment);
       - or holds a `*`.
     - **Why refuse rather than seed:** a seed for an added page would be another typed field of §7.2's request (the
       create endpoint, its body and the parameter the id fills), with its own design and outside review. Refusing
       keeps a proposal from passing validation only to block at acceptance, which is the failure #2779 exists to
       end. The seed mechanism is filed as #2781.
     - **Read stricter than the renderer:** an added catch-all (`/docs/*`) is refused too, though the renderer reads
       a catch-all at its unmatched path. The supervisor's rule names `*`, and #2781 can relax it with the seed
       design.
     - **What stays fail-closed:** a request stored before the rule may still name an added parameterized route. It
       blocks, unseeded, whatever anchor it names. A pinned parameterized route is seeded from its manifest as
       before, and isn't refused.
     - The proposer is told the rule in its request asset, before its first attempt.
   - **P2 2: a development correction repair lost the anchor.**
     - **Why:** `increment_views` reached `development.develop` but wasn't in `REPAIR_PRESENCE_KEYS`, and the repair
       prompt rendered no views. So a developer correcting a failed view could rewrite it without the anchor
       acceptance enforces.
     - **The fix:**
       - `increment_views` rides `REPAIR_PRESENCE_KEYS` (`capabilities/context_assembly.py`);
       - `_RepairPromptMixin._render_increment_views_section` renders the same managed asset,
         `request.increment_views_appendix`, into `request.cycle_repair_task` (version 16, slot
         `increment_views_section`);
       - the section renders for a dev repair only, from the failed task's `increment_views`, or from a failed
         `qa.test` scope's `views`, so a dev repair of a qa failure keeps it too. A qa repair already sees the views in
         its test scope.
     - This replaces the item's first text, which listed "a dev repair isn't shown the views" as not built.
6. **The outside review's final round on PR #2780, relayed by the owner: one P2 and two P3s, all addressed here.** The
   owner's words: "Consider this the last feedback rounds so we can merge after changes are made and CI green".
   - **P2: an anchor was unique per route, not across pages.**
     - **The failure:** `/` is pinned with `home-view`, and a request adds `/export` naming `home-view` too. The
       candidate never builds `/export`, the single-page app's fallback renders the home view there, and `/export`
       reads held.
     - **The fix:** an added page's anchor must be one no other page carries, read by one function,
       `anchor_conflicts` (`campaigns/change_request.py`). "Another page" means:
       - every route of the approved manifest, with every test id its view carries, not only its root, since the
         fallback renders the whole view;
       - every other page the request adds.
     - **Where it's checked:**
       - **The rails** refuse a conflict as `anchor_not_unique`, naming the page that carries the anchor and asking
         for an anchor of the page's own.
         - They read the manifest's anchors from the proposal's input, as `ProductContext.route_anchors`, which
           `product_context` builds from the `approved_manifest` the run already composes (§24cj item 3) through
           `increment_tree.declared_routes`, the reading acceptance uses.
         - A manifest acceptance can't read gives none. Acceptance then blocks every pinned route (`NO_MANIFEST`),
           so there is nothing to hold against.
       - **The renderer** blocks such a route on a request stored before the rule, with the reason `the change
         request names an anchor another page carries (<page>)`. It never holds it. Where the anchor it reuses is a
         pinned view's root, that pinned route is blocked too, by §24co item 13's shared-root rule: neither page can
         be told from the other's (fail-closed).
     - The proposer is told the rule in its request asset.
   - **P3: the rollout is a gate, not a note.**
     - **What a request with no anchor keeps:** main's document and its exact hash. That's
       `test_a_request_that_names_no_anchor_keeps_the_document_and_hash_it_had`, which pins `83b4cece…`, the hash
       `origin/main`'s `change_request.py` computes. It was recomputed on main `5a59fb65`, whose `change_request.py` is
       main's of `96709264`, and it is unchanged. Every live campaign's stored sample-app request still loads
       (`test_change_request.py`'s fixtures).
     - **What an anchored request does on a skewed deploy:** an older runtime-api fails closed. Its parse ignores
       `anchor` and its hash leaves it out, so the stored hash doesn't match, and the request is refused at load ("the
       stored change request's content does not match its hash"). The framing then can't read it, so no increment is
       built or accepted on a request half the deploy can't read. This was read by loading a request the new rails
       stored with main's own `change_request.py`: it was refused, and an anchor-less one loaded with its hash.
     - **The gate:** the loaded-check pair `2780-rollout-runtime` (runtime-api) and `2780-rollout-nat` (nat).
       - Each hashes, stores and loads one fixed anchored request, and expects the same hash.
       - The nat row also expects `anchor_not_unique` and a conflict found.
       - `verify_loaded.py` fails on any row that answers otherwise, so a deploy where either side lacks the anchor
         fails verification. Read on #2777's head `c1cfe48a`, both rows fail.
   - **P3: live integration.** The 2.5 demonstrations are where it runs live: a complete anchored increment on
     `z_shelfnote`, and a missing-route negative. Nothing more is built for it here.

**Not built here:**
- **An added page whose path needs a seed** is refused, not seeded (item 5). The seed is #2781.
- **The anchors of pages earlier increments added** aren't known to the rails or the renderer. They're in no manifest,
  and in no current request. So a request may reuse one, and a page it never built could hold where the fallback
  renders that earlier page. The same holds for a product with no approved manifest, whose existing pages' ids are
  known nowhere. Closing it needs the accepted increments' anchors carried into the proposal's input, as the frozen
  criteria are (§24ap). That's #2783.
- **The anchor is matched anywhere on the page,** as a pinned route's root anchor is (§24co item 5), not only on the
  view's outermost element. The prompts ask for the root.
- **A route the request adds that the profile pins later** (its pin moves between the proposal and the acceptance) is
  judged by its pin, as item 3 says.

**Evidence.**
- **The wiring, entered at the live callers:**
  - `test_product_runner_acceptance_wiring.py`: the executor's end of plan (`_execute_sequential`) on the shared
    fixture's Tally, its request asserting R1 on `/totals` with the anchor `totals-view`. A candidate whose page
    renders it holds the route. One whose page renders another view reads it broken, and the increment is
    rejected with `route /totals: missing totals-view`. The pinned routes hold beside it in both.
  - `test_strategy_propose_product_increment.py`: `handle()` with the real assets. The proposer is shown the judged
    pages and the anchor paragraph, a page with no anchor is returned for revision as `anchor_required`, and the
    revision's stored request carries the anchor. A criterion on a judged page is accepted with none, and Tally,
    which judges no page, is shown no judged-pages section.
  - `test_product_proposal.py`: `RunProvisioning.prepare` composes the profile's `client_routes` into the proposal's
    input, and `[]` for Tally.
  - `test_product_increment_seams.py`: `generate_task_plan` for the framing gives the merger the views index, and the
    plan authors' real `render_surfaces` renders it. For the implementation, the developer is given
    `increment_views` and the suite's author the scope's `views`, and both prompts are rendered by their
    handlers, the qa author's by its whole `handle()`. A request with no anchor gives neither.
- **The rails:** `test_product_change_request.py`, which covers:
  - the accepted shape, its anchor stored and hash-bound;
  - the hash of a request that names none pinned as main's;
  - each of the three refusals;
  - two criteria naming one anchor, accepted;
  - seven malformed values;
  - an anchor off a page or on a sample application;
  - a page with no UI base.
- **The renderer:** `test_product_routes.py`, which covers:
  - an added route held, broken on another view's page, and broken on a server error;
  - one unread, blocked with the reader's reason;
  - a pinned route keeping its manifest's anchor against the request's;
  - `requested_routes` over a stored request: an endpoint left out, and a second criterion that names no anchor
    not blanking the first's.
- **Rendered (the prompt standard's rule 8),** through the real handlers on the tests' inputs, with sizes estimated
  as characters / 4:
  - the proposer's prompt is 9,371 characters (about 2,340 tokens). The anchor paragraph is about 160 tokens of it,
    and the judged-pages section about 75;
  - the views appendix is about 160 tokens in the developer's focused prompt.
- **Twenty-three mutants, each caught:**
  - in the schema: an empty anchor stored; the anchor left out of the hash; any value read as well-formed; an anchor
    on a sample application, or off a page, admitted;
  - in the rails: the rails never run; an anchor on a judged page, an added page with none, and two anchors on one
    page, each let through; the judged routes never composed, or never read;
  - in the proposer's prompt: no judged-pages section;
  - in the renderer: delivery handing no anchors; a later criterion blanking one; the renderer ignoring it; the
    request's anchor overriding a pinned one;
  - in what the authors are shown: the scope's views, the plan index, the view author's input and its declaration
    each dropped; the developer's, the suite's and the plan surfaces' renderings dropped.
- **The loaded checks** `2779-runtime`, `2779-nat`, `2779-neo`, `2779-eve` and `2779-max`
  (`scripts/dev/loaded_checks.yaml`). Each row answers its `expect` on the source, and each was read on #2777's head
  (`8c09cd4f`), where every row answers something else.
- **Item 5's evidence** (the outside review's two P2s):
  - **P2 1, end to end under the refusal:** `test_strategy_propose_product_increment.py` enters at `handle()`. The
    proposer is told the rule before its first attempt, and an added `/reports/:report_id` is refused at each
    attempt as `added_route_unseedable`. The task fails with no change request stored, so nothing is ruled on or
    built.
  - **P2 1 at the rails:** `test_product_change_request.py` covers five paths refused (`:x`, `{x}`, `[x]`,
    `[...x]`, `/docs/*`) and a pinned parameterized page accepted.
  - **P2 1 at the renderer:** `test_product_routes.py` shows a request stored before the rule still blocks its added
    parameterized route, unseeded.
  - **P2 2:** `test_product_increment_seams.py` starts from the anchored `development.develop` that
    `generate_task_plan` makes. It fails the task into the correction loop (`run_correction_protocol`, a patch
    decision), and runs the dispatched `development.correction_repair` through
    `DevelopmentCorrectionRepairHandler.handle()` with the real assets. The repair carries `increment_views`, and its
    prompt names `/totals` and `totals-view`. On a request that names no anchor, neither appears.
  - **Nine more mutants, each caught:**
    - the seed rule never asked;
    - a bracketed segment, a wildcard, or a `:param` read as fixed;
    - the proposer never told the rule;
    - the repair handoff dropping the views;
    - the dev repair rendering none;
    - the rendered section never reaching the template;
    - the template without its slot.
  - **Loaded checks** `2780-review-runtime`, `2780-review-nat` and `2780-review-neo`, each run on the source.
- **Item 6's evidence** (the final round):
  - **At the rails:** `test_product_change_request.py` refuses an added page reusing a pinned view's root, another id a
    pinned view carries, the fallback view's root, and one anchor shared by two added pages. An anchor no page
    carries is accepted.
  - **Through the proposer's `handle()`:** `test_strategy_propose_product_increment.py` gives an input carrying a real
    approved manifest. The proposer is told the rule, a page reusing the home view's root is returned as
    `[anchor_not_unique]`, and only the revision's own anchor is stored.
  - **At the executor's end of plan:** `test_product_runner_acceptance_wiring.py` uses a request stored before the rule,
    naming `/`'s `counter-list` for `/totals`. The candidate never builds `/totals`, and the fallback serves the
    counter list there. `/totals` reads blocked, never held. `/` shares its root with it, so it's blocked too
    (§24co item 13), and `*` still holds.
  - **At the renderer:** `test_product_routes.py` covers the same three conflicts.
  - **Eight more mutants, each caught,** for 40 in all:
    - the rails never checking across pages;
    - the manifest's pages ignored;
    - added pages not checked against each other;
    - only a view's root read;
    - the input's manifest never read;
    - the renderer holding a reused anchor;
    - the renderer reading no pinned anchors;
    - the proposer never told.
  - **The rollout pair** `2780-rollout-runtime` and `2780-rollout-nat`, run on the source.

**Who ruled.** The supervisor placed #2779 in 2.5 (2026-10-28) and directed its shape: a typed anchor, validated at
the rails, hashed, and named in the proposer's prompt. Making the anchor required on an added page, refusing it on a
judged one, and narrowing the framing section are the implementer's choices (the Spark lane), for the supervisor's
and the owner's review. This changes §7.2's change request, a shared contract, so it takes the outside review SIP-0112
H.12 provides before the merge. Item 5 answers that review's first round, relayed by the owner (2026-10-28). Refusing
an added page that needs a seed, and filing the seed as #2781, are the supervisor's choices for 2.5. The repair's fix
is as the review asked. Item 6 answers the review's final round, relayed by the owner (2026-10-28), as it asked:
uniqueness across every page, refused at the rails, and the rollout as a loaded-check pair. Reading every id a pinned
view carries, not only its root, and blocking at the renderer too, are the implementer's.

### 24cq. An owner's pause or abort holds across a cycle's hearing: the campaign is read again before each write, and a paused campaign's ending waits for its resume (2026-10-29, §10, §12a, §17, §24cc; SIP-0113 §4.1, §10ac; #2789; the implementer's fix, for the owner)

**What was found.** #2788's outside review (its P2-A) found a calibration record's hearing promoting and deciding
from a campaign read before a minutes-long baseline reading. The hearing of a cycle's ending has the same shape,
`CampaignProgress._hear`:
- it reads the campaign once, then assesses the ending and evaluates it against the pinned suite (SIP-0113 §4.1), which
  builds, starts and reads the product;
- it then promotes and decides from what it read first.

Reproduced on the shared fixture (Tally, a real managed clone, an increment delivered for real), with the owner's
pause applied while the increment's tree was read. The rows after the hearing were:
- `pause` (`building → paused`);
- `promote` (`paused → building`);
- `decide` (`building → evaluating`);
- `decide`, to its next action.

The pause was undone. An abort applied the same way had the promotion refused, and the refusal was raised out of the
hearing.

**A second defect, read while building it.** A campaign the owner paused *before* its cycle ended fared the same:
- **Today's hearing decided it at once.** Probed on the same fixture, it promoted the increment (`paused → paused`)
  and decided it out of `paused`: to `escalated` there, since row 5's proposal profile isn't held, and to
  `at_proposal` with a launch on a deploy that holds it.
- **§17 says otherwise:** "a `paused` campaign holds the decision's pending action, and its resume executes that
  action". The code holds an action only for a limit's pause. `Guard.PAUSED` comes from `_pausing_limit`, and
  `held_action` reads only a decision row that moved the campaign into `paused`. A decision made under an owner's
  pause had no held form.
- **It made the first fix moot.** Without a fix to this, re-reading during the hearing would only delay the undo. The
  sweep re-hears within its interval (`rehear_ended`), and that hearing would decide over the still-paused campaign.

**What changed** (`src/squadops/campaigns/progress.py`):
1. **The campaign is read again before each write.**
   - Before the promotion (`:706`), after the assessment and the evaluation.
   - Before the decision (`:742`), after the promotion and the reads that build the decision and its launch.

   `_still` (`:812`) compares the state with the one read before the step. A campaign that moved (paused, aborted,
   anything) is logged (`campaign_cycle_not_decided_campaign_moved`), and the hearing returns nothing. The re-hearing
   decides it as it then is, and its evaluation isn't taken twice: the evaluator skips a cycle it has read
   (SIP-0113 §10c).
2. **A refusal is logged, never raised.** A move in the instant between a read and a write can still refuse the
   promotion or the move to `evaluating`. `_promoted_and_evaluating` (`:770`) logs it (`campaign_cycle_promotion_refused`),
   and the hearing returns nothing. The decision's own refusal was already caught.
3. **A paused campaign's ending waits for its resume** (`_heard_now`, `:341`). The hearing returns at once, nothing
   promoted, evaluated or decided. Once the owner resumes it, the re-hearing decides it, as any ending is decided.
   - **This is a change of behaviour.** The supervisor's brief for #2789 asked that a pause before the cycle ends
     behave "exactly as today: the decision is recorded and its guardable action is held for the resume". The code
     did not hold it (above), so "today" and that description disagree.
   - **I kept the description's intent** (nothing launches over a pause, and the resume leads on) and not the code's
     behaviour, which is the defect.
   - **The alternative** was to record the decision as held under an owner's pause. That would change `held_action`,
     `owner_held` and the resume route's reading of a paused campaign. That's a change to §10's held-action contract,
     larger than this fix, and it is left for the owner to rule if wanted.
4. **A re-hearing takes an applied promotion as written** (`_promoted_already`, `:803`).
   - **Why:** the promotion's row carries the campaign's state at the time. Replaying it under a state that has moved
     since (`evaluating`, or back from a pause) sends other content under the same key, which the registry refuses as
     a conflicting idempotency key (§12a).
   - **Found while building this.** It was also latent in §12a's own restart: after the move to `evaluating` had
     committed and before the decision, the restarted hearing's replayed promotion was refused, and the ending was
     never decided.
   - The branch's ref follows its row by the startup's and the sweep's re-sync (§24cd point 2).

**What it doesn't change:**
- a campaign left alone, heard at once as before;
- a completed campaign's ending, never decided;
- an escalated campaign's ending, decided as before;
- the rows' shapes and keys.

**Not closed here:** the instant between the decision's last read and its write. No row carries an `expected_state`,
and a decision written with one would refuse itself whenever anything legitimate moved the campaign.

**Evidence.**
- **The wiring:** `tests/unit/campaigns/test_hearing_holds_the_owners_word.py` enters at `CampaignProgress.cycle_ended`
  and `rehear_ended`, the completion boundary's and the startup's calls. The progress and the evaluator are built as the
  runtime root builds them. It runs on the shared fixture's Tally, an increment delivered for real, and an evaluation
  against a pinned suite. It covers:
  - a pause during the evaluation: nothing written, not decided while paused, and decided once after the resume, its
    evaluation taken once;
  - an abort during it: nothing written, and no raise;
  - a refusal in the last instant: logged, not raised;
  - a pause after the promotion: the decision held, then decided after the resume, with one promotion;
  - a campaign paused before its cycle ended: nothing until it is resumed, then decided once;
  - a restart after the move to `evaluating`: decided once;
  - the control: a campaign left alone, heard at once.
- **Mutants: 8, 7 caught by a named failing test:**
  - each re-read dropped;
  - a moved campaign read as still;
  - a paused campaign's ending decided at once;
  - the promotion's refusal raised;
  - an applied promotion replayed;
  - another cycle's promotion taken for this one's.

  The survivor returns the campaign read before the step, not the one read again, when its state is unchanged. That
  is equivalent under today's operations. Only a promotion or a branch's rebase changes a campaign's fields other than
  its state, and neither runs while a cycle is being built. A record-only operation changes only the log.

**Who ruled.** The supervisor placed #2789's fix in 2.5, stacked on #2788, so that it deploys before the
demonstrations: a later fix would void their evidence under the plan's invalidation rule. The build choices are the
implementer's, for the supervisor's and the owner's review. Item 3 departs from the brief's "unchanged", with the
evidence above.
