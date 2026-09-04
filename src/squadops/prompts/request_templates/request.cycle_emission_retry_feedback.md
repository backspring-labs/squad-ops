---
template_id: request.cycle_emission_retry_feedback
version: "1"
required_variables:
  - reason_line
  - expected_files
---
### Prior Attempt Failed — Output Format (authoritative — apply exactly)

Your previous response to this exact task was DISCARDED before any of its content
was used: {{reason_line}}

The extraction step maps each fenced code block to a file path taken from the
fence header. A fence without a path cannot be stored. Re-emit your work now,
following these rules exactly:

- Emit ONE fenced code block per required file, and nothing outside the fences
  except brief notes.
- Every fence header MUST carry the file's own path, exactly as the expected list above
  writes it: ` ```language:<the expected path> `. Not a placeholder, not a prefixed variant.
  — for example ` ```python:backend/tests/test_runs.py `.
- Close every fence with ` ``` ` on its own line.
- Required files:
{{expected_files}}
