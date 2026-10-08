---
template_id: request.proposal_convention_undeclared_field_unfixed
version: "1"
required_variables: []
---
**What happens to a request field the manifest does not declare is not fixed.** The route handlers
that read a request body are written by each build, so before a change adds a field, one correct
build ignores it and another refuses the request. A criterion therefore does not depend on how the
accepted application treats the new field. It observes what only the change makes true: the value
coming back, or a request refused because of it.
