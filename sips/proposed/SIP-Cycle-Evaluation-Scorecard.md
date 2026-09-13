---
sip_uid: '17883224960396698'
status: proposed
title: Cycle Evaluation Scorecard
author: SquadOps Architecture
created_at: '2026-02-28T00:00:00Z'
---
# SIP-0XXX: Cycle Evaluation Scorecard

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 2

| Rev | Date | What changed |
|---|---|---|
| 1 | 2026-02-28 | The evaluation philosophy from `docs/ideas/IDEA-cycle-evaluation-scorecard-framework.md`: four dimensions, seven failure-attribution categories, three comparison styles, profile-aware fairness, a console Scorecard page and an API, five maturation phases. |
| — | 2026-09-12 | Amended in place by the owner's ruling on the 1.8 plan: this SIP is 1.8's Lane S headline beside Scoped Code Revision, and its 1.8 slice is headless and mechanical. |
| 2 | 2026-09-13 | **Rewritten to the slice**, before its design review (1.8 plan §3.1). The normative text is now the four deliverables the plan names (§4). The console page, recommendations, profile weighting, the three comparison styles beyond one window, and the internal eval packs move out of the slice, by name (§6). The seven categories become one registry derived from the five failure vocabularies the code already has, not an eighth (§4.2). The computation is ruled mechanical, with no agent in the path (§3.1). The single-model arm is defined as a proposal for the review (§4.4). Every code fact is verified on main `f30938bc`, and line numbers are as of that commit. |

**Targets: v1.8 — the Lane S headline** (owner's ruling, 2026-09-12; `docs/plans/1-8-0-plan.md`
§2.2 and §3.4). Its design review has the same reviewer, the owner, and the same outcome
vocabulary as SIP-0107's: *accepted*, *accepted with required revision*, or *rejected and
reframed*. **Its acceptance is independent of SIP-0107's**, but for the comparison window to
stay in 1.8.0 it must land, with the single-model arm defined, before the loop set's
pre-registration is committed (plan §4.2, §7 step 8). Otherwise deliverable (d) moves to 1.8.1
by that commit.

**Sequences after:** SIP-0096 Verification Evidence Integrity (implemented v1.5.0). Every
indicator here is read from evidence that cannot be fabricated by a stubbed, skipped or inert
check; scoring un-integrity-checked evidence would institutionalize the wrong lessons.

---

## 1. Summary

The project can state a functional yield. It cannot state that a squad outperforms a single
model at equal scaffolding and cost. This SIP makes that claim testable, and gives v2.0's
Campaign Orchestration the grades its continuation policy consumes instead of raw checks.

The 1.8 slice is four things, all mechanical:

- **(a) `CycleAssessment`**, a pure projection over the `CycleOutcome` seam and a durable
  evidence record. It has four dimensions, and every indicator cites evidence that resolves.
- **(b) One failure-attribution registry.** The seven categories become derivations over the
  five failure vocabularies the code already has. Every value maps to exactly one id, and a
  drift test holds it.
- **(c) A benchmark registry.** The stored counted rolls are re-graded deterministically from
  durable stores, each row with its code lineage.
- **(d) A comparison harness and one pre-registered window,** squad against a single model, with
  its result stated whichever way it goes.

(a) and (b) are the judgement contract 2.0 consumes; (c) and (d) accumulate evidence about it.

---

## 2. What exists on main

Verified on `f30938bc`. The slice composes these; it does not rebuild them.

**The outcome seam.** `CycleOutcome` (`src/squadops/cycles/verification_integrity.py:418`)
carries the cycle verdict (`RunVerdict`: `accepted`, `rejected`, `blocked_unverified`), the
verified and failed check ids, `unverified` with a reason and a required flag per check (`:240`),
`inert`, `waived`, `criteria_verified`, `criteria_total`, `run_count` and replay provenance. It is
derived from the durable per-run table `run_verification_summaries` (migration 1400, written at
run finalization through `CycleRegistryPort.record_run_verification_summary`). Its own docstring
already names the scorecard as projections over it.

**Five failure vocabularies**, each authoritative where it is used today:

| vocabulary | where | values |
|---|---|---|
| `FailureEvidenceCategory` | `src/squadops/cycles/failure_evidence.py:189` | `executed_and_failed`, `app_error`, `extraction_loss`, `emission_absent`, `sandbox_preexec_failure`, `verification_infra_failure`, `evidence_unavailable` |
| `FailureLocus` | `failure_evidence.py:249` (classifier `:353`) | `own_artifact` (the task's own artifact is the defect), `subject` (the thing under test failed), `unknown` |
| plan-validation rejection classes | `ImplementationPlan.validate_*`, fourteen, recorded by `RejectionClassifier` (`src/squadops/cycles/rejection_baseline.py:45`) | `validate_against_profile` … `validate_derived_criteria` |
| manifest winnability proofs | `src/squadops/cycles/manifest_gates.py:35–48` (`WinnabilityFinding` `:70`) | `parses`, `lint`, `expands`, `contract_derives`, `checks_live`, `testid_coverage`, `status_declared`, `status_warranted`, `error_shape_agrees`, `stack_matches_config` |
| correction movement | `src/squadops/cycles/correction_signature.py:165–169` | `new`, `repeat`, `progress`, `expansion`, `shifted` |

**Durable evidence a projection can read without logs.** The registry holds `cycle_runs` — with
`started_at`, `finished_at` and `failure_reason` (migration 1010), where a plan-defect
termination of the correction chain is named (#427, `adapters/cycles/correction_runner.py:686`) —
and the run summaries. The artifact vault holds every stored
artifact, with its metadata. That includes failed emissions stamped `emission_status: failed`
with their attempt (#971, #1436), and one `correction_decision.md` per correction round. The
governance attribute shape a registry must copy is `CheckSpec`'s (#730,
`src/squadops/cycles/acceptance_check_spec.py:139`): required keyword-only attributes, so every
entry declares them and none defaults through.

**Gaps the slice has to name:**
- **Token usage has no durable home.** `_llm_call` (`handlers/cycle/base.py:939`) records every
  generation to the observability port, and the production adapter is LangFuse. That is the
  drill-down lane, not a store of truth. Nothing writes usage beside the run summaries (§4.1).
- **Two loop facts live only in logs.** A refunded correction round (#1053) and the round-over-
  round movement (`classify_movement`) are logged by the correction path and stored nowhere. The
  verification-set driver reads them from container logs, which a projection may not. They join
  the durable run summary proposed in §4.1.
- **No clean-room verdict at run finalization.** SIP-0102 step 5 (`verified_executable`,
  `verified_functional` into SIP-0096's derivation) is open. The delivered-app audit is post-hoc
  and set-only, run by the verification-set driver. The quality dimension declares those
  indicators unaskable until step 5 lands; it does not read the driver's audit (§4.1).
- **Code lineage is not on the cycle row.** #80 adds `framework_version`, `framework_git_sha` and
  the request-profile name in the 1.8 prelude; the benchmark registry needs them (§4.3).
- **The driver's per-roll JSON records are partial.** `var/verification_sets/` holds 47 roll
  files for the 1.6.5–1.7.3 sets. The 1.7.4 and 1.7.5 records are not on the box, while the
  registry and the vault still hold those cycles (checked for three 1.7.5 cycles, 2026-09-13).
  The benchmark reads the durable stores, not those files (§4.3).

---

## 3. Rulings this revision proposes

### 3.1 The computation is mechanical — no agent in the path

Rev 1 asked whether "the Data agent assembles evidence, Lead evaluates" (its question 6).
**No.** An assessment computed by an agent is the self-graded evidence SIP-0096 exists to refuse,
and a grade the squad writes about itself is exactly what 2.0 must not act on. Every indicator is
read from a durable store by deterministic code. No LLM call, no clock, no I/O happens inside the
projection.

### 3.2 Four dimensions, indicators, no composite and no grade bands in 1.8

Rev 1's "four dimensions, not one number" stands. The slice also defines **no thresholds or grade
bands**. A band is a policy, and setting one before the benchmark registry shows the historical
distributions would bake a guess into every later comparison. The consumer that needs a stopping
rule, Campaign in 2.0, sets its policy over indicators the registry has already measured.

### 3.3 Every indicator is three-state and cites what it read

An indicator is *observed* with its value, *asked_none* when its producer ran and found nothing,
or *unaskable(reason)* when the producer could not ask on this cycle. That is the vocabulary the
verification-set driver adopted in 1.7.5 (#1445). Every observed value carries an evidence
reference that resolves: a run id, a vault artifact id, or a run-summary key. **A zero is never
written for an unaskable indicator.**

---

## 4. The slice — normative

### 4.1 (a) `CycleAssessment`

**Shape.** A frozen dataclass in `src/squadops/cycles/` beside the outcome seam:
`assess(outcome: CycleOutcome, evidence: CycleEvidence) -> CycleAssessment`. `CycleEvidence` is a
frozen record assembled by an adapter from durable stores only: the registry's runs and run
summaries, the vault's artifact metadata, and the usage summary below. **The projection performs
no I/O and reads nothing but its two arguments.** An architecture test holds that by imports.

**The indicators, by dimension:**

| dimension | indicators | read from |
|---|---|---|
| **outcome** | cycle verdict; criteria verified / total; required checks unverified, by reason; inert and waived checks, disclosed | `CycleOutcome` |
| **quality** | failed checks by id; unverified checks by reason; `verified_executable` and `verified_functional` — **unaskable until SIP-0102 step 5**, with that reason | `CycleOutcome`; run summaries |
| **coordination** | correction rounds; emission retries and contentless emissions, from failed-emission stamps; framing re-rolls (framing runs beyond the first); plan-defect terminations; refunded rounds and the correction movement sequence | vault artifact metadata; registry runs and `failure_reason`; refunds and movement from the run summary below |
| **efficiency** | wall-clock per run and for the cycle; prompt, completion and reasoning tokens per run and per task type; LLM calls | `cycle_runs` timestamps; the run summary below |

**The run summary — proposed for the review (§7 question 2).** At run finalization, beside
`run_verification_summaries`, the executor persists one durable row per run with the loop facts
no store holds today:
- **usage** — the sums of the generations that run's tasks made: calls, and prompt, completion
  and reasoning tokens by task type, with durations. Each handler's result carries a `usage`
  block that `_llm_call` accumulates, and the executor adds them up;
- **refunded rounds**, with the refund reason (#1053);
- **the correction movement sequence**, per failed task.

LangFuse remains the per-call drill-down. Historical cycles have no such row, so those indicators
are unaskable for them, never backfilled from logs.

**Primary attribution.** An assessment of a cycle that did not accept carries one primary
attribution: the registry id (§4.2) of the evidence that decided its verdict. That is the failed
required check's category and locus, or the plan or manifest gate that stopped the run. An
accepted cycle carries none. Contributing attributions, from every correction round, are listed
beside it and never merged into it.

**Computed on read, never stored as truth.** An assessment may be cached, keyed on the identity
of its inputs; the stores remain the record.

### 4.2 (b) One failure-attribution registry

**One module** (`src/squadops/cycles/failure_attribution.py`) declares the attribution ids, each
with a meaning written as what the evidence establishes, not a cause:

| id | what the evidence establishes |
|---|---|
| `model_insufficiency` | a producing role's artifact failed an executed criterion, or its emission carried nothing, under a contract and inputs that had passed their gates |
| `coordination_failure` | the handoff between stages lost or misrouted work: an emission's content lost in extraction, a framing artifact inconsistent with the plan or profile, a correction chain that stopped converging |
| `context_failure` | a task received inputs that did not carry what its contract required (reserved: no current vocabulary value maps to it, and the registry says so) |
| `validation_failure` | the verifying artifact itself was the defect: a suite that could not run or collect, rather than a subject that failed it |
| `resource_failure` | a declared budget ran out: completion cap reached with nothing extractable, time budget, correction attempts |
| `acceptance_criteria_failure` | the criteria or the contract could not be won as written: a winnability proof or a criteria-scoped plan validator refused them |
| `external_dependency_failure` | the environment failed before or around the product: sandbox pre-exec, verification infrastructure |
| `unattributed` | no rule maps the evidence; counted and shown, never hidden |

**Totality, drift-guarded.** Every value of the five vocabularies (§2) maps to exactly one id,
and a test fails on a value with no mapping or with two. **No failure-class string literal
appears anywhere else.** Each entry declares its governance attributes in the #730 shape: the
source vocabulary, the value, the id, and whether it can be a cycle's primary attribution (a
movement token cannot).

**Proposed mapping — the review may change rows; the drift test holds whatever it rules:**

| vocabulary | value | id |
|---|---|---|
| `FailureEvidenceCategory` | `executed_and_failed`, `app_error` | `model_insufficiency` |
| | `extraction_loss` | `coordination_failure` |
| | `emission_absent` | `resource_failure` when the marker shows the completion cap reached, else `model_insufficiency` (a declared two-row rule) |
| | `sandbox_preexec_failure`, `verification_infra_failure` | `external_dependency_failure` |
| | `evidence_unavailable` | `unattributed` |
| `FailureLocus` | `subject` | `model_insufficiency` (the product failed its suite) |
| | `own_artifact` | `validation_failure` (the suite itself is the defect) |
| | `unknown` | `unattributed` |
| plan validators | `validate_criteria_scope`, `validate_command_checks`, `validate_criteria_refs`, `validate_derived_criteria`, `validate_check_applicability` | `acceptance_criteria_failure` |
| | the other nine | `coordination_failure` |
| winnability proofs | `contract_derives`, `checks_live`, `testid_coverage`, `status_declared`, `status_warranted`, `error_shape_agrees` | `acceptance_criteria_failure` |
| | `parses`, `lint`, `expands`, `stack_matches_config` | `coordination_failure` |
| correction movement | `repeat`, `shifted`, `expansion` | `coordination_failure` (contributing only) |
| | `new`, `progress` | none: a movement that is not a failure (declared, so totality holds) |

### 4.3 (c) The benchmark registry

**The counted rolls from 1.6.3 through 1.7.5, re-graded by (a) with attribution from (b),** read
from the registry and the vault. It never reads the driver's JSON records, which are partial
(§2), or the logs. Replay-first: no new cycle.

- **Each row** carries the cycle id, the set, the arm, the roll's role (counted, shakeout,
  diagnostic or void, as the release packages name it), the assessment, and code lineage. That is
  #80's fields where the row has them, and otherwise the set's pinned commit and image ids from
  its pre-registration document.
- **Grouping** uses the one cycle-lineage seam the 1.8 prelude extracts from inert detection
  (plan §3.5), never a second series key.
- **A preflight states which rolls are re-gradeable and why the rest are not**: a cycle missing
  from the registry, runs with no summary row, and so on. Token indicators are unaskable for every
  historical roll (§4.1).
- **Acceptance:** the re-graded 1.7.5 rows agree with the 1.7.5 record's headline table on
  verdict, criteria and correction rounds.

### 4.4 (d) The comparison harness and one window

**The harness.** The verification-set driver gains an arm axis (squad profile × request profile
× model), and a pre-registration gains a comparison section. Both arms are graded by (a) with
attribution from (b).

**Registration before observation** (plan rev 4, §4.2). The comparison is designed in the loop
set's pre-registration, before any roll of either arm is observed. That design fixes which of the
loop set's React rolls form the squad arm, the inclusion rules, N per arm, the dimensions
compared, the declared envelope below, and **the decision rule for "exceeds"** — at N = 6 a rule
is a count over paired rolls, declared up front, never a rate read afterwards. The single-model
arm runs after the loop set closes, on the same frozen deploy if nothing has moved.

**The question, in the record's words:** *at equal scaffolding and declared cost, does the
squad's assessment exceed the single model's on outcome and quality, and at what efficiency
cost?* The answer is stated whichever way it goes. A negative is a result: it is 2.0's problem and
the thesis's, not the cut's.

**The single-model arm — proposed for the review (§7 question 1).** On `full-38` every role
already runs on one model, `qwen3.8:27b`. The arm is therefore not a different model. It is **one
agent, in one role**, doing the work the squad divides.

| | same in both arms | the squad arm only |
|---|---|---|
| **model and serving** | `qwen3.8:27b` on the same Ollama configuration and box, the same per-call completion caps | — |
| **inputs** | the PRD (`group_run`), the stack (FastAPI + React) | — |
| **deterministic scaffolding** | skeleton expansion from the manifest, frozen files, write grants, fill-slot integrity, the verification contract derived from the manifest, typed checks, the rendered container packaging (#598) | — |
| **the loop** | emission retries, the correction attempt budget (`max_correction_attempts`), repair targeting by the deterministic locus rules (register entry 36), patch acceptance, retests | the analyzer (`data.analyze_failure`) and the lead's correction decision |
| **authoring** | one manifest, the application's files, the qa suite — each written by the arm's author | framing by six roles: strategy analysis, research context, plan review, the role-specific prompts, the handoffs |
| **gates** | the same gate, approved by the same fixed notes | — |
| **declared envelope** | the same run time budget (SIP-0079 RC-8) and the same per-call caps; total tokens and wall-clock **measured and reported**, not capped | — |

**What building the arm takes**, named so capacity is judged honestly: a `solo` squad profile of
one agent, a request profile whose task plan assigns every authoring task to that agent, and a
generalist system prompt asset. No framework seam changes: the loop, the scaffolding and the
verification are the squad's own. This is why (d) is first in the 1.8 plan's drop order (§5).

---

## 5. Acceptance criteria — the slice

1. **(a)** `assess()` returns four dimensions of three-state indicators. An architecture test
   proves the projection does no I/O and reads only `CycleOutcome` and `CycleEvidence`. On every
   counted record of the 1.8 set, every observed indicator's evidence reference resolves.
2. **(a)** The run summary (usage, refunds, movement) is persisted at run finalization for every
   run, and a wiring test enters at the executor's finalization and asserts the row. If §7
   question 2 rules otherwise, the alternative it names is the criterion instead.
3. **(b)** The registry is total over the five vocabularies, and the drift test fails on an
   unmapped or doubly-mapped value. No failure-class literal exists outside it (a guard test).
   Every non-accepted assessment carries a primary attribution id or `unattributed`.
4. **(c)** The preflight names the re-gradeable rolls. The re-graded 1.7.5 rows match that
   record's table on verdict, criteria and correction rounds.
5. **(d)** The driver runs both arms under one comparison section, and one window closes with its
   result stated against the registered decision rule — **if (d) is in 1.8.0's scope at the loop
   set's pre-registration**. Otherwise this criterion is 1.8.1's (plan §3.4, §5).

---

## 6. Out of the slice, by name

Named so silence is not read as shipped:

- **The console Scorecard page** is SIP-0069's surface, a later consumer of `assess()`.
- **Next-step recommendations** (rev 1's "try a larger model", its question 5) have no consumer
  in 1.8 and would be an agent in the path.
- **Profile-aware weighting and fairness bands** for lean against max-quality profiles (rev 1's
  goal 5, its question 1): no bands in 1.8 (§3.2).
- **Rev 1's three comparison styles:** one window only, squad against a single model. Fixed
  coordination with variable models, and a fixed envelope with variable strategy, are 2.0's.
- **The internal eval packs** (Dev, QA, Research, Tool Executor) go to 2.0 with the Campaign that
  would run them (plan §8 decision 4).
- **A public API endpoint:** in 1.8 the driver and the benchmark call `assess()` in-process over
  the assembled record. A `/api/v1` resource arrives with its first remote consumer, following the
  route-lane standard.
- **Review-packet synthesis** (#950) overlaps rev 1's "what happened" question, and is a later
  consumer; nothing is built for it here.

---

## 7. Questions for the design review

1. **The single-model arm (§4.4).** Is "one agent in one role, with the squad's deterministic
   scaffolding and loop but without the analyzer, the lead's decision and the framing roles" the
   comparison the thesis needs? And is the declared envelope — same time budget and per-call caps,
   totals measured — "equal cost"?
2. **The run summary (§4.1).** A durable per-run row written at finalization for usage, refunds
   and movement? Or tokens read from the observability port at assessment time, with refunds and
   movement unaskable in 1.8? This revision proposes the row: LangFuse is the drill-down lane, and
   an assessment must not depend on a trace store's retention or on logs.
3. **The attribution mapping (§4.2).** Rule on the proposed rows. In particular: does
   `subject` → `model_insufficiency` hold for a suite that asserted the wrong behaviour, and should
   `context_failure` stay reserved with no mapping in 1.8?
4. **No grade bands in 1.8 (§3.2).** Confirm that Campaign sets its stopping policy in 2.0 over
   measured distributions, rather than this SIP fixing bands now.

---

## 8. Interaction with other SIPs

- **SIP-0096** (implemented): the substrate. The assessment adds no raw field to `CycleOutcome`.
- **SIP-0101** (accepted): its replay records are an input to the benchmark registry, as a
  consumer, not a completion.
- **SIP-0102** (accepted): step 5 is **absent**, and the quality dimension declares its two
  indicators unaskable with that reason until it lands.
- **SIP-0107** (accepted, 1.8 Lane M): its §39.8 transaction readout is the loop set's evidence,
  not an assessment input in 1.8. Scoped-revision indicators may join the coordination dimension
  after 1.8.1's default flip.
- **SIP-0069** (console): the later consumer of the Scorecard page.
- **Campaign Orchestration** (proposed, v2.0 headline): the first consumer allowed to act on
  `CycleAssessment`. It reads indicators and attribution ids and never raw checks; its objective
  envelope enriches the lineage seam, and no consumer migrates.
- **Cross-Cycle Memory** (proposed, v2.2): may key recall on attribution ids; nothing is built
  for it here.

---

## 9. Source ideas

- `docs/ideas/IDEA-cycle-evaluation-scorecard-framework.md` — the evaluation philosophy, the four
  dimensions, the attribution model and the comparison intent. Its "Target Release: 1.1+" is
  superseded by this SIP's v1.8 target, and the idea document now says so.
