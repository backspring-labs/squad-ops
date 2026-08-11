---
template_id: request.development_develop_frozen_surface_appendix
version: "2"
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
model fields and error codes: what is listed is what is there. A `package.json` line names
the **closed set of installed packages** — a package not listed is not installed.

Where a line says `import as`, that is the module path to import the file by. Otherwise
import it exactly as the listing shows other scaffold files importing it (`its own
imports` describes each file's interior). Where a path alias appears (`@/lib/store`), use
that form — a relative path guessed from your own file's location is the single most
common way this build fails.

If you need something these files do not declare, build it inside your own slot. Do not
add it to a frozen file.
