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
| `src/squadops/cycles/task_plan.py` | Add `PLANNING_TASK_STEPS`, `REFINEMENT_TASK_STEPS` constants. Add workload-type branching at top of `generate_task_plan()` — when `run.workload_type` is set, it takes precedence over `plan_tasks`/`build_tasks` flags. Import `REQUIRED_REFINEMENT_ROLES` from models, validate for refinement runs. |

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
from squadops.cycles.models import WorkloadType, REQUIRED_REFINEMENT_ROLES

if run.workload_type == WorkloadType.PLANNING:
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
- Planning validates REQUIRED_PLAN_ROLES (already covered by existing logic)

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

The base `_CycleTaskHandler.handle()` does all the work: builds user prompt from PRD + prior_outputs, gets system prompt via `context.ports.prompt_service.get_system_prompt(role)`, calls LLM, records generation, returns artifacts.

**No custom `handle()` overrides needed in V1.** The differentiation comes from:
1. Role-specific system prompts (loaded by PromptService from `prompts/roles/{role}/`)
2. Task-type-specific prompt fragments (loaded from `prompts/shared/task_type/`)
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

Test pattern: mock `ExecutionContext` with mock LLM port (returns canned response), mock PromptService. Same pattern as `tests/unit/capabilities/handlers/` existing tests.

### Commit 2b: Task-type prompt fragments for planning

**New files (prompt fragments):**

| File | Purpose |
|------|---------|
| `prompts/shared/task_type/data.research_context.md` | Instructions for Data agent during planning: gather constraints, prior patterns, risk areas, proto validation targets |
| `prompts/shared/task_type/strategy.frame_objective.md` | Instructions for Strategy agent: frame objective, scope, non-goals, acceptance criteria |
| `prompts/shared/task_type/development.design_plan.md` | Instructions for Dev agent: technical design, interfaces, sequencing, proto validation, unknown classification. Includes proto constraint: "Proto work validates feasibility. Do not implement features." |
| `prompts/shared/task_type/qa.define_test_strategy.md` | Instructions for QA agent: acceptance checklist, test strategy note, defect severity rubric. Stage A maturity: no full test suite. |
| `prompts/shared/task_type/governance.assess_readiness.md` | Instructions for Lead agent: consolidate all outputs, design sufficiency check (5 criteria), readiness recommendation. Must produce YAML frontmatter. Blocker unknowns → readiness must be revise/no-go. |

Each fragment is a focused markdown file (~20-40 lines) that the PromptService assembles into the system prompt alongside the agent's identity and global constraints. The fragments define what each role should produce during planning.

**Modified file:**

| File | Change |
|------|--------|
| `prompts/manifest.yaml` | Add 5 new task_type fragment entries |

**Note:** The `prompts/` directory does not currently exist. If the PromptService is not yet wired to load task_type fragments from disk, the prompt fragments are a forward-looking preparation. Handlers will still work without them — PromptService silently skips missing fragments. The fragments become effective once the PromptService's fragment loader is implemented.

---

## Phase 3: Refinement Handlers

### Commit 3a: 2 refinement handler classes + failure behavior

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | Add 2 refinement handlers |

```python
class GovernanceIncorporateFeedbackHandler(_CycleTaskHandler):
    _handler_name = "governance_incorporate_feedback_handler"
    _capability_id = "governance.incorporate_feedback"
    _role = "lead"
    _artifact_name = "planning_artifact_revised.md"

class QAValidateRefinementHandler(_CycleTaskHandler):
    _handler_name = "qa_validate_refinement_handler"
    _capability_id = "qa.validate_refinement"
    _role = "qa"
    _artifact_name = "refinement_validation.md"
```

**`GovernanceIncorporateFeedbackHandler` override:** This handler needs a custom `validate_inputs()` to enforce D17 — if `plan_artifact_refs` is missing from `execution_overrides` in inputs, fail immediately with a validation error:

```python
def validate_inputs(self, inputs, contract=None):
    errors = super().validate_inputs(inputs, contract)
    resolved_config = inputs.get("resolved_config", {})
    if not resolved_config.get("plan_artifact_refs"):
        errors.append("'plan_artifact_refs' is required in execution_overrides for refinement runs")
    return errors
```

Also needs a custom `_build_user_prompt()` that includes:
- The original planning artifact content (from `plan_artifact_refs` resolved via artifact vault or `artifact_contents` pre-resolution)
- Refinement instructions (from `resolved_config.get("refinement_instructions")`)
- Prior outputs (standard)

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
| `prompts/shared/task_type/governance.incorporate_feedback.md` | Instructions for Lead: parse refinement instructions, apply targeted changes to planning artifact, produce revised artifact with YAML frontmatter, track changes in refinement artifact |
| `prompts/shared/task_type/qa.validate_refinement.md` | Instructions for QA: verify acceptance criteria still hold after refinement, flag any gaps introduced by changes |

**Tests:** `tests/unit/capabilities/handlers/test_planning_tasks.py` (add ~15)
- `GovernanceIncorporateFeedbackHandler` has correct capability_id and artifact_name
- `GovernanceIncorporateFeedbackHandler.validate_inputs()` fails when `plan_artifact_refs` is missing
- `GovernanceIncorporateFeedbackHandler.validate_inputs()` passes when `plan_artifact_refs` is present
- `GovernanceIncorporateFeedbackHandler.handle()` includes refinement instructions in user prompt
- `QAValidateRefinementHandler` has correct capability_id and artifact_name
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
- 2 planning pulse check suites (`planning_scope_guard`, `planning_completeness`)
- `cadence_policy` with `max_pulse_seconds: 5400`, `max_tasks_per_pulse: 5`

**Tests:** `tests/unit/contracts/test_planning_profile.py` (~5)
- Profile loads and validates without errors
- Profile has correct `workload_sequence` entries
- Pulse check suites parse correctly
- Gate name passes prefix validation (`progress_plan_review`)

### Commit 4b: Version bump + plan file + final cleanup

- Copy this plan to `docs/plans/SIP-0078-planning-workload-protocol-plan.md`
- Bump version to `0.9.16` in `pyproject.toml`
- Add `tests/unit/capabilities/handlers/` to `run_new_arch_tests.sh` if not already present
- Run full regression suite
- Update `docs/ROADMAP.md` with v0.9.16 entry

---

## File Summary

### New Files (10)

| File | Purpose |
|------|---------|
| `src/squadops/cycles/unknown_classification.py` | `UnknownClassification` constants class (5 values) |
| `src/squadops/capabilities/handlers/planning_tasks.py` | 7 handler classes (5 planning + 2 refinement) |
| `src/squadops/contracts/cycle_request_profiles/profiles/planning.yaml` | Planning workload CRP profile |
| `prompts/shared/task_type/data.research_context.md` | Data agent planning prompt fragment |
| `prompts/shared/task_type/strategy.frame_objective.md` | Strategy agent planning prompt fragment |
| `prompts/shared/task_type/development.design_plan.md` | Dev agent planning prompt fragment |
| `prompts/shared/task_type/qa.define_test_strategy.md` | QA agent planning prompt fragment |
| `prompts/shared/task_type/governance.assess_readiness.md` | Lead agent planning prompt fragment |
| `prompts/shared/task_type/governance.incorporate_feedback.md` | Lead agent refinement prompt fragment |
| `prompts/shared/task_type/qa.validate_refinement.md` | QA agent refinement prompt fragment |

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
| `prompts/manifest.yaml` | Add 7 task_type fragment entries |

### Files NOT Modified

| File | Why |
|------|-----|
| `adapters/cycles/distributed_flow_executor.py` | No executor changes (SIP D11) |
| `src/squadops/api/routes/cycles/` | No API route changes |
| `src/squadops/events/types.py` | No new event types |
| `src/squadops/cycles/pulse_models.py` | No new pulse models |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | `workload_sequence` already in `_APPLIED_DEFAULTS_EXTRA_KEYS` |

**Estimated new tests:** ~60
**Estimated total after:** ~2,687

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
- **Prompt fragments are optional** — if a task_type fragment doesn't exist, PromptService silently skips it. Handlers will still work, just without task-specific instructions. But planning handlers need these fragments to produce correct output structure (YAML frontmatter, unknown classification, sufficiency table).
- **`GovernanceIncorporateFeedbackHandler` needs custom `validate_inputs()` and `_build_user_prompt()`** — it's the only handler that's not a pure thin subclass. It must enforce D17 (fail on missing `plan_artifact_refs`) and include refinement instructions in the prompt.
- **`manifest.yaml` integrity** — prompt fragments need SHA256 hashes in the manifest. The assembler validates these at load time.
- **No executor changes** — planning workloads use existing sequential dispatch. If tests try to run planning tasks through the executor, they'll need the same mock setup as existing cycle execution tests.
- **Existing `CYCLE_TASK_STEPS` remain for `workload_type=None`** — the legacy branch is unchanged. Only workload-typed runs use the new step selection.
- **`prompts/` directory does not exist yet** — the prompt fragment files are forward-looking. PromptService fragment loading from disk is not yet wired. Handlers work without them; fragments become effective once the loader exists.
