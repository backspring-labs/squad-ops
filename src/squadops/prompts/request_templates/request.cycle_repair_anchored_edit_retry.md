---
template_id: request.cycle_repair_anchored_edit_retry
version: "3"
required_variables:
  - refusal_lines
optional_variables: []
---
### Your Previous Edits Were Not Applied (authoritative — fix exactly this)

Your previous response to this repair was DISCARDED: none of its edits were applied, and no
file from it was used. The framework refused it for these reasons:

{{refusal_lines}}

- `anchor_not_found`: the SEARCH text does not occur in the file as it is now. Copy it again,
  character for character, from the file as shown under *The Files as They Are Now* — do not
  retype it from memory.
- `anchor_ambiguous`: the SEARCH text occurs more than once. Add surrounding lines until it
  occurs exactly once.
- `unresolved_entity`: no entity of that name exists in the file. Use a name exactly as the
  entity list above spells it.
- `ambiguous_entity`: the name matches more than one entity (a redefinition). Use an anchored
  block for the one you mean.
- `unreadable_structure`: that file has no structural reading. Use an anchored block.
- `invalid_syntax`: the edited file would not parse. Check the indentation and every bracket in
  your lines.
- `overlapping_ranges`: two blocks in one file cover the same lines. Merge them into one block.
- A malformed block names the marker that is missing or misplaced.

Emit the repair again now, following the edit rules above.
