---
template_id: request.cycle_repair_loop_state
version: "1"
required_variables:
  - attempt
  - max_attempts
optional_variables:
  - persistence_note
---

### Where you are in the correction loop

This is repair attempt **{{attempt}} of {{max_attempts}}**. The loop is finite: when the
budget is exhausted the run fails, whatever state the work is in.
{{persistence_note}}
