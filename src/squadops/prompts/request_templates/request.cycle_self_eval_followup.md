---
template_id: request.cycle_self_eval_followup
version: "1"
required_variables:
  - validation_summary
  - failing_checks
  - produced_files
  - closing_instruction
optional_variables:
  - missing_components
  - current_files_section
  - anchored_edit_section
  - disputed_checks_section
---
## Your Previous Response Did Not Pass Validation

**Validation summary:** {{validation_summary}}

Every check that failed, with what it reported:

{{failing_checks}}

{{missing_components}}

**Files you already produced:** {{produced_files}}

{{current_files_section}}

{{anchored_edit_section}}

{{disputed_checks_section}}

{{closing_instruction}}
