---
template_id: request.cycle_repair_app_traceback_appendix
version: "1"
required_variables:
  - traceback_blocks
optional_variables: []
---
**THE APPLICATION'S OWN ERROR (from the failing run):**

{{traceback_blocks}}

This is what the application actually raised, not a description of it. Read the innermost
frame and the exception before deciding what to change: it names the file, the line and the
rule that was violated. Where it disagrees with the analyzer's summary above, the traceback
is the fact and the summary is an interpretation of it.
