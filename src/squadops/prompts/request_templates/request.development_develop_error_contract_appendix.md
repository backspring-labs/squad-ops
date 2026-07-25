---
template_id: request.development_develop_error_contract_appendix
version: "1"
required_variables:
  - error_lines
optional_variables: []
---
**ERROR CONTRACT (authoritative — apply exactly):**
{{error_lines}}

This is the scaffold's own error seam, generated from the interface manifest. The
frozen `backend/errors.py` owns the envelope shape and the code→status mapping — you
raise the code, it renders the response. Getting the raise wrong does not fail loudly
at generation: the call raises `TypeError` at request time and every error path
returns HTTP 500, which passes import- and compile-level checks and only surfaces
later as a behavioural test failure.
