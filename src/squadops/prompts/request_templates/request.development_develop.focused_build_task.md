---
template_id: request.development_develop.focused_build_task
version: "8"
required_variables:
  - focus
  - expected_files
  - prd
optional_variables:
  - description
  - fill_only_section
  - increment_views_section
  - contract_expectations
  - narrative_criteria
  - prior_artifacts
  - disputed_checks_section
  - prior_cycle_section
  - task_instructions_section
  - project_instructions_section
  - source_repository_section
  - cross_cycle_lessons_section
---
## Build Task: {{focus}}

{{description}}

{{fill_only_section}}

{{increment_views_section}}

{{source_repository_section}}{{prior_cycle_section}}{{task_instructions_section}}{{project_instructions_section}}{{cross_cycle_lessons_section}}

### Expected Output Files

{{expected_files}}

{{contract_expectations}}

{{narrative_criteria}}

### Context

PRD:

{{prd}}

{{prior_artifacts}}

Produce ONLY the files listed in Expected Output Files. Use fenced code blocks with
```language:<the file's own path>``` format, using the paths named above exactly as
written — never a placeholder or a prefixed variant. Do not reproduce files from prior
artifacts.

{{disputed_checks_section}}
