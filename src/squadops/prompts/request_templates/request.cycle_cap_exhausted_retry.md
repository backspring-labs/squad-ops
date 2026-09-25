---
template_id: request.cycle_cap_exhausted_retry
version: "1"
required_variables:
  - completion_cap
  - completion_tokens
optional_variables: []
---
### Your previous response was empty

It used {{completion_tokens}} tokens, the whole {{completion_cap}}-token output budget, on
reasoning and wrote nothing, so none of it could be used. The budget is the same this time.
Put the output first — the files, or the answer the task asks for — and keep any reasoning
short.
