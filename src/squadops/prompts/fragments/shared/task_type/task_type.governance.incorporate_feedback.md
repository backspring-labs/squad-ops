---
fragment_id: task_type.governance.incorporate_feedback
layer: task_type
version: "0.9.16"
roles: ["lead"]
---
## Governance Feedback Incorporation (Refinement Workload)

You are incorporating feedback into an existing planning artifact. The original
planning artifact and refinement instructions are provided as context.

### Deliverables

1. **Revised planning artifact** — update the original planning artifact to
   address the refinement instructions. Preserve unchanged sections; only
   modify what the feedback requires.
2. **Refinement log** — document what changed and why

### Rules

- Apply targeted changes only; do not rewrite sections that were not flagged
- Preserve the YAML frontmatter structure (readiness, sufficiency_score,
  blocker_unknowns) and update values if the changes affect them
- If refinement resolves a blocker unknown, reclassify it appropriately
- Track all changes in the refinement log for audit

### Output Format

Produce `planning_artifact_revised.md` with updated YAML frontmatter and
body reflecting the incorporated feedback.
