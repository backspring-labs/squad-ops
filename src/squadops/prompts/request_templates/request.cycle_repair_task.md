---
template_id: request.cycle_repair_task
version: "3"
required_variables:
  - prd
  - role
  - failed_task_type
  - failure_summary
  - correction_decision
optional_variables:
  - subtask_focus
  - subtask_description
  - expected_artifacts
  - acceptance_criteria
  - prior_outputs
  - fill_only_section
  - contract_expectations
  - dom_anchor_section
  - frozen_surface_section
---
## Repair Task

You are repairing a failed `{{failed_task_type}}` task. Your job is to re-produce the named output artifact(s) below so they satisfy the acceptance criteria. Do not rewrite the PRD, do not produce a status tracker, do not emit a generic narrative document.
{{fill_only_section}}
{{contract_expectations}}
{{dom_anchor_section}}
{{frozen_surface_section}}

### Failed Task Contract

Focus: {{subtask_focus}}

{{subtask_description}}

### Required Output Artifacts

The repair MUST produce the following file(s) by name, using fenced code blocks in the format ` ```language:path/to/file ` so the framework can extract them:

{{expected_artifacts}}

### Acceptance Criteria (narrative)

The narrative criteria below describe intent. They are context, not letter-of-the-law: where a Contract Expectations line above covers the same ground, the Contract Expectations line is authoritative and the narrative may be imprecise.

{{acceptance_criteria}}

### Why the Prior Attempt Failed

{{failure_summary}}

### Correction Decision

The lead reviewed the failure and chose to patch (not rewind). Their rationale:

{{correction_decision}}

### Product Requirements Document

{{prd}}

{{prior_outputs}}

---

Produce the named artifacts now. Use fenced code blocks (` ```language:path/to/file `) for every file you emit. Do not include explanatory prose between code blocks unless it is essential.
