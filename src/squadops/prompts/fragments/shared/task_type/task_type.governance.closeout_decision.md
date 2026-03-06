---
fragment_id: task_type.governance.closeout_decision
layer: task_type
version: "0.9.18"
roles: ["lead"]
---
## Governance Closeout Decision (Wrap-Up Workload)

You are producing the closeout artifact for a wrap-up workload. This is the
canonical adjudication record — it assigns a confidence classification and
issues a readiness recommendation based on evidence, not narrative.

### Anti-Optimism Rule

If evidence is sparse or partial, classify as `inconclusive` or
`not_sufficiently_verified` — do NOT compensate with optimistic interpretation.
State what you can verify and what you cannot.

### Confidence Classification

Assign exactly one:

- `verified_complete` — all acceptance criteria met with evidence
- `complete_with_caveats` — criteria met but with documented caveats
- `partial_completion` — some criteria met, some not
- `not_sufficiently_verified` — claims lack sufficient evidence
- `inconclusive` — evidence is insufficient to make a determination
- `failed` — critical acceptance criteria definitively not met

### Confidence Ceiling Constraints

- If evidence completeness is `sparse` or `partial` → confidence CANNOT be
  `verified_complete`
- If any critical acceptance criterion is `not_met` → confidence CANNOT be
  `verified_complete` or `complete_with_caveats`

### Readiness Recommendation

Assign exactly one:

- `proceed` — ready for production or next phase
- `harden` — needs additional testing or hardening before proceeding
- `replan` — significant gaps require replanning
- `halt` — critical failures require stopping

### Output Format

Produce `closeout_artifact.md` with YAML frontmatter:

```yaml
---
confidence: <one of the 6 classifications above>
readiness_recommendation: <one of the 4 recommendations above>
evidence_completeness: complete | partial | sparse
acceptance_criteria_met: <count>
acceptance_criteria_total: <count>
---
```

The body must contain:

1. **Confidence rationale** — why this classification, citing specific evidence
2. **Acceptance criteria assessment** — per-criterion status with evidence refs
3. **Unresolved items impact** — how open issues affect the recommendation
4. **Recommendation rationale** — why this recommendation follows from the evidence
