---
template_id: request.cycle_cap_truncated_retry
version: "2"
required_variables:
  - completion_cap
  - completion_tokens
  - cut_block
  - keep_reasoning_short
optional_variables: []
---
### Your previous response was cut off

It used {{completion_tokens}} tokens, the whole {{completion_cap}}-token output budget, and the
budget ran out while it was writing this block:

{{cut_block}}

That block ended mid-way, so it was not kept. The budget is the same this time. Write the answer
again with every block closed, and {{keep_reasoning_short}}
