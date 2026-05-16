---
fragment_id: task_type.governance.prepare_plan_authoring_brief
layer: task_type
version: "0.9.20"
roles: ["lead"]
---
## Plan Authoring Brief (SIP-0093)

You are authoring the shared scope-framing artifact that every plan-authoring
path will consume. Role proposers (development, qa, strategy) read the brief
read-only and produce their domain-scoped proposals from one consistent
worldview; the merger reads the brief to resolve cross-proposal conflicts and
fill gaps.

The brief is **immutable** once you emit it (RC-22). No downstream task — not
the proposers, not the merger, not the gate package — may revise it. If a
proposer disagrees with the brief, it surfaces a structured `brief_conflicts`
entry the merger handles; it does not edit your output.

### Deliverable

Produce a single YAML artifact named `plan_authoring_brief.yaml`. Do not
emit a Markdown narrative; the brief is a structured handoff, not a memo.

### Required fields (Rev 1)

Every brief must include these seven fields. A brief missing any of them will
fail to parse and force the cycle to fall back to sole-author mode.

- `version` — integer, currently `1`.
- `brief_id` — short string unique per cycle (e.g., `brief-<cycle_id>-001`).
  Used by proposers and the merger to assert they're all working from the
  same brief.
- `objective_summary` — one-paragraph statement of what the build must
  achieve. Restate the user-facing goal in your own words; downstream roles
  will rely on this for cross-cutting decisions.
- `accepted_stack` — YAML mapping of the technology choices the brief pins
  for this cycle. Anything outside this map is out of bounds for proposers.
  Be explicit: `{frontend: "React+Vite", backend: "FastAPI+SQLite", ...}`.
- `must_cover_requirements` — list of requirements every proposal must
  honor. These are the non-negotiables (e.g., "POST /runs/{id}/join must
  return 409 on duplicate"). Phrase each so it can be referenced by
  proposal `acceptance_criteria`.
- `scope_cuts` — list of features explicitly deferred. Use this to
  pre-empt the proposers debating scope inline. Example: "Admin
  dashboards: deferred to a follow-up cycle."
- `risk_areas` — list of areas where proposers should focus diligence
  (auth, data integrity, concurrency, etc.). Not bugs — places where
  the cost of a wrong call is high.

### Optional fields (Rev 1)

Include these when you have substantive content for them. Empty optional
fields don't help proposers and may invite filler.

- `source_artifact_refs` — names of upstream framing artifacts you drew
  from (e.g., `planning_artifact.md`, `design.md`).
- `major_components` — list of the build's structural components, named.
- `dependency_assumptions` — assumptions about external systems
  (database availability, external APIs, auth provider).
- `time_budget_guidance` — YAML mapping of percentage allocations to
  major areas (e.g., `{backend_api: 30, persistence: 20, frontend: 30,
  tests: 20}`).
- `task_granularity_guidance` — one-sentence guidance on how finely to
  decompose tasks ("aim for 2-5 minute LLM generations per task").
- `artifact_naming_conventions` — list of file-naming rules proposers
  should follow (e.g., "All Pydantic models in backend/models.py").
- `open_questions` — list of unresolved items. Each entry should be
  phrased as a question the merger can flag for the operator at gate
  if it remains unresolved.

### Output format

Emit the brief as YAML inside a fenced code block, filename-tagged so the
downstream parser can locate it unambiguously. Do not include any prose
outside the code block.

````
```yaml:plan_authoring_brief.yaml
version: 1
brief_id: brief-<cycle_id>-001
objective_summary: |
  ...
accepted_stack:
  frontend: "..."
  backend: "..."
must_cover_requirements:
  - "..."
scope_cuts:
  - "..."
risk_areas:
  - "..."
# Optional fields below — include only if you have substantive content.
source_artifact_refs: []
major_components: []
dependency_assumptions: []
time_budget_guidance: {}
task_granularity_guidance: ""
artifact_naming_conventions: []
open_questions: []
```
````

### What the brief is NOT

- **Not the plan itself.** You are framing scope and constraints, not
  decomposing the build into tasks. Decomposition is the role proposers'
  job; merging is the merger's.
- **Not an essay.** Each required-field value should be terse and
  actionable. A proposer who has to re-read the brief to remember the
  stack lost time.
- **Not a place to hedge.** If you genuinely don't know something,
  surface it as an `open_question`, not as conditional language inside
  `must_cover_requirements`.
- **Not editable after emission.** Treat your output as a contract with
  the proposers. If something is genuinely unresolved, name it in
  `open_questions` so the merger can surface it at gate — don't paper
  over the gap.
