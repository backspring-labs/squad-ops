---
template_id: request.cycle_repair_anchored_edit_appendix
version: "1"
required_variables:
  - editable_files
optional_variables: []
---
### Editing a File That Already Exists (preferred for a repair)

These files already exist in the workspace, and you may change them:

{{editable_files}}

To change part of one of them, do not re-emit the whole file. Emit an **edit block** that names
the exact text to replace and its replacement:

```edit:backend/routes.py
<<<<<<< SEARCH
    return Run(**payload.dict())
=======
    return Run(**payload.dict(exclude_none=True))
>>>>>>> REPLACE
```

Rules — an edit that breaks one is not applied, and nothing from the response is used:

- The header is ` ```edit:<path> `, with the file's own path as listed above. One edit fence per file.
- Copy the SEARCH text **exactly** from the file as it is now: every character, space and
  indentation. It must occur **exactly once** in that file. If the lines you want to change
  also appear elsewhere, include enough surrounding lines to make the SEARCH text unique.
- A fence may hold several SEARCH/REPLACE blocks. Their SEARCH texts must not overlap, and
  each is matched against the file as it is now, not after an earlier block.
- An empty REPLACE deletes the SEARCH text.
- Every other byte of the file stays exactly as it is. You do not re-emit what you are not changing.
- Do not both edit a file and re-emit it whole in the same response. A file you create, or
  genuinely rewrite from top to bottom, still uses ` ```language:<path> `.
