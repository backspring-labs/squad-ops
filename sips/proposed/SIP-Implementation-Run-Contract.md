# SIP-0XXX: Implementation Run Contract & Correction Protocol

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

This SIP defines the contract and runtime protocol for the **Implementation Workload** — the core execution phase of a SquadOps Cycle. The Implementation Run operates from an approved planning artifact and owns the full dev/test/fix convergence loop. It introduces a formal correction protocol (detect → RCA → decide → record plan delta → resume), bounded retry/timebox limits, durable state for checkpoint/resume, and role-specific capability baselines required for controlled long-duration execution.

## 2. Problem Statement

A long autonomous implementation run can appear productive while actually degrading over time. Without explicit controls, the squad may:

- Wander away from the approved objective without traceability.
- Silently change scope.
- Retry weak paths too long, burning time on failing approaches.
- Produce code without meaningful verification.
- Finish with incomplete or low-trust artifacts.

An 8-hour implementation run amplifies all of these risks. Additional compute capacity (e.g., DGX Spark) does not solve coordination, recovery, or artifact integrity problems. The platform needs an explicit run contract, bounded correction protocol, and checkpoint/resume capability to make long-duration execution trustworthy.

## 3. Goals

1. Establish **durable checkpoint and resume** as a non-negotiable platform capability — the platform must persist task completion state, artifacts, and plan delta history so that a long run can recover from interruptions without losing progress. Without this, no amount of architectural cleanliness makes a long run trustworthy.
2. Define the **Implementation Run Contract** — the canonical execution input that specifies objective, acceptance criteria, non-goals, time budget, stop conditions, and required wrap-up artifacts.
3. Establish a **correction protocol** with explicit steps: detect problem → root cause analysis → decide (continue, patch, rewind, abort) → record plan delta → resume with traceability.
4. Define **bounded retry and timebox limits**: max retries per task, max debug time per task, max consecutive failed validations before escalation.
5. Define **Pulse Check expectations** during implementation: plan divergence, repeated failures, scope creep, regression patterns, lack of forward progress.
6. Establish **role-specific capability baselines** required for a long-duration implementation run.
7. Ensure the implementation workload owns the **dev/test/fix convergence loop** — testing is part of implementation, not a separate workload.

## 4. Non-Goals

- Defining the planning or wrap-up workload protocols (separate SIPs).
- Implementing full self-healing or autonomous adjustment based on prior run history (1.1+).
- Retrieval-before-debugging memory integration (1.1+).
- Scored memory and decay logic (1.1+).
- Role-specific dependency overlays in Docker images (strongly recommended but can land independently).
- Defining the Workload domain model (covered by the Workload & Gate Canon SIP).

## 5. Approach Sketch

### Implementation Run Contract

Each implementation run begins with a hard execution contract:

- **Objective** — what the run must achieve (derived from the approved plan).
- **Acceptance Criteria** — testable conditions that define success.
- **Non-Goals** — explicit exclusions to prevent scope creep.
- **Time Budget** — total execution time envelope.
- **Stop Conditions** — when the run should halt rather than continue.
- **Required Wrap-Up Artifacts** — what the run must produce even on failure.

The contract is stored as a run-level artifact and is the reference point for all Pulse Checks and correction decisions.

### Correction Protocol

When a Pulse Check or task failure indicates drift or degradation:

1. **Detect** — Pulse Check identifies the problem (plan divergence, repeated failure, scope drift, regression).
2. **Root Cause Analysis** — Data/Lead analyze the failure. Classify as: implementation error, design gap, dependency issue, environmental issue, model limitation.
3. **Decide** — Lead selects a correction path:
   - `continue` — minor issue, proceeding as planned.
   - `patch` — fix the immediate problem, resume from current point.
   - `rewind` — roll back to the last valid checkpoint, try a different approach.
   - `abort` — halt the implementation run, proceed to wrap-up with partial results.
4. **Record Plan Delta** — store a structured artifact describing what changed, why, and what the new approach is.
5. **Resume** — execution continues with updated plan context and traceability.

### Bounded Execution Limits

For 1.0, the platform enforces:

- **Max retries per task** — configurable, default 3.
- **Max debug time per task** — configurable timebox before escalation.
- **Max consecutive failed validations** — threshold before mandatory Pulse Check escalation.
- **Checkpoint interval** — periodic state snapshots for resume capability.

### Checkpoint and Resume

The runtime preserves:

- Persistent artifact storage.
- Run metadata and task completion state.
- Last known good checkpoint (task/workload boundary).
- Plan delta history for the run.

Resume launches from the last valid checkpoint with full plan delta context.

### Implementation Convergence Loop

The implementation workload owns:

- Coding and build.
- Test execution.
- Issue identification and defect fixing.
- Re-test and convergence toward acceptable quality.

Testing is not split into a separate workload. The implementation workload runs until acceptance criteria are met, a stop condition is reached, or the time budget is exhausted.

### Role Capability Baselines

Minimum capabilities required for a long-duration implementation run:

- **Lead/Strategy**: interpret run contract, break work into bounded tasks, detect plan drift, recommend correction paths, generate plan deltas.
- **Dev**: implement within bounded scope, run targeted verification, emit implementation notes, hand off cleanly to QA.
- **QA**: execute verification against acceptance criteria, detect false progress, run targeted tests during the cycle, report defects with evidence.
- **Data**: analyze failure patterns, assist with RCA, identify repeated breakdown patterns.

### Pulse Check Focus Areas

Implementation-specific Pulse Checks monitor:

- Plan divergence (current work vs approved plan).
- Repeated failed fixes on the same issue.
- Scope creep (work appearing that was not in the plan).
- Regression patterns (previously passing tests now failing).
- Lack of forward progress (time passing without task completion).
- Artifact degradation (quality declining over time).

## 6. Key Design Decisions

1. **The protocol is duration-agnostic.** Checkpoint/resume, correction protocol, bounded retries, and convergence loop must work identically for a 1-hour MacBook cycle and an 8-hour DGX Spark cycle. Duration amplifies problems; it does not create them. All protocol mechanics must be developed and validated locally on short cycles before attempting long-duration runs on more capable hardware.
2. **Checkpoint/resume is the single most important capability in this SIP.** A long run without durable checkpoint/resume is fragile regardless of how clean the architecture is. The platform must persist: completed task state, produced artifacts, plan delta history, and the run contract itself. Resume launches from the last valid task boundary with full context. This is non-negotiable for the first validation run — local or Spark.
3. **Artifact continuity across resume** — when a run resumes from a checkpoint, all previously stored artifacts remain accessible. The resumed run does not re-execute completed tasks or re-produce existing artifacts. The operator-visible failure/resume reason is recorded as a durable event.
4. **Implementation owns testing** — the dev/test/fix convergence loop is a single workload, not separate workloads for development and testing. Testing becomes a separate workload only for release validation, compliance, or cross-system certification.
5. **Correction is protocol, not heroics** — correction follows a defined sequence (detect → RCA → decide → record → resume) rather than ad-hoc fixes.
6. **Plan deltas are append-only artifacts** — they do not mutate the original plan; they layer corrections on top with full traceability.
7. **Stop conditions are contractual** — the run contract declares when to halt. The platform respects these limits rather than letting the squad "try harder."

## 7. Acceptance Criteria

1. **Checkpoint/resume works at the task boundary level** — a run interrupted mid-execution can be resumed from the last completed task with all artifacts, plan deltas, and run metadata intact.
2. **Artifact continuity across resume** — previously stored artifacts remain accessible after resume; completed tasks are not re-executed.
3. **Operator-visible failure/resume reason** — the reason for interruption and the resume point are recorded as durable events and visible via API.
4. Implementation Run Contract schema is defined and storable as a run-level artifact.
5. Correction protocol is implemented: detect → RCA → decide → record plan delta → resume.
6. Plan Delta artifact schema captures what changed, why, classification, and new approach.
7. Bounded execution limits (max retries, max debug time, max consecutive failures) are configurable via cycle request profile.
8. Implementation-specific Pulse Check suites are defined and active during runs.
9. Role capability baselines are documented.
10. Convergence loop (dev → test → fix → retest) operates without workload boundary crossings.

## 8. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-long-run-readiness.md` — run contract, correction protocol with RCA and plan deltas, bounded retry/timebox limits, checkpoint/resume, role capability baselines, Pulse Check expectations, domain-aligned observability, first DGX Spark validation run requirements.

## 9. Open Questions

1. Should the run contract be a platform-native artifact type distinct from planning artifacts, or a section within the planning artifact?
2. Should plan deltas support superseding prior plan sections, or remain strictly append-only?
3. Should correction path decisions (`continue`, `patch`, `rewind`, `abort`) be automated based on Pulse Check signals, or always require Lead involvement?
4. How should domain-aligned telemetry (trace = cycle, span = workload, nested = task/pulse) map to the existing OTel and LangFuse infrastructure?

**Resolved**: The minimum resume boundary for 1.0 is the **task level** (resume after the last completed task). This is settled as a design decision, not an open question.
