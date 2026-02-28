# SIP-0XXX: Cycle Evaluation Scorecard

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

This SIP establishes a first-class evaluation framework for SquadOps Cycles, measuring what actually matters: whether a Cycle produced a valuable result, how good that result was, how effectively the squad coordinated, and what it cost in time and resources. The framework evaluates four dimensions — outcome success, output quality, coordination effectiveness, and resource efficiency — with explicit failure attribution to prevent the platform from drawing the wrong lessons. A Scorecard page in the Cycles console perspective surfaces these evaluations to operators.

## 2. Problem Statement

Today, a completed cycle can only be judged by manual inspection of traces, logs, artifacts, and status panels. That is not a durable operating model. As cycles become longer, more autonomous, and more varied in model/coordination profiles, several problems emerge:

- **Strong models blamed for weak coordination** — a model receives incomplete context or broken handoffs, and the run looks weak even though the framework is at fault.
- **Small models judged unfairly** — a constrained profile delivers good value for its cost but loses every comparison against absolute output ceiling.
- **Activity confused with value** — the system optimizes for prompt volume, task counts, or visible motion instead of accepted results.
- **Operators lose tuning clarity** — without separating model, coordination, context, and resource failures, tuning becomes guesswork.
- **Console becomes decorative** — traces and event counts without evaluation of whether the cycle delivered value is instrumentation theater, not an operator surface.

## 3. Goals

1. Establish a **canonical evaluation philosophy** for SquadOps cycles: evaluate as a system outcome, not as a collection of isolated agent actions.
2. Define **four evaluation dimensions**: outcome success, output quality, coordination effectiveness, resource efficiency.
3. Introduce **failure attribution categories** that separate model insufficiency, coordination failure, context failure, validation failure, resource failure, acceptance criteria failure, and external dependency failure.
4. Support **disciplined comparison** across model profiles, coordination strategies, and resource envelopes with three comparison styles: fixed coordination/variable models, fixed model/variable coordination, fixed resources/variable strategy.
5. Ensure **fair evaluation of resource-constrained profiles** — a lean profile is judged against its intended operating envelope, not against a max-quality profile.
6. Surface evaluation through a **Scorecard page** in the Cycles console perspective.

## 4. Non-Goals

- Reducing all cycle performance to one magic number — multiple visible dimensions prevent that.
- Eliminating human judgment from evaluation — operators still interpret and override.
- Defining a universal quality definition for every workload type — workload-specific weighting is deferred.
- Defining final implementation details for every scoring mechanism — this is an intent and framework SIP.
- Replacing raw telemetry or structured logging — those serve different purposes.
- Implementing the wrap-up workload or closeout artifact (covered by the Wrap-Up Workload Protocol SIP).

## 5. Approach Sketch

### Evaluation Dimensions

Every completed cycle is evaluated through four lenses:

#### 1. Outcome Success
Did the cycle achieve the intended result? A cycle that never reaches acceptable output should not receive high marks for being active, clever, or thorough.

#### 2. Output Quality
Is the result trustworthy? Includes validation health, build stability, test outcomes, and defect signals. Measures whether the result could be accepted without major rewrite or rescue.

#### 3. Coordination Effectiveness
How well did agents hand work to one another? How often did they stall? How much rework was created? Did checkpoints improve flow or create drag? This dimension prevents framework quality problems from being hidden or misattributed to models.

#### 4. Resource Efficiency
Was the result achieved efficiently? A result that is marginally better but dramatically more expensive may not be the best operating point. Covers time, token budget, queue time, and resource consumption.

### Failure Attribution

When a cycle underperforms, the framework classifies the primary limiting factor:

| Category | Meaning |
|----------|---------|
| `model_insufficiency` | Model capability was the bottleneck |
| `coordination_failure` | Handoffs, framing, or sequencing were the problem |
| `context_failure` | Incomplete or incorrect context was provided |
| `validation_failure` | QA/verification was too weak to catch issues |
| `resource_failure` | Time, tokens, or compute were exhausted |
| `acceptance_criteria_failure` | Criteria were vague, untestable, or misaligned |
| `external_dependency_failure` | External service, API, or tool was unavailable |

### Benchmarking Support

Three comparison styles for disciplined experimentation:

- **Fixed coordination, variable models** — what did the models change?
- **Fixed model, variable coordination** — what did the framework change?
- **Fixed resource envelope, variable strategy** — what is the best quality-efficiency point?

### Profile-Aware Evaluation

Cycles run under intentionally different profiles (lean, balanced, max-quality). The framework evaluates a cycle against the strategy it was intentionally pursuing, not against an absolute ceiling.

### Scorecard Page (Console)

The Cycles perspective in the console includes a Scorecard page showing:

- Four dimension scores with key evidence.
- Primary failure attribution.
- Resource profile and model/coordination profile used.
- Baseline comparison to similar prior runs.
- Next-step recommendations.

Answers four operator questions: what happened, how good was it, what constrained it, what should we adjust next.

### Phased Maturation

1. **Phase 1**: Establish evaluation contract — define dimensions, attribution philosophy, fair comparison principles.
2. **Phase 2**: Capture evidence consistently — runtime emits evidence needed for explainable evaluation.
3. **Phase 3**: Compute explainable scorecards — derive scores that remain transparent and attributable.
4. **Phase 4**: Surface in Cycles perspective — scorecard page becomes part of the operator console.
5. **Phase 5**: Support disciplined experimentation — compare model families, coordination patterns, budget envelopes.

## 6. Key Design Decisions

1. **Four dimensions, not one number** — prevents optimization of the wrong dimension and keeps accountability separable.
2. **Failure attribution is mandatory** — every underperforming cycle gets classified so the platform learns correctly.
3. **Scores must be explainable** — a score with no visible evidence behind it is decorative, not operational.
4. **Efficiency is a first-class dimension** — not secondary to outcome or quality. Especially important for local or constrained infrastructure.
5. **Constrained profiles evaluated fairly** — a lean profile is not condemned for not being a larger model. The framework asks whether the profile performed well within its intended envelope.
6. **Evaluation is a system concern, not an analytics sidecar** — established before the coordination framework matures so weak assumptions don't get embedded.

## 7. Acceptance Criteria

1. Evaluation contract defines the four dimensions with measurable indicators for each.
2. Failure attribution categories are defined and assignable to completed cycles.
3. Scorecard data model captures dimension scores, attribution, evidence references, and comparison baselines.
4. API endpoint returns scorecard data for a completed cycle.
5. Console Scorecard page renders four dimensions, failure attribution, profile info, and recommendations.
6. Benchmarking support: API can filter/compare cycles by model profile, coordination strategy, and resource envelope.
7. Profile-aware evaluation: lean cycles are not penalized for lower absolute output compared to max-quality cycles.
8. Evidence for each dimension score is traceable to specific artifacts, metrics, or events.

## 8. Source Ideas

- `docs/ideas/IDEA-cycle-evaluation-scorecard-framework.md` — full evaluation philosophy, four dimensions, failure attribution model, benchmarking intent, fairness for constrained profiles, scorecard page concept, phased maturation plan.

## 9. Open Questions

1. Which dimensions should carry the most weight for different workload types?
2. How strict should baseline comparison be when selecting similar prior runs?
3. Which evidence signals should be mandatory vs optional in early versions?
4. How much of the score explanation should be visible by default in the console?
5. When should rule-based recommendations (e.g., "try a larger model" or "improve handoff framing") be introduced on top of the scorecard?
6. Should scorecard computation be automated (Data agent assembles evidence, Lead evaluates) or fully mechanical?
