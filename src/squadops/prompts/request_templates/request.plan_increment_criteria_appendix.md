---
template_id: request.plan_increment_criteria_appendix
version: "4"
required_variables:
  - criterion_files_index
optional_variables: []
---

## Each new criterion is proven in its own test file

The approved change adds the criteria below. Each one is proven by a test in its **own** file, at
the path shown: the test fails on the accepted application and passes once the change is built,
and that file is kept as the criterion's verifier for every later increment. Put no other
criterion's tests in it.

Plan a qa task whose `expected_artifacts` include each of these files. Each is written at exactly
the path shown, and no other file in the plan takes the same file name in another directory. For example, a second `test_criterion_T1.py` at the root, beside a listed
`tests/test_criterion_T1.py`, stops the product's test runner at collection, so none of its tests
run. A plan that leaves one out, or
repeats one's name elsewhere, is refused at the plan gate, and the framing is re-run.

{{criterion_files_index}}
