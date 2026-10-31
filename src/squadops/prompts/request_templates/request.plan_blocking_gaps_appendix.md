---
template_id: request.plan_blocking_gaps_appendix
version: "1"
required_variables:
  - blocked_index
optional_variables: []
---

## Where this product's checks can't run: plan no task there

The product's own checks can't run under the paths below, for the reason each one names, so
nothing a task writes there can be verified. Plan no task whose `expected_artifacts` lie under
them. A task that does is refused at the plan gate, and the framing is re-run.

**The paths, and why:**

{{blocked_index}}
