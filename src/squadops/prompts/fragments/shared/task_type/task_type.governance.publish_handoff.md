---
fragment_id: task_type.governance.publish_handoff
layer: task_type
version: "0.9.18"
roles: ["lead"]
---
## Governance Publish Handoff (Wrap-Up Workload)

You are producing the handoff artifact for a wrap-up workload. This is the
forward-looking instruction record — it packages carry-forward items and
recommends the next cycle type.

### Next Cycle Type

Recommend exactly one:

- `planning` — needs a new planning cycle (significant replanning required)
- `implementation` — needs another implementation cycle (incremental work)
- `hardening` — needs a hardening cycle (testing, stability, performance)
- `research` — needs a research cycle (unknowns require investigation)
- `none` — no further cycles needed (work is complete)

### What Not to Retry

Include a section documenting approaches that were tried and failed or were
abandoned. This prevents the next cycle from repeating known-bad strategies.
Be specific: name the approach, why it failed, and what to do instead.

### Output Format

Produce `handoff_artifact.md` with YAML frontmatter:

```yaml
---
next_cycle_type: <one of the 5 types above>
carry_forward_count: <number of items>
---
```

The body must contain:

1. **Carry-forward items** — unresolved issues that transfer to the next cycle,
   with suggested owner and priority
2. **Next cycle recommendation** — what the next cycle should focus on and why
3. **What should not be retried** — failed approaches with rationale
4. **Context for next cycle** — key decisions, constraints, and assumptions
   that the next cycle team needs to know
