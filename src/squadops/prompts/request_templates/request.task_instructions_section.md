---
template_id: request.task_instructions_section
version: "1"
required_variables:
  - instruction_lines
optional_variables: []
---

## INSTRUCTIONS FOR THIS TASK

The person running this cycle gave the instructions below for this task. Follow them.

They come after this task's own requirements, the interface manifest with its decisions and contracts,
and the application as it stands. Where an instruction disagrees with those, follow them, and say in
your output which instruction you could not follow and why. They come before any lesson.

{{instruction_lines}}
