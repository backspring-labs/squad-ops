---
fragment_id: task_type.data.classify_unresolved
layer: task_type
version: "0.9.18"
roles: ["data"]
---
## Data Unresolved Issue Classification (Wrap-Up Workload)

You are categorizing unresolved items from the implementation run. Your goal is
to classify each item by type and severity, and suggest ownership for resolution.

### Issue Type Categories

Use exactly one of these types per item:

- `defect` — bug or functional regression
- `design_debt` — architectural shortcut or technical debt
- `test_gap` — missing or insufficient test coverage
- `environmental` — infrastructure or environment issue
- `dependency` — blocked by external dependency
- `operator_decision_pending` — requires human operator decision
- `deferred_enhancement` — feature or improvement deferred to future cycle

### Severity Levels

Use exactly one of these severities per item:

- `critical` — blocks production readiness
- `high` — significant impact, should be resolved before next milestone
- `medium` — moderate impact, can be addressed in next cycle
- `low` — minor impact, cosmetic or convenience improvement

### Suggested Owner

Assign each item to one of: `lead`, `qa`, `dev`, `data`, `strat`, `builder`,
or `operator` (for items requiring human decision).

### Output Format

Produce `unresolved_items.md` with a table containing these columns:

| # | Description | issue_type | severity | Impact | suggested_owner | Recommended Action |

Include a summary section with counts by type and severity.
