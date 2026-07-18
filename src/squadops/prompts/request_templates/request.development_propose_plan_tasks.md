---
template_id: request.development_propose_plan_tasks
version: "1"
required_variables:
  - brief_content
  - planning_content
  - proposal_id
  - source_brief_id
optional_variables:
  - prd
  - roles_section
  - builder_section
  - typed_acceptance_vocabulary
  - scaffold_section
  - bind_criteria_section
---
You are proposing development-domain plan tasks for the upcoming build.

## Authoritative brief (read-only — RC-22)

The brief below was authored upstream and is immutable. Your proposal must operate within its frame. Disagreements surface via `brief_conflicts` (see output shape), never by editing requirements out of your proposal.

```yaml:plan_authoring_brief.yaml
{{brief_content}}
```

{{roles_section}}{{builder_section}}## PRD

{{prd}}

## Planning artifacts (upstream framing)

{{planning_content}}

{{typed_acceptance_vocabulary}}
## Your task

Decompose the development work for this build into focused tasks (`task_type: development.develop`) that, together with QA's test proposal and Strategy's guidance, will assemble into a complete implementation plan. Restrict your proposal to dev-domain tasks. Use the typed-acceptance vocabulary above where applicable.

Pre-filled identifiers below — copy verbatim:

```yaml:proposed_plan_tasks.yaml
version: 1
proposal_id: {{proposal_id}}
source_brief_id: {{source_brief_id}}
proposing_role: development
scope_statement: |
  One-paragraph self-assessment of what this proposal covers.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Backend user model"
    description: |
      Detailed description of what this task produces and why.
    expected_artifacts:
      - "backend/models.py"
    acceptance_criteria:
      - check: field_present
        file: backend/models.py
        class_name: User
        fields: [id, email]
        severity: error
    depends_on_focus: []
brief_conflicts: []  # Raise structured disagreements here if needed (see SIP-0093 §5.5).
# Optional Rev 1 fields — include only if you have substantive content.
source_artifact_refs: []
assumptions: []
risks: []
gaps_not_covered: []
confidence: ""  # low | medium | high
```

{{scaffold_section}}
{{bind_criteria_section}}
