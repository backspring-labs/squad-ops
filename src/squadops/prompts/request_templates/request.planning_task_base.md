---
template_id: request.planning_task_base
version: "6"
required_variables:
  - prd
  - role
optional_variables:
  - increment_section
  - prior_cycle_section
  - cross_cycle_lessons_section
  - target_stack_section
  - time_budget_section
  - prior_outputs
  - rejection_context_section
  - authoring_rules_section
---
## Product Requirements Document

{{prd}}
{{increment_section}}
{{prior_cycle_section}}{{cross_cycle_lessons_section}}
{{target_stack_section}}
{{time_budget_section}}
{{prior_outputs}}
{{authoring_rules_section}}
{{rejection_context_section}}
Please provide your {{role}} analysis and deliverables.
