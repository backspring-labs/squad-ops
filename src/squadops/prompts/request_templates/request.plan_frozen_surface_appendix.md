---
template_id: request.plan_frozen_surface_appendix
version: "1"
required_variables:
  - frozen_surface_index
optional_variables: []
---
## The scaffold already wrote these files — they are frozen

Before any task runs, the build is expanded into a working skeleton. The files below
are **already written and cannot be changed by anyone**. An agent that emits one has its
emission discarded and the scaffold's version restored, every time.

This is not a rule to work around — it is what makes the rest of the plan safe. The
interfaces are settled before generation starts, so tasks can fill behaviour without
negotiating structure.

**Two things follow, and both matter.**

**Do not assign a frozen file as a task's `expected_artifacts`.** The task cannot produce
its own output. It will emit, be restored, and consume a slot for nothing.

**Do not write typed checks against a frozen file unless the line below proves it passes.**
A check on a frozen file has exactly two outcomes and neither is useful. If the scaffold
satisfies it, the check can never fail, so it verifies nothing. If the scaffold does not,
the plan is unwinnable: the task fails, the repair rewrites the file, the rewrite is
restored, and the check fails identically until the correction budget is gone. Plan
validation now runs these checks against the real skeleton before dispatch and rejects
the plan if one cannot pass — so a guess here costs the whole framing, not just the task.

**A file listed below with no declarations after its name may not be checked at all.**
The listing states what a frozen file declares only for languages this system can read
today; for the rest it can state that the file exists and nothing more. That is a limit of
the tooling, not evidence that the file is empty — so for those entries you have no line
proving anything passes, and the rule above applies with no exception available. Write your
check against a fill slot instead, or verify the behavior through the suite.

**What the frozen files actually declare:**

{{frozen_surface_index}}

Read that index literally. The names in it are the only names that exist. If a model
lists `location`, there is no `meeting_location`. If a module imports `` `.routes` ``,
then `backend.routes` is not what it imports. Field names, class names and import paths
are all exact — none of them are yours to choose, and near-misses fail as hard as
inventions.

Where the interface is not what the work needs, say so in prose in the task description.
Do not encode the disagreement as a check: the check will simply fail.
