# SIP-0XXX: Wrap-Up Workload Protocol

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Updated:** 2026-03-05
**Revision:** 2

---

## 1. Abstract

This SIP defines the protocol for the **Wrap-Up Workload** — the terminal phase of a SquadOps Cycle that determines what was actually achieved, how confidently those outcomes can be trusted, and what should happen next. Wrap-up is not casual cleanup or narrative summarization. It functions as the adjudication layer that converts execution into operational memory, producing evidence-backed closeout artifacts, confidence classifications, and next-cycle handoff packages.

The SIP is the fifth in the Spark-critical sequence (after SIP-0076 Workload & Gate Canon, SIP-0077 Cycle Event System, SIP-0078 Planning Workload Protocol, SIP-0079 Implementation Run Contract & Correction Protocol) and must land before the first local validation milestone.

---

## 2. Terminology

| Term | Definition |
|------|-----------|
| **Wrap-Up Workload** | A run with `workload_type = "wrapup"` that adjudicates the prior implementation run and packages results for operator review and next-cycle planning. |
| **Closeout Artifact** | The primary output of a wrap-up run — a structured, evidence-backed summary of what was achieved, at what confidence, with what remains unresolved. Stored as a run-level artifact of type `document`. |
| **Confidence Classification** | A six-level assessment of how trustworthy the implementation run's outcomes are, from `verified_complete` to `failed`. |
| **Handoff Artifact** | A structured artifact that packages unfinished work, risks, and recommendations for the next cycle. Consumed by the next planning phase. |
| **Quality Reconciliation** | The process of cross-referencing implementation outputs against acceptance criteria, QA findings against completion claims, and RCA records against final status. |
| **Evidence Inventory** | A compiled list of all available artifacts, test results, plan deltas, corrections, and operator interventions from the implementation run, with completeness assessment. |
| **Planned-vs-Actual Comparison** | Explicit accounting of what was planned, what was done, what changed, and whether changes were intentional — mandatory in every closeout artifact. |
| **Closeout Gate** | The `progress_wrapup_review` gate at which the operator reviews the closeout artifact and decides whether the cycle is complete. |

---

## 3. Problem Statement

A long implementation run can produce code, tests, notes, logs, retries, partial fixes, and operator interventions, yet still fail to produce a trustworthy close. Without a defined wrap-up protocol, the platform risks:

- Completion claims that are not supported by evidence.
- Summary artifacts that bury caveats or deviations.
- Inability to distinguish planned work from drifted work.
- Weak carry-forward into the next cycle — the next planning phase starts with avoidable ambiguity.
- Operator review that depends on raw logs rather than decision-grade closeout artifacts.

If planning authorizes implementation, wrap-up authorizes memory. The wrap-up run determines whether the prior hours of execution become durable value or expensive ambiguity.

**Specific infrastructure gaps in the current platform (v0.9.17):**

1. **No wrap-up workload type** — `WorkloadType` has `PLANNING`, `IMPLEMENTATION`, `EVALUATION`, `REFINEMENT` but no wrap-up. The cycle execution pipeline ends after implementation without structured adjudication.
2. **No confidence classification** — the platform has no model for expressing how trustworthy a run's outcomes are beyond binary pass/fail.
3. **No structured unresolved issue tracking** — unresolved items live in prose within artifacts, not as categorized, queryable records.
4. **No planned-vs-actual comparison** — the platform stores plan deltas (SIP-0079) but does not require or produce an explicit reconciliation of planned scope against actual outcomes.
5. **No next-cycle handoff** — when a cycle ends, the next cycle starts without structured carry-forward of what remains, what failed, and what should not be retried.

---

## 4. Design Principles

### 4.1 Wrap-up is adjudication, not narration

The deliverable is a decision-grade closeout artifact, not a narrative summary. Wrap-up must answer three questions: What exactly was produced? How sure are we? What should happen next? If the closeout reads like a transcript, it has failed.

### 4.2 Non-success is a valid outcome

If wrap-up always emits a polished victory narrative, it is not trustworthy. "Implementation produced but not sufficiently verified" is a legitimate classification. The confidence model has six levels precisely because most real outcomes are not binary.

### 4.3 Missing evidence lowers confidence, never silently compensated

When required inputs are missing or inconsistent, wrap-up explicitly lowers the confidence classification and records the gap. It does not fill holes with optimistic assumptions or produce a higher confidence level than the evidence supports.

### 4.4 Wrap-up is bounded analysis, not a convergence loop

Unlike implementation (which has a dev/test/fix convergence loop), wrap-up is a single-pass analysis with a fixed task sequence. There is no correction protocol for wrap-up — if a handler fails, normal retry handles it. If the wrap-up run fails entirely, the operator investigates and may create a new wrap-up run.

### 4.5 Evidence reconciliation is cross-cutting

Wrap-up does not assess each artifact in isolation. It reconciles evidence across the whole cycle — implementation outputs vs acceptance criteria, QA findings vs completion claims, RCA records vs final status, open risks vs recommendation to proceed.

---

## 5. Goals

1. Define a **Wrap-Up Workload contract** — purpose, required inputs, required outputs, validation expectations, and what constitutes cycle-closed vs partial-close vs failed-close.
2. Establish a **standard closeout artifact** structure with YAML frontmatter that a human can review without reconstructing the run from logs.
3. Require **planned-vs-actual comparison** — explicit accounting of what was planned, what was done, what changed, and whether changes were intentional.
4. Require **evidence-backed completion claims** — assertions of completion must cite supporting evidence (passed tests, build outputs, file diffs, verification results).
5. Introduce a **confidence classification model** as a constants class: `verified_complete`, `complete_with_caveats`, `partial_completion`, `not_sufficiently_verified`, `inconclusive`, `failed`.
6. Define **structured unresolved issues** with constants classes for type (7 categories) and severity (4 levels), plus impact, owner, and recommended next action.
7. Produce a **next-cycle handoff artifact** with structured carry-forward items and a recommended next cycle type.
8. Define **wrap-up-specific task steps and handlers** that integrate into the existing task plan generator and executor pipeline.
9. Define **wrap-up-specific pulse check suites** using the existing SIP-0070 framework.
10. Integrate with the **existing gate mechanism** for operator review at closeout.

---

## 6. Non-Goals

- Defining the implementation or planning workload protocols (separate SIPs, already implemented).
- Multi-workload orchestration — automatic sequencing of planning → implementation → wrap-up. This SIP defines what happens *within* a wrap-up workload; the pipeline that chains workloads is a separate concern. In 1.0, operators manually create wrap-up runs.
- Richer scoring models or historical comparison across closeouts (1.1+).
- Automatic trend analysis across multiple cycles (1.1+).
- Advanced memory summarization into LanceDB (1.1+).
- Autonomous improvement proposals based on repeated failures (1.1+).
- Defining the scorecard evaluation framework (covered by the Cycle Evaluation Scorecard SIP).
- New executor logic — wrap-up workloads use the existing sequential dispatch, prior-output chaining, pulse check evaluation, and gate pause/resume mechanisms.
- Auto-generating draft cycle requests for the next cycle from the handoff artifact (1.1+).

---

## 7. Design

### 7.1 Wrap-Up Task Steps

The wrap-up workload uses a 5-step task sequence. Each step maps a `task_type` to a role, following the existing `PLANNING_TASK_STEPS` / `IMPLEMENTATION_TASK_STEPS` pattern.

```python
WRAPUP_TASK_STEPS: list[tuple[str, str]] = [
    ("data.gather_evidence", "data"),             # Gather and reconcile inputs
    ("qa.assess_outcomes", "qa"),                 # Planned vs actual, acceptance assessment
    ("data.classify_unresolved", "data"),          # Categorize unresolved items
    ("governance.closeout_decision", "lead"),      # Confidence classification, closeout artifact
    ("governance.publish_handoff", "lead"),        # Next-cycle handoff artifact
]
```

**Placement:** `src/squadops/cycles/task_plan.py` (alongside existing step constants)

The sequence is intentional:
1. **Data first** — gathers all available evidence (artifacts, test results, plan deltas, corrections) and produces an evidence inventory with completeness assessment.
2. **QA second** — compares planned vs actual scope, evaluates acceptance criteria, identifies deviations and evidence gaps. QA is the independent verification voice.
3. **Data third** — categorizes unresolved items using structured types and severities. Data sees the full evidence inventory and QA's assessment to produce a complete issue registry.
4. **Lead fourth** — synthesizes all prior outputs into the closeout artifact with confidence classification and readiness recommendation.
5. **Lead fifth** — produces the next-cycle handoff artifact from the closeout decision, packaging carry-forward items for the next planning phase.

Required roles for wrap-up:

```python
REQUIRED_WRAPUP_ROLES = frozenset({"data", "qa", "lead"})
```

**Placement:** `src/squadops/cycles/models.py` (alongside existing `REQUIRED_PLAN_ROLES`, `REQUIRED_REFINEMENT_ROLES`)

Strategy (`strat`) and Dev (`dev`) are intentionally excluded. Wrap-up is adjudication — it assesses what happened, it does not propose strategy or produce code. Including Dev or Strategy would risk turning wrap-up into a continuation of implementation.

### 7.2 Wrap-Up Handlers

Five new handler classes, all extending `_CycleTaskHandler`. Each follows the existing pattern: LLM call with role-specific system prompt, prior outputs as context, single artifact output.

| Handler Class | `capability_id` | Role | Artifact | Purpose |
|--------------|-----------------|------|----------|---------|
| `DataGatherEvidenceHandler` | `data.gather_evidence` | data | `evidence_inventory.md` | Collect and reconcile all available evidence from the implementation run |
| `QAAssessOutcomesHandler` | `qa.assess_outcomes` | qa | `outcome_assessment.md` | Compare planned vs actual, evaluate acceptance criteria, identify deviations |
| `DataClassifyUnresolvedHandler` | `data.classify_unresolved` | data | `unresolved_items.md` | Categorize unresolved issues with type, severity, impact, owner, next action |
| `GovernanceCloseoutDecisionHandler` | `governance.closeout_decision` | lead | `closeout_artifact.md` | Synthesize closeout artifact with confidence classification and recommendation |
| `GovernancePublishHandoffHandler` | `governance.publish_handoff` | lead | `handoff_artifact.md` | Produce next-cycle handoff artifact with structured carry-forward items |

All 5 handlers live in `src/squadops/capabilities/handlers/wrapup_tasks.py`, following the existing `planning_tasks.py` module pattern.

### 7.3 Handler Input/Output Chain

Each handler receives `prior_outputs` from upstream handlers (same chaining as existing cycle tasks):

- `data.gather_evidence` receives: implementation run artifacts (via `execution_overrides.impl_run_id`), run contract, planning artifact, plan deltas, test results, correction records
- `qa.assess_outcomes` receives: Data's evidence inventory + implementation artifacts
- `data.classify_unresolved` receives: Data's evidence inventory + QA's outcome assessment
- `governance.closeout_decision` receives: all 3 prior outputs (evidence inventory, outcome assessment, unresolved items)
- `governance.publish_handoff` receives: all 4 prior outputs (including closeout artifact)

**Required inputs for wrap-up:**

The wrap-up run is created with `execution_overrides` referencing the implementation run:

```json
{
    "impl_run_id": "<implementation_run_id>",
    "plan_artifact_refs": ["<planning_artifact_id>"]
}
```

The `data.gather_evidence` handler uses these references to access artifacts from the implementation run via the artifact vault. The handler does not query artifacts directly — it receives pre-resolved artifact content via `inputs["artifact_contents"]`, following the existing build task artifact pre-resolution pattern (SIP-0068).

**Pre-resolution ownership:** Artifact pre-resolution is performed by the **executor** in `_execute_sequential()`, following the SIP-0068 pattern where `_BUILD_ARTIFACT_FILTER` maps task types to prior artifact selections. For wrap-up, the executor resolves artifacts from the run referenced by `execution_overrides.impl_run_id` and injects them into `inputs["artifact_contents"]` before dispatching `data.gather_evidence`. If pre-resolution fails (e.g., `impl_run_id` references a non-existent run), the executor injects an empty `artifact_contents` dict — `data.gather_evidence` then runs in degraded mode, recording "evidence unavailable" in the inventory rather than failing the task. This is consistent with D5 (missing evidence lowers confidence, never fails the run).

**Implementation run precondition:** The wrap-up run requires a valid `impl_run_id` in `execution_overrides`. The referenced implementation run must be in a terminal or paused state (`COMPLETED`, `FAILED`, `CANCELLED`, `PAUSED`). If the implementation run is still `RUNNING` or `PENDING_GATE`, wrap-up run creation is rejected — wrapping up a moving target would produce unreliable results. This validation is performed at the API route layer when the wrap-up run is created, before task dispatch.

**Handling missing inputs:** If implementation artifacts are missing or inaccessible, the `data.gather_evidence` handler records the gap in the evidence inventory rather than failing. Downstream handlers use the completeness assessment from the evidence inventory to lower confidence accordingly (§4.3).

### 7.4 Confidence Classification Model

```python
class ConfidenceClassification:
    """Confidence classification for wrap-up closeout decisions.

    Follows the constants-class pattern (WorkloadType, ArtifactType, EventType).
    """

    VERIFIED_COMPLETE = "verified_complete"
    COMPLETE_WITH_CAVEATS = "complete_with_caveats"
    PARTIAL_COMPLETION = "partial_completion"
    NOT_SUFFICIENTLY_VERIFIED = "not_sufficiently_verified"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
```

**Placement:** `src/squadops/cycles/wrapup_models.py`

| Classification | Meaning | Typical Evidence |
|----------------|---------|-----------------|
| `verified_complete` | All acceptance criteria met with supporting evidence | All tests pass, all artifacts produced, no unresolved blockers |
| `complete_with_caveats` | Core objectives met; minor gaps or untested edges remain | Most tests pass, primary artifacts produced, minor unresolved items |
| `partial_completion` | Some objectives met; significant work remains | Subset of acceptance criteria met, key deliverables missing |
| `not_sufficiently_verified` | Artifacts exist but validation is insufficient to confirm quality | Code produced but tests incomplete, build not verified |
| `inconclusive` | Cannot determine outcome from available evidence | Evidence too sparse for assessment (e.g., many missing inputs) |
| `failed` | Core objectives not met | Primary acceptance criteria failed, critical blockers unresolved |

The classification is assigned by the Lead agent in the `governance.closeout_decision` handler based on the evidence inventory, QA outcome assessment, and unresolved item registry. Automated classification is a 1.1 consideration.

### 7.5 Unresolved Issue Model

Two constants classes define the structured taxonomy for unresolved items:

```python
class UnresolvedIssueType:
    """Type classification for unresolved items in wrap-up.

    Follows the constants-class pattern.
    """

    DEFECT = "defect"
    DESIGN_DEBT = "design_debt"
    TEST_GAP = "test_gap"
    ENVIRONMENTAL = "environmental"
    DEPENDENCY = "dependency"
    OPERATOR_DECISION_PENDING = "operator_decision_pending"
    DEFERRED_ENHANCEMENT = "deferred_enhancement"


class UnresolvedIssueSeverity:
    """Severity classification for unresolved items.

    Follows the constants-class pattern.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

**Placement:** `src/squadops/cycles/wrapup_models.py` (alongside `ConfidenceClassification`)

Each unresolved item in the `unresolved_items.md` artifact includes:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | One of `UnresolvedIssueType` constants |
| `severity` | Yes | One of `UnresolvedIssueSeverity` constants |
| `description` | Yes | What the issue is |
| `impact` | Yes | What is affected if not resolved |
| `suggested_owner` | Yes | Who should address it — one of the controlled values below |
| `recommended_action` | Yes | Specific guidance for resolution |
| `evidence_refs` | No | Artifact IDs or file paths supporting the classification |

**Allowed `suggested_owner` values:** `lead`, `qa`, `dev`, `data`, `strat`, `builder`, `operator`. The first 6 are agent roles; `operator` indicates a human decision is required. This is advisory — it informs the next cycle's planning phase but is not enforced by the platform.

### 7.6 Closeout Recommendation Model

```python
class CloseoutRecommendation:
    """Readiness recommendation for the closeout artifact.

    Follows the constants-class pattern.
    """

    PROCEED = "proceed"        # Implementation is sufficiently complete; move forward
    HARDEN = "harden"          # Artifacts exist but need dedicated verification cycle
    REPLAN = "replan"          # Significant gaps or drift; return to planning
    HALT = "halt"              # Critical issues; do not continue without operator decision
```

**Placement:** `src/squadops/cycles/wrapup_models.py`

The `CloseoutRecommendation` is distinct from `NextCycleRecommendation` (§7.7). The closeout recommendation answers "what should the operator do right now?" while the next-cycle recommendation answers "what type of cycle should follow?" They may differ — an operator may `proceed` even when the recommended next cycle type is `hardening`.

The `readiness_recommendation` field is added to the closeout artifact YAML frontmatter (§7.8) as a machine-parseable value from this controlled vocabulary.

### 7.7 Next-Cycle Recommendation Model

```python
class NextCycleRecommendation:
    """Recommended next cycle type for handoff artifact.

    Follows the constants-class pattern.
    """

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    HARDENING = "hardening"
    RESEARCH = "research"
    NONE = "none"  # Cycle fully complete, no follow-up needed
```

**Placement:** `src/squadops/cycles/wrapup_models.py`

| Recommendation | When to use |
|----------------|-------------|
| `planning` | Significant scope changes or unresolved design questions require replanning |
| `implementation` | Core objective partially met; clear path forward for remaining work |
| `hardening` | Code produced but insufficient verification; needs dedicated QA/testing cycle |
| `research` | Fundamental unknowns discovered; needs investigation before further implementation |
| `none` | All objectives met, no follow-up required |

### 7.8 Standard Closeout Artifact

The closeout artifact (`closeout_artifact.md`) is the canonical output of the wrap-up workload. It is produced by the `governance.closeout_decision` handler and stored in the artifact vault with `artifact_type="document"` and `producing_task_type="governance.closeout_decision"`.

The artifact uses markdown with YAML frontmatter for machine-parseable metadata:

```markdown
---
confidence: verified_complete | complete_with_caveats | partial_completion | not_sufficiently_verified | inconclusive | failed
readiness_recommendation: proceed | harden | replan | halt
next_cycle_recommendation: planning | implementation | hardening | research | none
acceptance_criteria_met: 4
acceptance_criteria_total: 5
unresolved_count: 2
unresolved_critical: 0
unresolved_high: 1
plan_deltas_count: 1
corrections_count: 0
evidence_completeness: complete | partial | sparse
scope_baseline_source: run_contract | planning_artifact
---

# Closeout Artifact: {cycle objective}

## 1. Cycle Objective
[Original objective from run contract / planning artifact]

## 2. Planned vs Completed Scope

### Planned
[Scope items from planning artifact / run contract]

### Completed
[What was actually delivered, with evidence references]

### Not Completed
[What was planned but not delivered, with explanation]

### Scope Changes
[Items added or removed during implementation, with intentionality assessment]
- [change description] — **intentional** / **drift** — [reason]

## 3. Implementation Summary
[Concise summary of what was built, not a transcript of every task]

## 4. Validation Summary
[Test results, build verification, acceptance criteria assessment]

| Acceptance Criterion | Status | Evidence |
|---------------------|--------|----------|
| [criterion from plan] | met / not met / partially met | [artifact ref, test name, or observation] |

## 5. Deviations from Plan
[Deviations with intentionality assessment — was this planned change or drift?]

### Plan Deltas
[Summary of plan deltas recorded during implementation (SIP-0079)]

### Corrections
[Summary of correction protocol activations, paths chosen, outcomes]

## 6. Unresolved Issues

| # | Type | Severity | Description | Impact | Owner | Recommended Action |
|---|------|----------|-------------|--------|-------|-------------------|
| 1 | defect | high | [description] | [impact] | [role] | [action] |

## 7. Risk Assessment
[Outstanding risks that affect the recommendation]

## 8. Confidence Classification

**Classification: {CONFIDENCE_LEVEL}**

[Justification based on evidence completeness, acceptance criteria results, unresolved items, and plan adherence]

## 9. Readiness Recommendation

**Recommendation: {proceed / harden / replan / halt}** (from `CloseoutRecommendation` §7.6)

[What the operator should do next, based on confidence and unresolved items]

## 10. Next-Cycle Recommendation

**Recommended next cycle type: {planning / implementation / hardening / research / none}**

[Why this cycle type is appropriate given the current state]

## 11. Artifact Index

| Artifact | Type | Producing Task | Notes |
|----------|------|---------------|-------|
| [name] | [type] | [task_type] | [status/notes] |
```

#### Planned-vs-Actual Scope Baseline Precedence

Three inputs can define "what was planned," and they may disagree. The precedence rule:

1. **Run contract** (SIP-0079) is the canonical scope baseline if present — it was generated from the planning artifact at implementation start and captures the objective, acceptance criteria, and non-goals as contractual commitments.
2. **Planning artifact** (SIP-0078) is the fallback if no run contract exists (e.g., cycles that ran without the implementation workload protocol).
3. **Plan deltas** (SIP-0079) are layered on top of the baseline — scope changes justified by a plan delta are classified as **intentional**; scope changes without a corresponding plan delta are classified as **drift**.

If the run contract and planning artifact disagree (e.g., the contract narrowed scope from the original plan), the closeout must call out the disagreement explicitly and use the run contract as the operative baseline. The `scope_baseline_source` frontmatter field records which source was used (`run_contract` or `planning_artifact`).

#### Evidence Completeness Rubric

The `evidence_completeness` frontmatter field uses a deterministic rubric based on four required evidence categories:

| Category | What constitutes "present" |
|----------|--------------------------|
| Planning artifact or run contract | At least one is accessible and non-empty |
| Implementation artifacts | At least one source/document artifact from the implementation run |
| Test results | Test output or QA validation artifact present |
| Plan deltas or correction records | Accessible (may be empty if no corrections occurred — empty is valid, missing/inaccessible is not) |

| Completeness Level | Definition |
|-------------------|------------|
| `complete` | All 4 categories present |
| `partial` | Exactly 1 category missing or unreadable |
| `sparse` | 2 or more categories missing or unreadable |

This rubric is applied by the `data.gather_evidence` handler and recorded in the evidence inventory. The `governance.closeout_decision` handler copies it to the closeout artifact frontmatter.

#### Acceptance Criteria Counting Rules

The `acceptance_criteria_met` and `acceptance_criteria_total` frontmatter fields follow these rules:

- **Canonical source:** The acceptance criteria list from the **run contract** (if present), otherwise from the **planning artifact**'s acceptance checklist (SIP-0078 §5.5).
- **Counting:** `partially_met` counts as **not met** in `acceptance_criteria_met`. This prevents inflated completion metrics.
- **Missing AC list:** If neither run contract nor planning artifact contains an acceptance criteria list, set both fields to `0` and force `confidence` to `inconclusive` or `not_sufficiently_verified` — a cycle without defined acceptance criteria cannot be `verified_complete`.

### 7.9 Next-Cycle Handoff Artifact

The handoff artifact (`handoff_artifact.md`) is produced by the `governance.publish_handoff` handler. It is the input for the next cycle's planning phase — a structured, actionable package that prevents the next cycle from starting with avoidable ambiguity.

```markdown
---
source_cycle_id: "{cycle_id}"
source_run_id: "{run_id}"
confidence: "{confidence_classification}"
next_cycle_type: planning | implementation | hardening | research | none
carry_forward_count: 3
stable_count: 5
do_not_retry_count: 1
---

# Next-Cycle Handoff: {cycle objective}

## 1. What Is Stable
[Completed work that can be relied upon in the next cycle]

## 2. What Remains Unfinished
[Unresolved items carried forward, with context from closeout]

| # | Description | Type | Severity | Recommended Approach |
|---|-------------|------|----------|---------------------|
| 1 | [description] | [type] | [severity] | [approach for next cycle] |

## 3. What Should Happen Next
[Specific, actionable recommendations for the next cycle]

## 4. What Should Not Be Retried Blindly
[Approaches that were attempted and failed — avoid repeating without changes]

| Approach | Why It Failed | Alternative |
|----------|--------------|-------------|
| [approach] | [failure reason] | [suggested alternative] |

## 5. Risks Needing Dedicated Attention
[Risks that the next cycle must explicitly address]

## 6. Recommended Next Cycle Configuration
[Suggestions for cycle type, profile, and focus areas — informational, not auto-applied]
```

The handoff artifact is stored with `artifact_type="document"` and `producing_task_type="governance.publish_handoff"`. It does NOT auto-generate a draft cycle request — in 1.0, the operator creates the next cycle manually using the handoff as input.

### 7.10 Quality Reconciliation

Quality reconciliation is not a separate handler or mechanism — it is the core responsibility of the `qa.assess_outcomes` handler. The handler cross-references evidence across the whole cycle rather than assessing artifacts in isolation:

| Comparison | What it detects |
|-----------|----------------|
| Implementation outputs vs acceptance criteria | Are claims of completion actually evidenced? |
| QA findings vs completion claims | Do test results support or contradict the implementation summary? |
| RCA records vs final status | Were identified root causes actually resolved, or just acknowledged? |
| Plan deltas vs scope changes | Were deviations intentional (with plan deltas) or untracked drift? |
| Open risks vs recommendation to proceed | Is the recommendation honest given known risks? |

This is where the squad proves it can judge the run rather than merely narrate it.

### 7.11 Wrap-Up Gate Protocol

The wrap-up workload concludes with a gate (`progress_wrapup_review`) that uses the existing `GateDecisionValue` enum from SIP-0076:

| Gate Decision | Meaning | What Happens |
|--------------|---------|--------------|
| `approved` | Closeout accepted, cycle complete | Cycle transitions to completed |
| `returned_for_revision` | Closeout needs rework | Create new wrap-up run with feedback notes |
| `rejected` | Closeout rejected, cycle incomplete | Cycle remains open for operator decision |

**Cycle-close semantics:** When `progress_wrapup_review` is `approved`, the wrap-up run transitions to `COMPLETED` via `registry.update_run_status()`. `derive_cycle_status()` then derives the cycle's status from its runs — if the wrap-up run is the final run and all prior runs are in terminal states, the cycle derives as `COMPLETED`. The cycle-level transition is emergent (computed by `derive_cycle_status()`), not an explicit registry call. This means the wrap-up gate approval effectively closes the cycle, but through the existing status derivation mechanism rather than a separate "close cycle" API.

The `approved_with_refinements` gate decision is NOT used for wrap-up in 1.0. If the operator wants changes to the closeout, they return for revision — the wrap-up sequence is short enough that a full re-run is acceptable. Wrap-up refinement is a 1.1 consideration.

**Operator review actions** map to gate decisions:

| Operator Action | Gate Decision | Notes |
|----------------|---------------|-------|
| Accept closeout | `approved` | Cycle closes normally |
| Request clarification | `returned_for_revision` | Feedback in gate `notes` field |
| Request revised classification | `returned_for_revision` | Feedback specifies classification concern |
| Request further validation | `returned_for_revision` | Feedback specifies what needs validation |
| Reject closeout | `rejected` | Cycle does not close; operator decides next step |

### 7.12 Wrap-Up Pulse Check Suites

Wrap-up-specific pulse checks use the existing SIP-0070 framework. Two milestone-bound suites monitor for common wrap-up failure modes:

#### Suite 1: `wrapup_evidence_guard` (post-evidence-gathering)

Fires after `data.gather_evidence` completes. Verifies the evidence inventory exists and is non-empty.

```yaml
- suite_id: wrapup_evidence_guard
  boundary_id: post_evidence
  binding_mode: milestone
  after_task_types:
    - data.gather_evidence
  checks:
    - check_type: file_exists
      target: "{run_root}/evidence_inventory.md"
    - check_type: non_empty
      target: "{run_root}/evidence_inventory.md"
  max_suite_seconds: 15
  max_check_seconds: 5
```

#### Suite 2: `wrapup_completeness` (post-closeout)

Fires after `governance.closeout_decision` completes. Verifies the closeout artifact exists and is non-empty.

```yaml
- suite_id: wrapup_completeness
  boundary_id: post_closeout
  binding_mode: milestone
  after_task_types:
    - governance.closeout_decision
  checks:
    - check_type: file_exists
      target: "{run_root}/closeout_artifact.md"
    - check_type: non_empty
      target: "{run_root}/closeout_artifact.md"
  max_suite_seconds: 15
  max_check_seconds: 5
```

Wrap-up pulse checks in 1.0 are intentionally structural — they verify artifact presence and completeness, not semantic quality. Semantic assessment (is the closeout honest? are caveats surfaced?) is the responsibility of handler output plus operator review at the closeout gate. Content-level pulse checks (e.g., "does the closeout contain unresolved issues if QA flagged them?") are a 1.1 enhancement.

### 7.13 Cycle Request Profile

A new cycle request profile provides the default configuration for wrap-up workloads:

**`wrapup.yaml`**:

```yaml
name: wrapup
description: "Wrap-up workload with closeout review gate"
defaults:
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: progress_wrapup_review
        description: "Review closeout artifact before cycle completion"
        after_task_types:
          - governance.publish_handoff
  expected_artifact_types:
    - document
  workload_sequence:
    - type: wrapup
      gate: progress_wrapup_review
  pulse_checks:
    - suite_id: wrapup_evidence_guard
      boundary_id: post_evidence
      binding_mode: milestone
      after_task_types:
        - data.gather_evidence
      checks:
        - check_type: file_exists
          target: "{run_root}/evidence_inventory.md"
        - check_type: non_empty
          target: "{run_root}/evidence_inventory.md"
      max_suite_seconds: 15
      max_check_seconds: 5
    - suite_id: wrapup_completeness
      boundary_id: post_closeout
      binding_mode: milestone
      after_task_types:
        - governance.closeout_decision
      checks:
        - check_type: file_exists
          target: "{run_root}/closeout_artifact.md"
        - check_type: non_empty
          target: "{run_root}/closeout_artifact.md"
      max_suite_seconds: 15
      max_check_seconds: 5
  cadence_policy:
    max_pulse_seconds: 3600
    max_tasks_per_pulse: 5
  experiment_context: {}
  notes: "Wrap-up workload cycle"
```

The `workload_sequence` in `wrapup.yaml` is informational only in 1.0. Multi-workload orchestration (automatic progression from implementation to wrap-up) is a separate SIP. In 1.0, operators manually create wrap-up runs after the implementation run completes.

### 7.14 Task Plan Generator Changes

The `generate_task_plan()` function in `src/squadops/cycles/task_plan.py` gains a new `elif` branch for wrap-up workloads:

```python
def generate_task_plan(cycle, run, profile):
    if run.workload_type == WorkloadType.PLANNING:
        steps = PLANNING_TASK_STEPS
    elif run.workload_type == WorkloadType.REFINEMENT:
        steps = REFINEMENT_TASK_STEPS
    elif run.workload_type == WorkloadType.IMPLEMENTATION:
        if _has_builder_role(profile):
            steps = BUILDER_ASSEMBLY_TASK_STEPS
        else:
            steps = BUILD_TASK_STEPS
    elif run.workload_type == WorkloadType.WRAPUP:          # New
        steps = WRAPUP_TASK_STEPS                            # New
    else:
        # Legacy: no workload_type → use plan_tasks/build_tasks flags
        ...  # existing logic unchanged
```

When `workload_type == "wrapup"`, the generator selects `WRAPUP_TASK_STEPS` and validates that `REQUIRED_WRAPUP_ROLES` are present in the cycle's role roster.

### 7.15 Executor Integration

No changes to `DistributedFlowExecutor`. The existing executor pipeline handles wrap-up workloads identically to planning workloads:

- **Sequential dispatch** — tasks execute in order. The 5-step wrap-up chain builds progressively.
- **Prior-output chaining** — each handler receives outputs from all prior handlers via `prior_outputs` dict.
- **Artifact storage** — handler artifacts stored via the vault with `producing_task_type` metadata.
- **Artifact pre-resolution** — implementation run artifacts are pre-resolved into handler inputs via `execution_overrides.impl_run_id`, following the SIP-0068 pattern.
- **Pulse check evaluation** — milestone bindings resolve against wrap-up task types (`data.gather_evidence`, `governance.closeout_decision`).
- **Gate pause/resume** — `progress_wrapup_review` fires after `governance.publish_handoff`. The executor pauses the run and waits for a gate decision.
- **Checkpoint/resume** — wrap-up runs automatically benefit from SIP-0079 checkpoint infrastructure. If interrupted, they can be resumed from the last completed task.
- **Event emission** — SIP-0077 events are emitted for all wrap-up task dispatches, successes, failures, pulse checks, and gate decisions. No new event types needed.

The only code that changes is the task plan generator (§7.14), which selects the right steps based on `workload_type`. This matches the pattern established by SIP-0078 (D11: no executor changes for planning workloads).

### 7.16 Event Taxonomy

No new `EventType` constants are needed. Wrap-up runs emit the existing lifecycle events:

- `RUN_STARTED` / `RUN_COMPLETED` / `RUN_FAILED` for run lifecycle
- `TASK_DISPATCHED` / `TASK_SUCCEEDED` / `TASK_FAILED` for each handler
- `PULSE_BOUNDARY_REACHED` / `PULSE_SUITE_EVALUATED` for pulse checks
- `GATE_DECIDED` for the closeout gate
- `ARTIFACT_STORED` for each produced artifact (evidence inventory, outcome assessment, unresolved items, closeout artifact, handoff artifact)
- `CHECKPOINT_CREATED` at each task boundary (SIP-0079 infrastructure)

The confidence classification is captured within the closeout artifact and its YAML frontmatter — it does not need a separate event type. Bridges (LangFuse, Prefect, Metrics) handle wrap-up events via existing generic handlers.

### 7.17 API and CLI Surface

No new API routes or CLI commands are needed. Wrap-up uses existing platform mechanisms:

| Operation | Mechanism |
|-----------|-----------|
| Create wrap-up run | `POST /runs` with `workload_type=wrapup` + `execution_overrides` |
| View closeout artifact | `GET /runs/{run_id}/artifacts` (standard artifact API) |
| Review closeout | `POST /gates/{gate_name}/decide` (standard gate API) |
| CLI: create wrap-up run | `squadops runs create <project> <cycle_id> --workload-type wrapup` |
| CLI: view artifacts | `squadops artifacts list <project> <cycle_id> <run_id>` |
| CLI: decide gate | `squadops gate decide <project> <cycle_id> <run_id> <gate_name> --approve` |

This matches SIP-0078's approach — no new API routes for planning workloads either.

### 7.18 Role Expectations

Each role has specific responsibilities within the wrap-up workload:

**Data (data.gather_evidence, data.classify_unresolved)**
- Compile evidence inventory from implementation run artifacts
- Assess completeness — identify missing or inaccessible evidence
- Categorize unresolved items using structured type and severity constants
- Link each unresolved item to supporting evidence
- Do NOT interpret or judge outcomes — that is QA's and Lead's responsibility

**QA (qa.assess_outcomes)**
- Compare planned scope against actual deliverables
- Evaluate each acceptance criterion (met / not met / partially met) with evidence
- Identify deviations from plan and classify intentionality
- Cross-reference QA findings against implementation claims
- Challenge completion claims that lack supporting evidence
- Do NOT set the confidence classification — that is Lead's responsibility

**Lead (governance.closeout_decision, governance.publish_handoff)**
- Synthesize all prior outputs into the closeout artifact
- Assign confidence classification based on evidence, QA assessment, and unresolved items
- Issue readiness recommendation (proceed / harden / replan / halt)
- Produce the handoff artifact with actionable carry-forward items
- If evidence is sparse, classify as `inconclusive` or `not_sufficiently_verified` — do not compensate

---

## 8. Backwards Compatibility

### 8.1 WorkloadType

`WorkloadType.WRAPUP` is additive. Existing workload types and their behavior are unchanged.

### 8.2 Task Plan Generator

The new `elif` branch only activates when `workload_type == "wrapup"`. All existing branches (planning, refinement, implementation, legacy) are unchanged.

### 8.3 Cycle Request Profiles

The new `wrapup.yaml` profile is additive. Existing profiles are unchanged. All keys used by the wrap-up profile (`pulse_checks`, `cadence_policy`, `workload_sequence`) are already in `_APPLIED_DEFAULTS_EXTRA_KEYS`. No schema changes needed.

### 8.4 Executor

No executor changes. Wrap-up runs flow through the existing pipeline identically to planning runs.

### 8.5 Event Bus

No new event types. Existing bridges handle wrap-up events via existing generic handlers.

### 8.6 Tests

All existing tests pass without modification. New tests cover wrap-up models, handlers, task planning, and profile validation.

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrap-up quality depends on implementation artifacts — poor artifacts yield thin closeouts | Low-value closeout that does not help the operator | Confidence classification explicitly handles this: `inconclusive` and `not_sufficiently_verified` are valid outcomes. The evidence inventory records gaps rather than hiding them. |
| LLM produces overly optimistic confidence classifications | False confidence in cycle outcomes | QA's independent outcome assessment provides a counterbalance. Pulse checks verify artifact presence. Operator review at the closeout gate is the final check. Handler system prompts explicitly instruct against optimistic compensation. |
| Wrap-up perceived as overhead — operators skip it | Cycles close without adjudication | The `workload_sequence` in full-cycle profiles (1.1) will include wrap-up by default. In 1.0, documentation and workflow guidance emphasize wrap-up value. |
| Closeout artifact becomes a transcript instead of a decision artifact | Operator still depends on raw logs | Handler system prompts explicitly instruct: "Produce a decision-grade closeout artifact, not a transcript. Lead with the confidence classification and recommendation." Pulse check failure modes include "turning the closeout into a transcript." |
| Missing implementation artifacts cause wrap-up handler failures | Wrap-up run fails before producing any useful output | The `data.gather_evidence` handler records gaps in the evidence inventory rather than failing (§7.3). Downstream handlers produce lower-confidence output, but still produce output. |

---

## 10. Rollout Plan

### Phase 1: Domain Models and Task Steps

1. Define `ConfidenceClassification`, `UnresolvedIssueType`, `UnresolvedIssueSeverity`, `NextCycleRecommendation` constants classes in `src/squadops/cycles/wrapup_models.py`.
2. Add `WorkloadType.WRAPUP = "wrapup"` to `src/squadops/cycles/models.py`.
3. Add `WRAPUP_TASK_STEPS` and `REQUIRED_WRAPUP_ROLES` to `src/squadops/cycles/task_plan.py` and `models.py` respectively.
4. Add `elif run.workload_type == WorkloadType.WRAPUP` branch to `generate_task_plan()`.
5. Create `wrapup.yaml` cycle request profile.
6. Unit tests for constants classes, task plan generation, and profile loading.

**Success gate:** All new models are constants classes with correct values. `generate_task_plan()` selects `WRAPUP_TASK_STEPS` for wrapup workload type. Profile loads and validates. `run_new_arch_tests.sh` green.

### Phase 2: Handlers and Artifact Templates

1. Implement all 5 handler classes in `src/squadops/capabilities/handlers/wrapup_tasks.py`.
2. Define handler system prompts with explicit anti-narration, anti-optimism instructions.
3. Validate closeout artifact template structure (YAML frontmatter, required sections).
4. Validate handoff artifact template structure.
5. Wire artifact pre-resolution for implementation run references.
6. Unit tests for all handlers (inputs, outputs, error handling, prior-output chaining).

**Success gate:** All 5 handlers produce correct artifacts with expected structure. Prior-output chaining works across the 5-step sequence. Handler failure paths produce structured error output, not crashes. `run_new_arch_tests.sh` green.

### Phase 3: Tests, Version Bump, Promotion

1. Profile contract tests.
2. Pulse check suite binding tests.
3. Full wrap-up flow integration test (all 5 handlers chained).
4. Version bump.
5. SIP promotion.

**Success gate:** All tests pass. Full regression green. Wrap-up run completes end-to-end with all 5 artifacts produced. `run_new_arch_tests.sh` green.

---

## 11. File-Level Design

### New Files

| File | Contents |
|------|----------|
| `src/squadops/cycles/wrapup_models.py` | `ConfidenceClassification`, `CloseoutRecommendation`, `UnresolvedIssueType`, `UnresolvedIssueSeverity`, `NextCycleRecommendation` constants classes |
| `src/squadops/capabilities/handlers/wrapup_tasks.py` | 5 handler classes: `DataGatherEvidenceHandler`, `QAAssessOutcomesHandler`, `DataClassifyUnresolvedHandler`, `GovernanceCloseoutDecisionHandler`, `GovernancePublishHandoffHandler` |
| `src/squadops/contracts/cycle_request_profiles/profiles/wrapup.yaml` | Wrap-up workload cycle request profile |
| `tests/unit/cycles/test_wrapup_models.py` | Constants class tests (~12) |
| `tests/unit/cycles/test_wrapup_task_plan.py` | Task plan generator tests for wrapup workload type (~8) |
| `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | Handler unit tests (~30) |
| `tests/unit/contracts/test_wrapup_profile.py` | Profile validation tests (~5) |

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `WorkloadType.WRAPUP = "wrapup"`, `REQUIRED_WRAPUP_ROLES` |
| `src/squadops/cycles/task_plan.py` | Add `WRAPUP_TASK_STEPS`, `elif WorkloadType.WRAPUP` branch in `generate_task_plan()` |
| `pyproject.toml` | Version bump |

### Files NOT Modified

| File | Why |
|------|-----|
| `adapters/cycles/distributed_flow_executor.py` | No executor changes (§7.15) |
| `src/squadops/api/routes/cycles/` | No API route changes (§7.17) |
| `src/squadops/cli/commands/` | No CLI changes (§7.17) |
| `src/squadops/events/types.py` | No new event types (§7.16) |
| `src/squadops/events/bridges/` | No bridge changes (§7.16) |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | No new `_APPLIED_DEFAULTS_EXTRA_KEYS` needed |

---

## 12. Test Plan

| Suite | File | Tests | Purpose |
|-------|------|-------|---------|
| ConfidenceClassification constants | `tests/unit/cycles/test_wrapup_models.py` | ~4 | All 6 values defined, no duplicates, string format |
| UnresolvedIssueType constants | `tests/unit/cycles/test_wrapup_models.py` | ~3 | All 7 values defined, no duplicates |
| UnresolvedIssueSeverity constants | `tests/unit/cycles/test_wrapup_models.py` | ~3 | All 4 values defined, no duplicates |
| CloseoutRecommendation constants | `tests/unit/cycles/test_wrapup_models.py` | ~2 | All 4 values defined, no duplicates |
| NextCycleRecommendation constants | `tests/unit/cycles/test_wrapup_models.py` | ~2 | All 5 values defined, no duplicates |
| Confidence ceiling constraints | `tests/unit/cycles/test_wrapup_models.py` | ~3 | sparse/partial blocks verified_complete, critical AC not_met blocks complete_with_caveats |
| Task plan generator (wrapup) | `tests/unit/cycles/test_wrapup_task_plan.py` | ~8 | Correct steps selected for wrapup workload_type, role validation, legacy fallback unchanged |
| DataGatherEvidenceHandler | `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~6 | Evidence inventory produced, missing inputs handled, completeness assessment |
| QAAssessOutcomesHandler | `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~6 | Planned vs actual comparison, acceptance criteria evaluation, deviation detection |
| DataClassifyUnresolvedHandler | `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~6 | Unresolved items categorized with type/severity, structured output |
| GovernanceCloseoutDecisionHandler | `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~6 | Closeout artifact produced, confidence classification assigned, YAML frontmatter valid |
| GovernancePublishHandoffHandler | `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~6 | Handoff artifact produced, carry-forward items structured, next cycle recommendation |
| Profile validation | `tests/unit/contracts/test_wrapup_profile.py` | ~5 | Profile loads, pulse checks defined, gate configured, profile appears in listing |
| **Total** | | **~60** | |

---

## 13. Key Design Decisions

### D1: Wrap-up is execution adjudication, not final notes

The deliverable is a decision-grade closeout artifact, not a narrative summary. The closeout must answer: What was produced? How sure are we? What next? This shapes every handler's system prompt and every artifact template.

### D2: Non-success is a valid and expected outcome

The confidence model has 6 levels because most real outcomes are not binary. A wrap-up that always produces `verified_complete` is broken. The handler system prompts explicitly instruct the Lead to classify honestly based on evidence.

### D3: Wrap-up is manually triggered in 1.0

Despite the principle that "analysis is most valuable when the run did not go well," automatic triggering requires a multi-workload orchestration pipeline that does not exist yet. In 1.0, the operator manually creates a wrap-up run after implementation completes. The `workload_sequence` in the profile declares the intent; automatic orchestration is a separate SIP. This matches SIP-0078's approach (§5.13: operators manually create implementation runs after planning gate approval).

### D4: Confidence classification is Lead-assigned, not automated

For v1.0, the Lead agent assigns the confidence classification based on evidence from Data and QA. This matches SIP-0079 D4 (correction decisions always require Lead involvement). Automated classification — computing a score from signal aggregation — is a 1.1 enhancement that requires calibration data from real wrap-up runs.

### D5: Missing evidence lowers confidence rather than failing the run

The `data.gather_evidence` handler records gaps in the evidence inventory rather than returning a failure. Downstream handlers produce output at whatever confidence the evidence supports. A wrap-up that fails because artifacts are missing defeats its purpose — even a sparse closeout with `inconclusive` confidence is more valuable than no closeout at all.

### D6: No correction protocol for wrap-up

Wrap-up is a bounded analysis phase, not a convergence loop. If a handler fails, normal retry handles it. There is no detect → RCA → decide → resume sequence for wrap-up. If the entire wrap-up run fails, the operator creates a new wrap-up run. This keeps the wrap-up workload simple and predictable.

### D7: No `approved_with_refinements` for wrap-up in 1.0

The planning workload supports `approved_with_refinements` with a separate `REFINEMENT_TASK_STEPS` sequence. Wrap-up does not need this complexity — the 5-step sequence is short enough that returning for full revision is acceptable. If the operator wants changes, they return for revision. Wrap-up refinement is a 1.1 consideration.

### D8: Strategy and Dev excluded from wrap-up roles

Wrap-up is adjudication. Strategy (framing) and Dev (building) roles have no place in assessing what happened. Including them risks turning wrap-up into a continuation of implementation. Data gathers evidence, QA verifies claims, Lead decides. This is a deliberate constraint.

### D9: Handoff artifact does not auto-generate cycle requests

The handoff artifact recommends a next cycle type and packages carry-forward items, but does NOT produce a draft `CycleCreateRequest`. In 1.0, the operator creates the next cycle manually, informed by the handoff. Auto-generation requires validated mapping from handoff structure to cycle request schema, which needs real usage data to calibrate.

### D10: Closeout and handoff are separate artifacts from separate handlers

The closeout artifact (adjudication) and handoff artifact (next-cycle packaging) serve different audiences and lifetimes. The closeout is for the current cycle's operator review. The handoff is for the next cycle's planning phase. Separate handlers allow checkpointing between them and keep each handler's responsibility clear.

### D11: No executor changes needed

Wrap-up workloads run through the existing executor pipeline. The task plan generator selects `WRAPUP_TASK_STEPS` based on `workload_type`. The executor dispatches them sequentially, chains prior_outputs, evaluates pulse checks, and pauses at gates — all existing behavior. This matches SIP-0078 (D11: no executor changes for planning workloads).

### D12: No new API routes or CLI commands needed

Wrap-up runs are created, monitored, and reviewed using existing platform mechanisms — `POST /runs` with `workload_type=wrapup`, standard artifact APIs, standard gate APIs. No new platform capabilities are introduced that would require dedicated endpoints. This matches SIP-0078's approach.

### D13: No new event types needed

Wrap-up runs emit existing lifecycle events (`RUN_STARTED`, `TASK_DISPATCHED`, `ARTIFACT_STORED`, `GATE_DECIDED`, etc.). The confidence classification is captured in the closeout artifact's YAML frontmatter, not as a separate event. Adding a `CLOSEOUT_CLASSIFIED` event type would be over-engineering for v1.0.

### D14: Wrap-up pulse checks are structural, not semantic

Pulse checks verify artifact presence (file exists, non-empty), not content quality. Whether the closeout is honest, whether caveats are surfaced, whether evidence supports claims — these are handler responsibilities and operator review responsibilities. Content-aware pulse checks require NLP-level evaluation and are deferred to 1.1.

### D15: Promotion is unconditional — closeout and handoff are always promoted

Wrap-up artifacts are stored with `promotion_status="promoted"` at write time, regardless of confidence classification. A `failed` closeout is still the authoritative record and must be accessible without a separate promotion step. Promotion does not imply success.

### D16: Executor owns artifact pre-resolution for `impl_run_id`

Following the SIP-0068 pattern, the executor pre-resolves implementation run artifacts into `inputs["artifact_contents"]` before dispatching `data.gather_evidence`. If pre-resolution fails (non-existent run), the executor injects an empty dict and the handler runs in degraded mode rather than failing. This prevents a mismatch where tests inject `artifact_contents` but production forgets to pre-resolve.

### D17: Scope baseline precedence — run contract over planning artifact

When both exist, the run contract (SIP-0079) is the canonical scope baseline, not the planning artifact. The run contract was generated at implementation start and represents contractual commitments; the planning artifact represents pre-contract intent. Plan deltas layer on top. Scope changes without corresponding plan deltas are classified as drift.

### D18: Evidence completeness is deterministic, not vibes

The `evidence_completeness` field uses a mechanical rubric based on 4 required evidence categories (§7.8). `complete` = all 4 present, `partial` = 1 missing, `sparse` = 2+ missing. This makes the field comparable across cycles and removes LLM judgment from the completeness assessment.

### D19: Confidence ceiling enforced by evidence constraints

If evidence is `partial` or `sparse`, confidence cannot be `verified_complete`. If any critical AC is not met, confidence cannot be `verified_complete` or `complete_with_caveats`. These constraints are enforced by the `governance.closeout_decision` handler and validated by tests. This prevents optimistic closeout artifacts from slipping through.

---

## 14. Acceptance Criteria

1. `WRAPUP_TASK_STEPS` is defined and produces valid task envelopes via `generate_task_plan()` when `workload_type` is `"wrapup"`.
2. `WorkloadType.WRAPUP` exists and is accepted by `validate_workload_type()`.
3. `REQUIRED_WRAPUP_ROLES` validates that Data, QA, and Lead are present for wrap-up runs.
4. All 5 wrap-up handlers extend `_CycleTaskHandler`, register correct `capability_id` values, and produce expected artifacts.
5. `ConfidenceClassification` constants class exists with 6 classification values.
6. `UnresolvedIssueType` constants class exists with 7 type values.
7. `UnresolvedIssueSeverity` constants class exists with 4 severity values.
8. `NextCycleRecommendation` constants class exists with 5 recommendation values.
9. Closeout artifact structure follows the template in §7.8 with YAML frontmatter containing `confidence`, `readiness_recommendation`, `next_cycle_recommendation`, `acceptance_criteria_met`, `acceptance_criteria_total`, `unresolved_count`, `evidence_completeness`, and `scope_baseline_source` fields.
10. Handoff artifact structure follows the template in §7.9 with YAML frontmatter containing `source_cycle_id`, `source_run_id`, `next_cycle_type`, and `carry_forward_count` fields.
11. Wrap-up handlers chain `prior_outputs` correctly: each handler receives upstream outputs.
12. `data.gather_evidence` records missing inputs as evidence gaps rather than failing the handler.
13. Wrap-up cycle request profile (`wrapup.yaml`) loads and validates without errors.
14. Wrap-up pulse check suites bind to correct milestones (`data.gather_evidence`, `governance.closeout_decision`) and fire during wrap-up workload execution.
15. Existing `generate_task_plan()` behavior is unchanged for all other workload types (backward compatibility).
16. If `evidence_completeness` is `partial` or `sparse`, `confidence` must not be `verified_complete`.
17. If any critical acceptance criterion is marked `not_met`, `confidence` must not be `verified_complete` or `complete_with_caveats`.
18. Closeout and handoff artifacts are stored with `promotion_status="promoted"` regardless of confidence classification.
19. Wrap-up run creation rejects `impl_run_id` referencing a run in `RUNNING` or `PENDING_GATE` status.
20. `CloseoutRecommendation` constants class exists with 4 recommendation values (`proceed`, `harden`, `replan`, `halt`).
21. All existing tests pass (no regressions).

---

## 15. Resolved Open Questions

**Q1: Should the wrap-up run always execute even after catastrophic implementation failure, or should there be a minimum evidence threshold below which wrap-up is skipped?**

Decision (D5): Always execute. A catastrophic failure is precisely when wrap-up is most valuable — it records what went wrong, why, and what to do next. If required inputs are missing, the `data.gather_evidence` handler records the gaps and downstream handlers produce lower-confidence output. A closeout with `inconclusive` confidence is more valuable than no closeout.

**Q2: Should confidence classification be computed automatically from evidence signals, assigned by the Lead agent, or both?**

Decision (D4): Lead-assigned for v1.0. The Lead agent reviews all prior outputs (evidence inventory, QA outcome assessment, unresolved items) and assigns the classification. Automated computation — aggregating signals into a score — requires calibration data from real wrap-up runs and is a 1.1 enhancement.

**Q3: How should the next-cycle handoff artifact integrate with cycle request profiles — should it auto-generate a draft cycle request for the next cycle?**

Decision (D9): No auto-generation in 1.0. The handoff recommends a next cycle type and packages carry-forward items. The operator creates the next cycle manually, informed by the handoff. Auto-generation requires validated mapping from handoff structure to cycle request schema.

**Q4: Should wrap-up artifacts be promoted to cycle level automatically, or require explicit promotion via gate?**

Decision (D15): Wrap-up artifacts are stored with `promotion_status="promoted"` by the handler at write time, following the existing pattern where handlers set artifact metadata at storage time. No separate promote-gate is required. Both the closeout and handoff artifacts are primary outputs of the wrap-up workload and should be immediately accessible without an additional promotion step.

**Invariant:** Closeout and handoff artifacts are promoted **regardless of confidence classification** — even `failed` or `inconclusive` closeouts must be promoted and accessible. Promotion does not imply success; it implies the artifact is the authoritative record of the wrap-up decision.

**Q5: How much of the closeout artifact should be human-written vs agent-generated for 1.0?**

Decision: Fully agent-generated, with operator review at the closeout gate (§7.11). The operator can accept, return for revision with feedback, or reject. The operator does not edit the closeout directly — they return for revision with notes, and the Lead incorporates feedback in a re-run. This matches the planning workload's gate review pattern.

---

## 16. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-wrapup-run-readiness.md` — wrap-up contract, standard closeout artifact, planned-vs-actual comparison, evidence-backed claims, confidence classification, structured unresolved issues, quality reconciliation, next-cycle handoff, wrap-up Pulse Checks, human review at closeout.

---

## 17. Estimated Scope

- **New constants classes:** 5
- **New handlers:** 5
- **New test files:** 4
- **Modified files:** 2–3
- **Estimated new tests:** ~60
- **No executor changes, no API changes, no CLI changes, no new event types**

---

## 18. Revision History

| Rev | Date | Changes |
|-----|------|---------|
| 1 | 2026-02-28 | Initial proposal: approach sketch, goals, open questions |
| 2 | 2026-03-05 | Acceptance-ready rewrite: terminology, design principles, concrete domain models (5 constants classes), 5-step task sequence with role assignments, 5 handler specifications with input/output chain, closeout artifact template with YAML frontmatter, handoff artifact template, cycle request profile YAML, pulse check suite definitions, task plan generator changes, executor integration (no changes), API/CLI surface (no changes), event taxonomy (no changes), file-level design, 3-phase rollout plan, test plan (~60 tests), 19 design decisions, 21 acceptance criteria, resolved all 5 open questions, backward compatibility, risks and mitigations. Incorporated 10 reviewer tightenings: artifact pre-resolution ownership and executor fallback (#1), planned-vs-actual scope baseline precedence rule (#2), deterministic evidence completeness rubric (#3), unconditional artifact promotion invariant (#4), cycle-close semantics of gate approval (#5), impl run status precondition for wrap-up creation (#6), suggested_owner controlled vocabulary (#7), acceptance criteria canonical source and counting rules (#8), CloseoutRecommendation constants class (#9), negative-path acceptance criteria for confidence ceiling (#10) |
