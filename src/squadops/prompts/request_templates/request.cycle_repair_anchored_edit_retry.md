---
template_id: request.cycle_repair_anchored_edit_retry
version: "1"
required_variables:
  - refusal_lines
optional_variables: []
---
### Your Previous Edits Were Not Applied (authoritative — fix exactly this)

Your previous response to this repair was DISCARDED: none of its edits were applied, and no
file from it was used. The framework refused it for these reasons:

{{refusal_lines}}

- `anchor_not_found`: the SEARCH text does not occur in the file as it is now. Copy it again,
  character for character, from the current file — do not retype it from memory.
- `anchor_ambiguous`: the SEARCH text occurs more than once. Add surrounding lines until it
  occurs exactly once.
- `overlapping_ranges`: two SEARCH texts in one file cover the same lines. Merge them into one block.
- A malformed block names the marker that is missing or misplaced.

Emit the repair again now, following the edit rules above.
