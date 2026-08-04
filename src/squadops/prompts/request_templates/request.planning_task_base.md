---
template_id: request.planning_task_base
version: "3"
required_variables:
  - prd
  - role
optional_variables:
  - time_budget_section
  - prior_outputs
  - rejection_context_section
  - authoring_rules_section
---
## Product Requirements Document

{{prd}}
{{time_budget_section}}
{{prior_outputs}}
{{authoring_rules_section}}
{{rejection_context_section}}
Please provide your {{role}} analysis and deliverables.
