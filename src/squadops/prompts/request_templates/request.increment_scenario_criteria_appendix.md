---
template_id: request.increment_scenario_criteria_appendix
version: "1"
required_variables:
  - scenario_lines
---

## The criteria this increment's scenarios check

Each criterion below is checked by playing its scenario in the running game. When the increment is
judged, the framework plays the scenario and reads what the game shows. The criterion holds only
when the scenario's expectations are met there. No test checks it, and no test in any file asserts
it: a unit test runs without the game, so it can't observe what the scenario does. Leave each one
to its scenario.

{{scenario_lines}}
