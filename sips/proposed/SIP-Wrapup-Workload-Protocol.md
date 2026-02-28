# SIP-0XXX: Wrap-Up Workload Protocol

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

This SIP defines the protocol for the **Wrap-Up Workload** — the terminal phase of a SquadOps Cycle that determines what was actually achieved, how confidently those outcomes can be trusted, and what should happen next. Wrap-up is not casual cleanup or narrative summarization. It functions as the adjudication layer that converts execution into operational memory, producing evidence-backed closeout artifacts, confidence classifications, and next-cycle handoff packages.

## 2. Problem Statement

A long implementation run can produce code, tests, notes, logs, retries, partial fixes, and operator interventions, yet still fail to produce a trustworthy close. Without a defined wrap-up protocol, the platform risks:

- Completion claims that are not supported by evidence.
- Summary artifacts that bury caveats or deviations.
- Inability to distinguish planned work from drifted work.
- Weak carry-forward into the next cycle — the next planning phase starts with avoidable ambiguity.
- Operator review that depends on raw logs rather than decision-grade closeout artifacts.

If planning authorizes implementation, wrap-up authorizes memory. The wrap-up run determines whether the prior hours of execution become durable value or expensive ambiguity.

## 3. Goals

1. Define a **Wrap-Up Workload contract** — purpose, required inputs, required outputs, validation expectations, and what constitutes cycle-closed vs partial-close vs failed-close.
2. Establish a **standard closeout artifact** structure that a human can review without reconstructing the run from logs.
3. Require **planned-vs-actual comparison** — explicit accounting of what was planned, what was done, what changed, and whether changes were intentional.
4. Require **evidence-backed completion claims** — assertions of completion must cite supporting evidence (passed tests, build outputs, file diffs, verification results).
5. Introduce a **confidence classification model**: verified-complete, complete-with-caveats, partial-completion, not-sufficiently-verified, inconclusive, failed.
6. Define **structured unresolved issues** — categorized by type (defect, design debt, test gap, environmental, dependency, deferred enhancement) with severity, impact, and recommended next action.
7. Produce a **next-cycle handoff artifact** — what is stable, what remains unfinished, what should happen next, what should not be retried blindly.

## 4. Non-Goals

- Defining the implementation or planning workload protocols (separate SIPs).
- Richer scoring models or historical comparison across closeouts (1.1+).
- Automatic trend analysis across multiple cycles (1.1+).
- Advanced memory summarization into LanceDB (1.1+).
- Autonomous improvement proposals based on repeated failures (1.1+).
- Defining the scorecard evaluation framework (covered by the Cycle Evaluation Scorecard SIP).

## 5. Approach Sketch

### Wrap-Up Workload Contract

The wrap-up phase operates under an explicit contract:

- **Purpose**: adjudicate the implementation run and package results for operator review and next-cycle planning.
- **Required Inputs**: run contract, planning artifact, plan refinement deltas, implementation workload outputs, test results, failure/retry/RCA records, operator interventions, telemetry summary.
- **Required Outputs**: closeout artifact, next-cycle handoff artifact, artifact index.
- **Validation Expectations**: planned-vs-actual comparison, evidence-backed claims, confidence classification.
- **Handling Missing Inputs**: if inputs are missing or inconsistent, wrap-up explicitly lowers confidence rather than silently compensating.

### Wrap-Up Run Shape

Five segments:

1. **Gather and Reconcile Inputs** — collect run artifacts, verify required inputs exist, detect missing or conflicting evidence.
2. **Assess Outcomes** — compare planned vs actual, assess acceptance criteria, summarize validations, identify deviations.
3. **Classify Unresolved Items** — categorize defects, risks, debt, pending decisions, recommended follow-up.
4. **Produce Closeout Decision** — assign confidence classification, recommend next-cycle type, recommend operator action.
5. **Publish Handoff** — emit closeout artifact, next-cycle brief, artifact index, structured carry-forward items.

### Standard Closeout Artifact

Sections:

- Cycle objective
- Planned vs completed scope
- Implementation summary
- Validation summary
- Deviations from plan (with intentionality assessment)
- Notable corrections or rewinds (from plan delta history)
- Unresolved issues (structured, categorized)
- Risk assessment
- Confidence classification
- Readiness recommendation
- Next-cycle recommendation
- Artifact index

### Confidence Classification

| Classification | Meaning |
|----------------|---------|
| `verified_complete` | All acceptance criteria met with supporting evidence |
| `complete_with_caveats` | Core objectives met; minor gaps or untested edges remain |
| `partial_completion` | Some objectives met; significant work remains |
| `not_sufficiently_verified` | Artifacts exist but validation is insufficient to confirm quality |
| `inconclusive` | Cannot determine outcome from available evidence |
| `failed` | Core objectives not met |

### Structured Unresolved Issues

Each unresolved item includes:

- **Type**: defect, design-debt, test-gap, environmental, dependency, operator-decision-pending, deferred-enhancement.
- **Severity**: critical, high, medium, low.
- **Impact**: description of what is affected.
- **Suggested Owner/Role**: which agent role or human should address it.
- **Recommended Next Action**: specific guidance for resolution.

### Quality Reconciliation

Wrap-up reconciles evidence across the whole cycle:

- Implementation outputs vs acceptance criteria.
- QA findings vs completion claims.
- RCA records vs final status.
- Open risks vs recommendation to proceed.

### Next-Cycle Handoff Artifact

- What is stable now.
- What remains unfinished.
- What should happen next.
- What should not be retried blindly.
- Which risks need dedicated attention.
- Recommended next cycle type: planning, implementation, hardening, or research.

### Wrap-Up Pulse Checks

Monitor for common wrap-up failure modes:

- Over-summarizing and missing defects.
- Declaring success too early.
- Burying caveats.
- Ignoring plan deviations.
- Producing operator-unfriendly output.
- Turning the closeout into a transcript instead of a decision artifact.

### Human Review at Closeout

Operator review is expected for 1.0. The reviewer can:

- Accept closeout.
- Request clarification.
- Request revised classification.
- Request further validation.
- Reject closeout and reopen unresolved work.

## 6. Key Design Decisions

1. **Wrap-up is execution adjudication, not final notes** — the deliverable is a decision-grade closeout artifact, not a narrative summary.
2. **Non-success is a valid outcome** — if wrap-up always emits a polished victory narrative, it is not trustworthy. "Implementation produced but not sufficiently verified" is a legitimate classification.
3. **Wrap-up starts automatically** — no HIL gate between implementation and wrap-up by default (per Workload & Gate Canon SIP). Analysis is most valuable when the run did not go well.
4. **Confidence is multi-level, not binary** — six classification levels provide honest, usable granularity beyond pass/fail.
5. **Missing inputs lower confidence, not silently compensated** — the wrap-up does not fill gaps with optimistic assumptions.
6. **Planned-vs-actual comparison is mandatory** — without it, the platform can accidentally reward drift while describing it as success.

## 7. Acceptance Criteria

1. Wrap-Up Workload contract schema is defined and loadable from cycle request profiles.
2. Standard closeout artifact is emitted as a run artifact with all required sections.
3. Planned-vs-actual comparison is present in every closeout artifact.
4. Completion claims are evidence-backed (linked to specific artifacts, test results, or verification outputs).
5. Confidence classification is assigned and visible in the closeout artifact and via API.
6. Unresolved issues are structured with type, severity, impact, owner, and next action.
7. Next-cycle handoff artifact is emitted and consumable by the next planning phase.
8. Wrap-up Pulse Checks are defined and active during the wrap-up run.
9. Human review endpoint supports accept, request-clarification, revise-classification, request-validation, reject.

## 8. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-wrapup-run-readiness.md` — wrap-up contract, standard closeout artifact, planned-vs-actual comparison, evidence-backed claims, confidence classification, structured unresolved issues, quality reconciliation, next-cycle handoff, wrap-up Pulse Checks, human review at closeout.

## 9. Open Questions

1. Should the wrap-up run always execute even after catastrophic implementation failure, or should there be a minimum evidence threshold below which wrap-up is skipped?
2. Should confidence classification be computed automatically from evidence signals, assigned by the Lead agent, or both (auto-computed with Lead override)?
3. How should the next-cycle handoff artifact integrate with cycle request profiles — should it auto-generate a draft cycle request for the next cycle?
4. Should wrap-up artifacts be promoted to cycle level automatically, or require explicit promotion via gate?
5. How much of the closeout artifact should be human-written vs agent-generated for 1.0?
