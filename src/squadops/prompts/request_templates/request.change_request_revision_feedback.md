---
template_id: request.change_request_revision_feedback
version: "1"
required_variables:
  - refusals
---
### Your change request was refused — revise it

The checks below are deterministic: they apply your delta to the accepted manifest and run the same
gates every manifest passes. Each line names one refusal; all of them are listed.

{{refusals}}

Emit the whole corrected `change_request.yaml` again, in one fenced block. A change that reaches
outside the allowed files is refused whole: narrow the change itself, do not leave parts out of the
delta that the criteria need.
