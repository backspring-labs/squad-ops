---
sip_uid: '17883224960382348'
title: Campaign Orchestration
status: proposed
author: jladd
created_at: '2026-07-04T00:00:00Z'
---
# SIP: Campaign Orchestration

## Status

Proposed — **revision 3 (2026-10-01), for design review.** **Targets v2.0, the headline**
(`docs/plans/2-0-0-plan.md`, draft).

**The rule this SIP establishes** (from the crew's design review, adopted):

> A campaign is a **persisted, resumable state machine** in which:
> - **the strategy role alone authors change requests;**
> - **the supervisor rules without becoming the author;**
> - **every launch is derived exactly once from durable evidence and a recorded ruling.**

**What revision 3 changes.** Revision 2 made the campaign evolve one app, under a supervisor's leash.
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
4. The **change request is typed** (§7.2), and evaluation runs on **three trees**: accepted, candidate,
   and the baseline-evaluator overlay (§7.4).
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

### 7.4 The three trees

| tree | content | identity | who writes it |
|---|---|---|---|
| **accepted** | the last accepted increment's tree | SIP-0107 §20 verified identity | promotion only (§12a) |
| **candidate** | the accepted tree plus this increment's applied patches | workspace revision id (#734) | the increment's implementation and correction runs |
| **baseline-evaluator overlay** | the accepted tree's **product code**, plus the candidate's test files, test configuration and test-only dependencies. **Never the candidate's product code** | the accepted identity plus a hash of the overlaid test set | built per evaluation; never persisted as a tree |

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

At acceptance, each criterion is **frozen**: its id, its test ids, the test files' content hashes, and
the exact runner invocation. That frozen set is the criterion's executable form. Accumulated acceptance
re-executes **every frozen criterion** not in `retires` on the **candidate** tree, by its frozen
invocation, and an increment is accepted only if all of them pass.
- A frozen test file whose hash differs on the candidate is a must-not-break violation, unless its
  criterion is in `retires`.
- A criterion that cannot execute counts as `blocked_unverified`, never as a pass (SIP-0096).

### 8.2 Baseline discrimination: one test per new criterion

For a `feature` or `fix` increment, each criterion it adds needs **at least one test that fails on the
baseline-evaluator overlay for the intended reason, and passes on the candidate.** Other new tests,
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
| accumulated acceptance (§8.1) | the candidate tree | the frozen criteria | `blocked_unverified` | a per-criterion result keyed by (increment, criterion id, candidate identity) | recomputed, idempotent by key |
| route rendering (§8.3) | the candidate tree, booted | the accumulated manifest's routes | `blocked_unverified` | a per-route result | recomputed |
| promotion (§12a) | none: reads the results above | every result recorded and passing | no promotion | the new accepted identity, in one control-log transition | idempotent: the transition is keyed by (campaign, increment, candidate identity) |
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

Computed once per campaign cycle, after it reaches `CycleCompletion` and its participants are released:

```
campaign_continuation_decision(
    campaign:  CampaignState,       # objective, policy, counters, flags, accepted identity
    cycle:     CycleRecord,         # kind, terminal state, gate outcome
    latest:    CycleAssessment,     # verdict; attribution.primary (SIP-0108 §4.2)
) -> ContinuationDecision           # pure; keyed by cycle id
```

**The ordered table. The first matching row wins:**

| # | predicate | outcome |
|---|---|---|
| 1 | the campaign is aborted | `stop` (aborted) |
| 2 | `cycle.kind = calibration` and `latest.verdict = accepted` | `continue`: the calibration tree becomes the first accepted baseline |
| 3 | `cycle.kind = calibration` and `latest.verdict ≠ accepted` | `stop_failure` (calibration) |
| 4 | `latest.verdict = accepted` and the objective's measurement is met with this increment counted | `stop_success` |
| 5 | a stopping limit is reached (total cycles, no-progress) | `stop_failure` (that limit) |
| 6 | a pausing limit is reached (elapsed time, budget, rejected proposals in a row) | `pause` (that limit) |
| 7 | the cycle ended `rejected_at_gate` or `proposal_failed` | `continue`: propose anew |
| 8 | `latest.verdict = accepted` | `continue`: promote, then propose the next |
| 9 | `latest.verdict = blocked_unverified` and repair cycles remain for the increment | `repair` |
| 10 | `latest.verdict = blocked_unverified` | `escalate` |
| 11 | `latest.verdict = rejected`, `latest.attribution.primary = environment_or_infrastructure_failure`, and retry cycles remain | `retry` |
| 12 | `latest.verdict = rejected` and repair cycles remain for the increment | `repair` |
| 13 | `latest.verdict = rejected` | `continue`: the increment is abandoned (counts as unaccepted); propose anew |
| 14 | otherwise | `escalate` |

**The rules that bind the table:**
- **Success first.** An increment that meets the objective on the last allowed cycle is a success
  (row 4 before row 5).
- **Hard stops before pauses,** and pauses before outcome-driven continuation.
- **`blocked_unverified` never yields `continue` or `stop_success`.** It yields `repair`, `escalate`,
  or a limit's stop or pause. An unverified cycle proves nothing to continue from.
- **`stop_success` needs `latest.verdict = accepted`.** Agent narrative never yields it.
- **No outcome launches a cycle directly.** `continue`, `repair` and `retry` create the next cycle,
  whose own gate and launch preflight apply.
- **No `wait` outcome.** A pending ruling is an open gate inside the next cycle, never an output of
  this function.

---

## 11. The calibration cycle (#1709)

Every campaign opens with **the same PRD built from scratch** on the campaign's deploy, under a fixed
request profile. It is the **yardstick for greenfield behaviour**, and only rows 2–3 of §10 read its
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
| completed | nothing |

**The required outcomes, each verified by a fault-injected diagnostic:**

| event | required outcome |
|---|---|
| a restart in any state above | the table's resumption; **no ruling lost**, because a ruling is committed before it is acknowledged |
| a duplicate completion event for one cycle | **one** continuation decision, keyed by cycle id; never two cycles created |
| a repeated ruling | the recorded ruling; nothing new happens |
| a conflicting idempotency key | refused and recorded |
| interruption during accumulated acceptance or promotion | **no partial promotion**: the accepted identity changes only in the promotion transition, after every result is recorded |
| an abort | terminal: the running cycle is cancelled by the existing path; **no continuation follows**, whatever arrives after |
| a timeout or launch-blocked state | resumable exactly as §9.2 and §9.3 say |

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
- **one failure record per failure:** each `FailureEvent` the evidence carries
  (`src/squadops/cycles/failure_attribution.py:416`), its class by `compose()`
  (`failure_attribution.py:446`), the registry version, and the campaign, cycle and increment.
  `compose()` already records an unplaceable event as `unattributed`, and a declared non-failure as none.
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
- `ContinuationDecision`.

---

## 16. Persistence

`CampaignRegistryPort`, beside `CycleRegistryPort`, with memory and Postgres adapters. Tables:
- `campaigns`;
- `campaign_control_log`;
- `campaign_ledger`;
- `campaign_frozen_criteria`;
- `campaign_failure_records`;
- `campaign_box_lease`;
- `cycles.campaign_id` and `cycles.kind`, both nullable.

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

Every transition is a control-log row with its cause. `cancelled` derives `CANCELLED`, as on `Cycle`.

---

## 18. Implementation order (dependency-ordered)

| step | delivers | what it proves before the next starts |
|---|---|---|
| 1 | the domain model and the transactional control log (#1799) | a control operation commits atomically with its state change; an idempotency conflict is refused; a restart reads state from the log |
| 2 | the proposal run and the typed change request (#1706) | the run recruits and releases like any run; out-of-scope proposals are refused; the delta passes the manifest gates or the run fails |
| 3 | the three trees and their isolation (#1806) | the accepted tree is immutable; the overlay contains no candidate product code; test identity classifies new, modified and renamed tests |
| 4 | accumulated acceptance and baseline discrimination (#1707, #1796) | frozen criteria execute on the candidate; a criterion without a discriminating test is not met; an import error is not discrimination |
| 5 | the increment gate, the binding, the box lease and the continuation table (#1801, #1802, #1800) | stale and conflicting rulings are refused; every launch path honours the lease; each table row is reachable, with precedence as written |
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
12. Each row of §10's table is reached by a crafted input, with the precedence as written. The function
    is pure, which an architecture test asserts.
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
- **Recovery:** one fault-injected diagnostic per row of §12a's required outcomes.
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

## Revision history

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
