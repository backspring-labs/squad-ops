---
template_id: request.qa_test_frozen_surface_appendix
version: "1"
required_variables:
  - frozen_lines
---
**THE APPLICATION TREE AND WHAT IT DECLARES (authoritative — import only from this):**
{{frozen_lines}}

Read the list literally, the same way the developer does. The names after each path
are the **only** names those files export, and where a line says `import as`, that is
the **only** module path a test may import the file by — never a relative form guessed
from the suite's own location.

The `package.json` line is the **closed set of installed packages**. A package not
named there is not installed: importing it fails collection before a single test runs,
no matter how standard the package is for the job. Test what exists with what exists —
the runner and assertion library named in the list, plus the language's own facilities.

A line's `its own imports` names what that file imports for itself. It is a
description of the file's interior, not guidance for yours.
