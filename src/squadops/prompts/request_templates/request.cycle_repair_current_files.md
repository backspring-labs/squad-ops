---
template_id: request.cycle_repair_current_files
version: "1"
required_variables:
  - current_files
optional_variables: []
---
### The Files as They Are Now

Each file you may revise, exactly as it is in the workspace now. This is the text your edits
are matched against: an anchored block's SEARCH text is copied from here, character for
character, and a structural block names one of the entities the next section lists for the
file. Nothing below is a fence to emit — a file shown here is changed with an edit fence,
never re-emitted.

{{current_files}}
