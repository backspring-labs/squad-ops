---
template_id: request.plan_increment_frozen_appendix
version: "1"
required_variables:
  - frozen_files_index
optional_variables: []
---

## Earlier criteria's tests are frozen

The files below are the verifiers of criteria earlier increments added. Each is kept exactly as it
was frozen and run on this increment's build, to prove the earlier behaviour still holds.

No task may name one of these files in its `expected_artifacts`. A plan that does is refused at the
plan gate, and the framing is re-run. If this change makes an earlier behaviour obsolete, that is
for the change request to say (`retires`), not for a task to rewrite the test. Put this change's own
tests in the new criterion files listed above, or elsewhere in the test namespace.

{{frozen_files_index}}
