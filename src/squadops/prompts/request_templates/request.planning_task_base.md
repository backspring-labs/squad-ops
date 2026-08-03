---
template_id: request.planning_task_base
version: "2"
required_variables:
  - prd
  - role
optional_variables:
  - time_budget_section
  - prior_outputs
  - rejection_context_section
---
## Product Requirements Document

{{prd}}
{{time_budget_section}}
{{prior_outputs}}
{{rejection_context_section}}
Please provide your {{role}} analysis and deliverables.
