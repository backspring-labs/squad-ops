---
template_id: request.increment_framework_files_section
version: "1"
required_variables:
  - framework_file_lines
---

### Files in the footprint that the framework writes itself

Each file below is the declaration of one of this change's scenario criteria. The framework
writes it, exactly as the approved change request froze it, and the play session reads it. It
is in `footprint` so that the build may hold it.

- Plan no task for it, and list it in no task's `expected_artifacts`. A task that names one is
  refused at the plan gate.
- It needs nothing from an operator. That no task covers it is no gap in the plan and no
  conflict with the brief.

{{framework_file_lines}}
