# SIP-XXXX: Plutarch Experimentation and Cycle Assessment Framework
## Target Release: v1.1

### Status
Proposed

### Authors
Strategy / Architecture

### Type
Platform Capability

### Summary
Introduce **Plutarch** as a first-class SquadOps capability for benchmark-driven experimentation, cycle assessment, failure diagnosis, and improvement recommendation.

Plutarch is the governed **master experimenter** for SquadOps. Its purpose is to determine whether coordinated squads can outperform a single strong model on meaningful long-horizon software-building work, and to measure how individual-agent improvement translates into squad-level delivery improvement.

This revised SIP is intentionally more implementation-specific than the earlier version. It does not only define Plutarch’s mission and evaluation model. It also defines the **supporting capabilities SquadOps itself must implement** in order for Plutarch to function.

For v1.1, the proposal is to implement:
- explicit observability contracts for cycles, agents, tools, memory, and artifacts
- benchmark and internal eval registries
- cycle and squad health assessment artifacts
- failure diagnosis workflows and diagnostic categories
- bounded experiment orchestration primitives
- multi-model experiment lanes before, during, and after cycle runs
- recommendation and remediation workflows
- governance controls and approval boundaries

The guiding principle is simple:

**Plutarch cannot improve what SquadOps cannot observe, isolate, compare, and govern.**

---

## Motivation

SquadOps is aiming toward a demanding long-horizon goal: a governed squad that can build meaningful app increments autonomously over an 8–10 hour run.

That requires a disciplined way to answer:
1. **Can coordinated squads outperform a single strong model on sustained software-building work?**
2. **How does individual-agent improvement translate into squad-level improvement?**
3. **When a cycle fails, what actually broke?**
4. **When a squad underperforms, where is the real bottleneck?**
5. **What intervention should happen next: memory update, prompt change, routing change, model comparison, configuration change, topology change, or no change?**

Without a formal master experimenter capability, SquadOps risks:
- relying on intuition instead of evidence
- diagnosing symptoms rather than causes
- overreacting to isolated failures
- confusing local agent gains with real squad gains
- spending premium inference without measured return
- producing RCA that is descriptive but not operationally reusable

Plutarch exists to close that gap.

---

## Problem Statement

The earlier framing correctly described Plutarch’s strategic value, but it left a key implementation question under-specified:

**What exact capabilities must SquadOps expose and implement so that Plutarch can actually design experiments, diagnose broken cycles, assess broken squads, and recommend credible improvements?**

Without explicit support in the core framework, Plutarch would be reduced to a passive analyst with partial telemetry and weak intervention fidelity.

That is not sufficient.

To function as a real master experimenter, Plutarch needs:
- full-cycle observability
- agent-level and squad-level health signals
- explicit failure diagnosis surfaces
- comparable experiment setup and replay primitives
- controlled access to eval harnesses, models, memory, routing, and artifact history
- governed remediation and recommendation pathways

This SIP proposes those support requirements as part of v1.1 scope.

---

## Goals

### Primary Goals
- Establish **Plutarch** as the governed master experimenter for SquadOps
- Measure whether coordinated squads outperform a single strong model on long-horizon software-building work
- Measure how individual-agent improvement translates into squad-level delivery improvement
- Enable Plutarch to diagnose:
  - broken cycles
  - broken agents
  - broken handoffs
  - broken routing
  - broken memory usage
  - broken squad topology
- Produce evidence-backed recommendations for:
  - memory updates
  - prompt/instruction changes
  - routing changes
  - model comparisons
  - tuning/configuration changes
  - reruns and isolation experiments
  - squad topology changes
  - no-change outcomes

### Secondary Goals
- Create a repeatable improvement loop for SquadOps
- Improve confidence in long-run autonomous execution
- Reduce wasted time and cost from poorly-targeted changes
- Create a clean path from telemetry -> diagnosis -> experiment -> recommendation -> governed adoption

---

## Non-Goals

- Fully autonomous self-modification in v1.1
- Unreviewed production model swapping
- Silent mutation of active routing or prompt policy
- Treating public benchmarks as sufficient for all roles
- Building a public benchmark platform
- Replacing human strategic judgment
- Letting Plutarch directly bypass governance controls

---

## Core Charter

### Definition
**Plutarch** is the governed master experimenter for SquadOps. It designs bounded experiments, observes cycle execution, diagnoses failures, evaluates comparative performance, and generates evidence-backed recommendations for continuous improvement.

### Core Questions Owned
1. Can squads outperform a single strong model?
2. How does individual-agent improvement translate into squad improvement?
3. What failed in a broken cycle?
4. What failed in a broken squad?
5. What change is most likely to improve future performance?

### Core Principle
Plutarch is not one model. It is an **experiment orchestration role** with governed access to different model-backed lanes and framework resources across planning, monitoring, diagnosis, and evaluation.

---

## Why v1.1

This belongs in v1.1 because it improves the entire operating model of SquadOps without requiring unsafe autonomous mutation first.

v1.1 should create the foundation:
- observability contracts
- artifact schemas
- eval registries
- diagnosis surfaces
- experiment orchestration primitives
- recommendation workflows
- governance boundaries

Later releases can add:
- more automation
- adaptive tuning
- scheduled experiment cadences
- stronger release gating
- challenger lanes and tournament flows

---

# 1. Required Capabilities SquadOps Must Implement to Support Plutarch

This section is the most important addition in this revision.

Plutarch is only viable if SquadOps implements the following capability categories.

## 1.1 Observability Capabilities

Plutarch must have a complete and structured view of how a cycle executed.

### Required implementation in SquadOps

#### A. Cycle Graph Visibility
SquadOps must expose:
- cycle UID
- task graph
- dependency graph
- execution order
- task parent/child relationships
- blocked/unblocked transitions
- completion status transitions

#### B. Event Timeline Visibility
SquadOps must emit structured events for:
- task started
- task completed
- task failed
- handoff created
- handoff accepted
- handoff rejected
- escalation triggered
- rewind triggered
- tool invoked
- tool failed
- model lane selected
- memory bundle retrieved
- validation started/completed
- artifact generated/updated
- approval requested/granted/denied

#### C. Agent Execution Visibility
For each agent step, SquadOps must preserve:
- agent identity
- role
- model used
- lane used
- task context package ID
- prompt/instruction template version
- memory bundle IDs injected
- tool calls made
- outputs generated
- validation outcomes
- duration
- token/cost telemetry

#### D. Memory Retrieval Visibility
SquadOps must record:
- which MemoryRules or memory bundles were retrieved
- why they were retrieved
- task classification used
- whether they were likely followed, ignored, or violated
- whether the retrieval looked relevant or noisy

#### E. Artifact and Diff Visibility
SquadOps must preserve:
- artifact versions
- artifact diffs across attempts
- generated code diffs
- generated document diffs
- test result deltas
- golden-source comparison results where applicable

#### F. Environment and Runtime Visibility
SquadOps must record:
- runtime profile used
- environment (local/cloud)
- repo/branch/worktree
- dependency/environment version snapshot
- failure in infra/tooling vs failure in reasoning/execution

### Why this matters
Without this, Plutarch cannot distinguish root cause from downstream symptom.

---

## 1.2 Diagnostic Capabilities

Plutarch must be able to diagnose both a **broken cycle** and a **broken squad**.

### Required implementation in SquadOps

#### A. Failure Classification Framework
SquadOps must support structured failure classification at minimum across:
- task setup failure
- dependency or prerequisite failure
- prompt/instruction failure
- memory miss
- memory misuse
- routing failure
- model capability gap
- tool failure
- validation failure
- handoff degradation
- artifact incompleteness
- architecture boundary violation
- environment/config drift
- budget exhaustion
- coordination failure
- topology failure

#### B. First Failure vs Symptom Detection
SquadOps must support identifying:
- first failing node
- first invalid handoff
- first incorrect routing decision
- first bad memory retrieval
- first tool failure
- first invalid artifact generation
- downstream cascade effects

#### C. Local vs Systemic Failure Analysis
SquadOps must support distinguishing:
- single-task failure
- single-agent failure
- repeated role-level failure
- role interaction failure
- squad-wide instability

#### D. Broken Cycle Diagnosis
Plutarch must be able to answer:
- why this cycle failed
- where the cycle first diverged
- whether the failure was recoverable
- whether retries were wasted
- whether escalation timing was correct
- whether memory or routing would likely have changed the outcome

#### E. Broken Squad Diagnosis
Plutarch must be able to answer:
- which role is bottlenecking the squad
- whether handoffs are degrading output quality
- whether coordination overhead is too high
- whether role boundaries are wrong
- whether one agent’s improvement is being lost downstream
- whether squad topology should change

### Why this matters
A broken cycle and a broken squad are not the same problem. v1.1 must make both diagnosable.

---

## 1.3 Experiment Orchestration Capabilities

Plutarch must be able to run bounded, comparable experiments.

### Required implementation in SquadOps

#### A. Experiment Definition Primitive
SquadOps must support an experiment object that includes:
- experiment UID
- hypothesis
- target metric(s)
- baseline config
- challenger config
- dataset/task pack
- stop conditions
- budget cap
- time cap
- governance level
- result artifact links

#### B. Supported Experiment Types
v1.1 should explicitly support:
- single strong model vs squad comparison
- model A vs model B comparison for same role
- memory on/off experiment
- memory bundle A vs B experiment
- routing policy A vs B experiment
- prompt/instruction variant comparison
- retry/escalation threshold comparison
- single-agent substitution test
- seeded failure replay
- golden-source rebuild comparison
- benchmark slice comparison

#### C. Isolated Execution Surface
SquadOps must support:
- sandbox branch/worktree runs
- isolated eval runs
- non-production experiment lanes
- replay of prior tasks or task packs
- reproducible baseline/challenger comparison conditions

#### D. Stop Conditions and Guardrails
SquadOps must support:
- max tokens
- max cost
- max wall-clock duration
- max retries
- max rewinds
- allowed tools list
- allowed mutation scope
- required approval gates

### Why this matters
Plutarch should not run vague experiments. It should run bounded, comparable ones.

---

## 1.4 Resource Access Contracts

Plutarch must have explicit governed access to the resources required to design and assess experiments.

### Required implementation in SquadOps

#### A. Benchmark Registry Access
Plutarch must be able to:
- read benchmark definitions
- read benchmark scope notes
- read harness locations
- request benchmark execution
- read benchmark result history

#### B. Internal Eval Pack Access
Plutarch must be able to:
- read available eval packs
- select eval packs by role/task class
- request eval execution
- compare results across runs

#### C. Model Registry Access
Plutarch must be able to:
- read available models
- read model tags/capabilities
- read cost and lane restrictions
- select from allowed models for experiments

#### D. Routing Policy Access
Plutarch must be able to:
- read active routing policies
- compare current vs candidate routing config
- propose changes
- run experiments under alternate routing policies

#### E. Prompt/Instruction Registry Access
Plutarch must be able to:
- read active role prompts/instruction templates
- compare versions
- run bounded experiments with candidate variants
- propose revisions

#### F. Memory Registry Access
Plutarch must be able to:
- read MemoryRules and bundle definitions
- inspect retrieval history
- propose new rules or scope changes
- run memory-related experiments

#### G. RCA and Historical Assessment Access
Plutarch must be able to:
- read prior RCA artifacts
- read prior CycleAssessments
- read prior AgentImpactAssessments
- detect recurring patterns over time

#### H. Test and Validation Access
Plutarch must be able to:
- request tests
- request validations
- read results
- compare pass/fail deltas between configurations

### Why this matters
Without resource contracts, Plutarch becomes an advisory concept instead of an executable system capability.

---

## 1.5 Recommendation and Remediation Capabilities

Plutarch must not stop at diagnosis. It must be able to propose credible next actions.

### Required implementation in SquadOps

#### A. Recommendation Taxonomy
SquadOps must support recommendation categories at minimum:
- memory_update
- prompt_update
- routing_change
- model_comparison
- model_assignment_change
- tuning_or_config_change
- rerun_same_config
- rerun_with_isolation
- rerun_with_stronger_model
- topology_review
- no_change

#### B. Recommendation Artifact
SquadOps must support a recommendation artifact containing:
- recommendation UID
- source assessment(s)
- hypothesis
- expected impact
- priority
- confidence
- resource implications
- approval status
- follow-on experiment link if needed

#### C. Remediation Planning
Plutarch must be able to propose:
- rerun with same settings
- rerun with isolated role change
- rerun with memory patch
- rerun with changed routing
- rerun with stronger model
- remove one suspect agent from the flow
- add a validation gate
- request new eval coverage for an uncovered failure mode

### Why this matters
The improvement loop is incomplete if Plutarch can only score and complain.

---

## 1.6 Governance Capabilities

v1.1 must keep Plutarch governed.

### Required implementation in SquadOps

SquadOps must support:
- experiment approval levels
- recommendation approval workflow
- distinction between experimental and active policies
- audit trail for experiment execution
- audit trail for recommendation promotion or rejection
- budget ceilings per experiment
- model lane restrictions
- tool restrictions
- mutation scope restrictions

### Why this matters
Plutarch in v1.1 must be recommendation-producing, not self-authorizing.

---

# 2. Architecture Overview

Plutarch v1.1 consists of seven parts:

1. Benchmark Registry
2. Internal Eval Pack Framework
3. Cycle Assessment Framework
4. Squad Health and Agent Impact Assessment
5. Failure Diagnosis Layer
6. Experiment Orchestration Layer
7. Recommendation and Governance Layer

---

## 2.1 Benchmark Registry

A structured registry of role-aligned external and internal benchmarks.

Purpose:
- map roles to relevant evals
- define benchmark intent and scope
- record harness locations and execution policy
- support consistent model and role comparison

### Required artifacts
- `BenchmarkRegistryEntry`
- benchmark result history records

---

## 2.2 Internal Eval Pack Framework

A registry and harness for SquadOps-native evaluation packs.

Purpose:
- cover roles with weak public benchmark coverage
- evaluate repo-specific and architecture-specific work
- provide reusable comparison packs for experiments

### Required artifacts
- `InternalEvalPack`
- `InternalEvalCase`
- `EvalRunResult`

---

## 2.3 Cycle Assessment Framework

A scorecard for real production or sandbox cycles.

Purpose:
- assess whether an actual cycle succeeded
- measure quality, efficiency, stability, memory usefulness, and routing fit
- provide a normalized artifact for RCA and recommendations

### Required artifact
- `CycleAssessment`

---

## 2.4 Squad Health and Agent Impact Assessment

A layer specifically focused on the relationship between local agent gains and squad-level gains.

Purpose:
- measure bottlenecks
- measure handoff quality
- measure force-multiplier roles
- measure translation efficiency from individual improvement to squad improvement

### Required artifacts
- `AgentImpactAssessment`
- `SquadHealthAssessment`

---

## 2.5 Failure Diagnosis Layer

A structured diagnosis layer that operates over observability data.

Purpose:
- classify failure types
- identify first failing node
- detect local vs systemic issues
- diagnose broken cycles
- diagnose broken squads

### Required artifact
- `FailureDiagnosis`

---

## 2.6 Experiment Orchestration Layer

A governed mechanism for baseline/challenger experiments.

Purpose:
- define experiments
- run isolated comparisons
- support ablations and substitutions
- support stop conditions and budget controls

### Required artifact
- `ExperimentRun`

---

## 2.7 Recommendation and Governance Layer

A layer that turns observations and diagnoses into governed next-step proposals.

Purpose:
- produce recommendation artifacts
- rank interventions
- support approval workflow
- support adoption into active policy

### Required artifacts
- `ImprovementRecommendation`
- `PromotionDecision`

---

# 3. Key Questions the Framework Must Support

## 3.1 Can squads outperform one strong model?

The baseline must not be weak.

Plutarch should support comparison against:
- single strong model
- single strong model + tools
- single strong model + memory
- single strong model + orchestrated retries

### Required comparison dimensions
- completion rate
- first-pass acceptance
- accepted deliverables
- defect rate
- regression rate
- cost per accepted task
- throughput over an 8–10 hour window
- architectural conformance
- recovery behavior
- long-run stability

A squad is only “better” if it wins on meaningful weighted delivery outcomes, not because it generated more intermediate activity.

---

## 3.2 How does individual improvement translate into squad improvement?

Plutarch must explicitly separate:

### Local Improvement
The agent itself improved on role-aligned work.

### Systemic Improvement
The squad produced better results because of that improvement.

### Required measures
- role benchmark delta
- internal eval delta
- first-pass quality delta
- handoff acceptance delta
- downstream correction burden delta
- throughput delta
- regression delta
- completion delta

### Required derived metrics
- bottleneck index
- handoff quality score
- force multiplier score
- translation efficiency

This is the mechanism for deciding where limited tuning bandwidth should be spent.

---

# 4. Multi-Model Operating Pattern

Plutarch should support different model-backed lanes at different phases.

## 4.1 Before the Cycle
Use stronger planning/evaluator lanes for:
- experiment design
- benchmark selection
- hypothesis generation
- risk framing
- selecting baseline/challenger setups

## 4.2 During the Cycle
Use lower-cost or narrower lanes for:
- telemetry monitoring
- anomaly detection
- threshold checks
- narrow live interventions
- bounded challenger runs in isolation

## 4.3 After the Cycle
Use stronger evaluator lanes for:
- RCA support
- contrastive analysis
- recommendation generation
- model comparison interpretation
- adoption proposals

## Policy rule
Plutarch must use **policy-bounded model lanes**, not unrestricted model access.

---

# 5. Role-to-Benchmark Mapping

Public benchmark fit varies by role.

## Roles with stronger public benchmark alignment
- Dev / implementation
- tool executor / function caller
- research / browsing
- web UI operator
- support / policy workflow

## Roles with weaker public benchmark alignment
- Lead
- Strategy
- Product
- Architecture
- QA in deeper judgment mode
- orchestration and decomposition quality

These require internal evals.

### Initial map

#### Dev / Neo
External:
- SWE-bench / SWE-bench Verified
- HumanEval
- MBPP
- Aider Polyglot

Internal:
- bounded code fix
- contract evolution propagation
- DDD boundary preservation
- Hex adapter refactor
- seeded regression repair
- golden-source rebuild

#### Tool Executor / Data
External:
- BFCL
- τ-bench

Internal:
- tool routing tasks
- API sequencing
- schema transformation
- structured extraction tasks

#### Research / Analyst
External:
- BrowseComp
- GAIA

Internal:
- vendor comparison
- standards lookup
- architecture precedent lookup
- evidence-grounded synthesis

#### UI Walker / Product Operator
External:
- WebArena
- VisualWebArena

Internal:
- product walkthrough
- click-path verification
- guided-tour tasks
- UI-state validation

#### QA
External:
- partial only; no single benchmark is sufficient

Internal:
- seeded defect detection
- regression identification
- contract drift detection
- architecture boundary violation detection
- artifact completeness review

#### Strategy / Product / Architecture
External:
- partial generalist signal only

Internal:
- PRD generation quality
- acceptance criteria completeness
- ambiguity detection
- decomposition quality
- architecture review pass rate
- boundary-placement correctness
- downstream rework introduced vs prevented

---

# 6. Hybrid Eval Stack

Plutarch should use three layers.

## Layer 1: External Objective Benchmarks
Purpose:
- model selection
- baseline capability comparison
- role-model mismatch detection

## Layer 2: Internal SquadOps Eval Packs
Purpose:
- evaluate repo-specific and architecture-specific work
- assess the roles public benchmarks do not cover well

## Layer 3: Live Cycle Assessment
Purpose:
- measure actual operating performance under real work

The three together create a more honest improvement system than any one layer alone.

---

# 7. Required Artifact Model

Below are the core artifacts v1.1 should implement.

## 7.1 BenchmarkRegistryEntry
```yaml
kind: BenchmarkRegistryEntry
uid: benchmark-entry-dev-swebench
role: dev
benchmark: swe_bench_verified
type: external
purpose:
  - model_selection
  - regression_tracking
harness: evals/external/swe_bench_verified
cadence: on_demand
owner: eval
notes:
  - "best external fit for repo issue resolution style tasks"
```

## 7.2 CycleAssessment
```yaml
kind: CycleAssessment
uid: cycle-assessment-0042
cycle_uid: cycle-0042
task_uid: task-1284
role: dev
agent: neo
model: qwen-coder-32b
assessment_window: single_cycle

scores:
  outcome: 0.85
  quality: 0.78
  efficiency: 0.61
  memory: 0.73
  routing: 0.54
  stability: 0.80
  benchmark_alignment: 0.58

telemetry:
  retries: 3
  escalations: 1
  rewinds: 1
  qa_rejections: 1
  tests_passed_ratio: 0.92
  token_cost_usd: 1.84
  wall_clock_minutes: 21
```

## 7.3 FailureDiagnosis
```yaml
kind: FailureDiagnosis
uid: failure-diagnosis-0091
cycle_uid: cycle-0042
scope: cycle
first_failing_node: task-1284
failure_class: handoff_degradation
local_vs_systemic: systemic
dominant_cause: insufficient_boundary_validation
symptoms:
  - downstream_contract_mismatch
  - qa_rejection
likely_contributors:
  - memory_rule_missing
  - escalation_late
confidence: medium
```

## 7.4 AgentImpactAssessment
```yaml
kind: AgentImpactAssessment
uid: agent-impact-0017
agent: neo
role: dev
window: release_v1_1_eval_window

individual_delta:
  external_benchmark_delta: 0.07
  internal_eval_delta: 0.11
  first_pass_quality_delta: 0.09

squad_translation:
  deliverable_quality_delta: 0.04
  throughput_delta: 0.03
  regression_delta: -0.02
  handoff_acceptance_delta: 0.10

derived:
  bottleneck_index: 0.72
  force_multiplier_score: 0.68
  translation_efficiency: 0.44
```

## 7.5 SquadHealthAssessment
```yaml
kind: SquadHealthAssessment
uid: squad-health-0003
squad_uid: squad-main
window: release_v1_1_eval_window

health:
  topology_health: medium
  coordination_health: low
  handoff_health: medium
  stability_health: medium

bottlenecks:
  - qa
  - dev_handoff

signals:
  repeated_rework: true
  downstream_rejection_high: true
  escalation_pattern_inefficient: true
```

## 7.6 ExperimentRun
```yaml
kind: ExperimentRun
uid: experiment-0021
hypothesis: "Routing contract-heavy changes to a stronger dev lane earlier will reduce rework."
baseline_config: routing-policy-v3
challenger_config: routing-policy-v3a
task_pack: internal_eval_contract_changes
budget_cap_usd: 15
time_cap_minutes: 120
stop_conditions:
  - cost_cap
  - regression_detected
status: completed
result_links:
  - cycle-assessment-100
  - cycle-assessment-101
```

## 7.7 ImprovementRecommendation
```yaml
kind: ImprovementRecommendation
uid: improvement-rec-0048
source_artifacts:
  - cycle-assessment-0042
  - failure-diagnosis-0091
type: routing_change
priority: medium
confidence: medium
expected_impact: reduce_contract_rework
action: escalate_earlier_for_multi_boundary_contract_changes
approval_status: pending
```

---

# 8. Cycle Assessment Scorecard

Every meaningful cycle should produce a `CycleAssessment`.

## Dimensions
- outcome
- quality
- efficiency
- memory
- routing
- stability
- benchmark alignment

## Additional requirement
v1.1 should also allow scorecard linkage to:
- related failure diagnoses
- related recommendations
- related experiment runs
- related memory proposals

That creates traceability from execution to improvement.

---

# 9. Failure Diagnosis Model

v1.1 must treat diagnosis as a first-class subsystem.

## Required diagnosis questions
- What failed first?
- What failed later as a symptom?
- Was the issue local or systemic?
- Was the issue likely due to memory, prompt, routing, model capability, tooling, environment, or topology?
- Was the failure recoverable?
- Was recovery attempted well?
- What is the most plausible next experiment to isolate the cause?

## Required outputs
- failure class
- first failing node
- local vs systemic classification
- likely contributors
- confidence
- candidate remediation path

---

# 10. Recommendation Taxonomy

The system should not only score. It should propose next actions.

## Categories
- memory_update
- prompt_update
- routing_change
- model_comparison
- model_assignment_change
- tuning_or_config_change
- rerun_same_config
- rerun_with_isolation
- rerun_with_stronger_model
- topology_review
- no_change

## Important rule
Every recommendation should point to:
- supporting evidence
- expected impact
- confidence
- approval requirement

---

# 11. What Must Be Implemented in SquadOps for v1.1

This is the concrete implementation checklist.

## 11.1 Telemetry and Eventing
Implement:
- structured cycle events
- structured agent-step events
- structured handoff events
- structured escalation/rewind events
- structured memory retrieval events
- structured validation/test events
- structured cost/time events

## 11.2 Artifact Persistence
Implement persistence for:
- prompts/instruction template version references
- memory bundle references
- artifact versions and diffs
- cycle assessments
- failure diagnoses
- agent impact assessments
- squad health assessments
- experiment runs
- improvement recommendations

## 11.3 Eval Infrastructure
Implement:
- benchmark registry
- internal eval pack registry
- first-wave internal eval harness
- result history storage
- model comparison execution surface

## 11.4 Diagnosis Infrastructure
Implement:
- failure classification taxonomy
- first-failing-node detection support
- local vs systemic analysis support
- broken cycle diagnostic workflow
- broken squad diagnostic workflow

## 11.5 Experiment Infrastructure
Implement:
- experiment definition object
- baseline/challenger config support
- isolated execution support
- cost/time/stop controls
- replay and seeded-failure execution support

## 11.6 Model Lane Policy
Implement:
- planning lane definition
- monitoring lane definition
- evaluation lane definition
- allowed models per lane
- cost ceilings per lane
- approval requirements per lane

## 11.7 Recommendation Workflow
Implement:
- recommendation schema
- recommendation review workflow
- approval status tracking
- promotion decision logging
- linkage to MemoryRule proposal flow where applicable

## 11.8 Historical Analysis Support
Implement:
- ability to query past assessments
- ability to detect repeated failure classes
- ability to detect trend regressions
- ability to compare pre/post change outcomes

---

# 12. Rollout Plan

## Phase 1 — Schema and Contracts
- define all core artifact schemas
- define observability contracts
- define event taxonomy
- define failure taxonomy

## Phase 2 — First-Wave Infrastructure
- benchmark registry
- internal eval pack registry
- telemetry persistence
- cycle assessment generation

## Phase 3 — Diagnosis and Experimentation
- failure diagnosis workflow
- experiment definition and execution support
- isolated baseline/challenger runs

## Phase 4 — Recommendation Layer
- recommendation generation
- recommendation review workflow
- MemoryRule proposal handoff

## Phase 5 — Agent and Squad Impact
- agent impact assessment
- squad health assessment
- translation efficiency reporting

---

# 13. Success Criteria for v1.1

Plutarch v1.1 is successful if it can:

1. observe and reconstruct a full cycle execution with structured evidence
2. diagnose at least the basic cause of a broken cycle
3. produce a first-pass squad health assessment
4. compare at least one squad configuration against at least one strong single-model baseline
5. compare at least one role across at least two models under the same eval pack
6. generate evidence-backed recommendations in the defined taxonomy
7. identify at least one case where individual improvement did or did not translate into squad improvement
8. do all of the above without autonomous mutation of active production policy

---

# 14. Risks

- overbuilding the experiment system before the app-building loop is stable
- generating too much telemetry with too little signal
- false confidence from synthetic evals
- noisy recommendations
- overfitting to benchmark behavior
- misclassifying local failures as systemic
- high implementation overhead in v1.1

---

# 15. Mitigations

- focus first on Dev, QA, Research, and Tool Executor roles
- keep v1.1 recommendation-producing, not self-authorizing
- start with a narrow first-wave artifact set
- keep telemetry structured and purpose-driven
- preserve a no-change path
- use benchmark + internal eval + live cycle assessment together
- build diagnosis around first-failing-node and repeated-failure logic

---

# 16. Alternatives Considered

## 16.1 Keep the earlier higher-level SIP only
Rejected because it does not specify the operational support Plutarch needs.

## 16.2 Build Plutarch as a pure external sidecar analyst
Rejected because it would lack sufficient access to internal state, experiments, and replay surfaces.

## 16.3 Make Plutarch fully autonomous in v1.1
Rejected because governance and trust risk is too high before the scoring and diagnosis system is proven.

---

# 17. Open Questions

- Should `FailureDiagnosis` be generated automatically first, or drafted and then reviewed?
- Which internal eval packs should be in the very first wave after Dev?
- Should squad topology changes be recommendation-only in v1.1, or require a separate design review?
- How should weighted scorecards be calibrated initially?
- How much historical retention is needed for useful trend analysis without overcomplicating storage?
- Should challenger lanes such as NemoClaw be explicitly deferred to v1.2, even if the extension points exist in v1.1?

---

# 18. Recommendation

Accept this SIP for v1.1 with the explicit understanding that **Plutarch is not only an experiment idea but a supported system capability**.

That means SquadOps must implement:
- observability contracts
- diagnostic artifacts
- experiment primitives
- registry access surfaces
- recommendation workflows
- governance boundaries

Without those, Plutarch cannot reliably execute cycles, diagnose failures, or perform credible experiments.

With those, Plutarch becomes a concrete path toward disciplined continuous improvement and toward the broader goal of sustained autonomous app building over long-horizon runs.

---

## Appendix A — Plutarch Identity

**Name:** Plutarch  
**Role:** Master Experimenter  
**Mission:** Design bounded experiments, observe execution, diagnose failures, compare baselines, and recommend evidence-backed improvements to memory, prompts, routing, model assignment, and squad structure.

**Primary Questions Owned:**
1. Can squads outperform a single strong model?
2. How does individual-agent improvement translate into squad improvement?
3. What broke in this cycle or squad?
4. What change is most likely to improve the next run?

---

## Appendix B — Short Charter

**Plutarch measures whether coordinated specialization, memory, and governance allow SquadOps to outperform a single strong model in long-horizon autonomous app building, diagnoses what breaks when cycles or squads fail, and determines which changes produce the highest squad-level return.**
