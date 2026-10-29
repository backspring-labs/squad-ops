---
template_id: request.plan_increment_criteria_development_appendix
version: "1"
required_variables:
  - criterion_files_index
optional_variables: []
---

## Each new criterion is proven in its own test file, which a qa task writes

The approved change adds the criteria below. Each one is proven by a test in its **own** file, at
the path shown: the test fails on the accepted application and passes once the change is built.
The qa proposal plans the task that writes each file, so the files are qa's, not yours.

Leave these files out of your tasks' `expected_artifacts`, and plan no task that writes them. Plan
the code that makes each test pass instead: the files the change touches, in the tasks that change
them. A file named in a development task's `expected_artifacts` and a qa task's too is claimed
twice, and the plan gate refuses a plan with a file claimed twice.

{{criterion_files_index}}
