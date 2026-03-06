# Plan: SIP-0080 Wrap-Up Workload Protocol Implementation

## Context

SIP-0080 defines the Wrap-Up Workload Protocol — the terminal phase of a SquadOps Cycle that adjudicates implementation outcomes and produces structured closeout and handoff artifacts. Wrap-up is not cleanup or narration; it is evidence-backed adjudication with six-level confidence classification.

The SIP builds on SIP-0076 (Workload & Gate Canon), SIP-0077 (Cycle Event System), SIP-0078 (Planning Workload Protocol), and SIP-0079 (Implementation Run Contract). It requires **no executor changes, no API changes, no CLI changes, and no new event types** — wrap-up workloads plug into the existing dispatch, chaining, pulse check, and gate mechanisms.

**Branch:** `feature/sip-wrapup-workload-protocol` (off main)
**SIP:** `sips/accepted/SIP-0080-Wrap-Up-Workload-Protocol.md` (Rev 2)

---

## Phase 1: Domain Models and Task Steps

### Commit 1a: Wrap-up constants classes

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cycles/wrapup_models.py` | 5 constants classes: `ConfidenceClassification`, `CloseoutRecommendation`, `UnresolvedIssueType`, `UnresolvedIssueSeverity`, `NextCycleRecommendation` |

**Pattern reference:** `WorkloadType` in `src/squadops/cycles/models.py:89-99` (class with string constants, not enum).

```python
"""Wrap-up workload domain models (SIP-0080).

Constants classes for confidence classification, closeout recommendations,
unresolved issue taxonomy, and next-cycle recommendations.
"""

from __future__ import annotations


class ConfidenceClassification:
    """Confidence classification for wrap-up closeout decisions.

    Follows the constants-class pattern (WorkloadType, ArtifactType, EventType).
    """

    VERIFIED_COMPLETE = "verified_complete"
    COMPLETE_WITH_CAVEATS = "complete_with_caveats"
    PARTIAL_COMPLETION = "partial_completion"
    NOT_SUFFICIENTLY_VERIFIED = "not_sufficiently_verified"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


class CloseoutRecommendation:
    """Readiness recommendation for the closeout artifact.

    Follows the constants-class pattern.
    """

    PROCEED = "proceed"
    HARDEN = "harden"
    REPLAN = "replan"
    HALT = "halt"


class UnresolvedIssueType:
    """Type classification for unresolved items in wrap-up.

    Follows the constants-class pattern.
    """

    DEFECT = "defect"
    DESIGN_DEBT = "design_debt"
    TEST_GAP = "test_gap"
    ENVIRONMENTAL = "environmental"
    DEPENDENCY = "dependency"
    OPERATOR_DECISION_PENDING = "operator_decision_pending"
    DEFERRED_ENHANCEMENT = "deferred_enhancement"


class UnresolvedIssueSeverity:
    """Severity classification for unresolved items.

    Follows the constants-class pattern.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NextCycleRecommendation:
    """Recommended next cycle type for handoff artifact.

    Follows the constants-class pattern.
    """

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    HARDENING = "hardening"
    RESEARCH = "research"
    NONE = "none"


# Controlled vocabulary for suggested_owner field in unresolved items.
# First 6 are agent roles; "operator" indicates a human decision is required.
ALLOWED_SUGGESTED_OWNERS = frozenset({
    "lead", "qa", "dev", "data", "strat", "builder", "operator",
})
```

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `WorkloadType.WRAPUP = "wrapup"` and `REQUIRED_WRAPUP_ROLES` |

Exact changes to `models.py`:

1. Add to `WorkloadType` class (after line 99):
```python
    WRAPUP = "wrapup"
```

2. Add after `REQUIRED_REFINEMENT_ROLES` (after line 179):
```python
# Required roles for wrap-up workloads. Wrap-up is data + QA + lead. (SIP-0080 §7.1)
REQUIRED_WRAPUP_ROLES = frozenset({"data", "qa", "lead"})
```

**Tests:** `tests/unit/cycles/test_wrapup_models.py` (~15)

- `ConfidenceClassification` has exactly 6 values, all lowercase dot-free strings
- No duplicate values across `ConfidenceClassification` constants
- `CloseoutRecommendation` has exactly 4 values
- No duplicate values across `CloseoutRecommendation` constants
- `UnresolvedIssueType` has exactly 7 values
- No duplicate values across `UnresolvedIssueType` constants
- `UnresolvedIssueSeverity` has exactly 4 values
- No duplicate values across `UnresolvedIssueSeverity` constants
- `NextCycleRecommendation` has exactly 5 values, including `NONE = "none"`
- No duplicate values across `NextCycleRecommendation` constants
- `ALLOWED_SUGGESTED_OWNERS` contains exactly 7 entries (`lead`, `qa`, `dev`, `data`, `strat`, `builder`, `operator`)
- `WorkloadType.WRAPUP == "wrapup"`
- `REQUIRED_WRAPUP_ROLES == frozenset({"data", "qa", "lead"})`
- None of the constants classes are `enum.Enum` subclasses (they are plain classes)
- Confidence ceiling: `verified_complete` and `complete_with_caveats` are distinct from the "non-success" classifications (`partial_completion`, `not_sufficiently_verified`, `inconclusive`, `failed`)

Test pattern: direct attribute assertions on constants classes. Same approach as existing `test_models.py` for `WorkloadType` / `ArtifactType`.

### Commit 1b: WRAPUP_TASK_STEPS and task plan generator branch

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/task_plan.py` | Add `WRAPUP_TASK_STEPS` constant, add `WorkloadType.WRAPUP` to `_KNOWN_WORKLOAD_TYPES`, add `elif` branch in `generate_task_plan()`, import `REQUIRED_WRAPUP_ROLES` |

Exact changes:

1. Add task step constant (after `REPAIR_TASK_STEPS`, before `_KNOWN_WORKLOAD_TYPES`):

```python
# Wrap-up task steps (SIP-0080 §7.1)
WRAPUP_TASK_STEPS: list[tuple[str, str]] = [
    ("data.gather_evidence", "data"),
    ("qa.assess_outcomes", "qa"),
    ("data.classify_unresolved", "data"),
    ("governance.closeout_decision", "lead"),
    ("governance.publish_handoff", "lead"),
]
```

2. Add to `_KNOWN_WORKLOAD_TYPES` set:
```python
_KNOWN_WORKLOAD_TYPES = {
    WorkloadType.PLANNING,
    WorkloadType.IMPLEMENTATION,
    WorkloadType.REFINEMENT,
    WorkloadType.EVALUATION,
    WorkloadType.WRAPUP,          # New
}
```

3. Add to imports from `models.py`:
```python
from squadops.cycles.models import (
    REQUIRED_PLAN_ROLES,
    REQUIRED_REFINEMENT_ROLES,
    REQUIRED_WRAPUP_ROLES,       # New
    ...
)
```

4. Add `elif` branch in `generate_task_plan()` (after the `EVALUATION` branch, before `else`):

```python
        elif run.workload_type == WorkloadType.WRAPUP:
            missing = REQUIRED_WRAPUP_ROLES - profile_roles
            if missing:
                raise CycleError(
                    f"Squad profile '{profile.profile_id}' is missing required "
                    f"wrap-up roles: {', '.join(sorted(missing))}"
                )
            steps = list(WRAPUP_TASK_STEPS)
```

This goes between the `EVALUATION` branch (line 184) and the `else` (line 186) in the current code.

**Tests:** `tests/unit/cycles/test_wrapup_task_plan.py` (~8)

- `workload_type="wrapup"` → 5 envelopes with correct task_types: `data.gather_evidence`, `qa.assess_outcomes`, `data.classify_unresolved`, `governance.closeout_decision`, `governance.publish_handoff`
- `workload_type="wrapup"` → roles match: `data`, `qa`, `data`, `lead`, `lead`
- `workload_type="wrapup"` with missing Data role → `CycleError`
- `workload_type="wrapup"` with missing QA role → `CycleError`
- `workload_type="wrapup"` with missing Lead role → `CycleError`
- All 5 envelopes share correlation_id and trace_id
- Causation chain: each envelope's causation_id is the prior task_id (or correlation_id for first)
- `workload_type=None` → legacy behavior unchanged (backward compat regression)

Test pattern: same as `tests/unit/cycles/test_planning_task_plan.py` — construct minimal `Cycle`, `Run`, `SquadProfile` frozen dataclasses, call `generate_task_plan()`, assert on returned `TaskEnvelope` list.

---

## Phase 2: Handlers, Prompts, and Profile

### Commit 2a: 5 wrap-up handler classes

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/capabilities/handlers/wrapup_tasks.py` | 5 handler classes extending `_PlanningTaskHandler` |

All 5 wrap-up handlers extend `_PlanningTaskHandler` (not `_CycleTaskHandler` directly) to inherit the `task_type`-aware prompt assembly via `assemble(role, hook, task_type=self._capability_id)`. This matches the planning handlers pattern exactly.

```python
"""Wrap-up task handlers — LLM-powered handlers for wrap-up workload pipeline.

5 handlers whose capability_ids match the pinned task_type values from
WRAPUP_TASK_STEPS (SIP-0080 §7.1). All extend ``_PlanningTaskHandler``
to activate the task_type prompt layer for role-specific wrap-up behavior.

Part of SIP-0080.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.capabilities.handlers.planning_tasks import _PlanningTaskHandler

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DataGatherEvidenceHandler(_PlanningTaskHandler):
    _handler_name = "data_gather_evidence_handler"
    _capability_id = "data.gather_evidence"
    _role = "data"
    _artifact_name = "evidence_inventory.md"


class QAAssessOutcomesHandler(_PlanningTaskHandler):
    _handler_name = "qa_assess_outcomes_handler"
    _capability_id = "qa.assess_outcomes"
    _role = "qa"
    _artifact_name = "outcome_assessment.md"


class DataClassifyUnresolvedHandler(_PlanningTaskHandler):
    _handler_name = "data_classify_unresolved_handler"
    _capability_id = "data.classify_unresolved"
    _role = "data"
    _artifact_name = "unresolved_items.md"


class GovernanceCloseoutDecisionHandler(_PlanningTaskHandler):
    _handler_name = "governance_closeout_decision_handler"
    _capability_id = "governance.closeout_decision"
    _role = "lead"
    _artifact_name = "closeout_artifact.md"


class GovernancePublishHandoffHandler(_PlanningTaskHandler):
    _handler_name = "governance_publish_handoff_handler"
    _capability_id = "governance.publish_handoff"
    _role = "lead"
    _artifact_name = "handoff_artifact.md"
```

**Design note — handler simplicity for V1:**

Unlike the `GovernanceEstablishContractHandler` (SIP-0079) which has custom JSON parsing and outcome routing, wrap-up handlers are **thin subclasses** for V1. The LLM produces markdown artifacts with YAML frontmatter; the handlers do not parse or validate the frontmatter content mechanically. Content validation (confidence classification, evidence completeness) is enforced by the system prompt and verified by the operator at the closeout gate.

**Why not `_CycleTaskHandler` directly?** The handlers need `task_type`-aware prompt assembly to get wrap-up-specific instructions. `_PlanningTaskHandler` already provides this via `assemble(role, hook, task_type=self._capability_id)`. Inheriting from `_PlanningTaskHandler` is a pragmatic reuse — the "planning" in the name is historical; the behavior is "task_type-aware prompt assembly."

**V1.1 deferrals:**
- YAML frontmatter validation on closeout artifact (confidence value is valid, evidence_completeness matches rubric)
- Confidence ceiling mechanical enforcement (D19 — currently prompt-enforced, not code-enforced)
- Structured JSON output from unresolved items handler (currently markdown tables)

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/bootstrap/handlers.py` | Import 5 wrap-up handlers, add to `HANDLER_CONFIGS` with role tuples |

Add import:
```python
from squadops.capabilities.handlers.wrapup_tasks import (
    DataGatherEvidenceHandler,
    QAAssessOutcomesHandler,
    DataClassifyUnresolvedHandler,
    GovernanceCloseoutDecisionHandler,
    GovernancePublishHandoffHandler,
)
```

Add registration entries (after the refinement handler entries):
```python
    # Wrap-up handlers (SIP-0080: Wrap-Up Workload Protocol)
    (DataGatherEvidenceHandler, ("data",)),
    (QAAssessOutcomesHandler, ("qa",)),
    (DataClassifyUnresolvedHandler, ("data",)),
    (GovernanceCloseoutDecisionHandler, ("lead",)),
    (GovernancePublishHandoffHandler, ("lead",)),
```

**Tests:** `tests/unit/capabilities/handlers/test_wrapup_tasks.py` (~30)

Handler attribute tests (5 handlers × 4 attributes):
- Each handler has correct `capability_id` matching WRAPUP_TASK_STEPS task_type
- Each handler has correct `_role`
- Each handler has correct `_artifact_name`
- Each handler's `name` property returns expected `_handler_name`

Handler execution tests (5 handlers):
- Each handler's `validate_inputs()` requires `prd`
- Each handler's `validate_inputs()` passes with valid inputs
- Each handler's `handle()` calls LLM and returns `HandlerResult` with `success=True`
- Each handler's `handle()` includes artifact in outputs
- LLM failure → `HandlerResult` with `success=False` and error message
- Prior_outputs chaining: handler includes upstream outputs in user prompt

Specific handler tests:
- `DataGatherEvidenceHandler` includes `artifact_contents` from inputs in prompt when present
- `DataGatherEvidenceHandler` succeeds even when `artifact_contents` is empty (degraded mode, D5)
- `GovernanceCloseoutDecisionHandler` receives all 3 prior outputs in user prompt
- `GovernancePublishHandoffHandler` receives all 4 prior outputs in user prompt

Registration tests:
- All 5 handlers are present in `HANDLER_CONFIGS` in `bootstrap/handlers.py`
- Handlers registered with correct role tuples

Test pattern: mock `ExecutionContext` with mock LLM port (returns canned markdown response), mock `PromptService`. Same pattern as `tests/unit/capabilities/handlers/test_planning_tasks.py`.

### Commit 2b: Task-type prompt fragments for wrap-up

**New files (5 prompt fragments):**

| File | Purpose |
|------|---------|
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.gather_evidence.md` | Data agent: compile evidence inventory, assess completeness using 4-category rubric, record gaps rather than filling them |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.assess_outcomes.md` | QA agent: planned-vs-actual comparison, acceptance criteria evaluation, deviation detection, cross-reference QA findings vs completion claims |
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.classify_unresolved.md` | Data agent: categorize unresolved items using type (7 categories) and severity (4 levels), structured table with impact/owner/action |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.closeout_decision.md` | Lead agent: synthesize closeout artifact with YAML frontmatter, assign confidence classification, issue readiness recommendation. Anti-narration, anti-optimism instructions. Confidence ceiling constraints. |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.publish_handoff.md` | Lead agent: produce next-cycle handoff artifact, package carry-forward items, recommend next cycle type, "what not to retry" section |

Each fragment uses standard YAML frontmatter:
```markdown
---
fragment_id: task_type.data.gather_evidence
layer: task_type
version: "0.9.18"
roles: ["*"]
---
```

**Key prompt content guidance (from SIP-0080 §4, §7.18):**

- `data.gather_evidence`: Must include the evidence completeness rubric (§7.8). Four categories: planning artifact/run contract, implementation artifacts, test results, plan deltas/corrections. `complete` = all 4, `partial` = 1 missing, `sparse` = 2+ missing. Do NOT interpret or judge outcomes.
- `qa.assess_outcomes`: Must include scope baseline precedence rule (§7.8): run contract > planning artifact > plan deltas. `partially_met` counts as NOT met. Challenge completion claims lacking evidence. Do NOT set confidence classification.
- `data.classify_unresolved`: Must reference `UnresolvedIssueType` and `UnresolvedIssueSeverity` controlled vocabularies. `suggested_owner` must be one of: `lead`, `qa`, `dev`, `data`, `strat`, `builder`, `operator`.
- `governance.closeout_decision`: Must produce closeout artifact with YAML frontmatter per §7.8 template. Must include anti-optimism instruction: "If evidence is sparse, classify as inconclusive or not_sufficiently_verified — do not compensate." Confidence ceiling: sparse/partial evidence → cannot be `verified_complete`. Critical AC not met → cannot be `verified_complete` or `complete_with_caveats`.
- `governance.publish_handoff`: Must produce handoff artifact per §7.9 template. Include "what should not be retried blindly" section.

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/prompts/fragments/manifest.yaml` | Add 5 new task_type fragment entries with SHA256 hashes, bump version |

### Commit 2c: Wrap-up cycle request profile

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/contracts/cycle_request_profiles/profiles/wrapup.yaml` | Wrap-up workload profile with pulse checks, gate, cadence policy |

Content per SIP-0080 §7.13:

```yaml
name: wrapup
description: "Wrap-up workload with closeout review gate"
defaults:
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: progress_wrapup_review
        description: "Review closeout artifact before cycle completion"
        after_task_types:
          - governance.publish_handoff
  expected_artifact_types:
    - document
  workload_sequence:
    - type: wrapup
      gate: progress_wrapup_review
  pulse_checks:
    - suite_id: wrapup_evidence_guard
      boundary_id: post_evidence
      binding_mode: milestone
      after_task_types:
        - data.gather_evidence
      checks:
        - check_type: file_exists
          target: "{run_root}/evidence_inventory.md"
        - check_type: non_empty
          target: "{run_root}/evidence_inventory.md"
      max_suite_seconds: 15
      max_check_seconds: 5
    - suite_id: wrapup_completeness
      boundary_id: post_closeout
      binding_mode: milestone
      after_task_types:
        - governance.closeout_decision
      checks:
        - check_type: file_exists
          target: "{run_root}/closeout_artifact.md"
        - check_type: non_empty
          target: "{run_root}/closeout_artifact.md"
      max_suite_seconds: 15
      max_check_seconds: 5
  cadence_policy:
    max_pulse_seconds: 3600
    max_tasks_per_pulse: 5
  experiment_context: {}
  notes: "Wrap-up workload cycle"
```

No schema changes needed — all keys (`pulse_checks`, `cadence_policy`, `workload_sequence`) are already in `_APPLIED_DEFAULTS_EXTRA_KEYS` (confirmed in `schema.py`).

---

## Phase 3: Tests, Version Bump, Promotion

### Commit 3a: Profile and integration tests

**New file:**

| File | Tests |
|------|-------|
| `tests/unit/contracts/test_wrapup_profile.py` | ~5 profile validation tests |

Profile tests:
- Profile loads from YAML without errors (uses `load_profile()` or equivalent)
- Profile `name` is `"wrapup"`
- Profile `defaults` contains `task_flow_policy` with `progress_wrapup_review` gate
- Gate name `progress_wrapup_review` passes `progress_` prefix validation (SIP-0076)
- Pulse check suites contain `wrapup_evidence_guard` and `wrapup_completeness` with correct `after_task_types`
- Profile appears in profile listing (`list_profiles()` includes `wrapup`)

Test pattern: same as `tests/unit/contracts/test_planning_profile.py` — load YAML, validate against schema helpers.

### Commit 3b: Version bump and SIP promotion

- Bump version to `0.9.18` in `pyproject.toml` via `scripts/maintainer/version_cli.py`
- Promote SIP-0080 from accepted to implemented via `update_sip_status.py`
- Run full regression suite

---

## Tension Resolution: Artifact Pre-Resolution for `impl_run_id`

The SIP has a tension between §7.3 ("the executor resolves artifacts from `execution_overrides.impl_run_id`") and §7.15 ("No executor changes"). Resolution for V1:

**Approach: No executor changes. Handler-level access via `prior_outputs` and `execution_overrides`.**

In V1, the wrap-up run's `data.gather_evidence` handler receives implementation run context via:
1. `inputs["resolved_config"]` — contains `execution_overrides` with `impl_run_id` and `plan_artifact_refs`
2. `inputs["prior_outputs"]` — standard chaining from upstream handlers (empty for the first handler)
3. `inputs["artifact_contents"]` — if pre-resolution is added later, it arrives here; for V1, this key may be absent

The handler's system prompt instructs the LLM to reference implementation artifacts by ID from `execution_overrides`. The actual artifact content resolution is deferred to the executor's existing `_BUILD_ARTIFACT_FILTER` mechanism in a follow-up commit (adding a `"data.gather_evidence"` entry), or to a future cross-run artifact access capability.

**Why this works for V1:** The wrap-up handler receives the `impl_run_id` in its inputs. The system prompt instructs the Data agent to compile an evidence inventory based on what it can see. In a real execution environment, the executor already pre-resolves artifacts for known task types — extending `_BUILD_ARTIFACT_FILTER` with a `"data.gather_evidence"` entry is a one-line change to the executor, which can be done in a follow-up if needed. For the unit tests and initial integration, the handler works with whatever `artifact_contents` or `prior_outputs` are provided.

**Decision:** Do NOT modify `distributed_flow_executor.py` in this SIP. The handler is tested with injected `artifact_contents` in inputs. Actual executor wiring for cross-run artifact resolution is a follow-up concern. This is consistent with SIP-0080 §7.15 and D11.

---

## File Summary

### New Files (8)

| File | Purpose |
|------|---------|
| `src/squadops/cycles/wrapup_models.py` | 5 constants classes + `ALLOWED_SUGGESTED_OWNERS` |
| `src/squadops/capabilities/handlers/wrapup_tasks.py` | 5 handler classes extending `_PlanningTaskHandler` |
| `src/squadops/contracts/cycle_request_profiles/profiles/wrapup.yaml` | Wrap-up workload cycle request profile |
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.gather_evidence.md` | Data agent evidence gathering prompt |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.assess_outcomes.md` | QA agent outcome assessment prompt |
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.classify_unresolved.md` | Data agent unresolved classification prompt |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.closeout_decision.md` | Lead agent closeout decision prompt |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.publish_handoff.md` | Lead agent handoff publication prompt |

### New Test Files (4)

| File | Tests |
|------|-------|
| `tests/unit/cycles/test_wrapup_models.py` | ~15 |
| `tests/unit/cycles/test_wrapup_task_plan.py` | ~8 |
| `tests/unit/capabilities/handlers/test_wrapup_tasks.py` | ~30 |
| `tests/unit/contracts/test_wrapup_profile.py` | ~5 |

### Modified Files (4)

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `WorkloadType.WRAPUP = "wrapup"`, `REQUIRED_WRAPUP_ROLES` |
| `src/squadops/cycles/task_plan.py` | Add `WRAPUP_TASK_STEPS`, `WorkloadType.WRAPUP` to `_KNOWN_WORKLOAD_TYPES`, `elif` branch in `generate_task_plan()` |
| `src/squadops/bootstrap/handlers.py` | Import and register 5 wrap-up handlers |
| `src/squadops/prompts/fragments/manifest.yaml` | Add 5 task_type fragment entries with SHA256 hashes |

### Files NOT Modified

| File | Why |
|------|-----|
| `adapters/cycles/distributed_flow_executor.py` | No executor changes (SIP §7.15, D11) |
| `src/squadops/api/routes/cycles/` | No API route changes (SIP §7.17, D12) |
| `src/squadops/cli/commands/` | No CLI changes (SIP §7.17, D12) |
| `src/squadops/events/types.py` | No new event types (SIP §7.16, D13) |
| `src/squadops/events/bridges/` | No bridge changes (SIP §7.16) |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | All keys already in `_APPLIED_DEFAULTS_EXTRA_KEYS` (SIP §8.3) |

---

## Commit Plan

| Commit | Message |
|--------|---------|
| 1a | `feat: wrap-up constants classes and WorkloadType.WRAPUP (SIP-0080 Phase 1)` |
| 1b | `feat: WRAPUP_TASK_STEPS and task plan generator branch (SIP-0080 Phase 1)` |
| 2a | `feat: 5 wrap-up handler classes with bootstrap registration (SIP-0080 Phase 2)` |
| 2b | `feat: task-type prompt fragments for wrap-up handlers (SIP-0080 Phase 2)` |
| 2c | `feat: wrapup cycle request profile (SIP-0080 Phase 2)` |
| 3a | `test: profile and handler integration tests (SIP-0080 Phase 3)` |
| 3b | `chore: bump version to 0.9.18, promote SIP-0080 to implemented` |

---

## Verification

1. `ruff check . && ruff format --check .` — no lint or format issues on all modified files
2. `pytest tests/unit/cycles/test_wrapup_models.py -v` — all constants class tests pass
3. `pytest tests/unit/cycles/test_wrapup_task_plan.py -v` — task plan generator tests pass
4. `pytest tests/unit/capabilities/handlers/test_wrapup_tasks.py -v` — all handler tests pass
5. `pytest tests/unit/contracts/test_wrapup_profile.py -v` — profile loads and validates
6. `pytest tests/unit/cycles/test_task_plan.py -v` — existing task plan tests unchanged (backward compat)
7. `./scripts/dev/run_new_arch_tests.sh -v` — full regression green

---

## Gotchas

- **Handler registration is explicit** — adding handler classes is not enough. Each must be imported and added to `HANDLER_CONFIGS` in `src/squadops/bootstrap/handlers.py` with a role tuple. Forgetting this means the handler exists but is never dispatched.
- **`_PlanningTaskHandler` not `_CycleTaskHandler`** — wrap-up handlers need `task_type`-aware prompt assembly. `_CycleTaskHandler.handle()` calls `get_system_prompt(role)` which skips the task_type layer entirely. `_PlanningTaskHandler.handle()` calls `assemble(role, hook, task_type=...)` which activates the task_type prompt fragments.
- **`manifest.yaml` integrity** — each prompt fragment needs a SHA256 hash in `manifest.yaml`. The assembler verifies hashes at load time (`HashMismatchError`). The `manifest_hash` must also be recomputed after adding entries.
- **Fragment naming convention** — files must be named `task_type.{capability_id}.md` (e.g., `task_type.data.gather_evidence.md`) and use YAML frontmatter with matching `fragment_id` and `layer: task_type`.
- **No executor changes** — artifact pre-resolution for `impl_run_id` is deferred. Handlers receive `execution_overrides` with `impl_run_id` in `inputs["resolved_config"]` but do not have automatic artifact content injection. This is acceptable for V1 — the handler works with whatever context it receives.
- **Gate name prefix** — the gate `progress_wrapup_review` uses the `progress_` prefix, which is validated case-sensitively by SIP-0076.
- **`_KNOWN_WORKLOAD_TYPES` must include `WRAPUP`** — without this, `generate_task_plan()` raises `CycleError("Unknown workload_type 'wrapup'")` instead of selecting `WRAPUP_TASK_STEPS`.
- **Tests directory** — `tests/unit/capabilities/handlers/` already exists (created by SIP-0078). No new directory creation needed.
- **Estimated total tests after:** ~2,685 (current 2,627 + ~58 new)
