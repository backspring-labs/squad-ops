---
template_id: request.development_develop_testid_surface_appendix
version: "1"
required_variables:
  - testid_lines
optional_variables: []
---
**DOM ANCHOR CONTRACT (authoritative — attach and preserve these data-testid attributes):**
{{testid_lines}}

These anchors are pinned by the interface manifest and are the surface the QA
suite queries. The root anchor is already stamped on each view stub's container
— keep it there. Attach every other listed anchor to the element that plays that
role as you build the view (a list gets its list anchor, each item its item
anchor, each form and input its own). Do not rename, remove, or invent anchors:
a missing anchor fails the suite against a correct-looking view, and an
unlisted one is invisible to verification.
