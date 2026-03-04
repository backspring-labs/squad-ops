---
title: Planning Workload Protocol
status: implemented
authors: SquadOps Architecture
created_at: '2026-02-28'
revision: 3
sip_number: 78
updated_at: '2026-03-03T20:39:59.320484Z'
---
# SIP-0078: Planning Workload Protocol

**Status:** Accepted
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 3

## 1. Abstract

This SIP defines the protocol for the **Planning Workload** — the first phase of a multi-workload Cycle. The Planning Workload produces an implementation-authorizing artifact with enough design proof and proto validation that the subsequent implementation phase can proceed with bounded risk, clear sequencing, and meaningful verification. It also establishes QA-first test strategy participation, plan refinement tracking, and a formal readiness decision (go / revise / no-go) before implementation begins.

## 2. Problem Statement

Without a disciplined planning phase, long implementation cycles degrade into expensive confusion. Several failure modes emerge:

- Planning becomes architecture brainstorming instead of implementation authorization.
- Proto work expands into uncontrolled implementation.
- Acceptance criteria remain vague or untestable.
- Risky assumptions go unclassified and are mistaken for resolved design decisions.
- QA enters too late to shape testability.
- Implementation sequencing is missing or weak.
- Human review occurs against an artifact that sounds confident but does not actually authorize build.
- The system advances to implementation with confidence but without clarity.

Additionally, QA involvement in planning is often an afterthought. For short autonomous runs, requiring a full test suite before implementation is too rigid, but QA should still produce acceptance checks, a test strategy note, and defect severity guidance before implementation begins.

## 3. Goals

1. Define a **Planning Workload contract** that bounds the phase: objective, timebox, required outputs, completion criteria, abort conditions.
2. Specify the **durable planning artifact** structure — the canonical handoff into implementation.
3. Establish **targeted proto validation** rules: what warrants proto work, what output types are acceptable, and how to prevent proto from becoming uncontrolled implementation.
4. Introduce **unknown classification** states (resolved, proto-validated, acceptable-risk, requires-human-decision, blocker) to prevent false certainty.
5. Define a **design sufficiency check** that determines whether the plan is ready to authorize implementation.
6. Integrate **QA-first test strategy** into the planning phase: acceptance checklist, test strategy note, and defect severity rubric — without requiring a full automated test suite upfront.
7. Specify **plan refinement tracking** so human feedback is captured as structured deltas, not informal edits.
8. Define the **readiness decision protocol**: go / revise / no-go with explicit gate outcomes including `approved_with_refinements`.
9. Define **planning-specific task steps and handlers** that integrate into the existing task plan generator and executor pipeline.
10. Specify **planning-specific pulse check suites** using the existing SIP-0070 framework.

## 4. Non-Goals

- Defining the implementation workload protocol (separate SIP).
- Multi-workload orchestration — automatic sequencing of planning → implementation → evaluation runs. This SIP defines what happens *within* a planning workload; the pipeline that chains workloads is a separate concern.
- Automated plan quality scoring (1.1+ enhancement).
- Retrieval-enriched planning memory or historical comparison (1.1+).
- Defining the Workload domain model itself (covered by SIP-0076 Workload & Gate Canon).
- Full automated test suite authoring during planning (explicitly deferred to implementation phase by QA-first strategy).
- New executor logic — planning workloads use the existing sequential dispatch, prior-output chaining, pulse check evaluation, and gate pause/resume mechanisms.

## 5. Design

### 5.1 Planning Task Steps

The planning workload uses a 5-step task sequence. Each step maps a `task_type` to a role, following the existing `CYCLE_TASK_STEPS` pattern from SIP-0066 §5.4.

```python
PLANNING_TASK_STEPS: list[tuple[str, str]] = [
    ("data.research_context", "data"),         # Data: constraints, prior patterns, risk areas
    ("strategy.frame_objective", "strat"),      # Strategy: scope, acceptance criteria, non-goals
    ("development.design_plan", "dev"),         # Dev: technical design, interfaces, sequencing, proto
    ("qa.define_test_strategy", "qa"),          # QA: acceptance checklist, test strategy, severity rubric
    ("governance.assess_readiness", "lead"),    # Lead: consolidate, sufficiency check, readiness decision
]
```

The sequence is intentional:
1. **Data first** — constraints and prior patterns inform the strategy framing.
2. **Strategy second** — objective and scope boundaries inform the technical design.
3. **Dev third** — design, interfaces, and proto validation inform the QA test strategy.
4. **QA fourth** — acceptance checklist and test strategy inform the Lead's readiness assessment.
5. **Lead last** — synthesizes all prior outputs into the durable planning artifact with a readiness recommendation.

### 5.2 Refinement Task Steps

When a planning gate returns `approved_with_refinements`, a refinement run executes a narrower 2-step sequence focused on incorporating feedback:

```python
REFINEMENT_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.incorporate_feedback", "lead"),    # Lead: parse feedback, update plan sections
    ("qa.validate_refinement", "qa"),               # QA: verify acceptance criteria still hold
]
```

Refinement does not re-run the full 5-step planning sequence. The Lead receives the original planning artifact plus the human's refinement instructions as inputs, applies targeted changes, and QA confirms the acceptance criteria remain testable after the changes.

### 5.3 Planning Handlers

Seven new handler classes, all extending `_CycleTaskHandler`. Each follows the existing pattern: LLM call with role-specific system prompt, PRD + prior outputs as context, single markdown artifact output.

| Handler Class | `capability_id` | Role | Artifact | Purpose |
|--------------|-----------------|------|----------|---------|
| `DataResearchContextHandler` | `data.research_context` | data | `context_research.md` | Gather constraints, prior patterns, risk areas, proto validation targets |
| `StrategyFrameObjectiveHandler` | `strategy.frame_objective` | strat | `objective_frame.md` | Frame objective, scope, non-goals, acceptance criteria, assumptions |
| `DevelopmentDesignPlanHandler` | `development.design_plan` | dev | `technical_design.md` | Technical design, interfaces, sequencing, unknown classification, proto findings |
| `QADefineTestStrategyHandler` | `qa.define_test_strategy` | qa | `test_strategy.md` | Acceptance checklist, test strategy note, defect severity rubric |
| `GovernanceAssessReadinessHandler` | `governance.assess_readiness` | lead | `planning_artifact.md` | Consolidate into durable planning artifact, design sufficiency check, readiness recommendation |
| `GovernanceIncorporateFeedbackHandler` | `governance.incorporate_feedback` | lead | `planning_artifact_revised.md` | Incorporate refinement instructions, produce updated planning artifact |
| `QAValidateRefinementHandler` | `qa.validate_refinement` | qa | `refinement_validation.md` | Verify acceptance criteria still hold after refinement |

All 7 handlers live in `src/squadops/capabilities/handlers/planning_tasks.py`, following the existing `cycle_tasks.py` module pattern.

#### Handler Input/Output Chain

Each handler receives `prior_outputs` from upstream roles (same chaining as existing cycle tasks):

- `data.research_context` receives: PRD only
- `strategy.frame_objective` receives: PRD + Data's context research
- `development.design_plan` receives: PRD + Data + Strategy outputs
- `qa.define_test_strategy` receives: PRD + Data + Strategy + Dev outputs
- `governance.assess_readiness` receives: PRD + all 4 prior outputs

For refinement:
- `governance.incorporate_feedback` receives: original planning artifact (via `plan_artifact_refs` in `execution_overrides`) + refinement instructions (via `execution_overrides.refinement_instructions`)
- `qa.validate_refinement` receives: revised planning artifact + original test strategy

**Refinement failure rule (V1):** If the original planning artifact ref (`plan_artifact_refs`) is missing from `execution_overrides`, unreadable, or resolves to no artifact, the refinement run fails immediately with a structured handler validation error. The system does not fall back to re-running full planning automatically.

### 5.4 Durable Planning Artifact

The planning artifact (`planning_artifact.md`) is the canonical output of the planning workload. It is produced by the `governance.assess_readiness` handler and stored in the artifact vault with `artifact_type="document"` and `producing_task_type="governance.assess_readiness"`.

The artifact uses markdown with YAML frontmatter for machine-parseable metadata:

The `readiness` field in the frontmatter is the **Lead's recommendation** — it is advisory. The gate decision (`approved`, `approved_with_refinements`, `returned_for_revision`, `rejected`) is the **authoritative operator/governance outcome**. The two may differ: a Lead may recommend `go` while the reviewer returns for revision, or a Lead may recommend `revise` while the reviewer approves. Downstream workload progression follows the gate decision, not the recommendation field.

```markdown
---
readiness: go | revise | no-go
unknowns_summary:
  resolved: 3
  proto_validated: 1
  acceptable_risk: 1
  requires_human_decision: 0
  blocker: 0
scope_status: bounded
sufficiency_score: 5
---

# Planning Artifact: {cycle objective}

## 1. Objective
[Clear scoped objective derived from PRD]

## 2. Scope
### In Scope
[Bounded implementation targets]

### Non-Goals
[What is explicitly excluded]

## 3. Assumptions and Constraints
[Operating assumptions, environment constraints, dependency requirements]

## 4. Proposed Design
### Interfaces and Boundaries
[Key interfaces, API shapes, module boundaries]

### State Model
[State transitions, data flow, persistence requirements]

## 5. Implementation Sequencing
1. [First step — establish baseline or contract]
2. [Second step — wire core logic]
3. [Third step — add verification hooks]
4. [...]

## 6. Verification Strategy
### Acceptance Checklist
[From QA — testable criteria for implementation success]

### Test Strategy
[From QA — what is manual vs automated, blocker vs non-blocker classification]

### Defect Severity Rubric
[Sev 1: blocker, Sev 2: major, Sev 3: minor — for fast Lead decisions at pulse checks]

## 7. Unknowns and Risks
| Unknown | Classification | Evidence | Notes |
|---------|---------------|----------|-------|
| [description] | resolved / proto_validated / acceptable_risk / requires_human_decision / blocker | [evidence or reference] | [context] |

## 8. Proto Findings
[Results of targeted proto validation — interface sketches, build proofs, payload examples]

## 9. Design Sufficiency Assessment
| Criterion | Met? | Notes |
|-----------|------|-------|
| Boundaries clear, interfaces specified | yes/no | ... |
| First implementation sequence obvious | yes/no | ... |
| Acceptance criteria testable | yes/no | ... |
| Risky assumptions validated or surfaced | yes/no | ... |
| QA has enough to verify meaningfully | yes/no | ... |

## 10. Readiness Recommendation
**Recommendation: GO / REVISE / NO-GO**

[Justification based on sufficiency assessment, unknown classification, and proto findings]
```

### 5.5 QA-First Outputs

QA produces three artifacts during planning. These are the "tests first" deliverables appropriate for 1.0 maturity — acceptance alignment and validation strategy, not a full automated test suite.

#### Acceptance Checklist (Required)

Derived from the cycle objective and PRD. Characteristics:
- PRD-aligned
- QA-verifiable (observable pass/fail)
- Focused on the happy path
- Stable even if implementation details shift

Example items:
- App starts with documented command
- Main route loads without error
- User can perform primary action
- App does not crash during happy-path flow
- QA can record evidence of the result

#### Test Strategy Note (Required)

Brief document describing how validation will be performed:
- What will be manual this cycle
- What could be automated later
- What evidence QA will capture
- What constitutes a blocker vs non-blocker
- Assumptions (stack, routes, startup command, mock data allowed)

#### Defect Severity Rubric (Recommended)

Classification system for fast Lead decisions at pulse checks:
- **Sev 1 — Blocker**: app does not start, main flow unavailable, crash on primary path
- **Sev 2 — Major**: key feature partially broken, incorrect behavior, workaround exists but acceptance criteria at risk
- **Sev 3 — Minor**: UI/copy issue, non-critical edge case, polish defect

#### Smoke Test Skeleton (Optional)

Only if the implementation surface is stable enough. Time-boxed. Not required in 1.0 (Stage A maturity).

### 5.6 Unknown Classification

Every identified unknown gets classified using one of five states:

```python
class UnknownClassification:
    """Classification states for planning unknowns (SIP-Planning-Workload-Protocol §5.6)."""
    RESOLVED = "resolved"
    PROTO_VALIDATED = "proto_validated"
    ACCEPTABLE_RISK = "acceptable_risk"
    REQUIRES_HUMAN_DECISION = "requires_human_decision"
    BLOCKER = "blocker"
```

This is a constants class (not enum), matching the `WorkloadType` / `ArtifactType` / `EventType` pattern. Custom values remain theoretically allowed by the constants-class pattern, but planning artifacts produced by the built-in planning handlers must only use the 5 canonical classification values. Custom values are out of scope for the standard planning workload protocol.

Classification semantics:
- `resolved` — answered with evidence (code check, documentation, confirmed by analysis)
- `proto_validated` — tested with proto output (interface sketch, build proof, payload validation)
- `acceptable_risk` — acknowledged, bounded, not blocking implementation but may need monitoring
- `requires_human_decision` — needs operator input at the review gate before implementation can proceed
- `blocker` — must be resolved before implementation; if present, readiness recommendation should be `revise` or `no-go`

If the majority of core unknowns remain at `acceptable_risk`, the `governance.assess_readiness` handler should recommend narrowing the implementation target.

### 5.7 Design Sufficiency Check

The design sufficiency check is performed by the `governance.assess_readiness` handler as the final step before issuing a readiness recommendation. It evaluates 5 criteria:

1. **Boundaries clear, interfaces specified** — can a developer start implementing from the design?
2. **First implementation sequence obvious** — is there an unambiguous starting point?
3. **Acceptance criteria testable** — can QA verify the implementation meaningfully?
4. **Risky assumptions validated or surfaced** — are dangerous unknowns classified, not ignored?
5. **QA has enough to verify meaningfully** — does the test strategy cover the implementation surface?

Each criterion is scored yes/no. The `sufficiency_score` (0–5) in the planning artifact frontmatter is the count of criteria marked `yes` — it is mechanically derived from the assessment table, not an independent LLM judgment. The readiness recommendation (`go` / `revise` / `no-go`) remains LLM judgment informed by the score, unknown classification, and proto findings.

The sufficiency check is embedded in the handler's system prompt as assessment criteria — it is not a separate mechanical check or pulse check suite. The handler evaluates the criteria against all prior planning outputs and populates the assessment table.

### 5.8 Readiness Decision Protocol

The planning workload concludes with a gate (`progress_plan_review`) that uses the existing `GateDecisionValue` enum from SIP-0076:

| Gate Decision | Meaning | What Happens |
|--------------|---------|--------------|
| `approved` | Plan authorizes implementation | Proceed to implementation workload |
| `approved_with_refinements` | Plan is mostly ready, targeted updates needed | Create refinement run (`workload_type=refinement`, `REFINEMENT_TASK_STEPS`), then proceed |
| `returned_for_revision` | Plan needs significant rework | Create new planning run (`workload_type=planning`, full `PLANNING_TASK_STEPS`) |
| `rejected` | Plan is not viable for this cycle | Cycle does not proceed to implementation |

These gate decisions already exist in the domain model. No new gate decision values are needed.

#### Refinement Flow

When the gate decision is `approved_with_refinements`:

1. The reviewer provides refinement instructions via the gate decision's `notes` field.
2. A new Run is created with `workload_type=refinement`.
3. The refinement run uses `REFINEMENT_TASK_STEPS` (2 steps: Lead incorporates, QA validates).
4. The Lead handler receives the original planning artifact plus refinement instructions.
5. The Lead produces an updated planning artifact (`planning_artifact_revised.md`).
6. QA validates that acceptance criteria still hold.
7. The revised planning artifact becomes the **current canonical handoff artifact** for downstream implementation. The original planning artifact remains stored and referenceable as historical output — replacement is by canonical reference selection, not destructive overwrite.

**Refinement bounding rule (V1):** Each `approved_with_refinements` gate decision authorizes exactly one refinement run. That refinement run does not recursively create additional refinement loops on its own. If the refinement result is still unsatisfactory, the next action must be an explicit human decision to either return for full revision (`returned_for_revision`) or manually create another refinement run as a new operator action.

### 5.9 Plan Refinement Artifact

When a refinement run executes, the Lead produces a revised planning artifact plus a companion refinement tracking artifact (`plan_refinement.md`):

```markdown
---
original_plan_ref: art_xxxxxxxxxxxx
refinement_source: gate_decision
scope_change: expanded | narrowed | unchanged
sequencing_changed: true | false
---

# Plan Refinement

## Refinement Instructions
[Human feedback from gate decision notes]

## Changes Applied
| Section | Change | Reason | Status |
|---------|--------|--------|--------|
| 5. Implementation Sequencing | Reordered steps 2 and 3 | Reviewer identified dependency | incorporated |
| 7. Unknowns | Added new unknown for API auth | Reviewer flagged missing concern | incorporated |
| 3. Assumptions | Removed assumption about Redis | No longer valid per reviewer | incorporated |

## Incorporation Summary
- Total items: N
- Incorporated: N
- Partially incorporated: N
- Not incorporated (with justification): N
- Superseded (by later feedback): N
```

### 5.10 Proto Validation Rules

Proto work within the planning phase is targeted and bounded. It proves or reduces risk — it does not partially build the feature.

**Acceptable proto output types:**
- Interface sketches (JSON contract, API shape, type definitions)
- Payload examples (request/response samples)
- State transition notes (lifecycle diagrams, state machine descriptions)
- API path validation (endpoint existence, method support)
- Plugin registration proof (import works, hook fires)
- Dependency build confirmation (package installs, compiles in target container)
- Draft test matrix (coverage map against acceptance criteria)
- Sample workload decomposition (task breakdown estimate)

**Proto output constraints:**
- Proto outputs are stored as part of the planning artifact (§8. Proto Findings), not as separate source artifacts.
- Proto code snippets are illustrative, not production code. They are not stored as `source` type artifacts.
- The `development.design_plan` handler's system prompt explicitly instructs: "Proto work validates feasibility. Do not implement features."
- Illustrative proto snippets may inform later implementation reasoning, but they are not treated as authoritative implementation artifacts and do not satisfy build progress on their own.

### 5.11 Planning Pulse Check Suites

Planning-specific pulse checks use the existing SIP-0070 framework — same `PulseCheckDefinition` model, same executor verification logic, same repair chain. Only the suite definitions and milestone bindings differ.

Planning pulse checks in 1.0 are intentionally structural — they verify artifact presence and completeness, not semantic quality. Semantic sufficiency (is the design good enough?) remains the responsibility of handler output plus the Lead's readiness assessment, not pulse-check mechanics. Deeper content-level checks may be added at higher maturity stages.

Two milestone-bound suites and one optional cadence-bound suite:

#### Suite 1: `planning_scope_guard` (post-strategy)

Fires after `strategy.frame_objective` completes. Verifies the strategy output exists and is non-empty.

```yaml
- suite_id: planning_scope_guard
  boundary_id: post_strategy
  binding_mode: milestone
  after_task_types:
    - strategy
  checks:
    - check_type: file_exists
      target: "{run_root}/objective_frame.md"
    - check_type: non_empty
      target: "{run_root}/objective_frame.md"
  max_suite_seconds: 15
  max_check_seconds: 5
```

#### Suite 2: `planning_completeness` (post-consolidation)

Fires after `governance.assess_readiness` completes. Verifies the planning artifact exists and is non-empty.

```yaml
- suite_id: planning_completeness
  boundary_id: post_consolidation
  binding_mode: milestone
  after_task_types:
    - governance
  checks:
    - check_type: file_exists
      target: "{run_root}/planning_artifact.md"
    - check_type: non_empty
      target: "{run_root}/planning_artifact.md"
  max_suite_seconds: 15
  max_check_seconds: 5
```

#### Suite 3: `planning_heartbeat` (cadence, optional)

Cadence-bound heartbeat for long planning pulses. Only useful if cadence_policy is set with a lower `max_tasks_per_pulse`.

```yaml
- suite_id: planning_heartbeat
  boundary_id: cadence
  binding_mode: cadence
  checks:
    - check_type: file_exists
      target: "{run_root}/.pulse_marker"
  max_suite_seconds: 10
  max_check_seconds: 5
```

### 5.12 Cadence Policy

Planning workloads use a cadence policy tuned for the 60–90 minute planning timebox:

```yaml
cadence_policy:
  max_pulse_seconds: 5400    # 90 minutes (advisory, not hard stop)
  max_tasks_per_pulse: 5     # All 5 planning steps fit in one pulse
```

The timebox is **advisory**: if the cadence limit is reached, cadence-bound pulse checks fire. If those checks pass, execution continues. This prevents hard-stopping a planning phase that is producing good output but running slightly over time.

### 5.13 CRP Profile Integration

A new cycle request profile provides the default configuration for planning workloads:

**`planning.yaml`**:

```yaml
name: planning
description: "Planning workload with design sufficiency review gate"
defaults:
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: progress_plan_review
        description: "Review planning artifact before implementation"
        after_task_types:
          - governance.assess_readiness
  expected_artifact_types:
    - document
  workload_sequence:
    - type: planning
      gate: progress_plan_review
    - type: implementation
      gate: null
  pulse_checks:
    - suite_id: planning_scope_guard
      boundary_id: post_strategy
      binding_mode: milestone
      after_task_types:
        - strategy
      checks:
        - check_type: file_exists
          target: "{run_root}/objective_frame.md"
        - check_type: non_empty
          target: "{run_root}/objective_frame.md"
      max_suite_seconds: 15
      max_check_seconds: 5
    - suite_id: planning_completeness
      boundary_id: post_consolidation
      binding_mode: milestone
      after_task_types:
        - governance
      checks:
        - check_type: file_exists
          target: "{run_root}/planning_artifact.md"
        - check_type: non_empty
          target: "{run_root}/planning_artifact.md"
      max_suite_seconds: 15
      max_check_seconds: 5
  cadence_policy:
    max_pulse_seconds: 5400
    max_tasks_per_pulse: 5
  experiment_context: {}
  notes: "Planning workload cycle"
```

The `workload_sequence` in `planning.yaml` is a canonical declaration of intended phase order and gate boundary, but in 1.0 it is informational and validating rather than automatically executed by an orchestration pipeline. The multi-workload orchestration pipeline that automatically creates runs for each workload entry is a separate SIP. In 1.0, operators manually create implementation runs after the planning gate is approved.

### 5.14 Role Expectations

Each role has specific responsibilities within the planning workload:

**Lead (governance.assess_readiness)**
- Own the planning contract
- Synthesize all prior outputs into the durable planning artifact
- Perform design sufficiency check
- Issue go / revise / no-go readiness recommendation
- Keep scope bounded during consolidation

**Strategy (strategy.frame_objective)**
- Frame the cycle objective clearly
- Define scope boundaries and non-goals
- Write acceptance criteria QA can verify
- Identify constraints and assumptions
- Avoid ambiguous "nice-to-have" requirements

**Dev (development.design_plan)**
- Propose technical design with interfaces and boundaries
- Identify dependency impacts and integration risks
- Define implementation sequencing
- Run targeted proto validation where uncertainty is high
- Classify unknowns with evidence

**QA (qa.define_test_strategy)**
- Produce acceptance checklist (required)
- Write test strategy note (required)
- Define defect severity rubric (recommended)
- Challenge vague acceptance criteria
- Identify validation blind spots

**Data (data.research_context)**
- Analyze constraints and prior failure patterns
- Identify risk areas and open questions
- Recommend where proto validation is most needed
- Provide supporting context for strategy framing

## 6. Key Design Decisions

### D1: Planning is implementation authorization, not design brainstorming
The deliverable is a build-authorizing artifact, not a "nice plan." The planning artifact must contain enough concrete design, acceptance criteria, and implementation sequencing that an implementation workload can start with bounded risk.

### D2: QA-first means acceptance checks first, not full test suite first
Rigid "write all tests first" creates brittle tests against changing implementation details in short cycles. QA produces acceptance checklist + test strategy note during planning. Full test automation happens during the implementation workload when the implementation surface is stable.

### D3: No-go is a valid outcome
A planning phase that always results in "ready to build" is not functioning as a real control. The `governance.assess_readiness` handler can recommend no-go, and the gate reviewer can reject the plan.

### D4: Proto is bounded
Proto outputs are constrained to specific types (§5.10) to prevent uncontrolled implementation creep. Proto proves or reduces risk — it does not partially build the feature.

### D5: Plan refinement is tracked, not hand-waved
Human feedback becomes a structured, attributable artifact with incorporation tracking (§5.9). Refinement is incorporated via a narrower task sequence, not informal edits to the canonical plan.

### D6: Timebox is advisory, not a hard stop
60–90 minutes is the recommended planning window. Enforcement uses cadence policy (§5.12), which triggers pulse checks but does not hard-stop execution. A planning phase that is producing good output should not be killed by a wall-clock timer.

### D7: Planning steps are a new task sequence, not a replacement for existing CYCLE_TASK_STEPS
The existing `CYCLE_TASK_STEPS` remain for backward compatibility with single-workload cycles. `PLANNING_TASK_STEPS` are used when `run.workload_type == "planning"`. Both can coexist in the same codebase.

### D8: Refinement uses a narrower task plan
Refinement runs use `REFINEMENT_TASK_STEPS` (2 steps) rather than the full `PLANNING_TASK_STEPS` (5 steps). This prevents full re-planning when only targeted updates are needed.

### D9: Planning pulse checks use the existing SIP-0070 framework
No new pulse check infrastructure. Planning-specific checks are new suite definitions with planning-appropriate milestone bindings. This is the intended extensibility model from SIP-0070.

### D10: Design sufficiency criteria are LLM-assessed; the score is mechanical
The design sufficiency check (§5.7) is embedded in the `governance.assess_readiness` handler's system prompt. It evaluates 5 criteria (yes/no each) — this requires LLM judgment because the questions ("are interfaces specified?") require reading and understanding the design. The `sufficiency_score` is mechanically derived as the count of `yes` rows, keeping it interpretable. The readiness recommendation remains LLM judgment informed by the score.

### D11: No executor changes needed
Planning workloads run through the existing executor pipeline. The task plan generator selects `PLANNING_TASK_STEPS` based on `workload_type`. The executor dispatches them sequentially, chains prior_outputs, evaluates pulse checks, and pauses at gates — all existing behavior.

### D12: Planning artifact routing to implementation is a deployment concern
In single-run cycles (planning + build in one run), prior_output chaining handles data flow between phases. In multi-workload cycles, artifact references are passed via `execution_overrides.plan_artifact_refs` when the implementation run is created. The orchestration pipeline that automates this is a separate SIP.

### D13: Unknown classification is a constants class; planning handlers use canonical values only
Follows the `WorkloadType` / `ArtifactType` / `EventType` pattern — not an enum, not a model. Custom values remain theoretically allowed by the pattern, but built-in planning handlers must only use the 5 canonical values to preserve artifact consistency for downstream consumers.

### D14: Readiness recommendation is advisory; gate decision is authoritative
The `readiness` field in the planning artifact frontmatter is the Lead's recommendation. The gate decision is the operator/governance outcome. The two may differ. Downstream workload progression follows the gate decision, not the recommendation field.

### D15: Refinement is bounded to one run per gate decision
Each `approved_with_refinements` authorizes exactly one refinement run. No recursive refinement loops. If the result is unsatisfactory, the next action requires an explicit human decision.

### D16: Original planning artifact is preserved, not overwritten
Refinement produces a new artifact that becomes the canonical handoff by reference selection. The original remains stored and referenceable as historical output.

### D17: Refinement fails fast on missing source artifact
If `plan_artifact_refs` is missing or unresolvable, the refinement run fails immediately with a validation error. No silent fallback to full re-planning.

## 7. Task Plan Generator Changes

The `generate_task_plan()` function in `src/squadops/cycles/task_plan.py` gains workload-type-aware step selection:

```python
def generate_task_plan(cycle, run, profile):
    # Workload-type-aware step selection (Planning Workload Protocol)
    if run.workload_type == WorkloadType.PLANNING:
        steps = PLANNING_TASK_STEPS
    elif run.workload_type == WorkloadType.REFINEMENT:
        steps = REFINEMENT_TASK_STEPS
    elif run.workload_type == WorkloadType.IMPLEMENTATION:
        # Implementation uses build steps only (no plan steps)
        if _has_builder_role(profile):
            steps = BUILDER_ASSEMBLY_TASK_STEPS
        else:
            steps = BUILD_TASK_STEPS
    else:
        # Legacy: no workload_type → use plan_tasks/build_tasks flags
        # Backward compatible with pre-workload-sequence cycles
        include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))
        include_build = bool(cycle.applied_defaults.get("build_tasks"))
        ...  # existing logic unchanged
```

When `workload_type` is set, it takes precedence over `plan_tasks` / `build_tasks` flags. This ensures workload-typed runs always get the correct task sequence without ambiguity.

Role validation for planning runs: `REQUIRED_PLAN_ROLES` already covers `{strat, dev, qa, data, lead}`, which matches the 5 planning roles. No new validation needed. Refinement runs require `{lead, qa}` — a new `REQUIRED_REFINEMENT_ROLES` constant defined in `src/squadops/cycles/models.py` alongside the existing `REQUIRED_PLAN_ROLES`, and imported by `task_plan.py` for validation during refinement workload plan generation.

## 8. Executor Integration

No changes to `DistributedFlowExecutor`. The existing executor:

- **Sequential dispatch** — dispatches tasks one at a time, waits for results. Planning steps execute in order.
- **Prior-output chaining** — each handler receives outputs from all prior roles via `prior_outputs` dict. The 5-step planning chain builds progressively.
- **Artifact storage** — handler artifacts are stored via the vault with `producing_task_type` metadata. Planning artifacts are stored as `artifact_type="document"`.
- **Pulse check evaluation** — milestone bindings resolve against planning task types (`strategy`, `governance`). Suite definitions in the CRP profile control what checks fire.
- **Gate pause/resume** — the `progress_plan_review` gate fires after `governance.assess_readiness` via `after_task_types`. The executor pauses the run and waits for a gate decision.
- **Event emission** — SIP-0077 events are emitted for all planning task dispatches, successes, failures, pulse checks, and gate decisions. No new event types needed.

The only code that changes is the task plan generator (§7), which selects the right steps based on `workload_type`.

## 9. File-Level Design

### New Files

| File | Contents |
|------|----------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | 7 handler classes: `DataResearchContextHandler`, `StrategyFrameObjectiveHandler`, `DevelopmentDesignPlanHandler`, `QADefineTestStrategyHandler`, `GovernanceAssessReadinessHandler`, `GovernanceIncorporateFeedbackHandler`, `QAValidateRefinementHandler` |
| `src/squadops/cycles/unknown_classification.py` | `UnknownClassification` constants class |
| `src/squadops/contracts/cycle_request_profiles/profiles/planning.yaml` | Planning workload CRP profile |
| `tests/unit/capabilities/handlers/test_planning_tasks.py` | Handler unit tests (~35) |
| `tests/unit/cycles/test_planning_task_plan.py` | Task plan generator tests for planning/refinement workload types (~15) |
| `tests/unit/contracts/test_planning_profile.py` | Planning CRP profile validation tests (~5) |

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/cycles/task_plan.py` | Add `PLANNING_TASK_STEPS`, `REFINEMENT_TASK_STEPS`, `REQUIRED_REFINEMENT_ROLES`, workload-type branching in `generate_task_plan()` |
| `src/squadops/cycles/models.py` | Add `REQUIRED_REFINEMENT_ROLES = {"lead", "qa"}` |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | No changes needed — `workload_sequence` already in `_APPLIED_DEFAULTS_EXTRA_KEYS` |
| `pyproject.toml` | Version bump, any new markers |

### Files NOT Modified

| File | Why |
|------|-----|
| `adapters/cycles/distributed_flow_executor.py` | No executor changes (D11) |
| `src/squadops/api/routes/cycles/` | No API route changes |
| `src/squadops/events/types.py` | No new event types |
| `src/squadops/cycles/pulse_models.py` | No new pulse models |

## 10. Acceptance Criteria

1. `PLANNING_TASK_STEPS` and `REFINEMENT_TASK_STEPS` are defined and produce valid task envelopes via `generate_task_plan()` when `workload_type` is set.
2. All 7 planning handlers extend `_CycleTaskHandler`, register correct `capability_id` values, and produce expected artifacts.
3. `generate_task_plan()` selects correct steps based on `workload_type` (planning, refinement, implementation) and falls back to legacy behavior when `workload_type` is None.
4. Planning CRP profile (`planning.yaml`) loads and validates without errors.
5. Planning pulse check suites bind to correct milestones (`strategy`, `governance`) and fire during planning workload execution.
6. `UnknownClassification` constants class exists with 5 classification states.
7. `REQUIRED_REFINEMENT_ROLES` validates that Lead and QA are present for refinement runs.
8. Planning handlers chain prior_outputs correctly: each handler receives upstream outputs.
9. Planning artifact structure follows the template in §5.4 with YAML frontmatter.
10. Existing `CYCLE_TASK_STEPS` behavior is unchanged when `workload_type` is None (backward compatibility).
11. If the planning artifact contains blocker-classified unknowns, the readiness recommendation must be `revise` or `no-go` — never `go`.
12. When a refinement run occurs, the original planning artifact remains preserved as historical output and the revised planning artifact becomes the canonical downstream handoff reference.
13. If `plan_artifact_refs` is missing or unresolvable when a refinement run starts, the run fails immediately with a validation error.
14. All existing tests pass (no regressions).

## 11. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-planning-proto-readiness.md` — planning-phase contract, durable planning artifact, proto validation, unknown classification, design sufficiency, readiness decision.
- `sips/proposed/IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md` — QA-first strategy, acceptance checklist, test strategy note, defect severity rubric, maturity-staged testing progression.

## 12. Resolved Open Questions

### Q1: Planning artifact schema — JSON schema or markdown template?

**Decision: Markdown template with YAML frontmatter.**

The planning artifact is primarily a human-readable document for gate review. YAML frontmatter provides machine-parseable metadata (readiness recommendation, unknown classification summary, sufficiency score) without requiring the entire document to be structured data. This matches how existing cycle artifacts work — markdown content stored via the artifact vault, with structured metadata on the `ArtifactRef`.

### Q2: Timebox enforcement — platform hard stop or advisory?

**Decision: Advisory via cadence policy.**

The existing `CadencePolicy` framework supports `max_pulse_seconds` which triggers pulse check evaluation at cadence boundaries. Planning workloads set `max_pulse_seconds: 5400` (90 minutes). If exceeded, cadence-bound pulse checks fire but do not hard-stop the run. Hard stops are too brittle for planning work where an extra few minutes may produce a significantly better artifact.

### Q3: Planning Pulse Checks — same framework or distinct mechanism?

**Decision: Same framework, different suites.**

The SIP-0070 pulse check framework is designed for extensibility via CRP profile suite definitions. Planning-specific checks are new `PulseCheckDefinition` entries with planning-appropriate `after_task_types` bindings. No new infrastructure code is needed.

### Q4: Refinement Run — reuse planning task plan or generate new one?

**Decision: New scoped plan via `REFINEMENT_TASK_STEPS`.**

Refinement uses a narrower 2-step sequence (Lead incorporates feedback, QA validates) rather than the full 5-step planning sequence. This avoids re-running research and strategy when only targeted changes are needed. The Lead receives the original planning artifact plus refinement instructions as inputs.

### Q5: QA smoke test scaffolding — when required vs optional?

**Decision: Optional in 1.0 (Stage A maturity).**

Following the QA-first IDEA's maturity progression: at Stage A (current), acceptance checklist + test strategy note are sufficient. Smoke test scaffolding becomes recommended at Stage B (after at least one successful planning → implementation cycle) and required at Stage C (high maturity). This prevents over-automation before the implementation surface stabilizes.

## 13. Estimated Scope

- **New handlers:** 7
- **New test files:** 3
- **Modified files:** 2–3
- **Estimated new tests:** ~55
- **No executor changes, no API changes, no new event types**
