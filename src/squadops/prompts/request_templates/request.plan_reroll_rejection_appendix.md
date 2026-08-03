---
template_id: request.plan_reroll_rejection_appendix
version: "1"
required_variables:
  - rejection_reasons
optional_variables:
  - rejected_plan_section
---
## PRIOR ATTEMPT REJECTED (authoritative — revise, do not repeat)

An earlier framing of this cycle authored an implementation plan that failed system plan validation. The reasons below are deterministic validator rules, not reviewer taste — a plan with the same shape will be rejected again, and re-roll attempts are limited. Author a revised plan that fixes every listed defect. Keep whatever structure of the prior attempt was sound; do not discard good task decomposition because one rule fired.

Rejection reasons:
{{rejection_reasons}}
{{rejected_plan_section}}
