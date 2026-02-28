# IDEA: Cycle-Scoped Multi-Run Workloads, Gate Semantics, and MEH-ta Follow-On Analysis

- Status: Idea
- Date: 2026-02-27
- Domain: SquadOps Core
- Category: Execution Model / Workflow Control / Evaluation
- Intended Follow-On: SIP

## Summary

This idea proposes a cleaner and more durable execution model for SquadOps centered on the distinction between **Cycle**, **Workload**, **Run**, **Task**, **Pulse**, and **Gate**.

The intent is to preserve clear architectural boundaries between:

- the durable mission container
- the bounded units of intended work
- the concrete execution attempts against that work
- the in-run health and alignment checks
- the explicit approval or progression boundaries
- the post-run evaluation and debrief path

This idea also introduces a formal place for:

- human-in-the-loop (HIL) plan review and refinement
- a tracked **Plan Refinement Artifact** and refinement lineage
- automatic follow-on analysis after implementation
- a **MEH-ta** evaluation path that can review a run using shared criteria and evidence

The goal is to avoid collapsing too many responsibilities into a single monolithic runtime concept. Instead, SquadOps should support a model in which a **Cycle progresses through Workloads**, **Workloads are executed by Runs**, **Pulse monitors health during a Run**, and **Gates control progression or promotion when a human or policy decision is required**.

This preserves clarity, lineage, pause/resume behavior, and future scorecard/evaluation support.

## Why This Matters

As SquadOps evolves toward longer-running autonomous behavior, richer coordination, and stronger observability, the execution model must stay semantically clean. If the platform collapses cycle, run, checkpoint, approval, and evaluation into one blurred control plane concept, several problems emerge quickly:

- pause/resume behavior becomes messy
- HIL approvals become hard to reason about
- provenance becomes muddy
- scorecards and RCA lose meaningful attribution
- in-run convergence loops become clogged with approval semantics
- post-run evaluation becomes an awkward afterthought instead of a first-class follow-on capability

The platform needs a structure that supports both autonomy and control without turning either into sludge.

The emerging concept stack now feels stronger and more internally consistent:

- **Cycle** = mission container
- **Workload** = bounded unit of intended work
- **Run** = execution attempt of a workload
- **Task** = atomic work within a workload run
- **Pulse** = in-run health/alignment checkpoint
- **Gate** = progression or promotion boundary

That distinction is valuable because each concept answers a different question:

- What are we trying to achieve overall? -> Cycle
- What bounded thing are we trying to get done now? -> Workload
- What attempt is currently executing that work? -> Run
- What concrete units of work are being performed? -> Task
- How healthy and aligned is the current attempt? -> Pulse
- Should progression continue, pause, revise, rewind, or promote? -> Gate

This idea is meant to preserve and formalize that model.

## Core Intent

The core intent of this idea is to establish a modern SquadOps canon in which:

1. A **Cycle** is the durable container of mission intent, context, state, lineage, artifacts, and progression.
2. A **Workload** is the bounded unit of intended work within the cycle.
3. A **Run** is an execution attempt against a workload.
4. A **Pulse** is a cadence/checkpoint construct used during a run to inspect health, alignment, drift, quality, and blockers.
5. A **Gate** is an explicit progression or promotion boundary used when the platform or a human must make a decision.
6. A cycle may contain multiple workloads such as planning, implementation, and wrap-up evaluation.
7. The implementation workload should include its own test/fix/retest convergence loop.
8. Post-run evaluation should be treated as a formal workload/run rather than an informal side effect.
9. HIL review should default to operating at workload progression or artifact promotion boundaries, not as a stop/start mechanism embedded throughout normal execution.
10. Human plan feedback should be incorporated through tracked refinement rather than direct unstructured mutation of canonical artifacts.

## Canonical Terminology

### Cycle

A **Cycle** is the durable mission container.

A Cycle should own:

- mission objective
- scope and constraints
- canonical context package
- workload graph or workload sequence
- gate history
- shared artifact index
- lineage across runs
- overall status and final outcome

A Cycle is not the same thing as a Run. A Cycle is expected to outlive any individual execution attempt.

### Workload

A **Workload** is a bounded unit of intended work within a Cycle.

A Workload should own:

- objective
- scope
- acceptance criteria
- expected inputs
- expected outputs
- dependency relationships
- gating expectations
- assigned roles or participating agent types

A Workload is the semantic unit that gets run.

This is why the phrase **"run a workload"** feels correct. The workload carries the intent; the run carries the execution.

Examples of workload types:

- planning workload
- implementation workload
- evaluation workload
- refinement workload
- recovery workload

### Run

A **Run** is an execution attempt of a Workload.

A Run should own:

- workload association
- execution timing
- model profile used
- coordination profile used
- produced artifacts
- metrics and telemetry
- outcome
- failure or completion status

A Workload may have more than one Run.

Examples:

- initial run
- retry run
- revision run
- escalated-model run
- recovery run

This allows SquadOps to preserve the bounded intent of a workload while still supporting multiple attempts.

### Task

A **Task** is atomic or near-atomic work within a Workload Run.

Tasks should remain subordinate to the Workload and Run. They are not the same thing as Workloads, and they should not carry the same semantic weight.

### Pulse

A **Pulse** is an in-run health and alignment checkpoint.

Pulse is not a competing unit of intent. It is not another workload.

Pulse exists to ask questions such as:

- Are we still aligned to the workload objective?
- Are we making real progress?
- Are blockers accumulating?
- Is quality degrading?
- Is work drifting from the plan or acceptance criteria?
- Do we need correction, escalation, or rewind?

Pulse should remain a cadence or checkpoint construct that lives **inside the run of a workload**.

A useful way to think about it is:

- Workload = what are we trying to get done?
- Run = this is the current attempt to do it.
- Pulse = how healthy is this attempt right now?

### Gate

A **Gate** is an explicit progression or promotion boundary.

A Gate is different from Pulse.

- Pulse inspects health and alignment during execution.
- Gate decides whether progression, promotion, revision, rewind, or branching may occur.

A Gate may be policy-driven, system-driven, or human-in-the-loop.

Gates should be the place where SquadOps performs explicit decision control, especially when progression depends on a human judgment or policy boundary rather than a purely mechanical check.

## Recommended Structural Pattern

The recommended execution structure is:

- A **Cycle** contains one or more **Workloads**.
- A **Workload** is executed by one or more **Runs**.
- A **Run** contains one or more **Tasks**.
- A **Run** is monitored by **Pulse** checkpoints.
- **Gates** control whether progression continues after significant run or artifact boundaries.

Expressed more simply:

> A Cycle progresses through Workloads. Workloads are executed by Runs. Runs are monitored by Pulse. Gates control progression and promotion.

This structure is cleaner than collapsing everything into a single run concept.

## Multi-Workload Cycle Pattern

A single Cycle should be able to contain multiple Workloads that correspond to major bounded phases of work.

A strong example pattern is:

1. **Planning Workload**
2. **Implementation Workload**
3. **Wrap-up / Evaluation Workload**

Each of these workloads may be executed by one or more runs.

### Planning Workload

Produces artifacts such as:

- plan artifact
- task graph
- assumptions
- risk notes
- acceptance criteria refinement

### Implementation Workload

Produces artifacts such as:

- code changes
- tests
- validation outputs
- implementation notes
- issue/fix loop evidence

### Wrap-up / Evaluation Workload

Produces artifacts such as:

- scorecard inputs
- run summary
- failure attribution
- RCA starter or closure note
- recommendations for next cycle or next workload run
- MEH-ta debrief artifacts

This pattern lets a Cycle act as the durable container while each workload remains bounded and semantically coherent.

## Shared Cycle Data Store

All workloads and runs within a cycle should be able to leverage the **same cycle data store**, provided that the store supports both shared and scoped provenance.

The cycle store should not be a giant junk drawer. It should preserve both shared continuity and run-level attribution.

### Shared cycle scope should include

- cycle objective
- cycle constraints
- canonical context package
- approved/promoted plan
- approved/promoted task graph
- final artifact index
- gate history
- lineage references

### Run-scoped areas should include

- run-local artifacts
- run-local logs
- run-local metrics
- run-local model profile
- run-local coordination profile
- run-local decisions and observations

This allows a later evaluation workload to inspect prior outputs without losing provenance.

### Promotion model

Not every artifact created during a run should become canonical cycle truth.

The platform should distinguish between:

- **working artifacts**
- **promoted artifacts**

Working artifacts are draft or run-local outputs.
Promoted artifacts are elevated to cycle-level significance after review or gate approval.

This helps prevent noise, stale drafts, or half-baked outputs from polluting the canonical cycle state.

## Implementation Workload Should Include Testing

Testing should be treated as part of the **Implementation Workload**, not split out too early as a separate top-level workload.

The reason is simple: implementation is not complete when code is merely written. The implementation workload should own the convergence loop required to produce an acceptably validated implementation.

That means the implementation workload should include:

- coding
- build/test execution
- issue identification
- fixing defects found during implementation validation
- re-test and convergence toward acceptable implementation quality

This is cleaner than forcing a false hard boundary between development and testing where defects must bounce awkwardly between independent workload domains for what is fundamentally one bounded unit of work.

Testing may become a separate workload later if it represents a broader or different intent, such as:

- release validation
- cross-system certification
- compliance review
- independent post-implementation analysis

But the default should be:

> The implementation workload owns the iterative dev/test/fix/retest loop required to converge on an acceptable implementation.

## HIL Gates: Recommended Semantics

### Default recommendation

HIL gates should **not** be the default mechanism used inside a normal workload run.

Inside a run, the preferred mechanisms are:

- tasks
- pulse checkpoints
- pulse checks
- repair loops
- operator visibility
- operator intervention when necessary

The default design should not turn a workload run into stop/start approval sludge.

### Why avoid default HIL pauses inside runs

Embedding formal HIL pause gates throughout the interior of normal workload execution creates several problems:

- breaks convergence flow
- weakens autonomy
- muddies run state
- complicates observability
- turns a bounded execution attempt into fragmented control flow
- makes evaluation harder because it becomes unclear whether the run was progressing, paused, blocked, or awaiting human confirmation

The better default is:

- **Pulse** for in-run health/alignment
- **Gate** for progression or promotion boundaries

### Where HIL gates do make sense

HIL gates make the most sense at true decision boundaries, such as:

- plan promotion to implementation
- artifact promotion to canonical cycle state
- release/deploy/destructive action boundaries
- branch decisions that require product or operator judgment
- exception escalation where policy or confidence thresholds are crossed

### Special-case in-run HIL

An in-run HIL gate may still be allowed in explicitly declared special cases, such as:

- irreversible or destructive actions
- compliance-mandated signoff
- legally or operationally required human confirmation
- genuine human preference or branch choice that cannot be resolved mechanically

But these should be rare, visible, policy-driven exceptions, not the default pattern.

## No HIL Gate Between Implementation and Analysis by Default

A HIL gate should generally **not** sit between the implementation workload and the wrap-up/evaluation workload.

The analysis or MEH-ta workload should usually begin automatically once implementation concludes or terminates.

This is important because post-run analysis is often most valuable when the run did not go well. Requiring human approval before analysis can delay or suppress the very feedback loop the platform most needs.

The preferred pattern is:

- implementation workload run completes or terminates
- evaluation workload run starts automatically
- MEH-ta analysis and debrief artifacts are produced automatically

This creates a cleaner closed-loop learning path.

## Plan Review and Plan Refinement

One of the most important implications of this model is how human review of a plan should work.

A plan review gate should not be modeled as a binary approve/reject only. It should support richer outcomes.

### Recommended gate outcomes for planning review

- **Approve**
- **Approve with Refinements**
- **Return for Revision**
- **Reject / Abort**

The most important new outcome is:

- **Approve with Refinements**

This represents a case where the human agrees with the direction of the plan but wants changes before implementation begins.

### Why this matters

If the platform only supports approve vs reject, it forces awkward behavior:

- either the plan is promoted too early
- or the human is forced to reject a plan that is mostly good
- or changes happen informally outside the tracked system

All three are poor outcomes.

## Plan Refinement Artifact

This idea proposes introducing a formal **Plan Refinement Artifact** and associated refinement tracking so that human feedback becomes attributable and reviewable.

### Core concept

When a planning gate returns **Approve with Refinements**, the human feedback should be persisted as structured refinement instructions rather than informal notes alone.

That feedback should then be incorporated through a tracked follow-on refinement step rather than directly mutating the promoted canonical plan invisibly.

### Refinement record should capture

- refinement id
- source gate id
- cycle id
- planning workload id
- source run id
- target plan artifact id
- reviewer identity
- timestamp
- refinement type
- refinement instruction
- priority
- required-before-implementation flag
- incorporation status
- incorporation notes

### Suggested refinement types

- scope change
- sequencing change
- acceptance criteria change
- dependency correction
- risk mitigation
- task addition
- task removal
- wording/clarity improvement

### Why structured refinement matters

This preserves:

- provenance
- lineage
- what changed
- why it changed
- whether it was incorporated
- whether it improved later results

That is valuable not only for auditability but also for later MEH-ta evaluation and RCA.

## Plan Refinement Run

The preferred mechanism for incorporating meaningful human plan feedback is a **Plan Refinement Run**.

This should usually be modeled as another run of the **same Planning Workload**, not a wholly separate top-level workload unless the refinement path becomes large enough to justify its own workload semantics.

### Recommended flow

1. Planning workload run produces a candidate plan.
2. Human reviews the plan at a planning gate.
3. Human selects **Approve with Refinements**.
4. Gate decision record and refinement instructions are stored.
5. A **Plan Refinement Run** is launched against the planning workload.
6. Revised plan artifact and change summary are produced.
7. Revised plan is promoted as canonical.
8. Implementation workload begins from the revised promoted plan.

This keeps lineage clean and avoids shadow edits to canonical artifacts.

### Incorporation tracking

The refinement mechanism should support a clear mapping between requested refinements and resulting changes.

A refinement incorporation summary should be able to say things like:

- incorporated
- partially incorporated
- not incorporated
- superseded

with rationale where appropriate.

This gives the platform strong traceability for how human plan input changed the eventual implementation path.

## Gates and Progression Across Workloads

Gates should generally be treated as progression or promotion boundaries associated with the cycle/workload progression model.

This means a clean pattern such as:

- workload run completes
- gate evaluates result
- cycle pauses in an awaiting-decision state if needed
- once approved, the next run or next workload may begin

This is cleaner than keeping one giant long-lived flow in a weird half-paused state.

### Recommended mental model

- Runs are bounded
- Gates are explicit
- Cycle state is durable
- Progression resumes by launching the next run for the appropriate workload

That keeps pause/resume semantics understandable and better suited to orchestration platforms such as Prefect.

## MEH and MEH-ta Follow-On Analysis

This idea also proposes a formal relationship between execution and evaluation.

### MEH

**MEH** stands for **Model Evaluation Heuristic**.

MEH is intended as a practical evaluative lens or top-line shorthand for discussing how well a model/framework/resource combination performed in practice.

The point is not raw model intelligence in isolation. The point is practical delivered value under a coordination and resource profile.

### MEH-ta

**MEH-ta** is the meta-evaluation capability that analyzes the results of a run or workload using shared evaluation criteria and evidence.

MEH-ta should answer not just what happened, but why it happened and what should change next.

### Preferred execution pattern

The platform should treat post-run analysis as a formal follow-on workload/run rather than an informal side effect.

For example:

- execution workload run produces artifacts and evidence
- evaluation workload run consumes the evidence
- evaluation run produces scorecard inputs, debrief artifacts, likely limiting factors, and recommendations

This makes the analysis path first-class and benchmarkable.

## Role of Data, Max, and Claude in MEH-ta

### Data

Data should own assembly of a structured **Run Evaluation Pack**.

Data should gather and normalize:

- cycle and workload context
- acceptance criteria
- model profile
- coordination profile
- resource profile
- key events
- validation results
- failure signals
- baseline deltas
- selected evidence excerpts

The goal is to avoid making downstream evaluators churn raw event soup directly.

### Max

Max should consume the Run Evaluation Pack and act as the primary evaluator or operator-side analyst.

Max should assess:

- run verdict
- likely primary limiting factor
- secondary contributors
- fairness of the MEH interpretation
- recommended next changes

### Claude

Claude can act as a second-opinion evaluator using the same pack and same criteria, providing an additional perspective or challenging internal assumptions.

### Why this split matters

This prevents:

- expensive free-form log wandering
- inconsistent weighting of evidence
- dramatic log-line bias
- informal postmortem theater

and instead supports a cleaner pattern:

> Run Evidence -> Data-built Run Evaluation Pack -> Max/Claude MEH-ta Debrief

## Proposed Run Evaluation Pack

A Run Evaluation Pack should likely include:

- run context
- workload objective
- acceptance criteria
- model profile
- coordination profile
- resource profile
- top-line metrics or score inputs
- validation summary
- coordination summary
- resource summary
- failure attribution candidates
- timeline highlights
- baseline comparison
- recommended review questions

This gives post-run evaluators a shared evidence substrate.

## Why Keeping Cycle and Run Separate Was the Right Call

This idea strongly reinforces the value of not smashing Cycle and Run together.

If Cycle and Run were collapsed into one concept, the platform would struggle with:

- pause/resume semantics
- HIL review boundaries
- workload progression
- refinement steps
- automatic follow-on analysis
- clean evaluation and scorecard lineage

By keeping them distinct, the platform gains:

- durable mission state at the cycle level
- bounded execution attempts at the run level
- cleaner progression across workloads
- cleaner gate semantics
- cleaner evaluation lineage

This is one of the core architectural wins emerging from this concept model.

## Architectural Recommendations

### Recommendation 1

Adopt **Cycle -> Workload -> Run -> Task** as the primary execution hierarchy.

### Recommendation 2

Keep **Pulse** as an in-run cadence/checkpoint construct rather than turning it into another workload-like unit.

### Recommendation 3

Treat **Gate** as a progression/promotion construct rather than as a generic in-run pause mechanism.

### Recommendation 4

Default to **no HIL pause gates inside normal workload runs**.

### Recommendation 5

Support **Approve with Refinements** and a formal **Plan Refinement Artifact** for planning review.

### Recommendation 6

Incorporate meaningful plan feedback through a tracked **Plan Refinement Run** rather than informal direct edits to canonical plan artifacts.

### Recommendation 7

Treat post-run evaluation as a formal **evaluation workload/run** and let it start automatically after implementation by default.

### Recommendation 8

Use **Data** to assemble the Run Evaluation Pack and let **Max** and optionally **Claude** perform MEH-ta analysis using that shared evidence substrate.

### Recommendation 9

Use the cycle data store as the shared parent evidence store, while preserving run-scoped provenance and promotion rules for artifacts.

## Questions for SIP Exploration

This idea should be turned into one or more SIPs that explore what platform capability is required to support it well.

Key questions include:

1. What first-class entities should SquadOps introduce or formalize for Cycle, Workload, Run, Pulse, Gate, and Artifact?
2. How should workload graphs or workload sequencing be modeled inside a cycle?
3. What state models are required for cycle state, workload state, run state, and gate state?
4. What artifact promotion model is needed to distinguish working artifacts from canonical cycle artifacts?
5. How should Plan Refinement Artifacts be stored, linked, versioned, and surfaced?
6. Should Plan Refinement Run remain a run of the planning workload, or ever become its own workload type?
7. How should HIL gate outcomes be represented in the platform and console?
8. What events and lineage are required to support clean pause/resume and RCA?
9. How should evaluation workloads and MEH-ta runs be modeled and triggered?
10. What is the minimum viable Run Evaluation Pack for useful post-run debriefs?
11. How should Data, Max, and other agents participate in evaluation workloads without muddying accountability?
12. How should Prefect orchestration map onto cycle progression, workload runs, gate waits, and follow-on runs?

## Suggested Follow-On SIP Candidates

This idea could branch into multiple SIPs, for example:

1. **Cycle, Workload, Run, Pulse, and Gate Canonical Model**
2. **Artifact Promotion and Cycle-Scoped Provenance**
3. **Plan Review, Plan Refinement Artifact, and Refinement Run Semantics**
4. **Evaluation Workload and MEH-ta Follow-On Analysis**
5. **Run Evaluation Pack and Agent-Assisted Debrief Flow**
6. **Cycle/Workload State Model and Gate Progression Semantics**

## Closing Thought

The emerging model feels strong because the semantics are tightening instead of blurring.

- A cycle is the durable mission container.
- A workload is the bounded unit of intended work.
- A run is the attempt that executes that workload.
- pulse manages health during the run.
- gates manage progression and promotion.
- implementation owns convergence, including testing.
- evaluation is formal follow-on work, not an afterthought.
- human refinement is tracked, not hand-waved.

That is a much stronger foundation for SquadOps than a flattened model where everything is just a run, every checkpoint is a pause, and every review step becomes workflow soup.
