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

> **Placement and delivery (2026-10-04: the owner's rulings on the SIP-portfolio audit, `sips/PORTFOLIO.md`).** **The 2.2 headline, and 2.2's only change to squad behaviour**, beside #1708's auto tier and escalation queue, which change the control plane, not the squad. #557, #949 and #950 follow Outcome Evaluation's scenarios (2.4 or later). **Its 2.1 part** (the inert recall port, its call site, and the Phase-1 re-read) is **#1964**. **It owns** memory's scopes, lifecycle and payload; Capability-Backed Agents (3.x) defers to it. **A constraint from 3.x:** memory stays addressable as a service, the Embodiment Runtime's invariant 2. **Accepted with revision 4 (2026-10-06, §5b):** the re-read moves Phase 1's proving workload to the campaign's proposal gate.


## Status
Accepted (2026-10-06), with revision 4, on the 2.2 plan's PR. The owner reviews both together, and
the merge is the acceptance (CLAUDE.md, SIP workflow step 3). Phase 1 is the 2.2 headline
(`docs/plans/2-2-0-plan.md`, a draft in the same PR).

**Author:** Jason Ladd
**Created:** 2026-08-03
**Revision:** 5 (2026-10-06). It adopts an external design review as §0, the normative Phase-1 contract, and
records the change in §5c. Revision 4 (2026-10-06) re-reads Phase 1's value hypothesis against the evidence of 2.1's
line (§5b, #1964) and moves Phase 1's proving workload from the plan gate to the campaign's proposal
gate, where the recurrence is live. Revision 3 (2026-10-01) folds in the new elements of the owner's v4 draft (2026-08-29,
recorded in `docs/ideas/cross-cycle-memory-v4-draft.md`) as §5a, corrects references that went stale,
and states how Campaign (2.0) and this SIP meet. Revision 2 (2026-08-03) incorporated design-review
round 1: the typed Phase-1 primitive, governed encoding templates, the lifecycle `status` dimension,
deterministic Phase-1 retrieval, the recall-vs-outcome metric split, and Phase-1 decay.
**Builds on:** SIP-042 (LanceDB semantic memory — the storage mechanics), SIP-0088/0089
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

## Delivery ledger (current as of 2026-10-06)

Kept by the rule in CLAUDE.md ("SIP System"): one row per part, updated in the PR that ships or
re-places it.

| part | status | where |
|---|---|---|
| the recall port, inert (answers empty), injected explicitly by the root, and its call site through `plan_rejection_context` | **shipped** | 2.1.0, PR #2058, issue #1964 |
| the re-read of the Phase-1 value hypothesis against 2.1's recurrence evidence, as an amendment here | **placed** | 2.1.0, #1964: the evidence up to the final deploy is §5b (revision 4), and the cut set's readings are added at the cut |
| Phase 1, slice 1: capture each proposal's inputs before authoring, and the source-case inspection (§0.11, §0.4) | **placed** | 2.2.0, #2105 |
| Phase 1, slice 2: the proposal replay, three arms (§0.11–§0.12) | **placed** | 2.2.0, #2106 |
| Phase 1, slice 3: the mechanism, inert until approved (§0.2–§0.10) | **placed** | 2.2.0, #2096 |
| Phase 1, slice 4: the template and the measurement window, read before 2.2.0's cut (§0.4, §0.12–§0.13) | **placed** | 2.2.0, #2107 |
| Phase 1.5: the correction lane (§13 question 3) | **unplaced** | read again when `failed_detail` holds failures of more than one shape (§5b) |
| Phase 2: consolidation and promotion (§8) | **unplaced** | gated on Phase 1's measurement (§8) |

**What closes this SIP:** Phase 1's four slices shipped in 2.2.0 with the window's finding recorded (§0.13), and Phase 2's
gate ruled by the owner on that finding, which also places or drops Phase 1.5.

## 0. The Phase-1 contract (normative, revision 5)

**This section governs Phase 1.** Revision 5 (2026-10-06) adopts an external design review of revision 4 and of the 2.2 plan. The review found that earlier sections still read as active requirements and contradict each other:
- the observation seam (§5) against the proposal ruling (§5b);
- the consumer;
- the instrument (§5a, §9);
- the experiment;
- deterministic retrieval against §6's composite scoring;
- admission (`validated` against §5a's `candidate`);
- feedback (§5) against §7's campaign-close update;
- the Phase-2 gate (§8).

Where an earlier section disagrees with this one, this one holds, and the earlier text is marked as superseded where it stands. Who ruled it is §5c.

**In one paragraph:**
- Phase 1 observes committed, eligible proposal-return rulings. It encodes reviewed reflective guidance in project scope, and supplies approved, applicable pattern revisions to `strategy.propose_increment`.
- Retrieval is deterministic and uses a memory snapshot pinned when the campaign is admitted.
- Proposal replay is the proving instrument.
- The plan-authoring recall seams (#2058) stay inert.
- These stay deferred: correction-lane ingestion, semantic ranking, autonomous promotion and any other payload.

### 0.1 What Phase 1 tests

Phase 1 tests whether **retaining and selectively applying reviewed lessons from earlier campaigns' proposal returns improves later proposal authoring** under controlled conditions. It discovers no corrective rules: people write the templates, and observed experience decides which reviewed lessons are kept and supplied.

**It is cross-campaign learning.**
- Observations are recorded while a campaign runs. New guidance does not become active within that campaign.
- Owner-approved changes apply to campaigns admitted afterwards.
- Correction within a proposal stays SIP-0109 §9.2's revision note.
- Unattended learning (evidence-gated activation at a declared boundary, with rollback and measurement) would need its own authorization. It must not emerge from feedback updates.

### 0.2 The domain model

These six are domain concepts, not services or databases:

| concept | what it is | identity |
|---|---|---|
| **observation** | one immutable occurrence: a committed ruling that returned a proposal, with its classification disposition and evidence | the ruling's control-log entry |
| **pattern** | the stable identity of one behavioral lesson | project scope, target behavior (§0.4), task type |
| **pattern revision** | immutable guidance text, applicability and template version | pattern and revision number |
| **approval** | the owner's authorization of one revision for a stated applicability | revision and applicability |
| **exposure** | the exact revisions supplied to one proposal invocation, with what was omitted and why | the invocation |
| **assessment** | what was observed for that exposure's targets (§0.10) | the exposure |

They are stored as four records: observations, pattern revisions, approvals, and exposures that carry their assessment.

**The invariant:** a new occurrence adds evidence. It never resets a lesson's history, restores deprecated guidance, or inherits approval for changed content. Re-encoding a historical observation through a new template keeps the observation's identity, so one failure never becomes two pieces of evidence.

### 0.3 Observe

**What is read.** The observation is a committed ruling at the increment gate (SIP-0109 §9.4) that returns a proposal. It is read as a projection from the campaign control log, which stays the authoritative record. The projection's guarantees:
- only committed, eligible rulings produce memory;
- a duplicate delivery adds no evidence, pattern or feedback;
- a crash between the ruling's commit and the projection is recovered by reconciliation;
- a retraction or reclassification keeps the history and marks the guidance that depended on it;
- replay experiments never write to the production corpus.

The projection uses the campaign's existing durable log. It is not a new service or a distributed transaction.

### 0.4 Classify and encode

**Every return carries a classification disposition:** a `ProposalClassification` class, or an explicit `unclassified` with its rationale and evidence. An `unclassified` return:
- is a valid gate action;
- produces no pattern;
- is counted in coverage reporting;
- enters a taxonomy backlog.

A return carrying neither is refused (SIP-0109's rail, 2.2 plan decision D2). A historical return whose class is only in prose enters through a reviewed annotation, which keeps both the original ruling and the annotation's provenance.

**Target behaviors sit beneath the vocabulary.** `ProposalClassification` stays the gate's vocabulary. Where one class holds different corrections, a reviewed **target behavior** beneath it names one. *Criteria not checkable* holds at least two:
- a new criterion already satisfied by the accepted application;
- a criterion stating a rule the request does not.

Phase 1 supports one target behavior: **a proposed new acceptance criterion is already satisfied by the accepted application.** A class or behavior claimed as supported must have its template, and an unsupported one is disclosed backlog that never blocks a legitimate return.

**Each template maps:**
- the observable defect;
- the corrective action;
- the evidence needed to take it;
- its applicability and exceptions;
- the rubric that assesses recurrence.

For this target, the corrective rule leads to evidence of the intended before-and-after difference against the accepted application. It is not an admonition to write checkable criteria, which already failed (#1947).

**What the encoding may and may not use.**
- No LLM is in the encode path.
- Free text stays evidence. Guidance comes only from governed templates.
- The v4 draft's precedence rule (compilation, then security, then function, then performance; §5a) is not applied to proposal classes. Every observed defect is kept as evidence.

**`validated` means admissible, not effective:** the observation has an admissible source, recorded evidence, a supported classification and a valid governed encoding. It says nothing about whether the guidance helps. Source admissibility, the owner's authorization and measured benefit stay distinct.

### 0.5 Provenance

The source is a **proposal ruling**, a typed source beside §5's `gate_decision`. It carries:
- the project and campaign;
- the proposal's id and version;
- the ruling's control-log entry, and any that supersedes it;
- the decider's identity and type;
- the proposal invocation (run and task);
- the accepted application's identity it was judged against;
- the criterion and evidence references;
- the classification and template versions.

**What is optional, and what the model fields mean.**
- The cycle id is optional, because a returned proposal may never create a cycle.
- `origin_mode = cycle` names the execution posture, not a cycle's existence.
- The origin model is the **proposer's**. A model used in classifying, if any, is recorded separately.

### 0.6 Approval and activation

**What an approval binds.** An approval binds one pattern revision to a stated applicability: project, task type, role, stack and model families. A new approval is needed to:
- change the content;
- widen the applicability;
- add a model family.

**The statuses.**
- Approval to influence execution is distinct from promotion to a broader scope, which is Phase 2's.
- In Phase 1, `status = promoted` (§5) is read as *approved for its stated applicability*, and no other promotion exists.
- A revision approved for model family A is not recalled for family B.

### 0.7 The campaign snapshot

When a campaign is admitted, it pins a memory snapshot, an immutable manifest of:
- the available pattern revisions and their approvals;
- the template versions;
- the retrieval policy and thresholds;
- the applicability rules;
- the ordering and the budgets.

**What can change, and when.**
- Every proposal task selects from that snapshot and records its exposure.
- Feedback accrues at once.
- Approval, deprecation, confidence and template changes reach campaigns admitted later.
- Concurrent campaigns keep their own snapshots.
- A restart reproduces the original selection from the same snapshot and task inputs.

**Emergency revocation** of demonstrably harmful guidance halts or restarts the affected work under a new snapshot, and the affected measurements are explicitly invalidated or set apart. A counted intervention is never changed silently halfway through.

### 0.8 Recall

**Who owns what.**
- `MemoryPort` owns storage (SIP-042).
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

The recall reaches `strategy.propose_increment` through a managed fragment, in its own slot, separate from §9.2's revision note. With an empty or unapproved snapshot, the rendered prompt is byte-identical to one rendered without memory.

### 0.10 Assessment and feedback

**What an assessment attaches to.** It attaches to the exact proposal revision and exposure, not to the next gate event. A ruling's silence about a class is not evidence the class is absent:
- the proposal may be returned for another defect;
- it may carry several defects and record one;
- it may be approved without the target being checked;
- it may avoid the defect by omitting meaningful work.

Each target is assessed by its template's rubric as **present**, **absent after assessment**, **not applicable**, or **unassessed**. Retrieval, injection, assessment and outcome are recorded separately.

**The statistic is `target_absence_rate`,** over applicable, assessed exposures. It replaces §5's `success_rate`. It is observational, not a causal estimate of memory's benefit. Unassessed and inapplicable exposures earn no credit. Campaign-close aggregation summarizes assessments, and never overwrites them with cycle success (§7).

**What a recurrence means:**
- Repeated recurrence is a diagnostic trigger, not proof the rule is false. The model may lack the evidence, misread the instruction, or fail to follow valid guidance.
- Invalid guidance and ineffective delivery are told apart.
- Harm is attributed only on explicit evidence.

**Phase 1 has no automatic decay.** Deprecation is the owner's decision on assessed evidence, and takes effect at the next campaign admission. A small, precise policy is preferred to an unsupported confidence formula.

### 0.11 The instrument: proposal replay

**What is captured.** A `ProposalReplayEnvelope` is captured immediately before `strategy.propose_increment`. It contains, or immutably references:
- the objective and policy;
- the accepted application's, PRD's, manifest's and evidence's revisions;
- the task's actual inputs;
- the prior proposal and revision note, when it is a revision;
- the complete assembled prompt and its fragment versions;
- the model's identity, version and sampling settings;
- the memory snapshot and the exact intervention;
- the hashes of inputs and artifacts.

The capture is complete, independent of the stored prompt's 10,000-character cut (#1756), or its reconstruction is proven lossless. A historical case whose inputs cannot be verified is diagnostic only.

**Temporal validity.**
- A target's eligible lessons originate in campaigns before the target's.
- Replaying a proposal with a lesson derived from its own return tests assisted repair, not transfer, and is reported as that.

**The cases.**
- Development cases, used to write the templates, are separated from held-out evaluation cases before any tuning.
- First proposals in later campaigns are the primary test. Revisions are reported separately, since they already receive the revision note.

### 0.12 The experiment and its pre-registration

| arm | purpose |
|---|---|
| current baseline | today's prompt, with #1947 and any revision note, and no cross-campaign memory |
| scoped memory | identical ordinary inputs, plus the eligible historical guidance |
| static guidance (secondary) | the same reviewed guidance under a fixed prompt policy. With one target behavior it differs from scoped memory only where the lesson does not apply, so it measures selectivity, unnecessary injection and token cost |

**What is deferred, and how the runs are controlled.**
- The v4 draft's raw-trace and factual-memory arms (§5a) are deferred.
- The corpus, templates, model settings, policies and rubric are frozen before scored runs.
- Arm order is randomized or balanced. Inputs are paired.
- Repeated generations of one case are reported apart from independent cases.
- Any live confirmation assigns treatment at campaign boundaries, because alternating within an evolving campaign carries over through the accepted application.
- Calibration cycles are operational checks, not the comparison.
- An improvement in ordinary inputs (the evidence the proposer sees, §0.4) is a separately identified change, held identical across arms.

**The pre-registration fixes, before scored runs:**
- the primary target and what counts as an eligible opportunity (never defined after seeing an output);
- the development and test split;
- unique cases, campaigns and repeated generations, counted separately;
- the unit of analysis and the treatment of campaign and lineage dependence;
- confirmatory and exploratory comparisons;
- the minimum worthwhile effect, and the uncertainty reporting suited to the design;
- the handling of missing assessments and invalid replays;
- the budget cap and the stopping rule;
- the versions of prompts, templates, models, policies and the evaluator;
- the local guardrails:
  - the proposal still advances the objective;
  - required scope and meaningful criteria remain;
  - other serious defects do not materially increase;
  - context cost stays within budget;
  - memory cannot earn a win with an empty proposal or by avoiding the requested work.

All outputs, approvals and other returns included, are assessed by one fixed rubric, with evaluators blind to the arm where practical and adjudication recorded. Injected tokens are reported as measured.

### 0.13 Findings and what follows

**The instrument's validity is read first.** An invalid instrument supports no conclusion about memory. A valid one reads one of four findings:
1. **Supported benefit:** a meaningful targeted improvement, adequate evidence, and the guardrails held.
2. **No demonstrated useful benefit:** an informative experiment below the practical threshold.
3. **Harm:** unacceptable regressions caused by the guidance or the system.
4. **Inconclusive:** too few independent opportunities, too much uncertainty, or incomplete assessment.

**The record states five things separately:**
- the mechanism's correctness;
- the experiment's validity and result;
- the activated patterns and their applicability;
- the auto-gate scope enabled;
- the owner's disposition for the next phase.

**What a finding does and does not license.**
- A negative result for one class, template, model and workload does not disprove decision, correction, procedural or organizational memory.
- A successful replay does not by itself authorize Phase 2.
- **Phase 2 begins only on the owner's ruling after a valid finding** (§8, amended).

**The corpus is small.** The target behavior has about three independent historical cases, in three campaigns, none captured before authoring. So the test corpus is built by the 2.2 line's own campaigns, and **"inconclusive" is a likely and legitimate finding** for 2.2.

### 0.14 Deferred, and who owns what

**Deferred:**
- correction-lane ingestion (Phase 1.5);
- semantic ranking;
- LLM-generated lessons;
- autonomous promotion;
- organization-wide transfer;
- procedural-success learning;
- duty and ambient write tools;
- generic consolidation.

Decision records belong to the Design Decision Register and #950 (§5b).

| document or interface | owns |
|---|---|
| SIP-0110 | memory payloads, lifecycle, applicability, approvals, exposure and effectiveness semantics |
| SIP-0109 | ruling events, the campaign snapshot's admission point, gate authority, escalation and continuation |
| SIP-042 | storage and the adapter's guarantees |
| the replay specification (#2096's slices) | the pre-proposal envelope, temporal isolation, arm execution and scoring |
| SIP-0088/0089 | persistent identity and mode compatibility |
| the Design Decision Register, #950 | the authoritative decision payload and its lifecycle |

### 0.15 Acceptance matrix

Synthetic fixtures establish the mechanism's behavior. They are never evidence of cross-campaign improvement.

| area | required scenario |
|---|---|
| provenance | a returned proposal with no cycle id is encoded and traced correctly |
| idempotency | a duplicate ruling delivery does not double-count evidence or feedback |
| recovery | a crash after the ruling's commit and before the projection is recovered |
| corrections | a reclassification or retraction keeps history and updates dependents explicitly |
| classification | a novel `unclassified` defect is returned without creating a pattern |
| pattern identity | a repeat occurrence cannot reset or resurrect deprecated guidance |
| approval | new template content or widened applicability requires its own approval |
| model scope | approval for one model family does not apply to another |
| isolation | wrong-project, incompatible-stack and unapproved records are excluded before the budgets |
| determinism | tied timestamps and more than three eligible patterns give a stable selection |
| budget | oversized guidance is omitted explicitly, never truncated |
| campaign freeze | feedback, approval or deprecation cannot alter a running campaign's snapshot |
| restart | the original exposure is reconstructed after a restart |
| failure disclosure | disabled, empty, filtered and failed recall remain distinguishable |
| inert behavior | an empty or unapproved snapshot leaves the rendered prompt unchanged |
| feedback | unassessed or partly classified outputs earn no credit |
| replay fidelity | both arms have identical ordinary pre-proposal inputs |
| temporal validity | a target cannot learn from its own later return or a later campaign's evidence |
| experiment isolation | test runs cannot modify production memory or learn from their outputs |
| quality | a target reduction cannot be achieved by omitting meaningful required work |

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

> **Superseded by §0 (revision 5):** Phase 1 observes committed proposal-return rulings (§0.3). The plan-gate and correction-finalization observations below are historical.

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

> **Revision 5 settles all three, and narrows one rule above.** The instrument is proposal replay (§0.11). The sample is
> pre-registered, with "inconclusive" a legitimate finding (§0.12, §0.13). The auto tier stays off increment rulings through
> the measurement window (the 2.2 plan, D3). And templates are written per **target behavior** beneath a class, not per
> class (§0.4).

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

Phase 2 does not begin until Phase 1's recurrence-rate measurement is in hand. **Amended by revision 5 (§0.13):** it begins only on the owner's ruling after a valid finding, which may be any of the four. Later consolidation keeps disputed, superseded and differently scoped claims with their evidence, never deletes history to resolve a contradiction, and does not equate low reuse with low value.

## 9. Success metrics (measured, not aspirational)

Two tiers, deliberately separated — a memory can suppress its targeted class while the
overall result stays poor, so conflating them would let recall wins masquerade as
outcome wins:

> **Revision 5:** the metric's statistic is `target_absence_rate` over assessed exposures (§0.10); the instrument, arms and pre-registration are §0.11–§0.12; and Phase 1 keeps local non-regression guardrails, so "never gates Phase 1" below holds for Functional App Yield, not for the guardrails (§0.12).

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
