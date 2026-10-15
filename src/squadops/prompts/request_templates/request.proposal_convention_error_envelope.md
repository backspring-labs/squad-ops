---
template_id: request.proposal_convention_error_envelope
version: "2"
required_variables:
  - envelope
  - module
---
**Every contract error comes back as the frozen envelope** `{{envelope}}`, at the status the
manifest's error contract gives its code, written by the frozen `{{module}}`. A criterion names the
code (`body.error.code`), never another shape, and a new error adds its code to the
`error_contract` in the same change.

**An error's wording is declared on its code,** never on an endpoint: `modify` the `error_code`
with its `http` and a `message`, as in `{ http: 409, message: "This name has already joined." }`.
The frozen `{{module}}` then returns that message word for word, wherever the code is raised, and
every later change keeps it until one declares another. A criterion on the wording reads
`body.error.message`.
