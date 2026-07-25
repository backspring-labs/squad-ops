---
template_id: request.development_develop.focused_build_task
version: "1"
required_variables:
  - focus
  - expected_files
  - prd
optional_variables:
  - description
  - fill_only_section
  - contract_expectations
  - narrative_criteria
  - prior_artifacts
---
## Build Task: {{focus}}

{{description}}

{{fill_only_section}}

### Expected Output Files

{{expected_files}}

{{contract_expectations}}

{{narrative_criteria}}

### Context

PRD:

{{prd}}

{{prior_artifacts}}

Produce ONLY the files listed in Expected Output Files. Use fenced code blocks with
```language:path/to/file``` format. Do not reproduce files from prior artifacts.
