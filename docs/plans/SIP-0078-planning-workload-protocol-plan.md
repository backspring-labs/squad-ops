# Plan: SIP-0078 Planning Workload Protocol Implementation

## Context

SIP-0078 defines the Planning Workload Protocol — the first phase of a multi-workload Cycle. Today, all cycles use `CYCLE_TASK_STEPS` (5-step plan tasks) and/or `BUILD_TASK_STEPS` (2-step build tasks) regardless of workload type. The `WorkloadType` constants (`planning`, `implementation`, `refinement`, `evaluation`) exist from SIP-0076 but `generate_task_plan()` doesn't use them — it only checks `plan_tasks` / `build_tasks` flags.

SIP-0078 introduces planning-specific task steps, handlers, unknown classification, design sufficiency checks, bounded refinement, and a planning CRP profile. The key architectural insight: **no executor changes are needed**. Planning workloads plug into the existing dispatch, chaining, pulse check, and gate mechanisms. The only runtime code change is in the task plan generator's step selection.

**Branch:** `feature/sip-0078-planning-workload-protocol` (off main)
**SIP:** `sips/accepted/SIP-0078-Planning-Workload-Protocol.md` (Rev 3)

---

## Phase 1: Domain Models and Task Plan Generator

### Commit 1a: UnknownClassification constants + REQUIRED_REFINEMENT_ROLES

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cycles/unknown_classification.py` | `UnknownClassification` constants class with 5 values: `RESOLVED`, `PROTO_VALIDATED`, `ACCEPTABLE_RISK`, `REQUIRES_HUMAN_DECISION`, `BLOCKER` |

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `REQUIRED_REFINEMENT_ROLES = {"lead", "qa"}` alongside existing `REQUIRED_PLAN_ROLES` |

**Pattern references:**
- `UnknownClassification` follows `WorkloadType` / `ArtifactType` pattern (class with string constants, not enum): `src/squadops/cycles/models.py:89-99`
- `REQUIRED_PLAN_ROLES` already in `models.py` — `REQUIRED_REFINEMENT_ROLES` goes right next to it

**Tests:** `tests/unit/cycles/test_unknown_classification.py` (~5)
- All 5 constants exist and are lowercase strings
- Constants class is not an enum
- `REQUIRED_REFINEMENT_ROLES` contains exactly `{"lead", "qa"}`

### Commit 1b: PLANNING_TASK_STEPS, REFINEMENT_TASK_STEPS, workload-type branching

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/task_plan.py` | Add `PLANNING_TASK_STEPS`, `REFINEMENT_TASK_STEPS` constants. Add workload-type branching at top of `generate_task_plan()` — when `run.workload_type` is set, it takes precedence over `plan_tasks`/`build_tasks` flags. Add `WorkloadType` and `REQUIRED_REFINEMENT_ROLES` to the existing `from squadops.cycles.models import ...` line. |

**Task step definitions:**

```python
PLANNING_TASK_STEPS: list[tuple[str, str]] = [
    ("data.research_context", "data"),
    ("strategy.frame_objective", "strat"),
    ("development.design_plan", "dev"),
    ("qa.define_test_strategy", "qa"),
    ("governance.assess_readiness", "lead"),
]

REFINEMENT_TASK_STEPS: list[tuple[str, str]] = [
    ("governance.incorporate_feedback", "lead"),
    ("qa.validate_refinement", "qa"),
]
```

**Branching logic in `generate_task_plan()`** — insert before existing step selection:

```python
# Add to existing import: from squadops.cycles.models import ..., WorkloadType, REQUIRED_REFINEMENT_ROLES

if run.workload_type == WorkloadType.PLANNING:
    # Validate required roles (planning uses all 5 standard roles)
    profile_roles = {a.role for a in profile.agents if a.enabled}
    missing = REQUIRED_PLAN_ROLES - profile_roles
    if missing:
        raise CycleError(
            f"Squad profile '{profile.profile_id}' is missing required roles: "
            f"{', '.join(sorted(missing))}"
        )
    steps = list(PLANNING_TASK_STEPS)
elif run.workload_type == WorkloadType.REFINEMENT:
    # Validate required roles
    profile_roles = {a.role for a in profile.agents if a.enabled}
    missing = REQUIRED_REFINEMENT_ROLES - profile_roles
    if missing:
        raise CycleError(f"Squad profile missing required refinement roles: {', '.join(sorted(missing))}")
    steps = list(REFINEMENT_TASK_STEPS)
elif run.workload_type == WorkloadType.IMPLEMENTATION:
    builder_used = _has_builder_role(profile)
    if builder_used:
        steps = list(BUILDER_ASSEMBLY_TASK_STEPS)
    else:
        steps = list(BUILD_TASK_STEPS)
else:
    # Legacy: no workload_type → existing plan_tasks/build_tasks logic (unchanged)
    ...
```

When `workload_type` is set, the function skips the `plan_tasks`/`build_tasks` flag logic entirely. The existing `else` branch remains identical for backward compatibility.

**Tests:** `tests/unit/cycles/test_planning_task_plan.py` (~15)
- `workload_type=planning` → 5 PLANNING_TASK_STEPS envelopes with correct task_types and roles
- `workload_type=refinement` → 2 REFINEMENT_TASK_STEPS envelopes
- `workload_type=implementation` → BUILD_TASK_STEPS (or BUILDER_ASSEMBLY_TASK_STEPS with builder)
- `workload_type=None` → legacy behavior unchanged (backward compat)
- Refinement with missing Lead role → CycleError
- Refinement with missing QA role → CycleError
- Planning produces shared correlation_id and trace_id across all 5 envelopes
- Planning produces correct causation chain (task → task)
- Planning with missing role → CycleError (validates REQUIRED_PLAN_ROLES explicitly in the planning branch)

---

## Phase 2: Planning Handlers

### Commit 2a: 5 planning handler classes

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | 5 handler classes extending `_CycleTaskHandler` |

All 5 follow the same pattern as the existing cycle task handlers in `cycle_tasks.py` — they are thin subclasses that set 4 class attributes:

```python
class DataResearchContextHandler(_CycleTaskHandler):
    _handler_name = "data_research_context_handler"
    _capability_id = "data.research_context"
    _role = "data"
    _artifact_name = "context_research.md"

class StrategyFrameObjectiveHandler(_CycleTaskHandler):
    _handler_name = "strategy_frame_objective_handler"
    _capability_id = "strategy.frame_objective"
    _role = "strat"
    _artifact_name = "objective_frame.md"

class DevelopmentDesignPlanHandler(_CycleTaskHandler):
    _handler_name = "development_design_plan_handler"
    _capability_id = "development.design_plan"
    _role = "dev"
    _artifact_name = "technical_design.md"

class QADefineTestStrategyHandler(_CycleTaskHandler):
    _handler_name = "qa_define_test_strategy_handler"
    _capability_id = "qa.define_test_strategy"
    _role = "qa"
    _artifact_name = "test_strategy.md"

class GovernanceAssessReadinessHandler(_CycleTaskHandler):
    _handler_name = "governance_assess_readiness_handler"
    _capability_id = "governance.assess_readiness"
    _role = "lead"
    _artifact_name = "planning_artifact.md"
```

The base `_CycleTaskHandler.handle()` does most of the work: builds user prompt from PRD + prior_outputs, gets system prompt, calls LLM, records generation, returns artifacts. However, the current base class calls `context.ports.prompt_service.get_system_prompt(self._role)` which is `assemble(role, hook="agent_start")` — **without passing `task_type`**. This means the assembler skips the task_type layer entirely.

**Planning handlers need a minor override** to activate the task_type prompt fragments. The planning handler base should call `context.ports.prompt_service.assemble(role=self._role, hook="agent_start", task_type=self._capability_id)` instead of `get_system_prompt()`. This is a one-line change in `handle()` — either a shared `_PlanningTaskHandler` base or individual overrides. The cleanest approach is a `_PlanningTaskHandler(_CycleTaskHandler)` base class that overrides only the prompt assembly line:

```python
class _PlanningTaskHandler(_CycleTaskHandler):
    """Base for planning handlers — activates task_type prompt fragments."""

    async def handle(self, context, inputs):
        # Override: use assemble() with task_type to include task-specific prompt fragment
        # Everything else identical to _CycleTaskHandler.handle()
        ...
        assembled = context.ports.prompt_service.assemble(
            role=self._role, hook="agent_start", task_type=self._capability_id
        )
        ...
```

**Differentiation comes from:**
1. Role-specific identity prompts (existing `src/squadops/prompts/fragments/roles/{role}/identity.md`)
2. Task-type-specific prompt fragments (new, in `src/squadops/prompts/fragments/shared/task_type/`)
3. Prior-output chaining (each handler sees upstream outputs)

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/bootstrap/handlers.py` | Import 5 planning handlers, add to `HANDLER_CONFIGS` with role tuples |

Registration entries:
```python
(DataResearchContextHandler, ("data",)),
(StrategyFrameObjectiveHandler, ("strat",)),
(DevelopmentDesignPlanHandler, ("dev",)),
(QADefineTestStrategyHandler, ("qa",)),
(GovernanceAssessReadinessHandler, ("lead",)),
```

**Tests:** `tests/unit/capabilities/handlers/test_planning_tasks.py` (~20)
- Each handler has correct `capability_id`, `name`, `_role`, `_artifact_name`
- Each handler's `validate_inputs()` requires `prd`
- Each handler's `handle()` calls LLM and returns HandlerResult with artifact
- Prior_outputs chaining: handler receives upstream outputs in user prompt
- LLM failure → HandlerResult with `success=False`
- All 5 handlers registered in HANDLER_CONFIGS with correct roles

Test pattern: mock `ExecutionContext` with mock LLM port (returns canned response), mock PromptService. Same pattern as existing handler tests in `tests/unit/capabilities/`.

**Note:** Existing handler tests live flat in `tests/unit/capabilities/` (e.g., `test_cycle_task_handlers.py`, `test_build_handlers.py`). The `tests/unit/capabilities/handlers/` subdirectory does not exist yet — it must be created. This is a deliberate choice to organize the growing number of handler test files. `run_new_arch_tests.sh` already includes `tests/unit/capabilities/` which discovers subdirectories recursively, so no script change is needed.

### Commit 2b: Task-type prompt fragments for planning

The prompt fragment infrastructure is already in place (SIP-0057):
- Fragment directory: `src/squadops/prompts/fragments/`
- Assembler: `src/squadops/prompts/assembler.py` — resolves `task_type.{task_type}` fragments
- Manifest: `src/squadops/prompts/fragments/manifest.yaml` (v0.8.5, 9 existing fragments)
- Empty `shared/task_type/` directory already exists, ready for task-type fragments

Fragment naming convention: the assembler resolves `task_type.{task_type}` as the fragment_id. So for `task_type="data.research_context"`, the fragment_id is `task_type.data.research_context` and the file path is `shared/task_type/task_type.data.research_context.md`.

Each fragment file uses the standard YAML frontmatter header:
```markdown
---
fragment_id: task_type.data.research_context
layer: task_type
version: "0.8.5"
roles: ["*"]
---
<prompt content>
```

**New files (prompt fragments):**

| File | Purpose |
|------|---------|
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.research_context.md` | Instructions for Data agent during planning: gather constraints, prior patterns, risk areas, proto validation targets |
| `src/squadops/prompts/fragments/shared/task_type/task_type.strategy.frame_objective.md` | Instructions for Strategy agent: frame objective, scope, non-goals, acceptance criteria |
| `src/squadops/prompts/fragments/shared/task_type/task_type.development.design_plan.md` | Instructions for Dev agent: technical design, interfaces, sequencing, proto validation, unknown classification. Includes proto constraint: "Proto work validates feasibility. Do not implement features." |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.define_test_strategy.md` | Instructions for QA agent: acceptance checklist, test strategy note, defect severity rubric. Stage A maturity: no full test suite. |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.assess_readiness.md` | Instructions for Lead agent: consolidate all outputs, design sufficiency check (5 criteria), readiness recommendation. Must produce YAML frontmatter. Blocker unknowns → readiness must be revise/no-go. |

Each fragment is a focused markdown file (~20-40 lines) that the PromptAssembler appends after the identity, constraints, and lifecycle layers. The fragments define what each role should produce during planning.

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/prompts/fragments/manifest.yaml` | Add 5 new task_type fragment entries with SHA256 hashes, bump version, recompute `manifest_hash` |

---

## Phase 3: Refinement Handlers

### Commit 3a: 2 refinement handler classes + failure behavior

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | Add 2 refinement handlers |

Both refinement handlers extend `_PlanningTaskHandler` (same as planning handlers) so their task_type prompt fragments are activated via `assemble(task_type=self._capability_id)`.

```python
class GovernanceIncorporateFeedbackHandler(_PlanningTaskHandler):
    _handler_name = "governance_incorporate_feedback_handler"
    _capability_id = "governance.incorporate_feedback"
    _role = "lead"
    _artifact_name = "planning_artifact_revised.md"

class QAValidateRefinementHandler(_PlanningTaskHandler):
    _handler_name = "qa_validate_refinement_handler"
    _capability_id = "qa.validate_refinement"
    _role = "qa"
    _artifact_name = "refinement_validation.md"
```

**`GovernanceIncorporateFeedbackHandler` overrides (D17 fail-fast):**

This handler needs a custom `validate_inputs()` to enforce D17 — fail if `plan_artifact_refs` is missing from `execution_overrides`:

```python
def validate_inputs(self, inputs, contract=None):
    errors = super().validate_inputs(inputs, contract)
    resolved_config = inputs.get("resolved_config", {})
    if not resolved_config.get("plan_artifact_refs"):
        errors.append("'plan_artifact_refs' is required in execution_overrides for refinement runs")
    return errors
```

Also needs a custom `handle()` that enforces D17 at execution time — if `plan_artifact_refs` is present but the resolved content is empty or unreadable, return `HandlerResult(success=False)` with a structured error. The three D17 failure conditions are:
1. `plan_artifact_refs` missing from `execution_overrides` → caught by `validate_inputs()`
2. Artifact unreadable (vault retrieval fails) → caught by `handle()` during artifact resolution
3. Resolves to no content (empty artifact) → caught by `handle()` before LLM call

Also needs a custom `_build_user_prompt()` that includes:
- The original planning artifact content (from `plan_artifact_refs` resolved via artifact vault or `artifact_contents` pre-resolution)
- Refinement instructions (from `resolved_config.get("refinement_instructions")`)
- Prior outputs (standard)

**Companion artifact (SIP §5.9):** `GovernanceIncorporateFeedbackHandler` produces TWO artifacts:
1. `planning_artifact_revised.md` — the updated planning artifact (canonical handoff)
2. `plan_refinement.md` — companion change-tracking artifact with YAML frontmatter (`original_plan_ref`, `refinement_source`, `scope_change`, `sequencing_changed`) and a structured Changes Applied table + Incorporation Summary

The handler's `handle()` should emit both artifacts in the outputs list. The `_artifact_name` class attribute is `planning_artifact_revised.md` (primary), and `plan_refinement.md` is added programmatically.

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/bootstrap/handlers.py` | Import 2 refinement handlers, add to `HANDLER_CONFIGS` |

Registration entries:
```python
(GovernanceIncorporateFeedbackHandler, ("lead",)),
(QAValidateRefinementHandler, ("qa",)),
```

**New prompt fragments:**

| File | Purpose |
|------|---------|
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.incorporate_feedback.md` | Instructions for Lead: parse refinement instructions, apply targeted changes to planning artifact, produce revised artifact with YAML frontmatter, track changes in refinement artifact |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.validate_refinement.md` | Instructions for QA: verify acceptance criteria still hold after refinement, flag any gaps introduced by changes |

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/prompts/fragments/manifest.yaml` | Add 2 refinement task_type fragment entries with SHA256 hashes |

**Tests:** `tests/unit/capabilities/handlers/test_planning_tasks.py` (add ~18)
- `GovernanceIncorporateFeedbackHandler` has correct capability_id and artifact_name
- `GovernanceIncorporateFeedbackHandler.validate_inputs()` fails when `plan_artifact_refs` is missing
- `GovernanceIncorporateFeedbackHandler.validate_inputs()` passes when `plan_artifact_refs` is present
- `GovernanceIncorporateFeedbackHandler.handle()` fails when artifact content is empty (D17 condition 3)
- `GovernanceIncorporateFeedbackHandler.handle()` includes refinement instructions in user prompt
- `GovernanceIncorporateFeedbackHandler.handle()` produces both `planning_artifact_revised.md` and `plan_refinement.md` (SIP §5.9)
- `QAValidateRefinementHandler` has correct capability_id and artifact_name
- Both refinement handlers extend `_PlanningTaskHandler` (use task_type prompt assembly)
- Both handlers registered in HANDLER_CONFIGS

---

## Phase 4: CRP Profile, Integration, and Cleanup

### Commit 4a: Planning CRP profile

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/contracts/cycle_request_profiles/profiles/planning.yaml` | Planning workload profile with `workload_sequence`, `pulse_checks`, `cadence_policy`, `progress_plan_review` gate |

Profile content per SIP §5.13 — includes:
- `task_flow_policy.gates` with `progress_plan_review` gate after `governance.assess_readiness`
- `workload_sequence` with planning → implementation ordering (informational in 1.0)
- 3 planning pulse check suites: `planning_scope_guard` (milestone, post-strategy), `planning_completeness` (milestone, post-consolidation), `planning_heartbeat` (cadence, optional per SIP §5.11)
- `cadence_policy` with `max_pulse_seconds: 5400`, `max_tasks_per_pulse: 5`

**Tests:** `tests/unit/contracts/test_planning_profile.py` (~5)
- Profile loads and validates without errors
- Profile has correct `workload_sequence` entries
- Pulse check suites parse correctly
- Gate name passes prefix validation (`progress_plan_review`)

### Commit 4b: Version bump + plan file + final cleanup

- Bump version to `0.9.16` in `pyproject.toml`
- Run full regression suite
- Update `docs/ROADMAP.md` with v0.9.16 entry (and fix stale stats block which still says v0.9.14)

---

## File Summary

### New Files (10)

| File | Purpose |
|------|---------|
| `src/squadops/cycles/unknown_classification.py` | `UnknownClassification` constants class (5 values) |
| `src/squadops/capabilities/handlers/planning_tasks.py` | 7 handler classes (5 planning + 2 refinement) + `_PlanningTaskHandler` base |
| `src/squadops/contracts/cycle_request_profiles/profiles/planning.yaml` | Planning workload CRP profile |
| `src/squadops/prompts/fragments/shared/task_type/task_type.data.research_context.md` | Data agent planning prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.strategy.frame_objective.md` | Strategy agent planning prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.development.design_plan.md` | Dev agent planning prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.define_test_strategy.md` | QA agent planning prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.assess_readiness.md` | Lead agent planning prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.governance.incorporate_feedback.md` | Lead agent refinement prompt fragment |
| `src/squadops/prompts/fragments/shared/task_type/task_type.qa.validate_refinement.md` | QA agent refinement prompt fragment |

### New Test Files (4)

| File | Tests |
|------|-------|
| `tests/unit/cycles/test_unknown_classification.py` | ~5 |
| `tests/unit/cycles/test_planning_task_plan.py` | ~15 |
| `tests/unit/capabilities/handlers/test_planning_tasks.py` | ~35 |
| `tests/unit/contracts/test_planning_profile.py` | ~5 |

### Modified Files (4)

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `REQUIRED_REFINEMENT_ROLES` |
| `src/squadops/cycles/task_plan.py` | Add step constants + workload-type branching |
| `src/squadops/bootstrap/handlers.py` | Register 7 planning/refinement handlers |
| `src/squadops/prompts/fragments/manifest.yaml` | Add 7 task_type fragment entries with SHA256 hashes, bump version |

### Files NOT Modified

| File | Why |
|------|-----|
| `adapters/cycles/distributed_flow_executor.py` | No executor changes (SIP D11) |
| `src/squadops/api/routes/cycles/` | No API route changes |
| `src/squadops/events/types.py` | No new event types |
| `src/squadops/cycles/pulse_models.py` | No new pulse models |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | `workload_sequence` already in `_APPLIED_DEFAULTS_EXTRA_KEYS` |

**Estimated new tests:** ~65
**Estimated total after:** ~2,692

---

## Verification

1. `./scripts/dev/run_new_arch_tests.sh -v` — all existing 2,627+ tests pass (no regressions)
2. `pytest tests/unit/cycles/test_unknown_classification.py tests/unit/cycles/test_planning_task_plan.py -v` — domain model + task plan tests pass
3. `pytest tests/unit/capabilities/handlers/test_planning_tasks.py -v` — all handler tests pass
4. `pytest tests/unit/contracts/test_planning_profile.py -v` — CRP profile loads and validates
5. Verify backward compatibility: `pytest tests/unit/cycles/test_task_plan.py -v` — existing task plan tests unchanged
6. Verify `workload_type=None` produces identical behavior to current code (no regressions for existing cycles)

---

## Gotchas

- **Handler registration is explicit** — adding handler classes is not enough. Each must be imported and added to `HANDLER_CONFIGS` in `src/squadops/bootstrap/handlers.py` with role tuple.
- **Handlers must call `assemble()` with `task_type=`** — the current `_CycleTaskHandler.handle()` calls `get_system_prompt(role)` which is `assemble(role, hook="agent_start")` without passing `task_type`. Planning handlers need to call `assemble(role, hook="agent_start", task_type=self._capability_id)` to activate the task_type prompt fragments. A `_PlanningTaskHandler` base class handles this.
- **Prompt fragments are optional but important** — the assembler silently skips missing task_type fragments. Handlers work without them, but planning handlers need these fragments to produce correct output structure (YAML frontmatter, unknown classification, sufficiency table).
- **`manifest.yaml` integrity** — each prompt fragment needs a SHA256 hash in `src/squadops/prompts/fragments/manifest.yaml`. The assembler verifies hashes at load time (`HashMismatchError`). The `manifest_hash` must also be recomputed after adding entries.
- **Fragment naming convention** — files must be named `task_type.{capability_id}.md` (e.g., `task_type.data.research_context.md`) and use YAML frontmatter with matching `fragment_id` and `layer: task_type`.
- **`GovernanceIncorporateFeedbackHandler` needs custom `validate_inputs()` and `_build_user_prompt()`** — it's the only handler that's not a pure thin subclass. It must enforce D17 (fail on missing `plan_artifact_refs`) and include refinement instructions in the prompt.
- **No executor changes** — planning workloads use existing sequential dispatch. If tests try to run planning tasks through the executor, they'll need the same mock setup as existing cycle execution tests.
- **Existing `CYCLE_TASK_STEPS` remain for `workload_type=None`** — the legacy branch is unchanged. Only workload-typed runs use the new step selection.
