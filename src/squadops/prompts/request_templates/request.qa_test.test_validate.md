---
template_id: request.qa_test.test_validate
version: "6"
required_variables:
  - prd
  - test_supplement
optional_variables:
  - validation_plan
  - source_files
  - scaffold_harness_section
  - source_repository_section
  - prior_outputs
  - task_instructions_section
  - project_instructions_section
  - cross_cycle_lessons_section
---
## Product Requirements Document

{{prd}}
{{validation_plan}}
{{source_files}}

{{scaffold_harness_section}}

{{test_supplement}}{{source_repository_section}}{{task_instructions_section}}{{project_instructions_section}}{{cross_cycle_lessons_section}}
{{prior_outputs}}
