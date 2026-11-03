---
template_id: request.qa_propose_plan_task_example_python
version: "1"
required_variables: []
optional_variables: []
---
- task_type: qa.test
    role: qa
    focus: "Backend user-CRUD pytest suite"
    description: |
      Distinguish the faults the brief's user requirements could be built
      with: a duplicate email accepted, a deleted user still readable.
      One test per fault, each failing on that wrong implementation.
    expected_artifacts:
      - "backend/tests/test_users.py"
    acceptance_criteria:
      - check: function_defined
        file: backend/tests/test_users.py
        name_prefix: "test_"
        min_count: 1
        severity: error
    depends_on_focus:
      - "dev:user crud routes"