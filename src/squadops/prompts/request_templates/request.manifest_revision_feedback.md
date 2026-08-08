---
template_id: request.manifest_revision_feedback
version: "1"
required_variables:
  - findings
---
### The manifest you just emitted was rejected — revise it

The gates below are deterministic: they read the document, not the build. Each line names
one defect and what to do about it.

{{findings}}

Re-emit the **complete** `interface_manifest.yaml` with every defect above fixed. Keep
everything that was not named — the rejection is about specific entries, not a request to
start over, and re-deriving the parts that were already correct only risks new defects.
