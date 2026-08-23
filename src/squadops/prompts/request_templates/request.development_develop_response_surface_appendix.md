---
template_id: request.development_develop_response_surface_appendix
version: "2"
required_variables:
  - response_lines
optional_variables: []
---
**SUCCESS RESPONSE (authoritative — the suite asserts exactly this):**
{{response_lines}}

Each line states one endpoint's success status and the floor for its response body, generated
from the interface manifest. The generated test shells assert both in their frozen region, so
a handler that returns the wrong status — or omits a listed field, or returns an array of the
wrong element kind — fails deterministically.

Return the stated status explicitly. A line that says `HTTP 201` means the framework default is
wrong for that endpoint: the skeleton's stub carries the status only as a comment in the body
you are replacing, so if you do not write it, it is gone. A handler that returns a correct body
under a 200 the contract pins at 201 fails just as hard as a missing field.

This is a floor, not a schema. Additional fields are yours to choose and nothing checks them;
optional fields may be omitted entirely; the values are the app's business, only presence and
element kind are pinned. Return the listed fields and you cannot fail this check.

Element kind is the one that is easy to miss. A field declared as an array of strings must
contain strings, not objects wrapping them — returning `[{"name": "ada"}]` where the manifest
says an array of strings is a contract break the status code cannot show, and it has killed a
run before.
