# SIP-DRAFT: Cycle Evaluation and Scorecard Intent Framework

- Status: Draft
- Type: Standards Track
- Created: 2026-02-27
- Target Release: 1.1+
- Owner: SquadOps Core
- Depends On: Cycle, Pulse, Task, RCA, Telemetry, Console Perspectives
- Related: WarmBoot, Pulse Checks, operator console, model-profile evaluation, benchmark harness

## Summary

This SIP proposes that SquadOps adopt a first-class evaluation framework for cycles so the platform can measure what actually matters: whether a cycle produced a valuable result, how good that result was, how effectively the squad coordinated to produce it, and what it cost in time and resources.

The purpose of this proposal is not to create a shallow leaderboard for models or agents. The purpose is to create an operating discipline that allows SquadOps to improve intelligently.

SquadOps needs to know when a cycle underperformed because the model was too weak, when it underperformed because coordination was poor, when it failed because context was incomplete, and when it produced acceptable work at an inefficient cost. Without that separation, the platform will optimize blindly and draw the wrong conclusions.

This SIP therefore introduces an intent-first evaluation model centered on four core dimensions:

1. outcome success
2. output quality
3. coordination effectiveness
4. resource efficiency

These dimensions should become a first-class part of the operator experience through a dedicated Scorecard page in the Cycles perspective of the console.

## Why This SIP Exists

SquadOps is not being built merely to execute prompts. It is being built to coordinate work through a structured multi-agent system capable of producing meaningful outcomes over longer-running cycles.

As soon as that ambition becomes real, evaluation becomes a structural concern rather than a reporting concern.

A short local experiment can still be judged informally. A long-running cycle with multiple agents, multiple validations, different model profiles, and different coordination patterns cannot. At that point, raw traces and logs are not enough. Event counts are not enough. Even pass or fail is not enough.

The system needs a way to answer questions such as:

- Did this cycle actually succeed in a meaningful sense?
- Was the output trustworthy or merely plausible?
- Did the squad work together effectively or did it stumble through friction and rework?
- Did the host and model strategy support the workload well, or was the whole run inefficient?
- If the run was disappointing, what actually caused that disappointment?

Without a disciplined framework, poor conclusions become inevitable. A capable model may look weak because the coordination framework is poor. A smaller efficient model may look weak because it is being judged against the absolute output ceiling of a much larger model. A noisy cycle may look productive because the system is measuring activity instead of value.

This SIP exists to stop that drift before it becomes embedded into the platform.

## Core Thesis

The core thesis of this proposal is:

> A cycle must be evaluated as a system outcome, not as a collection of isolated agent actions.

A system outcome can only be judged well if the platform explicitly measures multiple dimensions of success and preserves enough evidence to explain the result.

That means SquadOps should treat cycle evaluation as a first-class architectural concern, not an optional analytics layer.

## Goals

This proposal has the following goals:

1. establish a canonical evaluation philosophy for SquadOps cycles
2. make cycle outcomes measurable in a way that is fair, explainable, and useful
3. prevent model evaluation and framework evaluation from being carelessly conflated
4. support disciplined comparison across model profiles, coordination strategies, and resource envelopes
5. provide an operator-facing scorecard in the Cycles perspective that reflects the actual health of a run
6. create a foundation for better RCA, WarmBoot behavior, and future optimization decisions

## Non-Goals

This SIP does not attempt to:

1. reduce all cycle performance to one magic number
2. eliminate human judgment from evaluation
3. declare a single universal definition of quality for every workload
4. turn telemetry into a fake proxy for semantic correctness
5. define the final implementation details for every scoring mechanism

This is an intent and framework SIP. It establishes what SquadOps should care about and why.

## Problem Statement

Today, it is still possible to inspect a run by hand and form an opinion. That is not a durable operating model.

As SquadOps matures, cycles will become:

- longer-running
- more autonomous
- more parallel
- more dependent on handoffs and checkpoints
- more likely to be compared across different model mixes and hardware constraints

When that happens, a weak evaluation model becomes a serious liability.

### If evaluation remains shallow, several bad outcomes follow

#### 1. Strong models get blamed for weak coordination
A model may receive incomplete context, poorly framed subtasks, or broken handoffs. The run then looks weak, but the weakness is in the framework, not the model.

#### 2. Small models get judged unfairly
A constrained profile may deliver very good value for its size and cost, yet still lose every comparison if the platform only values absolute output ceiling.

#### 3. Activity becomes confused with value
The system may begin optimizing for prompt volume, task counts, or visible motion instead of accepted results.

#### 4. Operators lose tuning clarity
If the platform cannot distinguish among model, coordination, context, validation, and resource failures, tuning becomes guesswork.

#### 5. The console becomes decorative
A console that shows traces, event counts, and status lights without exposing whether the cycle actually delivered value is not yet an operator surface. It is just instrumentation theater.

SquadOps therefore needs an evaluation framework that treats cycle assessment as part of the product, not as a sidecar.

## Design Principles

### 1. Outcomes matter more than activity
A cycle that is noisy, busy, or verbose is not necessarily successful. The platform should privilege accepted outcomes over visible effort.

### 2. Accountability must remain separable
Model capability, coordination quality, context quality, validation strength, and resource constraints are different layers. The framework must keep them separate so the system can learn correctly.

### 3. Efficiency is part of value
A result that is only marginally better but dramatically more expensive may not be the best operating point. Efficiency is not secondary. It is one of the dimensions of success.

### 4. Scores must remain explainable
Operators should be able to understand why a score changed. A score with no visible evidence behind it is decorative rather than operational.

### 5. Constrained profiles must be evaluated fairly
A smaller model should not be condemned merely because it is not a larger model. The framework should allow the platform to ask whether a given profile performed well within its intended envelope.

### 6. Evaluation must support improvement
The point of evaluation is not retrospective judgment alone. It is to improve future cycles, improve WarmBoot decisions, improve coordination design, and improve model selection.

## End State Vision

When this SIP is realized, an operator should be able to open a completed cycle in the Cycles perspective and immediately understand:

- whether the cycle succeeded in a meaningful sense
- whether the output quality was strong or weak
- whether the squad coordinated effectively or struggled through friction
- whether the cycle consumed resources efficiently or wastefully
- what most likely limited success
- how this run compares to similar runs or baseline profiles

The operator should not have to infer these answers from raw telemetry.

The operator should also be able to compare runs in a disciplined way. For example:

- same workload, same coordination, different models
- same workload, same model, different coordination approach
- same workload, same budget envelope, different strategy

That comparison ability is a strategic capability, not a reporting nicety.

## Evaluation Philosophy

This SIP recommends that SquadOps evaluate every cycle through four primary lenses.

### 1. Outcome Success
This asks the most basic question: did the cycle achieve the intended result?

A cycle that never reaches acceptable output should not receive high marks simply because it was active, clever, or thorough. Outcome must remain central.

### 2. Output Quality
A cycle may finish without producing work that is trustworthy. The framework should capture the difference between completion and credibility.

For software-oriented workloads, this includes evidence such as validation health, build stability, test outcomes, and defect signals. More broadly, it includes whether the result could be accepted without major rewrite or rescue.

### 3. Coordination Effectiveness
SquadOps is not just evaluating models; it is evaluating a coordination framework. That means the platform must measure how well agents hand work to one another, how often they stall, how much rework they create, and whether checkpoints improve flow or just create drag.

This is one of the most important parts of the SIP because framework quality is easy to hide and easy to misattribute.

### 4. Resource Efficiency
A cycle that succeeds but burns disproportionate time, memory, queue time, or token budget may still be the wrong operating point. The platform should therefore treat efficiency as part of the overall evaluation.

This is especially important for local or constrained infrastructure, where resource discipline is a product concern rather than a cost-accounting footnote.

## Failure Attribution Intent

One of the most important intentions of this SIP is to make failure attribution explicit.

A run should not simply be labeled as failed or weak. It should be classified in a way that helps SquadOps learn.

The framework should be able to distinguish at least the following categories:

- model insufficiency
- coordination failure
- context failure
- validation failure
- resource failure
- acceptance criteria failure
- external dependency failure

The purpose of these categories is not bureaucratic tidiness. The purpose is to ensure that the platform does not draw the wrong lesson.

If a model fails because it was given poor context, that is not the model’s failure alone. If a cycle looks successful only because the validation layer was weak, that is not a quality success. If a smaller model delivers adequate results at far lower cost, it should not be dismissed because it did not match the strongest large-model output.

This failure attribution model is one of the key pieces that allows benchmarking to remain honest.

## Benchmarking Intent

This SIP also exists because SquadOps will increasingly need to compare different combinations of:

- model families
- model sizes
- single-model versus multi-model strategies
- coordination patterns
- pulse-check density
- resource envelopes

Those comparisons are only meaningful if the platform can hold the right things constant.

The framework should therefore support three major comparison styles:

### Fixed coordination, variable models
Use when the question is: what did the models change?

### Fixed model, variable coordination
Use when the question is: what did the framework change?

### Fixed resource envelope, variable strategy
Use when the question is: what is the best point on the quality-efficiency frontier?

This is how the system avoids turning experimentation into mythology.

## Fairness for Resource-Constrained Profiles

A core concern behind this SIP is fairness.

You explicitly do not want to punish a model because coordination is poor, and you do not want to expect too much from a model that was designed to operate within a tighter resource envelope. This SIP agrees with that framing completely.

The framework should therefore assume that cycles may be run under intentionally different profiles, such as:

- lean
- balanced
- max-quality

Each of these profiles may have different expectations around:

- model size
- latency tolerance
- resource consumption
- validation strictness
- accepted tradeoffs

The point is not to lower standards artificially. The point is to evaluate a cycle against the strategy it was intentionally pursuing.

A lean profile should still be judged seriously, but not naively compared as if it were attempting the same operating point as a max-quality profile.

## Why the Cycles Perspective Needs a Scorecard Page

This SIP recommends that the Cycles perspective in the console include a dedicated Scorecard page.

That page should exist because a completed cycle is the natural unit of evaluation for an operator.

The operator should not need to bounce among raw traces, logs, artifacts, and status panels to form a judgment. The platform should present a coherent scorecard that tells the story of the cycle at the right altitude while still allowing deeper drill-down.

The Scorecard page should center on four visible dimensions:

- Outcome
- Quality
- Coordination
- Efficiency

Around those, it should present:

- the key evidence behind those scores
- the primary failure attribution
- the resource profile under which the cycle ran
- the model and coordination profile used
- baseline comparisons to similar prior runs
- next-step recommendations for the operator

The page should help the operator answer:

- what happened?
- how good was it?
- what constrained it?
- what should we adjust next?

That is why the scorecard belongs in the Cycles perspective as a first-class page.

## What the Framework Should Encourage

This SIP is not only about measurement. It is also about shaping behavior.

The framework should encourage SquadOps to:

- optimize for accepted outcomes
- preserve strong validation discipline
- improve handoffs and planning quality
- use larger models where they are justified
- use smaller models where they are efficient and sufficient
- detect coordination drag early
- capture evidence strong enough to support RCA
- evolve toward a more intentional operating frontier between quality and efficiency

In other words, this SIP should help SquadOps become a force multiplier rather than a machine that merely produces visible effort.

## Strategic Recommendation

This SIP recommends that SquadOps formally adopt cycle evaluation as a core systems concern.

The platform should not postpone evaluation until after the coordination framework is already mature. By then, weak assumptions will already be embedded in the runtime, the console, and the operator’s mental model.

Instead, SquadOps should establish now that every meaningful cycle is expected to answer four questions:

1. Did it succeed?
2. Was the output good?
3. Did the squad coordinate well?
4. Was the result achieved efficiently?

Everything else in this SIP flows from that discipline.

## Phased Intent

This SIP intentionally avoids over-fixating on implementation mechanics, but it does recommend a broad sequence of maturation.

### Phase 1 - Establish the evaluation contract
SquadOps should first define what it intends to measure and why. This includes the score dimensions, failure attribution philosophy, and the meaning of fair comparison.

### Phase 2 - Capture evidence consistently
Once the contract exists, the runtime should emit the evidence required to support it. The goal is not maximal telemetry. The goal is sufficient evidence for explainable evaluation.

### Phase 3 - Compute explainable scorecards
Once evidence exists, the platform should derive scorecards that remain transparent and attributable.

### Phase 4 - Surface scorecards in the Cycles perspective
Once the scorecards are trustworthy enough to explain themselves, they should become part of the operator console.

### Phase 5 - Support disciplined experimentation
After that foundation exists, SquadOps can compare model families, coordination patterns, and budget envelopes without confusing one variable for another.

## Risks

### Risk: false precision
If the platform presents scores as if they are objective truth, it will overstate what the system actually knows.

### Risk: metric sprawl
If too many metrics appear before the framework has clear priorities, operators will lose focus.

### Risk: wrong attribution
If failures are classified casually, the framework will teach the wrong lessons.

### Risk: optimizing the wrong dimension
If efficiency becomes overemphasized, quality may degrade. If outcome becomes overemphasized, cost discipline may degrade. If coordination becomes invisible, the framework may quietly remain weak.

These risks are exactly why the SIP emphasizes multiple visible dimensions instead of one synthetic number.

## Open Questions

This SIP leaves several questions intentionally open for later refinement:

1. Which score dimensions should carry the most weight for different workload types?
2. How strict should baseline comparison be when selecting similar prior runs?
3. Which signals should remain mandatory versus optional in early versions?
4. How much of the score explanation should be visible by default in the console?
5. When should rule-based recommendations be introduced on top of the scorecard?

These are good implementation questions, but they should follow the intent, not precede it.

## Recommendation

Adopt this SIP as the intent-level foundation for SquadOps cycle evaluation and scorecards.

SquadOps should treat evaluation as a structural part of the platform’s operating model, not as post-hoc analytics. The Cycles perspective should ultimately expose that evaluation through a first-class Scorecard page so operators can reason clearly about outcome, quality, coordination, and efficiency.

This proposal is, at its heart, about discipline.

SquadOps should not ask only whether a cycle ran.
It should ask whether the cycle delivered value, how it delivered that value, what constrained it, and whether the chosen model and coordination strategy were the right fit for the resource envelope.

That is the intent this SIP is designed to establish.
