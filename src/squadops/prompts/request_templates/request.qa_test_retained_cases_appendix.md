---
template_id: request.qa_test_retained_cases_appendix
version: "1"
required_variables:
  - case_lines
  - case_count
optional_variables: []
---
**CASES A PREVIOUS ATTEMPT EXPOSED ({{case_count}}, from the test runner):**
{{case_lines}}

A previous suite for this task ran these cases against the application and they FAILED.
Whatever else your suite covers, it must still cover these — the same behaviour, asserted
at least as strictly. They are the evidence this task already has, and a suite that drops
them turns a found defect into a green run.

If you believe a case was wrong about the application's contract, keep a case for the same
behaviour and say in a comment above it what you changed and why. Do not silently omit one.
