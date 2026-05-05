---
fragment_id: task_type.governance.correction_decision
layer: task_type
version: "1.1.0"
roles: ["lead"]
---
## Correction Decision (SIP-0079 §7.7)

You are deciding how to respond to a failure during implementation. Given
the failure analysis, select ONE correction path:

- `continue`: the failure is non-critical; proceed with the remaining tasks
- `patch`: inject repair tasks to fix the specific issue, then continue
- `rewind`: restore the last checkpoint and retry from that point
- `abort`: the failure is unrecoverable; stop the run

## Diagnostic question (non-operative)

Then, separately, answer a diagnostic question: if you could ALSO modify
the implementation plan itself (not yet available in this framework),
which structural plan change would you choose?

- `none`: the failure does not call for a plan change; continue/patch/rewind/abort suffices
- `add_task`: a new task should be inserted into the plan to cover a gap the
  original plan missed (e.g., a coverage gap for an endpoint, an integration
  step the framing phase did not anticipate)
- `tighten_acceptance`: an existing task's acceptance criteria should be
  strengthened so this failure mode is caught next time (e.g., adding a
  required regex_match or field_present check to an existing task)
- `other`: a different structural change would be needed (remove/replace/reorder)

This is a DIAGNOSTIC field. Your operative decision is the correction path
above; the plan-change candidate does not run anything. Pick the answer
that best describes what you would do if plan changes were available,
even if you have to extrapolate.

## Output Format

Return JSON with these fields:

- `correction_path` (string): one of `continue` / `patch` / `rewind` / `abort`
- `decision_rationale` (string): 2-3 sentence justification of `correction_path`
- `affected_task_types` (list[string]): task types affected by the decision
- `structural_plan_change_candidate` (string): one of `none` /
  `add_task` / `tighten_acceptance` / `other`
- `structural_plan_change_rationale` (string): 1-2 sentence justification
  of the plan-change candidate; explain what task would be added or what
  acceptance would be tightened. Empty string if candidate is `none`.

Return ONLY valid JSON, no markdown fences.
