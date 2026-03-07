---
title: Time Budget Awareness in Planning Prompts
status: implemented
author: SquadOps Architecture
created_at: '2026-03-07'
sip_number: 82
updated_at: '2026-03-07T11:22:37.722952Z'
---
# SIP: Time Budget Awareness in Planning Prompts

| Field | Value |
|-------|-------|
| Status | Proposed |
| Authors | SquadOps Architecture |
| Created | 2026-03-07 |

------------------------------------------------------------------------

## 1. Abstract

Planning should produce scope proportional to the available cycle time budget.
`time_budget_seconds` already exists as a hard Prefect flow timeout, but
planning handlers have no awareness of it. This SIP injects time budget
context into planning user prompts so agents scope their deliverables to
fit the available execution window.

------------------------------------------------------------------------

## 2. Problem Statement

`time_budget_seconds` already exists as infrastructure:
- Set in cycle request profile YAML (`defaults.time_budget_seconds`)
- Flows through `applied_defaults` → `resolved_config` → handler inputs
- Enforced as a hard Prefect flow timeout in `distributed_flow_executor.py`

But planning handlers never read this value. The result:
- **Short budgets**: agents produce ambitious plans that get killed mid-execution
- **Long budgets**: agents under-scope because nothing signals they have room

**Motivating use case**: bounded-cycle testing on dev hardware (e.g., DGX Spark)
where progressively complex sample apps need time-constrained cycle request
profiles that exercise full squad coordination.

------------------------------------------------------------------------

## 3. Design Decisions

**D1: Inject in `_PlanningTaskHandler._build_user_prompt`, not individual handlers.**
All 5 planning handlers inherit from `_PlanningTaskHandler`. Overriding
`_build_user_prompt` once provides coverage to all. The refinement handler
`GovernanceIncorporateFeedbackHandler` has its own override and gets a
separate injection.

**D2: User prompt, not system prompt.**
Consistent with how `generation_timeout` and `dev_capability` are injected
in implementation handlers. System prompt comes from prompt fragments
(task_type layer); runtime config goes in user prompt.

**D3: Conditional injection — no section when no budget.**
When `time_budget_seconds` is absent or zero, no time section appears.
Fully backward compatible.

**D4: Scoping guidance, not just a number.**
The injected section includes brief, operational scoping guidance — not
verbose heuristics that invite prompt sermonizing.

**D5: Resolve budget in `handle()`, pass to prompt helper.**
`_PlanningTaskHandler.handle()` resolves the time budget from `inputs` and
passes it into `_build_user_prompt` as a parameter. The prompt builder
remains stateless — no `self._resolved_config` accumulation on the handler
instance.

**D6: Differentiate refinement wording from initial planning.**
Initial planning scopes the plan to fit the budget. Refinement preserves
budget realism while incorporating feedback. The refinement handler gets
a tailored variant rather than identical text.

**D7: No runtime estimation or adaptive planning.**
This SIP does **not** introduce budget tiers, dynamic plan complexity
classes, estimated task durations, per-role time allocations, automatic
decomposition based on remaining time, or adaptive re-planning based on
elapsed runtime. Those belong to a different class of feature.

------------------------------------------------------------------------

## 4. Specification

### 4.1 Time formatting utility

Module-level `_format_time_budget(seconds: int) -> str` in `planning_tasks.py`.
Converts raw seconds to human-readable form:

| Input | Output |
|-------|--------|
| 60 | "1 minute" |
| 1800 | "30 minutes" |
| 3600 | "1 hour" |
| 5400 | "1 hour 30 minutes" |
| 7200 | "2 hours" |
| 45 | "45 seconds" |

### 4.2 Time budget prompt section

Module-level `_build_time_budget_section(time_budget_seconds: int | None) -> str`.
Returns empty string when None/zero. When positive, returns:

```
## Time Budget

This cycle has a **{formatted_time}** time budget ({seconds}s).
Scope only what can reasonably be planned and executed within this window.
Prefer a smaller executable plan over a broader incomplete plan.
Explicitly defer out-of-budget work.
```

### 4.3 Refinement time budget section

Module-level `_build_refinement_time_budget_section(time_budget_seconds: int | None) -> str`.
Same conditional logic. When positive, returns:

```
## Time Budget

This cycle has a **{formatted_time}** time budget ({seconds}s).
Preserve budget realism while incorporating feedback. Do not expand scope beyond what can execute within this cycle budget.
```

### 4.4 Handler changes

1. `_PlanningTaskHandler.handle()` resolves
   `time_budget = inputs.get("resolved_config", {}).get("time_budget_seconds")`
   and passes it to `_build_user_prompt`.

2. `_PlanningTaskHandler._build_user_prompt(prd, prior_outputs, time_budget_seconds)`
   overrides the inherited base method. Injects the time budget section
   between the PRD and Prior Analysis sections.

3. `GovernanceIncorporateFeedbackHandler._build_user_prompt(prd, prior_outputs, time_budget_seconds)`
   injects the refinement variant after the PRD section in its existing override.

------------------------------------------------------------------------

## 5. Backward Compatibility

- No schema, model, port, adapter, API, or CLI changes
- No prompt fragment changes
- `time_budget_seconds` key already exists in `_APPLIED_DEFAULTS_EXTRA_KEYS`
- When the key is absent from `resolved_config`, behavior is identical to today

------------------------------------------------------------------------

## 6. Test Plan

| Suite | Tests | Purpose |
|-------|-------|---------|
| `TestFormatTimeBudget` | ~6 | Parametrized: seconds → human string edge cases |
| `TestBuildTimeBudgetSection` | ~4 | None/zero → empty, positive → section with formatted time and scoping phrase |
| `TestTimeBudgetAwareness` | ~8 | Parametrized across handlers: budget present → section in user prompt, absent → no section |

~18 new tests. Tests assert on section presence/absence, formatted time
strings, and a small number of critical scoping phrases — not exact-match
on injected prose, to stay durable through wording tuning.

------------------------------------------------------------------------

## 7. Acceptance Criteria

1. A time-budget section is included in planning user prompts when a positive
   `time_budget_seconds` exists in `resolved_config`.
2. No time-budget section is included when the budget is absent or zero.
3. The section expresses the budget in human-readable form and instructs the
   planner to keep scope executable.
4. The refinement path includes budget-aware guidance with wording appropriate
   to refinement (preserve realism, not re-scope from scratch).

------------------------------------------------------------------------

## 8. Files Modified

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | `_format_time_budget`, `_build_time_budget_section`, `_build_refinement_time_budget_section`, override `_build_user_prompt` |
| `tests/unit/capabilities/test_planning_handlers.py` | New test classes |

### What does NOT change

- No schema changes (key already in `_APPLIED_DEFAULTS_EXTRA_KEYS`)
- No model/port/adapter changes
- No prompt fragment changes (fragments are system prompt; this goes in user prompt)
- No executor changes (hard timeout behavior unchanged)
- No API/CLI changes
- No cycle request profile YAML changes
