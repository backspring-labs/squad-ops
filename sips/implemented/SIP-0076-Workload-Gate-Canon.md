---
title: Workload & Gate Canon
status: implemented
author: SquadOps Architecture
created_at: '2026-02-28T00:00:00Z'
sip_number: 76
updated_at: '2026-02-28T12:01:03.944490Z'
---
# SIP-0XXX: Workload & Gate Canon

**Status:** Proposed\
**Target Release:** SquadOps 1.0\
**Authors:** SquadOps Architecture\
**Created:** 2026-02-28\
**Revision:** 3 (2026-02-28)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-28 | Initial proposal (~110-line outline) |
| 2   | 2026-02-28 | Acceptance-ready rewrite: concrete domain model definitions with exact field types, DDL migration SQL, API route changes with DTOs, cycle request profile integration, gate semantic tightening with expanded `GateDecisionValue`, artifact promotion model, multi-workload cycle pattern, pulse vs gate clarification, telemetry event additions, backwards compatibility guarantees, phased rollout plan. Resolved all 5 open questions. |
| 3   | 2026-02-28 | Implementation tightenings (12 items): (1) Gate-awaiting run status must be `paused`, not terminal, to remain gate-decidable. (2) `returned_for_revision` stays on current workload path; does not advance workload sequence. (3) Promoted artifacts are canonical inter-workload inputs (design principle 3.5). (4) Promotion endpoint is idempotent end-to-end (`200`, no `409`). (5) `workload_sequence.gate` explicitly defined as boundary after that workload. (6) `refinement` is convention, not executor control plane. (7) Gate naming validation: `progress_`/`promote_` prefix required in `workload_sequence` references. (8) `workload_type` input validation: trim, reject empty, preserve case. (9) Only promoted artifacts eligible for baseline. (10) `workload.*` telemetry events are explicit emissions, not derived. (11) Recommended cycle shape is reference canon, not execution mandate. (12) Five negative-path acceptance criteria added (ACs 17-21). |

------------------------------------------------------------------------

## 1. Abstract

SquadOps currently models execution as Cycle -> Run -> Task. This SIP
formalizes the **Workload** concept as the bounded unit of intended work
within a Cycle, and tightens the semantics of Gates, Pulses, and
artifact promotion.

The result is a cleaner execution hierarchy ---
Cycle -> Workload -> Run -> Task --- where each concept answers a
distinct question and the platform can support multi-phase cycles
(planning, implementation, wrap-up) without collapsing responsibilities
into a single monolithic run.

For 1.0, "Workload" is a **classification on Run** (`workload_type`
field), not a new database entity. This is the minimum viable vocabulary
that enables multi-phase orchestration without over-engineering.

------------------------------------------------------------------------

## 2. Problem Statement

As SquadOps moves toward longer-running, multi-phase cycles, the current
Cycle -> Run model lacks a semantic layer for "what bounded thing are we
trying to get done." Without it:

-   A Cycle that includes planning, implementation, and wrap-up must
    either be one giant Run or multiple Runs with no explicit
    relationship to the phase they serve.
-   Gates conflate in-run health checks with inter-phase progression
    decisions.
-   Artifact provenance is flat --- there is no distinction between
    working artifacts and promoted cycle-level artifacts.
-   Pause/resume semantics become ambiguous when a Cycle has multiple
    sequential concerns.
-   Post-run evaluation has no natural workload container.

The platform needs a vocabulary and domain model that keeps these
concerns separate so they can be reasoned about, orchestrated, and
evaluated independently.

------------------------------------------------------------------------

## 3. Design Principles

### 3.1 Minimum Viable Vocabulary

Add the fewest concepts needed to distinguish workload phases, gate
roles, and artifact provenance. A `workload_type` field on Run is
cheaper and more reversible than a full Workload entity table.

### 3.2 Classification, Not Entity

Workload is a Run classification for 1.0. If the domain model demands a
first-class Workload entity later, this classification gives the
migration path: runs already carry the workload_type, so a new
`cycle_workloads` table can reference them without a data migration.

### 3.3 Additive Schema Changes Only

All domain model, DDL, and API changes are additive. Existing fields
retain their types and defaults. New fields default to `None` or
`"working"` so existing consumers are unaffected.

### 3.4 Gate Role Clarity

Gates serve two distinct purposes (progression between phases,
promotion of artifacts). Making the role explicit prevents semantic
drift as the platform gains more gate types.

### 3.5 Promoted Artifacts as Canonical Inter-Workload Inputs

When a downstream workload requires an authoritative artifact from a
previous workload, it should prefer **promoted artifacts** over working
artifacts. Working artifacts remain available for debugging and operator
review, but promoted artifacts are the canonical inter-workload handoff
state. This prevents later protocol SIPs from inventing inconsistent
handoff rules.

------------------------------------------------------------------------

## 4. Terminology

### Workload

A bounded unit of intended work within a Cycle. Each Workload has an
objective (planning, implementation, evaluation), expected
inputs/outputs, and acceptance criteria. For 1.0, a Workload is
expressed as the `workload_type` field on Run --- not a separate entity.

### Workload Type

A free-form string classifying the kind of work a Run performs. Standard
values are defined as well-known constants in a `WorkloadType` helper
class. Custom values are permitted for extensibility.

### Gate

A **human or policy decision point** where an operator approves,
rejects, or refines forward progress. Gates are defined in
`task_flow_policy` (SIP-0064) and are distinct from pulse checks. Gates
require a decision; pulse checks are fully automatic.

### Gate Role

Gates serve one of two roles:

- **Progression** --- controls whether the next workload phase may
  begin. Example: plan review gate before implementation.
- **Promotion** --- controls whether a run-scoped artifact is elevated
  to cycle-level canonical status. Example: approving a plan artifact
  as the authoritative plan.

Gate role is expressed by convention (gate name prefix `progress_` or
`promote_`), not as a field on the `Gate` dataclass. This avoids a
schema change while making intent explicit in cycle request profiles.

### Pulse Check

An automatic, mechanical verification suite that runs at the end of a
Pulse (cadence-bounded execution interval). Produces a boundary
decision with no human involvement: PASS, FAIL, or EXHAUSTED. Defined
by SIP-0070.

### Pulse vs Gate Boundary

- **Pulse** = in-run health check. Fires on cadence limits. Does not
  pause execution. Monitors alignment, progress, drift, quality. Stays
  within a single Run. Fully automatic.
- **Gate** = inter-workload progression boundary. Requires explicit
  decision (human or policy). Pauses cycle progression until decided.
  Typically sits between Runs of different workload types.

### Artifact Promotion Status

A classification on `ArtifactRef` distinguishing working (run-scoped,
in-progress) artifacts from promoted (cycle-scoped, canonical)
artifacts. Default is `working`. Promotion is always explicit, never
implicit.

------------------------------------------------------------------------

## 5. Goals

1.  Introduce **Workload** as a first-class domain concept: a bounded
    unit of intended work within a Cycle, with its own objective, scope,
    acceptance criteria, and expected inputs/outputs.
2.  Add `workload_type` to `Run` so each Run is explicitly associated
    with a Workload classification (e.g., planning, implementation,
    evaluation).
3.  Formalize **Gate** semantics as progression/promotion boundaries
    between Workloads, not as in-run pause mechanisms.
4.  Formalize **Pulse** semantics as in-run health/alignment checkpoints
    that live inside a Run, distinct from Gates.
5.  Introduce an **artifact promotion model** distinguishing working
    (run-scoped) artifacts from promoted (cycle-scoped) artifacts.
6.  Define a recommended multi-workload Cycle pattern:
    Planning -> Implementation -> Wrap-Up/Evaluation.

------------------------------------------------------------------------

## 6. Non-Goals

-   Implementing the Planning, Implementation, or Wrap-Up workload
    protocols (those are separate SIPs that build on this canon).
-   Introducing a Workload database entity with its own table --- for
    1.0, Workload is a classification on Run (`workload_type`), not a
    new entity level.
-   Defining the MEH-ta evaluation model or scorecard framework (covered
    by the Cycle Evaluation Scorecard SIP).
-   Replacing or modifying existing Pulse Check behavior from SIP-0070
    --- this SIP clarifies the semantic boundary, not the
    implementation.
-   WebSocket or real-time event delivery --- post-1.0 concern.
-   Adding a `role` field to the `Gate` dataclass --- gate role is
    expressed by naming convention for 1.0.

------------------------------------------------------------------------

## 7. Domain Model Changes

### 7.1 WorkloadType Helper Class

Following the existing `ArtifactType` pattern (class with string
constants, not an enum), `workload_type` is a free-form `str | None`
with well-known constants. This is extensible without code changes;
custom values are permitted.

``` python
class WorkloadType:
    """Well-known workload type constants.

    workload_type on Run is free-form str | None. These constants
    document the standard vocabulary. Custom values are permitted.
    """
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    EVALUATION = "evaluation"
    REFINEMENT = "refinement"
```

Placement: `src/squadops/cycles/models.py`, alongside existing
`ArtifactType` and `RunInitiator` classes.

`REFINEMENT` is a **recommended standard value**, not a special case in
the executor. The V1 executor must not hardcode special orchestration
semantics solely because `workload_type == "refinement"`. Refinement
meaning comes from the gate outcome (`returned_for_revision`) and the
pipeline protocol, not from the workload_type string alone. This
prevents `workload_type` classification from quietly becoming a hidden
control plane.

### 7.2 Run Dataclass Extension

Add `workload_type` as an optional field with `None` default. Existing
Runs (legacy) have `workload_type=None`.

``` python
@dataclass(frozen=True)
class Run:
    """Single execution attempt of a Cycle. SIP-0064 §8.4."""

    run_id: str
    cycle_id: str
    run_number: int
    status: str                          # RunStatus value
    initiated_by: str                    # RunInitiator value
    resolved_config_hash: str
    resolved_config_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: tuple[GateDecision, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    workload_type: str | None = None     # <-- NEW (WorkloadType value or custom)
```

The new field is last among the optional fields to preserve
positional-argument compatibility. All existing code that constructs
`Run` instances by keyword arguments is unaffected.

### 7.3 GateDecisionValue Enum Extension

Expand from binary `approved`/`rejected` to four outcomes:

``` python
class GateDecisionValue(StrEnum):
    """Gate decision values.

    Expanded from binary (SIP-0064 T4) to support richer progression
    semantics. SIP-Workload-Gate-Canon §7.3.
    """
    APPROVED = "approved"
    APPROVED_WITH_REFINEMENTS = "approved_with_refinements"
    RETURNED_FOR_REVISION = "returned_for_revision"
    REJECTED = "rejected"
```

Semantics:
- `approved` --- proceed to next workload phase (or promote artifact).
- `approved_with_refinements` --- proceed, but record that refinements
  are needed. The platform records the decision and notes; it does NOT
  auto-create a refinement run. Pipeline protocol SIPs may act on this
  signal.
- `returned_for_revision` --- do not proceed. The current workload
  should produce a new run (refinement) addressing the feedback. Not
  terminal --- the cycle remains active.
- `rejected` --- terminal rejection. No further runs for this workload
  phase. Cycle may be cancelled or the gate may be overridden by a
  subsequent decision (subject to existing `GateAlreadyDecidedError`
  constraint).

### 7.4 Gate Decision Constraint

The existing UNIQUE constraint `(run_id, gate_name)` on
`cycle_gate_decisions` remains unchanged. A gate may only be decided
once per run. `approved_with_refinements` and `returned_for_revision`
do not conflict with this constraint --- they are single decisions, not
sequences.

If a gate needs to be re-decided (e.g., after a refinement run), the
new decision is recorded on the *new* run, not by updating the original
run's gate decision. This preserves immutability and audit trail.

### 7.5 GateDecisionRequest DTO Extension

The API request DTO expands to accept the new decision values:

``` python
class GateDecisionRequest(BaseModel):
    """Gate decision (expanded vocabulary)."""

    decision: Literal[
        "approved",
        "approved_with_refinements",
        "returned_for_revision",
        "rejected",
    ]
    notes: str | None = None

    class Config:
        extra = "forbid"
```

### 7.6 ArtifactRef Promotion Status

Add `promotion_status` to the existing `ArtifactRef` frozen dataclass:

``` python
@dataclass(frozen=True)
class ArtifactRef:
    """Immutable artifact metadata. SIP-0064 §8.5."""

    artifact_id: str
    project_id: str
    artifact_type: str
    filename: str
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    cycle_id: str | None = None
    run_id: str | None = None
    metadata: dict = field(default_factory=dict)
    vault_uri: str | None = None
    promotion_status: str = "working"    # <-- NEW ("working" | "promoted")
```

`promotion_status` is placed last (after `vault_uri`) among fields with
defaults. Existing code that constructs `ArtifactRef` instances is
unaffected.

### 7.7 PromotionStatus Helper Class

``` python
class PromotionStatus:
    """Well-known artifact promotion status constants."""
    WORKING = "working"
    PROMOTED = "promoted"
```

Placement: `src/squadops/cycles/models.py`, alongside `ArtifactType`.

------------------------------------------------------------------------

## 8. DDL Migration

File: `infra/migrations/004_workload_canon.sql`

``` sql
-- 004_workload_canon.sql
-- SIP-Workload-Gate-Canon: workload_type on runs, promotion_status on artifacts.
-- All DDL is idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

-- Add workload_type to cycle_runs
ALTER TABLE cycle_runs
    ADD COLUMN IF NOT EXISTS workload_type TEXT;

-- Index for workload_type filtering (nullable, partial index on non-null)
CREATE INDEX IF NOT EXISTS idx_cycle_runs_workload_type
    ON cycle_runs(workload_type)
    WHERE workload_type IS NOT NULL;

-- Add promotion_status to cycle_artifacts (if artifact table exists)
-- Note: artifacts are currently stored via ArtifactVaultPort adapters.
-- If a cycle_artifacts table is introduced, add:
--   ALTER TABLE cycle_artifacts
--       ADD COLUMN IF NOT EXISTS promotion_status TEXT NOT NULL DEFAULT 'working';
-- For filesystem vault: promotion_status lives in the ArtifactRef metadata dict.
-- For Postgres vault (future): promotion_status is a column.

-- No backfill needed:
-- - Existing runs: workload_type = NULL (legacy, no classification)
-- - Existing artifacts: promotion_status defaults to 'working'
-- - Existing gate decisions: 'approved'/'rejected' remain valid values
```

### 8.1 Migration Notes

- `workload_type` is `TEXT`, nullable. `NULL` means "legacy run with no
  workload classification." No backfill is required.
- The partial index (`WHERE workload_type IS NOT NULL`) avoids indexing
  legacy rows and keeps the index small.
- Artifact promotion status is handled differently per vault adapter:
  - **Filesystem vault**: `promotion_status` is stored in the
    `ArtifactRef.metadata` dict (key `"promotion_status"`). The
    dataclass field provides the canonical accessor.
  - **Postgres vault (future)**: `promotion_status` is a column with
    `DEFAULT 'working'`.
- Migration file follows the existing naming convention
  (`001_cycle_registry.sql`, `002_pulse_verification.sql`,
  `003_squad_profiles.sql`).

------------------------------------------------------------------------

## 9. API Changes

### 9.1 Run Filtering by Workload Type

Add optional `workload_type` query parameter to the existing `list_runs`
endpoint:

```
GET /api/v1/projects/{project_id}/cycles/{cycle_id}/runs?workload_type=planning
```

The filter is applied server-side. `workload_type` is optional; omitting
it returns all runs (existing behavior).

Implementation: add `workload_type: str | None = None` parameter to
`list_runs()` route function. Pass through to
`CycleRegistryPort.list_runs()` which gains an optional
`workload_type` filter parameter.

### 9.2 CycleRegistryPort.list_runs Extension

``` python
@abstractmethod
async def list_runs(
    self,
    cycle_id: str,
    *,
    workload_type: str | None = None,   # <-- NEW
    limit: int = 50,
    offset: int = 0,
) -> list[Run]:
    """List runs for a cycle, with pagination and optional workload filter."""
```

Both MemoryCycleRegistry and PostgresCycleRegistry adapters implement
the filter. Postgres adapter adds `AND workload_type = $N` when the
parameter is non-None.

### 9.3 RunResponse DTO Extension

``` python
class RunResponse(BaseModel):
    run_id: str
    cycle_id: str
    run_number: int
    status: str
    initiated_by: str
    resolved_config_hash: str
    resolved_config_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: list[GateDecisionResponse] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    workload_type: str | None = None     # <-- NEW
```

The `run_to_response()` mapping function adds
`workload_type=run.workload_type`.

### 9.4 ArtifactRefResponse DTO Extension

``` python
class ArtifactRefResponse(BaseModel):
    artifact_id: str
    project_id: str
    cycle_id: str | None = None
    run_id: str | None = None
    artifact_type: str
    filename: str
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    metadata: dict = Field(default_factory=dict)
    vault_uri: str | None = None
    promotion_status: str = "working"    # <-- NEW
```

The `artifact_to_response()` mapping function adds
`promotion_status=artifact.promotion_status`.

### 9.5 Artifact Promotion Endpoint

New endpoint to promote an artifact from `working` to `promoted`:

```
POST /api/v1/artifacts/{artifact_id}/promote
```

Request body: empty (no payload required).

Response: `ArtifactRefResponse` with `promotion_status: "promoted"`.
Returns `200` in all success cases, including when the artifact is
already promoted (idempotent).

Errors:
- `404 ARTIFACT_NOT_FOUND` if artifact_id does not exist.

Implementation: the endpoint calls a new
`ArtifactVaultPort.promote_artifact()` method that updates the
promotion status. For the filesystem vault, this updates the metadata
JSON. For a future Postgres vault, this updates the column.

The route is idempotent end-to-end: promoting an already-promoted
artifact returns `200` with the unchanged artifact. The UI may choose
to show "already promoted" as an informational state based on the
returned `promotion_status` field, not an HTTP error code. This is
cleaner for automation, simpler for CLI/UI, and retry-safe.

### 9.6 ArtifactVaultPort.promote_artifact Extension

``` python
@abstractmethod
async def promote_artifact(self, artifact_id: str) -> ArtifactRef:
    """Promote an artifact from 'working' to 'promoted'.

    Promotion is one-way: promoted artifacts cannot be demoted.
    Idempotent: promoting an already-promoted artifact returns it unchanged.

    Raises:
        ArtifactNotFoundError: If the artifact_id is not found.
    """
```

Promotion is one-way. There is no `demote` operation. Once promoted, an
artifact retains that status permanently. This simplifies reasoning
about artifact lifecycle and prevents accidental demotion of canonical
artifacts.

Both the port method and the API route are idempotent: promoting an
already-promoted artifact returns it unchanged with no error.

### 9.7 Artifact Filtering by Promotion Status

Add optional `promotion_status` query parameter to existing artifact
list endpoints:

```
GET /api/v1/projects/{project_id}/artifacts?promotion_status=promoted
GET /api/v1/projects/{project_id}/cycles/{cycle_id}/artifacts?promotion_status=promoted
```

This allows the console to show "promoted artifacts for this cycle"
without client-side filtering.

### 9.8 Run Creation with Workload Type

The `create_run` route accepts an optional `workload_type` in the
request body. For the first run created atomically with a cycle, the
`workload_type` is set by the executor (see Section 13).

For retry runs created via the API, the caller may specify
`workload_type` to match the workload of the original run.

**V1 input validation rules for `workload_type`:**

- Accepts any non-empty string or `null`.
- Well-known `WorkloadType` constants are recommended, not enforced.
- Leading/trailing whitespace is trimmed.
- Empty string after trim is rejected (`422 VALIDATION_ERROR`).
- Supplied value is preserved exactly after trim (no case
  normalization). `"Planning"` and `"planning"` are distinct values;
  callers are expected to use the well-known lowercase constants.

### 9.9 GateDecisionResponse DTO

No changes needed. The `decision` field is already `str` type and will
carry the expanded values without schema change.

------------------------------------------------------------------------

## 10. Gate Semantic Tightening

### 10.1 Gate Role Convention

Gates serve two roles: **progression** (controls phase transition) and
**promotion** (controls artifact elevation). For 1.0, role is expressed
by naming convention:

- `progress_*` gates (e.g., `progress_plan_review`) --- progression
  gates. The gate decision controls whether the next workload phase
  begins.
- `promote_*` gates (e.g., `promote_plan_artifact`) --- promotion
  gates. The gate decision controls whether an artifact is promoted.

The `Gate` dataclass does not gain a `role` field. Convention-based
classification keeps the schema change minimal and avoids a
migration on `task_flow_policy` JSONB.

**V1 validation rule:** gate names referenced in `workload_sequence`
entries must use a recognized prefix (`progress_` or `promote_`).
Non-conforming gate names in `workload_sequence` are rejected at cycle
request profile validation time. Gate names elsewhere (in
`task_flow_policy.gates` without a `workload_sequence` reference) are
unconstrained for backward compatibility. This prevents the naming
convention from becoming fuzzy folklore while preserving existing
behavior for non-workload cycles.

### 10.2 Gate Decision Semantics

The expanded `GateDecisionValue` enum enables richer workflows:

| Decision | Effect on Cycle | Typical Usage |
|----------|-----------------|---------------|
| `approved` | Next workload phase may begin (progression) or artifact is promoted (promotion) | Standard approval |
| `approved_with_refinements` | Next phase begins, but refinement feedback is recorded in `notes` | Plan approved with minor changes requested |
| `returned_for_revision` | Current workload should produce a new run addressing feedback | Plan needs rework; cycle stays active |
| `rejected` | No further progress on this workload path | Terminal rejection of plan or artifact |

### 10.3 Run Status at Gate Boundaries

A run that completes its workload tasks and is awaiting a progression
gate must end in a **non-terminal, gate-decidable state**. The V1 rule:

- When the executor finishes dispatching tasks for a workload phase that
  has a progression gate, the run transitions to `paused` --- not
  `completed`.
- The run remains in `paused` until the gate decision is recorded.
- Terminal run states (`completed`, `failed`, `cancelled`) are only used
  once the run/workload path is fully closed.
- Gate decisions are recorded against the `paused` workload-boundary
  run.

This is critical because `record_gate_decision()` rejects decisions for
terminal runs (`RunTerminalError`). If a run were marked `completed`
before the gate is decided, gate recording would be blocked by existing
validation. The `paused` state keeps the run gate-decidable.

### 10.4 Interaction with Existing Gate Validation

The existing `record_gate_decision()` validation rules (SIP-0064 T11)
remain unchanged:

1. `gate_name` must exist in the Cycle's `TaskFlowPolicy.gates`.
2. Run must not be in a terminal state (`RunTerminalError`).
3. Conflicting decision raises `GateAlreadyDecidedError`.
4. Same decision is idempotent (no-op, return current Run).

The new decision values integrate naturally. The validation checks
`gate_name` membership and conflict, not the decision value itself.
Decision values are validated by the API DTO's `Literal` type
constraint.

### 10.5 `returned_for_revision` and Workload Sequencing

`returned_for_revision` does **not** advance the cycle to the next
workload in `workload_sequence`. Instead:

- The cycle stays on the current workload phase.
- A new run is created for the same workload path, with
  `workload_type="refinement"` by convention (or the same
  `workload_type` as the original run).
- Progression to the next workload is blocked until a subsequent
  progression gate on a new run yields `approved` or
  `approved_with_refinements`.
- Prior run history is never mutated. The original run's gate decision
  (`returned_for_revision`) and the refinement run's gate decision are
  separate immutable records.

This makes refinement a retry path within the current workload phase,
not a sibling phase. It affects run history, UI grouping (refinement
runs group with their parent workload), and executor logic
(the workload sequence pointer does not advance).

### 10.6 What `approved_with_refinements` Does NOT Do

The platform **does not** auto-create a refinement run when
`approved_with_refinements` is selected. The decision is recorded with
its notes, and the pipeline protocol SIPs (Planning Workload Protocol,
etc.) determine how to act on it.

This is deliberate: the Workload & Gate Canon defines vocabulary, not
orchestration behavior. Orchestration belongs to the workload protocol
SIPs that consume this vocabulary.

------------------------------------------------------------------------

## 11. Artifact Promotion Model

### 11.1 Promotion Status Field

Every `ArtifactRef` carries a `promotion_status` field:

| Value | Meaning |
|-------|---------|
| `working` | Default. Run-scoped, in-progress artifact. May be incomplete or draft. |
| `promoted` | Cycle-scoped, canonical artifact. Represents the authoritative version. |

### 11.2 Promotion Rules

1. **Explicit only** --- promotion happens via API call (`POST
   /artifacts/{id}/promote`) or as a side effect of a promotion gate
   decision. Never implicitly.
2. **One-way** --- promoted artifacts cannot be demoted. This prevents
   accidental loss of canonical status.
3. **Independently callable** --- promotion does not require a gate
   decision. Any authenticated user can promote an artifact via API.
   Gate decisions MAY trigger promotion as a side effect (determined by
   pipeline protocol SIPs), but promotion is not gate-locked.
4. **Idempotent** --- promoting an already-promoted artifact is a no-op.

### 11.3 Interaction with Baselines

Artifact promotion and baseline promotion are orthogonal concepts:

- **Promotion** (`working` -> `promoted`): elevates an artifact from
  run-scoped to cycle-scoped canonical status. Answers: "is this the
  authoritative version for this cycle?"
- **Baseline** (`set_baseline`): designates a promoted artifact as the
  project-level baseline for its artifact type. Answers: "is this the
  current reference for this project?"

**Precedence rule:** only **promoted** artifacts are eligible to become
project baselines. `set_baseline` must reject working artifacts with a
validation error. This keeps "baseline" aligned with "authoritative
artifact" and prevents accidental project-level anchoring to draft
output.

A typical flow: artifact is stored (`working`) -> promoted after review
(`promoted`) -> set as baseline for incremental builds (`baseline`).

### 11.4 Storage

For the filesystem `ArtifactVaultPort` adapter (current implementation):
`promotion_status` is stored as a field on the in-memory `ArtifactRef`
and persisted via the existing metadata serialization. No new files or
directories are needed.

For a future Postgres vault adapter: `promotion_status` is a column
with `DEFAULT 'working'`.

------------------------------------------------------------------------

## 12. Cycle Request Profile Integration

### 12.1 Workload Type in Cycle Request Profiles

Cycle request profiles can specify a default `workload_type` in
`applied_defaults`. This is consumed by the executor when creating runs
for each workload phase.

``` yaml
# Cycle request profile with workload defaults
name: multi-phase
description: "Planning -> Implementation -> Evaluation cycle"
defaults:
  squad_profile_id: full-squad
  build_strategy: fresh
  workload_sequence:
    - type: planning
      gate: progress_plan_review
    - type: implementation
      gate: null
    - type: evaluation
      gate: null
```

### 12.2 Workload Sequence in Applied Defaults

The `workload_sequence` key flows into `applied_defaults` via the
existing CRP schema mechanism. Add `"workload_sequence"` to
`_APPLIED_DEFAULTS_EXTRA_KEYS`:

``` python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks",
    "plan_tasks",
    "pulse_checks",
    "cadence_policy",
    "build_profile",
    "dev_capability",
    "generation_timeout",
    "workload_sequence",    # <-- NEW
}
```

### 12.3 Workload Sequence Schema

Each entry in `workload_sequence` is a dict with:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `WorkloadType` value (or custom string) |
| `gate` | string or null | no | Name of the gate that follows this workload phase. `null` means no gate (auto-proceed to next phase). |

The `gate` on a workload entry represents the decision boundary **after
completion of that workload** and before the next workload may begin.
For example, `planning` + `progress_plan_review` means "after the
planning run completes, this gate must be decided before implementation
begins."

The executor reads `workload_sequence` from `applied_defaults` and uses
it to determine:
1. What `workload_type` to set on each run.
2. Whether a gate decision is required before proceeding to the next
   workload phase.

### 12.4 Single-Workload Cycles (Default)

If `workload_sequence` is absent from `applied_defaults`, the cycle
behaves exactly as today: a single run with `workload_type=None` and
no inter-workload gates. This preserves full backwards compatibility.

------------------------------------------------------------------------

## 13. Multi-Workload Cycle Pattern

### 13.1 Recommended Cycle Shape

The Planning -> Implementation -> Evaluation shape is the recommended
default multi-workload pattern for 1.0, but **not a required executor
topology**. Simpler single-workload cycles and alternative bounded
workload sequences remain valid. The executor must not enforce this
specific pattern; it processes whatever `workload_sequence` is provided
(or none at all).

The SIP defines the recommended shape as:

```
Cycle
├── Planning Run (workload_type: "planning")
│   ├── strategy.plan tasks
│   ├── Pulse checks (SIP-0070)
│   └── Artifacts: plan.md, acceptance_criteria.json
│
├── progress_plan_review Gate
│   └── Human reviews plan → approved / approved_with_refinements / returned_for_revision / rejected
│
├── [Optional] Refinement Run (workload_type: "refinement")
│   └── Only if returned_for_revision
│
├── Implementation Run (workload_type: "implementation")
│   ├── development.implement / development.build / qa.validate tasks
│   ├── Pulse checks (SIP-0070)
│   └── Artifacts: code files, test reports, build output
│
└── Evaluation Run (workload_type: "evaluation")
    ├── data.analyze / governance.closeout tasks
    └── Artifacts: scorecard, closeout report
```

### 13.2 Execution Flow

1. **Executor reads `workload_sequence`** from `applied_defaults`.
2. For each workload entry, the executor creates a Run with the
   specified `workload_type` and dispatches the appropriate task plan.
3. After each run completes, the executor checks whether a gate
   follows. If so, it pauses the cycle (sets run status to `paused`)
   and waits for a gate decision.
4. Gate decision determines next action:
   - `approved` -> proceed to next workload.
   - `approved_with_refinements` -> proceed; notes recorded.
   - `returned_for_revision` -> create a new run with
     `workload_type="refinement"` in the same workload phase.
   - `rejected` -> cycle fails or is cancelled (per policy).
5. If no gate follows, proceed to the next workload automatically.

### 13.3 Prefect Integration

One Prefect flow per Cycle. Workload boundaries are task-plan
boundaries within the flow, not separate flows. This avoids Prefect
flow proliferation and keeps the executor simple.

The flow run name already encodes `{project_id}/{cycle_id}/{run_id}`.
Workload type appears in the run metadata (tags or parameters) for
Prefect UI filtering.

------------------------------------------------------------------------

## 14. Pulse vs Gate Clarification

### 14.1 Semantic Boundary

| Aspect | Pulse Check (SIP-0070) | Gate (this SIP + SIP-0064) |
|--------|------------------------|---------------------------|
| **Scope** | Within a Run | Between Runs / workload phases |
| **Trigger** | Cadence limits (automatic) | Completion of a workload run (explicit) |
| **Decision** | PASS/FAIL/EXHAUSTED (automatic) | approved/rejected/... (human or policy) |
| **Run State** | Stays `RUNNING` | Transitions to `PAUSED` |
| **Purpose** | "Safe to continue this run?" | "Ready to move to next phase?" |
| **Defined in** | `defaults.pulse_checks` | `task_flow_policy.gates` |

### 14.2 What Changes in SIP-0070 Behavior

**Nothing.** This SIP does not modify SIP-0070's Pulse Check behavior,
configuration, or implementation. The clarification is purely
terminological:

- SIP-0070 already defines Pulse Checks as automatic, in-run,
  mechanical verification. This SIP affirms that definition.
- SIP-0070 already distinguishes Pulse Checks from Gates (Section 4:
  "Gate: A human decision point... distinct from pulse checks"). This
  SIP reinforces that distinction with the workload concept.

### 14.3 Terminology Enforcement

The terminology clarification is enforced through:

1. **Cycle request profile schema**: `pulse_checks` go in
   `defaults.pulse_checks`; gates go in
   `defaults.task_flow_policy.gates`. No cross-contamination.
2. **API routes**: pulse verification records are on the run; gate
   decisions are on the run but semantically between workload phases.
3. **Documentation**: all new docs use "pulse check" for in-run
   verification and "gate" for inter-workload decisions.

------------------------------------------------------------------------

## 15. Telemetry

### 15.1 Event Context Additions

The existing Cycle Event System gains `workload_type` in event context
for runs that have it set. All events emitted during a run include
`workload_type` in their context payload when it is non-null.

Affected event families:
- `cycle.run.*` events (started, completed, failed, cancelled)
- `pulse_check.*` events (started, passed, failed, exhausted)
- `task.*` events (dispatched, completed)

### 15.2 New Events

| Event Name | Emitted When | Fields |
|------------|-------------|--------|
| `artifact.promoted` | Artifact promotion_status changes to "promoted" | `artifact_id`, `artifact_type`, `cycle_id`, `run_id`, `promoted_by` |
| `gate.decided` | Gate decision recorded (all values) | `gate_name`, `decision`, `decided_by`, `run_id`, `cycle_id`, `workload_type` |
| `workload.started` | A new run with `workload_type` begins | `workload_type`, `run_id`, `cycle_id` |
| `workload.completed` | A run with `workload_type` reaches terminal state | `workload_type`, `run_id`, `cycle_id`, `status` |

`workload.started` and `workload.completed` are **explicitly emitted
events**, not derived projections of `cycle.run.*` events. The executor
emits them as separate calls to `LLMObservabilityPort.record_event()`
when a run with a non-null `workload_type` begins or reaches a terminal
state. This ensures downstream consumers can depend on them without
ambiguity about whether they are real or inferred.

### 15.3 LangFuse Integration

Workload type is included as a tag on LangFuse traces when the adapter
is active. This allows filtering LangFuse traces by workload phase.

------------------------------------------------------------------------

## 16. Backwards Compatibility

### 16.1 Domain Model

- `Run.workload_type` defaults to `None`. Existing code that constructs
  `Run` instances without `workload_type` is unaffected.
- `ArtifactRef.promotion_status` defaults to `"working"`. Existing code
  that constructs `ArtifactRef` instances without `promotion_status` is
  unaffected.
- `GateDecisionValue` gains two new members. Existing code that uses
  `APPROVED` or `REJECTED` is unaffected. The API DTO's `Literal` type
  expands but existing payloads with `"approved"` or `"rejected"` remain
  valid.

### 16.2 Database

- `workload_type` column is nullable. Existing rows have `NULL`.
- No backfill is required.
- Existing gate decisions with `"approved"` or `"rejected"` values
  remain valid.

### 16.3 API

- New fields on `RunResponse` and `ArtifactRefResponse` are optional
  with defaults. Existing API consumers that ignore unknown fields are
  unaffected.
- New query parameters (`?workload_type=`, `?promotion_status=`) are
  optional. Omitting them returns all results (existing behavior).
- Existing gate decision payloads (`"approved"`, `"rejected"`) remain
  valid.

### 16.4 Cycle Request Profiles

- Existing cycle request profiles without `workload_sequence` continue
  to work. The cycle behaves as a single-run, no-workload-type cycle.
- No existing profile keys are removed or renamed.

------------------------------------------------------------------------

## 17. Rollout Plan

### Phase 1: Domain Model and DDL (Foundation)

1. `WorkloadType` and `PromotionStatus` helper classes in
   `src/squadops/cycles/models.py`.
2. `workload_type: str | None = None` field on `Run` dataclass.
3. `promotion_status: str = "working"` field on `ArtifactRef` dataclass.
4. `GateDecisionValue` expanded with `APPROVED_WITH_REFINEMENTS` and
   `RETURNED_FOR_REVISION`.
5. DDL migration `004_workload_canon.sql` with `workload_type` column.
6. Unit tests for model construction, defaults, and field access.

**Success gate:** All existing tests pass. New model tests pass.
`run_new_arch_tests.sh` green.

### Phase 2: API Changes

1. `RunResponse` DTO gains `workload_type`.
2. `ArtifactRefResponse` DTO gains `promotion_status`.
3. `GateDecisionRequest` DTO expanded `Literal` type.
4. `run_to_response()` and `artifact_to_response()` mapping updated.
5. `list_runs` route gains `?workload_type=` filter parameter.
6. `CycleRegistryPort.list_runs()` gains `workload_type` filter.
7. Both registry adapters (memory, Postgres) implement the filter.
8. Unit tests for API routes, DTOs, and mapping.

**Success gate:** All API tests pass. Existing clients unaffected.

### Phase 3: Artifact Promotion

1. `ArtifactVaultPort.promote_artifact()` method.
2. Filesystem vault adapter implements promotion.
3. `POST /artifacts/{artifact_id}/promote` route.
4. Artifact list endpoints gain `?promotion_status=` filter.
5. `ArtifactVaultPort.list_artifacts()` gains `promotion_status` filter.
6. Unit tests for promotion logic and API.

**Success gate:** Promotion round-trip works end-to-end.

### Phase 4: Cycle Request Profile and Executor Integration

1. `workload_sequence` added to `_APPLIED_DEFAULTS_EXTRA_KEYS`.
2. Executor reads `workload_sequence` and sets `workload_type` on runs.
3. Executor pauses at gate boundaries between workload phases.
4. Telemetry events emitted for workload transitions.
5. Reference cycle request profile with multi-workload sequence.
6. Integration tests for multi-workload cycle flow.

**Success gate:** Multi-workload cycle completes end-to-end with
correct workload_type on each run and gate decisions between phases.

------------------------------------------------------------------------

## 18. Key Design Decisions

1. **Workload is a Run classification, not a new entity** (Option B from
   the IDEA). Adding `workload_type` to Run is the minimum viable
   change. A full Workload entity can come later if the domain model
   demands it, but 1.0 should not over-engineer.

2. **`workload_type` is free-form `str | None` with well-known
   constants** (resolved from Open Question 1). Follows the existing
   `ArtifactType` pattern. Extensible without code changes; standard
   values documented in `WorkloadType` helper class.

3. **No separate "workload view" endpoint** (resolved from Open Question
   2). Add `?workload_type=` filter to existing `list_runs`. Console
   groups by workload_type client-side.

4. **Artifact promotion is independently callable via API** (resolved
   from Open Question 3). Gate decisions MAY trigger promotion as a
   side effect, but promotion is not gate-locked. This keeps the model
   flexible for pipeline protocol SIPs.

5. **One Prefect flow per Cycle** (resolved from Open Question 4).
   Workload boundaries are task-plan boundaries within the flow, not
   separate flows. Avoids Prefect flow proliferation.

6. **`workload_type` set at run creation time** (resolved from Open
   Question 5). Cycle request profiles specify a `workload_sequence` in
   `applied_defaults`. The executor sets `workload_type` when creating
   runs for each workload phase.

7. **Gate outcomes are richer than binary** ---
   `approved_with_refinements` enables tracked plan feedback without
   forcing reject-and-redo cycles.

8. **No HIL gates inside normal workload runs by default** --- human
   intervention belongs at workload boundaries, not as interior pause
   points. In-run health is Pulse's job.

9. **Evaluation workload starts automatically** --- no HIL gate between
   implementation and evaluation by default. Analysis is most valuable
   when the run did not go well; gating it suppresses the feedback loop.

10. **Artifact promotion is explicit and one-way** --- prevents noise,
    stale drafts, and half-baked outputs from becoming canonical cycle
    state. No demotion operation.

11. **Gate role by naming convention** --- `progress_*` and `promote_*`
    prefixes express intent without adding a field to the Gate dataclass.
    A field can be added later if convention proves insufficient.

------------------------------------------------------------------------

## 19. Acceptance Criteria

1. `Run` dataclass includes `workload_type: str | None = None` field.
   Test: construct a `Run` with and without `workload_type`; verify
   field access and default.

2. `WorkloadType` helper class defines `PLANNING`, `IMPLEMENTATION`,
   `EVALUATION`, `REFINEMENT` constants.

3. Postgres DDL migration `004_workload_canon.sql` adds `workload_type`
   column to `cycle_runs`. Migration is idempotent.

4. `GateDecisionValue` enum includes `APPROVED`,
   `APPROVED_WITH_REFINEMENTS`, `RETURNED_FOR_REVISION`, `REJECTED`.
   Test: all four values are valid `GateDecisionValue` members.

5. `GateDecisionRequest` DTO accepts all four decision values. Test:
   validate request with each value; reject unknown values.

6. `ArtifactRef` dataclass includes
   `promotion_status: str = "working"` field. Test: default is
   `"working"`; can be set to `"promoted"`.

7. `PromotionStatus` helper class defines `WORKING` and `PROMOTED`
   constants.

8. `RunResponse` DTO includes `workload_type: str | None = None`.

9. `ArtifactRefResponse` DTO includes
   `promotion_status: str = "working"`.

10. `GET .../runs?workload_type=planning` filters runs by workload type.
    Test: create runs with different workload types; filter returns
    correct subset.

11. `POST /artifacts/{artifact_id}/promote` promotes an artifact. Test:
    artifact transitions from `working` to `promoted`; promotion is
    idempotent.

12. `ArtifactVaultPort` includes `promote_artifact()` abstract method.
    Both adapters implement it.

13. `_APPLIED_DEFAULTS_EXTRA_KEYS` includes `"workload_sequence"`.

14. Mapping functions `run_to_response()` and `artifact_to_response()`
    include the new fields.

15. Existing tests pass without modification. New tests cover workload
    classification, gate outcomes, and artifact promotion.

16. `list_artifacts` endpoints accept `?promotion_status=` filter.

17. When a progression gate is decided as `returned_for_revision`, the
    cycle does not advance to the next workload phase. A subsequent run
    may be created for the same workload path without mutating prior run
    history. Test: create a planning run, decide gate as
    `returned_for_revision`, verify workload sequence pointer does not
    advance, create refinement run, verify original run is unchanged.

18. A run awaiting a progression gate remains gate-decidable and is not
    treated as terminal before gate outcome is recorded. Test: complete
    a workload run with a gate, verify run status is `paused` (not
    `completed`), verify `record_gate_decision()` succeeds.

19. `set_baseline` rejects working artifacts. Test: attempt to set a
    `working` artifact as baseline, verify validation error. Promote
    the artifact, then set as baseline, verify success.

20. Gate names referenced in `workload_sequence` must use `progress_`
    or `promote_` prefix. Test: cycle request profile with non-prefixed
    gate name in `workload_sequence` is rejected at validation time.

21. `workload_type` input validation: empty string rejected, whitespace
    trimmed, non-empty string preserved. Test: submit `""`, `"  "`,
    `" planning "` and verify rejection/trimming behavior.

------------------------------------------------------------------------

## 20. Source Ideas

- `docs/ideas/IDEA-cycle-workload-run-gate-mehta-modern-canon.md` ---
  full concept exploration of the Cycle/Workload/Run/Pulse/Gate
  hierarchy, artifact promotion, gate semantics, and MEH-ta evaluation
  path.
