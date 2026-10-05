---
template_id: request.proposal_convention_unset_optional_unfixed
version: "1"
required_variables: []
---
**What an optional field a request leaves out comes back as is not fixed.** The frozen types only
mark the field optional (`field?: type`). Each build's handler decides whether the response leaves
it out, returns `null` or returns `""`, and stored builds of this stack do all three. So a criterion
does not depend on it: "a run created without a capacity has no capacity key" and "it returns
`"capacity": null`" each fail some correct build. If your change needs one answer, the criterion
states it as part of the change, for example "a run created without a capacity returns
`"capacity": null`".
