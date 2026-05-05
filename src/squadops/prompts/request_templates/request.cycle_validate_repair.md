---
template_id: request.cycle_validate_repair
version: "1"
required_variables:
  - prd
  - role
  - failed_task_type
  - failure_summary
optional_variables:
  - expected_artifacts
  - acceptance_criteria
  - repair_summary
  - prior_outputs
---
## Validate Repair

You are validating the repair of a previously failed `{{failed_task_type}}` task. Your job is to decide whether the repair output satisfies the original acceptance criteria. Do not write a fresh QA strategy. Do not enumerate test cases for the whole project. Answer the specific question: was the failure fixed?

### Original Required Artifacts

{{expected_artifacts}}

### Original Acceptance Criteria

The repair must satisfy every criterion below.

{{acceptance_criteria}}

### Original Failure

{{failure_summary}}

### Repair Output

{{repair_summary}}

### Product Requirements Document

{{prd}}

{{prior_outputs}}

---

Produce a `repair_validation.md` document with this exact structure:

```
# Repair Validation

## Verdict
PASS or FAIL

## Per-Artifact Findings
For each required artifact: was it produced? If yes, does its content satisfy the original acceptance criteria? Cite the specific criterion and the specific content (or absence of content) that satisfies or violates it.

## Per-Criterion Findings
For each acceptance criterion: PASS or FAIL with one-line justification grounded in the repair output.

## Recommendation
If FAIL, name the specific gap that remains. If PASS, state which criteria were the close calls.
```

Be concrete. Do not produce a generic QA framework.
