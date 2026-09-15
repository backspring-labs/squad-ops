---
template_id: request.cycle_repair_output_whole_file
version: "1"
required_variables:
  - expected_artifacts
optional_variables: []
---
### Required Output Artifacts

The repair MUST produce the following file(s) by name, using fenced code blocks whose header carries the file's own path — for the file(s)
named above, exactly as they are written there (` ```language:<that path> `) — so the
framework can extract them:

{{expected_artifacts}}

**This is a repair, not a rewrite.** Change the minimum necessary to fix the named failure.
The file list above is the set you may emit — it is not a list of things that need changing.
A file you are not fixing must be re-emitted byte-identical to what is already in the
workspace. Keep the file's structure as it is: the router construction, every route
decorator with its literal path, every function name and its signature. A repair that
re-emits the file as a rewrite — a prefixed router, renamed handlers, dropped decorators —
is refused by the acceptance checks before it is ever tested, even when the fix inside it
is correct, and the round is lost.
