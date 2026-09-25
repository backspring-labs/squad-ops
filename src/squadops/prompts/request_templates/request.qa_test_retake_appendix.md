---
template_id: request.qa_test_retake_appendix
version: "1"
required_variables:
  - current_files_section
  - anchored_edit_section
optional_variables: []
---
## A Re-take: Revise the Suite You Wrote

The repair round for this task produced nothing, so the task is being taken again. Your suite
from the previous attempt is shown below exactly as it is. Do not re-author it: change what the
failure requires with edit fences, as the next section describes, and leave the rest as it is.
Emit a whole file only for a suite file that does not exist yet.

{{current_files_section}}

{{anchored_edit_section}}
