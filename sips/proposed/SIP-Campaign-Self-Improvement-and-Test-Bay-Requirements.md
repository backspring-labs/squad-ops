---
title: Campaign-Driven Self-Improvement and Test Bay
status: proposed
author: jladd
created_at: '2026-07-02T00:00:00Z'
---
# SIP: Campaign-Driven Self-Improvement and Test Bay

Status: Proposed (vision anchor — see `docs/plans/2-0-roadmap-reconciliation.md` for the intended split before acceptance)  
Target Roadmap: SquadOps 2.0.0 direction, with an implementable **Campaign-orchestration** core carved out to **1.6**  
Author: jladd  
Reviewers: TBD  
Created: 2026-07-02  
Supersedes: Earlier informal Cycle Loop / Loop Policy concepts (this SIP is the successor to the "Loop Policy" naming in `docs/ideas/SquadOps-Roadmap-Runtime-Loop-Capability-Backed-Agents.md`)  
Related Concepts: Campaign, Cycle, Run, Duty, Capability Pack, Capability Asset, Capability Binding Contract, Continuum, Agent Runtime Modes, Test Bay, Capability Promotion

---

## 1. Executive Summary

This SIP proposes a strategic expansion of SquadOps from a system that executes bounded agent work into a system that can deliberately improve its own operating capability over time through governed, measurable, campaign-driven improvement.

The core proposal is to introduce three mutually reinforcing concepts:

1. Campaigns: long-running objective envelopes that coordinate one or more bounded Cycles toward a measurable outcome.
2. Self-Improvement Campaigns: a specialized class of Campaign focused on improving agent capability, framework reliability, benchmark quality, tool support, observability, safety, and operational effectiveness.
3. Test Bay: a GitHub-backed proving ground where agents build, repair, benchmark, compare, and qualify sample applications, capability assets, and framework improvements using durable source history and externally archived run evidence.

This SIP intentionally separates self-improvement from uncontrolled self-modification. The proposed model allows agents to research, propose, implement on isolated branches, test in constrained environments, produce evidence, and submit promotion recommendations. It does not grant agents unrestricted authority to mutate the live SquadOps runtime or deploy changes without gates.

The long-term goal is to make SquadOps compounding: every overnight run should be able to leave the system measurably better than it was before, or at minimum leave behind better evidence about why it did not improve.

The operating principle is:

Campaigns carry objectives. Cycles coordinate bounded collaboration. Runs execute. Test Bay proves. Artifact storage preserves evidence. Capability Promotion governs adoption. Continuum presents operator decisions.

---

## 2. Problem Statement

SquadOps currently has strong primitives for bounded coordination, agent execution, and emerging runtime modes, but the system needs a higher-level mechanism to pursue long-running improvement goals across multiple Cycles.

The existing Cycle abstraction is intentionally bounded. A Cycle is well-suited for a focused effort: build a feature, review a design, research a question, repair a failing app, run a benchmark, or coordinate a squad around a defined deliverable. It is not the right abstraction for an extended objective that may require multiple different Cycles, different squad profiles, different run types, accumulated evidence, and continuation decisions over time.

The earlier Cycle Loop concept attempted to address this need by allowing work to continue across repeated cycles. However, the word Loop risks overloading Cycle semantics and blending execution mechanics with objective-level orchestration. The better abstraction is Campaign.

Separately, the current sample application and spike workflow relies too heavily on ad hoc filesystem workspaces and temporary generation patterns. This creates several problems:

- Loss of durable source history.
- Weak comparability across runs.
- Poor replayability.
- Difficulty proving before-and-after improvement.
- Risk of exhausting local disk on the Spark.
- Difficulty applying normal development practices such as branching, review, test baselines, and promotion.
- Increased likelihood that agent-built apps diverge from how real apps are cloned, built, tested, versioned, and promoted.

Finally, the system lacks a formal improvement substrate. It is possible to run agents nightly, but without clear objectives, scorecards, benchmark baselines, source-controlled test targets, artifact retention, and promotion gates, nightly activity can become noise rather than compounding improvement.

This SIP addresses those gaps.

---

## 3. Goals

### 3.1 Strategic Goals

The strategic goals of this SIP are:

- Establish Campaign as the objective-level orchestration primitive for multi-Cycle work.
- Establish Self-Improvement Campaigns as a first-class operating mode for improving SquadOps over time.
- Establish Test Bay as the durable proving ground for agent-built applications, benchmark fixtures, capability-pack trials, and framework improvement work.
- Replace ad hoc temporary application generation with source-controlled app definitions and disposable execution workspaces.
- Enable nightly improvement runs that generate reviewable, comparable, evidence-backed improvement proposals.
- Create the foundation for SquadOps 2.0.0 as a system that can improve its own capability inventory, benchmark base, operational reliability, and framework quality.

### 3.2 Product Goals

The product goals are:

- Allow an operator to start or schedule a nightly improvement Campaign.
- Allow the Campaign to select or receive a measurable improvement objective.
- Allow the Campaign to run multiple Cycles with different squad profiles if needed.
- Allow each Cycle to produce evidence, decisions, and next-step recommendations.
- Allow the Campaign to accumulate evidence across Cycles.
- Allow Continuum to present an actionable morning review summary.
- Allow the operator to decide whether to reject, continue, promote, open a review item, or schedule follow-up work.

### 3.3 Engineering Goals

The engineering goals are:

- Introduce a durable Campaign model that references Cycles, Runs, squad profiles, objectives, policies, and evidence.
- Introduce Test Bay integration as a source-controlled execution substrate.
- Introduce artifact retention that separates source history from heavy run evidence.
- Introduce capability promotion records for moving candidate improvements through review stages.
- Introduce scorecards and benchmark-driven evaluation for improvement claims.
- Introduce lifecycle management for disposable workspaces and retained artifacts.
- Provide replayability through references to source revision, environment metadata, agent profile, capability pack versions, model mix, and benchmark set.

### 3.4 Governance Goals

The governance goals are:

- Prevent uncontrolled self-modification of the live SquadOps runtime.
- Ensure third-party skills and capability assets are treated as untrusted until reviewed and qualified.
- Ensure generated improvements produce evidence before promotion.
- Ensure capability changes can be rolled back or disabled.
- Ensure framework changes follow review and promotion lanes.
- Ensure the operator remains in control of live runtime promotion until sufficient maturity is proven.

---

## 4. Non-Goals

This SIP does not propose:

- Replacing Cycle with Campaign.
- Making Duty a synonym for Campaign.
- Allowing agents to directly modify and redeploy their live runtime without review.
- Turning all agent activity into Campaigns.
- Storing all run artifacts in Git.
- Treating external Claude Skills or other third-party capability assets as safe by default.
- Building a general-purpose public marketplace for skills or capability packs in the first version.
- Fully autonomous production deployment.
- Removing human promotion authority from the initial implementation.
- Replacing existing CI, repository management, or release workflows.

---

## 5. Key Definitions

### 5.1 Campaign

A Campaign is a long-running objective container that coordinates a sequence of bounded Cycles toward a measurable outcome. A Campaign preserves objective context, accumulated evidence, policy decisions, squad-profile choices, benchmark results, and final disposition.

A Campaign may run one Cycle or many Cycles. It may use the same squad profile throughout or adapt the squad profile as the objective evolves.

### 5.2 Self-Improvement Campaign

A Self-Improvement Campaign is a Campaign whose objective is to improve SquadOps’ operating capability. The improvement target may be an agent capability, benchmark suite, skill asset, tool adapter, runtime mechanism, prompt policy, memory strategy, observability surface, cost model, documentation set, or framework code change.

### 5.3 Test Bay

Test Bay is the GitHub-backed proving ground where SquadOps agents build, repair, benchmark, compare, and qualify sample applications, capability improvements, and framework changes.

Test Bay is not merely a playground. It is a controlled evaluation environment backed by source history, reproducible app definitions, benchmark fixtures, branch-based experimentation, artifact-linked run evidence, and promotion gates.

### 5.4 Cycle

A Cycle is a bounded squad collaboration unit. It has a defined scope, squad profile, task shape, acceptance criteria, and deliverable. A Campaign may coordinate multiple Cycles.

### 5.5 Run

A Run is the actual execution record of a task, cycle, deterministic workflow, research pass, design pass, benchmark pass, or other executable unit. Runs should be traceable to source revision, environment, agent configuration, model configuration, capability-pack versions, and artifacts.

### 5.6 Squad Profile

A Squad Profile defines the agent composition, role mix, model mix, runtime mode, and collaboration pattern used for a particular Cycle or Campaign phase.

### 5.7 Capability Pack

A Capability Pack is a governed plugin-style package that enhances one or more agents. It may include skill assets, prompts, tool bindings, MCP integrations, deterministic workflows, reference materials, tests, binding requirements, and promotion metadata.

### 5.8 Capability Asset

A Capability Asset is an individual reusable component inside a Capability Pack. Examples include a Claude Skill, prompt recipe, tool adapter, workflow template, benchmark fixture, checklist, domain reference, or task pattern.

### 5.9 Capability Binding Contract

A Capability Binding Contract declares what kind of agent can safely and usefully bind to a capability. It should describe prerequisites, allowed runtime context, required tools, risk level, expected input profile, and expected output profile.

### 5.10 Capability Promotion

Capability Promotion is the governance process that moves a candidate improvement from discovered or proposed status to approved, active, deprecated, or rejected status.

### 5.11 Artifact Bundle

An Artifact Bundle is a durable collection of run evidence, such as logs, traces, reports, benchmark outputs, summaries, screenshots where relevant, and generated review material. Artifact Bundles should be stored outside Git unless they are small curated fixtures or accepted benchmark assets.

---

## 6. Conceptual Model

The proposed conceptual model is:

- Campaigns orchestrate long-running objectives.
- Cycles coordinate bounded work.
- Runs execute specific attempts.
- Squad Profiles select the right agent mix.
- Test Bay provides source-controlled proving grounds.
- Artifact storage preserves heavy evidence.
- Scorecards determine whether improvement occurred.
- Promotion records govern adoption.
- Continuum presents operator decisions.

This model preserves existing bounded execution semantics while adding objective-level continuity and evidence-based improvement.

---

## 7. Design Principles

### 7.1 Campaigns Are Objective Envelopes, Not Execution Loops

Campaigns should not be treated as raw loops. A Campaign may continue, retry, fork, pause, or complete, but those decisions should be policy-driven and evidence-driven. The top-level abstraction is objective progression, not repetition.

### 7.2 Cycles Remain Bounded

A Cycle should retain a clear scope and acceptance boundary. Long-running improvement should be handled by Campaigns that coordinate multiple bounded Cycles rather than by making a Cycle unbounded.

### 7.3 Runs Are Disposable; Evidence Is Durable

Execution workspaces should be disposable. Source history, run metadata, and artifact bundles should be durable. The Spark should not become the long-term archive for every generated workspace.

### 7.4 Git Stores Source, Artifact Storage Stores Evidence

GitHub should preserve source code, benchmark fixtures, curated examples, manifests, and reviewable changes. Heavy logs, traces, raw transcripts, build outputs, and repeated run bundles should live in artifact storage with searchable metadata elsewhere.

### 7.5 Self-Improvement Requires Measurement

No improvement should be considered real unless it is tied to a baseline, scorecard, benchmark, failure pattern, or operator-validated outcome.

### 7.6 Capability Discovery Is Not Capability Adoption

External skills, prompts, tools, and assets are untrusted until evaluated, adapted, minimized, tested, and promoted through governance.

### 7.7 Agents May Propose Their Own Improvements Before They Are Allowed to Promote Them

The initial autonomy model should allow agents to research, design, branch, test, and recommend. It should not allow agents to directly mutate live runtime behavior without review.

### 7.8 Morning Review Must Be First-Class

Nightly improvement only works if the operator can understand what happened in the morning. Continuum must provide a clear decision surface, not just raw logs.

### 7.9 Improvement Should Compound Across Multiple Dimensions

SquadOps should not only add skills. It should improve benchmarks, tools, memory, policies, runtime reliability, observability, role design, cost routing, documentation, and framework quality.

### 7.10 Safety and Supply Chain Controls Are Part of the Core Design

Because capability assets can influence agent behavior, safety review and supply chain controls are not optional add-ons. They are central to the promotion model.

---

## 8. Proposed Capability: Self-Improvement Campaigns

### 8.1 Overview

A Self-Improvement Campaign is a governed Campaign that aims to improve a measurable aspect of SquadOps operation.

It should begin with a defined improvement target and baseline. It should then coordinate one or more Cycles to inspect evidence, research options, design changes, implement or propose candidate improvements, evaluate the results, and produce a promotion recommendation.

### 8.2 Required Campaign Intent

Each Self-Improvement Campaign must declare:

- The improvement objective.
- The primary improvement target type.
- The baseline or pain point being addressed.
- The expected measurement method.
- The allowed change scope.
- The maximum autonomy level.
- The required evidence for promotion.
- The termination conditions.
- The operator decision expected at completion.

### 8.3 Improvement Target Types

Self-Improvement Campaigns should support the following target types.

#### Capability Asset

Improves what agents can do by adding or refining skills, tool recipes, deterministic workflows, checklists, prompt recipes, domain packs, or support materials.

Typical outcomes:

- Candidate skill asset.
- Refined prompt recipe.
- New tool adapter proposal.
- New workflow pattern.
- Updated capability-pack binding contract.
- Benchmark evidence showing improvement.

#### Benchmark

Improves how the system measures agent capability.

Typical outcomes:

- New benchmark tasks.
- Improved scorecard rubrics.
- Regression fixtures from real failures.
- Golden examples.
- Clearer pass/fail criteria.
- Better before-and-after comparison reports.

#### Failure Archeology

Mines failed Cycles and Runs to identify recurring failure patterns and convert them into improvement opportunities.

Typical outcomes:

- Failure taxonomy updates.
- Root cause analysis.
- New regression benchmark.
- Proposed mitigation.
- Recommended capability improvement.
- Recommended framework fix.

#### Prompt and Policy

Improves agent instructions, role prompts, Cycle prompts, escalation policies, evidence requirements, completion criteria, handoff rules, and repair-loop boundaries.

Typical outcomes:

- Prompt policy proposal.
- Revised evidence requirements.
- Improved role guidance.
- Updated completion gate.
- Benchmark comparison before promotion.

#### Agent Role

Identifies whether a new agent role is warranted based on recurring gaps that cannot be solved by skills, tools, prompts, policies, or squad-profile changes.

Typical outcomes:

- Proposed role charter.
- Binding responsibilities.
- Required capabilities.
- Non-overlap analysis with existing roles.
- Benchmark or scenario proving the role adds value.
- Recommendation to add, reject, or defer the role.

#### Squad Profile

Improves which agent mix is used for particular classes of Campaigns or Cycles.

Typical outcomes:

- Recommended profile for a task class.
- Comparison between squad profiles.
- Model mix recommendation.
- Role participation analysis.
- Evidence that a profile improves success, cost, time, or quality.

#### Tooling and Integration

Improves deterministic support around agents so that agents rely less on brittle reasoning for repeatable tasks.

Typical outcomes:

- Tool adapter proposal.
- MCP integration proposal.
- Repository inspection aid.
- Test-running wrapper.
- Validation utility.
- Dependency analysis aid.
- Artifact summarization aid.

#### Runtime Reliability

Improves the ability of SquadOps to run unattended, recover from failure, and classify blocked or degraded states.

Typical outcomes:

- Improved stuck-state detection.
- Clearer blocked-state classification.
- Better retry policy.
- Better heartbeat and pulse behavior.
- Improved queue durability.
- Improved replayability.
- Improved crash recovery evidence.

#### Observability and Evidence

Improves the operator’s ability to understand what happened and decide what to do next.

Typical outcomes:

- Better Campaign summary.
- Better Cycle trace summary.
- Better decision log.
- Better benchmark report.
- Better failure clustering.
- Better contribution summary.
- Better cost and runtime reporting.
- Improved morning review surface.

#### Cost and Model Routing

Improves the economics and quality of model selection.

Typical outcomes:

- Model routing recommendation.
- Local versus frontier model comparison.
- Cost reduction opportunity.
- Task class routing policy.
- Cache recommendation.
- Deterministic replacement recommendation.

#### Memory and Retrieval

Improves how agents retain, retrieve, summarize, and use project context.

Typical outcomes:

- Improved context pack.
- Updated memory schema proposal.
- Better retrieval policy.
- Improved project glossary.
- Architecture decision digest.
- Known failure pattern library.
- Better handoff summary.

#### Security and Safety

Improves the safety of capabilities, tools, plugins, prompts, and autonomous execution.

Typical outcomes:

- Capability risk assessment.
- Skill quarantine recommendation.
- Prompt injection review.
- Permission boundary recommendation.
- Red-team finding.
- Safety benchmark.
- Promotion blocker.

#### Documentation and Onboarding

Improves how humans and agents understand the framework, app patterns, capability packs, and benchmark expectations.

Typical outcomes:

- Improved operator documentation.
- Agent-facing guide.
- App authoring guide.
- Benchmark guide.
- Capability-pack authoring guide.
- Example walkthrough.
- Release notes.

#### Framework Code

Improves SquadOps itself through controlled branch-based development and evidence-backed review.

Typical outcomes:

- Proposed branch.
- Reviewable change set.
- Tests.
- Benchmark results.
- Risk assessment.
- Rollback notes.
- Promotion recommendation.

#### Operator UX

Improves Continuum and operator interaction flows.

Typical outcomes:

- Improved Campaign review surface.
- Better status explanation.
- Better decision prompts.
- Better roster visibility.
- Better run comparison view.
- Better promotion workflow.

---

## 9. Recommended Initial Campaign Types

### 9.1 Failure Archeology Campaign

Purpose: Convert real failures into durable system learning.

This Campaign inspects recent failed, repaired, blocked, or manually corrected Cycles. It identifies recurring failure patterns, classifies causes, and produces one or more proposed mitigations.

High-value outputs include benchmark additions, failure taxonomy updates, prompt/policy changes, tool proposals, and capability-pack candidates.

Rationale: The most valuable improvements should come from actual observed failure, not abstract brainstorming.

### 9.2 Capability Discovery Campaign

Purpose: Find or design one new capability asset that can improve an agent’s operating skill.

This Campaign may research Claude Skills, internal skill patterns, tool adapters, prompt recipes, workflows, domain references, or deterministic utilities. It should not install external assets directly into live agents. It should produce a candidate asset, risk assessment, binding contract, benchmark plan, and promotion recommendation.

Rationale: Skills and capability assets provide compounding leverage, but only if governed as part of a capability supply chain.

### 9.3 Benchmark Expansion Campaign

Purpose: Improve measurement before increasing autonomy.

This Campaign adds benchmark tasks, acceptance rubrics, replayable failure fixtures, and before-and-after comparison methods.

Rationale: Without better benchmarks, the squad cannot reliably determine whether a change made the system better.

### 9.4 Runtime Reliability Campaign

Purpose: Improve overnight execution success.

This Campaign targets stuck states, timeouts, crash recovery, queue durability, heartbeat behavior, retry policy, run cleanup, and operator evidence for failed or partial work.

Rationale: Nightly improvement depends on unattended reliability.

### 9.5 Morning Review Campaign

Purpose: Improve the operator’s morning decision experience.

This Campaign focuses on summarization, evidence packaging, decision clarity, promotion recommendations, risk surfacing, run comparison, and Continuum UX.

Rationale: The system can only safely become more autonomous if humans can quickly understand and govern what happened.

### 9.6 Agent Role Proposal Campaign

Purpose: Determine whether a new role is justified.

This Campaign should be evidence-driven. It should analyze recurring gaps and determine whether the gap is better solved through a new role, skill, prompt change, tool, benchmark, or squad-profile adjustment.

Rationale: New roles add coordination cost. They should be created only when they provide distinct operational leverage.

### 9.7 Squad Profile Optimization Campaign

Purpose: Determine which squad profile works best for a recurring class of work.

This Campaign compares agent mixes, role participation, model mix, success rate, cost, and quality for a task class.

Rationale: Campaigns may require different squad profiles across phases. The system should learn which profiles work best.

### 9.8 Cost and Model Routing Campaign

Purpose: Improve model economics and routing decisions.

This Campaign evaluates whether particular task classes can use local models, smaller cloud models, deterministic tools, cached outputs, or frontier models only when necessary.

Rationale: Sustainable autonomy requires cost discipline.

### 9.9 Framework PR Campaign

Purpose: Allow agents to propose and test improvements to SquadOps itself.

This Campaign may create isolated branches, run tests, generate review evidence, and recommend promotion. It should not directly deploy to live runtime in early maturity stages.

Rationale: This is the path toward self-improving infrastructure without uncontrolled self-modification.

### 9.10 Security Red-Team Campaign

Purpose: Stress-test skills, capability packs, prompts, tools, and proposed framework changes.

This Campaign should attempt to identify prompt injection risks, unsafe tool usage, supply chain issues, permission boundary weaknesses, and unsafe promotion recommendations.

Rationale: Agent capability growth increases attack surface.

---

## 10. Test Bay Proposal

### 10.1 Purpose

Test Bay should become the source-controlled proving ground for SquadOps sample applications, benchmark fixtures, capability-pack trials, and Campaign-driven improvement work.

It should replace ad hoc temporary app generation as the default substrate for durable sample app development and benchmark-driven improvement.

### 10.2 Why Test Bay Is Needed

The current temporary filesystem approach is useful for spikes but insufficient for long-running improvement because it loses history, limits comparability, makes cleanup difficult, encourages unrealistic app-building behavior, and risks exhausting local disk.

Test Bay provides:

- Durable source history.
- Branch isolation.
- Reproducible baselines.
- Comparable diffs.
- Reviewable changes.
- Benchmark fixtures.
- Curated sample apps.
- Promotion-ready evidence.
- Realistic development flow.
- Reduced dependence on local disk retention.

### 10.3 Test Bay Scope

Test Bay should hold source-controlled materials that are useful for proving, comparing, and promoting agent improvements.

In scope:

- Sample application source.
- Benchmark fixtures.
- App definitions and build expectations.
- Test suites.
- Curated failure cases.
- Golden expected outcomes.
- Campaign templates in requirements form.
- Capability-pack evaluation materials.
- Operator-facing documentation.
- Agent-facing guidance.
- Reviewable proposals and branches.

Out of scope for direct Git storage:

- Large raw run logs.
- Full trace archives.
- Repeated generated output bundles.
- Dependency caches.
- Build artifacts.
- Every transcript from every agent run.
- Temporary workspace copies.
- Large binaries unless explicitly curated as fixtures.

### 10.4 Test Bay Naming

The recommended name is SquadOps Test Bay.

The name is intentionally stronger than Playground. Playground implies open-ended experimentation. Test Bay implies controlled experimentation, proving, qualification, and promotion readiness.

### 10.5 Test Bay as a Product Concept

Test Bay should become a visible concept in Continuum and Campaign review surfaces.

Potential operator language:

- Open target in Test Bay.
- Compare Test Bay runs.
- Promote from Test Bay.
- Review Test Bay branch.
- Re-run Test Bay benchmark.
- Archive Test Bay evidence.
- Continue Campaign in Test Bay.

### 10.6 Source Control Principle

Agents should not build durable sample apps in temporary directories. They should build from source-controlled app definitions using disposable workspaces and persist reviewable changes through branches, commits, review records, and artifact-linked evidence.

### 10.7 Artifact Retention Principle

Test Bay should not become the archive for every heavy run artifact. Heavy evidence should be stored in an artifact store and linked to Campaign, Cycle, Run, and source revision metadata.

### 10.8 Disk Management Principle

The Spark should be treated as an execution node, not as a permanent artifact warehouse. It may retain active checkouts, caches, and short-term workspaces, but long-term history should be carried by Git, artifact storage, and metadata records.

---

## 11. Sample Improvement Objectives

This section provides examples of improvement objectives that Self-Improvement Campaigns should eventually support. These are requirements-level examples, not implementation instructions.

### 11.1 Capability Asset Objectives

- Improve a Dev agent’s ability to diagnose failing tests by evaluating and adapting one candidate capability asset.
- Improve a QA agent’s ability to identify missing acceptance evidence.
- Improve a Strategy agent’s ability to synthesize roadmap implications from SIPs and dev plans.
- Improve a Design agent’s ability to detect design-system gaps and request capability-pack updates.
- Improve an agent’s repository orientation by providing a better project navigation asset.

### 11.2 Benchmark Objectives

- Add benchmark scenarios for failing-test repair.
- Add benchmark scenarios for feature implementation with acceptance evidence.
- Add benchmark scenarios for reviewing SIPs without drifting into tech-spec details.
- Add benchmark scenarios for avoiding premature role or agent assumptions.
- Add benchmark scenarios for capability-pack evaluation.

### 11.3 Failure Archeology Objectives

- Review recent failed Cycles and identify the most common root cause.
- Convert one recurring failure into a regression benchmark.
- Identify whether a failure was caused by missing context, weak tooling, bad prompt policy, unclear acceptance, or runtime instability.
- Recommend a mitigation that can be tested in a future Campaign.

### 11.4 Prompt and Policy Objectives

- Improve Cycle completion criteria so agents cannot mark work done without sufficient evidence.
- Improve escalation policy when a Cycle becomes blocked.
- Improve handoff policy between research and development Cycles.
- Improve role prompts to reduce overreach and premature implementation details.
- Improve repair-loop boundaries so the system stops before thrashing.

### 11.5 Agent Role Objectives

- Determine whether a Capability Curator role is warranted.
- Determine whether a Benchmark Designer role is warranted.
- Determine whether a Release Steward role is warranted.
- Determine whether a Red Team agent should participate in capability promotion.
- Determine whether a Memory Librarian role is justified by retrieval failures.

### 11.6 Squad Profile Objectives

- Compare a research-heavy squad profile against a balanced build-review profile.
- Determine the best default profile for capability discovery work.
- Determine the best default profile for framework PR work.
- Determine whether a Release Steward improves promotion quality.
- Determine whether a Red Team participant reduces unsafe promotion recommendations.

### 11.7 Tooling Objectives

- Identify one deterministic tool that would reduce agent uncertainty during repository repair.
- Improve validation of capability-pack metadata and binding requirements.
- Improve benchmark execution reliability.
- Improve source-to-run traceability.
- Improve artifact summarization.

### 11.8 Runtime Reliability Objectives

- Reduce failed overnight runs caused by stuck states.
- Improve blocked-state classification.
- Improve replayability of failed Runs.
- Improve cleanup of disposable workspaces.
- Improve timeout evidence and retry behavior.

### 11.9 Observability Objectives

- Improve morning Campaign summary quality.
- Improve before-and-after benchmark comparison.
- Improve agent contribution summaries.
- Improve risk surfacing in promotion recommendations.
- Improve decision log clarity.

### 11.10 Cost and Routing Objectives

- Identify task classes that can move from frontier models to local models.
- Identify task classes that should become deterministic workflows.
- Reduce unnecessary repeated context retrieval.
- Improve model selection by role and task class.
- Improve cost reporting per Campaign.

### 11.11 Memory and Retrieval Objectives

- Improve context packs for framework work.
- Improve retrieval of architecture decisions.
- Improve summarization of previous Campaign outcomes.
- Improve retention of known failure patterns.
- Improve agent handoff context between Cycles.

### 11.12 Security and Safety Objectives

- Evaluate candidate skills for unsafe instructions.
- Evaluate capability packs for overly broad tool access.
- Detect prompt-injection risks in skill metadata or instructions.
- Validate permission boundaries for candidate assets.
- Recommend quarantine, rejection, or constrained promotion.

### 11.13 Documentation Objectives

- Improve documentation for authoring Test Bay apps.
- Improve documentation for writing benchmark scenarios.
- Improve documentation for capability-pack promotion.
- Improve agent-facing guidance for Campaign participation.
- Improve operator-facing review instructions.

### 11.14 Framework Code Objectives

- Propose a Campaign metadata improvement.
- Propose a Run artifact linking improvement.
- Propose a benchmark replay improvement.
- Propose a Continuum Campaign review improvement.
- Propose a capability-pack validation improvement.

### 11.15 Operator UX Objectives

- Improve the Campaign review screen.
- Improve promotion decision clarity.
- Improve display of active, paused, blocked, and completed Campaigns.
- Improve visibility into Test Bay branches and evidence.
- Improve the morning review workflow.

---

## 12. Candidate New Agent Roles

New agent roles should not be introduced casually. A role should be justified only when there is recurring evidence that existing roles, prompts, tools, and squad profiles cannot cover the responsibility cleanly.

### 12.1 Capability Curator

Purpose: Finds, evaluates, normalizes, and proposes capability assets.

Responsibilities:

- Research candidate skills and capability assets.
- Evaluate fit against agent binding requirements.
- Produce risk and license notes.
- Recommend adaptation or rejection.
- Maintain capability inventory quality.

Justification: This role directly supports the capability supply chain and prevents ad hoc skill adoption.

### 12.2 Benchmark Designer

Purpose: Creates measurable tasks and scorecards for agent behavior.

Responsibilities:

- Convert failures into benchmark scenarios.
- Define acceptance rubrics.
- Maintain task difficulty ladders.
- Improve benchmark coverage.
- Compare before-and-after performance.

Justification: Self-improvement without benchmarks is not trustworthy.

### 12.3 Release Steward

Purpose: Reviews promotion evidence and ensures safe adoption.

Responsibilities:

- Review promotion readiness.
- Check rollback notes.
- Verify feature flag or activation strategy.
- Confirm benchmark evidence.
- Recommend promote, hold, reject, or continue.

Justification: A governed self-improvement system needs a role focused on safe promotion.

### 12.4 Red Team Agent

Purpose: Tests proposed capabilities and changes for unsafe behavior.

Responsibilities:

- Probe candidate skills and prompts.
- Identify prompt injection risks.
- Identify unsafe tool permissions.
- Stress-test assumptions.
- Recommend constraints or rejection.

Justification: Capability growth increases attack surface.

### 12.5 Failure Analyst

Purpose: Mines failed runs and turns them into actionable improvements.

Responsibilities:

- Review failed Cycles and Runs.
- Classify root causes.
- Identify recurring patterns.
- Recommend benchmarks and mitigations.
- Feed Campaign backlog.

Justification: Real failures are the best source of high-value improvement work.

### 12.6 Toolsmith

Purpose: Builds or proposes deterministic support tools and integration glue.

Responsibilities:

- Identify tasks that should not rely on model reasoning alone.
- Propose deterministic tools.
- Improve tool adapters.
- Support capability-pack integration.
- Improve repeatability of agent workflows.

Justification: Mature agent systems need deterministic tooling, not only more prompts.

### 12.7 Memory Librarian

Purpose: Improves retention, retrieval, context packaging, and summarization.

Responsibilities:

- Identify retrieval failures.
- Improve context packs.
- Maintain decision summaries.
- Improve known-failure memory.
- Improve cross-Cycle continuity.

Justification: Campaigns depend on continuity across Cycles and over time.

### 12.8 Operator UX Agent

Purpose: Improves the operator experience in Continuum.

Responsibilities:

- Review Campaign status surfaces.
- Improve morning review flows.
- Improve decision prompts.
- Improve evidence presentation.
- Improve visibility into Test Bay and promotion state.

Justification: More autonomy requires better human review surfaces.

### 12.9 Documentation and Onboarding Agent

Purpose: Keeps framework documentation, examples, recipes, and agent-facing guides current.

Responsibilities:

- Improve guides.
- Keep examples aligned with current architecture.
- Document Campaign patterns.
- Document capability-pack expectations.
- Document benchmark authoring practices.

Justification: Agents and humans both need clear durable instructions.

### 12.10 Recommended Initial Roles

The first roles to evaluate should be:

1. Capability Curator.
2. Benchmark Designer.
3. Release Steward.
4. Failure Analyst.
5. Red Team Agent.

These roles directly support governed self-improvement and reduce the risk of uncontrolled capability growth.

---

## 13. Capability Supply Chain

### 13.1 Overview

Self-Improvement Campaigns should treat new skills and capability assets as part of a supply chain.

The supply chain begins with discovery and ends only when a candidate is either rejected, quarantined, approved, activated, deprecated, or retired.

### 13.2 Discovery

Agents may discover candidate skills, prompt patterns, tools, workflows, domain references, and capability-pack ideas from approved sources.

Discovery should produce a candidate record, not an installation.

### 13.3 Quarantine

Third-party assets should be quarantined before use. Quarantine means the asset is available for inspection and evaluation but not active in live agent profiles.

### 13.4 Review

Candidate assets should be reviewed for:

- Fit to target capability.
- Clear invocation conditions.
- Safety concerns.
- License concerns.
- Tool permission requirements.
- External dependency risk.
- Prompt injection risk.
- Potential to bias agent behavior in unsafe ways.
- Benchmark relevance.

### 13.5 Adaptation

External assets should generally be adapted into internal capability-pack form rather than installed directly. Adaptation should minimize scope, clarify instructions, remove unnecessary permissions, and align with SquadOps binding contracts.

### 13.6 Evaluation

Candidate capabilities should be evaluated against benchmarks or scorecards appropriate to the target capability.

Evaluation should compare baseline and candidate behavior where feasible.

### 13.7 Promotion

Promotion should require evidence, risk assessment, rollback notes, and an operator or steward decision.

### 13.8 Activation

Activation should be explicit. A capability may be approved but inactive, active for one agent profile, active for one Campaign type, or active behind a feature flag.

### 13.9 Deprecation and Retirement

Capabilities should be removable. A capability that degrades performance, introduces risk, or becomes obsolete should be deprecated or retired.

---

## 14. Staged Autonomy Model

### 14.1 Rationale

The system should become more autonomous over time, but autonomy must be earned through evidence.

### 14.2 Level 0: Research Only

Agents may research and summarize improvement opportunities. No changes are made.

Appropriate for early capability discovery and role exploration.

### 14.3 Level 1: Proposal Only

Agents may draft proposed improvements, benchmark plans, and promotion recommendations. No source changes are committed.

Appropriate for SIP refinement, capability design, and campaign planning.

### 14.4 Level 2: Branch Only

Agents may create isolated source changes on a branch or equivalent review surface. No merge or live activation occurs.

Appropriate for Test Bay app work and early capability-pack trials.

### 14.5 Level 3: Sandbox Execution

Agents may run tests or benchmarks in constrained disposable environments with limited permissions and no production secrets.

Appropriate for validating candidate improvements.

### 14.6 Level 4: Reviewable Promotion Proposal

Agents may produce a full promotion package, including source changes, benchmark evidence, risk assessment, artifact links, and recommended decision.

Appropriate for nightly improvement work once Test Bay and artifact handling are mature.

### 14.7 Level 5: Controlled Promotion

A trusted human operator or designated release authority may approve activation behind a flag or within a constrained scope.

Appropriate after repeated evidence of safe operation.

### 14.8 Level 6: Limited Self-Promotion

Agents may promote low-risk changes within predefined policy limits after sufficient maturity. This level is explicitly out of scope for initial implementation.

### 14.9 Initial Recommendation

The initial implementation should target Levels 0 through 4. Level 5 may be introduced for tightly constrained, low-risk changes after the promotion evidence model is proven. Level 6 should be deferred.

---

## 15. Campaign Lifecycle Requirements

### 15.1 Campaign Creation

The system must allow a Self-Improvement Campaign to be created manually or by schedule.

A Campaign must include a clear objective, target type, baseline, and allowed autonomy level.

### 15.2 Campaign Planning

The Campaign should generate or accept a plan consisting of one or more Cycles. The plan should identify likely squad profiles and expected deliverables.

### 15.3 Cycle Execution

Each Cycle should operate within bounded scope and produce a deliverable. The Campaign should preserve the relationship between each Cycle and the larger objective.

### 15.4 Evidence Collection

Each Cycle and Run should produce evidence appropriate to the objective. Evidence should be summarized, stored, and linked.

### 15.5 Continuation Decision

After each Cycle, the Campaign should decide whether to continue, retry, repair, pivot, fork, pause, escalate, reject, or complete.

This decision should be based on evidence and policy, not arbitrary repetition.

### 15.6 Completion

A Campaign completes when its objective is achieved, rejected, deferred, exhausted, blocked, or escalated.

Completion should produce a final Campaign report.

### 15.7 Morning Review

Nightly Campaigns should produce a morning review summary designed for operator decision-making.

The summary should answer:

- What objective was pursued?
- What changed?
- What evidence was collected?
- Did the system improve?
- What risks were found?
- What decision is recommended?
- What should happen next?

---

## 16. Test Bay Lifecycle Requirements

### 16.1 Source Selection

A Campaign should be able to select a Test Bay target such as a sample app, benchmark fixture, capability-pack trial, or framework improvement area.

### 16.2 Disposable Workspace

Runs should execute in disposable workspaces created from source-controlled baselines.

### 16.3 Source Traceability

Every relevant Run should record the source baseline, branch or review surface, final revision if applicable, and related Campaign and Cycle identifiers.

### 16.4 Evidence Bundling

Runs should produce artifact bundles outside Git for heavy evidence.

### 16.5 Workspace Cleanup

Disposable workspaces should be cleaned up or pruned according to retention policy.

### 16.6 Comparison

Test Bay should support before-and-after comparison across runs, revisions, squad profiles, model mixes, and capability-pack versions.

### 16.7 Promotion Path

A successful Test Bay change should be promotable through a review process that includes evidence, risks, rollback notes, and activation scope.

---

## 17. Continuum Requirements

### 17.1 Campaign Visibility

Continuum should show active, scheduled, paused, blocked, completed, and failed Campaigns.

### 17.2 Campaign Detail

Continuum should show Campaign objective, target type, current Cycle, squad profile, evidence summary, continuation decisions, and final disposition.

### 17.3 Test Bay Integration

Continuum should link Campaigns and Runs to Test Bay branches, review surfaces, source revisions, benchmark targets, and artifact bundles.

### 17.4 Morning Review

Continuum should provide a morning review surface for overnight Campaigns.

The morning review should prioritize decisions over raw logs.

### 17.5 Promotion Decisions

Continuum should support operator decisions such as:

- Reject.
- Continue.
- Retry.
- Escalate.
- Open review.
- Promote behind flag.
- Approve for limited activation.
- Defer.

### 17.6 Risk Surfacing

Continuum should clearly surface safety, supply chain, regression, cost, and runtime risks associated with each promotion candidate.

---

## 18. Data and Traceability Requirements

The system should maintain traceability across:

- Campaign objective.
- Campaign target type.
- Campaign policy.
- Cycles.
- Runs.
- Squad profiles.
- Agent profiles.
- Capability-pack versions.
- Model configuration.
- Source baseline.
- Final source revision.
- Test Bay target.
- Benchmark suite.
- Artifact bundle.
- Scorecard results.
- Promotion decision.
- Operator decision.

The minimum viable traceability requirement is that a future reviewer can determine what was attempted, what source was changed, what evidence was produced, what decision was made, and why.

---

## 19. Scorecard Requirements

Self-Improvement Campaigns should use scorecards appropriate to the target type.

Common scoring dimensions include:

- Task success rate.
- First-pass acceptance rate.
- Benchmark pass rate.
- Regression impact.
- Evidence quality.
- Tool discipline.
- Cost.
- Runtime.
- Safety.
- Reproducibility.
- Operator review clarity.
- Maintainability.

Scorecards should support before-and-after comparison where feasible.

A Campaign should not claim improvement based solely on agent narrative. It must point to benchmark results, evidence, operator validation, or clearly stated qualitative rationale.

---

## 20. Acceptance Criteria

### 20.1 Campaign Acceptance Criteria

A Self-Improvement Campaign is acceptable when:

- It has a clear objective.
- It declares a target type.
- It identifies a baseline or current pain point.
- It identifies required evidence.
- It runs one or more bounded Cycles.
- It records continuation decisions.
- It produces a final recommendation.
- It is visible in Continuum.
- It links to source and artifact evidence where applicable.

### 20.2 Test Bay Acceptance Criteria

Test Bay is acceptable when:

- Durable sample app source is managed through source control.
- Runs use disposable workspaces rather than permanent temp app folders.
- Run records link to source baselines.
- Heavy run artifacts are stored outside Git.
- Benchmark and app targets are replayable.
- Campaigns can compare before-and-after results.
- Disk retention policy prevents unbounded Spark growth.

### 20.3 Capability Promotion Acceptance Criteria

Capability Promotion is acceptable when:

- Candidate capabilities are tracked separately from active capabilities.
- Third-party assets are quarantined before use.
- Promotion requires risk review.
- Promotion requires fit review.
- Promotion requires benchmark or scorecard evidence when feasible.
- Activation scope is explicit.
- Rollback or deactivation path is documented.

### 20.4 Nightly Improvement Acceptance Criteria

Nightly improvement is acceptable when:

- A scheduled Campaign can run without manual intervention.
- It produces a morning review summary.
- It does not require the operator to inspect raw logs first.
- It does not mutate live runtime without approval.
- It records what was attempted and why.
- It records whether improvement was achieved, rejected, or inconclusive.
- It cleans up disposable execution workspaces according to policy.

### 20.5 Framework Self-Improvement Acceptance Criteria

Framework self-improvement is acceptable when:

- Agents work on isolated review surfaces.
- Tests and benchmarks are run in constrained environments.
- No production secrets are exposed.
- No live runtime mutation occurs without approval.
- Proposed changes include evidence and rollback notes.
- Operator or release authority remains in control of promotion.

---

## 21. Risks and Mitigations

### 21.1 Risk: Uncontrolled Self-Modification

Risk: Agents may alter their own runtime in unsafe or unreviewed ways.

Mitigation: Use staged autonomy, isolated branches, sandbox execution, feature flags, human approval, and explicit promotion gates.

### 21.2 Risk: Capability Supply Chain Attack

Risk: Third-party skills or assets may contain malicious or manipulative instructions.

Mitigation: Quarantine assets, review metadata and instructions, constrain tool access, run safety checks, and adapt assets into internal capability-pack form before activation.

### 21.3 Risk: False Improvement Claims

Risk: Agents may claim improvement without measurable evidence.

Mitigation: Require scorecards, benchmarks, before-and-after comparisons, operator review, and explicit uncertainty when evidence is inconclusive.

### 21.4 Risk: Benchmark Overfitting

Risk: Agents may optimize for benchmark tasks without improving real performance.

Mitigation: Maintain diverse benchmarks, include real failure-derived cases, rotate scenarios, and use qualitative operator review for important promotions.

### 21.5 Risk: Disk Exhaustion

Risk: Repeated nightly runs may fill the Spark with workspaces and artifacts.

Mitigation: Use disposable workspaces, retention policies, external artifact storage, and cleanup enforcement.

### 21.6 Risk: Review Overload

Risk: Nightly Campaigns may generate too many proposals for the operator to review.

Mitigation: Prioritize morning summaries, group low-confidence findings, limit promotion candidates per run, and provide clear recommended decisions.

### 21.7 Risk: Role Proliferation

Risk: The system may create too many agent roles, increasing coordination overhead.

Mitigation: Require evidence that a new role solves a recurring gap better than a skill, tool, prompt, policy, or squad-profile adjustment.

### 21.8 Risk: Cost Growth

Risk: Nightly Campaigns may increase model cost and runtime.

Mitigation: Track cost per Campaign, compare local and cloud model performance, add routing policies, and prefer deterministic tools where appropriate.

### 21.9 Risk: Low-Quality Generated Code

Risk: Agents may generate framework changes that pass narrow tests but reduce maintainability.

Mitigation: Require review, architectural alignment, tests, benchmark evidence, rollback notes, and limited activation.

### 21.10 Risk: Poor Operator Trust

Risk: The operator may not trust self-improvement recommendations.

Mitigation: Improve evidence quality, traceability, summaries, explicit risk surfacing, and reproducible Test Bay links.

---

## 22. Roadmap Implications

### 22.1 Late 1.x Enablers

The following capabilities should be considered late 1.x enablers:

- Durable Run records.
- Better artifact linking.
- Improved Cycle evidence model.
- Basic Campaign model.
- Test Bay source-control integration.
- Disposable workspace cleanup.
- Initial benchmark scorecards.
- Initial Continuum Campaign visibility.
- Initial morning review summary.

### 22.2 SquadOps 2.0.0 Direction

SquadOps 2.0.0 should be oriented around governed compounding improvement.

Key 2.0.0 capabilities should include:

- First-class Campaign orchestration.
- Self-Improvement Campaign templates.
- Test Bay as the default proving ground.
- Capability supply chain and promotion model.
- Scorecard-driven improvement.
- Multi-Cycle objective tracking.
- Squad profile variation across Campaign phases.
- Framework PR Campaigns under controlled autonomy.
- Continuum decision surfaces for promotion and review.

### 22.3 Post-2.0.0 Expansion

After 2.0.0, the system can consider:

- More autonomous low-risk promotion.
- Broader capability-pack ecosystems.
- Public curated Test Bay examples.
- Cross-project benchmark libraries.
- Advanced cost/model optimization.
- More mature safety red-team automation.
- Campaign planning assisted by historical performance.

---

## 23. Implementation Considerations Without Mandating Design

This SIP does not prescribe implementation details, schemas, file structures, or code. However, it does establish several requirements that future technical plans should respect:

- Source-controlled Test Bay targets should be durable and reviewable.
- Execution workspaces should be disposable.
- Heavy artifacts should not be stored directly in Git by default.
- Run metadata should preserve enough traceability for replay and comparison.
- Capability candidates should be distinct from active capabilities.
- Promotion should be explicit and reversible.
- Continuum should prioritize operator decisions over raw execution detail.
- Autonomy should increase only after evidence supports it.

---

## 24. Open Questions

1. Should Test Bay begin as a private repository, with curated public examples later?
2. Should Campaigns become a late 1.x feature flag before becoming central in 2.0.0?
3. What is the minimum viable Campaign model required for nightly improvement?
4. What artifact store should be used for durable run evidence?
5. What is the initial retention policy for Spark execution workspaces?
6. What is the first benchmark suite that should be built?
7. Which initial self-improvement target type should be piloted first?
8. Should Capability Curator and Benchmark Designer be formal roles immediately or emergent squad profiles first?
9. What promotion decisions should Continuum support in the first version?
10. What level of autonomy should be allowed for framework code changes in the first release?
11. Should third-party skill discovery be limited to approved registries initially?
12. How should the system distinguish skill research, skill adaptation, and skill activation?
13. How should Test Bay results feed back into the main SquadOps roadmap?

---

## 25. Recommended Initial Scope

The first deliverable should not attempt to implement the entire self-improvement vision. It should establish the minimum substrate required for safe compounding improvement.

Recommended first scope:

1. Introduce Campaign as an objective container.
2. Introduce Test Bay as the source-controlled proving ground for sample apps and benchmark fixtures.
3. Replace temporary durable app generation with source-controlled targets and disposable execution workspaces.
4. Add basic run-to-source and run-to-artifact traceability.
5. Add one Self-Improvement Campaign type: Failure Archeology Campaign.
6. Add one Benchmark Expansion Campaign that turns failures into benchmark scenarios.
7. Add one Capability Discovery Campaign that produces a candidate capability asset but does not activate it automatically.
8. Add a morning review summary in Continuum.
9. Keep promotion manual.
10. Keep framework code changes branch-only with review evidence.

This scope creates the foundation for the larger 2.0.0 direction without overreaching.

---

## 26. Recommended First Pilot

The recommended first pilot is a nightly Failure Archeology and Benchmark Expansion Campaign.

Objective:

Review recent failed or repaired Cycles, identify one recurring failure pattern, and produce one benchmark scenario plus one proposed mitigation.

Why this pilot:

- It uses real evidence.
- It improves the measurement substrate.
- It avoids risky self-modification.
- It creates value even if no new capability is promoted.
- It prepares the system for future Capability Discovery Campaigns.

Expected output:

- Failure summary.
- Root cause classification.
- New or proposed benchmark case.
- Proposed mitigation.
- Confidence rating.
- Recommended next Campaign.

This pilot should precede more ambitious skill-discovery or framework-code Campaigns.

---

## 27. Success Metrics

### 27.1 Near-Term Metrics

- Number of nightly Campaigns completed with usable morning summaries.
- Percentage of Campaigns with clear final recommendations.
- Number of failures converted into benchmark cases.
- Number of candidate improvements rejected due to evidence or safety findings.
- Reduction in untraceable temporary workspace output.
- Reduction in Spark disk growth from retained run workspaces.

### 27.2 Medium-Term Metrics

- Improvement in benchmark pass rates after promoted capability changes.
- Reduction in recurring failure categories.
- Increase in first-pass acceptance rate.
- Reduction in manual debugging required after failed overnight runs.
- Increase in operator trust of Campaign summaries.
- Reduction in cost for equivalent task quality.

### 27.3 Long-Term Metrics

- Number of safe promoted capability improvements.
- Number of framework improvements proposed and accepted through controlled Campaigns.
- Improvement in autonomous run reliability.
- Improvement in agent role specialization quality.
- Improvement in test coverage and benchmark diversity.
- Demonstrated compounding improvement across multiple Campaigns.

---

## 28. Decision Summary

This SIP recommends adopting Campaigns, Self-Improvement Campaigns, and Test Bay as foundational concepts for the SquadOps 2.0.0 roadmap.

The key decisions are:

- Use Campaign, not Loop, as the objective-level orchestration primitive.
- Keep Cycle bounded.
- Use Test Bay as the source-controlled proving ground.
- Separate source history from heavy artifact evidence.
- Treat capability growth as a governed supply chain.
- Start with evidence-building Campaigns before enabling stronger self-modification.
- Use Continuum as the operator decision surface.
- Make nightly improvement measurable, reviewable, and reversible.

The central bet is that SquadOps becomes meaningfully more powerful when it can improve its own operating capability in a controlled, evidence-backed way.

This is the point where SquadOps can begin to move from agent orchestration to agentic organizational learning.

---

## 29. Final Position

This SIP should be treated as a strategic roadmap anchor for SquadOps 2.0.0.

The vision is not simply to run agents overnight. The vision is to run Campaigns that make the system better at running future Campaigns.

That requires source-controlled proving grounds, durable evidence, scorecards, promotion gates, safety controls, and operator trust.

Test Bay gives the squad a place to prove improvements. Campaigns give the squad a way to pursue objectives across multiple Cycles. Capability Promotion gives the system a safe path from candidate improvement to active capability.

Together, these concepts establish the foundation for SquadOps as a self-improving agent operating system.
