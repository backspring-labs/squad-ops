---
template_id: request.qa_propose_plan_task_example_javascript
version: "1"
required_variables: []
optional_variables: []
---
- task_type: qa.test
    role: qa
    focus: "user-CRUD API test suite"
    description: |
      Distinguish the faults the brief's user requirements could be built
      with: a duplicate email accepted, a deleted user still readable.
      One test per fault, each failing on that wrong implementation.
    expected_artifacts:
      - "test/users.test.js"
    acceptance_criteria:
      - check: command_exit_zero
        argv: ["node", "--check", "test/users.test.js"]
        severity: error
    depends_on_focus:
      - "dev:user crud routes"