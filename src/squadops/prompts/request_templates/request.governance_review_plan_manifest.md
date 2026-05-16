---
template_id: request.governance_review_plan_manifest
version: "1"
required_variables:
  - prd
  - planning_content
  - typed_acceptance_section
  - prd_coverage_discipline
  - project_id
  - cycle_id
  - prd_hash
  - total_tasks_expr
optional_variables:
  - roles_section
  - task_types_section
  - builder_guideline
  - qa_handoff_guideline
  - builder_example
  - summary_builder_line
---
Based on the following PRD and planning artifact, produce a build task manifest that decomposes the upcoming build into focused subtasks.

{{roles_section}}{{task_types_section}}## PRD
{{prd}}

## Planning Artifact
{{planning_content}}

Each subtask should:
1. Have a clear, narrow focus (e.g., 'Backend data models' not 'Build the app')
2. List the specific files it should produce
3. Declare dependencies on prior subtasks by task_index
4. Define acceptance criteria — prefer typed checks; see the section below
5. Be completable in a single focused LLM generation (~2-10 minutes)

Decomposition guidelines:
- Separate backend and frontend into distinct tasks
- Separate models/data from API endpoints/routes
- Separate UI shell/routing from individual view components
- Put integration config (CORS, proxy, requirements) in its own task
- Put tests after the code they test
{{builder_guideline}}{{qa_handoff_guideline}}{{typed_acceptance_section}}
{{prd_coverage_discipline}}
Output ONLY the manifest as a YAML code block with filename tag. The first three fields below are pre-filled with the cycle's authoritative values — copy them verbatim, do not invent or modify them:
```yaml:implementation_plan.yaml
version: 1
project_id: {{project_id}}
cycle_id: {{cycle_id}}
prd_hash: {{prd_hash}}
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "..."
    description: |
      ...
    expected_artifacts:
      - "path/to/file"
    acceptance_criteria:
      - "..."
    depends_on: []
{{builder_example}}summary:
  total_dev_tasks: N
  total_qa_tasks: M
{{summary_builder_line}}  total_tasks: {{total_tasks_expr}}
  estimated_layers: [backend, frontend, test, config]
```
