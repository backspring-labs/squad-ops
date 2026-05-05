---
fragment_id: task_type.governance.correction_decision
layer: task_type
version: "1.0.0"
roles: ["lead"]
---
## Correction Decision (SIP-0079 §7.7)

You are deciding how to respond to a failure during implementation. Given
the failure analysis, select ONE correction path:

- `continue`: the failure is non-critical; proceed with the remaining tasks
- `patch`: inject repair tasks to fix the specific issue, then continue
- `rewind`: restore the last checkpoint and retry from that point
- `abort`: the failure is unrecoverable; stop the run

### Output Format

Return JSON with these fields:

- `correction_path` (string): one of `continue` / `patch` / `rewind` / `abort`
- `decision_rationale` (string): 2-3 sentence justification
- `affected_task_types` (list[string]): task types affected by the decision

Return ONLY valid JSON, no markdown fences.
