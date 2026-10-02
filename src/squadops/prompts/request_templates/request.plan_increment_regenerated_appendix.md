---
template_id: request.plan_increment_regenerated_appendix
version: "1"
required_variables:
  - regenerated_index
optional_variables: []
---

## Files this change touches that the scaffold writes

The approved change alters the interface manifest, and the scaffold regenerates these files from
it. No task claims them in its `expected_artifacts` (the plan gate refuses one that does); the
tasks for the files above fill the slots that use what they declare.

{{regenerated_index}}
