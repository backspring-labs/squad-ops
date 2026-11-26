---
template_id: request.plan_test_runners_appendix
version: "1"
required_variables:
  - runners_index
optional_variables: []
---

## Where this product's tests live: a `qa.test` task names a file a runner collects

This product runs its tests with its own runners. A runner collects a file only when it is under
one of the runner's folders and its name matches the runner's pattern. A test file anywhere else
is run by nothing, so it verifies nothing.

Every file a `qa.test` task lists in `expected_artifacts` must be one a runner below collects, or
a support file listed below. A task that lists a product source file, a note, a new helper file,
or a test-named file outside every folder is refused at the plan gate and the framing is re-run.
Put what a suite's tests share in the test file itself, or in a support file the product already
has. Product source belongs to a `development.develop` task.

**What each runner collects** (`.` as a folder means anywhere in the repository):

{{runners_index}}
