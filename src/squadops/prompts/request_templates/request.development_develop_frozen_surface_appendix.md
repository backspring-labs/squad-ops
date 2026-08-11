---
template_id: request.development_develop_frozen_surface_appendix
version: "1"
required_variables:
  - frozen_lines
optional_variables: []
---
**FROZEN FILES AND WHAT THEY DECLARE (authoritative — import from these, never rewrite them):**
{{frozen_lines}}

These files are already in your workspace and the scaffold restores them if you edit
them, so a change you make here is discarded before anything checks it.

Read the list literally. The names after each path are the **only** names those files
export. If a module lists `reset, all, insert, find`, then `runStore` does not exist and
importing it fails the build — no matter how reasonable the name looks. The same holds for
model fields and error codes: what is listed is what is there.

Import them exactly as the listing shows other scaffold files importing them. Where a path
alias appears (`@/lib/store`), use that form — a relative path guessed from your own file's
location is the single most common way this build fails.

If you need something these files do not declare, build it inside your own slot. Do not
add it to a frozen file.
