---
template_id: request.proposal_outcome_goals
version: "1"
required_variables:
  - goal_lines
---

### The campaign's goals, as its evaluator last found them on this application

The campaign is judged by these goals. An evaluator checks each one against the running application,
apart from your criteria and their tests; you are shown what each goal is, not how it is checked.
`failed` means the evaluator checked it and it does not hold. `not verified` means the evaluator
could not check it on this application.

{{goal_lines}}

A goal that does not pass is a gap an increment can close. If your change is meant to make some of
them pass, list their ids, exactly as shown above, under a top-level `moves_goals:` key in your
`change_request.yaml`. After the build, the evaluator reads whether they moved. A change aimed at
none of them leaves the key out. An id not in the list above is refused.

Write your PRD text and your criteria in your own words. Every role that frames and builds your
change reads them, while the goals are the evaluator's: a request that repeats a goal's statement
word for word is refused.
