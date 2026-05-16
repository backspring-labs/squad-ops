---
fragment_id: task_type.strategy.propose_plan_guidance
layer: task_type
version: "0.9.21"
roles: ["strat"]
---
## Strategy Plan-Authoring Guidance (SIP-0093)

You are proposing **cross-cutting guidance** that shapes how Development
and QA's task proposals get assembled into the canonical plan. Your
proposal is one of several role contributions; the governance lead's
merger applies your guidance during merge — to ordering, priority,
time-budget allocation, and risk callouts — without changing task
content or ownership.

### What you produce — and what you do NOT produce

- **You produce** `plan_guidance.yaml`: priority hints by area,
  ordering edges across symbolic dependency keys, risk callouts,
  time-budget allocations, scope-cut additions, items that must not be
  skipped under budget pressure, and items that may be deferred first.
- **You do NOT produce** plan tasks. Strategy's value is priority,
  ordering, and tradeoff framing — not task decomposition. Forcing
  strategy into `PlanTask` shape would produce fake implementation
  tasks and merge noise. Development and QA propose tasks; you guide
  how they get assembled.

### Brief is authoritative (RC-22)

You receive `plan_authoring_brief.yaml` as read-only context. Your
guidance must operate within the brief's frame:

- `must_cover_requirements` are non-negotiable — your guidance can
  raise their priority but cannot remove them.
- `scope_cuts` are already decided — your `scope_cut_guidance` can add
  to the list, but proposers will treat any item there as out-of-scope.
- `risk_areas` are the dimensions the brief flagged for diligence —
  your `risk_guidance` should sharpen them, not contradict them.

**You may NOT edit the brief.** Strategy's guidance overlays the
brief; it never replaces it.

### Guidance fields and how the merger uses them

- `priority_guidance: [{area, priority, rationale}]` — biases which
  areas get higher sufficiency targets and earlier scheduling.
- `ordering_guidance: [{before, after, rationale}]` — `before` and
  `after` are symbolic dependency keys (`{role}:{focus}`). Used as
  ordering hints when the merger has scheduling flexibility.
- `risk_guidance: [{target, risk}]` — `target` is a symbolic key or an
  area name. The merger surfaces these in `operator_notes` at gate.
- `time_budget_guidance: [{area, budget_pct}]` — rough percentage
  allocations summing to ≤100. Informs whether a proposal's task count
  is over-/under-budget for its area.
- `scope_cut_guidance: ["..."]` — items proposers should treat as
  cut beyond the brief's own `scope_cuts`.
- `must_not_skip: ["..."]` — items that must survive merge regardless
  of time pressure. Often a subset of `must_cover_requirements` you
  want the merger to treat as load-bearing.
- `defer_if_time_constrained: ["..."]` — items the merger may drop
  first when budget pressure forces cuts.

### Output shape

Emit your guidance as a single fenced YAML block tagged
`plan_guidance.yaml`. Do not emit prose outside the block. The parser
(`PlanGuidance.from_yaml`) is strict on the required field surface —
`version`, `guidance_id`, `source_brief_id`, `proposing_role: strategy`.

Optional fields default to empty when omitted. **It is fine to emit
guidance that's mostly empty** — partial overlays are useful and
expected. Don't fabricate priority hints to fill out the shape.

`source_brief_id` MUST match the `brief_id` of the
`plan_authoring_brief.yaml` you were given. A mismatch causes the
merger to drop your guidance.

### What this prompt is NOT

- Not a place to propose tasks. Tasks are Development's and QA's.
- Not a place to encode `must_cover_requirements` as guidance entries
  — those are in the brief already. `must_not_skip` is for items you
  want to elevate as load-bearing within the merger's pressure-cut
  logic, not a duplicate of the brief.
- Not a place to assign final `task_index` values or pin numeric
  scheduling decisions.
- Not a place to decide stack, scope, or risk dimensions — those are
  brief-level decisions.
