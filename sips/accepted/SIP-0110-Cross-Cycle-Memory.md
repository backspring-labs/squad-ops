---
sip_uid: '17883224960394576'
status: accepted
title: Cross-Cycle Memory
author: Jason Ladd
created_at: '2026-08-03T00:00:00Z'
sip_number: 110
updated_at: '2026-10-06T08:19:56.067127Z'
---
# SIP-0110: Cross-Cycle Memory

> **Placement and delivery (2026-10-04: the owner's rulings on the SIP-portfolio audit, `sips/PORTFOLIO.md`).** **The 2.2 headline, and 2.2's only change to squad behaviour**, beside #1708's auto tier and escalation queue, which change the control plane, not the squad. #557, #949 and #950 follow Outcome Evaluation's scenarios (2.4 or later). **Its 2.1 part** (the inert recall port, its call site, and the Phase-1 re-read) is **#1964**. **It owns** memory's scopes, lifecycle and payload; Capability-Backed Agents (3.x) defers to it. **A constraint from 3.x:** memory stays addressable as a service, the Embodiment Runtime's invariant 2. **Accepted with revision 4 (2026-10-06, §5b):** the re-read moves Phase 1's proving workload to the campaign's proposal gate. **Revision 6 (2026-10-07, §5d) restores the cycle as Phase 1's unit:** every eligible cycle is observed, inside a campaign or not, and the proposal gate is where Phase 1 is measured first, not its scope.


## Status
Accepted (2026-10-06), with revision 4, on the 2.2 plan's PR. The owner reviews both together, and
the merge is the acceptance (CLAUDE.md, SIP workflow step 3). Phase 1 is the 2.2 headline
(`docs/plans/2-2-0-plan.md`, a draft in the same PR).

**Author:** Jason Ladd
**Created:** 2026-08-03
**Revision:** 6 (2026-10-07). It restores the cycle as Phase 1's unit, which revision 5 had narrowed to the
campaign, and records the change in §5d. Revision 5 (2026-10-06) adopts an external design review as §0, the
normative Phase-1 contract, and records the change in §5c. Revision 4 (2026-10-06) re-reads Phase 1's value hypothesis against the evidence of 2.1's
line (§5b, #1964) and moves Phase 1's proving workload from the plan gate to the campaign's proposal
gate, where the recurrence is live. Revision 3 (2026-10-01) folds in the new elements of the owner's v4 draft (2026-08-29,
recorded in `docs/ideas/cross-cycle-memory-v4-draft.md`) as §5a, corrects references that went stale,
and states how Campaign (2.0) and this SIP meet. Revision 2 (2026-08-03) incorporated design-review
round 1: the typed Phase-1 primitive, governed encoding templates, the lifecycle `status` dimension,
deterministic Phase-1 retrieval, the recall-vs-outcome metric split, and Phase-1 decay.
**Builds on:** SIP-042 (LanceDB semantic memory — the storage mechanics until revision 6, which stores Phase 1's
records in Postgres, §0.8), SIP-0088/0089
(persistent agent identity), #669 (framing re-roll rejection context — the within-cycle
rung and the injection seam this SIP reuses), SIP-0101 (Cycle Replay Harness — the
measurement instrument), Campaign Orchestration (proposed, **v2.0's headline**, revision 2; see §7
and §5a).
**Absorbs:** the "Hierarchical Cognitive Memory Architecture" idea doc (J. Ladd, 2026-08)
as the long-term vision (§10); this SIP normatively specifies only Phase 1.
**Placement amended 2026-09-12 (owner's ruling, `docs/plans/1-8-0-plan.md` §8 decision 2):** **v2.2**, after Campaign headlines v2.0 — not a 1.8 rider and not a 2.0 rider. The evidence: the B1 baseline's inputs (`src/squadops/cycles/rejection_baseline.py`) hold thirteen rejection records, all 2026-08-10 to 2026-08-23, and none since 1.6.2's success-status single-sourcing; every counted set since 1.6.3 reports zero framing re-rolls, so Phase 1's seed corpus at the plan gate is empty on this workload — a zero that says the original proving workload is dormant, not that the mechanism has no value — and the recurrence that remains is in the correction loop (this SIP's own §13 question 3, "Phase 1.5"). **What 1.8 does for this SIP:** emits the B1 baseline as a document; ships the one lineage seam and the one failure-attribution registry (intentions 1 and 2) for the scorecard's sake. **What ships in v2.1, not in 1.8:** the recall port, an inert NoOp that answers *empty* (not `NoOpMemoryPort`, which raises), the root injecting it explicitly (a factory with a required selector arrives with the first real adapter), and the call site through `plan_rejection_context` — declared on six task types on main, not the three counted below. **2.1 also re-reads this SIP's Phase-1 value hypothesis against the recurrence evidence available at its cut**, so 2.2 activates the mechanism against a proving workload that is actually live. The paragraph below is the superseded 2026-08-07 placement, kept as the record.

**Placement amended 2026-08-07** (`docs/plans/post-1-5-roadmap-reconciliation.md`):
Phase 1 is no longer a committed 1.8 rider. It is a **decision point taken at 1.8 plan
time** — thin Phase 1 in 1.8, or pushed whole to 2.0 beside Phase 2 — because 1.8's two
co-headliners (Cycle Evaluation Scorecard + Campaign) are already substantial surface.
**The rails ship in 1.8 either way**, per the standing rails-before-mechanism rule
(SIP-0101 Slice 1, SIP-0096 Phase 1 inert core): the recall port is defined, a NoOp is
injected per the always-inject pattern, and the call site is wired, so whichever way the
decision goes it is an adapter swap and not a redesign. Four design intentions in that
record protect this SIP's seams inside 1.8 — one cycle-lineage identity (Campaign's
envelope, not a private concept), one failure-class vocabulary (not a parallel taxonomy
in the scorecard), recall through the existing `plan_rejection_context` contract rather
than a handler branch, and the inert port above. **A fifth intention lands in 1.6, not
1.8, and is the only one that cannot be retrofitted:** the pre-memory rejection-class
recurrence baseline must be recorded during the authored-mode window, since once memory
is live that baseline is unrecoverable and this SIP's value claim becomes unmeasurable.
**External reference:** CrewAI, "How we built cognitive memory for agentic systems"
(blog.crewai.com) — adopted for its failure catalog and recall design; deliberately
diverged from on agent-discretionary memory tools (§6).

---

## Delivery ledger (current as of 2026-10-08)

Kept by the rule in CLAUDE.md ("SIP System"): one row per part, updated in the PR that ships or
re-places it.

| part | status | where |
|---|---|---|
| the recall port, inert (answers empty), injected explicitly by the root, and its call site through `plan_rejection_context` | **shipped** | 2.1.0, PR #2058, issue #1964 |
| the re-read of the Phase-1 value hypothesis against 2.1's recurrence evidence, as an amendment here | **shipped** | PR #2097, issue #1964: the evidence up to the final deploy is §5b (revision 4), and the cut's readings are §5b's last part |
| Phase 1, slice 1: capture each consuming seam's inputs before authoring (proposal writing first, then plan writing, build authoring and repair), and the source-case inspection (§0.11, §0.4) | **placed** | 2.2.0, #2105 |
| Phase 1, slice 2: the authoring replay, three arms, validated first on proposals (§0.11–§0.12) | **placed** | 2.2.0, #2106 |
| Phase 1, slice 3: the mechanism, observing every eligible cycle and supplying four seams, inert until approved, with the app-build indicators beside each exposure, the failure-shape sorter and the repeat report (§0.2–§0.10) | **placed** | 2.2.0, #2096 |
| Phase 1, slice 4: the first lesson, drafted by the auditor, and the measurement window, read before 2.2.0's cut (§0.4, §0.12–§0.13) | **placed** | 2.2.0, #2107 |
| Phase 1.5: the correction lane (§13 question 3) | **dropped** | by revision 6 (§5d), which folds it into Phase 1: its observation is slice 3's, its repair seam is wired inert in slice 3, and its capture is slice 1's. A correction-round template waits for a recurring target behavior (§0.4) |
| Phase 2: consolidation and promotion (§8) | **unplaced** | gated on Phase 1's measurement (§8) |

**What closes this SIP:** Phase 1's four slices shipped in 2.2.0 with the window's finding recorded (§0.13), and Phase 2's
gate ruled by the owner on that finding.

## 0. The Phase-1 contract (normative, revision 6)

**This section governs Phase 1.** Revision 6 (2026-10-07) restores the cycle as Phase 1's unit. Revision 5 had
narrowed it to the campaign: it observed only proposal returns, pinned memory only at a campaign's admission, and
supplied it only to proposal writing. §5d records the change, its evidence and who ruled it, and this section is
edited in place so that it stays the one current contract.

Revision 5 (2026-10-06) adopts an external design review of revision 4 and of the 2.2 plan. The review found that earlier sections still read as active requirements and contradict each other:
- the observation seam (§5) against the proposal ruling (§5b);
- the consumer;
- the instrument (§5a, §9);
- the experiment;
- deterministic retrieval against §6's composite scoring;
- admission (`validated` against §5a's `candidate`);
- feedback (§5) against §7's campaign-close update;
- the Phase-2 gate (§8).

Where an earlier section disagrees with this one, this one holds, and the earlier text is marked as superseded where it stands. Who ruled it is §5c, and for revision 6 §5d.

**In one paragraph:**
- **Phase 1 observes every eligible cycle,** a standalone cycle or one inside a campaign. It reads three committed
  records: plan-review rejections, failed correction rounds, and proposal returns. Each is recorded whether or not a
  lesson exists for it (§0.3).
- **It encodes** reflective guidance in project scope. A frontier-model auditor drafts each lesson from the recorded
  evidence, between units, and each is frozen, replay-checked and approved by the owner before any task is given it
  (§0.4, §0.6). Correction rounds are sorted by the failure shape the test runner reported, and a repeat report
  separates repeated shapes from recurring mistakes the auditor has substantiated (§0.4).
- **It supplies approved, applicable pattern revisions at four authoring seams:** plan writing (#2058's call site),
  build authoring (`development.develop`, `qa.test`, `builder.assemble`), repair, and proposal writing
  (`strategy.propose_increment`) (§0.9).
- **Retrieval is deterministic,** from a memory snapshot pinned when the unit of execution is admitted: a standalone
  cycle when it is created, a campaign when it is admitted (§0.7). So a lesson learned inside a campaign reaches later
  units, never a later cycle of the same campaign (§0.1).
- **Counted regression rolls declare memory disabled,** so the regression yardstick does not move (§0.7).
- **Authoring replay is the proving instrument.** The first measured target is a proposal behavior, because the
  proposal gate is the only seam with a recurring target behavior in the record so far (§5b, §0.12).
- **App-build indicators are recorded beside each exposure** (correction rounds, rounds to green, acceptance). They are
  observed, never gating, and **Phase 1 claims no improvement in the built application** (§0.10, §0.13, §9).
- **These stay deferred:** semantic ranking, autonomous promotion and any other payload (§0.14).

### 0.1 What Phase 1 tests

Phase 1 tests whether **retaining and selectively applying reviewed lessons from earlier cycles improves later authoring** under controlled conditions. A frontier-model auditor drafts the lessons from the recorded evidence, between units, and the owner approves each after a replay check (§0.4, §0.6). Observed experience decides which are kept and supplied. Its first measured target is a proposal behavior (§0.4). That is where it is measured first, not what it is (§5d).

**It is cross-cycle learning.**
- Observations are recorded from every eligible cycle while it runs, whether the cycle stands alone or runs inside a
  campaign.
- New guidance never activates within the unit that is running. The unit is a standalone cycle, or a campaign together
  with its cycles and proposals.
- Owner-approved changes apply to cycles and campaigns admitted afterwards.
- **A campaign is provenance and one consumer, not memory's scope** (§7). A lesson learned in a standalone cycle
  reaches a later campaign's matching seam, and one learned in a campaign reaches a later standalone cycle, wherever
  its approved applicability holds.
- Correcting the same output stays with the rungs that already exist:
  - a framing re-roll's rejection context (#669);
  - the failure evidence a repair is handed;
  - a proposal revision's note (SIP-0109 §9.2).
- Unattended learning (evidence-gated activation at a declared boundary, with rollback and measurement) would need its own authorization. It must not emerge from feedback updates.

**When a lesson takes effect, exactly:**
- every eligible cycle contributes observations, standalone or inside a campaign (§0.3);
- what is learned is project-scoped (§0.6);
- a lesson takes effect at the next admission of a unit: a standalone cycle's creation, or a campaign's admission
  (§0.7);
- **within a campaign, a lesson learned from one of its cycles cannot reach a later cycle of the same campaign,**
  because the campaign's snapshot is fixed when it is admitted. Within a campaign, the existing carriers still apply:
  a retry's prior-cycle brief (#1692) and a returned proposal's note (SIP-0109 §9.2);
- this holds in Phase 1. **Activation within a running campaign is deferred** (§0.14): it would need an approval during
  an unattended run, and it would break the comparison of whole campaigns (§0.12).

### 0.2 The domain model

These six are domain concepts, not services or databases:

| concept | what it is | identity |
|---|---|---|
| **observation** | one immutable occurrence from one of §0.3's three sources: a rejected plan, a failed correction round, or a returned proposal, with its classification disposition and evidence | the committed record it projects: the gate decision, the correction round, or the ruling's control-log entry |
| **pattern** | the stable identity of one behavioral lesson | project scope, target behavior (§0.4), task type |
| **pattern revision** | immutable guidance text, applicability and template version, with its drafter (the auditor's model and version) and the observations it cites | pattern and revision number |
| **approval** | the owner's authorization of one revision for a stated applicability | revision and applicability |
| **exposure** | the exact revisions supplied to one authoring invocation at a consuming seam (§0.9), with what was omitted and why | the invocation |
| **assessment** | what was observed for that exposure's targets (§0.10) | the exposure |

They are stored as four records: observations, pattern revisions, approvals, and exposures that carry their assessment.

**The invariant:** a new occurrence adds evidence. It never resets a lesson's history, restores deprecated guidance, or inherits approval for changed content. Re-encoding a historical observation through a new template keeps the observation's identity, so one failure never becomes two pieces of evidence.

### 0.3 Observe

**What is read.** Three committed records, from every eligible cycle, whether it stands alone or runs inside a
campaign. Each is read as a projection from the record that stays authoritative:

| source | the observation | its authoritative record |
|---|---|---|
| **plan review** | a plan-review gate decision that rejects a plan, by a validator or by a person, with its reasons | the cycle's gate decisions (`cycle_gate_decisions`), with the `rejection_record` that names the validators and proofs it refused on (#809) |
| **correction round** | a failed correction round: the failed check, its attribution, and the round's own account of why (`failed_detail`, #2028, #2086) | the run's loop summary (`run_loop_summaries`) |
| **proposal ruling** | a ruling at the increment gate (SIP-0109 §9.4) that returns a proposal | the campaign control log |

**Eligibility.** Some failures say nothing about authoring, and these never become observations:
- a failure in a cycle that declares an injected fault: such a cycle is a diagnostic by construction
  (`capabilities/handlers/fault_injection.py`);
- a failure attributed to the environment (`environment_or_infrastructure_failure`, `cycles/failure_attribution.py`);
- a replay's outputs.

A counted regression roll is observed like any other cycle. Its plan rejections and failed rounds are real.

**The projection's guarantees:**
- only committed, eligible records produce memory;
- a duplicate delivery adds no evidence, pattern or feedback;
- a crash between the record's commit and the projection is recovered by reconciliation;
- a retraction or reclassification keeps the history and marks the guidance that depended on it;
- replay experiments never write to the production corpus;
- **the projection runs beside execution:** its failure never fails, holds or changes a cycle, and reconciliation
  recovers it.

Each projection uses its source's existing durable record. It is not a new service or a distributed transaction.

### 0.4 Classify and encode

**Every observation carries a classification disposition** in its source's own vocabulary, or an explicit
`unclassified` with its rationale and evidence:

| source | its vocabulary |
|---|---|
| plan review | the plan validator that refused the plan, or the manifest gate's proof class: the B1 baseline's vocabulary (`RejectionClassifier`, `cycles/rejection_baseline.py`). A person's rejection carries a class only when its decider records one |
| correction round | the failure's attribution (`AttributionClass`, `cycles/failure_attribution.py`) and the failed check, and beneath them the **failure shape** the sorter matches in the test runner's own message, and the target behavior the auditor substantiates from it (below). An `unattributed` failure is recorded as `unclassified` |
| proposal ruling | a `ProposalClassification` class |

An `unclassified` observation:
- is valid, and for a ruling a valid gate action;
- produces no pattern;
- is counted in coverage reporting;
- enters a taxonomy backlog.

**A rail on proposal returns only.** A proposal return carrying neither a class nor `unclassified` is refused (SIP-0109's
rail, 2.2 plan decision D2). Plan reviews and correction rounds gain no new rail in Phase 1: a person's plan rejection
with no recorded class enters as `unclassified`, and a correction round always carries its attribution. A historical
return whose class is only in prose enters through a reviewed annotation, which keeps both the original ruling and the
annotation's provenance.

**Target behaviors sit beneath each vocabulary.** Each source's vocabulary stays its gate's or its registry's. Where one
class holds different corrections, a reviewed **target behavior** beneath it names one. *Criteria not checkable* holds at
least two:
- a new criterion already satisfied by the accepted application;
- a criterion stating a rule the request does not.

**Phase 1 starts with one supported target behavior:** **a proposed new acceptance criterion is already satisfied by the
accepted application.** Plan reviews and correction rounds have none yet. The 2.0 and 2.1 windows show no recurring
target behavior at either: no plan was rejected, and the four failed rounds at the 2.1 cut were four different defects
(§5b). **A lesson for a plan-review or correction-round target is drafted when the auditor has substantiated one
target behavior recurring across independent cycles,** starting from the repeat report's repeated shapes (below). The
report is read at slice 4's pre-registration and again at the 2.2 cut, and the owner approves what is drafted from it
(§0.6). A class or behavior claimed as supported must have its template, and an unsupported one is disclosed backlog
that never blocks a legitimate return.

**The failure-shape sorter** (the 2.2 plan's D14). A correction round's attribution and check are too coarse to show a
repeat: every failed round in the 2.0 and 2.1 windows failed `tests_pass`, and what went wrong is only in the text of
`failed_detail`. So:
- **a failure shape is an observed signature: what the runner reported, never why.** The sorter establishes no cause,
  as the attribution registry's classes name evidence, never a cause (SIP-0108 §4.2);
- **each runner has a table** of its own failure messages and the failure shape each one identifies. It extends the
  tables the test runner already keeps per runner (`capabilities/handlers/test_runner.py`): the messages that mean a
  suite could not run (`_VITEST_SUITE_BROKEN_MARKERS`, #626) and the shapes a suite raises in its own frame
  (`_OWN_FRAME_SHAPES`, #1130, #1270). It does not start a second table. For example, vitest's
  `Failed to resolve import "…". Does the file exist?` identifies an unresolved import;
- **the correction-round projection applies the table of the runner that ran the suite** to each `failed_detail`
  entry, and records the shape it matches with the table's version. No model sorts. A message no row matches is
  `unclassified` and enters the backlog;
- **a shape sits beneath the attribution, never beside it.** It never maps to an attribution class, so the attribution
  registry (`cycles/failure_attribution.py`) stays the only home of attribution (SIP-0108 §4.2), and the sorter is not
  the parallel taxonomy SIP-0109 rules out for memory. It is coarser than the correction loop's own signature
  (`cycles/correction_signature.py`), which compares one run's rounds by check, file and test: a shape drops the file
  and the test, so the same mistake in another cycle's application still matches;
- the four rounds recorded with `failed_detail` so far (the 2.1 cut, §5b) each carry such a message: an unresolved
  import, an element not found, a mocked function that is not a function, and a spy called with other arguments.

**The auditor establishes the target behavior.** A shape is evidence. The auditor proposes a target behavior and a
corrective lesson only where the failed round's artifacts substantiate them: the suite, the subject files, the repair
it was handed and its result. The same shape can be different mistakes. `is not a function` is the suite's mistake or
the application's depending on whether the application defines the name, which is why the runner's own table carries
`ambiguous_when_app_defines`. A case the artifacts do not settle stays `unclassified`.

**The repeat report.** It counts, by the independent cycles they occurred in, two things kept apart: **repeated
shapes**, which the sorter found, and **recurring target behaviors**, which the auditor substantiated in each case. A
retry and the cycle it retries count once, and a campaign's cycles are named with their campaign. A repeated shape is a
candidate, not a finding. The report is the auditor's input (below), and it is read at slice 4's pre-registration and
at the 2.2 cut.

**Each lesson fills its target behavior's template:**
- the observable defect;
- the corrective action;
- the evidence needed to take it;
- its applicability and exceptions;
- the rubric that assesses recurrence.

For this target, the corrective rule leads to evidence of the intended before-and-after difference against the accepted application. It is not an admonition to write checkable criteria, which already failed (#1947).

**Who drafts a lesson, and what it may use** (the 2.2 plan's D15).
- **A frontier-model auditor drafts each lesson** from the observations and their evidence: the outer loop's model (the
  supervisor in 2.2, the crew once it is commissioned), never the squad's own model judging its own output. This is the
  owner's direction of 2026-09-28: frontier models improve the framework from the evidence of how cycles perform. The
  auditor cites the observations a lesson rests on, and fills its template.
- **It drafts between units, never inside a running one.** No model in a running cycle or campaign writes or changes a
  lesson, and recall and injection stay deterministic (§0.8).
- **A draft is frozen when it is drafted,** as a pattern revision (§0.2): its text, its drafter's model and version, and
  the observations it cites. No task is given it until it is replay-checked and approved (§0.6).
- **The auditor also reads the backlog.** It may propose a new target behavior, or a new row in a runner's table. A new
  row is a code change, reviewed as one.
- Free text stays evidence. It becomes guidance only through a frozen, approved revision.
- The v4 draft's precedence rule (compilation, then security, then function, then performance; §5a) is not applied to any source's classes. Every observed defect is kept as evidence.

**`validated` means admissible, not effective:** the observation has an admissible source, recorded evidence, a supported classification and a valid governed encoding. It says nothing about whether the guidance helps. Source admissibility, the owner's authorization and measured benefit stay distinct.

### 0.5 Provenance

The source is typed, one of three: §5's `gate_decision` for a plan review, a **correction round**, and a **proposal
ruling**.

**Every source carries:**
- the project, and the campaign when there is one;
- the record's identity, and any record that supersedes it;
- the authoring invocation it judged (cycle, run and task), where one exists;
- the criterion and evidence references;
- the classification and template versions.

**And each carries its own:**

| source | it also carries |
|---|---|
| plan review | the gate decision; the decider's identity and type (a validator or a person); the rejected plan, by reference |
| correction round | the round's index; the failed check and its attribution; `failed_detail`, the failure shape with the sorter table's version, and the target behavior with the auditor's substantiation, where one was established; the repair's task, when one was dispatched |
| proposal ruling | the proposal's id and version; the ruling's control-log entry; the decider's identity and type; the accepted application's identity it was judged against |

**What is optional, and what the model fields mean.**
- **The campaign is optional on every source.** A standalone cycle's observations carry none.
- **The cycle id is optional on a proposal ruling only,** because a returned proposal may never create a cycle.
- `origin_mode = cycle` names the execution posture, not a cycle's existence.
- **The origin model is the author's:** the planner's, the build author's, the repairer's or the proposer's. A model
  used in classifying, if any, is recorded separately.

### 0.6 Approval and activation

**What an approval binds.** An approval binds one pattern revision to a stated applicability: project, task type, role, stack and model families. A new approval is needed to:
- change the content;
- widen the applicability;
- add a model family.

**Before approval, a draft is replay-checked:** at its seam, on development cases (§0.11), with and without it, under
§0.12's guardrails. **It is checked together with the approved lessons that would be supplied beside it** under the same
applicability, since a task receives up to three (§0.8): the auditor checks the set for overlap and conflict first, and
the replay runs the combined set. A conflicting set is not approved as it stands: a lesson is revised, narrowed or
withdrawn. The result goes to the owner with the draft, and the approval records it. A draft whose seam has no
captured case waits for one. A lesson can be wrong whoever drafts it: #1947's prompt rule was written once the proposal
mistake had been recognized, and the mistake recurred twice after it (§5b).

**The statuses.**
- Approval to influence execution is distinct from promotion to a broader scope, which is Phase 2's.
- In Phase 1, `status = promoted` (§5) is read as *approved for its stated applicability*, and no other promotion exists.
- A revision approved for model family A is not recalled for family B.

### 0.7 The snapshot, pinned per unit of execution

When a unit of execution is admitted, it pins a memory snapshot, an immutable manifest of:
- the available pattern revisions and their approvals;
- the template versions;
- the retrieval policy and thresholds;
- the applicability rules;
- the ordering and the budgets.

**The unit is one of two:**
- **a standalone cycle,** pinned when the cycle is created;
- **a campaign,** pinned when it is admitted. Its proposals and all its cycles use the campaign's snapshot, so guidance
  never changes between its increments.

**What can change, and when.**
- Every consuming task (§0.9) selects from its unit's snapshot and records its exposure.
- Feedback accrues at once.
- Approval, deprecation, confidence and template changes reach cycles and campaigns admitted later.
- Concurrent units keep their own snapshots.
- A restart reproduces the original selection from the same snapshot and task inputs.

**Memory disabled, declared.** A unit may declare memory disabled when it is admitted: a standalone cycle when it is
created, a campaign when it is admitted, and the campaign's proposals and cycles then follow it. The unit pins no
snapshot, every consuming task records a `disabled` exposure, and its prompts are rendered as if memory did not exist.
A whole campaign declaring it is the memory-off arm of a live confirmation (§0.12). **Its observations are still
recorded** (§0.3). **Every counted regression roll declares it,** written by the
verification-set driver, until the owner rules otherwise on a finding of supported benefit (2.2 plan D12). The regression
set is the framework's yardstick, and an approved lesson must not move it unannounced.

**Emergency revocation** of demonstrably harmful guidance halts or restarts the affected work under a new snapshot, and the affected measurements are explicitly invalidated or set apart. A counted intervention is never changed silently halfway through.

### 0.8 Recall

**Who owns what.**
- **Phase 1's four records are stored in Postgres, beside the cycle registry** (the 2.2 plan's D13). They sit behind
  their own port, with an in-memory adapter for tests and a Postgres adapter in a deploy, selected as the cycle
  registry is (`adapters/cycles/factory.py`). The reasons:
  - recall in Phase 1 is exact filtering (below), so it needs no embedding;
  - each projection must be idempotent and reconciled against its source (§0.3), and the sources
    (`cycle_gate_decisions`, `run_loop_summaries`, the campaign control log) are in the same database;
  - the store stays addressable as a service, the Embodiment Runtime's invariant 2;
  - the nightly verified backup covers Postgres only (`scripts/dev/ops/backup_db.sh`).
- **SIP-042's `MemoryPort` is not Phase 1's store.** Its LanceDB adapter is each agent's own store, embedded in the
  agent's container (`agents/entrypoint.py`), and used today only by console chat. The runtime API, where recall and
  the plan composer run, has none. Phase 2 chooses a similarity index when it adds ranking (§8).
- The recall policy behind `FailurePatternRecallPort` owns eligibility, authorization, snapshot selection, ordering and disclosure.
- The executor is a consumer. Duty and ambient callers will reuse the policy rather than reimplement its trust rules.

**The algorithm:**
1. The authorized project scope, taken from trusted execution context, never from an agent-supplied namespace or replay flag.
2. The pinned snapshot.
3. Eligibility: payload, task type, role, stack, model family, approval. Unknown applicability never means "everywhere"; stack-independent guidance says so explicitly.
4. Deduplication: one revision per pattern, the latest approved in the snapshot.
5. A total order: approval time, then pattern id.
6. Budgets: at most three patterns, and a token budget. A pattern over budget is omitted whole, never truncated.
7. The exposure records what was selected and what was omitted, with reasons.

**Five outcomes stay distinct:** memory disabled, nothing eligible, eligible but omitted by budget, an invalid or incompatible record, and recall failed. Retries are bounded. A failure marks the measurement invalid, and never reads as an empty corpus or a memory-on trial.

**The continuation decision never queries mutable memory** (§7's purity boundary). It may consume ordinary evidence from memory-informed proposals.

### 0.9 Inject

**The recall reaches four authoring seams.** At each it arrives through a managed fragment in its own slot, never in a
within-cycle rung's slot:

| seam | the consuming task types | kept separate from |
|---|---|---|
| **plan writing** | the six plan-authoring types that declare `plan_rejection_context` (#2058's call site, `cycles/task_plan.py`) | a framing re-roll's rejection context (#669) |
| **build authoring** | `development.develop`, `qa.test`, `builder.assemble`, through the same plan-time composer as plan writing (`cycles/task_plan.py`) | a retry's prior-cycle brief (#1692, SIP-0109 §10a) and the manifest's surfaces |
| **repair** | `development.repair`, `development.correction_repair`, `qa.test_repair`, `builder.assemble_repair` | the failure evidence the repair is handed |
| **proposal writing** | `strategy.propose_increment` | a proposal revision's note (SIP-0109 §9.2) |

**Build authoring is where a correction-round lesson is front-loaded.** A lesson learned from failed correction rounds
reaches a later cycle's first authoring of the output, before its check can fail, and not only the repair after the
check has failed. That is §2's correction-lane thesis: about ten prompt lines spent to save one or two correction
attempts. Without this seam, a correction-round lesson could only arrive at a later cycle's second attempt.

**Which task types consume is declared,** on each type's context-assembly contract (`capabilities/context_assembly.py`),
as `plan_rejection_context` is today, never by a branch on the type.

**Current requirements outrank history.** The slot's fragment states that the task's own requirements and the
application's authoritative contracts (the manifest, the accepted application) take precedence over any lesson. A lesson
never overrides them.

**With an empty, unapproved or disabled snapshot, every seam's rendered prompt is byte-identical** to one rendered
without memory.

### 0.10 Assessment and feedback

**What an assessment attaches to.** It attaches to the exact authored output (a plan, a build output, a repair, or a
proposal revision) and its exposure, not to the next gate event or check. A gate's or a check's silence about a target
is not evidence the target is absent:
- the output may be refused for another defect;
- it may carry several defects and record one;
- it may be approved without the target being checked;
- it may avoid the defect by omitting meaningful work.

Each target is assessed by its template's rubric as **present**, **absent after assessment**, **not applicable**, or **unassessed**. Retrieval, injection, assessment and outcome are recorded separately.

**The statistic is `target_absence_rate`,** over applicable, assessed exposures. It replaces §5's `success_rate`. It is observational, not a causal estimate of memory's benefit. Unassessed and inapplicable exposures earn no credit. Aggregation at a cycle's or a campaign's close summarizes assessments, and never overwrites them with cycle success (§7).

**What a recurrence means:**
- Repeated recurrence is a diagnostic trigger, not proof the rule is false. The model may lack the evidence, misread the instruction, or fail to follow valid guidance.
- Invalid guidance and ineffective delivery are told apart.
- Harm is attributed only on explicit evidence.

**Phase 1 has no automatic decay.** Deprecation is the owner's decision on assessed evidence, and takes effect at the next admission of a cycle or campaign. A small, precise policy is preferred to an unsupported confidence formula.

**App-build indicators, observed beside each exposure.** Every exposure, `disabled` ones included, is joined to the
build that its output fed, and the cycle records that build's indicators:
- the implementation run's correction rounds, failed and refunded (`run_loop_summaries`);
- the rounds it took to reach green, or that it did not;
- its acceptance: the run's verdict, and in a campaign the increment's ruling.

**Counted once per build, with its state.** One run feeds many exposures (its plan writing, its build authoring, its
repairs), so the indicators are reported once per distinct build run, never once per exposure. An exposure's build is
in one of four states: built, with its indicators; no downstream build (a returned proposal); pending (an increment not
yet run); or evidence missing. None of the last three reads as a build failure.

These are §9's outcome tier: observed in Phase 1, never gating it. They never enter an exposure's assessment or the
`target_absence_rate`, since a green build says nothing about whether the target was present. Disabled exposures (the
counted regression rolls, §0.7) give a series without memory beside the series with it. The two run different
workloads, so a difference between them is descriptive, never a causal estimate.

### 0.11 The instrument: authoring replay

**What is captured.** An `AuthoringReplayEnvelope` is captured immediately before each consuming seam's authoring task
(§0.9). Revision 5's `ProposalReplayEnvelope` is this envelope at the proposal seam. It contains, or immutably
references:
- the seam and the task;
- the objective or PRD, and the policy;
- the revisions of the accepted application, PRD, manifest and evidence, where they exist;
- the task's actual inputs;
- the within-cycle rung it carries, if any: a re-roll's rejection context, a repair's failure evidence, a retry's
  prior-cycle brief, or a revision's prior proposal and note;
- the complete assembled prompt and its fragment versions;
- the model's identity, version and sampling settings;
- the memory snapshot and the exact intervention;
- the hashes of inputs and artifacts.

The capture is complete, independent of the stored prompt's 10,000-character cut (#1756), or its reconstruction is proven lossless. A historical case whose inputs cannot be verified is diagnostic only.

**Temporal validity.**
- **Every observation and evidence item a lesson rests on predates the target's pre-authoring cutoff,** the moment its
  envelope was captured. An earlier admission of the source unit is not enough: two units run at once, and the one
  admitted first may produce its failure after the other has authored.
- Replaying an output with a lesson derived from its own failure tests assisted repair, not transfer, and is reported
  as that.
- **Two kinds of claim stay apart.** A retrospective replay asks what would have happened had a lesson existed at the
  cutoff: a counterfactual. A prospective claim is about lessons actually approved and in the unit's snapshot when it
  ran. A counterfactual result never reads as a prospective one.

**The cases.**
- Development cases, used to draft the lessons and replay-check them, are separated from held-out evaluation cases
  before any tuning.
- **At each seam, the first authoring of its kind in a later unit is the primary test:**
  - a campaign's first proposal;
  - a cycle's first plan;
  - a cycle's first build authoring of the output the target concerns;
  - a cycle's first repair of the target.
- Revisions, re-rolls and repeat repairs are reported separately, since they already receive a within-cycle rung.

### 0.12 The experiment and its pre-registration

| arm | purpose |
|---|---|
| current baseline | today's prompt at the seam, with its within-cycle rung (a re-roll's rejection context, a repair's failure evidence, a retry's prior-cycle brief, a revision note) and #1947 where it applies, and no cross-cycle memory |
| scoped memory | identical ordinary inputs, plus the eligible historical guidance |
| static guidance (secondary) | the same reviewed guidance under a fixed prompt policy. With one target behavior it differs from scoped memory only where the lesson does not apply, so it measures selectivity, unnecessary injection and token cost |

**What is deferred, and how the runs are controlled.**
- The v4 draft's raw-trace and factual-memory arms (§5a) are deferred.
- The corpus, templates, model settings, policies and rubric are frozen before scored runs, and recorded in an
  **experiment manifest**, each by version or hash: the deployed artifact, the prompts and fragments, the configuration
  (the squad and request profiles), the model settings, the policies, the evaluator (the replay tool and the rubric),
  the PRDs and referenced evidence, and the store's lessons and approvals. Some of these live in the database, not in
  the repository. A change inside the manifest restarts the window under a new one, or is recorded as an intervention
  that sets the affected measurements apart (§0.7). A change outside it is free.
- Arm order is randomized or balanced. Inputs are paired.
- Repeated generations of one case are reported apart from independent cases.
- Any live confirmation assigns treatment at unit boundaries: a standalone cycle, or a whole campaign, because alternating within an evolving campaign carries over through the accepted application.
- Calibration cycles are operational checks, not the comparison.
- An improvement in ordinary inputs (the evidence the author sees, §0.4) is a separately identified change, held identical across arms.

**The pre-registration fixes, before scored runs:**
- the primary target, its seam, and what counts as an eligible opportunity (never defined after seeing an output). The
  target is chosen from the seam whose development corpus holds the most independent cases of one target behavior. On
  the evidence to the 2.1 cut, that is §0.4's proposal behavior. A recurring plan-review or correction-round target found
  by then is a secondary or exploratory comparison;
- the development and test split;
- unique cases, cycles, campaigns and repeated generations, counted separately;
- the unit of analysis and the treatment of campaign and lineage dependence;
- confirmatory and exploratory comparisons;
- the minimum worthwhile effect, and the uncertainty reporting suited to the design;
- the handling of missing assessments and invalid replays;
- the budget cap and the stopping rule;
- the versions of prompts, templates, models, policies and the evaluator, in the experiment manifest;
- the local guardrails:
  - the output still advances the objective;
  - required scope and meaningful criteria remain;
  - other serious defects do not materially increase;
  - context cost stays within budget;
  - memory cannot earn a win with an empty output or by avoiding the requested work.

All outputs, approvals and other returns included, are assessed by one fixed rubric, with evaluators blind to the arm where practical and adjudication recorded. Injected tokens are reported as measured.

### 0.13 Findings and what follows

**The instrument's validity is read first.** An invalid instrument supports no conclusion about memory. A valid one reads one of four findings:
1. **Supported benefit:** a meaningful targeted improvement, adequate evidence, and the guardrails held.
2. **No demonstrated useful benefit:** an informative experiment below the practical threshold.
3. **Harm:** unacceptable regressions caused by the guidance or the system.
4. **Inconclusive:** too few independent opportunities, too much uncertainty, or incomplete assessment.

**The record states eight things separately:**
- the mechanism's correctness;
- the experiment's validity and result;
- the activated patterns, their applicability, and each one's disposition (below);
- the app-build indicators beside the exposures (§0.10), as observation;
- the repeat report: repeated shapes and substantiated recurring target behaviors (§0.4);
- **the next build-side experiment:** its owner, the evidence that triggers it, its comparison, its quality checks and
  its release placement. If no build-side target recurred, the record says so and names when the question is read
  again;
- the auto-gate scope enabled;
- the owner's disposition for the next phase.

**Three results stay distinct:**
- **authoring improvement:** a target behavior's absence in authored output at a seam (§0.10). Phase 1 measures this;
- **delivery reliability:** correction rounds, rounds to green and acceptance (the app-build indicators). Phase 1
  observes this;
- **application quality:** what the built application does, read by Outcome Evaluation's independent scenarios. Phase 1
  does not read this.

**Every activated lesson gets a disposition** when the window closes, recorded with the finding:
- retained, within its tested applicability;
- disabled;
- revised, and sent back for retesting;
- continued in an explicitly bounded experiment: its applicability, its end point, and what ends it.

A harm finding invokes emergency revocation (§0.7). An inconclusive finding may ship the mechanism, but never makes a
lesson's activation permanent by default: a lesson continues only by an explicit disposition. A demonstrated benefit is
still not required to cut.

**What Phase 1 does not claim.** Phase 1 claims no improvement in the built application. Its finding is about one
target behavior's recurrence in authoring.
- **A delivery-reliability claim** (fewer repeated build failures, less repair effort, lower delivery cost) needs a
  recurring build-side target with an approved lesson (§0.4), and a comparison with memory on and off at the build
  seams, read from the replay and the app-build indicators. The counted rolls do not give that comparison while they
  declare memory disabled (§0.7). It does not wait for any later feature.
- **An application-quality claim** needs Outcome Evaluation's independent outcome scenarios: its instruments are placed
  in 2.3 (reporting only) and its feature half in 2.4 (`SIP-Outcome-Evaluation`).
- #557, #949 and #950 are later judgment and decision-record features (the post-retest review, feedback-scoped framing
  revision, the plan-gate review packet). They follow Outcome Evaluation, and no build-side experiment depends on them.

**What a finding does and does not license.**
- A negative result for one class, template, model and workload does not disprove decision, correction, procedural or organizational memory.
- A successful replay does not by itself authorize Phase 2.
- **Phase 2 begins only on the owner's ruling after a valid finding** (§8, amended).

**The corpus is small.**
- **The proposal behavior** has one clean historical case under today's prompt: counted campaign 1's increment 2,
  version 1, with the rule (#1947) stated and the evidence on screen. The source-case inspection (§5e) read the other
  three returns as a missing instruction (the two shakeouts, before #1947) and a missing fact since supplied (version
  2, before #2013). They stay diagnostic. None was captured before authoring.
- **Plan reviews and correction rounds** show no recurring target behavior in the 2.0 and 2.1 windows (§5b).
- **Every eligible cycle after slice 3's deploy adds observations,** the regression rolls included. Only campaigns add
  proposal cases.

So the test corpus is built by the 2.2 line's own cycles and campaigns, and **"inconclusive" is a likely and legitimate
finding** for 2.2.

### 0.14 Deferred, and who owns what

**Deferred:**
- lessons for plan-review and correction-round targets, until the repeat report shows one recurring (§0.4);
- semantic ranking;
- a built-in auditor that drafts lessons inside the product after each cycle (in Phase 1 the outer loop's model
  drafts them, §0.4);
- autonomous promotion;
- organization-wide transfer;
- procedural-success learning;
- duty and ambient write tools;
- generic consolidation;
- activation within a running campaign (§0.1).

Decision records belong to the Design Decision Register and #950 (§5b).

| document or interface | owns |
|---|---|
| SIP-0110 | memory payloads, lifecycle, applicability, approvals, exposure and effectiveness semantics |
| SIP-0109 | ruling events, a campaign's admission point (where its snapshot is pinned), gate authority, escalation and continuation |
| the cycle registry (SIP-0064, SIP-0067) and the correction loop (SIP-0086) | a standalone cycle's creation (where its snapshot is pinned), its gate decisions, and its correction rounds' records |
| this SIP's store, in Postgres beside the cycle registry (§0.8, the 2.2 plan's D13) | the four records, their idempotency keys and their reconciliation |
| SIP-042 | each agent's own semantic store, which Phase 1 does not use |
| the test runner (`capabilities/handlers/test_runner.py`) | each runner's failure-shape table, beside its suite-health markers and its own-frame shapes (§0.4) |
| the replay specification (slices 1 and 2: #2105, #2106) | the pre-authoring envelope, temporal isolation, arm execution and scoring |
| SIP-0088/0089 | persistent identity and mode compatibility |
| the Design Decision Register, #950 | the authoritative decision payload and its lifecycle |

### 0.15 Acceptance matrix

Synthetic fixtures establish the mechanism's behavior. They are never evidence of cross-cycle improvement.

| area | required scenario |
|---|---|
| sources | a standalone cycle and a campaign's cycle each record their rejected plans and failed correction rounds as observations, exactly once each |
| eligibility | a fault-injected diagnostic's failures, an environment-attributed failure and a replay's outputs produce no observation |
| execution isolation | a projection that fails leaves the cycle's outcome unchanged, and is reconciled |
| provenance | a returned proposal with no cycle id, a rejected plan in a standalone cycle with no campaign, and a failed correction round are each encoded and traced correctly |
| idempotency | a duplicate delivery of any source's record does not double-count evidence or feedback |
| recovery | a crash after the record's commit and before the projection is recovered |
| corrections | a reclassification or retraction keeps history and updates dependents explicitly |
| classification | a novel `unclassified` defect is returned without creating a pattern |
| failure shapes | a round's `failed_detail` is sorted by the table of the runner that ran it; the same message gives the same shape on every run; a message no row matches is `unclassified`; no shape maps to an attribution class or records a cause |
| repeat report | a shape in two independent cycles is reported as a repeated shape, and as a recurring target behavior only where the auditor substantiated it in each; a case the artifacts do not settle stays `unclassified`; a retry and the cycle it retries count once |
| lesson provenance | a revision records its drafter's model and version and the observations it cites; an approval records the replay check it was given; nothing in a running unit writes a revision |
| combined guidance | two approved lessons under different pattern ids that conflict under one applicability are caught by the overlap check before approval; the replay runs the set that would be supplied together; the rendered slot states that the task's requirements and the manifest take precedence |
| pattern identity | a repeat occurrence cannot reset or resurrect deprecated guidance |
| approval | new template content or widened applicability requires its own approval |
| model scope | approval for one model family does not apply to another |
| isolation | wrong-project, incompatible-stack and unapproved records are excluded before the budgets |
| determinism | tied timestamps and more than three eligible patterns give a stable selection |
| budget | oversized guidance is omitted explicitly, never truncated |
| unit freeze | feedback, approval or deprecation cannot alter a running cycle's or campaign's snapshot, and a campaign's cycles use the campaign's snapshot |
| transfer | an approved lesson learned in a standalone cycle reaches a later campaign's matching seam, and one learned in a campaign reaches a later standalone cycle, under the same applicability |
| restart | the original exposure is reconstructed after a restart |
| failure disclosure | disabled, empty, filtered and failed recall remain distinguishable |
| inert behavior | at every consuming seam (plan writing, build authoring, repair, proposal writing), an empty or unapproved snapshot leaves the rendered prompt unchanged |
| slot separation | at build authoring, a lesson and a retry's prior-cycle brief render in separate slots, and either one alone renders the other's slot empty |
| memory disabled | a standalone cycle or a campaign declaring memory disabled pins no snapshot, renders byte-identical prompts at every seam (a campaign's proposals and cycles included), records `disabled` exposures, and still records its observations |
| storage | the four records are in the deploy's Postgres, read by the runtime API, and survive every container's recreation |
| feedback | unassessed or partly classified outputs earn no credit |
| app-build indicators | an exposure, a `disabled` one included, records its build's correction rounds, rounds to green and acceptance; a green build leaves the exposure's assessment unchanged |
| indicator aggregation | a run that fed several exposures is reported once; an exposure with no downstream build, a pending build or missing evidence is reported as that, never as a build failure |
| replay fidelity | both arms have identical ordinary pre-authoring inputs, at each seam captured |
| temporal validity | a target cannot learn from its own later failure or from a later unit's evidence; with two units running at once, evidence the earlier-admitted unit produced after the target's cutoff is excluded |
| claim kinds | a replay result is reported as a counterfactual; only an exposure from a live snapshot supports a prospective claim |
| identity | a record carries `agent_id` apart from its role, and a role reassignment leaves `agent_id` unchanged (§6) |
| non-cycle provenance | a record with no cycle (a proposal ruling, a future duty or ambient origin) is valid without a fabricated cycle id (§0.5, §6) |
| recall outside the executor | the recall policy, called through `FailurePatternRecallPort` without the cycle executor, gives the same selection for the same snapshot and inputs (§6) |
| experiment manifest | a change to an input the manifest lists is detected, and restarts the window or is recorded as an intervention; a change outside it does neither |
| experiment isolation | test runs cannot modify production memory or learn from their outputs |
| quality | a target reduction cannot be achieved by omitting meaningful required work |

The identity, non-cycle provenance and recall rows check that the substrate stays open to §6's modes. They implement
no duty, ambient or organization memory.

The auto-review and escalation-queue scenarios are #1708's (2.2 plan §2.2).

---

## 1. Summary

SquadOps ships memory mechanics that nothing uses: `MemoryPort` + LanceDB (SIP-042) is
wired into `BaseAgent` via DI and consumed by no execution path. Meanwhile the 1.4 arc
demonstrated, four separate times, that injecting a known failure class into an authoring
prompt converts a recurring loss into a pass — and every one of those injections was a
hand-built framework patch shipped after a human recognized the recurrence:

| Hand-built injection | What recurred until it shipped |
|---|---|
| `api_behavior_contract` lines (#629) | five authored suite versions asserted 200 where the probe pinned 201 |
| `dom_testid_surface` inventory (#659) | suites invented DOM roles/text the view never promised (fay-6/fay-12) |
| error-contract block in repair prompts (pf-34) | repairs guessed `ApiError(status_code=, detail=)` and 500'd every error path |
| framing rejection context (#669) | re-rolls re-emitted the exact rejected shape (fay-10: same class, all three framings) |

This SIP mechanizes that pattern for failures that recur **across cycles**: observe
rejections and validated failures at deterministic seams, encode them as class-labeled
*behavioral* memories through the existing `MemoryPort`, and recall them into
plan-authoring inputs through the appendix-slot machinery #669 already built — so the
squad stops needing a framework patch per recurring mistake class.

Rung ladder: **#669 = within-cycle** (a re-roll sees this cycle's rejection; shipped in
1.4.1) → **this SIP = cross-cycle** (a new cycle sees prior cycles' rejection classes) →
**organization scope** (Phase 2 promotion, evidence-gated).

The substrate is **mode-neutral by design** (§6): Phase 1 implements the cycle-mode
loop, but the schema, identity model, and port are specified so duty- and ambient-mode
memory utilization (SIP-0089 postures, SIP-0091 duty durability) extends the system
rather than reworking it.

**The thesis, stated once:** this SIP does not build a generic AI memory system. It
builds a *validated organizational learning system* — the value is not that an agent
remembers things; it is that SquadOps can **prove** a learned behavior improved future
execution.

## 2. Justification — the specific cycle-success value

Cycle success today is bounded by two scarce budgets, and recurring known-class failures
tax both:

**The framing lane.** A framing pass on the full squad costs ~45 minutes wall-clock
(shk-1, 2026-08-03: framing-1 ran 16:17→17:04 UTC) — ~25% of the 3-hour cycle budget.
`framing_max_rerolls=2`, so a third rejection is a hard cycle failure. The rejection
classes that consume this budget demonstrably recur across independent cycles with fresh
dice:

- qa-claims-dev-slots: fay-2, fay-10, fay-11, fay-13
- dev-claims-frozen: fay-12 (pre-registered), fay-15 (live)
- doomed command checks: fay-2, fay-4, fay-5
- dual-claimed expected artifact: fay-18 (latent, rode to green), **shk-1 framing-1
  (2026-08-03 — the first roll on the 1.4.1 deploy tripped the same class again and paid
  a full re-roll for it)**

Every one of these rejections after the first is a *known* class re-authored by a squad
with no memory of it. A recalled one-line behavioral warning at framing-1 authoring time
("prior plans in this project dual-claimed a dev test file from the QA validation task;
verification-only tasks declare `expected_artifacts: []` + `criteria_refs`") targets the
rejection before it is authored. Value per prevented recurrence: ~45 minutes of budget
returned, one re-roll of headroom preserved, and the tail risk of re-roll exhaustion —
which is a 0% cycle, not a degraded one — removed for that class.

**The correction lane.** `max_correction_attempts=5` is the scarcest implementation
resource. Recurring emission classes (the ApiError signature guess burned repair chains
across pf-33 *and* pf-34; status-code mismatches burned five suite versions in the #629
loop) consume attempts that novel, genuinely-informative failures then don't get. The
banked 1.4 baseline is 3/5 green (60%) with zero machinery defects — the residual losses
are exactly this category: model emission classes (#627/#628/#629) that recur. Front-
loading a recalled class into first authoring spends ~10 prompt lines to save 1–2
correction attempts; attempts saved on known classes are attempts available for unknown
ones.

**The measurable claim** (hypothesis, not forecast): with rejection memory on, the
recurrence rate of already-labeled rejection classes drops measurably vs. the memory-off
baseline, and saved framing/correction budget converts to a Functional App Yield delta.
§9 defines the measurement; the SIP's phase-1 gate is the recurrence-rate number, scored
against stored plans via the SIP-0101 replay harness plus live rolls.

## 3. Problem

1. **Learning is trapped in artifacts nobody reads.** Plan-validation rejections are
   deterministic, class-labeled, repair-precise teaching text (#658's message names the
   file, the rule, and the consequence) — persisted in `gate_decisions` and, before #669,
   read by nobody. #669 fixed this within a cycle. Across cycles the blindness is intact:
   shk-1 re-tripped fay-18's class on a fresh deploy today.
2. **The alternative to memory is a patch per class.** The four hand-built injections in
   §1 each took a human noticing a recurrence, filing an issue, and shipping a prompt/
   framework change. That loop does not scale with project count and is exactly the
   "collection of independent agents" failure the vision doc names.
3. **Naive memory would make things worse.** CrewAI's reported failure modes — context
   bloat, stale facts poisoning later executions, contradiction accumulation — are what a
   store-everything/retrieve-by-similarity v1 produces. The design below adopts their
   countermeasures (atomic memories, composite scoring, confidence-gated recall,
   consolidation as a first-class operation) and scopes Phase 1 to a seed corpus that is
   deterministic and class-labeled by construction, so encoding quality is not dependent
   on model judgment on day one.

### 3a. Exhibits — the 1.5 shakedown's recurrence evidence (added 2026-08-07)

Two work-product reds from the Gate-2 exit shakedown (shk-6, 2026-08-05/06) are this
SIP's failure classes recurring on a fresh deploy, with the enforcement machinery
verified clean both times:

- **Shadow-store class** (roll-4, the A4 termination's true positive): dev re-implemented
  an in-memory store parallel to the scaffold-owned one, and the correction chain burned
  its budget against a defect class prior cycles had already exhibited — the
  zero-progress chain terminated honestly (`plan_defect`), but nothing *taught* the next
  cycle's dev what the prior one learned.
- **Import class** (wrap-up roll-1): the moving failure chain (collection failure →
  CORS assertion) reprised the unresolved-import family that the #591 pre-gate and #689
  exist for — caught in-cycle, invisible across cycles.

Both are Phase-1 seed-corpus material by construction (deterministic, class-labeled
evidence already persisted in gate decisions and failure analyses). Recorded here so the
acceptance decision weighs live recurrence, not hypotheticals.

## 4. Design principles

- **Behavioral, not factual.** "The `location` field is required" helps only on re-runs
  of one manifest. "You tend to rename interface identifiers — check the manifest before
  emitting" generalizes. Phase-1 encodings state the *tendency and the corrective rule*,
  not the instance data.
- **Mode-neutral substrate, mode-appropriate access.** Agents operate in three postures
  (`mode: ambient | cycle | duty`, SIP-0089), and the memory substrate — schema, store,
  port — must serve all three. What varies by mode is the *access discipline*, not the
  memory model. Nothing in the schema or port may assume a cycle exists (§6).
- **Deterministic seams in cycle mode, not model discretion.** Within cycle execution,
  memory writes happen at fixed pipeline points (gate rejection recorded, cycle
  finalized) and reads at fixed input-construction points (plan authoring, repair
  envelopes later). No agent-invoked `remember()`/`recall()` tools *in cycle-mode task
  execution* — this diverges from CrewAI's design and matches the 1.4-arc lesson that
  every win came from moving judgment out of the dice. It is a cycle-mode discipline,
  not a property of the substrate: ambient- and duty-mode access is agent-initiated by
  nature (§6).
- **Data-only inputs; prose in managed assets** (#448, CLAUDE.md). Recalled memories ride
  task inputs as data keys; the "here is what past cycles got rejected for — revise
  accordingly" prose lives in `src/squadops/prompts/fragments/` assets rendered through
  a template slot, exactly as `rejection_context_section` does today.
- **Memory is cognition, not storage** (CrewAI's core claim, adopted): retrieval is
  confidence-gated and budget-capped, consolidation resolves contradictions rather than
  accumulating them, and forgetting is a scheduled operation, not an accident.

## 5. Phase 1 (normative): cross-cycle rejection memory

One loop, end-to-end, one memory type, one consumer. Phase 1 does **not** implement
generic memory — it implements *recurring failure classes transformed into validated
behavioral guidance*, and the pipeline is typed to make that the only thing that can
flow through it.

**The Phase-1 primitive: `ReflectiveFailurePattern`.** A typed domain model — not a
convention over generic entries — that *serializes into* SIP-042's `MemoryEntry` for
storage (the storage substrate is unchanged; the type lives at the domain layer, per
the constants-not-strings discipline). Generic `MemoryEntry` becomes the future
umbrella: later phases add sibling types (`ProceduralSkill`, `EpisodicEvent`,
`SemanticKnowledge`, `HandoffMemory` — vision §10); Phase 1's encode, recall, and
inject paths accept `ReflectiveFailurePattern` only, so future contributors cannot
assume arbitrary memories flow through the proving loop.

> **Superseded by §0 (revision 5), and restored in §0's form by revision 6 (§5d):** Phase 1 observes rejected plans, failed correction rounds and returned proposals from every eligible cycle (§0.3), each with its source's classification or an explicit `unclassified` (§0.4). The details below are historical: where they differ from §0, §0 holds.

**Observe.** On a plan-validation rejection (gate auto-reject or human gate rejection
with reasons), and on cycle finalize for correction-loop failure classes that carry a
deterministic label (validator-emitted classes only in Phase 1).

**Encode — through a governed template registry, never invented.** The flow is
*validator rejection class → deterministic encoding template → behavioral entry*, with
an explicit abstraction layer in the middle: a per-class template (pattern statement +
corrective rule) that lives beside the prompt fragment assets (#448 discipline) and is
reviewed like any prompt content. Example: class `artifact_claim_conflict` → pattern
"plans tend to assign ownership of produced artifacts to validation roles" + correction
"verification-only tasks declare `expected_artifacts: []`; check ownership against the
producer/consumer split before authoring." The validator supplies the evidence; the
template supplies the generalization; **the memory system invents no patterns in
Phase 1** — a rejection class with no registered template is not encoded (and the gap
is disclosed, not silently skipped). No LLM anywhere in the encode path.

One `ReflectiveFailurePattern` per rejection class occurrence (atomic — one class, one
entry; never a blob of the whole gate decision):

- `namespace`: `project:<project_id>` (Phase 1 *writes* only this scope; the schema
  admits the full ladder from day one)
- `content`: the template-rendered behavioral statement + corrective rule
- `tags`: `rejection_class:<class>`, `task_type:<authoring task>`, `sip:cross-cycle-memory`
- metadata: `owner_role` (role id, never an agent name in source), `agent_id` (nullable —
  the persistent identity per SIP-0088/0089, for agent-scoped entries; null for
  squad-attributed ones), `scope` (`agent | role | project | organization` — the full
  ladder is schema-legal from day one even though Phase 1 writes only `project`),
  `origin_mode` (`cycle | duty | ambient` — Phase 1 writes only `cycle`), `status`
  (`candidate | validated | promoted | deprecated` — **lifecycle trust state,
  orthogonal to origin**: `origin_mode` says where a memory came from, `status` says
  whether it may influence execution; origin does not equal trust. Phase-1 rule:
  validator-sourced, template-encoded entries enter as `validated` — their evidence is
  a deterministic validator firing through a reviewed template, and requiring a
  further validation pass would deadlock the first proving loop; every other source,
  including all duty/ambient-born entries, enters as `candidate`. **Injection, by
  revision 3 (§5a):** only `promoted` entries, approved by the owner, inject into counted
  cycles. `validated` entries inject only in replay experiments, where the proving loop
  runs, so entering as `validated` still does not deadlock it. Decay demotes to
  `deprecated`, which never injects again), `type`
  (`reflective`), `confidence`, `importance`, `reuse_count`, `success_rate`,
  `created_cycle` (**optional** — duty- and ambient-born memories have no cycle),
  `created_campaign` (**optional** — carried when the origin cycle ran under a Campaign,
  per §7; a campaign is provenance and a recall-scoring signal, never a scope),
  `source` (a discriminated provenance union: `gate_decision:<ref>` in Phase 1;
  extensible to duty-handoff, observation, and conversation origins), `summary`.
  (SIP-042's `MemoryEntry` already carries namespace/tags/importance/cycle_id; the delta
  is the scoring/provenance/identity fields.)

> **Superseded by §0.8 (revision 6, the 2.2 plan's D13):** Phase 1's records are stored in Postgres beside the cycle
> registry, behind their own port, not through `MemoryPort`. There is still no new service.

**Store.** Existing `MemoryPort` → LanceDB adapter. No new storage service.

> **Superseded by §0 (revision 5):** the recall algorithm, the snapshot it reads and its disclosure are §0.7–§0.8. The `status` reading here is §0.6's.

**Recall — deterministic filters first; semantic ranking is Phase 2.** Phase 1's
retrieval question is narrow — *has this project previously failed with this class?* —
and class-labeled entries answer it exactly, so Phase 1 recall is a deterministic
filter chain, not a ranking system: project namespace match → task-type tag match →
`status = promoted` in counted cycles, `status ∈ {validated, promoted}` in replay
experiments (§5a) → confidence ≥ threshold → most-recent-per-class →
hard cap on total injected lines (all thresholds config-driven via
`SQUADOPS__MEMORY__*`). This keeps retrieval variance out of the measured lane
entirely — two identical cycles recall identical memories. Embeddings are still
*stored* (the schema keeps `embedding`), so Phase 2 can add composite semantic scoring
(similarity·recency·importance, the CrewAI formula) retroactively over the corpus when
exact class labels stop being sufficient. Zero matches → zero keys → templates render
without the section (presence-keyed, the #639/#643 pattern).

> **Superseded by §0 (revision 5):** the one consumer is `strategy.propose_increment` (§0.9). The plan-authoring call sites stay inert.

**Inject.** New data keys on the four plan-authoring task types (#657's set, merger
excluded — deterministic path stays dry), rendered through a new managed appendix asset
family and a template slot alongside `rejection_context_section`. Within-cycle #669
context and cross-cycle memory context stay *separate slots*: one is "this plan just
died," the other is "plans in this project tend to die this way."

> **Superseded by §0 (revision 5):** feedback attaches to the exact exposure and its assessment, never to the next gate event; the statistic is `target_absence_rate` (§0.10).

**Feedback.** On the next gate decision, update `reuse_count` (recalled entries) and
`success_rate` — defined strictly as **recall effectiveness**: was the *targeted class*
absent from the authored plan? It deliberately does not measure whether the plan or
cycle was good overall (a memory can suppress its class while the resulting strategy is
still poor) — that is **outcome effectiveness**, a later-phase metric (§9). This
telemetry is what Phase 2's promotion gates on — collected from day one, acted on later.

> **Superseded by §0 (revision 5):** Phase 1 has no automatic decay. Deprecation is the owner's decision on assessed evidence, at the next campaign admission (§0.10).

**Decay — the Phase-1 bad-memory protection.** Full consolidation is Phase 2, but bad
lessons must not accumulate in the proving loop: if a recalled entry's targeted class
recurs anyway on K consecutive recalls (config, default small), or its guidance is
implicated in a false-positive rejection, its `confidence` is decremented; below the
recall threshold it stops being injected, and past a floor its `status` moves to
`deprecated` (never injected again, retained for the audit trail). Computed entirely
from the same per-gate feedback above — no new machinery.

## 5a. Revision 3 additions (2026-10-01, from the v4 draft)

The v4 draft (`docs/ideas/cross-cycle-memory-v4-draft.md`) restates most of §5: a typed behavioral
pattern, the governed template registry, the trust lifecycle, deterministic seams and mode neutrality.
Its `VerifiedBehavioralPattern` is this SIP's `ReflectiveFailurePattern`. Revision 3 adopts what is new
in it:
- **A hard applicability gate.** A pattern is eligible only when project, role, task type and stack
  all match. In Phase 1 the eligible are ordered by §5's deterministic chain. Similarity ranking, when
  Phase 2 adds it, ranks only the eligible.
- **A density cap.** At most three recalled patterns per task: the first three in §5's deterministic
  order in Phase 1, and by weighted confidence in Phase 2.
> **Superseded by §0.4 (revision 5):** the precedence rule below is not applied to proposal classes, and every observed defect is kept as evidence.
- **Rejection precedence.** When validators conflict on one run, only the highest-precedence class
  (compilation, then security boundary, then function, then performance) writes a candidate.
- **Origin-model provenance.** Each pattern records the model family it was learned on. In Phase 1, a
  pattern learned on a different family than the cycle's model is not recalled into a counted cycle
  until it is promoted again for that family. Weighting by family is Phase 2's.
- **The context-efficiency measure,** beside recurrence suppression: the tokens injected for a pattern
  against the tokens of the raw trace it replaces.
> **Superseded by §0.11–§0.12 (revision 5):** proposal replay is the instrument, with three arms. The raw-trace and factual-memory arms are deferred, and #1765's convergence replay is not this instrument.
- **The four-arm experiment** as the proving design: no memory, raw trace, factual memory, distilled
  pattern. Its instrument is the **convergence replay harness** (#1765), which already replays stored
  failing rounds per arm. SIP-0101, which v4 named, replays a cycle from a boundary and does not run
  arms.

**Corrected by revision 3:**
- **#571 is closed.** The LanceDB filter-before-limit and similarity defects in §12 are fixed, so the
  prerequisite is met. Phase 1 still verifies recall against the adapter on its own corpus first.
- **The read seam is `plan_rejection_context`** on the live, dispatched execution path. It is not
  `InProcessFlowExecutor`, which v4 named.
- **The corpus.** v4 asks for at least 30 historical failure plans. The plan-gate corpus holds 13,
  none after 2026-08-23 (the placement note above). Phase 1's target is the correction lane (§13
  question 3), where recurrence is live. The jsdom pitfalls behind 1.9's two rejections (#1785) are
  this SIP's motivating class in its current form. **Campaigns are the corpus's source:** the evidence
  package records every failure under the failure-attribution registry's vocabulary, with campaign,
  cycle and increment (`SIP-0109-Campaign-Orchestration.md` revision 2, §14).

**Governance (normative in revision 3; §5's injection rule and recall chain carry it).** Under 2.0's rules, anything that changes how the squad
behaves lands between campaigns, with the owner's approval. That is how the calibration cycle can
still say whether a framework change helped. So:
- **only `promoted` patterns** (owner-approved) inject into counted cycles;
- `validated` patterns inject only in replay experiments, and `candidate` patterns never inject (§5);
- no pattern changes within a running campaign.

v4's case for automation (its §10.3: unattended campaigns must not stall on repeated errors) is answered
in 2.0 by the prior-cycle brief and the crew's outer loop. This SIP's later contribution is to **scope**
those approved corrective rules (the applicability gate) and to **measure** them (recurrence
suppression). Without it, every approved rule goes into every prompt, the bloat v4's §3.1 describes.

## 5b. Revision 4: the Phase-1 re-read against 2.1's evidence (2026-10-06, #1964)

The 2026-09-12 placement asked 2.1 to re-read Phase 1's value hypothesis against the recurrence
evidence of its day, so that 2.2 builds the mechanism against a proving workload that is live. This is
that re-read, on the evidence up to the 2.1 line's final deploy. The cut's own set adds its readings
when it closes (the delivery ledger's row).

**The window:** every cycle created from 2026-10-04 00:00 UTC to 2026-10-06 12:12 UTC, 45 in all:
- 31 on the 2.0 set's deploys: the shakeouts and the counted campaigns of #1908, recorded as framework
  1.9.0 because the version moved at the cut;
- 14 on the 2.1 line's deploys: rebuilds 1 to 4, the final deploy and its diagnostics, recorded as 2.0.1.

Read from the registry (`cycle_runs`, `cycle_gate_decisions`, `run_loop_summaries`,
`campaign_control_log`) and from each framing's `interface_manifest.yaml` in the vault.

| reading | 2.0 set's deploys | 2.1 line's deploys |
|---|---|---|
| framings completed | 24 | 12 |
| cycles with a framing re-roll | 0 | 0 |
| plan reviews approved, of all decided | 24 of 24 | 12 of 12 |
| implementation runs with a failed round | 2 of 24 | 2 of 12 |
| what those rounds failed | `qa.test` `tests_pass`, both | `qa.test` `tests_pass`, both |
| framings whose manifest carried an unresolved design question, of those that authored one | 5 of 9 | 3 of 10 |
| of those, about the runs list's order or pagination | 4 | 3 |
| increment rulings returned for revision, of all decided | 6 of 20 | 0 of 2 |

**What it shows:**

1. **The plan-gate workload is still dormant.** 36 framings, no re-roll, every plan review approved.
   B1's thirteen records (2026-08-10 to 08-23) are still the whole corpus.
2. **The correction lane is not a proving workload yet either.** 4 failed rounds in 36 implementation
   runs, one per run, all the qa suite's `tests_pass`. That is the name of a check, not a class a
   template could generalize: what failed differs per run, and until 2.1 nothing recorded which cases
   failed. #2028 and #2086 record them now (`failed_detail`), so the cut set's rounds are the first
   that could seed a class. Revision 3 named this lane as Phase 1's target (§5a, "the corpus"), and
   the window does not support it yet.
3. **The recurrence that is live is at the campaign's proposal gate.** 6 of 22 increment rulings were
   returned, all on the 2.0 set's deploys, all by the supervisor (#1908 §3a):
   - five were *criteria not checkable* (SIP-0109 §9.4). In four of them a new criterion named
     behaviour the accepted application already had, so its test could not fail before the change
     (§8.2). Shakeout 8's return of that class is what filed #1946. Its fix (#1947) tells the proposer
     the rule, and the class recurred after it in counted campaign 1, at version 1 and again at version
     2. That is §1's pattern: a prompt rule written after a person recognized the recurrence, and the
     class recurring anyway;
   - the fifth stated a rule the request did not, and the sixth was a PRD delta stating more than the
     request carried (#1995's class, classified *ambiguous manifest delta*).

   **The class label is already typed.** The supervisor's reading is a `ProposalClassification`
   (§9.4's five classes), recorded as a `classify` operation in the campaign control log. The two
   counted campaigns' three returns carry one. The three shakeout returns carry the class only in the
   ruling's prose.

   **The within-cycle rung exists, and the cross-cycle rung does not.** A revision of a returned
   proposal is shown the supervisor's note and the version it revises (SIP-0109 §9.2), as a framing
   re-roll is shown its rejection (#669). A new proposal, in the next increment or the next campaign, is
   shown nothing of earlier returns.

   **And the within-cycle rung did not convert this class.** Counted campaign 1's version 2 was shown
   version 1's return, which named the criterion, and it was returned for the same class, on two other
   criteria. So neither a prompt rule nor the returned note converted it. That is evidence against an
   easy win, and it is why the measurement decides Phase 1's value, not this re-read.
4. **Also recurring, and not Phase 1's.** 7 of the 8 unresolved design questions asked how the runs
   list is ordered or paged, on the same PRD. The plan gate answered each time, and the next roll asked
   again. These are decisions about the app under build:
   - §11 excludes them from Phase 1;
   - the Design Decision Register proposes decision records as memory's first payload (its §5), and the
     portfolio folds that register into #950 (Q12, 2.4 or later);
   - in the regression rolls they come from the fixed PRD, which is the yardstick and does not change.

   The boundary: this SIP owns the substrate (the portfolio's Q4), and a decision-record payload arrives
   with the register's home.

**Proposed in this revision, and accepted with it:**
- **Phase 1's proving workload is the proposal gate.**
  - Observe: an increment ruling returned with a `ProposalClassification`.
  - Encode: one governed template per class, so no LLM and no invented pattern (§5's rules,
    unchanged).
  - Recall into: `strategy.propose_increment`, the one task that authors a change request. That is one
    consumer, as §5 requires.
  - Scope: `project`, with `created_campaign` provenance (§7), so a class returned in one campaign
    reaches the next campaign's proposer.
- **A classified return enters as `validated`,** as a validator's firing does (§5). Its class comes
  from a closed vocabulary, recorded by the gate's decider, and is encoded through a reviewed template.
  Entering as `candidate` would deadlock the proving loop, which is §5's reason for the validator rule.
  It still injects into a counted cycle only once the owner promotes it (revision 3).
- **The plan-gate path stays specified and wired.** #2058's call site on the six plan-authoring task
  types stays. Its corpus is empty, so it injects nothing. It is not the proving workload.
- **§13 question 1 is answered for classified rulings.** A return by the supervisor or the owner that
  carries a `ProposalClassification` is class-labeled at its source, so it enters Phase 1's corpus
  through its template. A reason with no class still waits for Phase 2's encode.
- **The correction lane stays Phase 1.5** (§13 question 3). It is read again when `failed_detail` holds
  failures of more than one shape.
- **Revision 3's governance is unchanged.** Only promoted patterns, approved by the owner, inject into
  counted cycles, and nothing changes within a running campaign.

**What the re-read does not settle:**
- **The instrument.** §9's primary metric is the recurrence rate, memory-on against memory-off. The
  increment replay (#1959) starts from an approved increment's seeds, after the gate, so it does not
  replay a proposal run. Either a proposal-run replay, with and without a pattern, is Phase 1's first
  slice, or the measurement is live only. The 2.2 plan decides which.
- **The sample.** Six returns in one window is a small corpus, and two of them came before #1947. The
  measurement window's N is declared before rolling (§9).
- **The interaction with #1708's auto tier,** which lands in the same release and reads the same
  ledger. A proposal the auto tier approves is never classified, so a class the supervisor would have
  returned goes unobserved. The 2.2 plan sequences the two.

**The cut's readings (2026-10-07, #1964 at the 2.1 cut).** These are the 12 cycles on the 2.1 final deploy (`fcc7ce04`):
the diagnostics' campaigns, the cut's shakeout campaign and the four counted rolls.
- **The plan gate:** no framing re-roll, and all 11 plan reviews approved. Eight were approved by the system with no
  open question. Three answered how the runs list is ordered, the §5b item 4 class again.
- **The correction lane:** 4 of 11 implementation runs had one failed round, all `qa.test` `tests_pass`. Each recorded
  its reason (`failed_detail`, #2028, #2086), and the four are four shapes, all in the React frontend suites:
  - a mock asserted with the wrong arguments;
  - an unresolved relative import;
  - a test id not found;
  - a misused mock.

  None recurred, and each was repaired in one round. Phase 1.5's condition, failures of more than one shape, is now
  met, and nothing in this window recurs.
- **The proposal gate:** 4 increment rulings, all approved at version 1. **The whole 2.1 line returned no proposal.**
  The recurrence §5b measures is the 2.0 window's six returns, so the corpus note in §0.13 stands: the test corpus is
  built by 2.2's own campaigns.

**The re-read's conclusion stands:** Phase 1's proving workload is the proposal gate, and its value is measured, not
assumed.

> **Revision 5 settles all three, and narrows one rule above.** The instrument is proposal replay (§0.11). The sample is
> pre-registered, with "inconclusive" a legitimate finding (§0.12, §0.13). The auto tier stays off increment rulings through
> the measurement window (the 2.2 plan, D3). And templates are written per **target behavior** beneath a class, not per
> class (§0.4).

> **Revision 6 (§5d) reads this conclusion as where Phase 1 is measured first, not what Phase 1 is.** The proposal gate
> stays the first measured target. Every eligible cycle is observed, and plan writing, build authoring and repair are
> consuming seams beside proposal writing. The cut's readings above also met Phase 1.5's condition, so the correction
> lane joins Phase 1. "No LLM" in the encode step above is replaced: a frontier-model auditor drafts each lesson,
> frozen, replay-checked and approved before use (§0.4, §0.6).

## 5c. Revision 5: the external design review adopted (2026-10-06)

**What changed.** §0 is new and normative. Each passage it contradicts is marked as superseded where it stands. The
substance:
- **one current contract**, replacing implicit override by the latest amendment;
- **the activation boundary**: Phase 1 is cross-campaign learning, and guidance never changes within a running campaign;
- **six domain concepts**, with the invariant that a new occurrence adds evidence and never resets or resurrects a
  lesson;
- **`validated` as admissibility only**, with an explicit `unclassified` disposition;
- **target behaviors beneath `ProposalClassification`**, one supported in Phase 1;
- **a campaign snapshot** pinned at admission;
- **typed proposal-ruling provenance**, with approval bound to a revision and its applicability, model families
  included;
- **a complete recall algorithm**: a token budget, five distinct dispositions, and scope taken only from trusted
  context;
- **an idempotent projection** from the campaign control log;
- **assessment per exposure** in place of next-ruling success, with no automatic decay;
- **replay from a capture taken immediately before authoring**, with temporal validity and a development/test split;
- **three arms**, a pre-registered decision rule with local guardrails, and **four findings**;
- **the cross-SIP responsibilities** and an acceptance matrix.

**The evidence.**
- The review read revision 4 and the 2.2 plan and named each contradiction. Each was confirmed against this text
  before adoption:
  - §6's "composite-scored" against §5's deterministic chain;
  - §5a's precedence `candidate` against §5b's `validated`;
  - §5a's four arms against §5b's on/off;
  - §5's decay against §5a's no-change rule;
  - §8's "in hand" against the plan's "lowers recurrence".
- The review also caught that the plan's D1 set the replay's boundary at the ruling rather than before authoring.
- The corpus note in §0.13 is the supervisor's addition: three independent historical cases of the target behavior.

**Who ruled it.** The owner supplied the review on 2026-10-06 and asked which points were worth incorporating. The
supervisor recommended adopting them as specification, with four additions to the build (the snapshot, exposure
records, pre-proposal capture and the replay), and proposed writing them into this PR with the release shape the
owner chose. The owner chose shape B ("go with B"): 2.2.0's cut waits for the bounded measurement window's finding
(the 2.2 plan §3). This revision is reviewed with the plan in the same PR, and its merge is the acceptance.

> **Amended by revision 6 (§5d):** the activation boundary is the unit of execution, a standalone cycle or a campaign,
> and the snapshot is pinned at that unit's admission. "Cross-campaign learning" above is revision 5's wording, and the
> owner had not ruled on it.

## 5d. Revision 6: the cycle restored as Phase 1's unit (2026-10-07)

**What changed.** Revision 5 made the campaign Phase 1's unit:
- it called Phase 1 "cross-campaign learning";
- it pinned the snapshot only at a campaign's admission;
- it observed only proposal returns, and marked the plan-review and correction-round observations historical;
- it supplied memory only to proposal writing.

A SIP named and argued as cross-cycle memory became campaign memory. §1 states the problem as "failures that recur
**across cycles**", and its rung ladder runs within-cycle (#669), then cross-cycle, then organization. Under revision 5
a standalone cycle recorded nothing and received nothing.

**Revision 6 restores the cycle as the unit, in §0's form:**
- **observation from every eligible cycle,** standalone or inside a campaign, from three committed records:
  - rejected plans;
  - failed correction rounds;
  - returned proposals.

  Each carries its source's classification or an explicit `unclassified` (§0.4) and typed provenance (§0.5). The
  projection runs beside execution and never changes a cycle (§0.3);
- **eligibility:** fault-injected diagnostics, environment-attributed failures and replays produce no observation (§0.3);
- **the snapshot pinned per unit of execution:** a standalone cycle when it is created, a campaign when it is admitted
  (§0.7);
- **memory disabled, declared:** counted regression rolls declare it, pin no snapshot, and still record their
  observations (§0.7);
- **four consuming seams:** plan writing (#2058's call site), build authoring, repair, and proposal writing, each in
  its own slot and each byte-identical while nothing is approved (§0.9);
- **app-build indicators beside each exposure,** observed and never gating, and a statement that Phase 1 claims no
  improvement in the built application (§0.10, §0.13);
- **authoring replay:** one envelope type, captured before each consuming seam (§0.11). The first measured target stays
  the proposal behavior, and the pre-registration fixes it (§0.12);
- **the correction lane joins Phase 1:** its observation and its repair seam are Phase 1's, and its template waits for
  a recurring target behavior (§0.4). The ledger's Phase 1.5 row is dropped by this revision;
- **storage in Postgres, beside the cycle registry** (§0.8, the 2.2 plan's D13), in place of SIP-042's `MemoryPort`;
- **a campaign may declare memory disabled,** as a standalone cycle may, so that a live confirmation can assign the
  memory-off arm to a whole campaign as §0.12 requires (§0.7);
- **a frontier-model auditor drafts the lessons** (§0.4, the 2.2 plan's D15), in place of "people write the templates"
  and "no LLM in the encode path". Each draft cites its evidence, is frozen, is replay-checked on development cases and
  is approved by the owner (§0.6). Nothing in a running unit writes a lesson. A built-in auditor stays deferred (§0.14);
- **the failure-shape sorter and the repeat report** (§0.4, the 2.2 plan's D14): each runner's table of its
  own messages, extending the test runner's existing per-runner tables, sorts a correction round's `failed_detail`
  into a target behavior beneath its attribution, and the report counts each target behavior by independent cycles;
- **nine changes from review feedback the owner supplied before adoption:**
  1. the record names the next build-side experiment, or records that no build-side target recurred and when that is
     read again, and keeps three results apart: authoring improvement, delivery reliability and application quality
     (§0.13);
  2. the application-quality dependency is Outcome Evaluation's independent scenarios (instruments 2.3, feature half
     2.4), and a delivery-reliability claim waits for no later feature (§0.13);
  3. temporal validity is read by evidence time, not admission time, with a test for two units running at once, and
     counterfactual replays stay apart from prospective claims (§0.11);
  4. every activated lesson gets a disposition when the window closes, and an inconclusive finding never makes an
     activation permanent by default (§0.13);
  5. a draft is checked with the lessons that would be supplied beside it, and the task's requirements and the manifest
     take precedence over any lesson (§0.6, §0.9);
  6. a failure shape is an observed signature, never a cause; the auditor substantiates the target behavior from the
     round's artifacts, and the repeat report keeps repeated shapes apart from recurring target behaviors (§0.4);
  7. when a lesson takes effect is stated exactly, including that a lesson learned in a campaign cannot reach a later
     cycle of the same campaign; activation within a running campaign is deferred (§0.1, §0.14);
  8. the window's freeze is an experiment manifest of every input, some of them in the database, not a rule about which
     directories may change (§0.12);
  9. acceptance rows for identity, non-cycle provenance, recall outside the executor, indicator aggregation and the
     indicator states (§0.10, §0.15);
- **the acceptance matrix** gains rows for sources, eligibility, execution isolation, unit freeze, transfer, memory
  disabled, slot separation, the app-build indicators, storage, failure shapes, the repeat report, lesson provenance,
  combined guidance, indicator aggregation, claim kinds, identity, non-cycle provenance, recall outside the executor
  and the experiment manifest (§0.15).

**What did not change:**
- **governance:** the owner approves each revision for a stated applicability, and nothing changes within a running
  unit. Who drafts a lesson changed (above);
- deterministic recall and its budgets;
- per-exposure assessment, with no automatic decay;
- the three arms and the four findings;
- the purity boundary (§7);
- release shape B (the 2.2 plan §3).

**The evidence.**
- **The narrowing confused where Phase 1 is measured first with what Phase 1 is.** §5b chose the proposal gate as the
  proving workload, because it was the only seam with a recurring target behavior: 6 of 22 increment rulings returned,
  all on the 2.0 set's deploys. Revision 5 then wrote that workload into the contract's unit, its snapshot and its
  sources. Nothing in the evidence called for that:
  - §7 had already ruled "campaign is provenance, not scope";
  - §6's first constraint keeps the schema free of a cycle assumption so that memory is not tied to one mode.
- **The reason for the narrowing weakened at the 2.1 cut.** The whole 2.1 line returned no proposal, and the cut's
  correction rounds met Phase 1.5's condition, failures of more than one shape (§5b, the cut's readings).
- **Campaign-only memory leaves cycles out.** The regression rolls, the diagnostics and any operator's standalone cycle
  run outside a campaign. Under revision 5 none of them recorded anything.
- **One property revision 5 had by accident is kept on purpose.** Counted regression rolls received no memory only
  because they run no proposals. Revision 6 makes this a declaration, memory disabled, so the regression yardstick does
  not move when the first lesson is approved.
- **Build authoring was missing from the first draft of this revision.** The owner asked what cross-cycle memory
  produces in the quality of the application the squad builds. Read against that question, the draft supplied memory
  everywhere except the tasks that write the application:
  - plan writing shapes the plan, and proposal writing shapes what is built next;
  - repair arrives only after a check has failed.

  §2's correction-lane thesis is front-loading into first authoring, and the draft had no seam for it. The same reading
  found that nothing in Phase 1 would record what happened to the build: §9 keeps outcome effectiveness out of Phase 1's
  gate, and the counted rolls run with memory disabled. Hence the build-authoring seam, the indicators beside each
  exposure, and the explicit statement of what Phase 1 does not claim (§0.13). On the evidence to the 2.1 cut, none of
  this is likely to show an effect in 2.2: the counted set passed 4 of 4 with one correction round across the set, and
  the cut's four failed rounds were four different defects (§5b).
- **The store revision 5 named could not serve Phase 1.** §0.8 said `MemoryPort` owns storage, and the plan's slice 3
  named its LanceDB adapter. Reading the code for the owner's question about agent and squad memory found that the
  adapter is created inside each agent's container (`agents/entrypoint.py`, at `/app/data/memory_db`) and used only by
  console chat (`adapters/comms/chat_executor.py`). Recall runs in the runtime API (`api/runtime/main.py`,
  `adapters/cycles/run_provisioning.py`), which has no such store. Placing it in one agent's container would break the
  Embodiment Runtime's invariant 2, and a new store in the runtime API would need a compose change and sit outside the
  nightly backup, which covers Postgres only. The same reading found three agents with no volume for their own store
  (#2112).
- **A review of this revision's text,** asked for by the owner before kickoff, found four places still written for one
  seam or one unit: the exposure's definition (§0.2, "one proposal invocation"), the origin model (§0.5), what an
  assessment attaches to (§0.10), and the memory-disabled declaration, open to a cycle only while §0.12 assigns live
  treatment to whole campaigns (§0.7). Each is corrected in place.
- **Correction rounds could not show a repeat.** Their vocabulary is the attribution (ten classes) and the failed
  check, and every failed round in the 2.0 and 2.1 windows failed `tests_pass` (§5b). What went wrong is only in the
  text of `failed_detail`, so "one target behavior recurring across independent cycles" (§0.4) could only be read by
  hand, and the build-authoring and repair seams would stay inert by construction. The four rounds recorded with
  `failed_detail` each carry one test-runner message that names its defect, and two of the four are families the
  framework once fixed by hand: an import the suite cannot resolve (the frozen surface,
  `capabilities/context_assembly.py`, roll 9) and an element the page never renders (#659).
- **The sorter was first placed with each stack's declarations** (`capabilities/stack_*.py`). Surveying the other SIPs
  for their effect on memory found that the test runner already keeps per-runner message tables, and SIP-0105 names
  per-runner output signatures as a stack declaration. So the sorter extends the runner's tables, and stays beneath the
  attribution registry (SIP-0108 §4.2) (§0.4).
- **"People write the templates" did not describe how the project works.** The supervisor, which would draft them, is
  a frontier model, and the owner's direction of 2026-09-28 has frontier models improve the framework from evidence,
  while the squad's own model does not yet. What the rule protected is kept: a lesson is fixed before it is used,
  tested before any task is given it, and approved. A lesson can be wrong whoever writes it (§0.6, #1947).
- **Two passages this revision carried were wrong, and the feedback found both.**
  - §0.13 called #557, #949 and #950 "Outcome Evaluation's measures". They are the post-retest review (#557),
    feedback-scoped framing revision (#949) and the plan-gate review packet (#950), which follow Outcome Evaluation
    (the portfolio's Q2). Outcome Evaluation's own target is instruments in 2.3 and its feature half in 2.4.
  - The plan held prose merges harmless during the window "because the drift check reads only `src/` and `adapters/`"
    (`scripts/dev/verification_set_driver.py`, `framework_drift_problems`). The experiment also depends on the PRDs
    (`examples/`), `config/`, the deploy's model settings and the replay tool (`scripts/dev/`). The squad profile and,
    under D13, the lessons and approvals live in the database, where no merge rule reaches.
- **§0.11's admission rule let a replay use the future.** Two units admitted in order can fail out of order, so a lesson
  from the earlier unit could rest on evidence produced after the later unit authored.

**Who ruled it.** The owner, 2026-10-07, on the supervisor's overview of the 2.2 plan:
- "are memories captured after each cycle of a campaign as well; and also outside the scope of a campaign. I just want
  to ensure that campaigns are not the only mechanism to persist cycle memories";
- then "but this is cross cycle memory; not cross campaign memory. Just not clear why this turned into a campaign memory
  system".

Revision 5's campaign framing was the supervisor's recommendation in adopting the external review (§5c), not a ruling of
the owner's. The supervisor proposed this revision's shape. The owner asked for it to be drafted ("yes, draft revision 6
and the plan re-scoping"). The owner then asked "what does cross cycle memory produce in terms of output quality of the
target app build", and on the supervisor's answer asked for the build-authoring seam, the indicators and the statement
of what is not claimed to be added ("yes, add those three"). On the supervisor's account of how agent and squad memory
work, the owner asked for the storage decision to be added ("yes, add the Postgres decision to 2111"), and for a full
review of the PR before kickoff. On the review, the owner asked what "people write the lessons" meant, answered "who
better to determine the lesson than the AI auditing everything", and asked for the auditor and the sorter with its
report ("yes, make both changes in 2111"). The owner then supplied review feedback of nine points and asked "are these
worth considering?". The supervisor recommended all nine, and named point 7 as the owner's choice, since it states a
limit of campaigns. The owner asked for all nine ("yes, add all nine to 2111"), with point 7 as presented: lessons are
frozen within a campaign in 2.2, and activation within a running campaign is deferred. It is reviewed with the plan's
re-scoping in one PR, and its merge is the
ruling.

## 5e. The source-case inspection (2026-10-08, slice 1, #2105)

**What changed.** §0.13's corpus note. "About three independent historical cases" becomes **one clean case under
today's prompt**. The full inspection is posted on #2105. For each of the four returns it read the proposal, the
ruling, the proposal block the proposer was given (which carries the accepted manifest verbatim), and the deploy's
templates at its commit:

| case | deploy | the evidence on screen | what failed |
|---|---|---|---|
| shakeout 7, v1 (T2) | rebuild 19, before #1947 | partly: the criterion held only because the FastAPI stack's frozen request models ignore an undeclared field, which no convention said | a missing instruction, and one missing stack fact |
| shakeout 8, v1 (T3) | rebuild 20, before #1947 | yes: the manifest says the app excludes capacity limits | a missing instruction |
| counted campaign 1, increment 2, v1 (T2) | rebuild 22, with #1947 | yes, in full: the manifest declares `capacity` and `capacity_reached` | faulty reasoning. The proposal's empty `manifest_delta` and tests-only footprint show it registered the declaration |
| counted campaign 1, increment 2, v2 (T3, T4) | rebuild 22, without #2013 | no: trimming is the frozen models' `NonBlankStr` | missing information, since supplied by #2013 (#1962) |

**What follows.**
- The lesson targets reasoning, not access and not the rule. In the clean case the rule was stated and the evidence
  was on screen, so restating either repeats #1947. The corrective action is a comparison step: for each new
  criterion, name the element of the accepted manifest that makes it fail before the change.
- §5b's reading that the class "recurred after [#1947] in counted campaign 1, at version 1 and again at version 2" holds
  for version 1 only. Version 2 was a missing fact.
- One evidence-access gap remains: the FastAPI stack's undeclared-field convention. It is #2114, fixed as a separately
  identified change before the window (§0.4).
- "Inconclusive" is more likely than §0.13 first said. The window's corpus comes from 2.2's own campaigns.

**Who ruled it.** No ruling changes. The inspection is slice 1's first deliverable, built under the 2.2 standing
authority (the 2.2 plan §5). It corrects a count and records evidence.


## 6. Mode neutrality: cycle, duty, and ambient utilization

Phase 1 implements the cycle-mode loop, but the substrate is designed so duty- and
ambient-mode utilization is an *extension*, never a *migration*. (Revision 5 reads this as a promise of versioned
evolution through reusable interfaces, not a guarantee that no stored record ever migrates.) Binding constraints on
Phase 1's implementation (normative), with the utilization sketch they exist to permit:

**Constraints Phase 1 must honor:**

1. **No cycle assumption in schema or port.** `created_cycle` is optional, `origin_mode`
   is first-class, and provenance is a discriminated union — a memory formed during a
   duty window or ambient observation is schema-legal without a fake cycle ref.
2. **Identity is carried, not inferred.** `agent_id` (persistent identity, SIP-0088/0089)
   travels on every entry alongside `owner_role`. An agent-scoped memory survives role
   reassignment and squad recomposition; collapsing agent into role in the storage key
   would corner exactly the identity-memory future this section protects.
> **Revision 5:** Phase 1's recall is deterministic (§0.8), not composite-scored. Item 3's point, recall as a port-owned policy any mode can call, stands.

3. **Recall is a port operation, not an executor feature.** The composite-scored,
   confidence-gated recall of §5 lives behind `MemoryPort`, callable from any mode. The
   executor's plan-authoring seam is Phase 1's *consumer*, not the recall API's owner.
4. **Access discipline is a per-mode policy, not a substrate property.** Cycle mode:
   seam-mediated only (§4). Duty and ambient modes: agent-initiated recall/remember
   through the same port is the intended shape — there is no deterministic pipeline seam
   in a duty window waiting on events (SIP-0091) or in ambient presence, so discretionary
   access is not a compromise there; it is the only coherent design.

**Utilization sketch (non-normative, later phases):**

- **Duty mode:** a duty agent recalls its own agent-scoped and project-scoped memories at
  window start; duty handoff (the Duty-Continuity/Handoff-Ledger draft) is a natural
  encode/recall pair — the outgoing agent's handoff summary is an encode, the incoming
  agent's context load is a recall. Temporal owns duty durability (SIP-0091); memory owns
  what the duty *learned*.
- **Ambient mode:** ambient agents accumulate observations as agent-scoped candidate
  memories via agent-initiated `remember()`.
- **The quarantine rule (design stance, review-confirmable), generalized by the
  lifecycle `status` dimension (§5):** what may influence execution is governed by
  `status`, not by origin — **origin does not equal trust** (a cycle-generated memory
  can be wrong too). Duty/ambient-born memories enter as `candidate` and do **not**
  reach cycle-mode recall until promoted through Phase 2's evidence gates;
  validator-sourced cycle-born entries enter as `validated` (their evidence is a
  deterministic validator firing through a reviewed template); decay can demote any
  entry to `deprecated` regardless of where it came from. Cycle execution is the dice
  we measure; letting unvetted observations into authoring prompts would reintroduce
  the nondeterminism the 1.4 arc spent a release removing. Ambient/duty agents may
  freely recall *validated* project memories; the gate is on what flows *into* the
  measured lane, not out of it.

## 7. Campaign interaction

Campaign Orchestration (v2.0's headline since 2026-09-12; revision 2 makes a campaign evolve one app;
this SIP's Phase 1 follows in v2.2) is the sharpest consumer of cross-cycle memory: `repair`/`retry`/`fork` continuations create
back-to-back cycles pursuing one objective, where the prior cycle's failure classes are
maximally relevant and the recurrence metric takes its tightest form (did the class
recur *within the campaign*?).

Design decisions this implies:

- **Campaign is provenance, not scope.** Memories born in a campaign must outlive it —
  organizational learning would be defeated by campaign-lifetime memories. `created_campaign`
  rides the metadata; recall scoring may boost same-campaign provenance (the "this
  objective's own history" signal); the scope ladder (§5) is unchanged.
> **Revision 5:** campaign-close aggregation summarizes assessments and never overwrites them with cycle success (§0.10). Campaign close is one mode's consolidation trigger; duty and ambient memory will need their own.
> **Revision 6:** this bullet is now §0.1's rule. A campaign is provenance and one consumer, and Phase 1's unit is the cycle (§5d). A standalone cycle's close is a consolidation trigger too.
- **Campaign close is Phase 2's consolidation clock.** Consolidation and success-rate
  updates need a deterministic trigger; cycle-end is too frequent and wall-clock is
  arbitrary. Campaign disposition — the final continuation decision — is the natural
  batch point: reflect over the campaign's accumulated evidence (SIP-0096
  `CycleOutcome` roll-ups), consolidate per-class entries, update `success_rate` from
  the outcome trajectory. This instantiates the idea doc's reflection pipeline
  (Execution → Audit → Reflection → Extraction → Consolidation) at a real runtime seam.
- **The purity boundary (binding constraint):** memory is **never** an input to the
  campaign continuation decision. The Campaign SIP specifies that decision as a pure
  function of (objective, policy, accumulated evidence, latest outcome) — the
  reserve-buffer-guard pattern. Memory improves *how the next cycle authors*; the
  campaign decides *whether and what to launch*. Coupling them would make the
  continuation decision non-replayable and structurally entangle the two SIPs — and it
  would open a self-reinforcing loop: past failures bias the continuation decision,
  biased continuation reduces new experiments, and reduced experimentation reinforces
  the original belief. Keeping campaign control deterministic preserves replayability
  and measurement integrity.

## 8. Phase 2 (design-sketch, separately gated): consolidation and promotion

- **Consolidation** — CrewAI's genuine differentiator: on encode, similarity-search for
  related entries; on contradiction, update-or-delete with provenance preserved (never
  two competing facts). Scheduled forgetting/summarization for entries with low
  reuse_count past a config horizon.
- **Promotion** agent→project→organization, gated on observed `reuse_count`,
  `success_rate`, and audit validation — using Phase 1's telemetry, not judgment.
- LLM-assisted encoding for failure classes that lack a validator label (correction-loop
  behavioral classes), behind the same schema.

> **Revision 6:** Phase 1's lessons are drafted by a frontier-model auditor, between units (§0.4). Phase 2's part is a
> built-in auditor that drafts inside the product, and approval on measured evidence (promotion).

Phase 2 does not begin until Phase 1's recurrence-rate measurement is in hand. **Amended by revision 5 (§0.13):** it begins only on the owner's ruling after a valid finding, which may be any of the four. Later consolidation keeps disputed, superseded and differently scoped claims with their evidence, never deletes history to resolve a contradiction, and does not equate low reuse with low value.

## 9. Success metrics (measured, not aspirational)

Two tiers, deliberately separated — a memory can suppress its targeted class while the
overall result stays poor, so conflating them would let recall wins masquerade as
outcome wins:

> **Revision 5:** the metric's statistic is `target_absence_rate` over assessed exposures (§0.10); the instrument, arms and pre-registration are §0.11–§0.12; and Phase 1 keeps local non-regression guardrails, so "never gates Phase 1" below holds for Functional App Yield, not for the guardrails (§0.12).
>
> **Revision 6:** the outcome tier is observed through the app-build indicators recorded beside each exposure (§0.10): correction rounds, rounds to green and acceptance. Phase 1 claims no improvement in the built application (§0.13).

**Recall effectiveness (Phase 1 measures this; gates the phase):**
1. **Primary:** recurrence rate of labeled rejection classes, memory-on vs. memory-off
   (revision 4: on the proposal gate the classes are `ProposalClassification`'s, and the 2.2 plan
   chooses the instrument, §5b)
   — scored against stored plans via the SIP-0101 replay harness and over a
   pre-registered set of live rolls (FAY methodology; N declared before rolling).
2. Injection cost: prompt lines added per authoring task (must stay under the cap;
   context bloat is a regression, not a side effect).
3. Retrieval usefulness: `reuse_count`/`success_rate` distributions, decay/deprecation
   counts (Phase 2's promotion evidence).

**Outcome effectiveness (observed in Phase 1, measured later — never gates Phase 1):**
4. Framing re-rolls consumed per cycle (memory-on vs. baseline window).
5. Correction attempts consumed by already-labeled classes.
6. Functional App Yield delta (the §2 hypothesis; a later-phase measurement once
   recall effectiveness is established).

## 10. Long-term vision (from the idea doc; non-normative here)

> **Revision 5:** cycle and campaign are provenance, not scopes (§7), so the hierarchy below reads as the scope ladder (agent, role, project, organization) with cycle and campaign carried as provenance. Attribution, applicability and authorization stay distinct.

The destination is an engineering organization that learns from every execution cycle:
a memory hierarchy (Agent → Cycle → Project → Organization), four cognitive memory types
(episodic/semantic/procedural/reflective), role-tuned retrieval profiles
(developer procedural-heavy, qa episodic-heavy, strategy semantic-heavy, audit
reflective-heavy), a full Observe→Evaluate→Score→Encode→Consolidate→Store→Retrieve→
Promote→Forget lifecycle, and evidence-gated promotion into validated institutional
knowledge. Phase 1 deliberately instantiates the smallest slice of this that can prove
value on a number: one memory type (reflective), one scope (project), one consumer
(plan authoring), one metric (rejection recurrence).

## 11. Non-goals (Phase 1)

- Organization-scope memory and cross-project promotion (Phase 2, evidence-gated).
- Role cognitive profiles and per-role retrieval tuning (vision).
- Memory analytics services, governance service, "Memory Consolidation Engine" as a
  standalone service — Phase 1 adds **zero new services**; it is a pipeline through
  existing ports.
- Agent-discretionary remember/recall tools **in cycle-mode task execution** (deliberate
  divergence from CrewAI, §4). Duty- and ambient-mode discretionary access is explicitly
  designed *for* (§6) — deferred, not excluded.
- A Memory Librarian role — the Campaign-Self-Improvement draft's §12.7 should defer to
  this SIP rather than grow a parallel memory surface.
- Memories of *facts about the app under build* (manifest fields, endpoint shapes) — the
  contract/manifest seams already carry those deterministically; duplicating them in
  memory recreates the stale-fact poisoning CrewAI warns about.

## 12. Placement in the dev arc

> **Superseded as placement.** The placement is the Status block's note of 2026-09-12: **v2.2**, with the
> recall port's empty rail in v2.1. The text below is the 2026-08-03 record, kept for its reasoning: the
> #571 prerequisite (since fixed) and the confound argument.

Per the ratified post-1.4 reshuffle (`docs/plans/post-1-4-roadmap-reconciliation.md`,
2026-08-03):

- **Phase 1 → v1.8, riding as a thin non-headline feature** beside the release's
  headliners (Campaign mechanic, Lane M; scorecard/benchmark registry). Phase 1 adds
  zero services — the 1.2.0 precedent (three feature SIPs, one release) covers a thin
  rider. Deliberately **not** v1.6: injecting memory into authoring during the release
  that measures the authored-manifest baseline would confound that baseline; and not
  earlier, because by 1.8 Phase 1 inherits **two** seed corpora (plan-validation classes
  + the manifest-authoring rejection classes v1.6 creates) and measures recurrence
  against the banked 1.6 authored-mode FAY baseline.
- **Phase 2 → v2.0, inside the Capability-Backed Agents arc.** The 2.0 umbrella names
  scoped memory as a component of what an agent is and its problem statement demands
  exactly Phase 2's content — "memory needs scope, provenance, promotion, and
  disclosure." Phase 2 (consolidation, promotion, duty/ambient utilization, §6–§8) is
  that substrate, delivered with a Phase-1 measured result behind it rather than
  specified cold from inside an umbrella. Framed at the 2.0 altitude, this SIP is the
  *learned-experience* leg of the capability-backed agent equation — **agent = identity
  (SIP-0088/0089) + capability (packs) + memory (this SIP) + policy + evidence
  history** — which is why it precedes the umbrella rather than riding inside it.
- **Hard prerequisite — #571 (added 2026-08-04, verified against the code):** the
  SIP-042 LanceDB adapter's recall path has two defects that Phase 1 would build
  directly on top of. `adapters/memory/lancedb.py:130` applies `.limit()` *before*
  namespace and tag filtering (done in Python at 138–147), so a query whose nearest
  neighbours all sit in another namespace returns nothing while matching entries exist
  — and namespace-scoped recall is exactly what §5's filter chain does. Line 136 scores
  `1.0 - _distance` against LanceDB's default **L2** metric, which is not a `[0, 1]`
  similarity, so the confidence threshold in that same chain does not mean what it says.
  Neither is live today (nothing leverages memory yet), which is why they must be fixed
  BEFORE this SIP rather than beside it: §9's gate is a *measured recurrence-rate drop*,
  and a starving recall path would report "memory doesn't help" when the truth is
  "recall never returned the memory." Fix #571 first; it is small and independent.
- **Sequencing (readiness, not dates):** implementation can begin once design review
  accepts and #571 is fixed; the other hard dependencies are already shipped (SIP-042
  mechanics, the #669 injection seam, `gate_decisions` persistence). SIP-0101's replay
  harness must be usable before
  the Phase-1 *measurement* is scored, not before implementation starts. Campaign
  landing in the same release supplies `created_campaign` provenance and the
  within-campaign consumer from day one (§7); nothing in Phase 1 hard-requires it.
- **File ownership:** planning/authoring surfaces (task_plan, planning handlers,
  prompt assets) — Macbook-lane per the #281 ownership split; the LanceDB adapter and
  any config plumbing are shared surfaces.

## 13. Open questions for design review

> **Revision 5 answers:** question 2 (§0.2: the pattern's identity), 4 (§0.12: the pre-registration), 6 (§0.6 and §0.4: approval is the owner's, per revision and applicability), 7 (§0.10: no automatic decay in Phase 1) and 8 (§0.4: a supported behavior's missing template blocks its support claim, and an unsupported one is disclosed backlog). Questions 3 and 5 stay open for Phase 1.5 and Phase 2.
>
> **Revision 6 answers question 3** (§0.9): repair is one of Phase 1's four consuming seams, beside build authoring, and both are inert until a correction-round lesson is approved. **It extends the answer to question 1** (§0.4): a person's plan rejection with no recorded class is recorded as `unclassified` and produces no pattern, and the auditor reads it in the backlog and may propose a target behavior from it. Question 5 stays open for Phase 2.

1. Should human gate rejections (free-text reasons) enter Phase 1's corpus, or only
   validator-emitted classes? (Draft position: validator-only — deterministic encode; the
   human-reason path needs the Phase-2 LLM encode.) **Answered by revision 4 for classified
   rulings (§5b):** a return carrying a `ProposalClassification` enters; an unclassified reason does not.
2. Per-class deduplication key: rejection class alone, or class × task_type?
3. Does recall also belong on repair envelopes in Phase 1 (the correction lane of §2), or
   is that scope creep past "one consumer"? (Draft position: plan authoring only; repair
   recall is the first Phase-1.5 extension once the metric exists.) **Revision 4 keeps repair
   recall in Phase 1.5, and Phase 1's one consumer is the proposal task (§5b).**
4. Retention horizon and the memory-off control protocol for the measurement window.
5. Role-scoped expertise memory (procedural — "how this role solves problems well",
   keyed to persistent identity per SIP-0088/0089): does it enter as a Phase 1.5 with
   its own seed corpus, or wait for Phase 2's LLM-assisted encode?
6. The `candidate → validated` transition (§5/§6): what validation evidence promotes a
   duty- or ambient-born memory into cycle-mode recall — reuse under observation, audit
   sign-off, or a replay-scored trial? (Draft position: Phase 2's promotion gates are
   the single mechanism; no side door. The lifecycle `status` field now carries the
   answer's machinery; this question is about the *evidence bar*.)
7. Decay calibration (§5): the consecutive-ineffective threshold K and the confidence
   floor — fixed defaults, or derived from the measurement window's base rates?
8. Encoding-template governance: who reviews new per-class templates (they are prompt
   content under #448 — same review path as fragments?), and is a missing template a
   release-blocking gap for a newly shipped validator or a disclosed backlog item?
