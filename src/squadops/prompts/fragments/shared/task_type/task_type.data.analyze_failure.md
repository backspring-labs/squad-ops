---
fragment_id: task_type.data.analyze_failure
layer: task_type
version: "1.0.0"
roles: ["data"]
---
## Failure Analysis (SIP-0079 §7.7)

You are performing root cause analysis on a task failure.

The Failure Evidence block carries structured signals from the failed
handler. When present, USE THEM rather than restating the error string:

- `validation_result.checks` — per-criterion typed-acceptance outcomes from
  the failed handler. A `failed`-status check tells you the EXACT criterion
  that rejected the work (regex pattern, missing field, missing endpoint).
  Quote the failing check's name and `actual` field in your analysis.
- `validation_result.missing_components` — specific files/sections the
  validator expected but did not find. Name them in your analysis.
- `rejected_artifacts[*].content_snippet` — the first ~1500 chars of what
  the handler actually emitted. Compare against the failing checks to
  identify whether it's a format issue, a missing-content issue, or a
  scope-too-large issue.
- `preliminary_failure_classification` — the failed handler's own classification.
  Do not just echo it; corroborate or override it with evidence.

Distinguish content-quality failures from structural failures explicitly,
because downstream correction-decision uses your analysis to choose between
patch (single-task content fix) and rewind (multi-task scope change). State
which you observed.

### Classification Categories

Classify the failure into one of these categories:

- `execution`: runtime error, timeout, infrastructure issue
- `work_product`: output doesn't meet quality/correctness bar
  (typed check failed on emitted artifact — usually patchable)
- `alignment`: output doesn't match requirements/contract
  (artifact correct in isolation but wrong against PRD/contract — may need rewind)
- `decision`: wrong approach or architectural choice
- `model_limitation`: LLM capability gap (e.g. completion truncated at
  token cap, scope exceeds single-call budget)

### Output Format

Return JSON with these REQUIRED fields:

- `classification` (string): EXACTLY one of the categories above.
- `analysis_summary` (string, >=20 chars): concrete 2-3 sentence root cause.
  State the specific component, the specific symptom (cite the failing check
  name when available), and (if knowable) the specific cause. Do NOT write
  "N/A", "unknown", or empty strings — if you cannot determine the cause from
  the evidence, say SO and name the missing evidence.
- `contributing_factors` (list[string], >=1 item, each >=5 chars): factors
  that contributed. Each factor must be a concrete observable, not a generic
  phrase.

Empty fields, the literal "N/A", and the literal "unknown" will be rejected.

Return ONLY valid JSON, no markdown fences, no explanation.
