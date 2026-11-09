---
template_id: request.proposal_goal_set
version: "2"
required_variables:
  - revision
  - goal
  - expected_result_lines
  - constraint_lines
  - out_of_scope_lines
  - backlog_lines
  - latest_readings_section
  - next_item_section
---
### The product's goal set, revision {{revision}}

The owner keeps what this product should come to do as a goal set. The campaign works through its
backlog in the owner's order, one item per increment.

**The goal:** {{goal}}

**What the owner will accept as the goal met**, each with where it can be observed:
{{expected_result_lines}}

**Constraints** every change keeps:
{{constraint_lines}}

**Out of scope**, never proposed:
{{out_of_scope_lines}}

**The backlog, in the owner's order**, with where this campaign stands on each item:
{{backlog_lines}}

{{latest_readings_section}}

{{next_item_section}}

There is no requirements document here: the goal set above is the product's requirements. Leave
`prd_delta` out; the backlog item is what your request delivers.
