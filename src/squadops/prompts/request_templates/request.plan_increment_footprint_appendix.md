---
template_id: request.plan_increment_footprint_appendix
version: "1"
required_variables:
  - footprint_index
optional_variables: []
---

## This is an increment: plan only the approved change

The application already exists and is accepted. A supervisor approved one change to it, and
the files that change touches are listed below. Plan tasks **only** for these files: every
other file keeps its accepted implementation, which the build starts from.

A task whose `expected_artifacts` include a file outside this list is refused at the plan
gate, and the framing is re-run. A test task may write anywhere in the stack's test
namespace, which the list includes as a pattern.

**The files this increment may touch:**

{{footprint_index}}
