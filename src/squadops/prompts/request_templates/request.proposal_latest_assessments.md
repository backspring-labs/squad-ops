---
template_id: request.proposal_latest_assessments
version: "1"
required_variables:
  - assessment_lines
---
**How the operator judged each expected result in this campaign.** Each line is the latest
assessment of one result: `met`, `not_met` or `unclear`, why, and for a shortfall whose work it is
(`app_work` is yours to reach). A `stale` one was made before an increment serving that result was
accepted, or before the result changed, so it may no longer hold. Two `conflicting` ones disagree and
neither replaces the other. An assessment doesn't decide whether your change is accepted:
{{assessment_lines}}
