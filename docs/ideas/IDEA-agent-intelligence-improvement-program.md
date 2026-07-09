---
title: Agent Intelligence Improvement Program
id: idea.agent_intelligence_improvement_program
type: idea
status: draft
created_at: 2026-04-03
updated_at: 2026-04-03
owner: Jason Ladd
tags:
  - squad_ops
  - agents
  - benchmarks
  - evaluation
  - notebooklm
  - chatgpt
  - claude
  - gemini
---

# Agent Intelligence Improvement Program

## 1. Overview

This idea defines a structured program for improving the intelligence of individual agents inside SquadOps while SquadOps itself continues to evolve as a coordination and autonomous execution framework.

The core motivation is simple:

- SquadOps needs to run autonomously for **8–10 hours**
- that requires not only stronger coordination
- but also **stronger individual agents**
- and those agents need to improve in a disciplined, measurable way rather than through ad hoc prompt tweaking

This program treats agent intelligence improvement as a first-class workstream.

It also intentionally uses the “big 3” cloud agents the user already has access to:

- ChatGPT
- Claude
- Gemini

Those systems are not the end state. They are the external intelligence partners used to help design, critique, benchmark, and improve the agents that live inside SquadOps.

The long-term goal is not dependency on the big 3. The long-term goal is to build a **durable Agent Intelligence Improvement System** that strengthens SquadOps over time.

---

## 2. Problem Statement

SquadOps is evolving well on the orchestration side:

- coordination patterns
- cycle execution
- failure handling
- recovery logic
- experiments around autonomy and runtime operation

But stronger orchestration does not automatically create stronger agents.

There are two related but distinct problems:

### Problem A — Squad coordination quality
How well does the squad decompose work, assign the right agent, sequence tasks, recover from failures, and sustain productive autonomous execution over long windows?

### Problem B — Individual agent intelligence quality
How well does a given agent perform its role-specific work compared with what that role should be capable of doing?

These two problems interact, but they are not interchangeable.

A weak agent can sometimes be partially rescued by strong orchestration.
A strong agent can still be wasted by poor orchestration.
If both are weak, long autonomous runs become theater.

This program focuses on **Problem B** without losing sight of the connection to Problem A.

---

## 3. Core Thesis

Individual agents improve fastest when they are treated like role-specific systems with:

- explicit design definitions
- explicit tool and memory boundaries
- explicit benchmark suites
- explicit promotion criteria
- explicit learning loops from real cycle outcomes

In other words:

> Agent intelligence should be improved the same way a serious engineering team improves any meaningful subsystem:
> by documenting the current design, measuring behavior against known standards, testing upgrades under controlled conditions, and promoting only what actually improves results.

This implies several commitments:

1. “Intelligence” must be role-specific, not generic.
2. Improvements must be measurable, not vibe-based.
3. Research and experimentation should be separated from canonical design docs.
4. External frontier models should be used as accelerants, not as the permanent operating substrate.
5. Internal evidence from actual SquadOps runs must become part of the improvement loop.

---

## 4. Program Goal

Build a repeatable system that continuously improves the role-specific intelligence of SquadOps agents so the squad can operate autonomously for long windows with higher quality, better judgment, and lower supervision cost.

### Success criteria
The program is successful if it produces:

- stronger role performance by individual agents
- more reliable long-duration autonomous execution
- better benchmark scores by role
- better real-cycle outcomes
- lower failure rates on known weak points
- better recovery and decision quality during drift or failure
- a reusable system for future agent improvement rather than one-off upgrades

---

## 5. Program Principles

### 5.1 Separate coordination from intelligence
Do not confuse “the squad got better” with “the agents got smarter.”
Track both separately.

### 5.2 Benchmark by role
There is no single meaningful benchmark for all agents.
Each role should be measured against what that role is supposed to do.

### 5.3 Keep the crown jewels internal
Use the big 3 for research, critique, implementation support, and comparison.
Keep canonical designs, benchmarks, artifacts, and conclusions inside the SquadOps knowledge base and repo.

### 5.4 Promote only measurable improvements
No upgrade becomes canonical unless it improves benchmark or real-cycle performance in a way that survives review.

### 5.5 Preserve institutional memory
Lessons from failed and successful cycles should become reusable evidence, not disappear into chat history.

### 5.6 Prefer structured evidence over aesthetic intuition
Prompt changes, model changes, memory changes, and tool changes should all be evaluated using evidence.

---

## 6. The Big 3 Operating Model

The big 3 should not be treated as interchangeable. Each should be used where it is strongest for this initiative.

## 6.1 ChatGPT role
Use ChatGPT for:

- program planning
- benchmark architecture
- evaluation framework design
- schema design
- artifact structure
- synthesis across many documents
- experiment design
- comparative analysis of results

ChatGPT is especially useful as the planning and evaluation architect for the program.

## 6.2 Claude role
Use Claude for:

- codebase reading
- architecture critique
- specification tightening
- prompt design pressure-testing
- implementation review
- agent behavior critique
- repo- and code-oriented improvement proposals

Claude is especially useful as a code and design critic.

## 6.3 Gemini role
Use Gemini for:

- broad research collection
- source aggregation
- NotebookLM knowledge synthesis
- research note generation
- corpus comparison
- literature and framework scanning
- agent-pattern briefing generation

Gemini plus NotebookLM is especially useful as the research library and synthesis workspace.

## 6.4 What the big 3 are not
They are not the canonical source of truth.
They are not the lasting operating substrate of SquadOps.
They are not the replacement for internal benchmark discipline.

They are accelerators.

---

## 7. NotebookLM Role in the Plan

NotebookLM is a strong fit as a **research and synthesis workspace**, but it should not be the final canonical system of record.

### Recommended use of NotebookLM
Use NotebookLM to:

- gather external research on agents and autonomous systems
- store source packs per role
- compare public frameworks and design approaches
- generate briefings from source collections
- create shared research context for future planning artifacts

### Do not use NotebookLM as the canonical source of truth for
- final SquadOps architecture
- final role definitions
- benchmark specs
- experiment results
- promotion decisions
- canonical agent design docs

### Better pattern
Use NotebookLM as a **source workspace** and keep canonical outputs in:
- markdown docs
- repo artifacts
- SIPs / IDEA docs
- benchmark specs
- experiment reports
- structured evaluation records

### Recommended NotebookLM notebook structure
1. Common Agent Architecture Research
2. Lead Agent Research
3. Strategy Agent Research
4. Dev Agent Research
5. QA Agent Research
6. Data Agent Research
7. External Autonomous Agent Research
8. Benchmark Design Research
9. SquadOps Lessons Learned
10. Agent Improvement Program Artifacts

---

## 8. Knowledge Capture Strategy

Before improving agents, build a knowledge foundation.

This foundation should have four buckets.

## 8.1 Current SquadOps agent design knowledge
Capture what exists today:

- current role definitions
- current prompts/instructions
- tool access
- memory access
- task contracts
- coordination assumptions
- current runtime model choices
- known limitations

This becomes the baseline design pack.

## 8.2 External agent system research
Capture lessons from:

- OpenHands / agentic coding systems
- Devin-like public patterns
- public Anthropic / OpenAI / Google guidance
- open-source autonomous agents
- tool-using agent frameworks
- research papers on agent evaluation and autonomy
- public examples of long-duration software agents

### Important note
This program should avoid relying on unauthorized or questionable leaked material as a foundational source. Public, open, and clearly usable material is a stronger and safer base.

## 8.3 Internal SquadOps evidence
Capture what SquadOps itself is already teaching:

- successful cycles
- failed cycles
- RCA findings
- benchmark failures
- where agents drift
- where prompts collapse
- where memory helps
- where model swaps help
- where coordination masks individual weakness

This is one of the most valuable data sources because it is directly relevant to the real runtime.

## 8.4 Improvement proposals
Capture candidate upgrades such as:

- revised role prompts
- role splits or merges
- model-routing changes
- memory-structure improvements
- tool-access changes
- planning-pattern changes
- evaluation-pattern changes
- recovery-behavior changes

---

## 9. Role Intelligence Model

The program should define intelligence by role rather than as a generic property.

## 9.1 Lead / Max intelligence
Key qualities:

- decomposition quality
- assignment quality
- sequencing judgment
- escalation quality
- RCA and rewind quality
- stop/go judgment
- ability to preserve momentum without creating chaos

### Sample benchmark categories
- task decomposition
- ambiguous multi-step planning
- conflict resolution between agent outputs
- failure triage
- recovery sequencing
- escalation path selection

## 9.2 Strategy / Nat intelligence
Key qualities:

- PRD interpretation
- ambiguity detection
- scope control
- tradeoff clarity
- story and capability decomposition
- design intent preservation

### Sample benchmark categories
- PRD reading
- scope extraction
- ambiguity surfacing
- user story generation
- option analysis
- architecture implication analysis

## 9.3 Dev / Neo intelligence
Key qualities:

- implementation planning
- code correctness
- architectural adherence
- patch quality
- debugging ability
- recovery after failed attempt
- consistency with repo conventions

### Sample benchmark categories
- code patching
- implementation design
- refactoring
- bug fixing
- test-driven adjustments
- partial failure recovery

## 9.4 QA / Eve intelligence
Key qualities:

- failure detection
- signal-to-noise quality
- edge-case rigor
- test coverage quality
- validation depth
- ability to catch semantic breakage

### Sample benchmark categories
- test design
- failure case discovery
- regression detection
- edge-case identification
- bug report quality
- artifact validation

## 9.5 Data intelligence
Key qualities:

- experiment interpretation
- telemetry reading
- anomaly detection
- metric design
- evidence summarization
- recommendation quality

### Sample benchmark categories
- metric selection
- anomaly interpretation
- experiment result summary
- false positive discrimination
- RCA support
- recommendation clarity

---

## 10. The Agent Intelligence Baseline Pack

Before any major improvement work, create an **Agent Intelligence Baseline Pack** for each primary agent.

Each pack should include:

### 10.1 Identity and role
- agent name
- role
- responsibilities
- key interfaces with other agents

### 10.2 Current design
- prompt / instruction set
- model(s) used
- tool access
- memory access
- runtime assumptions
- escalation assumptions

### 10.3 Observed current behavior
- strengths
- weaknesses
- common failure modes
- known blind spots
- known latency/cost issues

### 10.4 Evidence
- examples from successful cycles
- examples from failed cycles
- benchmark observations if any already exist
- notable RCA findings

### 10.5 Candidate improvement hypotheses
- prompt improvements
- memory improvements
- model-routing changes
- tool additions
- role split possibilities
- role contract refinements

This baseline pack becomes the foundation for every later experiment.

---

## 11. Benchmark Strategy

## 11.1 Why benchmarks are necessary
Without benchmarks, “smarter” becomes subjective.
That leads to prompt drift, excitement bias, and false confidence.

Benchmarks provide:
- a before/after baseline
- a repeatable test harness
- evidence for promotion
- a way to compare model-role combinations
- a way to compare design changes over time

## 11.2 Benchmark design approach
Each role should have a benchmark pack with:

- 5 core tasks
- 5 edge-case tasks
- 5 failure-recovery tasks
- optional stretch tasks

This yields a realistic benchmark suite rather than a toy test.

## 11.3 Benchmark sources
Benchmark tasks can come from:

- actual SquadOps failures
- known good historical work products
- synthetic role challenges
- public benchmark inspiration adapted to role reality
- hand-crafted scenarios based on your architecture

## 11.4 What benchmark outputs should measure
Possible metrics:

- correctness
- completeness
- ambiguity detection
- recovery quality
- adherence to architecture
- evidence quality
- speed/latency
- token/cost profile
- repeatability / consistency

## 11.5 Promotion criteria
An upgrade should only be promoted if it improves at least one of:
- benchmark performance
- real-cycle usefulness
- failure recovery
- signal-to-noise ratio
- autonomy durability

without unacceptable regression in:
- cost
- latency
- control
- architecture alignment

---

## 12. Experiment Tracks

To avoid blob-ifying the effort, start with three experiment tracks only.

## 12.1 Track A — Role benchmark creation
Create benchmark packs for each target role.
This is the most important first move.

### Outputs
- role benchmark spec
- benchmark task library
- scoring rubrics
- benchmark execution harness plan

## 12.2 Track B — Model-role matching
Test whether different base models are better for different roles.

### Hypothesis
Different reasoning styles and model strengths may fit different roles better than a one-model-for-all strategy.

### Outputs
- model-role comparison matrix
- candidate default routing by role
- cost/latency tradeoff notes

## 12.3 Track C — Context and memory design
Test whether better role context improves performance more than model changes alone.

### Hypothesis
Structured role context, memory, and artifact retrieval may deliver larger gains than blindly switching models.

### Outputs
- role context pack design
- memory structure proposals
- retrieval strategy options
- before/after benchmark results

---

## 13. Improvement Loop

The core improvement loop should be:

### Step 1 — Document current role design
Capture the actual current state, not the aspirational state.

### Step 2 — Benchmark current performance
Establish a real baseline.

### Step 3 — Choose one upgrade hypothesis
Examples:
- change prompt contract
- change tool access
- change memory structure
- change model
- add self-critique pass
- split role in two

### Step 4 — Run controlled evaluation
Test the specific hypothesis against the benchmark pack and, where possible, selected real cycle tasks.

### Step 5 — Review cost / latency / control tradeoffs
A better answer that destroys cost or latency may not be a real promotion candidate.

### Step 6 — Promote or reject
Only promote if the evidence is strong enough.

### Step 7 — Capture lessons learned
Every experiment should produce a structured artifact, not just a vague memory.

---

## 14. Suggested Phases

## Phase 1 — Program foundation
Create:
- program charter
- role list
- baseline pack template
- benchmark template
- research corpus structure
- NotebookLM workspace structure

## Phase 2 — Baseline capture
For each primary agent:
- document current design
- capture known strengths/weaknesses
- gather examples from real cycles
- define preliminary benchmark hypotheses

## Phase 3 — Research corpus build
Assemble:
- public docs
- open-source agent references
- benchmarking literature
- design comparisons
- SquadOps internal lessons learned

## Phase 4 — Role benchmark suite
Create benchmark packs for:
- Max
- Nat
- Neo
- Eve
- Data

## Phase 5 — Comparative evaluation
Compare:
- ChatGPT-based role support
- Claude-based role support
- Gemini-based role support
- local/runtime alternatives where relevant

## Phase 6 — Targeted upgrades
Implement one or two role upgrades at a time, not all at once.

## Phase 7 — Promotion policy
Define what makes an agent design canonical.

---

## 15. Recommended Artifact Set

This initiative should produce a set of stable artifacts.

### Core artifacts
- Agent Intelligence Program Charter
- Agent Intelligence Baseline Template
- Role Benchmark Template
- Research Corpus Map
- Experiment Report Template
- Promotion Criteria Spec

### Role artifacts
- Max Baseline Pack
- Nat Baseline Pack
- Neo Baseline Pack
- Eve Baseline Pack
- Data Baseline Pack

### Evaluation artifacts
- Model-Role Comparison Matrix
- Role Benchmark Results
- Improvement Hypothesis Log
- Promotion / Rejection Decisions

---

## 16. Suggested Canonical Repo / Knowledge Layout

```text
docs/
  ideas/
    IDEA-agent-intelligence-improvement-program.md
  agents/
    baseline/
      max-baseline-pack.md
      nat-baseline-pack.md
      neo-baseline-pack.md
      eve-baseline-pack.md
      data-baseline-pack.md
    benchmarks/
      max-benchmark-pack.md
      nat-benchmark-pack.md
      neo-benchmark-pack.md
      eve-benchmark-pack.md
      data-benchmark-pack.md
    experiments/
      EXP-role-model-comparison-001.md
      EXP-role-context-design-001.md
      EXP-neo-memory-upgrade-001.md
    evaluations/
      role-model-comparison-matrix.md
      promotion-decisions.md
  research/
    corpus-map.md
    external-agent-patterns.md
    notebooklm-source-map.md
```

This keeps the canonical outputs in markdown and in-repo, while NotebookLM remains the synthesis layer.

---

## 17. Use of Real SquadOps Evidence

One of the strongest advantages you have is that SquadOps is already producing runtime evidence.

This initiative should explicitly mine:

- failed cycle reports
- RCA outputs
- successful autonomous runs
- prompt breakdowns
- tool-use confusion patterns
- model mismatch cases
- latency/cost pain points
- recovery success/failure examples

That evidence is better than generic external benchmark material because it directly reflects your real operating environment.

A useful principle:

> External research should shape hypotheses.  
> Internal runtime evidence should shape priorities.

---

## 18. What to Avoid

### 18.1 Avoid one giant “agent intelligence” blob
Keep separate tracks for:
- role design
- benchmark design
- orchestration design
- runtime implementation
- research knowledge management

### 18.2 Avoid assuming frontier model quality equals role fitness
A stronger generic model may still be the wrong fit for a particular role.

### 18.3 Avoid overfitting to benchmark theater
Benchmarks matter, but real-cycle utility matters too.

### 18.4 Avoid making NotebookLM the canonical truth
Use it as a research workspace, not as the lasting system of record.

### 18.5 Avoid promoting improvements without hard evidence
Interesting is not the same thing as better.

---

## 19. Recommended First 30 Days

### Week 1
- finalize program charter
- define target agent list
- create baseline pack template
- create benchmark pack template
- create NotebookLM workspace map

### Week 2
- complete Max, Nat, Neo baseline packs
- start research corpus build
- identify 10–15 benchmark tasks for each of those roles

### Week 3
- complete Eve and Data baseline packs
- finalize role benchmark packs
- define scoring rubrics
- run first baseline benchmark pass

### Week 4
- run first model-role comparison
- identify top 1–2 upgrade hypotheses per role
- choose one pilot upgrade role
- produce first experiment report

---

## 20. Recommended Pilot

The cleanest pilot is probably:

### Pilot option A — Max
Why:
- highest leverage on overall squad behavior
- strong link between individual judgment and squad autonomy
- clearer connection to long-run autonomous operation

### Pilot option B — Neo
Why:
- easier to benchmark concretely
- strong impact on real deliverables
- easier to compare across models

### Pilot recommendation
Start with **Max and Neo**:
- Max as the high-leverage coordination intelligence pilot
- Neo as the concrete implementation intelligence pilot

That gives you one strategic role and one execution role.

---

## 21. Exit Criteria for Phase 1

Phase 1 should be considered complete only when all of the following exist:

- a written program charter
- a defined role inventory
- a baseline pack template
- a benchmark pack template
- a canonical research corpus map
- NotebookLM notebook structure
- at least 2 completed role baseline packs
- at least 1 completed role benchmark pack
- at least 1 comparative model evaluation plan

---

## 22. Recommended Next Artifacts

The next documents to create after this one should be:

1. **Agent Intelligence Baseline Template**
2. **Role Benchmark Pack Template**
3. **Model-Role Comparison Matrix Template**
4. **Research Corpus Map**
5. **Max Baseline Pack**
6. **Neo Baseline Pack**

---

## 23. Final Framing

The strongest way to describe this initiative is:

> SquadOps is not only trying to coordinate agents better.  
> It is building a durable system for continuously improving the intelligence of the individual agents that make up the squad.

And the strongest strategic framing is:

> Use ChatGPT, Claude, and Gemini as external research, critique, evaluation, and implementation partners — while keeping SquadOps itself as the long-term operating substrate and the owner of its own intelligence improvement system.

That framing keeps the value compounding inside your system instead of inside theirs.

---

## 24. Benchmark Execution Strategy

The benchmark design (Section 11) defines what to measure. This section defines how benchmarks actually run.

The recommended approach layers four execution methods, each suited to different roles and evaluation needs.

### 24.1 Option A — pytest-based Benchmark Harness

Run benchmarks as a dedicated pytest suite under `tests/benchmarks/`.

Each benchmark task is a test case that sends a prompt and context to a handler and scores the output. Fixtures provide the role context, capability config, and mock or real LLM backend. Scoring functions assert on structured output properties such as correctness, completeness, and adherence. Results are captured via pytest markers and a custom plugin that writes JSON reports.

**Strengths:**
- Fits existing test infrastructure (3000+ tests already run this way)
- Repeatable, CI-friendly, version-controlled alongside the code
- Can run against mock LLM responses (deterministic) or real LLM calls (realistic)
- Developers already know how to run it

**Limitations:**
- Scoring LLM output with assertions is brittle — string checks or regex can miss valid alternatives
- Does not exercise the full agent runtime (message routing, memory, tool use)
- Fast but potentially shallow

**Best for:** Handler-level intelligence testing. Example: does Neo's dev handler produce correct code given a specific input?

### 24.2 Option B — Cycle-based Benchmark Runs

Use the actual cycle execution pipeline with dedicated benchmark cycle request profiles.

Create profiles like `benchmark-neo-impl.yaml` and `benchmark-max-decomposition.yaml`. Each profile defines a known task with known inputs (a synthetic PRD, a known bug, a planning scenario). Run via `squadops cycles create benchmark-project --request-profile benchmark-neo-impl`. Score the output artifacts against a rubric. LangFuse traces provide token counts, latency, and full prompt/response history. The event bus (SIP-0077) captures per-agent runtime data automatically.

**Strengths:**
- Exercises the real runtime — agents, message routing, memory, tool access, the full stack
- Produces real artifacts that can be inspected and compared across runs
- Event bus and LangFuse already capture everything needed for analysis
- Closest to how the agent actually performs in production

**Limitations:**
- Slow — a full cycle takes minutes, not seconds
- Requires Docker services running (Postgres, RabbitMQ, Prefect, agents)
- Non-deterministic — LLM responses vary between runs
- Harder to isolate agent intelligence changes from orchestration changes

**Best for:** End-to-end role performance validation, model-role comparison (Track B), autonomy durability testing.

### 24.3 Option C — LLM-as-Judge Evaluation

Use a separate LLM to score agent outputs against a structured rubric.

Capture agent outputs from Option A or Option B. Feed each output plus the original task plus a scoring rubric to a judge model. The judge returns structured scores (e.g., correctness: 4/5, completeness: 3/5, architecture adherence: 5/5). Aggregate scores across the benchmark pack.

**Strengths:**
- Can evaluate semantic quality that string assertions cannot (was this a good decomposition?)
- Scales — can score hundreds of outputs without manual review
- Rubrics are version-controlled and improvable

**Limitations:**
- Judge model introduces its own biases and failure modes
- Need to validate the judge itself (does it actually discriminate good from bad?)
- Cost multiplier — every benchmark run also costs judge tokens
- Risk of benchmark theater if the judge is too lenient

**Best for:** Scoring subjective qualities like Max's decomposition judgment or Nat's ambiguity detection.

### 24.4 Option D — Golden Output Comparison

Maintain a set of known-good outputs and diff against them.

For each benchmark task, store a reference golden output that has been human-reviewed and approved. Run the agent, diff the output against golden. Score based on structural similarity, key content presence, and absence of known failure patterns. Similar to snapshot testing.

**Strengths:**
- Simple, deterministic scoring — no LLM judge needed
- Easy to see exactly what changed between agent versions
- Good regression detection

**Limitations:**
- Rigid — any valid-but-different output looks like a failure
- Maintenance burden — golden outputs need updating as the system evolves
- Does not work well for roles with legitimately variable output (Max's planning)

**Best for:** Neo's code output (did it produce correct, runnable code?), Eve's test output (did it find the known bugs?).

### 24.5 Recommended Layering Strategy

Layer the four options rather than choosing one. Roll them out in this order:

**Layer 1 — pytest + golden outputs (Options A and D) for Neo and Eve.**
Their outputs are concrete and scorable. This gets benchmarks running fast with zero new infrastructure.

**Layer 2 — Cycle-based benchmark profiles (Option B) for Max.**
Decomposition and coordination judgment need the full runtime to be meaningful. The cycle request profile infrastructure from SIP-0083 already supports this.

**Layer 3 — LLM-as-judge (Option C) for Nat and Max.**
Add once there are enough outputs to validate the judge against human scoring. Use for roles where output quality is subjective.

### 24.6 Benchmark Result Storage

Benchmark results should land in `docs/agents/benchmarks/results/` as timestamped JSON reports. Each report should reference:

- git SHA of the codebase at time of run
- model and model version used
- cycle request profile version (for Option B runs)
- role and benchmark pack version
- raw scores and aggregate scores
- LangFuse trace IDs (for Option B runs)

This keeps results version-controlled and diffable without requiring new infrastructure.

### 24.7 Concrete Benchmark Pack Example — Neo (Dev Agent)

To make the benchmark strategy tangible, here is a sketch of what Neo's benchmark pack would look like.

#### Core tasks (5)
1. Implement a single-file Python function from a clear spec
2. Add a new API route to an existing FastAPI service
3. Refactor a function to reduce cyclomatic complexity
4. Fix a failing test by correcting the implementation (not the test)
5. Add error handling to an existing function that currently swallows exceptions

#### Edge-case tasks (5)
1. Implement when the spec contains contradictory requirements (should surface ambiguity)
2. Implement when the target file has an unusual structure (non-standard patterns)
3. Fix a bug where the root cause is in a different file than the symptom
4. Implement a feature that requires modifying frozen dataclasses correctly (using `dataclasses.replace()`)
5. Handle a spec that requests a change violating an existing architectural constraint

#### Failure-recovery tasks (5)
1. Resume after a previous attempt produced syntactically invalid code
2. Resume after a previous attempt broke existing tests
3. Recover from a partial implementation (half the files written, then interrupted)
4. Respond to QA feedback that rejects the first implementation
5. Implement correctly after receiving a correction decision from the lead agent

#### Scoring rubric (per task)
- **Correctness** (0-5): Does the code work? Does it pass the expected tests?
- **Completeness** (0-5): Are all requirements addressed? Any missing pieces?
- **Architecture adherence** (0-5): Does it follow repo conventions, hexagonal patterns, existing code style?
- **Recovery quality** (0-5, failure-recovery tasks only): Did the agent correctly identify the failure and produce a meaningfully different second attempt?
- **Token efficiency** (measured): Total tokens consumed for the task

---

## 25. Review Recommendations

The following recommendations were identified during initial review and should be addressed before this idea is promoted to a SIP.

### 25.1 Trim the Big 3 and NotebookLM sections

Sections 6 and 7 describe personal operational workflow rather than program architecture. The program principles (Section 5) already establish that external models are accelerants, not substrate. The Big 3 Operating Model and NotebookLM sections should be moved to an operational playbook appendix so they do not appear to contradict that principle by giving specific external tools first-class architectural standing.

### 25.2 Connect to existing telemetry infrastructure

The program should explicitly state that SIP-0077 cycle events and SIP-0061 LangFuse traces are the primary data sources for internal evidence (Section 8.3). The event bus already captures per-agent runtime data. LangFuse already captures token counts, latency, and full prompt/response chains. Mining these existing sources is cheaper and more reliable than manual cycle log review.

### 25.3 Elevate cost as a first-class success criterion

Section 4 (success criteria) does not mention cost. Section 11.4 lists token/cost profile as a possible metric but treats it as optional. For 8-10 hour autonomous runs, cost is load-bearing. An agent that is 10% smarter but 3x more expensive may not be a real improvement. Cost should appear in the success criteria alongside benchmark scores and cycle outcomes.

### 25.4 Add cross-role regression protection

When an upgrade is promoted for one role (e.g., Neo), there is no described mechanism to ensure other roles do not regress. Agent interactions mean a change to Neo's output quality can affect Eve's QA work and Max's coordination decisions. The promotion criteria (Section 11.5) should include a cross-role smoke test — at minimum, a multi-agent benchmark cycle that exercises the full squad after any single-role promotion.

### 25.5 Cap the research corpus scope

Section 8.2 (external research) defines what to collect but not when to stop. Research corpus builds expand indefinitely without a cap. Define a concrete scope limit — e.g., 10 source documents per role, reviewed and tagged — so research serves benchmarking rather than becoming its own workstream.

### 25.6 Narrow the 30-day timeline to pilot scope

The 30-day plan (Section 19) attempts baseline packs for all 5 roles, full benchmark suites, and a first model-role comparison. Given that SquadOps is still actively building coordination infrastructure (SIP-0079, SIP-0083), running a parallel agent intelligence program at this pace risks splitting focus. Scope Phase 1 to Max and Neo only (which Section 20 already recommends as pilots) and explicitly defer Eve, Nat, and Data baseline packs until the two pilots produce results.

---

## 26. Open Questions

1. Which roles should be in scope for the first wave beyond Max and Neo?
2. Should benchmark packs be fully deterministic or partially scenario-based?
3. How should real-cycle evidence be normalized so it can feed benchmarks?
4. How much of the evaluation harness should live inside SquadOps itself?
5. When should a role split into sub-roles instead of being “improved” as one agent?
6. Which improvements should be considered local-runtime compatible vs cloud-model dependent?
7. How should cost discipline be incorporated into promotion criteria?
8. What is the minimum number of benchmark runs needed to account for LLM non-determinism?
9. How should the LLM-as-judge be validated before trusting its scores?
10. Should benchmark results trigger automated alerts or remain a manual review process?

---

## 27. Recommendation

Proceed with this as a dedicated initiative, not as an informal side thread.

Treat the next concrete milestone as:

**Build the Agent Intelligence Baseline System.**

That means:
- define the templates
- build the baseline packs
- build the benchmark packs
- establish the first comparison loop
- only then start promoting intelligence upgrades into SquadOps
