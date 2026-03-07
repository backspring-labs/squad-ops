# SIP: Time Budget Awareness in Planning Prompts — Implementation Plan

## Context

Planning should produce scope proportional to the available cycle time budget. `time_budget_seconds` already exists as a hard Prefect flow timeout (`distributed_flow_executor.py`), flows through `applied_defaults` → `resolved_config` → handler inputs, and is already in `_APPLIED_DEFAULTS_EXTRA_KEYS`. But planning handlers never read it. This SIP injects time budget context into planning user prompts.

The SIP spec is at `sips/proposed/SIP-Time-Budget-Awareness-Planning-Prompts.md`.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Override `_build_user_prompt` in `_PlanningTaskHandler`, not in each handler | All 7 handlers (5 planning + 2 refinement) inherit from `_PlanningTaskHandler`. One override covers 6 of them. `GovernanceIncorporateFeedbackHandler` has its own override and gets a separate injection. Verified: `DataResearchContextHandler`, `StrategyFrameObjectiveHandler`, `DevelopmentDesignPlanHandler`, `QADefineTestStrategyHandler`, `GovernanceAssessReadinessHandler`, `GovernanceIncorporateFeedbackHandler`, `QAValidateRefinementHandler`. |
| D2 | User prompt injection, not system prompt | Consistent with implementation handlers (`generation_timeout`, `dev_capability`). System prompt comes from prompt fragments (task_type layer); runtime config goes in user prompt. |
| D3 | No section when budget absent or zero | Fully backward compatible. Tests without `time_budget_seconds` in inputs see no change. |
| D4 | Resolve budget in `handle()`, pass to `_build_user_prompt` as parameter | Keeps prompt builder stateless. No `self._resolved_config` on handler instance. |
| D5 | Differentiate refinement wording from initial planning | Initial planning: "scope to fit the budget." Refinement: "preserve budget realism while incorporating feedback." Prevents refinement from re-expanding scope. |
| D6 | Keep prompt guidance short and operational | Three direct sentences. Avoids verbose heuristics that invite LLM sermonizing about constraints instead of producing the plan. |
| D7 | No `planning.yaml` changes | `time_budget_seconds` already exists in the stack. Adding a commented config line adds review surface for zero operator value. |
| D8 | Tests assert on section presence and key phrases, not exact prose | Durable through wording tuning. No brittle exact-match on full injected text. |
| D9 | No runtime estimation or adaptive planning | No budget tiers, duration estimates, per-role allocations, or re-planning. Those are a different class of feature. |

---

## Phase 1: Module-Level Utilities

**File: `src/squadops/capabilities/handlers/planning_tasks.py`**

### 1.1 `_format_time_budget(seconds: int) -> str`

Pure function. Add after `_VALID_READINESS` (line 39), before the `_PlanningTaskHandler` class.

```python
def _format_time_budget(seconds: int) -> str:
    """Format seconds as coarse human-readable duration for planning guidance.

    Uses hours/minutes granularity; sub-minute remainders are dropped.
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts)
```

### 1.2 `_build_time_budget_section(time_budget_seconds: int | None) -> str`

Returns empty string when None/zero. When positive:

```python
def _build_time_budget_section(time_budget_seconds: int | None) -> str:
    """Build time budget prompt section for initial planning handlers."""
    if not time_budget_seconds or time_budget_seconds <= 0:
        return ""
    formatted = _format_time_budget(time_budget_seconds)
    return (
        f"\n\n## Time Budget\n\n"
        f"This cycle has a **{formatted}** time budget ({time_budget_seconds}s). "
        f"Scope only what can reasonably be planned and executed within this window. "
        f"Prefer a smaller executable plan over a broader incomplete plan. "
        f"Explicitly defer out-of-budget work."
    )
```

### 1.3 `_build_refinement_time_budget_section(time_budget_seconds: int | None) -> str`

Same conditional logic, different wording (D5):

```python
def _build_refinement_time_budget_section(time_budget_seconds: int | None) -> str:
    """Build time budget prompt section for refinement handlers."""
    if not time_budget_seconds or time_budget_seconds <= 0:
        return ""
    formatted = _format_time_budget(time_budget_seconds)
    return (
        f"\n\n## Time Budget\n\n"
        f"This cycle has a **{formatted}** time budget ({time_budget_seconds}s). "
        f"Preserve budget realism while incorporating feedback. "
        f"Do not expand scope beyond what can execute within this cycle budget."
    )
```

---

## Phase 2: Handler Changes

**File: `src/squadops/capabilities/handlers/planning_tasks.py`**

### 2.1 Override `_build_user_prompt` in `_PlanningTaskHandler`

The parent `_CycleTaskHandler._build_user_prompt(prd, prior_outputs)` is at `cycle_tasks.py:72-84`. Override in `_PlanningTaskHandler` to add a `time_budget_seconds` parameter and inject the section between PRD and Prior Analysis:

```python
def _build_user_prompt(
    self,
    prd: str,
    prior_outputs: dict[str, Any] | None,
    time_budget_seconds: int | None = None,
) -> str:
    """Assemble user prompt with optional time budget awareness."""
    parts = [f"## Product Requirements Document\n\n{prd}"]
    budget_section = _build_time_budget_section(time_budget_seconds)
    if budget_section:
        parts.append(budget_section)
    if prior_outputs:
        parts.append("\n\n## Prior Analysis from Upstream Roles\n")
        for role, summary in prior_outputs.items():
            parts.append(f"### {role}\n{summary}\n")
    parts.append(f"\nPlease provide your {self._role} analysis and deliverables.")
    return "\n".join(parts)
```

### 2.2 Update `_PlanningTaskHandler.handle()` to resolve and pass budget

At line 61-64, change from:

```python
prd = inputs.get("prd", "")
prior_outputs = inputs.get("prior_outputs")

user_prompt = self._build_user_prompt(prd, prior_outputs)
```

To:

```python
prd = inputs.get("prd", "")
prior_outputs = inputs.get("prior_outputs")
time_budget_seconds = inputs.get("resolved_config", {}).get("time_budget_seconds")

user_prompt = self._build_user_prompt(prd, prior_outputs, time_budget_seconds)
```

### 2.3 Update `GovernanceIncorporateFeedbackHandler._build_user_prompt`

Add `time_budget_seconds` parameter (D5). Inject `_build_refinement_time_budget_section` after the PRD section, before the artifact contents:

Current signature (line 361-365):
```python
def _build_user_prompt(
    self,
    prd: str,
    prior_outputs: dict[str, Any] | None,
) -> str:
```

New signature:
```python
def _build_user_prompt(
    self,
    prd: str,
    prior_outputs: dict[str, Any] | None,
    time_budget_seconds: int | None = None,
) -> str:
```

Insert after the PRD `parts.append`:
```python
budget_section = _build_refinement_time_budget_section(time_budget_seconds)
if budget_section:
    parts.append(budget_section)
```

---

## Phase 3: Tests

**File: `tests/unit/capabilities/test_planning_handlers.py`**

Add three new test classes at the end of the file (after `TestD17ArtifactContentValidation`). Import `_format_time_budget`, `_build_time_budget_section`, `_build_refinement_time_budget_section` from `planning_tasks`.

### 3.1 `TestFormatTimeBudget` (~6 tests)

Parametrized over `_format_time_budget`:

| Input | Expected output |
|-------|-----------------|
| 45 | "45 seconds" |
| 1 | "1 second" |
| 60 | "1 minute" |
| 1800 | "30 minutes" |
| 3600 | "1 hour" |
| 5400 | "1 hour 30 minutes" |
| 7200 | "2 hours" |

Assert exact output — this is a pure formatter, not LLM prose.

### 3.2 `TestBuildTimeBudgetSection` (~4 tests)

- `None` → returns `""`
- `0` → returns `""`
- `-100` → returns `""`
- `7200` → contains `"## Time Budget"`, contains `"2 hours"`, contains `"defer"`

One test for the refinement variant:
- `1800` → contains `"## Time Budget"`, contains `"30 minutes"`, contains `"Preserve budget realism"`

### 3.3 `TestTimeBudgetAwareness` (~6-8 tests)

These exercise real `handle()` calls and assert on the user prompt sent to `llm.chat()`:

**Budget present** — parametrized across all 7 handler classes:
- Set `inputs["resolved_config"] = {"time_budget_seconds": 7200}`
- Assert user prompt contains `"Time Budget"` and `"2 hours"`
- For `GovernanceIncorporateFeedbackHandler`, also provide `artifact_contents` to satisfy D17
- For `GovernanceIncorporateFeedbackHandler`, assert user prompt contains `"Preserve budget realism"` (not `"defer"`)

**Budget absent** — parametrized across all 7 handler classes:
- No `resolved_config` in inputs
- Assert user prompt does NOT contain `"Time Budget"`

**Budget zero** — single representative handler:
- `inputs["resolved_config"] = {"time_budget_seconds": 0}`
- Assert user prompt does NOT contain `"Time Budget"`

**Budget explicitly None** — single representative handler:
- `inputs["resolved_config"] = {"time_budget_seconds": None}`
- Assert user prompt does NOT contain `"Time Budget"`

### Test extraction pattern

All `handle()`-based tests use the existing pattern from `TestHandlePriorOutputs`:
```python
call_args = mock_context.ports.llm.chat.call_args
user_msg = call_args[0][0][1].content
```

For `GovernanceIncorporateFeedbackHandler`, use the existing `_inputs_with_artifact` pattern (provide `artifact_contents` with real content to pass D17).

---

## Phase 4: Verification

1. `ruff check src/squadops/capabilities/handlers/planning_tasks.py` — clean
2. `ruff format src/squadops/capabilities/handlers/planning_tasks.py` — clean
3. `pytest tests/unit/capabilities/test_planning_handlers.py -v` — all pass (existing + new)
4. `./scripts/dev/run_regression_tests.sh -v` — full regression suite passes

---

## Files Modified

| File | Change |
|------|--------|
| `sips/proposed/SIP-Time-Budget-Awareness-Planning-Prompts.md` | Already written |
| `src/squadops/capabilities/handlers/planning_tasks.py` | 3 module-level helpers, override `_build_user_prompt` in `_PlanningTaskHandler`, update `GovernanceIncorporateFeedbackHandler._build_user_prompt` |
| `tests/unit/capabilities/test_planning_handlers.py` | 3 new test classes (~18 tests) |

## What Does NOT Change

- No schema, model, port, adapter, API, or CLI changes
- No prompt fragment changes
- No cycle request profile YAML changes
- No executor changes (hard timeout behavior unchanged)
- No `_APPLIED_DEFAULTS_EXTRA_KEYS` changes (key already exists)
