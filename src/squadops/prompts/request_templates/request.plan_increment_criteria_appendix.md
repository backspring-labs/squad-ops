---
template_id: request.plan_increment_criteria_appendix
version: "3"
required_variables:
  - criterion_files_index
optional_variables: []
---

## Each new criterion is proven in its own test file

The approved change adds the criteria below. Each one is proven by a test in its **own** file, at
the path shown: the test fails on the accepted application and passes once the change is built,
and that file is kept as the criterion's verifier for every later increment. Put no other
criterion's tests in it.

Plan a qa task whose `expected_artifacts` include each of these files. A plan that leaves one
out is refused at the plan gate, and the framing is re-run.

{{criterion_files_index}}
