---
template_id: request.qa_test_repair_failing_cases_appendix
version: "2"
required_variables:
  - case_lines
  - case_count
optional_variables:
  - case_frames
---
**REPAIR SCOPE (authoritative — {{case_count}} failing case(s), from the test runner):**
{{case_lines}}

{{case_frames}}

Where a case is shown above, → marks the line the runner stopped on. The repair is on that
line or on what it rests on; the lines after it in the same case must hold too.

These are the only cases that failed; every other case in the file passed against the
application as it stands. Repair exactly these — fix the assertion, the setup or the
query that failed — and re-emit the file with the passing cases byte-for-byte unchanged.
Do not rename, reorder, drop or rewrite a passing case; do not add cases. A repair that
rewrites the whole file discards evidence the loop already has.
