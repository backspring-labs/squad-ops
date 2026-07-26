---
template_id: request.development_develop_model_surface_appendix
version: "1"
required_variables:
  - surface_lines
optional_variables: []
---
**MODEL SURFACE (authoritative — use these names exactly):**
{{surface_lines}}

These are the complete importable contents of the frozen data modules, generated from
the interface manifest. Every class, field, and store above exists; nothing else does.
A near-miss field name does not fail at import or compile — the call raises at request
time and the endpoint returns HTTP 500, which only surfaces later as a behavioural test
failure and a failed probe.
