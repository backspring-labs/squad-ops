---
template_id: request.cycle_repair_anchored_edit_appendix
version: "2"
required_variables:
  - editable_files
optional_variables: []
---
### Editing a File That Already Exists (preferred for a repair)

These files already exist in the workspace, and you may change them. Where the framework can
read a file's structure, its addressable entities are listed:

{{editable_files}}

Do not re-emit a whole file to change part of it. Emit **one edit fence per file**, holding one
or more blocks. There are two kinds of block.

**A structural block** names a listed entity. Use it to replace a whole function, component,
body, class or import, to insert something before or after one, or to remove one:

```edit:backend/routes.py
<<<<<<< REPLACE function:post_runs#body
    run = run_event_store.create(payload)
    return run
>>>>>>> END
<<<<<<< INSERT AFTER import:fastapi
from datetime import datetime
>>>>>>> END
<<<<<<< REMOVE import:os
>>>>>>> END
```

- The opener is `<<<<<<< REPLACE`, `<<<<<<< INSERT BEFORE`, `<<<<<<< INSERT AFTER` or
  `<<<<<<< REMOVE`, followed by exactly one entity name **as listed above**. Every block closes
  with `>>>>>>> END`.
- `#body` entities are the lines inside a function or component. Replacing a body keeps its
  signature, decorators and export exactly as they are. Write the body's lines with their full
  indentation.
- A `REMOVE` block carries no lines; an `INSERT` block must carry some.

**An anchored block** replaces an exact piece of text. Use it for a change smaller than any
listed entity:

```edit:backend/routes.py
<<<<<<< SEARCH
    return Run(**payload.dict())
=======
    return Run(**payload.dict(exclude_none=True))
>>>>>>> REPLACE
```

- Copy the SEARCH text **exactly** from the file as it is now: every character, space and
  indentation. It must occur **exactly once** in that file; include surrounding lines if needed.
- An empty REPLACE deletes the SEARCH text.

Rules for both — a response that breaks one is not applied, and nothing from it is used:

- The header is ` ```edit:<path> `, with the file's own path as listed above.
- Blocks in one file must not touch the same lines. Each is matched against the file as it is
  now, not after an earlier block.
- The result must still parse. Every byte you do not change stays exactly as it is.
- Do not both edit a file and re-emit it whole in the same response. A file you create, or
  genuinely rewrite from top to bottom, still uses ` ```language:<path> `.
