---
template_id: request.governance_correction_decision
version: "2"
required_variables:
  - prd
optional_variables:
  - failure_analysis
---
## PRD

{{prd}}
{{failure_analysis}}

## Diagnostic question (non-operative)

Today the framework can only run continue/patch/rewind/abort. A future
version will allow `add_task` (insert a new task to cover a gap) and
`tighten_acceptance` (strengthen an existing task's acceptance criteria).
In addition to your operative decision above, answer: if those two plan
changes were available, would you have chosen one of them, and why? Use
`none` when continue/patch/rewind/abort fully addresses the failure.

This answer is captured for measurement only — it does not run anything.
