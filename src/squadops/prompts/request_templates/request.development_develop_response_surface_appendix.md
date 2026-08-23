---
template_id: request.development_develop_response_surface_appendix
version: "1"
required_variables:
  - response_lines
optional_variables: []
---
**SUCCESS RESPONSE SHAPE (authoritative — the suite asserts exactly this):**
{{response_lines}}

Each line states the floor for one endpoint's success body, generated from the interface
manifest. The generated test shells assert it in their frozen region, so a response that
omits a listed field — or returns an array of the wrong element kind — fails deterministically
no matter what the endpoint's status code is.

This is a floor, not a schema. Additional fields are yours to choose and nothing checks them;
optional fields may be omitted entirely; the values are the app's business, only presence and
element kind are pinned. Return the listed fields and you cannot fail this check.

Element kind is the one that is easy to miss. A field declared as an array of strings must
contain strings, not objects wrapping them — returning `[{"name": "ada"}]` where the manifest
says an array of strings is a contract break the status code cannot show, and it has killed a
run before.
