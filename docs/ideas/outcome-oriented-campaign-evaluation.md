# Idea: Outcome-Oriented Campaign Evaluation and Autonomous Improvement

> **Recorded 2026-10-04** as the owner wrote it, during the 2.0 counted set. The owner asked whether it
> warranted a SIP and where it falls against Cross-Cycle Memory. **The owner agreed the recommendation the
> same day** ("yes, save the idea and draft the SIP"):
> - **Its evaluation half becomes a SIP:** `sips/proposed/SIP-Outcome-Evaluation.md`. That covers
>   independent outcome scenarios, local quality baselines, an intervention ledger, a per-increment
>   reading of outcome contribution, and AOR and the AWE as derived metrics.
> - **The rest stays here, as the charter that SIP serves:**
>   - the external tunnel to cloud evaluators (a security decision, after local evaluation);
>   - LLM UX scores (corroborating only);
>   - SquadOps proposing its own framework experiments (framework self-improvement is deferred; the
>     outer loop is the crew's).
> - **Ordering:** after Cross-Cycle Memory (2.2). The reporting-only instruments go to 2.3, and the
>   SIP's feature half heads 2.4, before the squad authors its own backlog.

## Purpose

SquadOps Campaigns should optimize for **verified outcomes**, not merely
the production of software outputs.

The long-term objective is not simply for SquadOps to generate more code
with less human involvement. It is for SquadOps to become increasingly
capable of **building, evolving, operating, and repairing high-quality
software autonomously**, with independent evidence that both the product
and the autonomous system are improving.

This suggests a core principle:

> **Tasks produce outputs. Cycles produce validated changes. Campaigns
> pursue outcomes. The outer loop expands the autonomous work
> envelope.**

A Campaign therefore should not be a fixed sequence of predeclared
Cycles. It should hold a persistent desired outcome and dynamically
select subsequent Cycles based on evidence from prior execution.

------------------------------------------------------------------------

## 1. The Problem With Output-Oriented Campaigns

A roadmap can easily become a list of capabilities shipped:

-   implement replay
-   improve memory
-   add verification contracts
-   add recovery
-   improve telemetry
-   add another Group Run feature

These may all be useful, but completing them does not prove that either:

1.  the target application became better, or
2.  SquadOps became better at autonomously producing good software.

A Campaign needs to measure both.

For the Group Run experiment, for example, "add persistent run history"
is an **output**. The more meaningful outcomes are things such as:

-   a user or independent agent can successfully resume an interrupted
    run;
-   the application is more understandable and usable;
-   existing behavior did not regress;
-   the capability meets reliability and performance thresholds;
-   SquadOps required fewer interventions to achieve the improvement;
-   SquadOps recovered from failures that previously required human
    help.

------------------------------------------------------------------------

## 2. Two Independent Outcome Dimensions

Campaign evaluation should explicitly separate **Product Outcome** from
**Autonomy Outcome**.

### Product Outcome

> Did the software actually become better?

This should include evidence such as:

-   functional correctness;
-   regression protection;
-   reliability;
-   usability;
-   accessibility;
-   performance;
-   security/best practices;
-   maintainability/architecture;
-   successful completion of representative user outcome scenarios.

### Autonomy Outcome

> Did SquadOps become better at producing that improvement autonomously?

This should include:

-   human interventions per Campaign/Cycle;
-   intervention type and severity;
-   autonomous recovery rate;
-   successful replanning rate;
-   time to recovery;
-   autonomous completion rate;
-   cost per verified outcome;
-   elapsed time per verified outcome.

Neither dimension can substitute for the other.

A system that produces poor software without asking for help is
autonomous but incompetent. A system that produces excellent software
only because a human continually rescues it is capable but not
autonomous.

The target is **autonomous excellence**.

------------------------------------------------------------------------

## 3. Quality Is a Gate on Autonomy

A foundational Campaign invariant should be:

> **A Campaign cannot claim increased autonomy unless product quality
> meets or exceeds its required quality baseline.**

This prevents autonomy metrics from being gamed by simply reducing
escalation or human involvement.

Similarly, a Cycle can successfully produce its requested output while
failing to create meaningful outcome improvement.

That distinction should be first-class:

-   **Output completed**
-   **Quality gates passed**
-   **Outcome contribution demonstrated**
-   **Autonomy contribution demonstrated**

A technically successful Cycle can therefore legitimately conclude:

> Output accepted; outcome contribution negligible.

That is useful learning rather than a false success.

------------------------------------------------------------------------

## 4. Campaigns Commit to Outcomes, Not Plans

Campaigns should **not** specify a fixed list of Cycles up front.

The stable elements of a Campaign are:

-   desired outcome;
-   success measures;
-   quality baselines;
-   constraints and guardrails;
-   budget and authority boundaries.

The adaptive elements are:

-   diagnosis of the current gap;
-   next Cycle objective;
-   implementation approach;
-   tasks;
-   recovery actions;
-   subsequent hypotheses.

The control loop becomes:

``` text
Desired Outcome
      |
      v
Observe Current State
      |
      v
Identify Highest-Value Gap
      |
      v
Form Outcome Hypothesis
      |
      v
Generate Next Cycle
      |
      v
Execute
      |
      v
Evaluate Product + Autonomy
      |
      v
Learn / Replan
      |
      +---------------------> repeat
```

The Campaign planner should therefore ask:

> **Given the desired outcome and everything learned so far, what is the
> highest-value next Cycle?**

---not---

> What remaining Cycle in the plan should execute next?

------------------------------------------------------------------------

## 5. Cycles as Outcome Hypotheses

A Cycle should contain more than an implementation objective.

Example:

### Cycle Objective

Add persistent Group Run history.

### Outcome Hypothesis

Persistent history will allow a user or agent to return to an
interrupted Group Run, understand its prior state, and continue
correctly.

### Expected Output

Persistent run-history capability.

### Quality Gates

-   persistence survives application restart;
-   no run-state corruption;
-   existing acceptance scenarios continue to pass;
-   accessibility does not regress;
-   performance remains within threshold;
-   architecture/maintainability does not regress.

### Outcome Evidence

An independent evaluator can:

1.  create/start a Group Run;
2.  interrupt it;
3.  return later;
4.  identify completed and remaining work;
5.  resume the correct run;
6.  complete it without repeating completed work.

### Campaign Contribution

If validated, Group Run has gained an independently demonstrated
capability and the Campaign has moved toward its desired outcome.

------------------------------------------------------------------------

## 6. A Layered Evaluation Model

No single score should determine application quality. Campaign
evaluation should combine several independent forms of evidence.

### Layer 1 --- Deterministic Engineering Gates

Examples:

-   build;
-   unit/integration tests;
-   type checking;
-   linting;
-   security scanning;
-   API contract verification;
-   deterministic acceptance tests;
-   regression tests.

These answer:

> **Is the implementation technically sound according to known rules?**

They are necessary but insufficient.

### Layer 2 --- Technical Web Quality

For web applications, tools such as **Google Lighthouse** and **axe**
can run locally and produce repeatable machine-readable measures.

Lighthouse can measure areas such as:

-   performance;
-   accessibility;
-   web best practices;
-   SEO where relevant.

These metrics can establish baselines and regression gates.

Example:

``` yaml
quality_gates:
  lighthouse:
    performance: ">= 85"
    accessibility: ">= 90"
    best_practices: ">= 95"
    max_regression: 5
```

A technically poor application can therefore fail the Campaign gate even
when its functional tests pass.

These scores still do **not** prove that the application is useful.

### Layer 3 --- Independent Outcome Scenarios

This should become one of the strongest Campaign quality signals.

Instead of asking an evaluator:

> Is this application good?

give an independent agent an actual job:

> Create a group, start a run, determine its state, interrupt it, return
> later, resume it, identify remaining work, and successfully finish.

Measure:

-   success/failure;
-   elapsed time;
-   number of actions;
-   retries;
-   recovery attempts;
-   incorrect actions;
-   evaluator confusion;
-   human assistance;
-   final outcome correctness.

This tests whether the application enables the outcome it was built to
support.

### Layer 4 --- Independent UX/Design Evaluation

An external service or independent model can provide additional signals
around:

-   visual hierarchy;
-   clarity;
-   usability;
-   consistency;
-   accessibility;
-   interaction design.

These scores should be treated as **corroborating evidence**, not
authoritative truth.

The important question over time is whether changes in an evaluator's
score correlate with improvements in independent outcome-scenario
success.

If not, remove or reduce the weight of that evaluator.

------------------------------------------------------------------------

## 7. The Evaluator Must Be Independent

SquadOps should not be allowed to completely define the tests by which
its own success is judged.

This is particularly important for generated software, because an
implementation agent can unintentionally create tests that merely
validate its own assumptions.

The evaluation architecture should preserve independence.

For the Nostromo/SquadOps experiment:

-   **SquadOps** builds/evolves the application.
-   **Brett** owns or executes independent outcome verification.
-   **Data** captures telemetry and longitudinal measurements.
-   **Ripley/Dallas** analyze failures and identify likely
    autonomy/platform constraints.
-   **Nostromo outer loop** recommends the next experiment or framework
    improvement.
-   **Owner** retains approval/authority boundaries where required.

Outcome scenarios and their success definitions should therefore live
outside the control of the agents implementing the feature.

------------------------------------------------------------------------

## 8. Human Intervention as an Autonomy Signal

Human intervention remains important, but it measures **SquadOps**, not
application quality.

Every intervention should be recorded and classified.

Example:

``` yaml
human_intervention:
  reason: verification_failure
  severity: unblock
  cycle: 7
  time_to_intervention: 00:14:32
  time_to_recovery: 00:06:11
  agent_could_have_resolved: true
```

Suggested reasons:

-   clarification;
-   planning failure;
-   implementation failure;
-   verification failure;
-   environment failure;
-   tool failure;
-   coordination failure;
-   memory/context failure;
-   judgment/escalation;
-   authorization.

Suggested severity:

-   advisory;
-   unblock;
-   recovery;
-   abort.

This creates a dataset from which the outer loop can identify the next
autonomy bottleneck.

For example:

> 47% of owner interventions across the last five Campaigns resulted
> from verification failures that the Lead correctly identified but
> lacked authority or mechanisms to recover from.

That is evidence for a platform improvement---not merely an intuition
that "recovery needs work."

------------------------------------------------------------------------

## 9. Autonomous Work Envelope

Rather than treating autonomy as binary, SquadOps should measure the
**Autonomous Work Envelope (AWE)**: the range of software work it can
reliably complete without human intervention while meeting quality,
cost, and safety constraints.

Possible dimensions include:

-   duration;
-   number of Cycles;
-   task complexity;
-   ambiguity;
-   number of collaborating agents;
-   external dependencies;
-   failure frequency;
-   required replanning;
-   recovery complexity;
-   quality threshold;
-   cost;
-   human intervention.

The objective of successive Campaigns is to expand this envelope.

Example:

  Work Envelope                     Verified Autonomous Success
  ------------------------------- -----------------------------
  30-minute single-Cycle change                             97%
  2-hour multi-Cycle feature                                91%
  8-hour Campaign                                           72%
  24-hour Campaign                                          41%
  Ambiguous greenfield build                                23%

Progress means moving this frontier outward while preserving product
quality.

------------------------------------------------------------------------

## 10. Autonomous Outcome Reliability

A useful north-star metric is **Autonomous Outcome Reliability (AOR)**:

> **The probability that SquadOps achieves a specified software outcome
> within required quality, cost, safety, and authority constraints
> without human intervention.**

This is stronger than simply counting autonomous runs.

A run is only an autonomous success if:

1.  the desired outcome was achieved;
2.  quality gates passed;
3.  required outcome scenarios passed;
4.  guardrails were respected;
5.  human intervention remained within the Campaign's autonomy
    threshold.

AOR can then be tracked by workload difficulty rather than collapsed
into a misleading single percentage.

------------------------------------------------------------------------

## 11. Quality-Adjusted Autonomous Output

The system ultimately needs to improve **quality and autonomy
simultaneously**.

Useful derived metrics might include:

-   verified outcomes per Campaign;
-   verified outcomes per dollar;
-   verified outcomes per hour;
-   verified outcomes per human intervention;
-   percentage of Cycles with positive measured outcome contribution;
-   autonomous recovery rate;
-   AOR by work-envelope class.

"Verified outcomes per human intervention" is useful while intervention
counts are nonzero, but becomes mathematically awkward as the system
approaches zero intervention. AOR is the more durable long-term metric.

The conceptual target remains:

``` text
                         PRODUCT QUALITY
                              ^
                              |
          Human-assisted      |      AUTONOMOUS
          excellence          |      EXCELLENCE
                              |
------------------------------+--------------------> AUTONOMY
                              |
          Poor + supervised   |      Autonomous
                              |      garbage
                              |
```

SquadOps should continuously move toward the upper-right quadrant.

------------------------------------------------------------------------

## 12. Ephemeral Outcome Evaluation Environment

Applications produced by SquadOps should be evaluated in an isolated,
reproducible runtime.

The existing Ephemeral Application Sandbox concept can evolve into an
**Outcome Evaluation Environment**.

Lifecycle:

``` text
Cycle completes
      |
      v
Build artifact
      |
      v
Launch isolated application sandbox
      |
      +---- deterministic verification
      |
      +---- Lighthouse / axe / local quality checks
      |
      +---- Brett-controlled browser outcome scenarios
      |
      +---- optional temporary HTTPS exposure
      |          |
      |          +---- external UX/design evaluator
      |          +---- cloud browser evaluator
      |
      v
Collect evaluation evidence
      |
      v
Score outcome contribution
      |
      v
Persist Campaign evidence
      |
      v
Destroy sandbox / tunnel
```

Most evaluation should remain local.

External exposure is needed only for cloud-based evaluators. When
required, the sandbox can be exposed temporarily through a short-lived
HTTPS tunnel.

External evaluation builds should contain:

-   no production credentials;
-   no personal data;
-   no reusable secrets;
-   no unrestricted access to the home/internal network;
-   synthetic evaluation data;
-   constrained network access.

The application itself should not need special evaluation awareness. The
Campaign infrastructure is responsible for launching, observing,
evaluating, and tearing it down.

------------------------------------------------------------------------

## 13. Example Campaign Scorecard

A Group Run Campaign might produce:

  Measure                            Baseline   Current      Target
  -------------------------------- ---------- --------- -----------
  Acceptance tests                        96%      100%        100%
  Independent outcome scenarios           68%       88%      \>=90%
  Lighthouse performance                   78        91       \>=85
  Lighthouse accessibility                 91        96       \>=90
  External UX score                        71        82       \>=80
  Autonomous recovery rate                35%       74%      \>=80%
  Human interventions / Campaign          5.2       1.8        \<=1
  Cost / verified outcome              \$4.80    \$3.20   \<=\$3.50
  AOR for target work class               47%       76%      \>=80%

The Campaign should not blindly optimize every number. Measures are
evidence against the desired outcome and guardrails.

------------------------------------------------------------------------

## 14. Outer-Loop Improvement

The outer loop should primarily ask:

> **What prevented SquadOps from achieving the desired outcome
> autonomously and at the required quality?**

Example output:

``` yaml
autonomy_constraint_report:
  campaign_outcome: partial_success

  product_quality:
    outcome_scenario_success: 0.91
    quality_gate_status: PASS

  autonomy:
    status: FAIL
    interventions: 3

  primary_constraint:
    verification_recovery

  evidence:
    - cycle_4_required_owner_unblock
    - cycle_7_required_owner_unblock

  root_cause:
    agent_recognized_failed_acceptance_criteria_but_could_not_replan

  recommended_experiment:
    allow_lead_to_generate_corrective_cycle_after_verification_failure

  expected_effect:
    reduce_verification_related_interventions

  confidence: 0.78
```

The next Cycle or Campaign improvement is then driven by evidence.

Over time, the desired progression is:

``` text
Owner -> Nostromo -> SquadOps

            becomes

Nostromo -> SquadOps

            becomes

SquadOps observes its performance
        -> identifies its constraint
        -> proposes an experiment
        -> executes an authorized improvement
        -> independently verifies the result
        -> retains the improvement if evidence supports it
```

Human control remains at policy, budget, security, authority, and
consequential decision boundaries.

------------------------------------------------------------------------

## 15. Proposed Campaign Design Principles

1.  **Campaigns commit to outcomes, not fixed plans.**
2.  **Cycles are hypotheses about the next best movement toward the
    Campaign outcome.**
3.  **Tasks create artifacts; artifacts are not themselves evidence of
    outcome achievement.**
4.  **Product quality and autonomy are measured independently.**
5.  **Autonomy gains count only when required product-quality gates
    pass.**
6.  **Independent outcome scenarios are stronger evidence than
    self-authored tests alone.**
7.  **No single evaluator owns the definition of quality.**
8.  **Every human intervention is telemetry about the current
    autonomous-work boundary.**
9.  **Evaluation results feed directly into selection of the next
    Cycle.**
10. **The outer loop exists to expand the Autonomous Work Envelope.**
11. **The ultimate objective is autonomous production of independently
    verified software outcomes.**

------------------------------------------------------------------------

## 16. Initial 2.x Experiment

The first Group Run Campaign can deliberately remain small.

### Campaign Outcome

> Iteratively improve Group Run through dynamically selected Cycles
> while demonstrating measurable improvement in both application quality
> and SquadOps autonomy.

### Baseline

Before the first improvement Cycle:

1.  run deterministic test suite;
2.  capture Lighthouse/axe results;
3.  execute a small Brett-owned outcome suite;
4.  perform an independent UX evaluation;
5.  record cost/time;
6.  record human interventions.

### Each Cycle

1.  identify the highest-value gap from current evidence;
2.  state the outcome hypothesis;
3.  execute the Cycle;
4.  launch the ephemeral evaluation environment;
5.  rerun the same independent quality suite;
6.  compare against baseline and previous Cycle;
7.  determine product outcome contribution;
8.  measure autonomy behavior;
9.  diagnose the dominant remaining constraint;
10. dynamically select the next Cycle.

### Success

The experiment succeeds if it demonstrates that:

-   Group Run objectively improves according to multiple independent
    signals;
-   SquadOps can make successive improvements with decreasing
    intervention;
-   quality does not degrade as autonomy increases;
-   Campaign evidence can explain *why* a subsequent Cycle was selected;
-   Nostromo can identify concrete SquadOps defects/enhancements from
    observed execution;
-   those improvements expand the measurable Autonomous Work Envelope.

------------------------------------------------------------------------

## North Star

The goal is not autonomous code generation.

It is:

> **Autonomous production, evaluation, and iterative improvement of
> independently verified software outcomes.**

That framing makes Campaigns the mechanism by which SquadOps learns not
merely to *do more work*, but to become progressively more competent at
achieving worthwhile software outcomes on its own.
