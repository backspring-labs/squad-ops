# SIP-0076: Workload & Gate Canon — Implementation Plan

## Context

SIP-0076 introduces workload classification on runs, expanded gate decision values, artifact promotion, and cycle request profile integration for multi-workload cycles. The accepted SIP is at `sips/accepted/SIP-0076-Workload-Gate-Canon.md` (rev 3, 21 acceptance criteria).

The implementation touches domain models, DDL, ports, adapters (memory + Postgres registries, filesystem vault), API routes/DTOs, cycle request profile schema, CLI, and telemetry. All changes are additive — no existing fields, tables, or endpoints are modified or removed.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | `WorkloadType` is a constants class, not an enum | Follows existing `ArtifactType` pattern; free-form `str` is extensible without code changes (SIP §7.1) |
| D2 | `workload_type` field is last among optional fields on `Run` | Preserves positional-argument compatibility; keyword-only construction unaffected (SIP §7.2) |
| D3 | `promotion_status` field is last on `ArtifactRef` (after `vault_uri`) | Same rationale as D2 (SIP §7.6) |
| D4 | Gate role by naming convention (`progress_*`/`promote_*`), not a field | No schema change on Gate dataclass or `task_flow_policy` JSONB (SIP §10.1) |
| D5 | Promotion endpoint is idempotent end-to-end (`200`, no `409`) | Cleaner for automation, retry-safe, simpler for CLI/UI (SIP §9.5, tightening #4) |
| D6 | `set_baseline` rejects working artifacts | Only promoted artifacts are baseline-eligible (SIP §11.3, tightening #9) |
| D7 | Gate-awaiting runs use `paused` status, not `completed` | `record_gate_decision()` rejects terminal runs; `paused` keeps run gate-decidable (SIP §10.3, tightening #1) |
| D8 | `returned_for_revision` stays on current workload path | Refinement is a retry within the current phase, not a sibling workload (SIP §10.5, tightening #2) |
| D9 | `workload_type` input validation: trim whitespace, reject empty, preserve case | Prevents data-quality drift in stored run classifications (SIP §9.8, tightening #8) |
| D10 | `refinement` is convention, not executor control plane | Executor must not hardcode behavior on the string; meaning comes from gate outcome (SIP §7.1, tightening #6) |
| D11 | Gate names in `workload_sequence` must use `progress_`/`promote_` prefix | Rejected at cycle request profile validation time (SIP §10.1, tightening #7) |
| D12 | `workload.*` telemetry events are explicit emissions, not derived projections | Downstream consumers can depend on them without ambiguity (SIP §15.2, tightening #10) |
| D13 | CLI `gate decide` gains `--with-refinements` and `--return-for-revision` flags | Extends existing `--approve`/`--reject` pattern (SIP §7.5) |
| D14 | `workload_type` validation is centralized in a shared helper, not API-only | Executor and CLI also create runs; all paths must get the same trim/reject-empty behavior (plan tightening #2) |
| D15 | `promotion_status` filter rejects unknown values with 422 | Avoids silent empty responses on typos; cleaner API contract (plan tightening #3) |
| D16 | `set_baseline` promotion check reads authoritative vault state | Must call `vault.get_metadata()` for current `promotion_status`; never trust stale/client-supplied state (plan tightening #4) |
| D17 | Filtered `list_runs()` preserves existing ordering contract | Workload type filter does not change result ordering (plan tightening #5) |
| D18 | Gate prefix validation in `workload_sequence` is case-sensitive | No normalization; `Progress_plan_review` is rejected (plan tightening #6) |
| D19 | Legacy artifacts without `promotion_status` default to `"working"` at read time only | Metadata is only rewritten on next mutation, not opportunistically backfilled on read (plan tightening #8) |
| D20 | CLI exits with usage error listing valid flags when no decision flag is provided | Standard Typer mutually exclusive group behavior, explicitly stated (plan tightening #9) |

---

## Phase 1: Domain Model and DDL (Foundation)

All work in this phase is pure domain model and schema — no API, no adapter logic changes.

### 1.1 Add `WorkloadType` constants class

**File:** `src/squadops/cycles/models.py`

Add after existing `RunInitiator` class:

```python
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

### 1.2 Add `PromotionStatus` constants class

**File:** `src/squadops/cycles/models.py`

Add after `WorkloadType`:

```python
class PromotionStatus:
    """Well-known artifact promotion status constants."""
    WORKING = "working"
    PROMOTED = "promoted"
```

### 1.3 Extend `Run` dataclass with `workload_type`

**File:** `src/squadops/cycles/models.py`

Add `workload_type: str | None = None` as the last field on `Run` (after `artifact_refs`). This is D2 — positional-argument compatibility preserved.

### 1.4 Extend `ArtifactRef` dataclass with `promotion_status`

**File:** `src/squadops/cycles/models.py`

Add `promotion_status: str = "working"` as the last field on `ArtifactRef` (after `vault_uri`). This is D3.

### 1.5 Expand `GateDecisionValue` enum

**File:** `src/squadops/cycles/models.py`

Add two new members:

```python
class GateDecisionValue(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_REFINEMENTS = "approved_with_refinements"
    RETURNED_FOR_REVISION = "returned_for_revision"
    REJECTED = "rejected"
```

### 1.6 Add `validate_workload_type()` helper

**File:** `src/squadops/cycles/models.py`

Centralized validation for `workload_type` input (D14). Used by API routes, executor, and CLI — all run creation paths get the same behavior.

```python
def validate_workload_type(value: str | None) -> str | None:
    """Validate and normalize a workload_type value.

    Rules (SIP §9.8):
    - None is valid (legacy/unclassified run).
    - Leading/trailing whitespace is trimmed.
    - Empty string after trim is rejected (ValidationError).
    - Supplied value is preserved exactly after trim (no case normalization).
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise ValidationError("workload_type must be a non-empty string or null")
    return trimmed
```

### 1.7 DDL migration

**New file:** `infra/migrations/004_workload_canon.sql`

```sql
-- 004_workload_canon.sql
-- SIP-0076 Workload & Gate Canon: workload_type on runs.
-- All DDL is idempotent.

ALTER TABLE cycle_runs
    ADD COLUMN IF NOT EXISTS workload_type TEXT;

CREATE INDEX IF NOT EXISTS idx_cycle_runs_workload_type
    ON cycle_runs(workload_type)
    WHERE workload_type IS NOT NULL;
```

No artifact table DDL — filesystem vault stores promotion_status in metadata.

### 1.7 Tests

**New file:** `tests/unit/cycles/test_workload_canon_models.py`

Tests (covers ACs 1, 2, 4, 6, 7):
- `Run` constructed without `workload_type` defaults to `None`
- `Run` constructed with `workload_type="planning"` stores value
- `WorkloadType.PLANNING` == `"planning"` (and other constants)
- `ArtifactRef` constructed without `promotion_status` defaults to `"working"`
- `ArtifactRef` constructed with `promotion_status="promoted"` stores value
- `PromotionStatus.WORKING` == `"working"`, `PromotionStatus.PROMOTED` == `"promoted"`
- All four `GateDecisionValue` members are valid StrEnum values
- Existing `Run` construction (without new field) still works (backward compat)
- Existing `ArtifactRef` construction (without new field) still works

**Success gate:** `run_new_arch_tests.sh` green. All existing tests pass unchanged.

---

## Phase 2: API Changes

### 2.1 Extend `RunResponse` DTO

**File:** `src/squadops/api/routes/cycles/dtos.py`

Add `workload_type: str | None = None` to `RunResponse`.

### 2.2 Extend `ArtifactRefResponse` DTO

**File:** `src/squadops/api/routes/cycles/dtos.py`

Add `promotion_status: str = "working"` to `ArtifactRefResponse`.

### 2.3 Expand `GateDecisionRequest` DTO

**File:** `src/squadops/api/routes/cycles/dtos.py`

Expand `decision` Literal type:

```python
decision: Literal[
    "approved",
    "approved_with_refinements",
    "returned_for_revision",
    "rejected",
]
```

### 2.4 Update mapping functions

**File:** `src/squadops/api/routes/cycles/mapping.py`

- `run_to_response()`: add `workload_type=run.workload_type`
- `artifact_to_response()`: add `promotion_status=artifact.promotion_status`

### 2.5 Add `workload_type` filter to `list_runs` route

**File:** `src/squadops/api/routes/cycles/runs.py`

Add `workload_type: str | None = None` query parameter to `list_runs()`. Pass through to `registry.list_runs(cycle_id, workload_type=workload_type)`.

Filtered results preserve the same default ordering as unfiltered `list_runs()` (D17). The filter is a WHERE clause, not a re-sort.

### 2.6 Extend `CycleRegistryPort.list_runs()`

**File:** `src/squadops/ports/cycles/cycle_registry.py`

Add `workload_type: str | None = None` keyword parameter to the abstract `list_runs()` method.

### 2.7 Update MemoryCycleRegistry adapter

**File:** `adapters/cycles/memory_cycle_registry.py`

- `create_run()`: persist `workload_type` from the `Run` object
- `list_runs()`: accept `workload_type` parameter; filter results when non-None
- `_to_run_snapshot()` or equivalent: include `workload_type` in the frozen snapshot

### 2.8 Update PostgresCycleRegistry adapter

**File:** `adapters/cycles/postgres_cycle_registry.py`

- `create_run()`: include `workload_type` in INSERT columns
- `list_runs()`: add `AND workload_type = $N` clause when parameter is non-None
- `_row_to_run()` or equivalent: read `workload_type` from DB row

### 2.9 Add `workload_type` to `create_run` route

**File:** `src/squadops/api/routes/cycles/runs.py`

Accept optional `workload_type` in request body for retry runs. Call `validate_workload_type()` (D14) — the centralized helper from Phase 1.6. This ensures API, executor, and CLI paths all get the same trim/reject-empty behavior.

### 2.10 Tests

**New file:** `tests/unit/api/test_workload_canon_api.py`

Tests (covers ACs 5, 8, 9, 10, 14):
- `RunResponse` serialization includes `workload_type`
- `ArtifactRefResponse` serialization includes `promotion_status`
- `GateDecisionRequest` validates all four decision values
- `GateDecisionRequest` rejects unknown decision value
- `run_to_response()` maps `workload_type` correctly
- `artifact_to_response()` maps `promotion_status` correctly
- `list_runs` with `?workload_type=planning` returns filtered results
- `list_runs` without filter returns all runs
- `workload_type` input validation: empty string rejected, whitespace trimmed (AC 21)

**File:** `tests/unit/cycles/test_memory_registry_workload.py`

Tests for MemoryCycleRegistry:
- `create_run` with `workload_type` persists it
- `list_runs` with `workload_type` filter returns correct subset
- `list_runs` without filter returns all runs

**Success gate:** All API tests pass. All existing tests pass unchanged.

---

## Phase 3: Artifact Promotion

### 3.1 Add `promote_artifact()` to `ArtifactVaultPort`

**File:** `src/squadops/ports/cycles/artifact_vault.py`

```python
@abstractmethod
async def promote_artifact(self, artifact_id: str) -> ArtifactRef:
    """Promote an artifact from 'working' to 'promoted'.

    Promotion is one-way and idempotent.

    Raises:
        ArtifactNotFoundError: If the artifact_id is not found.
    """
```

### 3.2 Add `promotion_status` filter to `list_artifacts()`

**File:** `src/squadops/ports/cycles/artifact_vault.py`

Add `promotion_status: str | None = None` parameter to `list_artifacts()`.

### 3.3 Implement in FilesystemArtifactVault

**File:** `adapters/cycles/filesystem_artifact_vault.py`

- `promote_artifact()`: load metadata, set `promotion_status` to `"promoted"` via `dataclasses.replace()`, persist updated metadata JSON. Idempotent — already-promoted returns unchanged.
- `store()`: ensure `promotion_status` is included in metadata JSON serialization.
- `list_artifacts()`: filter by `promotion_status` when parameter is non-None.
- `get_metadata()`: ensure `promotion_status` is read from metadata JSON, defaulting to `"working"` for legacy artifacts without it. This default is read-time only (D19) — metadata is not rewritten to disk on read. Legacy metadata is only updated on the next mutation (e.g., `promote_artifact()` or `store()`).

### 3.4 Add `set_baseline` promotion check

**File:** `src/squadops/api/routes/cycles/artifacts.py` (route level, per T6 pattern)

In `promote_baseline()` route: before calling `vault.set_baseline()`, read the artifact's current metadata from the vault via `vault.get_metadata(body.artifact_id)` (D16) and check that `promotion_status` is `"promoted"`. If `"working"`, raise validation error. This is D6. The check must use the authoritative vault record, never client-supplied or stale state.

### 3.5 Add promotion API route

**File:** `src/squadops/api/routes/cycles/artifacts.py`

```python
@router.post("/artifacts/{artifact_id}/promote")
async def promote_artifact(artifact_id: str):
    """Promote an artifact to cycle-scoped canonical status (SIP-0076 §9.5)."""
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
        promoted = await vault.promote_artifact(artifact_id)
        return artifact_to_response(promoted)
    except CycleError as e:
        raise handle_cycle_error(e) from e
```

Idempotent: returns `200` for already-promoted artifacts (D5).

### 3.6 Add `promotion_status` filter to artifact list routes

**File:** `src/squadops/api/routes/cycles/artifacts.py`

Add `promotion_status: str | None = None` query parameter to:
- `list_project_artifacts()`
- `list_cycle_artifacts()`
- `list_run_artifacts()`

Validate the filter value before passing through: reject unknown values (anything other than `"working"`, `"promoted"`, or `None`) with `422 VALIDATION_ERROR` (D15). This prevents silent empty responses on typos like `?promotion_status=promtoed`.

Pass through to `vault.list_artifacts(..., promotion_status=promotion_status)`.

### 3.7 Tests

**New file:** `tests/unit/cycles/test_artifact_promotion.py`

Tests (covers ACs 11, 12, 16, 19):
- `promote_artifact()` changes `promotion_status` from `"working"` to `"promoted"`
- `promote_artifact()` on already-promoted artifact returns unchanged (idempotent)
- `promote_artifact()` on unknown artifact_id raises `ArtifactNotFoundError`
- `list_artifacts(promotion_status="promoted")` returns only promoted
- `list_artifacts(promotion_status="working")` returns only working
- `list_artifacts()` without filter returns all
- `set_baseline` rejects working artifacts with validation error
- `set_baseline` succeeds for promoted artifacts

**New file:** `tests/unit/api/test_artifact_promotion_api.py`

Tests for API route:
- `POST /artifacts/{id}/promote` returns 200 with promoted artifact
- `POST /artifacts/{id}/promote` on already-promoted returns 200 (idempotent)
- `POST /artifacts/{id}/promote` on unknown returns 404
- Artifact list endpoints accept `?promotion_status=` filter

**Success gate:** Promotion round-trip works. Baseline rejects working artifacts.

---

## Phase 4: Cycle Request Profile and Gate Validation

### 4.1 Add `workload_sequence` to `_APPLIED_DEFAULTS_EXTRA_KEYS`

**File:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add `"workload_sequence"` to the set.

### 4.2 Add `workload_sequence` gate name validation

**File:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add a field validator for `defaults` that checks: if `workload_sequence` is present, any non-null `gate` value must start with `progress_` or `promote_`. Matching is case-sensitive (D18) — `Progress_plan_review` is rejected. Reject non-conforming gate names with a clear error message (D11).

### 4.3 Add reference cycle request profile

**New file:** `src/squadops/contracts/cycle_request_profiles/profiles/multi-phase.yaml`

This profile is a **reference example**, not a required executor topology or mandatory 1.0 default. Single-workload cycles and alternative workload sequences remain valid.

```yaml
# Reference example — not a required executor topology.
name: multi-phase
description: "Planning → Implementation → Evaluation multi-workload cycle"
defaults:
  squad_profile_id: full-squad
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: progress_plan_review
        description: "Human reviews plan before implementation"
        after_task_types: []
  workload_sequence:
    - type: planning
      gate: progress_plan_review
    - type: implementation
      gate: null
    - type: evaluation
      gate: null
```

### 4.4 Extend CLI `gate decide` with new decision values

**File:** `src/squadops/cli/commands/runs.py`

Add `--with-refinements` and `--return-for-revision` flags alongside existing `--approve`/`--reject`. Wire mapping:
- `--approve` -> `"approved"` (unchanged)
- `--reject` -> `"rejected"` (unchanged)
- `--with-refinements` -> `"approved_with_refinements"`
- `--return-for-revision` -> `"returned_for_revision"`

Exactly one flag must be provided (mutually exclusive group). If no decision flag is provided, the CLI exits with a usage error and clear guidance listing valid flags (D20).

### 4.5 Tests

**New file:** `tests/unit/contracts/test_workload_sequence_schema.py`

Tests (covers ACs 13, 20):
- `workload_sequence` accepted in CRP defaults (not rejected as unknown key)
- Gate name `progress_plan_review` in `workload_sequence` passes validation
- Gate name `promote_plan_artifact` in `workload_sequence` passes validation
- Gate name `my_custom_gate` in `workload_sequence` rejected with clear error
- `null` gate in `workload_sequence` passes validation
- CRP without `workload_sequence` passes validation (backward compat)

**New file:** `tests/unit/cli/test_gate_decision_values.py`

Tests for expanded CLI flags:
- `--with-refinements` sends `"approved_with_refinements"`
- `--return-for-revision` sends `"returned_for_revision"`
- Flags are mutually exclusive

**Success gate:** Profile validation enforces gate naming. CLI supports all four decision values.

---

## Phase 5: Gate Boundary Semantics and Negative-Path Tests

This phase covers the behavioral contracts introduced by the tightenings. These are primarily test-level validations against existing domain logic — minimal new code, mostly new test coverage.

The production code that enforces gate-boundary semantics already exists: `CycleRegistryPort.record_gate_decision()` checks for terminal status before accepting a decision (rejecting `completed`/`failed`/`cancelled` with `RunTerminalError`). Phase 5 tests validate that `paused` is correctly excluded from the terminal set, ensuring gate-awaiting runs remain decidable. The executor code that sets runs to `paused` at gate boundaries is a concern for the pipeline/executor SIPs — SIP-0076 defines the vocabulary and invariants, not the orchestration.

### 5.1 Gate-awaiting run status test

**New file:** `tests/unit/cycles/test_gate_boundary_status.py`

Tests (covers AC 18):
- A run with `status="paused"` accepts `record_gate_decision()` (not rejected as terminal)
- A run with `status="completed"` rejects `record_gate_decision()` with `RunTerminalError`
- Verify that `paused` is not in the terminal state set

### 5.2 `returned_for_revision` workload sequencing test

**New file:** `tests/unit/cycles/test_returned_for_revision.py`

Tests (covers AC 17):
- Record gate decision `returned_for_revision` on a run
- Verify original run's gate decision is immutable
- Create a new run for the same workload path (same or refinement workload_type)
- Verify both runs coexist with independent gate decisions

### 5.3 Version bump

**File:** `pyproject.toml` — bump version from `0.9.13` to `0.9.14`.

### 5.4 Regression suite

Run `./scripts/dev/run_new_arch_tests.sh -v` and verify all tests pass including new ones.

**Success gate:** `run_new_arch_tests.sh` green. All 21 acceptance criteria covered by tests.

---

## Files Modified (Summary)

| File | Phase | Action |
|------|-------|--------|
| `src/squadops/cycles/models.py` | 1 | Add `WorkloadType`, `PromotionStatus`, extend `Run`, `ArtifactRef`, `GateDecisionValue` |
| `infra/migrations/004_workload_canon.sql` | 1 | New DDL migration |
| `src/squadops/api/routes/cycles/dtos.py` | 2 | Extend `RunResponse`, `ArtifactRefResponse`, `GateDecisionRequest` |
| `src/squadops/api/routes/cycles/mapping.py` | 2 | Update `run_to_response()`, `artifact_to_response()` |
| `src/squadops/api/routes/cycles/runs.py` | 2 | Add `workload_type` filter + input validation |
| `src/squadops/ports/cycles/cycle_registry.py` | 2 | Add `workload_type` param to `list_runs()` |
| `adapters/cycles/memory_cycle_registry.py` | 2 | Implement `workload_type` filter |
| `adapters/cycles/postgres_cycle_registry.py` | 2 | Implement `workload_type` column + filter |
| `src/squadops/ports/cycles/artifact_vault.py` | 3 | Add `promote_artifact()`, `promotion_status` filter |
| `adapters/cycles/filesystem_artifact_vault.py` | 3 | Implement promotion + filter |
| `src/squadops/api/routes/cycles/artifacts.py` | 3 | Add promotion route, baseline check, `promotion_status` filter |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | 4 | Add `workload_sequence` to extra keys + gate name validation |
| `src/squadops/contracts/cycle_request_profiles/profiles/multi-phase.yaml` | 4 | New reference profile |
| `src/squadops/cli/commands/runs.py` | 4 | Add `--with-refinements`, `--return-for-revision` flags |
| `pyproject.toml` | 5 | Version bump 0.9.13 -> 0.9.14 |

## New Test Files

| File | Phase | Coverage |
|------|-------|----------|
| `tests/unit/cycles/test_workload_canon_models.py` | 1 | ACs 1, 2, 4, 6, 7 |
| `tests/unit/api/test_workload_canon_api.py` | 2 | ACs 5, 8, 9, 10, 14, 21 |
| `tests/unit/cycles/test_memory_registry_workload.py` | 2 | AC 10 (adapter) |
| `tests/unit/cycles/test_artifact_promotion.py` | 3 | ACs 11, 12, 16, 19 |
| `tests/unit/api/test_artifact_promotion_api.py` | 3 | ACs 11, 16 (route) |
| `tests/unit/contracts/test_workload_sequence_schema.py` | 4 | ACs 13, 20 |
| `tests/unit/cli/test_gate_decision_values.py` | 4 | AC 5 (CLI) |
| `tests/unit/cycles/test_gate_boundary_status.py` | 5 | AC 18 |
| `tests/unit/cycles/test_returned_for_revision.py` | 5 | AC 17 |

## Acceptance Criteria Coverage

| AC | Description | Test File | Phase |
|----|-------------|-----------|-------|
| 1 | `Run.workload_type` field | `test_workload_canon_models.py` | 1 |
| 2 | `WorkloadType` constants | `test_workload_canon_models.py` | 1 |
| 3 | DDL migration | Manual: verify column exists, index exists, existing rows readable with `workload_type=NULL` | 1 |
| 4 | `GateDecisionValue` expanded | `test_workload_canon_models.py` | 1 |
| 5 | `GateDecisionRequest` DTO | `test_workload_canon_api.py` | 2 |
| 6 | `ArtifactRef.promotion_status` | `test_workload_canon_models.py` | 1 |
| 7 | `PromotionStatus` constants | `test_workload_canon_models.py` | 1 |
| 8 | `RunResponse.workload_type` | `test_workload_canon_api.py` | 2 |
| 9 | `ArtifactRefResponse.promotion_status` | `test_workload_canon_api.py` | 2 |
| 10 | `list_runs` workload filter | `test_workload_canon_api.py` + `test_memory_registry_workload.py` | 2 |
| 11 | Promotion endpoint | `test_artifact_promotion.py` + `test_artifact_promotion_api.py` | 3 |
| 12 | `promote_artifact()` port method | `test_artifact_promotion.py` | 3 |
| 13 | `_APPLIED_DEFAULTS_EXTRA_KEYS` | `test_workload_sequence_schema.py` | 4 |
| 14 | Mapping functions | `test_workload_canon_api.py` | 2 |
| 15 | Existing tests pass | `run_new_arch_tests.sh` | 5 |
| 16 | Artifact list filter | `test_artifact_promotion.py` + `test_artifact_promotion_api.py` | 3 |
| 17 | `returned_for_revision` sequencing | `test_returned_for_revision.py` | 5 |
| 18 | Gate-awaiting run status | `test_gate_boundary_status.py` | 5 |
| 19 | Baseline rejects working | `test_artifact_promotion.py` | 3 |
| 20 | Gate naming validation | `test_workload_sequence_schema.py` | 4 |
| 21 | `workload_type` input validation | `test_workload_canon_api.py` | 2 |
