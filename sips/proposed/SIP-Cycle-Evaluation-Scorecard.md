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
**Revision:** 3

| Rev | Date | What changed |
|---|---|---|
| 1 | 2026-02-28 | The evaluation philosophy from `docs/ideas/IDEA-cycle-evaluation-scorecard-framework.md`: four dimensions, seven failure-attribution categories, three comparison styles, profile-aware fairness, a console Scorecard page and an API, five maturation phases. |
| — | 2026-09-12 | Amended in place by the owner's ruling on the 1.8 plan: this SIP is 1.8's Lane S headline beside Scoped Code Revision, and its 1.8 slice is headless and mechanical. |
| 2 | 2026-09-13 | **Rewritten to the slice**, before its design review (1.8 plan §3.1). The normative text is now the four deliverables the plan names (§4). The console page, recommendations, profile weighting, the three comparison styles beyond one window, and the internal eval packs move out of the slice, by name (§6). The seven categories become one registry derived from the five failure vocabularies the code already has, not an eighth (§4.2). The computation is ruled mechanical, with no agent in the path (§3.1). The single-model arm is defined as a proposal for the review (§4.4). Every code fact is verified on main `f30938bc`, and line numbers are as of that commit. |
| 3 | 2026-09-13 | **The design review's required revisions** (written review notes forwarded by the owner, disposition *accept with required revision*). The architecture is unchanged. **Attribution** (§4.2): the classes are renamed to what the evidence shows, not causes; the registry is total over *dispositions* (an attribution class or `non_failure`), over every vocabulary that decides a terminal state (eight, not five); orthogonal facts compose by declared precedence; primary attribution is the terminal evidence of the final state transition, with everything earlier contributing; `unattributed` is preferred to an unsupported mapping. **Comparison** (§4.4): named a system-level experiment — the SquadOps reasoning organization against one generalist agent on the same deterministic substrate — with cost measured, not equalized; authority stays task-scoped; reasoning policy and per-task-type caps frozen and asserted equal; pairs defined; exclusion only on pre-run identity and infrastructure validity. **Capture and identity** (§4.1): usage accounted at `_llm_call` for every invocation including failed ones; the terminal decision stored structured; every assessment names its projection and registry versions and its evidence identity. **Vocabulary:** 1.8 gives Campaign *measures*, not grades. Two acceptance criteria added (§5). |

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
generalist agent on the same deterministic substrate, or at what cost. This SIP makes that claim
testable, and gives v2.0's Campaign Orchestration the measures its continuation policy reads
instead of raw checks. **The scorecard measures; Campaign decides.**

The 1.8 slice is four things, all mechanical:

- **(a) `CycleAssessment`**, a pure projection over durable evidence: the `CycleOutcome` seam and
  the stored records beside it. The evidence is durable; the assessment is derived and
  reproducible. It has four dimensions, and every indicator cites evidence that resolves.
- **(b) One failure-attribution registry.** Rev 1's seven categories become evidence classes
  derived from the failure vocabularies the code already has. Every source value has exactly one
  declared disposition, orthogonal facts compose by declared rules, and a drift test holds it.
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

**Three more decide a terminal state**, and a primary attribution must read them (§4.2):

| vocabulary | where | values |
|---|---|---|
| `CorrectionTerminationReason` | `src/squadops/cycles/task_outcome.py:90–93` | `plan_defect`, `exhausted`, `converged`, `infrastructure_failure` |
| `FailureClassification` | `task_outcome.py:34–42` — the analyzer's root-cause taxonomy (SIP-0079 §7.7), whose `work_product` and `execution` handlers also set deterministically and whose `contract_compliance` the executor sets | `execution`, `work_product`, `alignment`, `decision`, `model_limitation`, `contract_compliance` |
| `NotExecutedReason` | `verification_integrity.py:143–164` | `config_disabled`, `unsupported_stack`, `missing_tooling`, `subject_missing`, `import_error`, `filtered_out`, `timeout_before_execution`, `evaluator_gap:*`, `unspecified` |

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
and a measure the squad writes about itself is exactly what 2.0 must not act on. Every indicator is
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

**The run summary — per the review notes (§7 question 2).** At run finalization, beside
`run_verification_summaries`, the executor persists one durable row per run with the loop facts
no store holds today:
- **usage, accounted at the one LLM seam.** Every invocation `_llm_call` observes contributes
  exactly once: a generation with its calls, prompt, completion and reasoning tokens and duration,
  or an explicit failed-call record when the call raised before usage existed. That covers
  successful and contentless generations, emission retries, correction calls, the analyzer's and
  the lead's calls, and calls whose handler result then failed. The accumulator rides the task
  result on success and failure alike, and finalization sums it. **Undercounting failed or retried
  calls would make the worse arm look cheaper**, which is why a handler's success path is not the
  source;
- **refunded rounds**, with the refund reason (#1053);
- **the correction movement sequence**, per failed task;
- **the terminal decision, structured:** the correction termination reason, the failure
  classification and the task it decided, as values rather than the prose of `failure_reason`.

LangFuse remains the per-call drill-down, never the ledger. Historical cycles have no such row, so
those indicators are unaskable for them, never backfilled from logs.

**Attribution.** A non-accepted assessment carries one **primary** disposition and an ordered list
of **contributing** dispositions, both from the registry and its rules (§4.2). An accepted cycle
carries neither.

**Identity of the projection.** Every assessment names what produced it:
- `assessment_version`, the version of this projection's contract;
- `attribution_registry_version`;
- `evidence_identity`, a hash over its `CycleOutcome` and `CycleEvidence`;
- `assessor_identity`, the framework version and git sha that computed it.

**Computed on read, never stored as truth.** An assessment may be cached, keyed on its evidence
identity and the two versions; the stores remain the record. Two readings are distinct and never
confused: a **current re-grade** — historical evidence read by today's contract — and a
**decision-time assessment**, the one a consumer acted on. A consumer that acts, Campaign in 2.0,
records the identity and versions of the assessment it acted on; this SIP makes that possible
and stores nothing for it.

### 4.2 (b) One failure-attribution registry

**One module** (`src/squadops/cycles/failure_attribution.py`) owns every attribution class
literal, every source → disposition entry and every composition rule. **No attribution-class
literal and no source-to-attribution mapping exists outside it.** The source vocabularies stay
where they are authoritative, and consumers import the registry rather than re-deriving it.

**Classes name what the evidence shows, never a cause.** Rev 1's categories were causes ("the model
was the bottleneck"). Evidence cannot establish a cause, and Campaign will act on these values, so
a deterministic but unjustified causal label is worse than `unattributed`. Later analysis — a
person, an agent, Campaign, memory — may infer causes from these facts; the scorecard does not.

| class | the evidence shows | rev 1 category it replaces |
|---|---|---|
| `producer_output_failure` | a producer's artifact failed an executed criterion, the application under test failed it, or the emission had nothing extractable below its completion cap | `model_insufficiency` |
| `verification_artifact_failure` | the verifying artifact itself could not run or collect: the suite is the defect, not the subject | `validation_failure` |
| `handoff_or_convergence_failure` | emitted content was lost between emission and artifact, or a correction chain terminated as not progressing, or rounds moved without converging | `coordination_failure` |
| `input_contract_failure` | a task's inputs lacked what its contract required — **reserved**: no reachable evidence establishes it today, and the registry says so rather than manufacturing a mapping | `context_failure` |
| `budget_exhaustion` | a declared budget ran out: the completion cap with nothing extractable, the correction attempts, the run time budget | `resource_failure` |
| `plan_gate_failure` | the implementation plan was refused by a named plan validator | — (new: a plan refusal shows the framing output failed a gate, and neither a contract nor a handoff claim) |
| `criteria_or_contract_failure` | the authored manifest or its criteria were refused by a named winnability proof | `acceptance_criteria_failure` |
| `write_authority_violation` | a producer emitted outside its write grant past the compliance budget (SIP-0100 §3.4a) | — (new) |
| `environment_or_infrastructure_failure` | the environment failed before or around the product: sandbox pre-exec, verification infrastructure, missing tooling | `external_dependency_failure` |
| `unattributed` | the evidence establishes less than any class claims; counted and shown, never hidden | — |

**Totality over dispositions.** Every value of every source vocabulary (§2: eight vocabularies)
has exactly one declared **disposition** — `attribution(<class>)` or `non_failure` — and a
governance attribute `primary_eligible`. A drift test fails on an undeclared value or a value
declared twice. `non_failure` is a first-class declaration, not an exception: `new` and `progress`
are movements that are not failures, and `converged` is a termination that is not one.

**Dispositions — the review may change rows; the drift test holds whatever it rules:**

| vocabulary | value | disposition | primary-eligible |
|---|---|---|---|
| `FailureEvidenceCategory` | `executed_and_failed`, `app_error` | composed with locus (rule 5 below) | yes |
| | `extraction_loss` | `handoff_or_convergence_failure` | yes |
| | `emission_absent` | rule 3 below | yes |
| | `sandbox_preexec_failure`, `verification_infra_failure` | `environment_or_infrastructure_failure` | yes |
| | `evidence_unavailable` | `unattributed` | yes |
| `FailureLocus` | `own_artifact`, `subject`, `unknown` | composed with category (rule 5) — never attributed alone | — |
| plan validators | all fourteen | `plan_gate_failure` | yes |
| winnability proofs | all ten | `criteria_or_contract_failure` | yes |
| correction movement | `repeat`, `shifted`, `expansion` | `handoff_or_convergence_failure` | **no** — contributing only |
| | `new`, `progress` | `non_failure` | no |
| `CorrectionTerminationReason` | `exhausted` | `budget_exhaustion` | yes |
| | `plan_defect` | `handoff_or_convergence_failure` | yes |
| | `infrastructure_failure` | `environment_or_infrastructure_failure` | yes |
| | `converged` | `non_failure` | no |
| `FailureClassification` | `work_product` | `producer_output_failure` | yes |
| | `contract_compliance` | `write_authority_violation` | yes |
| | `execution` | `environment_or_infrastructure_failure` | yes |
| | `alignment`, `decision`, `model_limitation` | `unattributed` — each names a cause, and only the analyzer sets it | yes |
| `NotExecutedReason` | `missing_tooling`, `timeout_before_execution` | `environment_or_infrastructure_failure` | yes |
| | `subject_missing`, `import_error` | `producer_output_failure` | yes |
| | `config_disabled`, `unsupported_stack`, `filtered_out` | `non_failure` — declared non-execution by configuration | no |
| | `evaluator_gap:*`, `unspecified` | `unattributed` | yes |

**Provenance: only what the framework sets.** A `FailureClassification` is read only where the
framework set it deterministically — a handler's own `failure_classification` or the executor's
compliance termination. The analyzer's `classification` (`data.analyze_failure`) is an agent's
output and never an input, whichever value it names (§3.1).

**Composition — one failure event, facts from several vocabularies, one disposition.** Applied in
order; the first rule that matches decides:
1. **Environment first.** A sandbox pre-exec or verification-infrastructure category, or an
   `infrastructure_failure` termination, is `environment_or_infrastructure_failure`, whatever the
   locus says.
2. **Nothing to classify.** `evidence_unavailable` is `unattributed`.
3. **An absent emission.** `budget_exhaustion` when its marker shows the completion cap reached;
   otherwise `producer_output_failure`.
4. **Lost content.** `extraction_loss` is `handoff_or_convergence_failure`.
5. **An executed failure composes with its locus.** With `own_artifact` it is
   `verification_artifact_failure`; with `subject` it is `producer_output_failure`; with `unknown`
   it is `unattributed`. Category and locus are orthogonal, so neither is attributed alone.

**Primary — the terminal evidence of the final state transition.** Everything earlier is
contributing. Read in this order:

| the cycle's final state | primary disposition | contributing |
|---|---|---|
| a run refused at a plan gate | `plan_gate_failure` | the validators that refused |
| a run refused at the manifest gate | `criteria_or_contract_failure` | the proofs that failed |
| a correction chain terminated | the termination reason's disposition: `exhausted` → `budget_exhaustion`, `plan_defect` → `handoff_or_convergence_failure`, `infrastructure_failure` → environment | every round's failure events, composed, and the movement sequence |
| the compliance budget exceeded | `write_authority_violation` | the refused emissions |
| the run time budget exceeded | `budget_exhaustion` | the failure events up to it |
| completed, verdict `rejected` | the composed disposition of the failed required checks **if they all resolve to one class**; otherwise `unattributed` — never an arbitrary pick | every failed check's disposition |
| completed, verdict `blocked_unverified` | the dispositions of the required unverified checks' reasons, if one class; otherwise `unattributed` | every unverified reason's disposition |
| accepted | none | none |
| any other reachable state | `unattributed` | what the evidence holds |

The terminal state is read from the run summary's structured terminal decision (§4.1), never from
the prose of `failure_reason`. **Determinism:** contributing dispositions are ordered by run,
round, task id and check id, so the same evidence in any order yields the same assessment.

**Uncertainty is recorded, not normalized away.** When the evidence establishes less than a class
claims, the entry is `unattributed` until a stronger rule exists — the same discipline SIP-0096
applies to not-executed checks.

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
× model), and a pre-registration gains a comparison section. Both arms are measured by (a) with
attribution from (b).

**What the experiment is — per the review notes (§7 question 1).** A **system-level** comparison: the
complete SquadOps reasoning organization against one generalist agent, on the same deterministic
substrate. The **independent variable** is the reasoning organization — role decomposition, the
role-specific prompts, the framing roles, the handoffs, and agent-mediated correction by the
analyzer and the lead's decision. It does **not** isolate agent count or handoffs alone; that
topology-isolation experiment, one agent running every task with every stage prompt and correction
step kept, is a later window's.

**The question, in the record's words:** *under the same deterministic substrate and execution
envelope, does the squad improve outcome and quality over one generalist agent, and at what
additional or reduced token and wall-clock cost?* Total cost is **measured, not equalized**; the
efficiency delta is itself a result, and no claim is made that a squad "won at equal cost". The
answer is stated whichever way it goes. A negative is a result: it is 2.0's problem and the
thesis's, not the cut's.

**Registration before observation** (plan rev 4, §4.2). The comparison is designed in the loop
set's pre-registration, before any roll of either arm is observed. That design fixes which of the
loop set's React rolls form the squad arm, the pairs, the inclusion rules, N per arm, the
dimensions compared, the envelope below, and **the decision rule** — at N = 6 a count over pairs,
declared up front, never a rate read afterwards. That rule is specific to this experiment and is
not a `CycleAssessment` grade band (§3.2). The single-model arm runs after the loop set closes, on
the same frozen deploy if nothing has moved.

**Inclusion and exclusion read pre-run identity and infrastructure validity only, never outcome.**
A roll leaves the comparison only by the pre-registered void rule — the identity it ran on, or an
infrastructure defect named by that rule — and a void removes its pair. A failed or unflattering
roll cannot be removed because its partner later looks inconvenient.

**Pairs.** Pair *k* is the squad arm's *k*-th registered React roll and the generalist arm's
*k*-th roll, fixed at registration. Both run on the same PRD, the same stack, the same frozen
framework deploy and serving configuration, from a clean workspace with no cross-roll model
context. **Byte-identical inputs are the ones before any authored artifact** — the PRD, the
request-profile constants, the framework deploy. The scaffold is expanded from each arm's *own*
authored manifest, so it is not byte-identical; the rules that expand it are. Ollama sampling is
not seeded, so pairs are **matched trials, not replicas**, and the record says so.

**The substrate — held equal:**

| | both arms |
|---|---|
| **model and serving** | `qwen3.8:27b`, the same Ollama configuration and box |
| **the initial problem** | the PRD (`group_run`), the stack (FastAPI + React), the request profile's constants |
| **deterministic mechanics** | skeleton expansion, frozen files, write authorization, fill-slot integrity, verification-contract derivation, typed checks, the rendered container packaging (#598), patch acceptance, retests |
| **the loop's budgets** | emission retries, the correction attempt budget, repair targeting by the deterministic locus rules (register entry 36) |
| **the execution envelope** | the same run time budget (SIP-0079 RC-8); the same **effective per-task-type** completion caps and reasoning levels (below) |
| **gates** | the same gate, approved by the same fixed notes |

**Authority stays task-scoped.** A producer's write grant is derived from the task it performs
(`_producer_grants` reads the envelope's task type,
`src/squadops/cycles/scaffold_enforcement.py:120`), never from the agent. Assigning every task
to one agent therefore widens no grant and merges no ownership: performing a qa task, the
generalist holds the qa task's authority, and performing a builder task, the builder task's. The
comparison refuses to run if either arm's effective grants for a task type differ.

**Reasoning policy and caps are frozen per task type.** Reasoning is declared per task type and
output shape (`REASONING_BY_TASK_TYPE`), so the generalist running the same task types gets the same
levels by construction. **Per-call caps are not yet task-type-scoped:** `full-38` sets the qa
agent's `max_completion_tokens` to 12288 as an agent-level override. The generalist profile must
reproduce every such override for the task types it covers, and the pre-registration tables both
arms' effective cap and reasoning level per task type and asserts them equal.

**The independent variable — squad arm only:** strategy analysis, research context and plan review
by their roles; the role-specific prompts; the handoffs between roles; the analyzer
(`data.analyze_failure`) and the lead's correction decision. The generalist authors the manifest,
the application and the suite itself, with one generalist system prompt.

**What building the arm takes**, named so capacity is judged honestly: a `solo` squad profile of
one agent with the squad's per-task-type overrides reproduced, a request profile whose task plan
assigns every task to that agent, and the generalist prompt asset. No framework seam changes. This
is why (d) is first in the 1.8 plan's drop order.

---

## 5. Acceptance criteria — the slice

1. **(a)** `assess()` returns four dimensions of three-state indicators. An architecture test
   proves the projection does no I/O and reads only `CycleOutcome` and `CycleEvidence`. On every
   counted record of the 1.8 set, every observed indicator's evidence reference resolves.
2. **(a)** The run summary (usage, refunds, movement, the structured terminal decision) is
   persisted at run finalization for every run. A wiring test enters at the executor's
   finalization and asserts the row, and a second enters at `_llm_call` with a call that raises
   and asserts the failed-call record reaches it. Every assessment carries its projection and
   registry versions and its evidence identity.
3. **(b)** Every value of the eight source vocabularies has exactly one declared disposition,
   and the drift test fails on an undeclared or doubly-declared value. No attribution-class
   literal and no source-to-attribution mapping exists outside the registry (a guard test).
4. **(b) Attribution determinism.** For every reachable terminal-outcome fixture, the same
   evidence produces exactly one primary disposition and one ordered list of contributing
   dispositions, and permuting the evidence changes neither.
5. **(c)** The preflight names the re-gradeable rolls. The re-graded 1.7.5 rows match that
   record's table on verdict, criteria and correction rounds.
6. **(d) Comparison integrity.** For each registered pair, the inputs before any authored
   artifact are byte-identical, and the arms' effective task authority, per-task-type caps and
   reasoning levels are equal; they differ only by the pre-registered reasoning organization.
7. **(d)** The driver runs both arms under one comparison section, and one window closes with its
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

## 7. The design review — questions and the rulings its notes suggest

Rev 3 is written to the review notes' suggested rulings. They become rulings when the owner accepts.

1. **The single-model arm (§4.4) — accept with revision.** A system-level SquadOps-against-generalist
   comparison on an equal deterministic substrate, not an isolation experiment for agent count.
   Cost measured, not equalized. Task-scoped grants and per-task-type reasoning and caps identical.
2. **The run summary (§4.1) — take the durable row.** Usage populated from the `_llm_call`
   accounting seam, so failed and retried calls cannot disappear; LangFuse is not the ledger.
3. **The attribution mapping (§4.2) — revised before acceptance.** Evidence classes rather than
   causes; totality over dispositions; composition by declared precedence; terminal-primary against
   contributing; `unattributed` over unsupported inference; `non_failure` declared.
   `input_contract_failure` stays reserved.
4. **No grade bands in 1.8 (§3.2) — confirmed.** 1.8 measures distributions; 2.0 owns the stopping
   and continuation policy. The comparison's decision rule is experiment-specific, not a band.

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
