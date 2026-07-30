---
template_id: request.qa_test_dom_anchor_appendix
version: "1"
required_variables:
  - testid_lines
optional_variables: []
---
**DOM ANCHOR CONTRACT (authoritative — query ONLY these anchors):**
{{testid_lines}}

These data-testid anchors are pinned by the interface manifest and injected
into the view author's prompt — they are the only DOM surface the views
promise. Locate elements exclusively via these anchors
(`screen.getByTestId(...)` / `[data-testid="..."]`). Do NOT assert roles,
visible text, tag structure, element counts, or CSS — the views promise none
of that, so such assertions fail against correct implementations and send
repairs chasing render details instead of behavior. Assert behavior through
the anchors: what an anchored element contains after an action, appears after
a load, or shows after an error.
