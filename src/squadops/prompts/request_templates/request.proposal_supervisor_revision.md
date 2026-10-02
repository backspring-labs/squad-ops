---
template_id: request.proposal_supervisor_revision
version: "1"
required_variables:
  - prior_version
  - supervisor_note
  - prior_change_request
---

### The supervisor returned version {{prior_version}} of your proposal for revision

The supervisor does not edit a proposal: you write the next version, and it is ruled on afresh.
Their note, word for word:

> {{supervisor_note}}

The version they returned, as you emitted it. Revise it to answer the note; keep what the note
does not touch, and emit the whole revised `change_request.yaml`.

```yaml
{{prior_change_request}}
```
