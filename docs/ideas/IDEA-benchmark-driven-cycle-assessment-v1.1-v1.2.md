# IDEA: Benchmark-Driven Cycle Assessment for SquadOps
## Target Release: v1.1 / v1.2

### Status
Draft

### Owner
Strategy / Architecture / Eval

### Summary
Introduce a benchmark-driven cycle assessment capability for SquadOps that evaluates agent roles against objective external benchmarks where available, combines that with SquadOps-native internal evals, scores cycle performance, and produces structured recommendations for memory updates, model comparison, routing changes, and tuning priorities.

This idea extends the broader collaborative memory direction by adding an explicit measurement loop:
- benchmark the role
- observe cycle performance
- compare actual outcomes against expected role capability
- recommend targeted improvements
- feed approved lessons back into MemoryRules, routing, prompts, and model policy

The goal is not to turn SquadOps into a leaderboard product. The goal is to create a disciplined evaluation and feedback system that can answer:
- which model is best for which role?
- which agent is regressing?
- which failures should become MemoryRules?
- when should routing or escalation policy change?
- when is prompt or memory tuning sufficient vs when is a model swap justified?

---

## Problem

SquadOps will likely generate a large amount of execution evidence, but raw activity volume does not equal trustworthy performance insight.

Without a benchmark and assessment layer, several things become hard to answer with confidence:
- whether an agent is actually improving
- whether a given model is underperforming for its assigned role
- whether a failure is due to model capability, missing memory, weak routing, poor decomposition, or weak task setup
- whether premium-model usage is buying real value
- whether cycle-level quality is rising because the system is better, or because the tasks have become easier
- whether a specific failure should lead to a memory update, a prompt update, a model change, or no change at all

This can lead to:
- subjective impressions rather than measurable evidence
- noisy RCA without a repeatable scoring baseline
- over-rotating on anecdotal failures
- unnecessary model churn
- excessive escalation to larger models
- weak confidence in long-term system quality

---

## Opportunity

SquadOps can treat evaluation as a first-class operating capability.

The system can combine:
1. **objective external benchmarks** for role-aligned capability measurement
2. **internal SquadOps benchmark tasks** aligned to the actual repo, artifacts, and workflows
3. **cycle-native telemetry** such as retries, escalations, rework, latency, cost, and quality outcomes
4. **contrastive RCA** to determine whether failures should become new MemoryRules or trigger tuning changes

The result would be a more disciplined assessment loop that supports:
- role-to-model fit analysis
- model comparison under the same harness
- memory effectiveness measurement
- targeted change recommendations
- evidence-based release quality decisions

---

## Why This Fits SquadOps

This idea aligns well with the current SquadOps direction:
- you already care about RCA, rewind, and correction rather than hand-waving over failure
- you already assume heterogeneous model routing
- you already want premium inference used intentionally, not casually
- you already value golden-source comparison, quality gates, and structured outputs
- you already want a force multiplier, which requires measurable performance and not just impressive demos

This idea also pairs naturally with collaborative memory:
- benchmarks help reveal recurring failure classes
- cycle assessment helps determine whether a failure came from missing capability or missing guidance
- approved lessons can become MemoryRules
- memory effectiveness can be measured by before/after score deltas and cycle efficiency changes

---

## Goals

- Establish objective role-aligned evaluation where external benchmarks exist
- Create SquadOps-native evals for roles that do not have good public benchmarks
- Score cycle performance in a structured and repeatable way
- Compare models for the same role under the same harness
- Recommend changes in memory, routing, prompt policy, or model assignment
- Make evaluation outputs useful to RCA, not separate from it
- Support release gating and ongoing health monitoring

---

## Non-Goals

- Blindly optimizing SquadOps to public benchmark leaderboards
- Replacing human judgment for architecture or product decisions
- Assuming that benchmark wins automatically translate to repo-specific excellence
- Building a public benchmark submission platform in v1
- Fully autonomous model swapping without review
- Treating all roles as equally benchmarkable with public suites

---

## Core Idea

Add a benchmark-driven cycle assessment subsystem made of four parts:

1. **Role Benchmark Registry**
   A mapping of SquadOps roles to external and internal benchmark suites.

2. **Cycle Assessment Scorecard**
   A normalized scorecard that measures the actual performance of a cycle.

3. **Recommendation Engine**
   A decision layer that proposes memory updates, prompt tuning, routing changes, model comparisons, or model swaps based on observed evidence.

4. **Improvement Feedback Loop**
   A mechanism that routes approved recommendations into MemoryRules, eval baselines, routing policy, or model config.

---

## Release Framing

### v1.1 focus
Build the minimum viable evaluation backbone:
- role-to-benchmark map
- benchmark registry artifact
- cycle scorecard schema
- manual or semi-automated assessment workflow
- recommendation categories
- internal eval harness for SquadOps-native tasks
- tie-ins to RCA and MemoryRule proposals

### v1.2 focus
Expand into adaptive and more automated eval operations:
- scheduled benchmark runs
- per-role trend analysis
- automatic comparison across candidate models
- memory effectiveness analytics
- routing policy recommendations
- release gating from eval thresholds
- eval dashboards and longitudinal health metrics

---

## External Benchmark Landscape by Role

Not every role has a strong public benchmark. The fit varies.

### 1. Dev / Implementation Agents
Best objective options:
- **SWE-bench / SWE-bench Verified**
- **HumanEval**
- **MBPP**
- **Aider Polyglot**

Why they matter:
- SWE-bench evaluates real GitHub issue resolution against actual repos and tests.
- SWE-bench Verified is the human-validated subset and is generally the more trusted view.
- HumanEval focuses on function-level code generation with correctness checked by tests.
- MBPP covers simpler Python programming tasks and is useful for lightweight coding checks.
- Aider Polyglot stresses coding and editing ability across multiple languages and iterative fix loops.

Best SquadOps fit:
- Neo / Dev
- code-fixing agents
- implementation specialists
- repo-modifying execution roles

### 2. Tool-Use / Function-Calling Agents
Best objective options:
- **BFCL** (Berkeley Function Calling Leaderboard)
- **τ-bench** for tool + policy conversation settings

Why they matter:
- BFCL measures function-calling correctness and executability across realistic tool schemas.
- τ-bench evaluates dynamic user-agent-tool interaction with policy constraints.

Best SquadOps fit:
- executor agents
- API / tool orchestrators
- data-query agents
- workflow-driving assistants

### 3. Research / Browsing Agents
Best objective options:
- **BrowseComp**
- **GAIA**

Why they matter:
- BrowseComp focuses on locating difficult-to-find information through browsing.
- GAIA evaluates broader general-assistant capability, including reasoning, tool use, browsing, and multimodal problem solving.

Best SquadOps fit:
- research agents
- market / vendor analysis roles
- evidence-gathering agents
- policy or standard lookup tasks

### 4. Web UI / App-Operation Agents
Best objective options:
- **WebArena**
- **VisualWebArena**
- broader WebArena-x family where relevant

Why they matter:
- WebArena evaluates realistic web-task completion in controlled environments.
- VisualWebArena adds visual and multimodal interaction stress.

Best SquadOps fit:
- UI-walker agents
- product demo or test agents
- browser automation roles
- future GuideRail / app navigation test agents

### 5. General Digital Worker / Cross-Functional Agents
Best objective options:
- **TheAgentCompany**
- **GAIA**
- selected τ-bench scenarios

Why they matter:
- TheAgentCompany is closer to a simulated workplace benchmark than a narrow coding or browsing suite.
- It blends browsing, code, communication, and task execution.

Best SquadOps fit:
- generalist operators
- future lead-assistant helpers
- hybrid task runners

### 6. Support / Policy-Constrained Workflow Agents
Best objective options:
- **τ-bench**
- domain-specific internal evals

Why they matter:
- τ-bench is highly relevant for tool use under policy and user interaction constraints.

Best SquadOps fit:
- support-oriented agents
- banking or operations workflow assistants
- policy-sensitive customer interaction roles

---

## Role Coverage Reality Check

The benchmark landscape is not equally mature across all SquadOps roles.

### Roles with strong public benchmark alignment
- Dev
- tool executor
- browsing / research
- browser UI operator
- support / policy workflow

### Roles with weak or partial public benchmark alignment
- Lead
- Strategy
- Product
- Architecture
- QA reviewer in the deeper judgment sense
- decomposition / orchestration quality

These roles usually need **internal SquadOps evals** rather than dependence on public leaderboards.

That means the right answer for SquadOps is not one benchmark. It is a hybrid eval stack.

---

## Recommended Hybrid Eval Stack

### Layer 1: External objective benchmarks
Used to assess raw role capability and model comparisons under known public tasks.

Purpose:
- model selection
- baseline capability comparisons
- detect obvious model-role mismatch
- monitor broader model quality changes over time

### Layer 2: Internal SquadOps benchmark tasks
Used for repo-specific and workflow-specific relevance.

Examples:
- implement a bounded change in `hello_squad`
- repair a known seeded regression
- produce a valid PRD section from a seeded feature brief
- classify defects into the right capability / task class
- regenerate a design artifact that matches a golden source
- update a contract and propagate required fixture/test changes
- complete a small DDD / Hex scaffold change without boundary violations

Purpose:
- assess what matters in SquadOps specifically
- avoid overfitting to generic public tasks
- test architecture and artifact quality expectations

### Layer 3: Live cycle assessment
Used to score real execution.

Examples:
- pass / fail
- first-pass quality
- retries
- escalation count
- rework needed
- QA rejection rate
- cost
- latency
- memory retrieval usefulness
- downstream breakage
- golden-source delta quality

Purpose:
- reveal how the system performs under real operating conditions

---

## Proposed SquadOps Role-to-Benchmark Map

### Neo / Dev
Primary external:
- SWE-bench Verified
- Aider Polyglot
Secondary external:
- HumanEval
- MBPP
Primary internal:
- repo issue repair tasks
- scaffold extension tasks
- contract change propagation tasks
- golden-source reproduction checks

### Data / Tool Executor
Primary external:
- BFCL
- τ-bench
Primary internal:
- tool routing tasks
- API sequencing tasks
- schema extraction and transformation tasks
- evidence gathering with structured output tasks

### Research / Analyst
Primary external:
- BrowseComp
- GAIA
Primary internal:
- vendor comparison tasks
- standards / policy evidence lookup
- research synthesis with source-grounded output
- architecture precedent lookup

### UI Walker / Product Operator
Primary external:
- WebArena
- VisualWebArena
Primary internal:
- product walkthrough tasks
- guided-tour tasks
- click-path verification
- UI-state validation tasks

### Lead / Strategy / Product / Architecture
Primary external:
- partial only; GAIA or TheAgentCompany may provide some signal, but not enough by themselves
Primary internal:
- PRD scoring
- decomposition scoring
- acceptance criteria completeness
- architecture review pass rate
- downstream rework introduced vs prevented
- handoff quality
- decision trace quality
- requirement coverage and ambiguity reduction

### QA
Primary external:
- partial overlap with coding and tool benchmarks, but no single public benchmark really captures deep QA judgment
Primary internal:
- seeded defect detection
- regression identification
- contract drift detection
- test adequacy review
- artifact completeness checks
- golden-source variance review

---

## Proposed Cycle Assessment Scorecard

Each cycle should produce a scorecard with both absolute and diagnostic measures.

### Scorecard dimensions

#### 1. Outcome Score
Did the cycle accomplish the objective?
- complete success
- partial success
- failure
- blocked / invalid task setup

#### 2. Quality Score
How good was the output?
- tests passed
- artifact completeness
- conformance to contract
- architectural correctness
- review acceptance
- defect escape rate

#### 3. Efficiency Score
How expensive and noisy was the path?
- number of turns
- retries
- rewinds
- escalations
- latency
- token / dollar cost

#### 4. Memory Score
Did memory help?
- relevant rules retrieved
- rules followed vs ignored
- rule usefulness correlation
- new repeated failure class observed
- candidate new MemoryRule detected

#### 5. Routing Score
Was the chosen model/agent path appropriate?
- underpowered model selected
- overpowered model selected
- escalation justified or avoidable
- handoff sequence appropriate or wasteful

#### 6. Stability Score
Did the result hold up downstream?
- regression introduced
- downstream task breakage
- follow-on correction required
- golden-source deviation severity

#### 7. Benchmark Alignment Score
How does live performance compare to expected role capability?
- below expected
- on profile
- above expected

This is especially useful when comparing a role’s live results against:
- recent external benchmark standing
- recent internal eval standing
- recent cycle trend

---

## Example Cycle Assessment Artifact

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

memory_observations:
  retrieved_rules:
    - mem-rule-0042
    - mem-rule-0118
  likely_helpful:
    - mem-rule-0042
  ignored_or_violated:
    - mem-rule-0118
  candidate_new_rule: true

diagnostics:
  dominant_failure_mode: contract_drift
  likely_cause: insufficient_boundary_validation
  benchmark_gap_signal: moderate

recommendations:
  - type: memory_update
    priority: high
    action: draft_new_rule_from_contrastive_rca
  - type: routing_change
    priority: medium
    action: escalate earlier for multi-boundary contract changes
  - type: model_comparison
    priority: medium
    action: compare against claude-sonnet and gpt-coder on same internal task pack
```

---

## Recommendation Categories

The assessment layer should not just score. It should recommend.

### 1. Memory Update Recommendation
Use when:
- a repeated failure class appears
- a contrastive RCA reveals a reusable invariant
- memory was absent, weak, or mis-scoped

Examples:
- create new MemoryRule
- strengthen existing rule
- split an over-broad rule
- retire stale rule
- add role or environment scope

### 2. Prompt / Instruction Tuning Recommendation
Use when:
- failures appear procedural rather than capability-bound
- the model is strong enough, but instructions underconstrain the behavior
- consistent formatting or verification steps are missing

Examples:
- require explicit contract validation step
- require artifact completeness checklist
- add role-specific verification language
- tighten “done means done” criteria

### 3. Routing Policy Recommendation
Use when:
- the wrong model was chosen for task complexity
- escalation happened late and wasted cycles
- a specialist should have been used earlier
- a weaker model handled the task fine and premium usage was unnecessary

Examples:
- escalate immediately for repo-wide refactors
- keep small model for local bounded edits
- route policy-sensitive tool tasks through a tool-strong model
- use browser-specialized path for research tasks

### 4. Model Comparison Recommendation
Use when:
- live cycle results are below expected profile
- two models may be close in cost but far apart in value
- a new model candidate should be tested

Examples:
- run same eval pack across three models
- compare first-pass quality and correction cost
- compare memory sensitivity by model family

### 5. Tuning / Configuration Recommendation
Use when:
- failures are tied to context assembly, retrieval, or decoding policy
- task classification is weak
- memory retrieval is noisy
- iteration limits or tool policies are poorly set

Examples:
- reduce retrieval count
- change task classifier granularity
- increase tool validation strictness
- alter max-turn or rewind threshold
- improve fixture diff presentation

### 6. No Change Recommendation
Use when:
- failure came from invalid task setup
- benchmark evidence and cycle history do not support intervention
- issue appears isolated and non-recurring

This is important. Not every failure should trigger system mutation.

---

## Decision Logic for Recommendations

The recommendation layer should reason roughly like this:

### Memory change likely
When:
- repeated failure class
- clear contrastive lesson
- same class improves when guidance is present
- issue is not mainly raw model capability

### Model / routing change likely
When:
- benchmark gap is persistent
- internal evals show consistent underperformance
- failures persist even with appropriate memory and prompt policy
- escalation repeatedly rescues the same task class

### Prompt / instruction change likely
When:
- failures are procedural
- benchmark capability is adequate
- the agent omits required steps rather than lacks underlying ability

### Internal eval expansion likely
When:
- the failure matters a lot in SquadOps but is not represented in the current eval pack
- a role has weak public benchmark coverage
- there is a recurring repo-specific failure mode

---

## Internal SquadOps Eval Design

Because many high-value roles are weakly benchmarked publicly, SquadOps should create its own eval packs.

### Suggested internal eval classes

#### Dev evals
- bounded code fix
- contract evolution propagation
- DDD boundary preservation
- Hex adapter refactor
- seeded regression repair
- golden-source rebuild

#### QA evals
- find seeded defect
- detect missing tests
- identify contract drift
- detect architecture boundary violation
- score artifact completeness

#### Strategy / Product evals
- transform feature brief into structured PRD section
- generate acceptance criteria
- identify ambiguity and missing decisions
- decompose initiative into tasks without leakage or omission

#### Architecture evals
- evaluate design against capability contracts
- identify wrong dependency direction
- propose bounded-context placement
- review change for cross-layer leakage

#### Research evals
- collect evidence for vendor / standard comparison
- summarize findings into structured decision memo
- verify claim grounding
- identify missing evidence

### Scoring approach
Internal evals should be scored with a mix of:
- deterministic checks where possible
- golden-source comparison
- rubric scoring
- downstream pass/fail effects
- review acceptance

---

## Benchmark-Driven Model Comparison

A useful function of the system is to compare models under the same role and harness.

### Suggested comparison dimensions
- external benchmark fit for the role
- internal eval pack score
- live cycle quality
- cost per successful completion
- escalation rate
- memory sensitivity
- correction burden after first pass
- stability of outputs over repeated runs

### Why this matters
A model that looks great on a public leaderboard may still be a poor fit if:
- it ignores your structure
- it is expensive relative to its gains
- it performs poorly with your retrieval strategy
- it generates unstable outputs on your repo tasks

Likewise, a smaller model may be excellent if:
- it performs well on your bounded internal tasks
- memory closes the gap enough
- its correction burden is low
- cost-adjusted throughput is much better

---

## Memory Effectiveness Measurement

This idea should explicitly connect to collaborative memory.

### Questions to answer
- Did memory improve first-pass success?
- Did memory reduce retries or turns?
- Did memory reduce escalations?
- Did memory reduce repeated failure classes?
- Which rules actually help by task class?
- Which rules are stale or noisy?

### Useful measurements
- success delta with vs without memory on same eval class
- cycle efficiency delta after rule introduction
- rule retrieval frequency
- rule helpfulness correlation
- rule violation frequency
- task-class-level failure reduction after rule activation

### Resulting actions
- promote rule to active
- narrow rule scope
- split rule by task class
- retire rule
- change retrieval ranking
- improve task classification

---

## Proposed Architecture

### 1. Benchmark Registry
A structured registry of:
- role
- benchmark name
- benchmark type
- external/internal
- scope notes
- harness location
- scoring method
- cadence
- owner

Example:
```yaml
kind: BenchmarkRegistryEntry
uid: benchmark-entry-neo-swebench
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
  - "best external fit for repo issue resolution role"
```

### 2. Eval Harness Layer
Runs:
- external benchmark subsets where practical
- internal task packs
- comparison runs across candidate models

### 3. Cycle Assessment Layer
Consumes:
- task telemetry
- validation results
- review outcomes
- memory retrieval logs
- routing and escalation data

### 4. Recommendation Engine
Generates:
- memory update proposals
- routing changes
- prompt changes
- model comparison jobs
- model replacement recommendations
- no-change outcomes

### 5. Feedback Layer
Routes approved changes into:
- MemoryRule registry
- prompt templates
- routing policy
- model config
- eval pack expansion
- release readiness reporting

---

## v1.1 Design

### v1.1 components
- `BenchmarkRegistry` schema
- `CycleAssessment` schema
- manual scorecard workflow
- internal eval pack starter set
- role-to-benchmark mapping
- recommendation taxonomy
- RCA integration
- MemoryRule proposal handoff

### v1.1 operating mode
- human-reviewed
- squad-assisted analysis
- low automation risk
- clear evidence trails
- no automatic production model swapping

### v1.1 initial supported roles
Recommended first wave:
- Dev
- QA
- Research
- Tool Executor

These have the clearest starting eval paths.

---

## v1.2 Design

### v1.2 extensions
- scheduled benchmark jobs
- historical trend tracking
- model tournament runs by role
- memory effectiveness dashboards
- routing recommendation confidence scores
- release gating policies tied to eval thresholds
- automatic candidate recommendation drafting
- environment-specific eval profiles
- per-role health dashboards

### v1.2 possible advanced features
- benchmark slices by task class
- benchmark-conditioned model routing
- eval-triggered warm boot recommendations
- automated drift alerts when a role degrades
- confidence-weighted recommendation ranking

---

## Repo / Package Implications

Potential areas:
- `squad_ops/evals/`
- `squad_ops/benchmarks/`
- `squad_ops/cycle_assessment/`
- `squad_ops/recommendations/`
- `squad_ops/memory/`
- `docs/ideas/`
- `docs/evals/`

Possible modules:
- `benchmark_registry.py`
- `cycle_assessment_schema.py`
- `cycle_scorer.py`
- `recommendation_engine.py`
- `model_comparison_runner.py`
- `memory_effectiveness.py`
- `internal_eval_pack.py`

---

## Risks

- overfitting to public benchmarks
- false confidence from synthetic evals
- too much scoring complexity early
- weak rubric consistency for subjective roles
- noisy recommendations
- benchmark costs becoming excessive
- automation pressure leading to premature model churn
- treating benchmark rank as more important than actual SquadOps task success

---

## Mitigations

- use a hybrid eval stack rather than a single benchmark
- keep internal evals tightly tied to SquadOps reality
- require evidence-backed recommendations
- preserve a no-change path
- cap benchmark scope in v1.1
- start with manual review of recommendations
- separate experimental changes from active routing policy
- measure live cycle performance alongside benchmark results

---

## Open Questions

- Should benchmark results be role-level only, or tracked by agent + model + workload profile?
- How should internal eval packs be versioned as the architecture evolves?
- Should MemoryRule usefulness be measured at rule level, bundle level, or task-class level?
- Should release gating use absolute thresholds or trend thresholds?
- How should subjective artifact scoring be normalized across reviewers?
- Should benchmark cadence be scheduled, event-driven, or both?
- How much of model comparison should be run locally vs remotely?
- Should the eval system be able to trigger a recommendation to expand the internal eval pack itself?

---

## Recommendation

Target this as:
- **v1.1**: benchmark registry, cycle scorecard, internal eval pack starter set, and evidence-based recommendation outputs
- **v1.2**: automated benchmark operations, trend analytics, memory effectiveness measurement, and stronger routing/model recommendations

This is a strong companion idea to collaborative memory distillation. Together, they form a cleaner operating loop:

1. evaluate role capability  
2. assess real cycle execution  
3. run RCA on failures  
4. decide whether to change memory, prompts, routing, or models  
5. verify the change with evals and future cycle performance  

That would give SquadOps a much more defensible path toward becoming a measurable force multiplier rather than a collection of interesting agent behaviors.

---

## Suggested Next Follow-On Artifacts
1. SIP: Benchmark Registry and Cycle Assessment subsystem
2. BenchmarkRegistry schema spec
3. CycleAssessment schema spec
4. internal eval pack design for first-wave roles
5. recommendation engine decision matrix
6. MemoryRule effectiveness measurement addendum

---

## Reference Notes on Public Benchmarks Considered
The following benchmark families were considered for role mapping in this idea:
- SWE-bench / SWE-bench Verified
- HumanEval
- MBPP
- Aider Polyglot
- BFCL
- BrowseComp
- GAIA
- WebArena / VisualWebArena
- TheAgentCompany
- τ-bench
