---
template_id: request.strategy_propose_plan_guidance
version: "1"
required_variables:
  - brief_content
  - planning_content
  - guidance_id
  - source_brief_id
optional_variables:
  - prd
  - roles_section
---
You are proposing cross-cutting plan-authoring guidance for the upcoming build.

## Authoritative brief (read-only — RC-22)

The brief below was authored upstream and is immutable. Your guidance overlays the brief; it does not replace any of its fields. Disagreements surface only through the brief's own escalation paths — your role contributes priority/ordering/risk overlay, not brief edits.

```yaml:plan_authoring_brief.yaml
{{brief_content}}
```

{{roles_section}}## PRD

{{prd}}

## Planning artifacts (upstream framing)

{{planning_content}}

## Your task

Produce `plan_guidance.yaml` capturing the cross-cutting priorities and tradeoffs Development and QA's proposers should be biased toward. Strategy's value is priority, ordering, and risk framing — NOT task decomposition. Do NOT propose plan tasks.

Partial guidance is fine. If you don't have substantive content for a field, omit it or leave the list empty; the merger handles empty overlays cleanly. Fabricating priority hints to fill the shape adds merge noise.

Pre-filled identifiers below — copy verbatim:

```yaml:plan_guidance.yaml
version: 1
guidance_id: {{guidance_id}}
source_brief_id: {{source_brief_id}}
proposing_role: strategy
priority_guidance:
  - area: backend_api
    priority: high
    rationale: |
      Brief calls API surface the integration anchor; prioritize it.
ordering_guidance:
  - before: "dev:repository layer"
    after: "dev:user crud routes"
    rationale: |
      Routes pin the contract before persistence shape lands.
risk_guidance:
  - target: "dev:user crud routes"
    risk: |
      Brief flagged auth as a risk area — make sure routes propose typed auth checks.
time_budget_guidance:
  - area: backend_api
    budget_pct: 30
scope_cut_guidance: []        # Items proposers should treat as out-of-scope beyond brief's own cuts.
must_not_skip: []             # Items the merger must preserve under budget pressure.
defer_if_time_constrained: [] # Items the merger may drop first under pressure.
confidence: ""                # low | medium | high
```
