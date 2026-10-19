---
template_id: request.repair_task_base
version: "3"
required_variables:
  - prd
  - role
optional_variables:
  - verification_context
  - prior_outputs
  - task_instructions_section
  - cross_cycle_lessons_section
---
## Product Requirements Document

{{prd}}
{{verification_context}}{{task_instructions_section}}{{cross_cycle_lessons_section}}
{{prior_outputs}}
Please provide your {{role}} analysis and deliverables.
