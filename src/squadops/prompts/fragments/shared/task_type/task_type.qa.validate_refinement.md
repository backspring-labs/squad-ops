---
fragment_id: task_type.qa.validate_refinement
layer: task_type
version: "0.9.16"
roles: ["qa"]
---
## QA Refinement Validation (Refinement Workload)

You are validating that a refined planning artifact still meets acceptance
criteria after feedback incorporation.

### Deliverables

1. **Criteria check** — verify each acceptance criterion from the original
   test strategy still holds after refinement
2. **Gap analysis** — identify any gaps introduced by the changes
3. **Recommendation** — confirm refinement is valid or flag issues

### Output Format

Produce a structured markdown document (`refinement_validation.md`) with a
checklist of acceptance criteria and their pass/fail status after refinement.
