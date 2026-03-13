---
template_id: request.planning_task_base
version: "1"
required_variables:
  - prd
  - role
optional_variables:
  - time_budget_section
  - prior_outputs
---
## Product Requirements Document

{{prd}}
{{time_budget_section}}
{{prior_outputs}}
Please provide your {{role}} analysis and deliverables.
