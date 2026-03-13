---
template_id: request.governance_incorporate_feedback
version: "1"
required_variables:
  - prd
  - role
optional_variables:
  - time_budget_section
  - artifact_contents
  - refinement_instructions
  - prior_outputs
---
## Product Requirements Document

{{prd}}
{{time_budget_section}}
{{artifact_contents}}
{{refinement_instructions}}
{{prior_outputs}}
Please provide your {{role}} analysis and deliverables.
