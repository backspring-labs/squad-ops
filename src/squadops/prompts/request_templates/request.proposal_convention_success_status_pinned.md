---
template_id: request.proposal_convention_success_status_pinned
version: "1"
required_variables: []
---
**An endpoint's declared `success_status` is fixed in its frozen route.** A create declared `201`
returns `201` in every build. A criterion about that status asserts nothing new unless your
`manifest_delta` changes the endpoint's `success_status`.
