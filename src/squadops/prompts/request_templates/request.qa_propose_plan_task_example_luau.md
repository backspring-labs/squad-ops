---
template_id: request.qa_propose_plan_task_example_luau
version: "1"
required_variables: []
optional_variables: []
---
- task_type: qa.test
    role: qa
    focus: "scoreboard Luau spec suite"
    description: |
      Distinguish the faults the brief's scoring requirements could be built
      with: a total awarded past its cap, a leader read from the wrong player.
      One test per fault, each failing on that wrong implementation, run by
      the product's own runner script.
    expected_artifacts:
      - "tests/Scoreboard.spec.luau"
    acceptance_criteria: []
    depends_on_focus:
      - "dev:scoreboard scoring module"
