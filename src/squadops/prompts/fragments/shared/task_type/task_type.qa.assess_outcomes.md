---
fragment_id: task_type.qa.assess_outcomes
layer: task_type
version: "0.9.18"
roles: ["qa"]
---
## QA Outcome Assessment (Wrap-Up Workload)

You are performing a planned-vs-actual comparison for a wrap-up workload. Your
goal is to evaluate each acceptance criterion against available evidence and
detect deviations between what was planned and what was delivered.

### Scope Baseline Precedence

Use this order to determine what was planned:

1. **Run contract** (highest authority) — if present, use its acceptance criteria
2. **Planning artifact** — if no run contract, use the planning artifact's criteria
3. **Plan deltas** — incorporate any corrections that modified the original plan

### Assessment Rules

- Evaluate each acceptance criterion as: `met`, `partially_met`, or `not_met`
- `partially_met` counts as NOT met for confidence classification purposes
- Challenge completion claims that lack supporting evidence
- Cross-reference QA findings against completion claims — flag contradictions
- Do NOT set the confidence classification — that is the lead agent's decision

### Output Format

Produce `outcome_assessment.md` with:

1. **Acceptance criteria matrix** — criterion, status, supporting evidence, gaps
2. **Deviation log** — planned vs actual for each significant deviation
3. **QA findings cross-reference** — any test failures or QA concerns that
   contradict completion claims
4. **Summary statistics** — counts of met/partially_met/not_met criteria
