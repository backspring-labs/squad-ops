# ADDENDUM: Proposal for Plutarch Artifact Schemas and Event Taxonomy
## Companion Addendum to: SIP-XXXX — Plutarch Experimentation and Cycle Assessment Framework
## Target Release: v1.1

### Status
Proposed Addendum

### Owner
Strategy / Architecture / Eval

### Purpose
This addendum proposes the initial schema model and event taxonomy needed to support the Plutarch framework described in the companion SIP.

The intent of this addendum is not to lock the final semantics prematurely. It is to provide a concrete, implementation-oriented design proposal that can be reviewed, tightened, and validated before coding. Claude or other design-review passes can refine the field semantics later, but SquadOps needs a strong proposed shape now in order to:
- define observable contracts
- persist the right artifacts
- support diagnosis and replay
- support baseline/challenger comparisons
- support recommendation generation
- preserve traceability from cycle execution to improvement decision

This addendum therefore focuses on:
1. artifact design principles
2. proposed core artifact set
3. proposed event taxonomy
4. required linkage and traceability rules
5. rollout sequencing for implementation

---

## 1. Design Principles

### 1.1 Artifact principles
Plutarch artifacts should be:
- explicit
- durable
- linkable
- reviewable
- minimally ambiguous
- useful for both machine processing and human inspection

### 1.2 Event principles
Events should be:
- append-only
- timestamped
- scoped
- structured enough for automation
- lightweight enough to emit throughout long runs
- expressive enough to reconstruct failure chains and experiment outcomes

### 1.3 Separation of concerns
The system should distinguish:
- raw execution events
- derived assessments
- diagnoses
- experiments
- recommendations
- promotion decisions

Do not collapse all of these into one catch-all record type.

### 1.4 Traceability requirement
Every major Plutarch conclusion should be traceable back to:
- one or more events
- one or more artifacts
- a known cycle/task/agent/model context
- a bounded assessment or experiment window

### 1.5 Reviewability requirement
Any recommendation that could affect active policy should be reviewable through linked evidence, not only through summary text.

---

## 2. Proposed Artifact Set

The v1.1 addendum proposes the following artifact families:

1. registry artifacts
2. execution artifacts
3. assessment artifacts
4. diagnosis artifacts
5. experiment artifacts
6. recommendation and governance artifacts

---

# 3. Registry Artifacts

## 3.1 BenchmarkRegistryEntry

### Purpose
Defines an external or internal benchmark known to the system.

### Why it exists
Plutarch needs a stable registry of benchmark options by role and purpose so experiments are not ad hoc.

### Proposed shape
```yaml
kind: BenchmarkRegistryEntry
uid: benchmark-entry-dev-swebench
status: active
name: swe_bench_verified
benchmark_type: external
roles:
  - dev
purpose:
  - model_selection
  - regression_tracking
scope:
  task_classes:
    - repo_issue_resolution
  environments:
    - sandbox
harness_ref: evals/external/swe_bench_verified
scoring_mode: benchmark_native
cadence: on_demand
cost_profile: medium
owner: eval
tags:
  - coding
  - repo
notes:
  - "best external fit for repo issue resolution style tasks"
```

### Minimum required fields
- uid
- status
- name
- benchmark_type
- roles
- purpose
- harness_ref

---

## 3.2 InternalEvalPack

### Purpose
Defines a SquadOps-native evaluation pack.

### Proposed shape
```yaml
kind: InternalEvalPack
uid: internal-eval-pack-contract-changes-v1
status: active
name: internal_eval_contract_changes
roles:
  - dev
  - qa
task_classes:
  - adapter_contract_change
  - boundary_validation
cases:
  - internal-eval-case-001
  - internal-eval-case-002
scoring_mode: mixed
owner: eval
version: 1
tags:
  - contract
  - regression
```

### Minimum required fields
- uid
- status
- name
- roles
- cases
- scoring_mode

---

## 3.3 InternalEvalCase

### Purpose
Defines one repeatable evaluation case within an internal pack.

### Proposed shape
```yaml
kind: InternalEvalCase
uid: internal-eval-case-001
pack_uid: internal-eval-pack-contract-changes-v1
status: active
title: propagate_contract_change_with_fixture_updates
role: dev
task_class: adapter_contract_change
setup_ref: setups/contract_case_001
expected_outputs:
  - updated_contract
  - updated_fixture
  - updated_tests
scoring_refs:
  - rubric-contract-propagation-v1
  - deterministic-check-contract-case-001
difficulty: medium
tags:
  - contract
  - fixture
```

---

## 3.4 ModelLanePolicy

### Purpose
Defines which models are allowed in which Plutarch lanes.

### Proposed shape
```yaml
kind: ModelLanePolicy
uid: model-lane-policy-v1
status: active
lanes:
  planning:
    allowed_models:
      - claude_reasoning
      - codex_high
    cost_ceiling_usd: 10
  monitoring:
    allowed_models:
      - qwen_local_small
      - llama_local_small
    cost_ceiling_usd: 2
  evaluation:
    allowed_models:
      - claude_reasoning
      - codex_high
    cost_ceiling_usd: 10
approval_requirements:
  planning: none
  monitoring: none
  evaluation: none
notes:
  - "production mutation remains out of scope for v1.1"
```

---

# 4. Execution Artifacts

## 4.1 CycleRecord

### Purpose
A durable summary record for a cycle.

### Proposed shape
```yaml
kind: CycleRecord
uid: cycle-0042
status: completed
cycle_type: app_build
squad_uid: squad-main
root_task_uid: task-1284
environment:
  runtime_profile: local
  repo_ref: repo-main
  branch_ref: experiment/plutarch-0042
started_at: 2026-03-29T09:00:00Z
ended_at: 2026-03-29T12:20:00Z
result: partial_success
event_stream_ref: events/cycle-0042.jsonl
artifacts:
  - artifact-001
  - artifact-002
tags:
  - v1_1_eval_window
```

### Why this artifact matters
Events are append-only, but a top-level cycle object is still needed for indexing, retrieval, and linkage.

---

## 4.2 TaskRecord

### Purpose
Represents a task instance within a cycle.

### Proposed shape
```yaml
kind: TaskRecord
uid: task-1284
cycle_uid: cycle-0042
parent_task_uid: null
status: failed
task_class: adapter_contract_change
role_expected: dev
assigned_agent: neo
assigned_model: qwen-coder-32b
lane: execution
started_at: 2026-03-29T09:05:00Z
ended_at: 2026-03-29T09:43:00Z
outcome: failed_validation
dependencies: []
memory_bundle_refs:
  - memory-bundle-011
prompt_template_ref: prompt-dev-v7
artifact_refs:
  - artifact-004
  - artifact-005
```

---

## 4.3 HandoffRecord

### Purpose
Represents a handoff between roles or agents.

### Proposed shape
```yaml
kind: HandoffRecord
uid: handoff-0029
cycle_uid: cycle-0042
from_agent: nat
to_agent: neo
from_role: strategy
to_role: dev
status: rejected
task_uid: task-1284
artifact_refs:
  - artifact-003
rejection_reason: insufficient_acceptance_criteria
created_at: 2026-03-29T09:02:00Z
resolved_at: 2026-03-29T09:06:00Z
```

### Why this matters
Squad health depends heavily on handoff quality. Handoffs need first-class representation.

---

## 4.4 ArtifactRecord

### Purpose
Represents a generated or modified artifact.

### Proposed shape
```yaml
kind: ArtifactRecord
uid: artifact-005
cycle_uid: cycle-0042
task_uid: task-1284
artifact_type: code_patch
path: src/adapters/payment_adapter.py
version: 3
parent_version_uid: artifact-004
status: superseded
generator_agent: neo
generator_model: qwen-coder-32b
created_at: 2026-03-29T09:31:00Z
diff_ref: diffs/artifact-005.diff
validation_refs:
  - validation-009
```

---

## 4.5 ValidationRun

### Purpose
Represents a test or validation execution.

### Proposed shape
```yaml
kind: ValidationRun
uid: validation-009
cycle_uid: cycle-0042
task_uid: task-1284
validation_type: unit_and_contract
status: failed
runner_ref: pytest_contract_suite
started_at: 2026-03-29T09:35:00Z
ended_at: 2026-03-29T09:37:00Z
summary:
  passed: 52
  failed: 3
failure_refs:
  - failure-signal-001
```

---

# 5. Assessment Artifacts

## 5.1 CycleAssessment

### Purpose
Represents the scored assessment of a cycle or task window.

### Proposed shape
```yaml
kind: CycleAssessment
uid: cycle-assessment-0042
cycle_uid: cycle-0042
task_uid: task-1284
scope: single_task
role: dev
agent: neo
model: qwen-coder-32b

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
  token_cost_usd: 1.84
  wall_clock_minutes: 21

linked_diagnoses:
  - failure-diagnosis-0091
linked_recommendations:
  - improvement-rec-0048
```

### Design note
Scores should be normalized, but exact formulas can remain configurable.

---

## 5.2 AgentImpactAssessment

### Purpose
Measures how individual-agent change relates to squad-level outcomes.

### Proposed shape
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

### Design note
The exact semantics of translation efficiency should be validated before implementation hardening.

---

## 5.3 SquadHealthAssessment

### Purpose
Represents the health of the squad over a window.

### Proposed shape
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

### Why this matters
Broken squads need explicit representation, not only broken tasks.

---

# 6. Diagnosis Artifacts

## 6.1 FailureDiagnosis

### Purpose
A structured diagnosis of a failure.

### Proposed shape
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
candidate_remediations:
  - rerun_with_stronger_model
  - memory_update
confidence: medium
```

### Required fields
- uid
- cycle_uid
- scope
- failure_class
- local_vs_systemic
- confidence

### Design note
This artifact is central. It should be easy to produce manually first, then partially automate later.

---

## 6.2 FailureSignal

### Purpose
A smaller-grain signal emitted during execution or validation that may feed diagnosis.

### Proposed shape
```yaml
kind: FailureSignal
uid: failure-signal-001
cycle_uid: cycle-0042
task_uid: task-1284
signal_type: contract_validation_failure
source: validation_run
severity: medium
detected_at: 2026-03-29T09:36:00Z
details_ref: logs/contract_failures_0042.json
```

### Why it exists
This allows noisy or low-level evidence to be persisted without prematurely declaring a diagnosis.

---

# 7. Experiment Artifacts

## 7.1 ExperimentRun

### Purpose
Represents a baseline/challenger experiment.

### Proposed shape
```yaml
kind: ExperimentRun
uid: experiment-0021
status: completed
hypothesis: "Routing contract-heavy changes to a stronger dev lane earlier will reduce rework."
baseline_config_ref: routing-policy-v3
challenger_config_ref: routing-policy-v3a
task_pack_ref: internal_eval_contract_changes
budget_cap_usd: 15
time_cap_minutes: 120
stop_conditions:
  - cost_cap
  - regression_detected
runs:
  baseline:
    - cycle-100
  challenger:
    - cycle-101
result_summary_ref: experiment-results-0021
```

---

## 7.2 ExperimentResultSummary

### Purpose
Provides a compact result view for an experiment.

### Proposed shape
```yaml
kind: ExperimentResultSummary
uid: experiment-results-0021
experiment_uid: experiment-0021
winner: challenger
confidence: medium
metric_deltas:
  quality: 0.08
  efficiency: 0.03
  regression_rate: -0.05
recommendation_refs:
  - improvement-rec-0048
notes:
  - "challenger improved contract propagation quality with acceptable cost increase"
```

---

# 8. Recommendation and Governance Artifacts

## 8.1 ImprovementRecommendation

### Purpose
Represents a proposed system improvement.

### Proposed shape
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
resource_implications:
  token_cost_change: low
  latency_change: medium
approval_status: pending
```

### Required fields
- uid
- source_artifacts
- type
- priority
- confidence
- action
- approval_status

---

## 8.2 PromotionDecision

### Purpose
Represents the outcome of approving or rejecting a recommendation.

### Proposed shape
```yaml
kind: PromotionDecision
uid: promotion-decision-0012
recommendation_uid: improvement-rec-0048
decision: approved
decided_by: lead
decided_at: 2026-03-29T15:12:00Z
effective_change_ref: routing-policy-v3a
notes:
  - "approved for sandbox promotion only"
```

---

# 9. Event Taxonomy Proposal

This section proposes the event stream categories needed for observability.

## 9.1 Event envelope

Every event should carry a common envelope:

```yaml
event_uid: event-000001
event_type: task.started
occurred_at: 2026-03-29T09:05:00Z
cycle_uid: cycle-0042
task_uid: task-1284
agent: neo
role: dev
lane: execution
correlation_uid: corr-019
payload: {}
```

### Required common fields
- event_uid
- event_type
- occurred_at
- cycle_uid
- payload

Optional but strongly recommended:
- task_uid
- agent
- role
- lane
- correlation_uid

---

## 9.2 Event categories

### A. Cycle lifecycle events
- cycle.created
- cycle.started
- cycle.paused
- cycle.resumed
- cycle.completed
- cycle.failed
- cycle.cancelled

### B. Task lifecycle events
- task.created
- task.started
- task.blocked
- task.unblocked
- task.completed
- task.failed
- task.retried
- task.rewound

### C. Handoff events
- handoff.created
- handoff.accepted
- handoff.rejected
- handoff.revised

### D. Agent execution events
- agent.step.started
- agent.step.completed
- agent.step.failed

### E. Model lane events
- lane.selected
- lane.denied
- model.selected
- model.escalated
- model.deescalated

### F. Memory and retrieval events
- memory.classification.completed
- memory.bundle.retrieved
- memory.bundle.injected
- memory.bundle.flagged_noisy
- memory.rule.violation.suspected

### G. Tool events
- tool.invoked
- tool.completed
- tool.failed

### H. Artifact events
- artifact.created
- artifact.updated
- artifact.superseded
- artifact.diff.generated

### I. Validation events
- validation.started
- validation.completed
- validation.failed

### J. Experiment events
- experiment.created
- experiment.started
- experiment.baseline.completed
- experiment.challenger.completed
- experiment.stopped
- experiment.completed

### K. Recommendation/governance events
- recommendation.created
- recommendation.reviewed
- recommendation.approved
- recommendation.rejected
- promotion.applied

---

# 10. Event Payload Suggestions

The exact semantics can be refined later, but these event types should at least include the following payload hints.

## 10.1 `task.failed`
Suggested payload:
```yaml
failure_reason: failed_validation
retry_count: 2
escalation_count: 1
artifact_refs:
  - artifact-005
validation_refs:
  - validation-009
```

## 10.2 `memory.bundle.retrieved`
Suggested payload:
```yaml
memory_bundle_refs:
  - memory-bundle-011
classification:
  task_class: adapter_contract_change
retrieval_reason: task_class_match
```

## 10.3 `model.escalated`
Suggested payload:
```yaml
from_model: qwen-coder-32b
to_model: claude_reasoning
reason: repeated_contract_validation_failure
```

## 10.4 `handoff.rejected`
Suggested payload:
```yaml
from_agent: nat
to_agent: neo
reason: insufficient_acceptance_criteria
artifact_refs:
  - artifact-003
```

## 10.5 `validation.failed`
Suggested payload:
```yaml
validation_type: unit_and_contract
passed: 52
failed: 3
failure_signal_refs:
  - failure-signal-001
```

---

# 11. Linkage and Traceability Rules

The system should enforce the following design rules:

### Rule 1
Every `CycleAssessment` should link back to at least one `CycleRecord`.

### Rule 2
Every `FailureDiagnosis` should reference:
- a cycle
- at least one supporting event, artifact, validation, or signal

### Rule 3
Every `ImprovementRecommendation` should reference one or more source artifacts.

### Rule 4
Every `PromotionDecision` should reference exactly one recommendation.

### Rule 5
Every `ExperimentRun` should identify baseline and challenger configs explicitly.

### Rule 6
Every assessment or diagnosis tied to a specific role should preserve:
- agent
- role
- model
- lane
where applicable.

### Rule 7
Event streams should be queryable by:
- cycle
- task
- agent
- role
- experiment
- model
- lane
- time window

---

# 12. Minimum Viable Implementation Set for v1.1

Not everything has to ship at once. This addendum recommends the following minimal artifact subset for the first wave.

## Must-have artifacts
- BenchmarkRegistryEntry
- InternalEvalPack
- CycleRecord
- TaskRecord
- HandoffRecord
- ArtifactRecord
- ValidationRun
- CycleAssessment
- FailureDiagnosis
- ExperimentRun
- ImprovementRecommendation
- PromotionDecision

## Strongly recommended in first wave
- AgentImpactAssessment
- SquadHealthAssessment
- FailureSignal
- ModelLanePolicy

---

# 13. Suggested Storage and Processing Model

This is intentionally high level, but the implementation direction should likely be:

### Raw events
- append-only event log
- immutable
- cheap to emit
- used for replay and reconstruction

### Durable artifacts
- structured documents in registry/artifact store
- mutable only by versioned supersession or explicit status changes
- queryable by UID and references

### Derived outputs
- assessments, diagnoses, and recommendations are generated from events + artifacts
- they should preserve source references to avoid opaque conclusions

---

# 14. Suggested Rollout Sequence

## Phase 1 — Event envelope and core records
Implement:
- event envelope
- cycle/task/handoff/artifact/validation records
- core event taxonomy

## Phase 2 — Assessment and diagnosis artifacts
Implement:
- CycleAssessment
- FailureDiagnosis
- ImprovementRecommendation
- PromotionDecision

## Phase 3 — Eval and experiment registry
Implement:
- BenchmarkRegistryEntry
- InternalEvalPack
- InternalEvalCase
- ExperimentRun
- ExperimentResultSummary

## Phase 4 — Translation and squad health
Implement:
- AgentImpactAssessment
- SquadHealthAssessment
- supporting trend queries

---

# 15. Open Design Questions

- Should `CycleRecord` and `TaskRecord` be persisted as independent artifacts or derived from the event log plus summary materialization?
- Should `FailureDiagnosis` have one dominant cause only, or ranked causes?
- Should `ImprovementRecommendation` allow multiple actions, or one action per recommendation?
- Should `SquadHealthAssessment` be generated only on windows, or optionally per large cycle?
- How much of `ModelLanePolicy` belongs in Plutarch versus global SquadOps policy?
- Should `ArtifactRecord` be generic across docs/code/slides, or typed into separate schemas?
- Should recommendation promotion always produce a new versioned policy artifact?

---

# 16. Recommendation

Adopt this addendum as the proposed design direction for the companion SIP.

It is intentionally more specific than the SIP while still leaving room for semantic refinement. That is the right balance for now.

The important design claim is:

**Plutarch needs both an artifact model and an event model.**
Without both:
- diagnosis will be weak
- experiments will be hard to compare
- recommendations will be hard to trust
- promotion decisions will be hard to audit

With both:
- SquadOps gets a viable foundation for continuous testing, assessment, diagnosis, and governed improvement.

---

## Appendix A — Short Design Summary

Plutarch should be implemented on top of:
- registry artifacts for benchmarks, eval packs, and model lanes
- execution artifacts for cycles, tasks, handoffs, artifacts, and validations
- derived artifacts for assessments, diagnoses, experiments, and recommendations
- an append-only event taxonomy that makes reconstruction and traceability possible

That combination is the minimum viable substrate for a real master experimenter.
