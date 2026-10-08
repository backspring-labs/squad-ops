---
template_id: request.proposal_convention_undeclared_field_ignored
version: "1"
required_variables: []
---
**A request field the manifest does not declare is ignored.** The frozen request models accept a
request that carries an extra field and drop the field, so the request succeeds as if it were not
there. So before a change adds the field, a run created with `"capacity": 2` is created without a
capacity, and "a run created with capacity 2 takes a second join" already holds. A criterion about a
new request field has to observe something the accepted application cannot do while it ignores the
field: the value coming back, or a request refused because of it.
