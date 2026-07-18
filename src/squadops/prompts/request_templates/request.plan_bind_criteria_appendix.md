---
template_id: request.plan_bind_criteria_appendix
version: "1"
required_variables:
  - criteria_index
optional_variables: []
---
## Bind the verification contract — do NOT author acceptance criteria

This build is governed by a **verification contract**: a pre-authored, frozen
statement of what a correct fill must satisfy. The contract already owns the
acceptance of the files below. Your job is to **bind** its criteria by id, not to
invent your own.

For every task whose `expected_artifacts` includes a contract-covered file, list
that file's criterion ids in the task's `criteria_refs` — **all of them, exactly**.
Do not author `acceptance_criteria` typed checks (`endpoint_defined`,
`import_present`, `field_present`, `command_exit_zero`) for a covered file: the
contract's are authoritative and yours would be rejected at plan validation. Prose
`acceptance_criteria` (human-readable intent) and checks on files the contract does
**not** cover remain welcome.

**Contract criteria index — bind these ids:**

{{criteria_index}}

Example task shape (YAML):

```yaml
- task_type: development.develop
  role: dev
  focus: "Implement the API routes"
  description: "Fill the route bodies in backend/routes.py."
  expected_artifacts: ["backend/routes.py"]
  criteria_refs: ["<the ids listed for backend/routes.py above>"]
  acceptance_criteria:
    - "Endpoints behave per the PRD's happy-path and error cases."   # prose is fine
```

Bind completely: a covered file that reaches the plan without all of its contract
criterion ids in some task's `criteria_refs` is a silent descoping of verification
and is rejected. When in doubt, bind more, author less.
