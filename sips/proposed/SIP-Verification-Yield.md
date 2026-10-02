---
sip_uid: '17909028044686722'
status: proposed
title: Verification Yield and Test Value
author: Backspring Labs / SquadOps
---
# SIP-XXXX: Verification Yield and Test Value

**Status:** Draft
**Revision:** 1
**Target:** TBD
**Authors:** Backspring Labs / SquadOps
**Theme:** Verification quality, test economics, agent efficiency

> **Placement, recorded 2026-10-01** at the owner's review of this draft against the 2.0 plan
> (`docs/plans/2-0-0-plan.md`). The body below is the draft as the owner wrote it.
>
> **Two test populations, with different owners and timing.** The draft speaks to both, and they land
> separately:
> 1. **Verification the squad writes inside cycles,** the qa and dev tests of a delivered app. This is
>    the half Campaign depends on.
> 2. **The framework's own suite,** written by the owner, frontier sessions and the Nostromo crew. This
>    is outer-loop work. `docs/TEST_QUALITY_STANDARD.md` already carries this SIP's plausible-fault rule
>    for it ("What bug would this catch?"), and its linter for anti-patterns 1–4 blocks the regression
>    suite. The audit, fault corpus and deletion experiment here extend that standard, rather than
>    restate it.
>
> **Ownership.** For the squad's tests, demonstrated discrimination (§7) is
> `SIP-Test-First-Verification.md`'s mechanism: a red gate against a contract-conforming stub. This SIP
> owns the principle, the measurement (the audit, the fault corpus, the detection matrix, cost) and its
> application to the framework's own suite. Checks against several of the anti-patterns in §39 already
> exist for the squad's tests, each built after a real failure:
> - a suite asserting its own mock (#915, #1126);
> - assertions contradicting declared types (#1153);
> - queries off the declared test anchors (#668);
> - additive-suite containment (#1022);
> - assertion strength (#999).
>
> **When each part lands:**
>
> | part | when |
> |---|---|
> | **each criterion an increment adds has a test that fails on its baseline for the intended reason** (demonstrated discrimination for brownfield cycles) | **before the first campaign**, as `SIP-Campaign-Orchestration.md` revision 3 §8.2 |
> | Test-First Verification's stub-based red gate, for greenfield cycles | after the first campaign: the calibration cycle is the yardstick, and changing its verification moves the baseline it exists to hold |
> | risk-first instructions for qa and builder, with "no new test is justified" a legal outcome (§19) | after the first campaign, as an outer-loop experiment read against the calibration cycle |
> | the test-value audit, fault corpus, detection matrix and deletion experiment on the framework's suite (§10–§28) | after, as Nostromo crew work. It suits crew local inference between cycles (§34). It is not commissioning work, because deletion decisions take judgement |
> | verification-cost reporting (§17–§18, §23) | after the first campaign, from the evidence package's cost data |

---

## 1. Abstract

SquadOps increasingly relies on agent-generated verification during implementation, repair, and acceptance. This improves consistency and repeatability, but it also creates a structural risk: agents can satisfy an implicit expectation to "write tests" by producing tests that are easy to generate, easy to satisfy, and unlikely to detect meaningful defects.

A test suite can therefore grow while its ability to discriminate between correct and incorrect implementations remains largely unchanged.

This SIP proposes **Verification Yield** as a first-class concept in SquadOps.

The central rule is:

> Verification should be justified by the defects it can detect, not by the amount of code it exercises.

SquadOps should stop treating test creation as an automatic consequence of implementation change. Instead, verification should begin with risks, invariants, contracts, and plausible incorrect behaviors. Tests become one possible mechanism for proving those properties.

The SIP introduces:

- a formal definition of **test value**;
- a **Test Value Audit** process for existing suites;
- mutation- and fault-seeding experiments to measure actual defect-detection capability;
- a **plausible-fault requirement** for newly proposed tests;
- a distinction between verification evidence and test quantity;
- support for project-specific fault models derived from real SquadOps failures;
- duplicate-verification and low-yield test detection;
- metrics for verification yield, redundancy, and cost;
- guidance for selectively deleting tests whose maintenance and generation cost exceeds their contribution to defect detection;
- integration with Verification Contracts and acceptance evidence;
- a path toward local-model-assisted verification triage to reduce cloud-token consumption.

This SIP does not propose indiscriminate test deletion.

It proposes replacing an implicit objective—

> maximize tests and coverage

—with a stronger objective—

> maximize confidence gained per unit of verification effort.

---

# 2. Motivation

## 2.1 The problem

Agentic software development changes the economics of testing.

A human engineer pays an obvious cost to write a low-value test. An agent can generate one rapidly, making the immediate cost appear negligible.

That cost is not actually zero.

Every generated test introduces some combination of:

- inference tokens;
- implementation time;
- review burden;
- execution time;
- repository size;
- maintenance burden;
- future context-window consumption;
- false confidence;
- coupling to implementation details;
- repair work when harmless refactoring changes behavior irrelevant to the product contract.

The result can be a large verification surface whose informational value is much smaller than its physical size.

SquadOps needs a way to distinguish:

> a test exists

from:

> a test provides useful evidence.

---

## 2.2 The characteristic failure mode

A particularly dangerous verification failure is not a failing test.

It is a test suite that passes regardless of whether an important behavior is correct.

Examples include tests that:

- assert mocked dependencies were called exactly as arranged;
- reproduce implementation structure rather than expected behavior;
- validate trivial object construction;
- assert a method returns a value supplied by its mock;
- verify getters and setters without meaningful invariants;
- cover a happy path already exercised by stronger integration verification;
- use mocks so extensively that the actual boundary behavior is never exercised;
- prove that the test fixture works rather than that the product works;
- assert internal method call order with no externally observable consequence;
- duplicate behavior already protected by another test;
- exercise code paths without making assertions capable of distinguishing meaningful faults.

Such tests may increase line coverage while contributing little additional fault detection.

---

## 2.3 Why this matters specifically to SquadOps

SquadOps is not merely executing a conventional engineering workflow faster.

It is building a system in which agents generate, evaluate, repair, and verify software.

That makes verification policy part of the behavior of the platform itself.

If agents learn an implicit rule such as:

> changed code requires additional tests

they will optimize toward satisfying that visible requirement.

If instead they are required to answer:

> what plausible incorrect implementation does this verification distinguish from the correct one?

then the optimization target changes.

That distinction matters both for correctness and for token economics.

---

# 3. Goals

This SIP proposes mechanisms to:

1. Measure whether SquadOps tests detect meaningful defects.
2. Identify tests with little or no incremental verification value.
3. Reduce unnecessary test generation.
4. Prefer verification tied to explicit risk, invariant, contract, or historical defect.
5. Measure verification effectiveness independently of code coverage.
6. Improve the quality of acceptance evidence.
7. Reduce token expenditure on low-yield test creation and maintenance.
8. Create feedback loops that help agents learn which forms of verification are valuable.
9. Encourage stronger integration, contract, state-machine, property, and regression verification where appropriate.
10. Make selective test deletion a supported engineering activity when evidence demonstrates redundancy or negligible value.

---

# 4. Non-Goals

This SIP does not:

- establish a universal desired test-count reduction;
- declare unit testing ineffective;
- require mutation testing on every commit;
- replace all tests with integration tests;
- prescribe one testing framework;
- optimize primarily for test execution speed;
- eliminate code coverage reporting;
- require every test to detect a unique fault;
- mandate deletion merely because a test is simple;
- claim that a passing mutation score alone proves software correctness.

The purpose is not "fewer tests."

The purpose is:

> higher-yield verification.

---

# 5. Core Concept: Verification Yield

## 5.1 Definition

**Verification Yield** measures the useful fault-detection confidence produced by a verification activity relative to its cost.

Conceptually:

**Verification Yield = meaningful defect-detection value / verification cost**

This SIP intentionally avoids prescribing a single numerical equation in the initial implementation.

The model should initially use several observable dimensions rather than collapse them prematurely into one score.

---

## 5.2 Verification value dimensions

Useful verification may provide value by protecting:

- an externally observable behavior;
- a Verification Contract;
- a domain invariant;
- a state-transition rule;
- a component boundary;
- a serialization or protocol contract;
- failure handling;
- ordering guarantees;
- concurrency behavior;
- persistence semantics;
- artifact identity;
- evidence provenance;
- security properties;
- authorization or authentication policy;
- recovery behavior;
- previously observed regressions.

A verification mechanism need not cover many of these.

It should normally cover at least one meaningful one.

---

# 6. The Plausible Fault Principle

Every non-trivial newly proposed automated test SHOULD be associated with at least one **plausible fault**.

A plausible fault is a realistic incorrect implementation or system state that the test is expected to reject.

The question is:

> What could the product plausibly do wrong that would cause this test to fail?

Acceptable answers might include:

- accept evidence for the wrong candidate tree;
- transition directly from READY to CRASHED without required intermediate handling;
- apply a repair to an obsolete artifact;
- treat stale facts as current after retry;
- publish an event before persistence commits;
- classify a failed acceptance check as passing;
- omit required provenance from verification evidence;
- bind verification output to the wrong execution slot;
- replay an event twice;
- silently accept malformed protocol input.

Weak answers include:

- coverage would decrease;
- the method changed;
- the implementation is different;
- the mock was not called;
- the line did not execute.

Those may occasionally matter, but they are not sufficient justification by themselves.

---

# 7. Stronger Rule: Demonstrated Discrimination

Where practical, a verification mechanism SHOULD demonstrate that it can distinguish:

1. the intended implementation; and
2. at least one plausible incorrect implementation.

This can be demonstrated through:

- red-before-green development;
- a seeded mutation;
- replaying an actual historical defect;
- intentionally violating an invariant;
- injecting incorrect boundary output;
- replacing an accepted artifact with a stale or incorrect one;
- disrupting event ordering;
- corrupting evidence metadata;
- simulating a failure path.

The important property is not the technique.

It is discrimination.

> Evidence is stronger when SquadOps can show that the verifier rejects something meaningfully wrong.

---

# 8. Verification Is Broader Than Tests

This SIP intentionally uses the term **verification mechanism**.

A conventional test is one mechanism.

Others may include:

- Verification Contracts;
- runtime assertions;
- schema validation;
- deterministic replay;
- static analysis;
- type checking;
- property checks;
- invariant monitors;
- protocol validators;
- model checking;
- fuzzing;
- acceptance probes;
- sandbox execution;
- artifact comparison;
- state-machine validation;
- runtime evidence inspection.

An implementation change SHOULD trigger the question:

> What evidence is required?

not automatically:

> What test should be added?

---

# 9. Proposed Verification Hierarchy

SquadOps SHOULD preferentially invest verification effort according to the consequences and architecture of the changed behavior.

A default ordering is:

## Tier A — Contract and invariant verification

Examples:

- Verification Contracts;
- acceptance requirements;
- domain invariants;
- protocol contracts;
- state-machine rules;
- artifact identity guarantees;
- security constraints.

These usually have the highest leverage because they correspond directly to intended system behavior.

---

## Tier B — Boundary and integration verification

Examples:

- persistence boundaries;
- RabbitMQ event flow;
- service/API contracts;
- artifact handoff;
- candidate-tree handling;
- producer/consumer sequencing;
- replay behavior;
- process or container boundaries.

These SHOULD be favored when failure is likely to occur in interaction between otherwise correct components.

---

## Tier C — Regression verification

A test reproducing a real previously observed failure is presumptively valuable.

Its causal connection to a defect is already known.

Regression verification SHOULD include sufficient information to explain:

- what failed;
- why the verification catches it;
- whether stronger verification now subsumes it.

---

## Tier D — Property and state-space verification

Useful for logic involving:

- many possible inputs;
- state transitions;
- serialization;
- ordering;
- idempotence;
- retry behavior;
- deterministic binding;
- transformations with strong invariants.

---

## Tier E — Targeted unit verification

Unit tests remain valuable where deterministic local logic contains meaningful branching or complexity.

Examples:

- ranking logic;
- planners;
- parsers;
- reducers;
- schedulers;
- transition logic;
- scoring;
- transformation algorithms.

Unit tests are not disfavored.

**Trivial unit tests are.**

---

## Tier F — Implementation mirroring

Verification primarily coupled to internal structure SHOULD receive the lowest default priority.

Examples:

- exact mock call choreography;
- private helper invocation order;
- trivial constructors;
- trivial property access;
- passthrough methods;
- assertions that repeat constants already enforced elsewhere.

These tests MAY exist when their specific value can be articulated.

They SHOULD NOT be produced by default.

---

# 10. Test Value Audit

SquadOps SHOULD introduce a repeatable **Test Value Audit**.

The audit can be performed:

- repository-wide;
- against a selected subsystem;
- against tests added over a defined release interval;
- against verification created by a particular campaign;
- against tests produced by a specific agent or model.

---

## 10.1 Audit questions

For every selected test or verification unit, determine:

1. **What behavior is protected?**
2. **What plausible fault would cause this to fail?**
3. **Has that fault ever occurred or is there architectural reason to expect it?**
4. **Is the behavior externally meaningful?**
5. **Is the same fault already detected elsewhere?**
6. **Does the test depend heavily on implementation structure?**
7. **Would harmless refactoring cause it to fail?**
8. **Does this test exercise real boundaries or mocked representations of them?**
9. **Can a mutation demonstrate its discriminatory value?**
10. **What would be lost if the test were deleted?**

---

# 11. Audit Classification

The initial audit SHOULD classify tests into categories such as:

### High Value

Clearly detects meaningful faults or protects critical contracts/invariants.

### Supporting Value

Provides useful defense in depth but substantially overlaps other verification.

### Specialized Value

Covers a narrow but justified condition unlikely to be exercised elsewhere.

### Redundant

The meaningful behavior is already covered adequately by stronger verification.

### Implementation-Coupled

Primarily asserts internal implementation structure rather than externally relevant behavior.

### Low Discrimination

Passes under plausible incorrect implementations.

### Unknown

Value cannot be determined without additional experiment.

These are diagnostic categories, not automatic deletion decisions.

---

# 12. Mutation-Based Validation

## 12.1 Purpose

Mutation testing provides one method for determining whether tests can distinguish correct code from incorrect code.

The experiment alters implementation behavior intentionally and observes which verification mechanisms fail.

---

## 12.2 Generic mutations

Useful generic mutations include:

- invert a conditional;
- change equality to inequality;
- remove validation;
- skip an exception;
- remove a state update;
- change a return value;
- alter a boundary constant;
- remove an event emission;
- reorder two operations;
- suppress persistence;
- return stale data;
- execute an operation twice.

Generic mutation testing can provide broad signals.

It is not sufficient by itself.

---

# 13. SquadOps-Specific Fault Injection

SquadOps SHOULD develop a curated fault corpus representing realistic platform failures.

This is expected to provide more value than relying only on language-level mutation operators.

Candidate examples include:

### Artifact faults

- wrong candidate tree;
- stale candidate tree;
- evidence references predecessor artifact;
- repaired output not reflected in accepted artifact;
- accepted artifact differs from verified artifact.

### Verification faults

- failed acceptance check reported as pass;
- verification omitted;
- stale verification reused;
- verifier runs against incorrect revision;
- incomplete evidence incorrectly marked sufficient.

### Execution faults

- prohibited FSM transition;
- duplicate transition;
- terminal state skipped;
- retry begins from stale context;
- duty/cycle state leaks between runs.

### Event faults

- event not emitted;
- event emitted twice;
- ordering reversed;
- incorrect correlation identifier;
- event emitted before durable state update.

### Binding faults

- output assigned to wrong slot;
- slot evidence associated with wrong producer;
- deterministic binding replaced by ambiguous inference;
- producer/repairer identity confused.

### Replay faults

- replay diverges from recorded execution;
- event omitted during reconstruction;
- duplicate event applied;
- original artifact identity lost.

### Integration faults

- mocked behavior differs from real adapter behavior;
- serialization mismatch;
- process boundary drops required metadata;
- sandbox and host behavior diverge.

The fault corpus SHOULD evolve from actual SquadOps failures.

---

# 14. Verification Fault Corpus

The curated set of realistic injected faults SHOULD become a versioned **Verification Fault Corpus**.

Each fault SHOULD record:

- identifier;
- category;
- description;
- affected architectural property;
- minimal reproduction;
- expected verification mechanisms;
- historical provenance if applicable;
- severity;
- whether it represents an observed or synthetic failure.

This corpus becomes a reusable benchmark.

---

# 15. Measuring Fault Detection

For a chosen suite and fault corpus, SquadOps can build a matrix:

| Fault | Test A | Test B | Test C | Contract V | Integration V |
|---|---|---|---|---|---|
| Wrong artifact identity | fail | pass | pass | fail | fail |
| Missing event | pass | pass | pass | pass | fail |
| Illegal FSM transition | pass | fail | pass | fail | pass |

This reveals:

- which faults are detected;
- which are completely unprotected;
- which tests duplicate one another;
- which tests uniquely detect faults;
- which verification forms provide the greatest leverage.

---

# 16. Unique Detection Value

A useful concept is **unique detection value**.

If twenty tests all detect the same fault and one stronger integration test detects it as well, all twenty are not necessarily worthless.

But their incremental contribution may be small.

The audit SHOULD distinguish:

- **total detection** — faults a test catches;
- **unique detection** — faults only that test catches;
- **shared detection** — faults also caught elsewhere.

This creates the ability to reason about redundancy without assuming redundancy is always bad.

---

# 17. Verification Cost

Verification value should be evaluated alongside cost.

Relevant costs include:

- generation tokens;
- review tokens;
- test implementation time;
- fixture complexity;
- execution time;
- cloud inference cost;
- local inference cost;
- maintenance frequency;
- flakiness;
- debugging burden;
- context-window footprint;
- infrastructure dependency;
- environmental setup.

Initially these costs MAY be approximated rather than measured exactly.

The important change is acknowledging them.

---

# 18. Token Economics

Agent-generated verification has a specific cost profile.

A test may consume tokens during:

1. initial code analysis;
2. test generation;
3. test execution diagnosis;
4. repair of failing test;
5. review;
6. future context loading;
7. future refactoring;
8. repeated maintenance.

A low-value test can therefore continue consuming tokens long after its creation.

SquadOps SHOULD eventually be able to report:

- tokens spent producing verification;
- tokens spent repairing verification;
- tests created;
- tests removed;
- fault-detection contribution;
- verification yield by agent/model;
- verification yield by test category.

---

# 19. Proposed New-Agent Rule

Agent instructions SHOULD move away from:

> Add tests for the changed code.

Toward:

> Identify the risks, contracts, invariants, and plausible incorrect behaviors introduced or affected by the change. Add or modify the minimum verification required to distinguish those failures from correct behavior.

The agent SHOULD be permitted to conclude:

> No additional automated test is justified.

That outcome should not itself be considered incomplete work.

---

# 20. Verification Justification

When an agent proposes new verification, it SHOULD provide concise justification containing:

- behavior protected;
- plausible fault;
- verification mechanism selected;
- why existing verification is insufficient.

Example:

> Protects accepted-artifact identity. A repair can produce artifact B while acceptance evidence remains attached to artifact A. Existing producer unit tests do not cross the acceptance boundary. Add one integration verification ensuring accepted evidence resolves to the exact repaired artifact.

This is much stronger than:

> Added tests for artifact handling.

---

# 21. No Automatic Test Quota

SquadOps SHOULD NOT enforce implicit or explicit rules such as:

- every implementation change requires a test;
- every new class requires a test file;
- every public method requires unit coverage;
- every changed line must increase coverage;
- every repair requires additional test count.

Requirements SHOULD instead be tied to meaningful verification evidence.

---

# 22. Coverage

Code coverage remains useful as a diagnostic.

It SHOULD NOT be treated as a primary quality measure.

Coverage answers:

> Was this code executed?

It does not answer:

> Would the verifier detect incorrect behavior?

A suite may exhibit high coverage with low fault discrimination.

Coverage SHOULD therefore be interpreted alongside verification yield.

---

# 23. Proposed Metrics

Initial metrics MAY include:

### Mutation Kill Rate

Percentage of injected faults rejected by the verification suite.

### Realistic Fault Kill Rate

Percentage of the SquadOps-specific fault corpus rejected.

### Verification Gap Rate

Percentage of important seeded faults detected by no verification mechanism.

### Redundancy Ratio

Degree to which multiple tests detect identical fault sets.

### Unique Detection Count

Number of faults for which a verifier contributes unique detection.

### Verification Maintenance Cost

Observed modification frequency and token/time cost associated with keeping verification valid.

### Verification Yield

Fault-detection contribution relative to verification cost.

### Low-Value Test Rate

Percentage of audited tests classified as low-discrimination, implementation-coupled, or unjustified redundancy.

---

# 24. No Single Score Initially

This SIP explicitly recommends against immediately reducing verification quality to one number.

A composite score introduced too early will become an optimization target.

Agents could then learn to optimize the metric rather than actual verification quality.

The initial platform SHOULD expose multiple dimensions.

A composite measure MAY be introduced only after sufficient empirical experience.

---

# 25. Deletion as a Supported Verification Action

Removing tests SHOULD become a legitimate outcome of verification work.

A test MAY be considered for deletion when:

- it detects no meaningful seeded faults;
- stronger verification fully subsumes its behavior;
- it exists primarily to mirror implementation;
- it repeatedly breaks during harmless refactoring;
- its maintenance cost materially exceeds its incremental value;
- it provides no contract, regression, invariant, or boundary protection.

Deletion SHOULD be evidence-based.

---

# 26. Safety Rule for Test Deletion

Before deleting a non-trivial test, SquadOps SHOULD answer:

1. What behavior did this test claim to protect?
2. What fault was it expected to detect?
3. Is that fault protected elsewhere?
4. Has mutation/fault injection demonstrated redundancy where practical?
5. Does removal create an unverified Verification Contract or acceptance condition?

This prevents "test reduction" from becoming an optimization objective independent of correctness.

---

# 27. The Verification Value Experiment

Before changing repository-wide policy, SquadOps SHOULD run a bounded experiment.

Suggested scope:

- one representative subsystem; or
- tests introduced across approximately 20–30 recent implementation PRs; or
- one release line containing both feature and repair work.

---

## 27.1 Baseline

Record:

- number of tests;
- test execution time;
- test LOC;
- coverage;
- recent test-maintenance activity;
- approximate generation/review cost;
- existing Verification Contracts relevant to the selected code.

---

## 27.2 Create fault corpus

Construct a representative set of:

- generic mutations;
- known historical defects;
- architecture-specific injected faults.

Include both easy and difficult failures.

---

## 27.3 Run full verification

Determine which verification mechanisms detect which faults.

Record the detection matrix.

---

## 27.4 Identify low-yield verification

Classify tests using the Test Value Audit.

Candidate low-yield groups should be identified without immediately deleting them.

---

## 27.5 Remove progressively

Create experimental suite variants such as:

- baseline;
- remove clear implementation-mirroring tests;
- remove fully redundant low-value tests;
- retain only stronger verification for selected behaviors.

For each variant, rerun the fault corpus.

---

## 27.6 Evaluate hypothesis

Primary hypothesis:

> A meaningful percentage of the current SquadOps test suite can be removed without materially reducing detection of realistic defects.

Possible outcomes include:

### Hypothesis strongly supported

Large test reduction produces negligible fault-detection loss.

### Hypothesis partially supported

Certain categories are low-value while others provide significant defense in depth.

### Hypothesis rejected

Apparently redundant tests detect faults not captured by stronger verification.

All three outcomes are useful.

---

# 28. Experimental Success Criteria

The experiment SHOULD NOT define success solely as test deletion.

Success is learning whether verification resources are well allocated.

Possible indicators:

- realistic fault detection maintained while test count decreases;
- previously unknown verification gaps discovered;
- integration verification detects faults unit tests miss;
- certain unit tests demonstrate unexpectedly high unique value;
- token expenditure decreases without lowering defect detection;
- acceptance failures become better correlated with real system failures.

---

# 29. Integration With Verification Contracts

Verification Contracts provide a natural anchor for this model.

A Verification Contract describes required behavior.

Verification mechanisms provide evidence that the contract holds.

Tests should therefore be traceable, where appropriate, to:

- a Verification Contract;
- an invariant;
- an acceptance criterion;
- a recorded regression;
- a documented risk.

This provides stronger semantics than associating tests merely with source files.

---

# 30. Verification Evidence Model

Future verification evidence SHOULD be able to express:

- property verified;
- verification mechanism;
- candidate artifact/revision;
- fault class protected;
- result;
- provenance;
- whether the mechanism has demonstrated fault discrimination;
- Verification Contract reference where applicable.

This SIP does not mandate immediate schema changes.

It establishes the conceptual direction.

---

# 31. Acceptance Evidence

Acceptance SHOULD value evidence based on relevance rather than volume.

Ten trivial passing tests should not outweigh one failing contract-level check.

Likewise:

> 347 tests passed

is weaker evidence than:

> All required verification contracts passed against the accepted candidate, including artifact identity, retry freshness, event ordering, and FSM validity.

Test counts MAY still be displayed.

They SHOULD NOT be treated as primary acceptance evidence.

---

# 32. Relationship to Repairs

Repairs are especially well suited to high-value regression verification because the defect is already known.

For a repair, SquadOps SHOULD prefer a verifier capable of rejecting the known bad behavior before accepting the repair.

Where practical:

1. replay the failing behavior;
2. prove verification rejects it;
3. apply repair;
4. prove verification accepts corrected behavior.

This creates strong defect-specific evidence.

---

# 33. Relationship to Replay

Cycle Replay and deterministic replay mechanisms create opportunities to verify actual execution behavior rather than synthetic unit arrangements.

Historical cycles can potentially become part of the fault and regression corpus.

A failure that occurred during a real cycle can be replayed to test whether present verification would detect it.

This is expected to be especially useful for:

- event ordering;
- state transitions;
- candidate identity;
- retry behavior;
- evidence propagation.

---

# 34. Local-Model Role

Test-value classification is a good candidate for local inference.

A local model can perform first-pass analysis such as:

- summarize what each test asserts;
- identify likely protected behavior;
- propose plausible faults;
- flag implementation coupling;
- detect likely duplicate verification;
- cluster tests by protected behavior;
- classify candidates for mutation testing;
- identify tests with no obvious externally meaningful assertion.

This analysis can occur before consuming cloud-model tokens.

Cloud models can then focus on:

- ambiguous cases;
- architectural interpretation;
- safety-critical verification;
- Verification Contract reasoning;
- deletion decisions with broad consequences.

---

# 35. Harness Implications

Agent harnesses SHOULD eventually expose verification intent separately from test generation.

A builder might emit:

### Risk

Retry can reuse stale evidence.

### Required property

Each retry must bind verification to the newly produced candidate.

### Existing verification

None crosses the retry-to-acceptance boundary.

### Proposed mechanism

Integration verification with intentionally stale evidence.

This structure gives reviewers something meaningful to challenge.

---

# 36. Reviewer Role

Reviewers SHOULD evaluate verification by asking:

- Does the verifier meaningfully distinguish wrong from right?
- Is this already protected?
- Is the chosen abstraction level appropriate?
- Are mocks hiding the actual risk?
- Is there a stronger existing verification mechanism?
- Is an integration check more appropriate than several unit tests?
- What failure would escape all current verification?

The reviewer SHOULD be empowered to reject useless tests even if they increase coverage.

---

# 37. QA Role

QA SHOULD focus increasingly on verification gaps rather than test quantity.

Useful QA outputs include:

- uncovered risk;
- unprotected invariant;
- undetected seeded fault;
- inconsistent verification behavior;
- redundant suite segment;
- verifier that passes both correct and incorrect implementations.

A QA finding such as:

> this test does not fail when artifact identity is intentionally corrupted

is highly actionable.

---

# 38. Builder Role

Builders SHOULD not be rewarded for producing many tests.

Builder completion criteria SHOULD instead include:

- identified risks are verified;
- required contracts have evidence;
- historical defect is demonstrably prevented where applicable;
- verification is sufficient for reviewer and QA acceptance.

---

# 39. Anti-Patterns

SquadOps SHOULD explicitly recognize these verification anti-patterns:

### Mock Echo

The assertion simply confirms values configured in mocks.

### Implementation Shadow

The test reproduces the implementation's own structure.

### Constructor Ceremony

Testing object creation with no meaningful invariant.

### Getter Proof

Testing trivial accessors with no domain semantics.

### Coverage Padding

Creating cases primarily to execute lines.

### Duplicate Happy Path

Adding another test for behavior already strongly protected.

### Call-Count Fetish

Asserting exact interaction counts where externally observable behavior does not depend on them.

### Mocked Integration

Claiming to verify a boundary while replacing both sides with mocks.

### Snapshot Without Semantics

Large snapshot assertions that fail frequently but do not encode meaningful requirements.

### Always-Green Verifier

A verifier that survives realistic incorrect implementations.

---

# 40. Test Debt Versus Test Assets

Tests should not automatically be treated as assets.

A test can be:

- an asset;
- neutral;
- debt.

A high-value regression test is an asset.

A heavily mocked test coupled to internal call structure may be debt.

This distinction matters for agentic repositories because automatic generation can produce verification debt faster than humans notice it.

---

# 41. Verification Portfolio

The suite SHOULD be viewed as a portfolio of verification mechanisms.

The objective is not to maximize the number of portfolio items.

The objective is to achieve strong coverage of important failure classes with acceptable cost and redundancy.

This enables deliberate tradeoffs such as:

- replacing six brittle unit tests with one strong boundary verification;
- retaining several redundant security checks intentionally;
- preserving a cheap unit test even when an integration test also exists;
- deleting expensive verification whose only detected faults are protected elsewhere.

---

# 42. Risk Weighting

Not all faults deserve equal weight.

Later iterations MAY weight fault classes according to:

- severity;
- likelihood;
- recoverability;
- customer impact;
- security impact;
- architectural centrality;
- historical frequency.

A verification mechanism protecting a catastrophic invariant may justify significant redundancy.

A verifier protecting trivial formatting may not.

---

# 43. Verification Gaps Are First-Class Findings

The most valuable output of mutation/fault experiments may not be low-value tests.

It may be discovering faults that **no test catches**.

These gaps SHOULD become first-class backlog items.

Example:

> None of 312 tests fail when accepted evidence is rebound to the predecessor artifact.

That is much more important than whether coverage is 94% or 96%.

---

# 44. Proposed Initial Deliverables

A first implementation of this SIP SHOULD produce:

1. Test Value Audit format.
2. Small SquadOps-specific fault corpus.
3. Mutation/fault execution mechanism.
4. Detection matrix.
5. Test classifications.
6. Baseline verification-cost estimates.
7. Experimental reduced-suite branches or configurations.
8. Comparison report.
9. Recommended agent instruction changes.
10. Candidate follow-on work for automation.

---

# 45. Suggested Phase Structure

## Phase 1 — Measure

Do not change test policy yet.

- select subsystem;
- audit current suite;
- create fault corpus;
- run experiments;
- classify verification.

Deliver evidence.

---

## Phase 2 — Compare

Create alternate suite configurations.

Measure:

- fault detection;
- execution cost;
- maintenance implications;
- coverage differences;
- token implications.

Determine whether low-yield tests can be removed safely.

---

## Phase 3 — Change Agent Behavior

Update builder/reviewer/QA instructions to require risk-driven verification.

Introduce plausible-fault justification.

Remove automatic expectations for test creation where not meaningful.

---

## Phase 4 — Automate

Automate:

- test classification;
- mutation execution;
- fault matrix generation;
- verification-gap detection;
- redundancy analysis;
- verification-yield reporting.

Prefer local models for inexpensive classification.

---

# 46. Proposed Experiment Record

Each experiment SHOULD preserve a record similar to:

## Scope

Subsystem/release/campaign examined.

## Baseline

Tests, coverage, runtime, approximate verification cost.

## Fault Corpus

Injected faults and why they are representative.

## Detection Matrix

Verification mechanisms versus faults.

## Findings

High-value, redundant, low-discrimination, and missing verification.

## Reduced Suite

Tests removed or disabled experimentally.

## Result

Change in:

- realistic fault detection;
- generic mutation detection;
- runtime;
- test count;
- estimated generation/maintenance burden.

## Decision

Policy changes supported by evidence.

---

# 47. Example Decision

Suppose an experiment finds:

- 420 tests;
- 37 representative faults;
- 33 faults detected by baseline;
- 110 tests classified as implementation-coupled;
- 86 of those detect no fault not already detected elsewhere.

After removing those 86 tests:

- 334 tests remain;
- the same 33 faults are detected;
- execution time declines;
- coverage falls slightly;
- no Verification Contract loses evidence.

The appropriate conclusion is not:

> 20% of tests are useless everywhere.

It is:

> For this subsystem, the removed tests provided no observed incremental detection against the measured fault model.

That distinction should be maintained throughout the initiative.

---

# 48. Counterexample

Suppose another experiment finds that apparently trivial unit tests uniquely detect subtle parsing faults not exercised by integration tests.

Those tests should remain.

The methodology must be capable of proving the user's initial suspicion wrong.

Otherwise it is not a valid experiment.

---

# 49. Guard Against Metric Gaming

Once verification yield becomes visible, agents may optimize against it.

Potential failure modes include:

- writing tests designed specifically to kill generated mutations;
- avoiding important tests because they lack unique detection;
- deleting useful redundancy;
- generating unrealistic faults that make a suite appear strong;
- preferring cheap verification while ignoring high-impact risks.

Therefore:

- realistic fault corpus quality matters;
- fault severity must eventually be considered;
- human/reviewer judgment remains relevant;
- no single metric should become a hard gate initially.

---

# 50. Architectural Principle

The deeper architectural principle is:

> Verification should be attached to meaning, not implementation volume.

Source code is an implementation artifact.

Contracts, invariants, risks, and observable behaviors are semantic artifacts.

SquadOps should increasingly organize verification around the latter.

---

# 51. Expected Token Impact

If the hypothesis is correct, token savings should arise from several places:

- fewer unnecessary tests generated;
- less fixture creation;
- fewer brittle tests repaired during refactors;
- smaller test context supplied to agents;
- less review of low-value code;
- fewer false failures;
- reduced cloud-model verification work;
- more triage performed locally.

The savings SHOULD be measured rather than assumed.

---

# 52. Expected Quality Impact

Potential quality improvements include:

- stronger alignment between verification and architecture;
- more meaningful acceptance evidence;
- discovery of currently invisible verification gaps;
- fewer false assurances from passing test suites;
- better regression protection;
- more purposeful integration testing;
- improved QA reasoning;
- better distinction between implementation correctness and contract correctness.

---

# 53. Risks

## 53.1 Over-deleting tests

Poor fault models may make valuable tests appear redundant.

**Mitigation:** experimental removal before permanent deletion.

---

## 53.2 Mutation-score fixation

Mutation scores can become another vanity metric.

**Mitigation:** distinguish generic mutation kill rate from realistic fault kill rate.

---

## 53.3 Expensive experiments

Large-scale mutation testing may consume significant compute.

**Mitigation:** sample representative areas and prioritize targeted fault injection.

---

## 53.4 Incomplete fault corpus

Unknown failures will always exist.

**Mitigation:** continuously incorporate real regressions into the corpus.

---

## 53.5 Excess ceremony

Requiring verbose justification for every trivial test could itself waste tokens.

**Mitigation:** justification should be short and machine-readable where possible.

---

# 54. Decision Rules

The following rules are proposed as long-term defaults:

1. **Do not create tests merely because code changed.**
2. **Start verification from risk, contract, invariant, or plausible fault.**
3. **Prefer the minimum verification set that provides sufficient confidence.**
4. **Favor externally meaningful behavior over implementation structure.**
5. **Demonstrate fault discrimination where practical.**
6. **Treat uncovered realistic faults as more important than raw coverage gaps.**
7. **Permit deletion when evidence shows negligible incremental value.**
8. **Preserve intentional redundancy for high-impact properties.**
9. **Measure verification cost as well as verification volume.**
10. **Use local models for mechanical verification triage where effective.**

---

# 55. Acceptance Criteria for This SIP

This SIP is considered successfully implemented when SquadOps can demonstrate at least one representative experiment in which:

1. a defined test population is audited;
2. a representative fault corpus is created;
3. verification mechanisms are executed against that corpus;
4. a fault-detection matrix is produced;
5. low-value and high-value verification are distinguished;
6. at least one verification gap is explicitly assessed;
7. reduced-suite behavior is compared to baseline;
8. resulting agent verification guidance is updated based on empirical evidence;
9. token or engineering-cost implications are estimated;
10. the result can support either retaining or removing tests based on measured value rather than intuition.

---

# 56. Follow-On Opportunities

Likely follow-on work includes:

- verification-yield telemetry;
- Continuum visualization of verification coverage by fault class;
- mapping Verification Contracts to evidence and fault classes;
- agent-specific verification-quality scorecards;
- historical regression corpus generation from cycle replay;
- local-model test-value reviewer;
- automated redundant-test detection;
- risk-weighted verification yield;
- campaign experiments comparing test-generation strategies;
- repository-level "verification portfolio" visualization.

These SHOULD remain follow-on work until the basic hypothesis is empirically tested.

---

# 57. Open Questions

1. What subsystem should serve as the first experimental target?
2. Should the first corpus be manually curated or partially derived from historical defects?
3. Which mutation framework is appropriate for the dominant SquadOps implementation language?
4. How much redundancy should be preserved intentionally?
5. Should fault-class metadata eventually be stored alongside tests?
6. Should Verification Contracts explicitly enumerate plausible failure modes?
7. At what point should verification cost become part of campaign optimization?
8. Should mutation/fault experiments run periodically rather than continuously?
9. Can historical cycle replay automatically generate regression candidates?
10. Should the Continuum console eventually expose verification yield as a dedicated perspective?

---

# 58. Final Principle

SquadOps should not ask:

> How many tests did the agents write?

It should ask:

> What important incorrect systems would this verification prevent us from accepting?

A passing test has value only to the extent that its failure means something.

The long-term goal is therefore not a smaller test suite.

It is a verification system in which every significant unit of verification has an understandable reason to exist, the platform knows what kinds of defects it can detect, and agent effort is concentrated on evidence that meaningfully separates correct software from plausible incorrect software.

**Tests are not the product of verification.**

**Confidence is.**
