---
template_id: request.skills_declared_stops
version: "1"
required_variables:
  - stop_list
optional_variables: []
---
### When a skill above tells you to stop

The skills above declare these stops. Each line is how a stop's one-line answer opens:

{{stop_list}}

The skill that declares a stop says when it applies. When that condition holds for this task,
your whole answer is the stop line as the skill writes it, with its reason filled in, and nothing
else.

A stop comes before this task's own requirements. The requirement elsewhere in this prompt to
emit a file or a fenced block does not apply to a task that stops: emit none. A stop is a valid
result of this task, and it is read as one. Do not weigh a stop against the task's requirements,
and do not write the artifact anyway.

When no stop's condition holds, emit what this task asks for, exactly as it says.
