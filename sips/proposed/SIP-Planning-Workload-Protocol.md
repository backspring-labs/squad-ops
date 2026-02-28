# SIP-0XXX: Planning Workload Protocol

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

This SIP defines the protocol for the **Planning Workload** — the first phase of a multi-workload Cycle. The Planning Workload produces an implementation-authorizing artifact with enough design proof and proto validation that the subsequent implementation phase can proceed with bounded risk, clear sequencing, and meaningful verification. It also establishes QA-first test strategy participation, plan refinement tracking, and a formal readiness decision (go / revise / no-go) before implementation begins.

## 2. Problem Statement

Without a disciplined planning phase, long implementation cycles degrade into expensive confusion. Several failure modes emerge:

- Planning becomes architecture brainstorming instead of implementation authorization.
- Proto work expands into uncontrolled implementation.
- Acceptance criteria remain vague or untestable.
- Risky assumptions go unclassified and are mistaken for resolved design decisions.
- QA enters too late to shape testability.
- Implementation sequencing is missing or weak.
- Human review occurs against an artifact that sounds confident but does not actually authorize build.
- The system advances to implementation with confidence but without clarity.

Additionally, QA involvement in planning is often an afterthought. For short autonomous runs, requiring a full test suite before implementation is too rigid, but QA should still produce acceptance checks, a test strategy note, and defect severity guidance before implementation begins.

## 3. Goals

1. Define a **Planning Workload contract** that bounds the phase: objective, timebox, required outputs, completion criteria, abort conditions.
2. Specify the **durable planning artifact** structure — the canonical handoff into implementation.
3. Establish **targeted proto validation** rules: what warrants proto work, what output types are acceptable, and how to prevent proto from becoming uncontrolled implementation.
4. Introduce **unknown classification** states (resolved, proto-validated, acceptable-risk, requires-human-decision, blocker) to prevent false certainty.
5. Define a **design sufficiency check** that determines whether the plan is ready to authorize implementation.
6. Integrate **QA-first test strategy** into the planning phase: acceptance checklist, test strategy note, and defect severity rubric — without requiring a full automated test suite upfront.
7. Specify **plan refinement tracking** so human feedback is captured as structured deltas, not informal edits.
8. Define the **readiness decision protocol**: go / revise / no-go with explicit gate outcomes including `approved_with_refinements`.

## 4. Non-Goals

- Defining the implementation workload protocol (separate SIP).
- Automated plan quality scoring (1.1+ enhancement).
- Retrieval-enriched planning memory or historical comparison (1.1+).
- Defining the Workload domain model itself (covered by the Workload & Gate Canon SIP).
- Full automated test suite authoring during planning (explicitly deferred to implementation phase by QA-first strategy).

## 5. Approach Sketch

### Planning Workload Contract

Each Planning Workload Run operates under an explicit contract that defines:

- Planning objective and problem statement
- Target outcome of the phase
- Timebox (recommended 60–90 minutes for 1.0 cycles)
- Required outputs (planning artifact, acceptance checklist, test strategy note)
- Completion criteria
- Escalation and abort conditions

### Durable Planning Artifact

The phase emits a structured planning artifact with sections:

- Objective, user/operator intent, scope, non-goals
- Assumptions and constraints
- Proposed design (interfaces, boundaries, state model)
- Workload breakdown and implementation sequencing
- Verification strategy
- Open questions, risks, and proto findings
- Recommended next step (go / revise / no-go)

### QA-First Participation

QA participates actively during planning, not after:

- **Acceptance Checklist** (required) — derived from cycle objective, PRD-aligned, verifiable, focused on the happy path.
- **Test Strategy Note** (required) — what will be manual, what could be automated later, what constitutes a blocker vs non-blocker.
- **Defect Severity Rubric** (recommended) — Sev 1 (blocker), Sev 2 (major), Sev 3 (minor) for fast Lead decisions at Pulse Checks.
- **Smoke Test Skeleton** (optional) — only if the implementation surface is stable enough; time-boxed.

### Role Expectations

- **Lead/Strategy**: own the planning contract, keep scope bounded, synthesize design choices, drive readiness.
- **Dev**: pressure-test feasibility, identify dependency impacts, propose sequencing, run tiny feasibility checks.
- **QA**: define testability early, challenge vague acceptance criteria, identify validation blind spots.
- **Data**: analyze risks, prior failure patterns, open questions; identify where proto validation is most needed.

### Proto Validation

Proto work is targeted and bounded. Acceptable proto outputs:

- Interface sketches, payload examples, state transition notes
- API path validation, plugin registration proof
- Dependency build confirmation in the target container
- Draft test matrix, sample workload decomposition

Proto work should prove or reduce risk, not partially build the feature.

### Unknown Classification

Every identified unknown gets classified:

- `resolved` — answered with evidence
- `proto-validated` — tested with proto output
- `acceptable-risk` — acknowledged, bounded, not blocking
- `requires-human-decision` — needs operator input at review gate
- `blocker` — must be resolved before implementation

If too many core items remain at `acceptable-risk`, the phase should recommend a narrower implementation target.

### Design Sufficiency Check

Before the readiness gate, the phase asks:

- Are boundaries clear? Are interfaces specified?
- Is the first implementation sequence obvious?
- Are acceptance criteria testable?
- Are risky assumptions validated or surfaced?
- Does QA have enough to verify meaningfully?

### Plan Refinement Tracking

When human review returns `approved_with_refinements`, feedback is stored as a structured Plan Refinement Artifact capturing:

- What changed, why it changed, what triggered the change
- Which planning artifact sections were updated
- Whether scope expanded or narrowed
- Whether implementation sequencing changed
- Incorporation status: incorporated / partially incorporated / not incorporated / superseded

Refinement is incorporated via a **Plan Refinement Run** against the same Planning Workload, not via informal edits to the canonical plan.

## 6. Key Design Decisions

1. **Planning is implementation authorization, not design brainstorming** — the deliverable is a build-authorizing artifact, not a "nice plan."
2. **QA-first means acceptance checks first, not full test suite first** — rigid "write all tests first" creates brittle tests against changing implementation details in short cycles.
3. **No-go is a valid outcome** — a planning phase that always results in "ready to build" is not functioning as a real control.
4. **Proto is bounded** — proto outputs are constrained to specific types to prevent uncontrolled implementation creep.
5. **Plan refinement is tracked, not hand-waved** — human feedback becomes a structured, attributable artifact with incorporation tracking.
6. **Timebox is explicit** — 60–90 minutes recommended for 1.0 cycles to prevent open-ended architecture exploration.

## 7. Acceptance Criteria

1. Planning Workload contract schema is defined and loadable from cycle request profiles.
2. Planning artifact structure is documented with required and optional sections.
3. QA acceptance checklist template exists and is emitted as a run artifact.
4. Unknown classification states are represented in the planning artifact schema.
5. Design sufficiency check criteria are defined and executable (manual or automated).
6. Plan Refinement Artifact schema captures structured deltas and incorporation status.
7. Readiness gate supports go / revise / no-go outcomes.
8. Planning-specific Pulse Checks are defined (scope drift, over-design, blocker accumulation).
9. Role expectations for the planning phase are documented.

## 8. Source Ideas

- `docs/ideas/IDEA-squadops-1.0-planning-proto-readiness.md` — planning-phase contract, durable planning artifact, proto validation, unknown classification, design sufficiency, readiness decision.
- `sips/proposed/IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md` — QA-first strategy, acceptance checklist, test strategy note, defect severity rubric, maturity-staged testing progression.

## 9. Open Questions

1. Should the planning artifact schema be a JSON schema or a markdown template with required sections?
2. Should the planning timebox be enforced by the platform (hard stop) or advisory (Pulse Check warning)?
3. How should Planning Pulse Checks differ from Implementation Pulse Checks — same framework with different check suites, or a distinct mechanism?
4. Should the Plan Refinement Run reuse the planning task plan or generate a new one scoped to the refinement instructions?
5. At what maturity stage should QA smoke test scaffolding become required rather than optional?
