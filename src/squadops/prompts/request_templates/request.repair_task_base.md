---
template_id: request.repair_task_base
version: "2"
required_variables:
  - prd
  - role
optional_variables:
  - verification_context
  - prior_outputs
  - cross_cycle_lessons_section
---
## Product Requirements Document

{{prd}}
{{verification_context}}{{cross_cycle_lessons_section}}
{{prior_outputs}}
Please provide your {{role}} analysis and deliverables.
