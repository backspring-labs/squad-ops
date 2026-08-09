---
template_id: request.manifest_revision_request_appendix
version: "1"
required_variables:
  - reviewer_notes
optional_variables:
  - prior_manifest
---
## REVISION REQUESTED — a reviewer returned your previous design

This is not a fresh start. A human read the interface manifest below, did not reject it,
and asked for a specific change. Your job is to **revise that document**, not to design the
application again.

### What the reviewer said

{{reviewer_notes}}
{{prior_manifest}}

### How to revise

- **Change what was asked about, and leave the rest alone.** Everything the reviewer did not
  raise was acceptable; re-deriving it risks replacing correct decisions with different ones
  and makes the reviewer read the whole design a second time.
- **If the note answers a question you declared `unresolved`,** resolve that decision: replace
  it with a `choice` and a `warrant` citing the reviewer's answer as its source. That is what
  the question was for.
- **If you disagree,** say so in the decision's `warrant` rather than silently complying or
  silently ignoring. A design record that hides a disagreement is worse than either.
- Re-emit the **complete** `interface_manifest.yaml`. The gates run again on the whole
  document, so a partial emission fails on everything you left out.
