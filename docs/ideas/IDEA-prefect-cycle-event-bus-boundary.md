# IDEA: Prefect Execution Boundary vs Cycle Event Bus Orchestration Boundary

## Status
Draft

## Type
Architecture / Platform Orchestration

## Summary
As SquadOps evolves its orchestration and recovery behavior around a Cycle Event Bus, there is a design risk that the platform may accidentally underuse Prefect as an execution engine while simultaneously rebuilding task execution, retry, and recovery mechanics in the SquadOps orchestration layer.

This IDEA defines a clean division of expertise:

- **Prefect owns execution mechanics and workload topology**
- **SquadOps owns domain interpretation, cross-workload coordination, and recovery strategy**
- **Tasks and workloads act as the translation layer by surfacing structured outcomes rather than raw failure noise**

The goal is to preserve Prefect's value as the runtime substrate without pushing SquadOps domain knowledge into Prefect, and without recreating a shadow workflow engine inside Cycle Event Bus handlers.

---

## Problem Statement
As orchestration logic moves into Cycle Event Bus handlers, there is a growing concern that:

1. **Prefect could be reduced to a glorified execution log**
   - Tasks run under Prefect, but meaningful recovery and control logic begins happening elsewhere.
   - Prefect stops being the authoritative owner of execution semantics.

2. **Cycle Event Bus handlers could become a second orchestrator**
   - Handlers begin deciding retries, compensation, resume behavior, or task re-execution.
   - SquadOps starts reimplementing stateful task runtime behavior that Prefect already provides.

3. **Prefect does not and should not carry deep domain expertise**
   - Prefect can retry, time out, and manage state, but it should not be asked to determine whether a failure means repair, rewind, re-plan, or escalation.

The design challenge is to navigate the seam between:

- avoiding domain-heavy logic inside Prefect
- avoiding mechanical workflow reimplementation inside SquadOps

That seam must be made explicit.

---

## Core Insight
The boundary is not:

- "Prefect handles everything" or
- "SquadOps handles everything"

The boundary is:

- **Prefect manages attempts**
- **SquadOps manages intent**
- **Tasks make outcomes legible**

This is the critical architectural division of expertise.

---

## Design Principles

### 1. Prefect should own execution semantics
Prefect should remain the primary owner of:

- task execution
- flow execution
- flow state transitions
- retries
- backoff
- timeouts
- cancellation
- concurrency control
- fan-out execution mechanics
- resumption and durable run state
- task and flow observability
- artifact persistence tied to execution
- explicit execution pause points when intentionally modeled

If removing Prefect would force SquadOps to rebuild the logic, that logic likely belongs in Prefect.

### 2. SquadOps should own semantic interpretation and strategic coordination
SquadOps should remain the primary owner of:

- cycle lifecycle interpretation
- workload sequencing decisions
- pulse checks
- policy reactions
- workload-level recovery strategy
- RCA and rewind decisions
- cross-workload coordination
- escalation decisions
- operator decision paths
- determining whether a failure means retry, repair, re-plan, or termination at the cycle level

If Prefect could be swapped for another execution substrate without changing the higher-order policy, that logic likely belongs in SquadOps.

### 3. Tasks should expose structured outcomes, not raw chaos
Tasks and workloads should not simply throw arbitrary exceptions upward and force orchestration layers to guess what happened.

Instead, they should classify outcomes in a structured way so that:

- Prefect can apply generic execution policy
- SquadOps can make domain-aware recovery decisions
- dashboards and RCA flows can interpret failure consistently

---

## Layered Ownership Model

### Layer 1: Task Layer
Owns:

- doing the work
- capturing local execution evidence
- collecting artifacts
- validating immediate output shape and quality where appropriate
- classifying outcomes
- surfacing structured failure context

This layer contains the knowledge closest to the work itself.

### Layer 2: Prefect Layer
Owns:

- running tasks and workloads
- sequential or parallel task topology execution
- task retry behavior
- timeout behavior
- durable execution state
- cancellation, pause, and resume semantics
- coordinating the mechanics of a workload attempt
- surfacing structured outcomes upward

Prefect should control **how attempts are run**, not **what failures mean strategically**.

### Layer 3: SquadOps Orchestration Layer
Owns:

- interpreting workload outcomes
- deciding whether to repair, rewind, re-plan, escalate, or terminate
- coordinating across workloads within a cycle
- running RCA workflows
- choosing next workload transitions
- preserving cycle intent, policy, and strategic alignment

SquadOps should control **what happens next**, not **how the runtime executes task mechanics**.

---

## The Most Important Boundary
The system should not ask:

- "Can Prefect fix this task with domain expertise?"

Instead it should ask:

- "Can Prefect manage this attempt correctly?"
- "Can the task classify what happened clearly enough that SquadOps can decide the next strategic move?"

This distinction avoids both failure modes:

- making Prefect domain-brained
- making SquadOps a mechanical workflow engine

---

## Mechanical Failure vs Semantic Failure

### Mechanical Failure
Mechanical failures are execution-oriented failures where Prefect can act effectively without deep domain knowledge.

Examples:

- transient network issue
- timeout
- temp filesystem lock
- container or worker hiccup
- dependency not ready yet
- brief rate limit response
- interrupted runtime
- recoverable infrastructure instability

These are good candidates for Prefect-owned retry or runtime handling.

### Semantic Failure
Semantic failures are meaning-oriented failures where the task may have completed execution but the result is wrong, misaligned, or strategically invalid.

Examples:

- generated code compiles but violates the plan
- artifact passed a basic check but failed acceptance criteria
- QA failure indicates planning defect, not implementation defect
- output is structurally valid but semantically wrong
- implementation drifted from the architectural contract
- retrying the same action is unlikely to change the outcome

These are not Prefect retry problems. These should surface upward to SquadOps for strategic recovery handling.

---

## TaskFailed Events: The Real Pressure Point
The presence of `TaskFailed` events on the Cycle Event Bus is not inherently wrong. The risk depends on what those handlers are allowed to do.

### Safe use of TaskFailed events
A `TaskFailed` event is safe when it is informational or observational, such as:

- updating telemetry
- incrementing failure counts
- appending RCA evidence
- degrading workload health indicators
- triggering operator visibility
- emitting a higher-order "at risk" signal
- contributing to pulse-level health assessment

### Dangerous use of TaskFailed events
A `TaskFailed` event becomes dangerous when it begins to govern execution mechanics, such as:

- deciding retry behavior for the task itself
- requeueing the task directly
- compensating within handler logic
- skipping downstream tasks by mutating runtime behavior
- manually altering execution state outside Prefect
- implementing custom resume or replay behavior from event handlers

This is the moment when Cycle Event Bus starts becoming a second orchestrator.

### Recommended posture
Keep `TaskFailed` events only as:

- telemetry signals
- evidence signals
- threshold inputs
- precursors to workload-level escalation

Do **not** let `TaskFailed` handlers own task recovery mechanics.

The preferred orchestration-relevant events should be higher level, such as:

- `WorkloadExecutionFailed`
- `WorkloadDegraded`
- `WorkloadNeedsRecoveryReview`
- `PulseThresholdBreached`
- `WorkloadQualityFailed`
- `CycleRecoveryDecisionRequired`

This preserves the abstraction boundary:

- task failure remains execution-local
- workload outcome becomes orchestration-relevant

---

## Structured Outcome Contract
The bridge between Prefect and SquadOps should be a structured outcome contract.

Tasks and workloads should ideally emit normalized statuses rather than arbitrary exceptions or loosely interpreted text.

A candidate contract could include:

- `Success`
- `RetryableFailure`
- `NonRetryableFailure`
- `Blocked`
- `NeedsRepair`
- `NeedsReplan`
- `NeedsEscalation`
- `Ambiguous`

These names are illustrative. The exact taxonomy can evolve, but the principle matters:

- tasks make the outcome legible
- Prefect applies mechanical policy generically
- SquadOps interprets strategic meaning

### Why this matters
Without structured outcomes:

- Prefect only sees "it failed"
- SquadOps must infer too much from raw runtime noise
- event handlers become fragile and over-clever
- RCA becomes inconsistent
- execution vs semantic failure boundaries blur

With structured outcomes:

- Prefect knows whether retry is appropriate
- SquadOps knows whether a new workload is needed
- telemetry becomes coherent
- recovery policy becomes auditable

---

## Failure Taxonomy
A formal failure taxonomy should be introduced so that failures are categorized consistently across workloads.

### 1. Execution Failures
These are primarily mechanical and runtime-oriented.

Examples:

- timeout
- dependency unavailable
- worker interruption
- transient transport error
- temporary service issue

**Likely first owner:** Prefect

### 2. Work Product Failures
These indicate the produced artifact or output is invalid or insufficient.

Examples:

- failed schema validation
- incomplete artifact
- invalid output structure
- failed verifier check
- malformed code or document

**Likely first owner:** task/workload logic, then SquadOps if unresolved

### 3. Alignment Failures
These indicate the produced result is off-plan or architecturally incorrect.

Examples:

- drift from plan
- contract violation
- wrong abstraction boundary
- acceptance mismatch
- output inconsistent with intended design

**Likely first owner:** SquadOps orchestration and recovery policy

### 4. Decision Failures
These indicate that the system cannot determine the correct next step safely.

Examples:

- conflicting evidence
- insufficient context
- ambiguity in recovery path
- no confident next action

**Likely first owner:** escalation or explicit recovery workflow

---

## Ownership Matrix Concept
A formal ownership matrix should be defined for each failure or outcome class. For each type, the model should specify:

- who detects it
- who handles it first
- whether it is retriable
- whether it terminates the workload
- what event is emitted
- who decides the next action

This would remove ambiguity and prevent recovery responsibilities from drifting over time.

---

## Recovery Model
The system should avoid trying to "fix the failed task" inside event handlers.

Instead, recovery should be modeled as explicit next actions at the workload or cycle level.

Recommended approach:

- let the workload stop cleanly with a structured outcome
- emit a normalized orchestration-relevant event
- let SquadOps decide the next strategic step
- execute that next step via Prefect again

This produces a cleaner model than hidden handler-driven intervention.

### Recovery should be first-class
Recovery is better modeled as explicit workloads rather than silent event handler magic.

Examples:

- `RepairWorkload`
- `ReplanWorkload`
- `RCAWorkload`
- `VerificationReplayWorkload`
- `EscalationWorkload`

This keeps recovery visible, auditable, and composable.

---

## Prefect-Owned Execution Topology Templates
Prefect can and should own reusable workload execution topology templates.

This is one of the strongest areas to leverage Prefect more fully.

Prefect is a good owner for runtime shape such as:

- sequential execution
- bounded fan-out
- fan-out then reduce
- staged pipeline execution
- verifier swarm execution
- bounded parallelism with aggregation

### Why this belongs in Prefect
These are execution-topology concerns, not domain concerns.

Examples of what Prefect should own:

- whether tasks are called directly in sequence
- whether tasks are submitted concurrently
- whether mapped work fans out over a collection
- whether a reduce phase collects results
- concurrency limits
- retry and timeout behavior within the topology
- durable task and flow state through the run

### Why SquadOps should still choose the template
SquadOps should still determine the intent-level pattern required by the workload.

Examples:

- "this workload is linear"
- "this workload should fan out across modules"
- "this workload should run bounded parallel verification"
- "this workload should execute fan-out and then aggregate findings"

That means the split becomes:

- **SquadOps chooses the pattern**
- **Prefect executes the pattern**

### Good use of Prefect templates
- "Run these N units with max parallelism 4, collect results, fail if threshold exceeded"

### Bad use of Prefect templates
- "If adapter implementation fails, switch to repair planner and reinterpret acceptance criteria"

The first is runtime topology. The second is domain recovery semantics.

---

## Recommended Template Catalog
A practical initial template catalog could include:

### 1. Sequential Workload
For workloads where order matters and later steps depend on earlier outputs.

Use cases:

- planning pipeline
- document refinement chain
- serial artifact assembly

### 2. Bounded Fan-Out Workload
For independent units of work that can execute in parallel up to a safe limit.

Use cases:

- per-file analysis
- per-module verification
- test partition execution
- batch artifact inspection

### 3. Fan-Out Then Reduce Workload
For workloads where individual units are processed independently and then collected into a synthesized result.

Use cases:

- verifier swarm with summary
- parallel review followed by aggregation
- per-component analysis with global recommendations

### 4. Staged Pipeline Workload
For workloads that run through distinct phases, where each phase may itself be sequential or parallel.

Use cases:

- plan -> implement -> verify
- ingest -> transform -> analyze -> summarize

### 5. Parallel Verify Workload
For applying multiple verifiers or quality checks concurrently against a shared artifact.

Use cases:

- QA pass set
- contract validation set
- architecture / schema / lint / test verification bundle

### 6. Repair Replay Workload
For explicit re-execution of a repair attempt against a known failed artifact or step, with controlled inputs and evidence capture.

Use cases:

- targeted recovery
- replay after fix generation
- bounded correction run

This remains a Prefect execution template, while the decision to invoke it remains with SquadOps.

---

## Litmus Tests
The following litmus tests help determine ownership.

### Litmus Test 1
If removing Prefect would force the system to rebuild the behavior, it probably belongs in Prefect.

### Litmus Test 2
If swapping Prefect for another execution engine would leave the policy mostly unchanged, it probably belongs in SquadOps.

### Litmus Test 3
If the logic changes what happens to the failed task itself, it likely belongs in Prefect.

### Litmus Test 4
If the logic changes what the cycle should do next based on the meaning of the failure, it likely belongs in SquadOps.

### Litmus Test 5
If the best response is "try again carefully," it likely stays in Prefect.

### Litmus Test 6
If the best response is "change the plan, change the strategy, or change the actor," it belongs above Prefect.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Prefect as passive logger
Prefect runs tasks but is bypassed for meaningful execution control.

### Anti-Pattern 2: Cycle Event Bus as shadow workflow engine
Handlers decide retries, resume logic, compensation, and task-level recovery behavior.

### Anti-Pattern 3: Raw exception-driven orchestration
Tasks bubble arbitrary exceptions upward and force every layer to guess what happened.

### Anti-Pattern 4: Hidden recovery magic
Recovery is performed implicitly in handler chains rather than as explicit workloads or visible policy transitions.

### Anti-Pattern 5: Domain expertise leaking into execution substrate
Prefect templates or flow logic begin to encode product-specific or architecture-specific recovery semantics.

---

## Recommended Canon Position
A useful canonical framing for SquadOps would be:

**Prefect owns workload execution topology and mechanical execution semantics; SquadOps owns workload intent, semantic interpretation, and recovery policy.**

A second concise framing:

**Prefect manages attempts. SquadOps manages intent. Tasks make outcomes legible.**

---

## Proposed Next Design Artifacts
This IDEA suggests the need for three follow-on artifacts:

### 1. Failure Ownership Matrix
A matrix defining, for each failure or outcome type:

- detected by
- first handler
- retriable or not
- workload impact
- emitted event
- recovery decision owner

### 2. Event Taxonomy
A formal event taxonomy clarifying:

- low-level telemetry events
- task evidence events
- workload outcome events
- pulse threshold events
- cycle recovery decision events

### 3. Outcome Contract Specification
A formal spec for task and workload result envelopes so that all workloads speak a consistent language to Prefect and SquadOps.

---

## Initial Recommendation
For SquadOps 1.0 / 1.1 direction, the recommended move is:

1. keep Prefect as the primary owner of task/workload runtime mechanics
2. demote `TaskFailed` event handlers to observational roles only
3. elevate orchestration decisions to workload-level outcome handling
4. introduce a structured outcome contract
5. formalize a failure taxonomy
6. model repair, RCA, and re-plan as explicit workloads
7. define a reusable catalog of Prefect execution topology templates

This path preserves the strengths of both systems while preventing architectural overlap and role confusion.

---

## Closing Thought
The solution is not to make Prefect smarter about SquadOps domain semantics.
The solution is not to make SquadOps responsible for runtime mechanics.

The solution is to make failures and outcomes legible enough that:

- Prefect can execute attempts correctly
- SquadOps can decide strategic recovery correctly
- recovery remains explicit, inspectable, and evolvable

That is the seam this IDEA is intended to protect.
