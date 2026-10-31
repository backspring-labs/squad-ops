---
template_id: request.proposal_previous_verification
version: "1"
required_variables:
  - verification_source
  - verification_commit
  - check_lines
---
### The product's checks at commit `{{verification_commit}}`

Your change is compared with these results ({{verification_source}}). A check that passes here must
still pass after it, or the change is not accepted. A check already failing here is not yours to
fix unless your proposal says so. Where it lists finding keys, it is read key by key, and a key your
change adds blocks the change too:
{{check_lines}}
