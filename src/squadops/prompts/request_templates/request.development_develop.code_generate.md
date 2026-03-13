---
template_id: request.development_develop.code_generate
version: "1"
required_variables:
  - prd
  - file_structure_guidance
  - example_structure
optional_variables:
  - impl_plan
  - strategy
  - prior_outputs
---
## Product Requirements Document

{{prd}}
{{impl_plan}}
{{strategy}}
{{file_structure_guidance}}

Target file structure:
{{example_structure}}
{{prior_outputs}}
