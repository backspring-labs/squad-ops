---
template_id: request.qa_propose_plan_tasks
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
---
You are proposing QA-domain plan tasks for the upcoming build.

## Authoritative brief (read-only — RC-22)

The brief below was authored upstream and is immutable. Your proposal must operate within its frame. Your role is the gap-catching pen: if `must_cover_requirements` lists items Development's proposal won't verify, propose qa tasks that do. Disagreements with the brief surface via `brief_conflicts` (see output shape), never by silent divergence.

```yaml:plan_authoring_brief.yaml
{{brief_content}}
```

{{roles_section}}{{builder_section}}## PRD

{{prd}}

## Planning artifacts (upstream framing)

{{planning_content}}

{{typed_acceptance_vocabulary}}
## Your task

Decompose the QA work for this build into focused tasks (`task_type: qa.test`) that verify the brief's `must_cover_requirements`. Where a requirement isn't already covered by acceptance criteria on a development task, propose a qa task that covers it explicitly. Restrict your proposal to qa-domain tasks. Reference development tasks via `depends_on_focus: ["dev:..."]` strings.

Pre-filled identifiers below — copy verbatim:

```yaml:proposed_plan_tasks.yaml
version: 1
proposal_id: {{proposal_id}}
source_brief_id: {{source_brief_id}}
proposing_role: qa
scope_statement: |
  One-paragraph self-assessment of what this proposal covers.
tasks:
  - task_type: qa.test
    role: qa
    focus: "Backend user-CRUD pytest suite"
    description: |
      Cover the user CRUD endpoints with pytest functions exercising
      create / read / update / delete and duplicate-handling.
    expected_artifacts:
      - "backend/tests/test_users.py"
    acceptance_criteria:
      - check: regex_match
        file: backend/tests/test_users.py
        pattern: "def test_"
        count_min: 5
        severity: error
    depends_on_focus:
      - "dev:user crud routes"
brief_conflicts: []  # Raise structured disagreements here if needed (see SIP-0093 §5.5).
# Optional Rev 1 fields — include only if you have substantive content.
source_artifact_refs: []
assumptions: []
risks: []
gaps_not_covered: []
confidence: ""  # low | medium | high
```
