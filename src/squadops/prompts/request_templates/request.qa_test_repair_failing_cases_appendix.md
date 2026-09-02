---
template_id: request.qa_test_repair_failing_cases_appendix
version: "1"
required_variables:
  - case_lines
  - case_count
optional_variables: []
---
**REPAIR SCOPE (authoritative — {{case_count}} failing case(s), from the test runner):**
{{case_lines}}

These are the only cases that failed; every other case in the file passed against the
application as it stands. Repair exactly these — fix the assertion, the setup or the
query that failed — and re-emit the file with the passing cases byte-for-byte unchanged.
Do not rename, reorder, drop or rewrite a passing case; do not add cases. A repair that
rewrites the whole file discards evidence the loop already has.
