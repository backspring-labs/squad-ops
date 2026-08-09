---
template_id: request.manifest_revision_request_appendix
version: "1"
required_variables:
  - reviewer_notes
optional_variables:
  - prior_manifest
---
## YOUR PREVIOUS DESIGN WAS RETURNED — revise it

This is not a fresh start. The manifest below came back — either from a reviewer who read it
and asked for a change, or from a deterministic gate that rejected the plan built on it.
Your job is to **revise that document**, not to design the application again.

### What came back

{{reviewer_notes}}
{{prior_manifest}}

### How to revise

- **Change what was raised, and leave the rest alone.** Everything not mentioned was
  acceptable; re-deriving it risks replacing correct decisions with different ones and makes
  the next reader check the whole design again.
- **If a note answers a question you declared `unresolved`,** resolve that decision: replace
  it with a `choice` and a `warrant` naming where the answer came from. That is what the
  question was for.
- **If you disagree,** say so in the decision's `warrant` rather than silently complying or
  silently ignoring. A design record that hides a disagreement is worse than either.
- Re-emit the **complete** `interface_manifest.yaml`. The gates run again on the whole
  document, so a partial emission fails on everything you left out.
