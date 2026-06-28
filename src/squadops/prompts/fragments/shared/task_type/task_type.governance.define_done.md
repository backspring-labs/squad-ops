---
fragment_id: task_type.governance.define_done
layer: task_type
version: "1.0.0"
roles: ["lead"]
---
## Define the Definition of Done (SIP-0079)

Given the planning artifacts and PRD, produce a JSON definition of done with
these fields:

- `objective` (string): one-sentence goal
- `acceptance_criteria` (list[string]): measurable success criteria
- `non_goals` (list[string]): explicitly out of scope
- `time_budget_seconds` (int): maximum wall-clock seconds
- `stop_conditions` (list[string]): conditions that should halt execution
- `required_artifacts` (list[string]): artifact filenames that must be produced

Return ONLY valid JSON, no markdown fences, no explanation.
