---
template_id: request.qa_test_proposed_behaviours_appendix
version: "1"
required_variables: []
---

## Behaviour you would test but nothing accepted requires: propose it

Write it as a proposal instead of a test. Emit, beside your test files, one fenced block whose header
carries `proposed_behaviours.yaml`. It is stored for the campaign's next proposal, never written to
the application and never run, so it cannot fail or repair this build. Leave it out when you have
nothing to propose.

```yaml:proposed_behaviours.yaml
proposed_behaviours:          # 1 to 10 entries, and no other top-level key
  - behaviour: "Two runs with the same date keep the order they were created in"
    why: "The list reorders itself between refreshes when dates tie"
    surface_kind: endpoint    # endpoint | client_route
    surface: "GET /runs"      # "METHOD /path", or a client route's path
```

Each entry has exactly those four fields, none blank.
