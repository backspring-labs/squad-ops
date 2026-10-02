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
| proposal-run retries | the cycle ends `proposal_failed` | — |
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
  unfrozen until a later criterion covers it.

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
  until the next restart.
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
