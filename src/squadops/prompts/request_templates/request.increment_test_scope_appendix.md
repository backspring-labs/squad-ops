---
template_id: request.increment_test_scope_appendix
version: "1"
required_variables:
  - scope_lines
---

## What this increment's tests may assert

A test asserts only behaviour that something accepted already requires: one of the criteria below
(its statement and its observable), or behaviour the accepted application already has and this
change leaves as it was. That holds for every test, in every file. A test outside a criterion's own
file still gates the build and can force a repair, so a rule nobody approved holds the build to it
wherever it lives.

Behaviour you think the application should have, but that nothing accepted requires, is not this
increment's to test. Leave it out of every test.

For example: a criterion says runs are listed in ascending order of their date. A test that two runs
with the same date keep the order they were created in asserts a rule the criterion never stated
(the 2.0 campaign froze exactly that test with the criterion, and every later increment was held to
it). So it is left out. A test that three runs with different dates come back in date order asserts
what the criterion states.

**The criteria this increment is held to:**
{{scope_lines}}
