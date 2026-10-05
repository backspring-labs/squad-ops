---
template_id: request.proposal_convention_error_envelope
version: "1"
required_variables:
  - envelope
  - module
---
**Every contract error comes back as the frozen envelope** `{{envelope}}`, at the status the
manifest's error contract gives its code, written by the frozen `{{module}}`. A criterion names the
code (`body.error.code`), never another shape, and a new error adds its code to the
`error_contract` in the same change.
