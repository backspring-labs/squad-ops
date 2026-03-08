---
fragment_id: task_type.governance.assess_readiness
layer: task_type
version: "0.9.16"
roles: ["lead"]
---
## Governance Readiness Assessment (Planning Workload)

You are performing the readiness assessment for a planning workload. Your goal
is to consolidate all upstream outputs into a coherent planning artifact and
assess whether the plan is ready for implementation.

### Deliverables

1. **Planning artifact** — a reconstituted document that synthesizes context
   research, objective frame, technical design, and test strategy into a
   coherent implementation plan
2. **Design sufficiency check** — evaluate against these 5 criteria:
   - Scope clarity (are boundaries well-defined?)
   - Technical feasibility (is the design implementable?)
   - Risk coverage (are unknowns classified and mitigated?)
   - Test strategy alignment (does QA coverage match risk areas?)
   - Resource fit (does the plan match available squad capabilities?)
3. **Readiness recommendation** — one of: `go`, `revise`, `no-go`

### Output Format

Your response MUST start with YAML frontmatter between `---` delimiters,
followed by the consolidated plan body. Do NOT start with a heading or
any other text before the frontmatter.

Example of correct output format:

```
---
readiness: go
sufficiency_score: 4
blocker_unknowns: 0
---

## Consolidated Plan

(plan body here...)
```

Frontmatter fields:
- `readiness`: exactly one of `go`, `revise`, or `no-go`
- `sufficiency_score`: integer from 1 to 5
- `blocker_unknowns`: integer count of blocker-classified unknowns

If any unknowns are classified as `blocker`, readiness MUST be `revise` or
`no-go`. A `go` recommendation with outstanding blockers is invalid.

The body should contain the consolidated plan with clear section headings
matching the upstream deliverables, plus your sufficiency assessment.
