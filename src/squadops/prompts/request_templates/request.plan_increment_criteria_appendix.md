---
template_id: request.plan_increment_criteria_appendix
version: "2"
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

### What this increment's tests assert

Every test the plan asks for asserts what the approved change states: a criterion's statement and
its observable, or behaviour the change leaves as it was. Nothing more. A rule the change does not
state (a range of values refused, a validation message, a sort order, a limit) is not this plan's
to add. In any test it holds the build to a rule nobody approved. In a criterion's file it is
frozen with that criterion, and every later increment is held to it.

For example: a change that adds an optional `capacity` does not say what a capacity of `0` means.
A test that requires `0` to be refused, or to mean "already full", asserts a rule the change never
made, so leave it out. A test that a run created with `capacity: 8` comes back with `capacity: 8`
asserts what the change states.
