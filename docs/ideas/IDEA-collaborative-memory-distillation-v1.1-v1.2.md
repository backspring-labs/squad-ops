# IDEA: Collaborative Memory Distillation for SquadOps
## Target Release: v1.1 / v1.2

### Status
Draft

### Owner
Strategy / Architecture

### Summary
Introduce a collaborative memory layer for SquadOps that distills reusable execution guidance from contrasted task trajectories rather than relying primarily on raw episodic history. The goal is to improve cross-agent reuse, reduce repeated failure modes, and increase cycle efficiency across heterogeneous models and roles.

This idea is inspired by the principle that shared memory is most reusable when it captures task-level invariants and failure-prevention rules, not the stylistic reasoning patterns of any one agent.

### Problem
Current or likely default memory patterns in agent systems tend to over-index on raw traces:
- full cycle transcripts
- tool call history
- prompt/response logs
- per-agent local notes
- artifact snapshots without normalized lessons

Those are useful for audit, debugging, and replay, but they are noisy as a primary reasoning substrate. In a heterogeneous squad, naive reuse of one agent’s trace-derived memory can carry agent-specific bias, local heuristics, and non-transferable reasoning habits.

For SquadOps, this creates several risks:
- repeated recurrence of the same failure class across cycles
- weak transfer of lessons between agents, roles, and model families
- prompt bloat from over-retrieving low-signal history
- unnecessary escalation to larger models
- excess Dev ↔ QA churn
- reduced value from RCA if lessons remain trapped in prose instead of normalized reusable guidance

### Opportunity
SquadOps can introduce a higher-order memory layer that transforms execution experience into compact, reusable MemoryRules. These rules would be generated through contrastive analysis of:
- failed vs successful task executions
- weaker-model attempt vs stronger-model correction
- pre-fix vs post-fix code paths
- QA-rejected vs QA-accepted outputs
- rebuilt output vs golden-source output
- regression-introducing change vs stabilized correction

The resulting memory would not store “how one agent happened to think,” but rather:
- when a class of situation is present
- what must be enforced
- what must be avoided
- what evidence supports the rule
- where the rule applies

### Core Idea
Add a collaborative memory distillation subsystem that produces normalized MemoryRules from contrastive RCA and routes those rules into future cycles using task-aware retrieval.

In practical terms:

1. SquadOps continues to preserve episodic execution history for replay and audit.
2. RCA or validation workflows compare good and bad trajectories for the same or similar task class.
3. A distillation step extracts reusable constraints.
4. Those constraints are stored in a structured memory registry.
5. Future tasks are classified before execution.
6. Only the most relevant high-confidence rules are injected into the active cycle context.

### Why This Fits SquadOps
This idea aligns strongly with existing SquadOps direction:
- RCA is already a key protocol
- golden-source validation already implies contrastive comparison
- heterogeneous model routing is a core assumption
- Pulse / quality gates already produce evidence that can feed memory distillation
- Capability Contracts give a natural scoping layer for memory applicability
- force-multiplier positioning benefits from reducing rework, not just increasing raw autonomy

### Goals
- Improve cross-agent reuse of lessons learned
- Reduce recurrence of known failure modes
- Improve first-pass quality of work products
- Reduce turns, retries, and escalation frequency
- Keep memory prompts compact and high-signal
- Make RCA outputs operationally reusable
- Preserve separation between audit memory and reasoning memory

### Non-Goals
- Replacing episodic memory, logs, or artifact history
- Storing private chain-of-thought style transcripts as the primary reusable memory object
- Building a universal memory system for all domains in v1
- Fully autonomous memory mutation without verification
- Solving long-term knowledge management for arbitrary user content

### Release Framing
This idea is best treated as a staged capability across v1.1 and v1.2.

#### v1.1 focus
Introduce the minimum viable collaborative memory foundation:
- MemoryRule artifact definition
- manual or semi-automated distillation from RCA outcomes
- task classification + filtered retrieval
- prompt injection of top-N relevant rules
- basic feedback logging on rule usefulness

#### v1.2 focus
Expand into adaptive memory operations:
- automated contrastive extraction pipelines
- confidence scoring and decay
- rule merge / split / supersession workflows
- stronger retrieval ranking
- broader integration with warm boot, golden-source validation, and model routing
- analytics on memory contribution to cycle success

### Proposed Architecture

#### 1. Memory Layers
SquadOps should explicitly separate three memory layers:

##### Episodic Memory
Stores raw execution history:
- tasks
- cycles
- messages
- tool outputs
- artifacts
- environment snapshots
- validation logs

Purpose:
- replay
- audit
- debugging
- RCA source material

##### Operational Memory
Stores environment and system facts:
- repo topology
- active contracts
- adapter mappings
- dependency state
- deployment profile facts
- known runtime capabilities
- open defects / workstream state

Purpose:
- execution grounding

##### Collaborative Reasoning Memory
Stores distilled reusable guidance:
- invariants
- forbidden patterns
- trigger conditions
- recommended enforcement steps
- applicability metadata
- evidence references

Purpose:
- future execution guidance

This idea concerns the third layer.

#### 2. New Artifact: MemoryRule
Introduce a canonical structured artifact to represent distilled execution guidance.

Suggested baseline shape:

```yaml
kind: MemoryRule
uid: mem-rule-0001
status: active
domain: squad_ops
scope:
  capability: implementation.execution
  task_class: adapter_contract_change
  roles:
    - dev
    - qa
  environments:
    - local
    - aws
trigger: "When modifying an adapter boundary used by more than one workload"
enforce:
  - "update contract tests before merge"
  - "validate downstream schema compatibility against fixtures"
avoid:
  - "changing payload shape without fixture regeneration"
  - "treating integration coverage as sufficient contract validation"
evidence:
  source_type: contrastive_rca
  source_refs:
    - task-1284
    - cycle-77
    - qa-run-443
confidence: high
freshness:
  introduced_in: v1.1
  last_validated_at: 2026-03-29
supersedes: []
tags:
  - contract-drift
  - adapter
  - regression-prevention
```

### Distillation Model

#### Contrast Sources
The strongest initial sources for rule extraction in SquadOps are:

1. Failed attempt vs successful correction  
2. QA-rejected output vs QA-accepted revision  
3. Warm rebuild vs golden source  
4. Regression-causing change vs stabilized fix  
5. Small-model draft vs large-model recovery  
6. Human override vs original agent path

#### Distillation Output
Each extracted rule should answer:
- what situation triggered the lesson?
- what invariant needed to hold?
- what anti-pattern caused failure?
- what evidence proves the lesson?
- where is the lesson applicable?

#### Preferred Rule Format
A normalized natural-language format is useful for both storage and prompt injection:

**When [trigger], enforce [constraint or practice]; avoid [failure pattern].**

Example:
- When updating a message schema consumed by multiple workloads, enforce fixture-backed contract validation before integration testing; avoid assuming downstream compatibility from unit coverage alone.

### Retrieval Strategy
A key part of this idea is that retrieval should be task-aware before similarity-aware.

#### Retrieval Flow
1. Classify the current task
2. Filter candidate MemoryRules by scope:
   - domain
   - capability
   - task_class
   - role
   - environment
3. Rank remaining candidates by:
   - relevance
   - confidence
   - recency
   - verified usefulness
   - rule specificity
4. Inject only the top few rules into the cycle

#### Initial Guidance Budget
Recommended initial budget:
- top 3 rule bundles
- each bundle contains 1–3 rules
- deduplicate overlapping rules
- enforce a strict token ceiling

This protects the cycle from memory overloading and low-signal prompt stuffing.

### Integration Points

#### RCA Protocol
RCA becomes a primary feeder for collaborative memory.
Every meaningful failure investigation should be eligible to produce:
- zero new rules
- one refined rule
- multiple rules if distinct failure mechanisms are found

#### Pulse / Quality Gates
Pulse checks can provide evidence:
- rule followed / violated
- pass / fail outcome
- whether injected rule correlated with success

#### Warm Boot / Golden Source
Golden-source comparison is an excellent contrastive input:
- generated artifact diverges from canonical reference
- corrected artifact reveals enforceable invariants

#### Capability Contracts
Capability Contracts provide scoping anchors for rules:
- task class
- interface boundary
- enforcement obligations
- downstream dependencies

#### Model Routing
Collaborative memory can lower unnecessary premium-model invocation by:
- improving first-pass outputs from smaller models
- reducing retries
- helping route escalation only when rule-guided execution still fails

### Initial v1.1 Design
For v1.1, keep this intentionally constrained.

#### v1.1 Components
- `MemoryRule` schema
- `memory_rules/` registry
- manual or assisted distillation workflow
- task classification service
- simple filtered retrieval
- prompt assembly integration
- rule feedback logging

#### v1.1 Authoring Model
Likely best as:
- human-reviewed
- squad-assisted
- no silent self-writing into active memory

This keeps the memory layer trustworthy while the patterns mature.

#### v1.1 Example Flow
1. Dev cycle fails contract compatibility downstream
2. QA detects regression
3. RCA compares failing and corrected paths
4. Squad drafts one or more MemoryRules
5. Human or Lead approves rule
6. Rule enters active registry
7. Future adapter-contract tasks retrieve that rule pre-execution

### v1.2 Expansion
v1.2 can extend the subsystem toward managed evolution.

#### Candidate v1.2 Features
- automated contrastive extraction jobs
- rule scoring based on observed impact
- rule conflict detection
- supersession chains
- confidence decay for stale rules
- split / merge recommendations
- role-specific views of shared rules
- metrics dashboard for memory contribution
- selective environment-specific rule packs
- model-family sensitivity analysis

### Proposed Repo / Package Implications
Potential areas:
- `squad_ops/memory/`
- `squad_ops/memory_rules/`
- `squad_ops/rca/`
- `squad_ops/retrieval/`
- `squad_ops/task_classification/`
- `docs/ideas/`
- `docs/architecture/`

Possible modules:
- `memory_rule_schema.py`
- `memory_distiller.py`
- `memory_registry.py`
- `memory_retriever.py`
- `task_classifier.py`
- `memory_feedback.py`

### Example Rule Categories for SquadOps
Useful early classes of MemoryRules may include:

- contract drift prevention
- fixture regeneration requirements
- adapter boundary discipline
- dependency inversion preservation
- test pyramid enforcement
- migration sequencing
- schema evolution safety
- environment parity checks
- idempotency handling
- retry / timeout guardrails
- task decomposition guidance
- artifact completeness checks
- golden-source delta review

### Risks
- low-quality rules may pollute future cycles
- overly generic rules may become platitudes
- overly specific rules may never retrieve again
- automated extraction may infer false lessons
- stale rules may outlive the architecture they describe
- too many rules may increase prompt noise rather than reduce it
- role-specific context may be lost if scoping is weak

### Mitigations
- require evidence references for every active rule
- start with human-reviewed rule approval
- enforce strict schema and scope fields
- support confidence and validation timestamps
- cap retrieval budget
- track rule usefulness explicitly
- allow retirement and supersession
- separate active rules from experimental rules

### Open Questions
- Should MemoryRules live as standalone artifacts or as a section within RCA records plus a promoted registry view?
- Should Nat own draft rule generation while Max owns retrieval and routing?
- Should QA have veto authority on rule activation when evidence is weak?
- Should rules be capability-scoped, workload-scoped, or both?
- How should rules differ between local and cloud deployment profiles?
- Should warm boot consume special golden-source rule packs?
- Is there a useful distinction between “invariant rules” and “heuristic rules”?
- How should rule usefulness be measured without overfitting to single cycles?

### Recommendation
Target this as:
- **v1.1**: foundational collaborative memory with manual / assisted MemoryRule creation and task-aware retrieval
- **v1.2**: adaptive and measurable collaborative memory evolution

This is a strong fit for SquadOps because it converts RCA from a diagnostic activity into a reusable execution advantage. It also supports the broader SquadOps thesis that a trusted squad should improve output through structured coordination and learned operational discipline, not just through bigger models or larger context windows.

### Suggested Next Follow-On Artifacts
1. SIP: Collaborative Memory Distillation subsystem
2. MemoryRule schema spec
3. RCA addendum for rule extraction workflow
4. Retrieval and routing design for task-aware memory injection
5. metrics definition for memory effectiveness
