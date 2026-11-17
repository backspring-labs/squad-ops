---
template_id: request.increment_scenario_criteria_appendix
version: "2"
required_variables:
  - scenario_lines
---

## The criteria this increment's scenarios check

Each criterion below is checked by playing its scenario in the running game. When the increment is
judged, the framework plays the scenario and reads what the game shows. The criterion holds only
when the scenario's expectations are met there. No test checks it, and no test in any file asserts
it: a unit test runs without the game, so it can't observe what the scenario does. Leave each one
to its scenario.

Each of these criteria also has a declaration file, which the framework writes itself from the
approved change request. The change request's `footprint`, and a brief written from it, may name
that file. Plan no task for it. That no task writes it is no gap in the plan and no conflict with
the brief, so raise none about it.

{{scenario_lines}}
