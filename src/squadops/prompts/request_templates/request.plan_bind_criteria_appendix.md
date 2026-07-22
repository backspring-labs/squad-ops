---
template_id: request.plan_bind_criteria_appendix
version: "2"
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

A file the index marks **"contract-owned (no per-file typed criteria)"** has nothing to
bind: leave that task's `criteria_refs` **empty** (`criteria_refs: []`, or omit the field
entirely) — never copy the description into it, invent an id, or write any placeholder
string. Any `criteria_refs` entry that is not a real contract criterion id from the index
above is rejected at plan validation.

Example task shapes (YAML):

```yaml
# Contract-covered file → bind its listed criterion ids, exactly (use the real ids, not a placeholder):
- task_type: development.develop
  role: dev
  focus: "Implement the API routes"
  description: "Fill the route bodies in backend/routes.py."
  expected_artifacts: ["backend/routes.py"]
  criteria_refs: ["vc-routes-endpoints", "vc-routes-apierror"]
  acceptance_criteria:
    - "Endpoints behave per the PRD's happy-path and error cases."   # prose is fine

# Contract-owned file (index says "no per-file typed criteria") → criteria_refs EMPTY:
- task_type: development.develop
  role: dev
  focus: "Build the runs list view"
  description: "Render the runs list in frontend/src/views/RunsListView.jsx."
  expected_artifacts: ["frontend/src/views/RunsListView.jsx"]
  criteria_refs: []            # nothing to bind — NEVER a placeholder string
  acceptance_criteria:
    - "List renders each run with its title and date."   # prose is fine
```

Bind completely: a covered file that reaches the plan without all of its contract
criterion ids in some task's `criteria_refs` is a silent descoping of verification
and is rejected. When in doubt, bind more, author less.
